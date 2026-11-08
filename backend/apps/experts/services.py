"""The ABI expert panel: registering experts, their personal links, consent, the questionnaire and completion.

Every step that would put the questionnaire in front of an expert goes through one gate here (AGENTS.md rule 6):
- an invitation is issued only once EXPERT_ETHICS_REFERENCE is set (the questionnaire and protocol are distributed
  "only after required approval") and while fewer than EXPERT_TARGET experts have completed;
- the questionnaire link (kobo_url) is built only after the expert's own participation consent is GIVEN, recorded on
  the portal.
The token pattern (32 random bytes, salted hash only, superseded on reissue, never moving backward) is the KII one.
"""

import hashlib
import hmac
import secrets
import string
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.utils import log_action
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import has_given_consent, record_consent

from . import instrument
from .models import ExpertInvitationToken, ExpertRecord, ExpertStatus, ExpertTokenStatus

CODE_ALPHABET = string.ascii_uppercase + string.digits
OPEN_TOKEN = (ExpertTokenStatus.GENERATED, ExpertTokenStatus.SENT, ExpertTokenStatus.OPENED, ExpertTokenStatus.CONSENTED,
              ExpertTokenStatus.STARTED)
TOKEN_ORDER = list(OPEN_TOKEN)


class ExpertError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


# --- Registering ---------------------------------------------------------------------------------------------------

def next_expert_id() -> str:
    numbers = [int(x[1:]) for x in ExpertRecord.objects.values_list("expert_id", flat=True) if x[1:].isdigit()]
    return f"E{(max(numbers, default=0) + 1):02d}"


@transaction.atomic
def create_expert(*, user=None, **fields) -> ExpertRecord:
    expert = ExpertRecord.objects.create(expert_id=next_expert_id(), created_by=user, **fields)
    log_action("expert.registered", expert, {"expert_id": expert.expert_id, "panel_area": expert.panel_area}, user=user)
    return expert


def completed_count() -> int:
    return ExpertRecord.objects.filter(status=ExpertStatus.COMPLETED).count()


def panel(target_by_area=None) -> list[dict]:
    """Each panel area with its target, how many are registered, invited, completed."""
    from .models import PanelArea

    targets = target_by_area or settings.EXPERT_PANEL_TARGETS
    rows = []
    for area in PanelArea:
        experts = ExpertRecord.objects.filter(panel_area=area)
        rows.append({"area": area.value, "label": area.label, "target": targets.get(area.value, 0),
                     "registered": experts.count(),
                     "invited": experts.exclude(status__in=[ExpertStatus.PROSPECT]).count(),
                     "completed": experts.filter(status=ExpertStatus.COMPLETED).count()})
    return rows


# --- Personal links ------------------------------------------------------------------------------------------------

