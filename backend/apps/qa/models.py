from django.core.exceptions import ValidationError
from django.db import models


class QARuleThreshold(models.Model):
    """Config, not code -- AGENTS.md ground rule 7: keep the *threshold
    values* in the database and the *evaluation logic* in Python, exactly as
    ABI keeps recommendation text in the database and selection logic in
    Python. Seeded from the proposed defaults in
    docs/15_QA_AND_DATA_QUALITY.md, flagged provisional pending PI sign-off
    (docs/27_AGENT_EXECUTION_PLAN.md "Open questions")."""

    code = models.CharField(max_length=64, unique=True)
    value = models.JSONField()
    effective_from = models.DateTimeField()
    set_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.code}={self.value}"


class QADecision(models.TextChoices):
    ACCEPT = "ACCEPT", "Accept"
    QUERY = "QUERY", "Query"
    REJECT = "REJECT", "Reject"


class ExceptionStatus(models.TextChoices):
    """Where an automated QA flag has got to.

    ResearchOS brief A6 wants a "daily exception queue with owner/status".
    Before this, a triggered rule produced a QAEvent and nothing else: there
    was no way to say who was looking at it, or whether anyone had. The
    queue was a list, not a workflow, and nothing could be tracked to
    closure.
    """

    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    RESOLVED = "RESOLVED", "Resolved"
    DISMISSED = "DISMISSED", "Dismissed (not a real problem)"


class QAEvent(models.Model):
    """Only a human-recorded QAEvent.decision=ACCEPT moves a record's
    qa_status to QA_PASSED -- never automatic, even when zero rules
    triggered (docs/15_QA_AND_DATA_QUALITY.md).

    Two kinds of row live here, distinguished by `reviewer`:
      - `reviewer is None`  -- an automated flag raised by a rule. These are
        the exceptions the queue tracks, and they carry owner/status below.
      - `reviewer` set      -- a human decision. Terminal by nature; the
        ownership fields stay at their defaults and are not used.
    """

    submission = models.ForeignKey(
        "kobo.QUANSubmission", null=True, blank=True, on_delete=models.CASCADE, related_name="qa_events"
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE, related_name="qa_events"
    )
    document_record = models.ForeignKey(
        "evidence.DocumentRecord", null=True, blank=True, on_delete=models.CASCADE, related_name="qa_events"
    )
    rule_triggered = models.CharField(max_length=64, blank=True)
    decision = models.CharField(max_length=8, choices=QADecision.choices)
    reviewer = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="qa_events")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- exception ownership (automated flags only) --------------------
    status = models.CharField(
        max_length=16, choices=ExceptionStatus.choices, default=ExceptionStatus.OPEN
    )
    assigned_to = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_qa_exceptions",
    )
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="resolved_qa_exceptions",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The queue's default read: open exceptions, oldest first.
            models.Index(fields=["status", "created_at"]),
        ]

    @property
    def is_automated_flag(self) -> bool:
        return self.reviewer_id is None

    @property
    def age_days(self) -> int:
        from django.utils import timezone

        return (timezone.now() - self.created_at).days if self.created_at else 0

    def clean(self):
        targets = (self.submission_id, self.kii_record_id, self.document_record_id)
        if sum(bool(t) for t in targets) != 1:
            raise ValidationError("Exactly one of submission/kii_record/document_record must be set.")

    def __str__(self):
        return f"QAEvent({self.decision})"
