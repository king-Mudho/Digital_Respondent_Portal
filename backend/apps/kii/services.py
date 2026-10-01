"""
KII scheduling, consent gating and status-flow transitions
(docs/13_KII_MODULE.md). Status flow: PROSPECT (identified in the sampling
frame, not yet approached) -> INVITED -> SCHEDULED -> COMPLETED (or
DECLINED/NO_SHOW), independent of transcript_status and coding_status,
which progress after the interview itself is complete. INVITED -> COMPLETED
directly is also allowed (2026-10-01), for a self-administered interview
with no call to schedule -- see the KII self-service invitation section
below.
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
from apps.consent.models import ConsentType
from apps.consent.services import has_given_consent
from apps.invitations.models import Channel
from apps.sampling.services import next_sequence

from .models import CodingStatus, KIIInvitationToken, KIIInvitationTokenStatus, KIIRecord, KIIStatus, TranscriptStatus


def generate_kii_id() -> str:
    """KII-<sequence(4)>, e.g. KII-0042. System-generated, never user-entered,
    same DB-sequence approach as Master_ID/Sample_ID (docs/09_IDENTIFIER_
    AND_SAMPLING_CONTROL.md)."""
    seq = next_sequence("KII_ID")
    return f"KII-{seq:04d}"


def create_kii_record(**fields) -> KIIRecord:
    record = KIIRecord(kii_id=generate_kii_id(), **fields)
    record.full_clean()
    record.save()
    return record


KII_STATUS_TRANSITIONS = {
    # COMPLETED direct from INVITED: a self-administered interview (see
    # KIIInvitationToken below) has no call to schedule -- an RA marks it
    # completed once the KoboToolbox submission arrives, the same COMPLETED
    # button as the interviewer-administered path, just not forced through
    # SCHEDULED first.
    KIIStatus.PROSPECT: {KIIStatus.INVITED, KIIStatus.DECLINED},
    KIIStatus.INVITED: {KIIStatus.SCHEDULED, KIIStatus.DECLINED, KIIStatus.COMPLETED},
    KIIStatus.SCHEDULED: {KIIStatus.COMPLETED, KIIStatus.NO_SHOW, KIIStatus.DECLINED},
    KIIStatus.COMPLETED: set(),
    KIIStatus.DECLINED: set(),
    KIIStatus.NO_SHOW: {KIIStatus.SCHEDULED},  # can be rescheduled
}


class InvalidKIITransition(Exception):
    pass


class KIIRecordingConsentRequired(Exception):
    pass


def transition_kii_status(record: KIIRecord, new_status: str) -> KIIRecord:
    allowed = KII_STATUS_TRANSITIONS.get(record.status, set())
    if new_status not in allowed:
        raise InvalidKIITransition(f"Cannot transition {record.status} -> {new_status}.")
    record.status = new_status
    record.save(update_fields=["status"])
    log_action("kii.status_changed", record, {"new_status": new_status})
    return record


def mark_completed(record: KIIRecord, *, with_recording: bool) -> KIIRecord:
    """Recording consent is always a separate, explicit decision from
    participation consent (AGENTS.md ground rule 6) -- a KII cannot be
    marked completed with a recording unless that separate consent was
    given."""
    if with_recording and not has_given_consent(record, ConsentType.KII_RECORDING):
        raise KIIRecordingConsentRequired("Recording consent was not given for this KII.")

    return transition_kii_status(record, KIIStatus.COMPLETED)


def advance_transcript_status(record: KIIRecord, new_status: str) -> KIIRecord:
    order = [TranscriptStatus.NOT_STARTED, TranscriptStatus.IN_PROGRESS, TranscriptStatus.VERIFIED, TranscriptStatus.ANONYMISED]
    if order.index(new_status) < order.index(record.transcript_status):
        raise InvalidKIITransition("Transcript status cannot move backwards.")
    record.transcript_status = new_status
    record.save(update_fields=["transcript_status"])
    return record


def advance_coding_status(record: KIIRecord, new_status: str) -> KIIRecord:
    order = [CodingStatus.NOT_STARTED, CodingStatus.IN_PROGRESS, CodingStatus.COMPLETE]
    if order.index(new_status) < order.index(record.coding_status):
        raise InvalidKIITransition("Coding status cannot move backwards.")
    if new_status == CodingStatus.COMPLETE and record.coding_status != CodingStatus.COMPLETE:
        # Coding is complete only once the pre-interview profile (if the interview had one) is reconciled.
        from apps.proit.services import reconciliation_blocker

        blocker = reconciliation_blocker(kii_record=record)
        if blocker:
            raise InvalidKIITransition(blocker)
    record.coding_status = new_status
    record.save(update_fields=["coding_status"])
    return record


# --- KoboToolbox KII Guide: prefilled interview link ------------------------

def kii_form_is_configured() -> bool:
    return bool((settings.KOBO_KII_FORM_URL or "").strip())


def build_kii_coding_url(record: KIIRecord) -> str | None:
    """Prefills the KoboToolbox Main Study KII Guide with this record's
    KII-ID, so a KII RA doesn't retype it and a typo can't make the
    completed interview fail to match back up with this record
    (docs/13_KII_MODULE.md), the same ?d[<data column>]=value mechanism as
    the other two forms (apps/kobo/services.py, apps/evidence/services.py).

    Deliberately narrower than the document coding link: a KIIRecord
    identifies a real person, so nothing participant-identifying
    (participant_name, organisation, role) goes into the URL -- only the
    system-generated ID and the interviewer's own username, mirroring
    apps/kobo/services.py build_redirect_url()'s minimal-identifiers
    pattern for the respondent questionnaire link. And unlike a document,
    the link is withheld entirely until participation consent is GIVEN --
    there is no legitimate reason to open the interview instrument on
    someone before they have consented to take part.

    Returns None when KOBO_KII_FORM_URL isn't set, or when participation
    consent hasn't been given yet.
    """
    if not kii_form_is_configured():
        return None
    if not has_given_consent(record, ConsentType.PARTICIPATION):
        return None
    form_url = settings.KOBO_KII_FORM_URL.strip().rstrip("/")
    fields = {"part_a/KII_ID": record.kii_id}
    if record.interviewer_id and record.interviewer.username:
        fields["part_a/interviewer_code"] = record.interviewer.username
    if record.interview_date:
        fields["part_a/interview_date"] = record.interview_date.isoformat()
    query = "&".join(f"d[{key}]={quote(str(value), safe='')}" for key, value in fields.items() if value)
    separator = "&" if "?" in form_url else "?"
    return f"{form_url}{separator}{query}"


# --- KII self-service invitation link (2026-10-01) ---------------------------
#
# A KII informant's own personal link, opened unsupervised (WhatsApp/email), the
# same way a Main-400 respondent already can. Mirrors apps.invitations.services'
# crypto/lifecycle pattern (32-byte CSPRNG token, salted-SHA256-hash-only
# storage, supersession on reissue, monotonic status) but as a dedicated model
# (KIIInvitationToken) and dedicated functions, not a shared import -- see
# KIIInvitationToken's docstring for why. The raw token is never persisted and
# must never be logged, same rule as the Main-400 token.

MANUAL_CODE_ALPHABET = string.ascii_uppercase + string.digits
MANUAL_CODE_LENGTH = 8


class KIITokenValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _hash_secret(raw: str) -> str:
    """Salted SHA-256, stored as "<salt_hex>$<digest_hex>" -- same scheme as
    apps.invitations.services._hash_secret, duplicated rather than imported
    (that function is private to its own module)."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + raw).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _verify_secret(raw: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    expected = hashlib.sha256((salt + raw).encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, digest)


