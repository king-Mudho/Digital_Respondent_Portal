from django.db import models


class TokenStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    SENT = "SENT", "Sent"
    OPENED = "OPENED", "Opened"
    ELIGIBILITY_PASSED = "ELIGIBILITY_PASSED", "Eligibility passed"
    CONSENTED = "CONSENTED", "Consented"
    SURVEY_STARTED = "SURVEY_STARTED", "Survey started"
    SUBMITTED = "SUBMITTED", "Submitted"
    QA_PASSED = "QA_PASSED", "QA passed"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class Channel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    PRINTED_CODE = "PRINTED_CODE", "Printed code"
    QR = "QR", "QR code"


class InvitationToken(models.Model):
    """docs/10_INVITATION_AND_CONSENT.md: 32-byte CSPRNG token, base64url-
    encoded; only a salted SHA-256 hash is ever persisted (see
    invitations.services). Only the latest non-expired, non-revoked token
    for a SampleCase is valid -- issuing a new one supersedes rather than
    deletes the prior row, preserving the full audit trail.
    """

    sample_case = models.ForeignKey(
        "sampling.SampleCase", on_delete=models.PROTECT, related_name="invitation_tokens"
    )
    token_hash = models.CharField(max_length=128, unique=True)
    # A shorter, separately-issued 8-character alphanumeric code for
    # respondents who receive it by telephone or printed letter
    # (docs/10_INVITATION_AND_CONSENT.md) -- hashed the same way, never the
    # sole credential for a web link.
    manual_code_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(max_length=24, choices=TokenStatus.choices, default=TokenStatus.GENERATED)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    invitation_wave = models.PositiveIntegerField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"InvitationToken({self.sample_case_id}, {self.status})"
