from django.db import models


class RoleCategory(models.TextChoices):
    OWNER_FOUNDER = "OWNER_FOUNDER", "Owner/founder"
    CEO_MD = "CEO_MD", "CEO/MD"
    FINANCE_CREDIT_RISK = "FINANCE_CREDIT_RISK", "Finance/credit/risk"
    OPERATIONS = "OPERATIONS", "Operations"
    STRATEGY_BD = "STRATEGY_BD", "Strategy/BD"
    SUPPLY_CHAIN_COMMERCIAL = "SUPPLY_CHAIN_COMMERCIAL", "Supply chain/commercial"
    OTHER_SENIOR_MANAGER = "OTHER_SENIOR_MANAGER", "Other senior manager"


class Respondent(models.Model):
    """Access-controlled -- full_name never appears in an aggregate dashboard
    payload or the de-identified analysis export
    (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md)."""

    sample_case = models.ForeignKey(
        "sampling.SampleCase", on_delete=models.CASCADE, related_name="respondents"
    )
    full_name = models.CharField(max_length=255)
    # Blank when the eligibility gate determined the respondent doesn't fit
    # any category on the fixed list (ineligible) -- never coerced to a
    # placeholder category (docs/10_INVITATION_AND_CONSENT.md).
    role_category = models.CharField(max_length=32, choices=RoleCategory.choices, blank=True)
    is_eligible = models.BooleanField(null=True, blank=True)
    eligibility_checked_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eligibility_checks",
    )
    phone = models.CharField(max_length=32, blank=True)
    whatsapp_number = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    gatekeeper_name = models.CharField(max_length=255, blank=True)
    gatekeeper_contact = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.sample_case_id})"


class ContactChannel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"
    PHONE = "PHONE", "Phone"
    SMS = "SMS", "SMS"
    FACE_TO_FACE = "FACE_TO_FACE", "Face to face"


class ContactOutcome(models.TextChoices):
    REACHED = "REACHED", "Reached"
    NO_ANSWER = "NO_ANSWER", "No answer"
    WRONG_NUMBER = "WRONG_NUMBER", "Wrong number"
    REFUSED = "REFUSED", "Refused"
    RESCHEDULED = "RESCHEDULED", "Rescheduled"
    COMPLETED = "COMPLETED", "Completed"


class ContactEvent(models.Model):
    sample_case = models.ForeignKey(
        "sampling.SampleCase", on_delete=models.CASCADE, related_name="contact_events"
    )
    channel = models.CharField(max_length=16, choices=ContactChannel.choices)
    occurred_at = models.DateTimeField()
    outcome = models.CharField(max_length=16, choices=ContactOutcome.choices)
    notes = models.TextField(blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    ra = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="contact_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]


class AppointmentMode(models.TextChoices):
    TEAMS = "TEAMS", "Microsoft Teams"
    ZOOM = "ZOOM", "Zoom"
    MEET = "MEET", "Google Meet"
    WHATSAPP_VOICE = "WHATSAPP_VOICE", "WhatsApp voice"
    WHATSAPP_VIDEO = "WHATSAPP_VIDEO", "WhatsApp video"
    PHONE = "PHONE", "Phone"
    FACE_TO_FACE = "FACE_TO_FACE", "Face to face"


class AppointmentStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    CONFIRMED = "CONFIRMED", "Confirmed"
    COMPLETED = "COMPLETED", "Completed"
    MISSED = "MISSED", "Missed"
    CANCELLED = "CANCELLED", "Cancelled"


class Appointment(models.Model):
    sample_case = models.ForeignKey(
        "sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE,
        related_name="appointments",
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE,
        related_name="appointments",
    )
    scheduled_for = models.DateTimeField()
    mode = models.CharField(max_length=16, choices=AppointmentMode.choices)
    status = models.CharField(max_length=16, choices=AppointmentStatus.choices, default=AppointmentStatus.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if bool(self.sample_case_id) == bool(self.kii_record_id):
            raise ValidationError("Exactly one of sample_case/kii_record must be set.")

    class Meta:
        ordering = ["scheduled_for"]
