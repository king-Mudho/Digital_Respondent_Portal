"""
Kobo redirect-URL construction and submission reconciliation.

FIELD-NAME ASSUMPTION (flagged in docs/27_AGENT_EXECUTION_PLAN.md "Open
questions"): docs/11_KOBOTOOLBOX_INTEGRATION.md requires the exact hidden-
field names, as they appear in the live Kobo form, to be frozen before
Phase 1 build -- this has not happened yet (no Kobo account is provisioned).
This module assumes the submission payload echoes back the same field names
used to populate the launch URL (master_id, sample_id, invitation_wave,
administration_mode, respondent_role_category, consent_status,
consent_version, portal_token_id, ra_id). Update EXPECTED_HIDDEN_FIELDS
below once the real Kobo form's field names are frozen against a real asset
-- do not assume this guess is correct in production.

EDIT DETECTION: rather than depend on any single Kobo metadata field for
"was this submission edited since we last saw it" (Kobo's exact edit-
tracking fields vary by deployment/version and are not part of the frozen
integration contract yet), reconciliation computes a content hash of the
full pulled payload each run and compares it to the previously stored hash.
Any change is treated as an edit -- robust regardless of which Kobo version
is eventually used, and satisfies the requirement that edited submissions
are never missed (docs/11_KOBOTOOLBOX_INTEGRATION.md).
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import timezone as dt_timezone
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.audit.models import AuditEvent
from apps.audit.utils import log_action
from apps.consent.services import has_given_consent
from apps.contacts.services import has_passed_eligibility
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import advance_token_status
from apps.sampling.models import SampleCase, WorkflowStatus
from apps.sampling.services import advance_case_on_respondent_event

from .client import KoboClient
from .models import QAStatus, QUANSubmission, ReconciliationLog, ReconciliationTrigger

logger = logging.getLogger(__name__)


class KoboRedirectDenied(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class KoboNotConfigured(Exception):
    """The KoboToolbox production form has not been connected yet.

    A state, not a failure. Until 2026-09-14 neither path checked for it:
    with KOBO_ASSET_UID empty (as in production), build_redirect_url()
    produced `.../x/?d[...]` -- a respondent who consented and tapped
    "Start the questionnaire" would have landed on Kobo's 404 page with no
    way back -- and the scheduled reconciliation called
    `/api/v2/assets//data/` every 15 minutes, writing 125 error rows and
    telling staff on the QA screen that sync had failed.
    """


def redirect_is_configured() -> bool:
    """The questionnaire link needs only the deployed form's public web link
    (KOBO_FORM_URL) -- not the API token, and not the asset UID, which is a
    different identifier on a different host."""
    return bool((settings.KOBO_FORM_URL or "").strip())


def reconciliation_is_configured() -> bool:
    """Pulling submissions needs the asset UID and an API token. Independent
    of the form link: the two are configured from different places in Kobo."""
    return bool((settings.KOBO_ASSET_UID or "").strip()) and bool((settings.KOBO_API_TOKEN or "").strip())


def build_redirect_url(
    sample_case: SampleCase,
    *,
    token_id,
    invitation_wave: int,
    administration_mode: str,
    respondent_role_category: str,
    consent_version: str,
    ra_id: str = "",
) -> dict:
    """GET /api/v1/kobo/redirect-url/ payload per docs/06_API_ARCHITECTURE.md.
    Never issued without a passed eligibility check and GIVEN participation
    consent (docs/10_INVITATION_AND_CONSENT.md) -- enforced here, the single
    point every caller goes through, not left to view-layer discipline.

    Both halves of that sentence are now actually checked. Until the
    Sep 2026 audit pass only consent was: the eligibility half was asserted
    in this docstring and in docs/28's Definition of Done ("an ineligible
    respondent is routed to referral, never to the questionnaire") but
    never enforced, so anyone holding a valid token could POST /consent/
    directly -- skipping the eligibility screen the frontend shows them --
    and be handed a questionnaire URL. The endpoint is AllowAny by design,
    so the frontend refusing to route there is not a control.
    """
    if not has_given_consent(sample_case):
        raise KoboRedirectDenied("consent_required", "Participation consent has not been given.")

    if not has_passed_eligibility(sample_case):
        raise KoboRedirectDenied(
            "eligibility_required",
            "No eligible respondent has been recorded for this case.",
        )

    # After the consent and eligibility gates, deliberately: those are
    # checked and refused on their own terms regardless of configuration.
    if not redirect_is_configured():
        raise KoboNotConfigured("The questionnaire form has not been connected yet.")

    form_url = settings.KOBO_FORM_URL.strip().rstrip("/")
    params = {
        "master_id": sample_case.organisation.master_id,
        "sample_id": sample_case.sample_id,
        "invitation_wave": invitation_wave,
        "administration_mode": administration_mode,
        "respondent_role_category": respondent_role_category,
        "consent_status": "GIVEN",
        "consent_version": consent_version,
        "portal_token_id": sign_portal_token(token_id, sample_case.sample_id),
        "ra_id": ra_id,
    }
    # Kobo's documented prefill syntax is ?d[<data column name>]=value
    # (support.kobotoolbox.org/data_through_webforms.html). Column names are
    # used as-is; if the hidden fields sit inside a group in the XLSForm, the
    # name must include the group path (e.g. group1/sample_id) -- keep them
    # at the top level. Values are percent-encoded.
    query = "&".join(f"d[{key}]={quote(str(value), safe='')}" for key, value in params.items())
    separator = "&" if "?" in form_url else "?"
    return {
        "kobo_form_url": f"{form_url}{separator}{query}",
        "administration_mode": administration_mode,
    }


EXPECTED_HIDDEN_FIELDS = (
    "master_id",
    "sample_id",
    "invitation_wave",
    "administration_mode",
    "respondent_role_category",
)

# The main-study XLSForm (ABF-FST_Main_Study_Questionnaire_v3.0_KOBO.xlsx,
# r2 2026-09-14) also works when opened without the portal link, e.g. an RA
# in KoboCollect. Then the hidden fields above are blank, and the form carries
# the Sample_ID the RA entered, and its own mode choice, in these top-level
# calculated fields instead.
FORM_SAMPLE_ID_FIELD = "SAMPLE_ID_FINAL"
FORM_MODE_FIELD = "ADMIN_MODE_FINAL"
FORM_MODE_TO_CODE = {
    "web_portal": "01",
    "telephone": "03",
    "whatsapp_assisted": "04",
    "face_to_face": "06",
}


def sign_portal_token(token_id, sample_id: str) -> str:
    """`<token id>.<signature>` for the questionnaire link's portal_token_id.

    The questionnaire accepts submissions without a Kobo login (respondents
    have none), so anyone holding the form's web link can submit it, typing
    any Sample_ID -- and Sample_IDs are sequential. The signature, which
    only this server can produce, is what shows a login-free submission
    really came through the portal for that case.
    """
    digest = hmac.new(
        f"{settings.SECRET_KEY}:kobo-portal-token".encode(), f"{token_id}:{sample_id}".encode(), hashlib.sha256,
    ).hexdigest()[:32]
    return f"{token_id}.{digest}"


def _submission_is_verified(payload: dict, sample_case: SampleCase) -> bool:
    """A submission is accepted for a case when either an authenticated Kobo
    user sent it (an interviewer in KoboCollect: Kobo records `_submitted_by`)
    or it carries the portal's signature for that case."""
    if payload.get("_submitted_by"):
        return True
    presented = str(payload.get("portal_token_id") or "")
    token_id, _, _ = presented.partition(".")
    return bool(token_id) and hmac.compare_digest(presented, sign_portal_token(token_id, sample_case.sample_id))