def _generate_manual_code() -> str:
    return "".join(secrets.choice(MANUAL_CODE_ALPHABET) for _ in range(MANUAL_CODE_LENGTH))


@transaction.atomic
def issue_kii_invitation(
    kii_record: KIIRecord,
    *,
    channel: str = Channel.WHATSAPP,
    issued_by=None,
) -> tuple[str, str, KIIInvitationToken]:
    """Issue a new self-service token for a KII record, superseding any
    still-open prior token for the same record. Returns (raw_token,
    raw_manual_code, KIIInvitationToken) -- the raw values exist only in this
    return value and the message sent to the informant; never store or log
    them."""
    KIIInvitationToken.objects.filter(
        kii_record=kii_record,
        status__in=[
            KIIInvitationTokenStatus.GENERATED, KIIInvitationTokenStatus.SENT,
            KIIInvitationTokenStatus.OPENED, KIIInvitationTokenStatus.CONSENTED,
            KIIInvitationTokenStatus.STARTED,
        ],
    ).update(status=KIIInvitationTokenStatus.EXPIRED)

    token_bytes = getattr(settings, "INVITATION_TOKEN_BYTES", 32)
    expiry_days = getattr(settings, "INVITATION_TOKEN_EXPIRY_DAYS", 14)

    raw_token = secrets.token_urlsafe(token_bytes)
    raw_manual_code = _generate_manual_code()
    now = timezone.now()

    token = KIIInvitationToken.objects.create(
        kii_record=kii_record,
        token_hash=_hash_secret(raw_token),
        manual_code_hash=_hash_secret(raw_manual_code),
        status=KIIInvitationTokenStatus.SENT,
        channel=channel,
        issued_at=now,
        expires_at=now + timedelta(days=expiry_days),
    )
    log_action(
        "kii_invitation.issued",
        token,
        {"kii_id": kii_record.kii_id, "channel": channel, "issued_by_id": getattr(issued_by, "id", None)},
        user=issued_by,
    )
    return raw_token, raw_manual_code, token