def _hash(raw: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${hashlib.sha256((salt + raw).encode()).hexdigest()}"


def verify_secret(raw: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hashlib.sha256((salt + raw).encode()).hexdigest(), digest)


def invitations_open() -> str:
    """Why an invitation can't be issued now, or "" when it can."""
    if not (settings.EXPERT_ETHICS_REFERENCE or "").strip():
        return ("Expert invitations are closed until the ethics approval reference is recorded "
                "(EXPERT_ETHICS_REFERENCE): the questionnaire is distributed only after the required approval.")
    if completed_count() >= settings.EXPERT_TARGET:
        return f"The panel is complete: {settings.EXPERT_TARGET} experts have submitted the questionnaire."
    return ""


@transaction.atomic
def issue_invitation(expert: ExpertRecord, *, channel: str, issued_by=None) -> tuple[str, str, ExpertInvitationToken]:
    """A new personal link and code, replacing any still-open one. The raw values exist only in the return value and
    the message to the expert; never stored or logged."""
    blocked = invitations_open()
    if blocked:
        raise ExpertError("invitations_closed", blocked, 409)
    if expert.status in (ExpertStatus.COMPLETED, ExpertStatus.DECLINED):
        raise ExpertError("not_invitable", f"{expert.expert_id} has {expert.get_status_display().lower()}: no new link is sent.", 409)
    ExpertInvitationToken.objects.filter(expert=expert, status__in=OPEN_TOKEN).update(status=ExpertTokenStatus.EXPIRED)
    raw_token = secrets.token_urlsafe(getattr(settings, "INVITATION_TOKEN_BYTES", 32))
    raw_code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    now = timezone.now()
    token = ExpertInvitationToken.objects.create(
        expert=expert, token_hash=_hash(raw_token), manual_code_hash=_hash(raw_code), status=ExpertTokenStatus.SENT,
        channel=channel, issued_at=now, expires_at=now + timedelta(days=getattr(settings, "INVITATION_TOKEN_EXPIRY_DAYS", 14)),
        issued_by=issued_by)
    if expert.status == ExpertStatus.PROSPECT:
        expert.status = ExpertStatus.INVITED
        expert.save(update_fields=["status", "updated_at"])
    log_action("expert_invitation.issued", token, {"expert_id": expert.expert_id, "channel": channel,
                                                   "issued_by_id": getattr(issued_by, "id", None)}, user=issued_by)
    return raw_token, raw_code, token


def _check_open(token: ExpertInvitationToken) -> ExpertInvitationToken:
    if token.status == ExpertTokenStatus.REVOKED:
        raise ExpertError("token_revoked", "This invitation has been withdrawn.")
    if token.status == ExpertTokenStatus.EXPIRED or token.expires_at <= timezone.now():
        raise ExpertError("token_expired", "This invitation has expired.")
    advance_token(token, ExpertTokenStatus.OPENED)
    return token


def validate_token(raw: str) -> ExpertInvitationToken:
    for pk, stored in ExpertInvitationToken.objects.values_list("id", "token_hash").iterator():
        if verify_secret(raw or "", stored):
            return _check_open(ExpertInvitationToken.objects.select_related("expert").get(pk=pk))
    raise ExpertError("token_invalid", "This invitation link is not valid.")


def validate_code(raw: str) -> ExpertInvitationToken:
    for pk, stored in ExpertInvitationToken.objects.exclude(manual_code_hash=None).values_list("id", "manual_code_hash").iterator():
        if verify_secret((raw or "").upper(), stored):
            return _check_open(ExpertInvitationToken.objects.select_related("expert").get(pk=pk))
    raise ExpertError("token_invalid", "This invitation code is not valid.")


def advance_token(token: ExpertInvitationToken, new_status: str) -> ExpertInvitationToken:
    """Forward only, never off EXPIRED/REVOKED."""
    if token.status not in TOKEN_ORDER or new_status not in TOKEN_ORDER:
        return token
    if TOKEN_ORDER.index(new_status) <= TOKEN_ORDER.index(token.status):
        return token
    token.status = new_status
    fields = ["status"]
    if token.first_opened_at is None:
        token.first_opened_at = timezone.now()
        fields.append("first_opened_at")
    token.save(update_fields=fields)
    return token


def revoke(token: ExpertInvitationToken, reason: str, *, user=None) -> ExpertInvitationToken:
    token.status, token.revoked_at, token.revoked_reason = ExpertTokenStatus.REVOKED, timezone.now(), (reason or "")[:255]
    token.save(update_fields=["status", "revoked_at", "revoked_reason"])
    log_action("expert_invitation.revoked", token, {"expert_id": token.expert.expert_id, "reason": reason}, user=user)
    return token


# --- Consent and the questionnaire ---------------------------------------------------------------------------------

@transaction.atomic
def record_expert_consent(token: ExpertInvitationToken, *, decision: str, information_sheet_version: str):
    """The expert's own decision on the portal, by web click-through. GIVEN opens the questionnaire; DECLINED closes
    their record, and no reminder or new link follows."""
    if decision not in (ConsentDecision.GIVEN, ConsentDecision.DECLINED):
        raise ExpertError("invalid_input", "Choose whether you agree to take part.")
    expert = token.expert
    consent = record_consent(expert=expert, consent_type=ConsentType.PARTICIPATION, decision=decision,
                             information_sheet_version=information_sheet_version or instrument.INFORMATION_SHEET_VERSION,
                             method=ConsentMethod.WEB_CLICKTHROUGH)
    expert.participation_consent = consent
    if decision == ConsentDecision.GIVEN:
        advance_token(token, ExpertTokenStatus.CONSENTED)
        if expert.status in (ExpertStatus.PROSPECT, ExpertStatus.INVITED):
            expert.status = ExpertStatus.CONSENTED
    else:
        expert.status = ExpertStatus.DECLINED
    expert.save(update_fields=["participation_consent", "status", "updated_at"])
    return consent


def form_is_configured() -> bool:
    return bool((settings.KOBO_EXPERT_FORM_URL or "").strip())


def kobo_url(expert: ExpertRecord) -> str | None:
    """The questionnaire with the Expert ID filled in -- and nothing else about the person. None until the expert has
    given participation consent on the portal, or while the form isn't connected. The one gate every caller uses."""
    if not form_is_configured() or not has_given_consent(expert, ConsentType.PARTICIPATION):
        return None
    base = settings.KOBO_EXPERT_FORM_URL.strip().rstrip("/")
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}d[{instrument.EXPERT_ID_PATH}]={quote(expert.expert_id, safe='')}"


def open_questionnaire(token: ExpertInvitationToken) -> str:
    if not form_is_configured():
        raise ExpertError("kobo_not_configured", "The questionnaire isn't set up yet. Please contact the research team.", 503)
    url = kobo_url(token.expert)
    if url is None:
        raise ExpertError("consent_required", "Your consent is needed before the questionnaire opens.", 403)
    advance_token(token, ExpertTokenStatus.STARTED)
    return url


# --- Completion ----------------------------------------------------------------------------------------------------

def mark_completed_from_kobo(expert_ids) -> int:
    """A questionnaire in KoboToolbox carrying an expert's ID completes them -- only if they consented on the portal."""
    done = 0
    for expert in ExpertRecord.objects.filter(expert_id__in=set(expert_ids)).exclude(status=ExpertStatus.COMPLETED):
        if not has_given_consent(expert, ConsentType.PARTICIPATION):
            continue
        expert.status, expert.completed_at = ExpertStatus.COMPLETED, timezone.now()
        expert.save(update_fields=["status", "completed_at", "updated_at"])
        log_action("expert.completed", expert, {"expert_id": expert.expert_id}, user=None)
        done += 1
    return done