def _submission_identity(payload: dict) -> str | None:
    """The submission's stable identity across edits.

    KoboToolbox gives an edited submission a new `_uuid` (and instanceID);
    only `meta/rootUuid` stays the same for the life of the submission
    (support.kobotoolbox.org/editing_deleting_data.html). Keyed on `_uuid`,
    every edit arrived as a brand-new submission -- a duplicate in the QA
    queue, with the original never marked edited. Both forms of the value
    are normalised without the "uuid:" prefix.
    """
    for key in ("meta/rootUuid", "_uuid", "meta/instanceID"):
        value = payload.get(key)
        if value:
            return str(value).removeprefix("uuid:")
    return str(payload["_id"]) if payload.get("_id") is not None else None


def _payload_sample_id(payload: dict) -> str | None:
    return payload.get("sample_id") or payload.get(FORM_SAMPLE_ID_FIELD)


def _payload_administration_mode(payload: dict) -> str:
    if payload.get("administration_mode"):
        return payload["administration_mode"]
    return FORM_MODE_TO_CODE.get(payload.get(FORM_MODE_FIELD) or "", "01")


def _parse_kobo_datetime(value):
    """Kobo timestamps arrive as ISO 8601 strings. Parse explicitly here
    rather than relying on the ORM's implicit str->datetime conversion on
    save -- that conversion only happens on the way to the database, so an
    in-memory model instance (as returned by .objects.create()) would
    otherwise still hold a raw string, breaking any code (e.g.
    qa.services.evaluate_submission's duplicate-window check) that does
    datetime arithmetic on it in the same request/task.

    A timestamp without an offset is UTC. Kobo's `_submission_time` is sent
    that way (`2026-09-14T14:03:21`), while the form's own start/end carry
    the device offset. Reading the naive value in TIME_ZONE (Africa/Harare,
    UTC+2) filed every submission two hours early -- before the respondent
    had even opened the form. Found by the first production test submission,
    2026-09-14."""
    if not value:
        return None
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, dt_timezone.utc)
        return parsed
    return value


