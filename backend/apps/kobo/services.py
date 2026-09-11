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
import json
import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.audit.utils import log_action
from apps.consent.services import has_given_consent
from apps.sampling.models import SampleCase

from .client import KoboClient
from .models import QAStatus, QUANSubmission, ReconciliationLog, ReconciliationTrigger


class KoboRedirectDenied(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


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
    """
    if not has_given_consent(sample_case):
        raise KoboRedirectDenied("consent_required", "Participation consent has not been given.")

    asset_uid = settings.KOBO_ASSET_UID
    params = {
        "master_id": sample_case.organisation.master_id,
        "sample_id": sample_case.sample_id,
        "invitation_wave": invitation_wave,
        "administration_mode": administration_mode,
        "respondent_role_category": respondent_role_category,
        "consent_status": "GIVEN",
        "consent_version": consent_version,
        "portal_token_id": str(token_id),
        "ra_id": ra_id,
    }
    query = "&".join(f"d[{key}]={value}" for key, value in params.items())
    return {
        "kobo_form_url": f"{settings.KOBO_API_BASE_URL}/x/{asset_uid}?{query}",
        "administration_mode": administration_mode,
    }


EXPECTED_HIDDEN_FIELDS = (
    "master_id",
    "sample_id",
    "invitation_wave",
    "administration_mode",
    "respondent_role_category",
)


def _parse_kobo_datetime(value):
    """Kobo timestamps arrive as ISO 8601 strings. Parse explicitly here
    rather than relying on the ORM's implicit str->datetime conversion on
    save -- that conversion only happens on the way to the database, so an
    in-memory model instance (as returned by .objects.create()) would
    otherwise still hold a raw string, breaking any code (e.g.
    qa.services.evaluate_submission's duplicate-window check) that does
    datetime arithmetic on it in the same request/task."""
    if not value:
        return None
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    return value


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
    (docs/11_KOBOTOOLBOX_INTEGRATION.md)."""
    run_started_at = timezone.now()
    submissions_pulled = new_submissions = updated_submissions = mismatches_flagged = 0

    client = KoboClient()
    raw_submissions = client.fetch_submissions()

    for payload in raw_submissions:
        submissions_pulled += 1
        kobo_uuid = payload.get("_uuid") or payload.get("meta/instanceID") or payload.get("_id")
        sample_id = payload.get("sample_id")

        try:
            sample_case = SampleCase.objects.get(sample_id=sample_id)
        except ObjectDoesNotExist:
            mismatches_flagged += 1
            log_action(
                "kobo.reconciliation_sample_id_mismatch",
                _MismatchStub(kobo_uuid),
                {"kobo_submission_uuid": kobo_uuid, "sample_id_in_payload": sample_id},
            )
            continue

        content_hash = _content_hash(payload)
        existing = QUANSubmission.objects.filter(kobo_submission_uuid=kobo_uuid).first()

        submission = None
        if existing is None:
            raw_payload_ref = _store_payload(kobo_uuid, payload)
            submission = QUANSubmission.objects.create(
                sample_case=sample_case,
                kobo_submission_uuid=kobo_uuid,
                administration_mode=payload.get("administration_mode", "01"),
                started_at=_parse_kobo_datetime(payload.get("start")),
                submitted_at=_parse_kobo_datetime(payload.get("_submission_time")) or run_started_at,
                raw_payload_ref=raw_payload_ref,
                payload_content_hash=content_hash,
                qa_status=QAStatus.PENDING,
            )
            new_submissions += 1
        elif existing.payload_content_hash != content_hash:
            raw_payload_ref = _store_payload(kobo_uuid, payload)
            existing.raw_payload_ref = raw_payload_ref
            existing.payload_content_hash = content_hash
            existing.last_edited_at = run_started_at
            # An edit re-enters QA review of the changed fields -- never
            # silently kept at whatever QA status it already had
            # (docs/11_KOBOTOOLBOX_INTEGRATION.md).
            existing.qa_status = QAStatus.PENDING
            existing.save(update_fields=[
                "raw_payload_ref", "payload_content_hash", "last_edited_at", "qa_status",
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
