"""
KIIRecord model. Pulled forward from Phase 7 (docs/27_AGENT_EXECUTION_PLAN.md)
because contacts.Appointment (Phase 2) has a nullable FK to it
(docs/05_DATABASE_ARCHITECTURE.md) -- Django needs the target model to exist
to build that relation. Full field set per docs/05 and docs/13_KII_MODULE.md;
the frontend/workflow wiring itself still lands in Phase 7.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.invitations.models import Channel


class KIIStatus(models.TextChoices):
    # A prospect identified in the KII sampling frame but not yet approached
    # -- added 2026-09-12 when importing the real KII Core-60/Reserve-30
    # register, where every one of the 90 rows is genuinely "Not contacted"/
    # "Available". Distinct from INVITED, which means an actual invitation
    # went out.
    PROSPECT = "PROSPECT", "Prospect (not yet contacted)"
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
    # Same pattern as contacts.Respondent's own contact fields (CharField, not a
    # stricter validator -- real-world register data is messier than a single clean
    # number). Needed to send a self-service invitation link (see KIIInvitationToken
    # below); blank until an RA records them.
    phone = models.CharField(max_length=255, blank=True)
    whatsapp_number = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=16, choices=KIIStatus.choices, default=KIIStatus.INVITED)
    # blank=True (2026-09-12): a PROSPECT hasn't chosen a mode yet -- only
    # meaningful once an actual invitation goes out.
    preferred_mode = models.CharField(
        max_length=16,
        blank=True,
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
    # Losslessly preserves register-provenance fields with no dedicated
    # model field (organisation/institution name, source register cross-
    # references, priority, verification status/confidence/source, etc.)
    # -- nothing invented, nothing discarded. Same pattern as sampling.
    # Organisation.metadata / SampleCase.metadata.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.kii_id} — {self.participant_name}"


class KIIInvitationTokenStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    SENT = "SENT", "Sent"
    OPENED = "OPENED", "Opened"
    CONSENTED = "CONSENTED", "Consented"
    # Set when the KII Guide link was actually issued to the informant (see
    # KIIKoboRedirectView) -- not "COMPLETED": this view has no way to know
    # whether they go on to finish the form. Whether the interview is actually
    # done lives on KIIRecord.status, set by an RA once the submission appears.
    STARTED = "STARTED", "Started"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class KIIInvitationToken(models.Model):
    """A KII informant's own self-service link -- same crypto/lifecycle pattern as
    invitations.InvitationToken (32-byte CSPRNG token, only a salted SHA-256 hash ever
    persisted; see kii.services), deliberately a SEPARATE model rather than reusing
    InvitationToken directly: that model's status set (ELIGIBILITY_PASSED,
    SURVEY_STARTED, QA_PASSED, ...) is QUAN-shaped and consumed by QUAN-only code
    (reconciliation, dashboards, exports) -- forcing KII through it would mean either
    meaningless statuses or overloading existing ones, and touching a model that
    central risks the live Main-400 flow. No eligibility concept here, and no
    SampleCase workflow to advance: a KII informant was already identified by name by
    an RA, unlike an anonymous Main-400 organisation."""

    kii_record = models.ForeignKey(
        KIIRecord, on_delete=models.PROTECT, related_name="invitation_tokens"
    )
    token_hash = models.CharField(max_length=128, unique=True)
    manual_code_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=KIIInvitationTokenStatus.choices, default=KIIInvitationTokenStatus.GENERATED
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"KIIInvitationToken({self.kii_record_id}, {self.status})"
