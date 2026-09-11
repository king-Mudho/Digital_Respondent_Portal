"""
KIIRecord model. Pulled forward from Phase 7 (docs/27_AGENT_EXECUTION_PLAN.md)
because contacts.Appointment (Phase 2) has a nullable FK to it
(docs/05_DATABASE_ARCHITECTURE.md) -- Django needs the target model to exist
to build that relation. Full field set per docs/05 and docs/13_KII_MODULE.md;
the frontend/workflow wiring itself still lands in Phase 7.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models


class KIIStatus(models.TextChoices):
    INVITED = "INVITED", "Invited"
    SCHEDULED = "SCHEDULED", "Scheduled"
    COMPLETED = "COMPLETED", "Completed"
    DECLINED = "DECLINED", "Declined"
    NO_SHOW = "NO_SHOW", "No show"


class TranscriptStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    VERIFIED = "VERIFIED", "Verified"
    ANONYMISED = "ANONYMISED", "Anonymised"


class CodingStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETE = "COMPLETE", "Complete"


class KIIRecord(models.Model):
    """Participant-identifying fields are access-controlled the same way as
    contacts.Respondent -- never in an aggregate dashboard payload or the
    de-identified analysis export (docs/18_DATA_PRIVACY_AND_COMPLIANCE.md)."""

    kii_id = models.CharField(max_length=32, unique=True, editable=False)
    stakeholder_category = models.CharField(max_length=64)
    organisation = models.ForeignKey(
        "sampling.Organisation", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="kii_records",
    )
    participant_name = models.CharField(max_length=255)
    participant_role = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=KIIStatus.choices, default=KIIStatus.INVITED)
    preferred_mode = models.CharField(
        max_length=16,
        choices=[
            ("TEAMS", "Microsoft Teams"),
            ("ZOOM", "Zoom"),
            ("MEET", "Google Meet"),
            ("WHATSAPP_VOICE", "WhatsApp voice"),
            ("WHATSAPP_VIDEO", "WhatsApp video"),
            ("PHONE", "Phone"),
            ("FACE_TO_FACE", "Face to face"),
        ],
    )
    participation_consent = models.ForeignKey(
        "consent.ConsentRecord", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="kii_participation_records",
    )
    recording_consent = models.ForeignKey(
        "consent.ConsentRecord", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="kii_recording_records",
    )
    interview_date = models.DateField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    interviewer = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="conducted_kiis",
    )
    # Pointer into the secure controlled file store -- never the file itself
    # (docs/13_KII_MODULE.md).
    recording_reference = models.CharField(max_length=512, blank=True)
    field_notes = models.TextField(blank=True)
    transcript_status = models.CharField(
        max_length=16, choices=TranscriptStatus.choices, default=TranscriptStatus.NOT_STARTED
    )
    coding_status = models.CharField(
        max_length=16, choices=CodingStatus.choices, default=CodingStatus.NOT_STARTED
    )
    thematic_coverage_tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.kii_id} — {self.participant_name}"
