from django.db import models


class AdministrationMode(models.TextChoices):
    """docs/11_KOBOTOOLBOX_INTEGRATION.md."""

    WEB_SELF = "01", "Web self-administration"
    WHATSAPP_LINK_SELF = "02", "WhatsApp link, self-completion"
    PHONE_ASSISTED = "03", "Telephone interviewer-administered"
    WHATSAPP_CALL_ASSISTED = "04", "WhatsApp call, interviewer-assisted"
    VIDEO_CALL_ASSISTED = "05", "Video call, interviewer-assisted"
    FACE_TO_FACE = "06", "Face to face"


class QAStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    QUERY = "QUERY", "Query"
    QA_PASSED = "QA_PASSED", "QA passed"
    REJECTED = "REJECTED", "Rejected"


class QUANSubmission(models.Model):
    sample_case = models.ForeignKey(
        "sampling.SampleCase", on_delete=models.PROTECT, related_name="quan_submissions"
    )
    kobo_submission_uuid = models.CharField(max_length=64, unique=True)
    administration_mode = models.CharField(max_length=2, choices=AdministrationMode.choices)
    ra = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="administered_submissions",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField()
    last_edited_at = models.DateTimeField(null=True, blank=True)
    completion_seconds = models.PositiveIntegerField(null=True, blank=True)
    qa_status = models.CharField(max_length=16, choices=QAStatus.choices, default=QAStatus.PENDING)
    # Pointer to the stored full Kobo submission payload (written to
    # MEDIA_ROOT/kobo_submissions/<uuid>.json by the reconciliation job) --
    # never the payload itself in this row, per docs/05_DATABASE_
    # ARCHITECTURE.md's "pointer, not the file" pattern (mirrors
    # KIIRecord.recording_reference).
    raw_payload_ref = models.CharField(max_length=255, blank=True)
    # A content hash of the last-pulled payload -- how reconciliation
    # detects an edited submission (see kobo.services module docstring for
    # why this, rather than a specific Kobo metadata field, is the
    # detection mechanism).
    payload_content_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"QUANSubmission({self.kobo_submission_uuid})"


class ReconciliationTrigger(models.TextChoices):
    SCHEDULE = "SCHEDULE", "Schedule"
    WEBHOOK_HEADSUP = "WEBHOOK_HEADSUP", "Webhook heads-up"
    MANUAL = "MANUAL", "Manual"


class ReconciliationLog(models.Model):
    run_started_at = models.DateTimeField()
    run_finished_at = models.DateTimeField(null=True, blank=True)
    submissions_pulled = models.PositiveIntegerField(default=0)
    new_submissions = models.PositiveIntegerField(default=0)
    updated_submissions = models.PositiveIntegerField(default=0)
    mismatches_flagged = models.PositiveIntegerField(default=0)
    triggered_by = models.CharField(max_length=16, choices=ReconciliationTrigger.choices)
    # Set when the Kobo API call itself failed (unreachable, invalid token,
    # timeout, HTTP error) -- the run still gets a ReconciliationLog row
    # rather than the exception propagating uncaught out of the scheduled
    # task/manual-trigger endpoint, so a Kobo outage is visible in the log
    # history instead of silently vanishing.
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-run_started_at"]

    def __str__(self):
        return f"ReconciliationLog({self.run_started_at:%Y-%m-%d %H:%M})"