def _validate_kii_common(token: KIIInvitationToken) -> None:
    if token.status == KIIInvitationTokenStatus.REVOKED:
        raise KIITokenValidationError("token_revoked", "This invitation has been revoked.")
    if token.status == KIIInvitationTokenStatus.EXPIRED or token.expires_at <= timezone.now():
        raise KIITokenValidationError("token_expired", "This invitation has expired.")
    _advance_kii_token_status(token, KIIInvitationTokenStatus.OPENED)


def validate_kii_token(raw_token: str) -> KIIInvitationToken:
    """Resolve and validate a raw KII self-service token. Never lists or
    exposes any other record -- same linear-scan-over-hashes approach as
    apps.invitations.services.validate_token, acceptable at the same small
    scale (a KII informant pool is smaller still)."""
    for token_id, token_hash in KIIInvitationToken.objects.values_list("id", "token_hash").iterator():
        if _verify_secret(raw_token, token_hash):
            token = KIIInvitationToken.objects.select_related("kii_record").get(pk=token_id)
            _validate_kii_common(token)
            return token
    raise KIITokenValidationError("token_invalid", "This invitation link is not valid.")


def validate_kii_manual_code(raw_code: str) -> KIIInvitationToken:
    rows = KIIInvitationToken.objects.filter(manual_code_hash__isnull=False).values_list("id", "manual_code_hash")
    for token_id, code_hash in rows.iterator():
        if _verify_secret(raw_code.upper(), code_hash):
            token = KIIInvitationToken.objects.select_related("kii_record").get(pk=token_id)
            _validate_kii_common(token)
            return token
    raise KIITokenValidationError("token_invalid", "This invitation code is not valid.")


def revoke_kii_invitation(token: KIIInvitationToken, reason: str, *, revoked_by=None) -> KIIInvitationToken:
    token.status = KIIInvitationTokenStatus.REVOKED
    token.revoked_at = timezone.now()
    token.revoked_reason = reason
    token.save(update_fields=["status", "revoked_at", "revoked_reason"])
    log_action(
        "kii_invitation.revoked",
        token,
        {"reason": reason, "revoked_by_id": getattr(revoked_by, "id", None)},
    )
    return token


# EXPIRED/REVOKED excluded -- set only by issue_kii_invitation's supersession
# and revoke_kii_invitation(), never through this function.
_KII_TOKEN_STATUS_ORDER = [
    KIIInvitationTokenStatus.GENERATED,
    KIIInvitationTokenStatus.SENT,
    KIIInvitationTokenStatus.OPENED,
    KIIInvitationTokenStatus.CONSENTED,
    KIIInvitationTokenStatus.STARTED,
]


def _advance_kii_token_status(token: KIIInvitationToken, new_status: str) -> KIIInvitationToken:
    """Monotonic, same reasoning as apps.invitations.services.advance_token_status:
    never moves backward, never off a terminal EXPIRED/REVOKED status."""
    if token.status in (KIIInvitationTokenStatus.EXPIRED, KIIInvitationTokenStatus.REVOKED):
        return token
    try:
        current_index = _KII_TOKEN_STATUS_ORDER.index(token.status)
        new_index = _KII_TOKEN_STATUS_ORDER.index(new_status)
    except ValueError:
        current_index = new_index = None
    if current_index is not None and new_index is not None and new_index <= current_index:
        return token
    token.status = new_status
    token.save(update_fields=["status"])
    return token
