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
