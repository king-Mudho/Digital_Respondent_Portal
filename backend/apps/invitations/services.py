"""
Invitation token lifecycle: generation, hashing, validation, expiry,
single-valid-token supersession, revocation. This is the entire access-
control boundary for the public respondent flow
(docs/10_INVITATION_AND_CONSENT.md, docs/08_BACKEND_ARCHITECTURE.md) --
"a pure, independently unit-testable module, since its correctness is the
entire access-control boundary."

The raw token is never persisted -- only a salted SHA-256 hash
(InvitationToken.token_hash). It must never be logged; callers must not pass
it to logging/audit metadata (see docs/10_INVITATION_AND_CONSENT.md).
"""

import hashlib
import hmac
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.utils import log_action
from apps.sampling.models import SampleCase, SampleType, WorkflowStatus
from apps.sampling.services import is_invitable, transition_workflow_status

from .models import Channel, InvitationToken, TokenStatus

MANUAL_CODE_ALPHABET = string.ascii_uppercase + string.digits
MANUAL_CODE_LENGTH = 8


class TokenNotInvitable(Exception):
    """Raised when attempting to issue a token for a case that fails
    sampling.services.is_invitable() -- e.g. a locked Reserve case."""


class TokenValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _hash_secret(raw: str) -> str:
    """Salted SHA-256, stored as "<salt_hex>$<digest_hex>"."""
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
def issue_invitation(
    sample_case: SampleCase,
    *,
    channel: str = Channel.WHATSAPP,
    invitation_wave: int = 1,
    issued_by=None,
) -> tuple[str, str, InvitationToken]:
    """Issue a new invitation token for a SampleCase, superseding (expiring)
    any still-open prior token for the same case. Returns
    (raw_token, raw_manual_code, InvitationToken instance) -- the raw values
    exist only in this return value and the message sent to the respondent;
    never store or log them.

    Raises TokenNotInvitable if sampling.services.is_invitable() is False --
    AGENTS.md ground rule 4: every invitation-issuing code path must go
    through is_invitable(), never check SampleCase.status inline.
    """
    if not is_invitable(sample_case):
        log_action(
            "invitations.issue_denied_not_invitable",
            sample_case,
            {"sample_type": sample_case.sample_type, "status": sample_case.status},
        )
        raise TokenNotInvitable(f"SampleCase {sample_case.sample_id} is not invitable.")

    # Supersede any still-open prior token for this case (docs/10: "issuing a
    # new token automatically expires any still-open prior token").
    InvitationToken.objects.filter(
        sample_case=sample_case,
        status__in=[TokenStatus.GENERATED, TokenStatus.SENT, TokenStatus.OPENED],
    ).update(status=TokenStatus.EXPIRED)

    token_bytes = getattr(settings, "INVITATION_TOKEN_BYTES", 32)
    expiry_days = getattr(settings, "INVITATION_TOKEN_EXPIRY_DAYS", 14)

    raw_token = secrets.token_urlsafe(token_bytes)
    raw_manual_code = _generate_manual_code()
    now = timezone.now()

    token = InvitationToken.objects.create(
        sample_case=sample_case,
        token_hash=_hash_secret(raw_token),
        manual_code_hash=_hash_secret(raw_manual_code),
        status=TokenStatus.GENERATED,
        channel=channel,
        invitation_wave=invitation_wave,
        issued_at=now,
        expires_at=now + timedelta(days=expiry_days),
    )
    log_action(
        "invitation.issued",
        token,
        {"sample_id": sample_case.sample_id, "channel": channel, "issued_by_id": getattr(issued_by, "id", None)},
    )
    _advance_to_invitation_sent(sample_case)
    return raw_token, raw_manual_code, token


def _advance_to_invitation_sent(sample_case: SampleCase) -> None:
    """Issuing an invitation is what actually sends it, so drive the S00-S16
    workflow status forward to S05 (Invitation sent) -- without this,
    nothing ever moves a case off S03/S04, and the reminder sequence
    (messaging.services) would have no cases to act on. A resend to a case
    already past S05 (opened/started/etc.) must never regress its status,
    so this only acts on MAIN cases still at S03 or S04."""
    if sample_case.sample_type != SampleType.MAIN:
        return
    if sample_case.workflow_status == WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED:
        transition_workflow_status(sample_case, WorkflowStatus.S04_INVITATION_PREPARED)
    if sample_case.workflow_status == WorkflowStatus.S04_INVITATION_PREPARED:
        transition_workflow_status(sample_case, WorkflowStatus.S05_INVITATION_SENT)


def _validate_common(token: InvitationToken) -> None:
    if token.status == TokenStatus.REVOKED:
        raise TokenValidationError("token_revoked", "This invitation has been revoked.")
    if token.status == TokenStatus.EXPIRED or token.expires_at <= timezone.now():
        raise TokenValidationError("token_expired", "This invitation has expired.")


def validate_token(raw_token: str) -> InvitationToken:
    """Resolve and validate a raw token from the URL. Never lists or exposes
    any other case (docs/06_API_ARCHITECTURE.md "Security").

    Searches every token, not just currently-active ones, so a revoked or
    expired token still resolves to its own row -- giving the respondent a
    specific, correct reason (token_revoked/token_expired) instead of a
    generic "not found" that would also match a token that never existed.
    At the documented scale ("a few hundred live tokens at any time",
    docs/10_INVITATION_AND_CONSENT.md) a full-table hash comparison is not a
    performance concern.
    """
    for token in InvitationToken.objects.select_related("sample_case").all():
        if _verify_secret(raw_token, token.token_hash):
            _validate_common(token)
            return token
    raise TokenValidationError("token_invalid", "This invitation link is not valid.")


def validate_manual_code(raw_code: str) -> InvitationToken:
    for token in InvitationToken.objects.select_related("sample_case").filter(
        manual_code_hash__isnull=False
    ):
        if _verify_secret(raw_code.upper(), token.manual_code_hash):
            _validate_common(token)
            return token
    raise TokenValidationError("token_invalid", "This invitation code is not valid.")


def revoke_token(token: InvitationToken, reason: str, *, revoked_by=None) -> InvitationToken:
    token.status = TokenStatus.REVOKED
    token.revoked_at = timezone.now()
    token.revoked_reason = reason
    token.save(update_fields=["status", "revoked_at", "revoked_reason"])
    log_action(
        "invitation.revoked",
        token,
        {"reason": reason, "revoked_by_id": getattr(revoked_by, "id", None)},
    )
    return token


def advance_token_status(token: InvitationToken, new_status: str) -> InvitationToken:
    """Monotonically advance token.status (e.g. OPENED -> ELIGIBILITY_PASSED
    -> CONSENTED -> ...) as the respondent progresses through the flow."""
    token.status = new_status
    token.save(update_fields=["status"])
    return token