def _completion_seconds(payload: dict, submitted_at) -> int | None:
    """Time spent in the form: its own `end` minus `start` (both recorded by
    the device), falling back to the server's submission time. Was never set
    at all, so the QA duration rules could not fire and the QA queue showed
    "duration unknown" for every submission."""
    started = _parse_kobo_datetime(payload.get("start"))
    finished = _parse_kobo_datetime(payload.get("end")) or submitted_at
    if not started or not finished or finished < started:
        return None
    return int((finished - started).total_seconds())


def _advance_token_on_submission(sample_case: SampleCase, new_status: str) -> None:
    """Advance the case's current invitation token's funnel status
    (docs/10_INVITATION_AND_CONSENT.md's SENT -> OPENED -> ... -> SUBMITTED
    -> QA_PASSED progression). Kobo's own submission-time signal is the only
    place this system can observe SUBMITTED at all -- there is no separate
    "survey started but not submitted" event from reconciliation, so
    SURVEY_STARTED is never independently reached (advance_token_status's
    monotonic ordering handles skipping it without issue). A case with no
    live token yet (e.g. reconciliation running before any invitation was
    issued for it) is a no-op, not an error."""
    token = InvitationToken.objects.filter(sample_case=sample_case).order_by("-issued_at").first()
    if token is not None:
        advance_token_status(token, new_status)


