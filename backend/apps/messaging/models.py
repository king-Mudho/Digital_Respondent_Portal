from django.db import models


class MessageChannel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"


class TemplateCategory(models.TextChoices):
    """WhatsApp Business Platform category -- UTILITY only for this portal,
    never MARKETING (docs/12_CONTACT_CRM_AND_MESSAGING.md)."""

    UTILITY = "UTILITY", "Utility"
    MARKETING = "MARKETING", "Marketing"
    AUTHENTICATION = "AUTHENTICATION", "Authentication"


class MetaApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class MessageTemplate(models.Model):
    name = models.CharField(max_length=128, unique=True)
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    category = models.CharField(max_length=16, choices=TemplateCategory.choices, default=TemplateCategory.UTILITY)
    meta_approval_status = models.CharField(
        max_length=16, choices=MetaApprovalStatus.choices, null=True, blank=True
    )
    body = models.TextField()

    def __str__(self):
        return self.name


class MessageStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"


class MessageLog(models.Model):
    sample_case = models.ForeignKey(
        "sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE, related_name="message_logs"
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE, related_name="message_logs"
    )
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="logs")
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=MessageStatus.choices, default=MessageStatus.QUEUED)
    # Null only for the approved automated reminder sequence -- every other
    # outbound message is triggered by an RA action and recorded against
    # them (docs/08_BACKEND_ARCHITECTURE.md, docs/12_CONTACT_CRM_AND_MESSAGING.md).
    triggered_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="triggered_messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReminderSequenceStep(models.Model):
    """Config-driven reminder cadence (AGENTS.md ground rule 7) -- default
    Day 0/2/4-5/7 sequence per docs/12_CONTACT_CRM_AND_MESSAGING.md, seeded
    via migration, adjustable via Django admin without a redeploy."""

    day_offset = models.PositiveIntegerField(unique=True)
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="sequence_steps")
    label = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["day_offset"]

    def __str__(self):
        return f"Day {self.day_offset}: {self.label or self.template.name}"


class MessagePurpose(models.TextChoices):
    INVITATION = "INVITATION", "Invitation"
    REMINDER = "REMINDER", "Reminder"
    INTRODUCTION = "INTRODUCTION", "Introduction (ask first)"
    REPLY = "REPLY", "Reply in a conversation"


class ProviderStatus(models.TextChoices):
    """Twilio's delivery states, as its status callback reports them."""

    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    READ = "READ", "Read"
    UNDELIVERED = "UNDELIVERED", "Not delivered"
    FAILED = "FAILED", "Failed"


class ProviderMessage(models.Model):
    """One SMS or WhatsApp message the portal sent itself, through Twilio (apps/messaging/twilio_client.py,
    2026-10-07), and what Twilio says happened to it. An invitation sent by hand from the study phone has no row here:
    only the portal's own sends can be followed to the handset.

    Only a masked number is kept: the full number stays on the Respondent / KII record it came from."""

    sample_case = models.ForeignKey("sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE, related_name="provider_messages")
    kii_record = models.ForeignKey("kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE, related_name="provider_messages")
    invitation_token = models.ForeignKey("invitations.InvitationToken", null=True, blank=True, on_delete=models.SET_NULL, related_name="provider_messages")
    kii_invitation_token = models.ForeignKey("kii.KIIInvitationToken", null=True, blank=True, on_delete=models.SET_NULL, related_name="provider_messages")
    message_log = models.OneToOneField(MessageLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="provider_message")
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    purpose = models.CharField(max_length=16, choices=MessagePurpose.choices)
    provider_sid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    to_masked = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=ProviderStatus.choices, default=ProviderStatus.QUEUED)
    error_code = models.CharField(max_length=16, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    segments = models.PositiveSmallIntegerField(null=True, blank=True)
    sent_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ProviderMessage({self.channel} {self.purpose} {self.status})"


class OutreachStatus(models.TextChoices):
    INTRO_SENT = "INTRO_SENT", "Asked"
    REMINDED = "REMINDED", "Asked again"
    ACCEPTED = "ACCEPTED", "Said yes: link sent"
    DECLINED = "DECLINED", "Said no"
    NO_REPLY = "NO_REPLY", "No reply"
    NOT_DELIVERED = "NOT_DELIVERED", "Could not be delivered"


OPEN_OUTREACH = [OutreachStatus.INTRO_SENT, OutreachStatus.REMINDED]


class Outreach(models.Model):
    """One "ask first" introduction to a case (apps/messaging/outreach.py, 2026-10-07): a message about the study asking
    the organisation to take part. A YES reply on WhatsApp issues the invitation and sends its link back in the same
    chat; a NO records the refusal.

    The number is kept as a keyed hash (to recognise replies) and a masked copy (to show): the number itself stays
    only on the Respondent record it came from."""

    sample_case = models.ForeignKey("sampling.SampleCase", on_delete=models.CASCADE, related_name="outreaches")
    respondent = models.ForeignKey("contacts.Respondent", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invitation_token = models.ForeignKey("invitations.InvitationToken", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=16, choices=OutreachStatus.choices, default=OutreachStatus.INTRO_SENT)
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    number_hash = models.CharField(max_length=64, db_index=True)
    number_masked = models.CharField(max_length=32)
    intro_sent_at = models.DateTimeField()
    reminded_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    sms_fallback_sent = models.BooleanField(default=False)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-intro_sent_at"]

    def __str__(self):
        return f"Outreach({self.sample_case_id} {self.status})"


class ReplyKind(models.TextChoices):
    YES = "YES", "Yes"
    NO = "NO", "No"
    OTHER = "OTHER", "Other"


class InboundMessage(models.Model):
    """A WhatsApp message someone sent to the study's Twilio number. YES and NO replies to an introduction are acted on
    automatically; everything else waits in Conversations for a person. Twilio may deliver the same message twice, so
    its SID is unique. The text is erased if the participant withdraws (consent.withdrawal)."""

    provider_sid = models.CharField(max_length=64, unique=True)
    outreach = models.ForeignKey(Outreach, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages")
    sample_case = models.ForeignKey("sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE, related_name="inbound_messages")
    number_hash = models.CharField(max_length=64, db_index=True)
    from_masked = models.CharField(max_length=32)
    # Kept only for a number the study has no record of, so a person can answer or phone them; a matched case's number
    # stays on its Respondent record.
    from_number = models.CharField(max_length=20, blank=True)
    body = models.TextField(blank=True)
    kind = models.CharField(max_length=8, choices=ReplyKind.choices, default=ReplyKind.OTHER)
    auto_reply = models.TextField(blank=True)
    needs_person = models.BooleanField(default=False)
    handled_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    handled_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"InboundMessage({self.from_masked} {self.kind})"
