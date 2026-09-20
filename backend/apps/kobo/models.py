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
        indexes = [
            models.Index(fields=["-submitted_at"], name="quan_submitted_idx"),
            models.Index(fields=["qa_status", "submitted_at"], name="quan_qa_queue_idx"),
        ]

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


class KoboFormSubmission(models.Model):
    """The portal's own copy of one completed KoboToolbox submission, for any
    of the three main-study forms (questionnaire, KII Guide, Document
    Analysis Tool).

    KoboToolbox stays the authority. This table is what "synced" means: after
    each sync the portal holds exactly the answers Kobo holds, a content hash
    proves it, and a submission deleted in Kobo is flagged (never silently
    kept as if it still counted). The questionnaire is *additionally*
    reconciled into QUANSubmission for the QA workflow -- that is unchanged.
    """

    form_key = models.CharField(max_length=20)
    kobo_id = models.BigIntegerField()
    # meta/rootUuid: stable across edits (Kobo gives an edited submission a new
    # _uuid but keeps the root) -- same identity rule as reconciliation.
    kobo_uuid = models.CharField(max_length=64, blank=True)
    record = models.CharField(max_length=120, blank=True)  # Sample_ID / KII ID / DOC-ID
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.CharField(max_length=150, blank=True)
    payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)
    first_synced_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField()
    last_changed_at = models.DateTimeField(null=True, blank=True)  # set when a later sync found an edit
    removed_at = models.DateTimeField(null=True, blank=True)  # no longer in Kobo (deleted there)

    class Meta:
        ordering = ["-submitted_at", "-kobo_id"]
        constraints = [models.UniqueConstraint(fields=["form_key", "kobo_id"], name="kobo_form_submission_unique")]
        indexes = [models.Index(fields=["form_key", "record"], name="kobo_formsub_record_idx")]

    def __str__(self):
        return f"KoboFormSubmission({self.form_key}:{self.kobo_id})"


class FormSyncLog(models.Model):
    form_key = models.CharField(max_length=20)
    run_started_at = models.DateTimeField()
    run_finished_at = models.DateTimeField(null=True, blank=True)
    pulled = models.PositiveIntegerField(default=0)
    new = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    removed = models.PositiveIntegerField(default=0)
    triggered_by = models.CharField(max_length=16, choices=ReconciliationTrigger.choices)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-run_started_at"]
        indexes = [models.Index(fields=["form_key", "-run_started_at"], name="kobo_formsync_idx")]

    def __str__(self):
        return f"FormSyncLog({self.form_key} {self.run_started_at:%Y-%m-%d %H:%M})"