def _content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _store_payload(kobo_submission_uuid: str, payload: dict) -> str:
    directory = os.path.join(settings.MEDIA_ROOT, "kobo_submissions")
    os.makedirs(directory, exist_ok=True)
    relative_path = os.path.join("kobo_submissions", f"{kobo_submission_uuid}.json")
    with open(os.path.join(settings.MEDIA_ROOT, relative_path), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return relative_path.replace("\\", "/")


def reconcile(triggered_by: str = ReconciliationTrigger.MANUAL) -> ReconciliationLog:
    """The actual source of truth for QUAN submission status -- never
    removed or "optimised away" in favour of webhook-only sync
    (docs/11_KOBOTOOLBOX_INTEGRATION.md).

    Raises KoboNotConfigured, and writes nothing, when there is no asset ID
    or API token: an unconnected form is not a failed sync, and recording
    it as one every 15 minutes buried any real failure in noise."""
    if not reconciliation_is_configured():
        raise KoboNotConfigured(
            "KoboToolbox is not connected yet: KOBO_ASSET_UID and KOBO_API_TOKEN must both be set."
        )

    run_started_at = timezone.now()
    submissions_pulled = new_submissions = updated_submissions = mismatches_flagged = 0

    client = KoboClient()
    try:
        raw_submissions = client.fetch_submissions()
    except requests.exceptions.RequestException as exc:
        # Kobo unreachable, timed out, or rejected the request (invalid
        # token/asset UID, 5xx, ...). Recorded as a failed run rather than
        # letting the exception propagate out of the Celery task (which
        # would just retry into the same failure silently) or the manual
        # "Sync now" endpoint (which would surface a raw 500).
        logger.warning("Kobo reconciliation run failed: %s", exc)
        return ReconciliationLog.objects.create(
            run_started_at=run_started_at,
            run_finished_at=timezone.now(),
            triggered_by=triggered_by,
            error_message=str(exc),
        )

    for payload in raw_submissions:
        submissions_pulled += 1
        kobo_uuid = _submission_identity(payload)
        sample_id = _payload_sample_id(payload)

        try:
            sample_case = SampleCase.objects.get(sample_id=sample_id)
        except ObjectDoesNotExist:
            mismatches_flagged += 1
            # Audited once per Kobo submission, not once per run. Every run
            # pulls the whole dataset, so an unmatched submission -- a stray
            # or spam entry on the public form, or one whose case was removed
            # -- otherwise added an AuditEvent every 15 minutes, indefinitely.
            if not AuditEvent.objects.filter(
                action="kobo.reconciliation_sample_id_mismatch", object_id=str(kobo_uuid)
            ).exists():
                log_action(
                    "kobo.reconciliation_sample_id_mismatch",
                    _MismatchStub(kobo_uuid),
                    {"kobo_submission_uuid": kobo_uuid, "sample_id_in_payload": sample_id},
                )
            continue

        if not _submission_is_verified(payload, sample_case):
            # Not from the portal link and not from a signed-in interviewer:
            # set aside, never matched to the case or put into QA.
            mismatches_flagged += 1
            if not AuditEvent.objects.filter(
                action="kobo.reconciliation_unverified_submission", object_id=str(kobo_uuid)
            ).exists():
                log_action(
                    "kobo.reconciliation_unverified_submission",
                    _MismatchStub(kobo_uuid),
                    {"kobo_submission_uuid": kobo_uuid, "sample_id_in_payload": sample_id},
                )
            continue

        content_hash = _content_hash(payload)
        existing = QUANSubmission.objects.filter(kobo_submission_uuid=kobo_uuid).first()

        submission = None
        if existing is None:
            raw_payload_ref = _store_payload(kobo_uuid, payload)
            submitted_at = _parse_kobo_datetime(payload.get("_submission_time")) or run_started_at
            submission = QUANSubmission.objects.create(
                sample_case=sample_case,
                kobo_submission_uuid=kobo_uuid,
                administration_mode=_payload_administration_mode(payload),
                started_at=_parse_kobo_datetime(payload.get("start")),
                submitted_at=submitted_at,
                completion_seconds=_completion_seconds(payload, submitted_at),
                raw_payload_ref=raw_payload_ref,
                payload_content_hash=content_hash,
                qa_status=QAStatus.PENDING,
            )
            new_submissions += 1
            _advance_token_on_submission(sample_case, TokenStatus.SUBMITTED)
            advance_case_on_respondent_event(sample_case, WorkflowStatus.S08_SURVEY_SUBMITTED)
        elif existing.payload_content_hash != content_hash:
            raw_payload_ref = _store_payload(kobo_uuid, payload)
            existing.raw_payload_ref = raw_payload_ref
            existing.payload_content_hash = content_hash
            existing.last_edited_at = run_started_at
            # An edit re-enters QA review of the changed fields -- never
            # silently kept at whatever QA status it already had
            # (docs/11_KOBOTOOLBOX_INTEGRATION.md).
            existing.qa_status = QAStatus.PENDING
            existing.completion_seconds = _completion_seconds(payload, existing.submitted_at)
            existing.save(update_fields=[
                "raw_payload_ref", "payload_content_hash", "last_edited_at", "qa_status", "completion_seconds",
            ])
            updated_submissions += 1
            submission = existing

        if submission is not None:
            # "On reconciliation, every new/updated QUANSubmission is
            # evaluated against every active QARuleThreshold"
            # (docs/15_QA_AND_DATA_QUALITY.md). Imported lazily to avoid a
            # kobo<->qa import cycle at module load time.
            from apps.qa.services import evaluate_submission

            evaluate_submission(submission)

    log = ReconciliationLog.objects.create(
        run_started_at=run_started_at,
        run_finished_at=timezone.now(),
        submissions_pulled=submissions_pulled,
        new_submissions=new_submissions,
        updated_submissions=updated_submissions,
        mismatches_flagged=mismatches_flagged,
        triggered_by=triggered_by,
    )
    return log


class _MismatchStub:
    """log_action() needs an object with a .pk; a mismatched submission has
    no SampleCase to attach the AuditEvent to, so this stands in as the
    audited "object" (object_type=_MismatchStub, object_id=the Kobo
    submission UUID) -- still queryable, never silently dropped."""

    def __init__(self, kobo_uuid):
        self.pk = kobo_uuid
