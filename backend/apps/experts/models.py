"""The ABI expert content-validation panel (Stage 1 of the ABI validation protocol, PI 8 Nov 2026).

Twelve experts rate the 16 candidate ABI indicators on the KoboToolbox questionnaire (apps/experts/instrument.py). The
portal registers each expert with their details, sends a personal link (WhatsApp, email), records their consent, opens
the questionnaire with their Expert ID filled in, and marks them complete when the submission arrives -- the same shape
as a KII informant (apps/kii), in its own models so the KII register and its counts never mix with the panel.

Identifiable contact and consent details stay here, with the authorised research team; the questionnaire carries only
the Expert ID (the protocol's "coded expert IDs, separate contact/consent files").
"""

from django.db import models

from apps.invitations.models import Channel


class PanelArea(models.TextChoices):
    """The protocol's panel composition (section 4.1), each with its target of the twelve (settings.EXPERT_PANEL_TARGETS)."""

    FINANCE = "FINANCE", "Agricultural banking, credit and development finance"
    AGRIBUSINESS = "AGRIBUSINESS", "Agribusiness management and value-chain operations"
    ECONOMICS = "ECONOMICS", "Agricultural economics and financing policy"
    METHODS = "METHODS", "Measurement, statistics and research methodology"
    FOOD_SYSTEMS = "FOOD_SYSTEMS", "Food systems, institutional policy and development"


class ExpertStatus(models.TextChoices):
    PROSPECT = "PROSPECT", "Prospect (not yet invited)"
    INVITED = "INVITED", "Invited"
    CONSENTED = "CONSENTED", "Consented"
    COMPLETED = "COMPLETED", "Completed"
    DECLINED = "DECLINED", "Declined"


class ExpertRecord(models.Model):
    expert_id = models.CharField(max_length=8, unique=True, editable=False)  # E01, E02, ... -- all the form ever sees
    full_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)  # position / designation
    institution = models.CharField(max_length=255, blank=True)
    institution_category = models.CharField(max_length=32, blank=True)  # instrument.INSTITUTION codes
    panel_area = models.CharField(max_length=16, choices=PanelArea.choices)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=255, blank=True)
    whatsapp_number = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    conflicts_note = models.TextField(blank=True)  # the protocol's documented conflict-of-interest disclosure
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=ExpertStatus.choices, default=ExpertStatus.PROSPECT)
    round = models.PositiveSmallIntegerField(default=1)
    participation_consent = models.ForeignKey("consent.ConsentRecord", null=True, blank=True, on_delete=models.SET_NULL,
                                              related_name="expert_participation_records")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expert_id"]

    def __str__(self):
        return f"{self.expert_id} — {self.full_name}"


class ExpertTokenStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    SENT = "SENT", "Sent"
    OPENED = "OPENED", "Opened"
    CONSENTED = "CONSENTED", "Consented"
    STARTED = "STARTED", "Questionnaire opened"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class ExpertInvitationToken(models.Model):
    """An expert's personal link: 32 random bytes, only a salted hash kept -- the KII token's pattern
    (kii.KIIInvitationToken), in its own table."""

    expert = models.ForeignKey(ExpertRecord, on_delete=models.PROTECT, related_name="invitation_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    manual_code_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(max_length=16, choices=ExpertTokenStatus.choices, default=ExpertTokenStatus.GENERATED)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    first_opened_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True)
    issued_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"ExpertInvitationToken({self.expert_id}, {self.status})"
