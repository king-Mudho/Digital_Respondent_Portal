from django.core.exceptions import ValidationError
from django.db import models


class ConsentType(models.TextChoices):
    PARTICIPATION = "PARTICIPATION", "Participation"
    KII_RECORDING = "KII_RECORDING", "KII recording"


class ConsentDecision(models.TextChoices):
    GIVEN = "GIVEN", "Given"
    DECLINED = "DECLINED", "Declined"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


class ConsentMethod(models.TextChoices):
    WEB_CLICKTHROUGH = "WEB_CLICKTHROUGH", "Web click-through"
    VERBAL_RA_RECORDED = "VERBAL_RA_RECORDED", "Verbal, RA-recorded"
    WRITTEN = "WRITTEN", "Written"


class ConsentRecord(models.Model):
    """PARTICIPATION and KII_RECORDING are always separate rows -- KII
    recording consent is never inferred from participation consent
    (AGENTS.md ground rule 6, docs/10_INVITATION_AND_CONSENT.md)."""

    # Nullable: docs/05_DATABASE_ARCHITECTURE.md models this FK as required,
    # but docs/13_KII_MODULE.md draws KII participants from stakeholder
    # categories that often have no Main-400 SampleCase at all (e.g. a
    # sector expert or financial-institution representative, not a sampled
    # organisation). Flagged in docs/27_AGENT_EXECUTION_PLAN.md "Open
    # questions" as a doc-schema gap closed this way rather than silently
    # forcing every KII consent onto an unrelated SampleCase.
    sample_case = models.ForeignKey(
        "sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE,
        related_name="consent_records",
    )
    respondent = models.ForeignKey(
        "contacts.Respondent", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="consent_records",
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE,
        related_name="consent_records",
    )
    consent_type = models.CharField(max_length=16, choices=ConsentType.choices)
    information_sheet_version = models.CharField(max_length=32)
    decision = models.CharField(max_length=16, choices=ConsentDecision.choices)
    method = models.CharField(max_length=24, choices=ConsentMethod.choices)
    timestamp = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.decision == ConsentDecision.WITHDRAWN and not self.withdrawn_at:
            raise ValidationError("withdrawn_at must be set when decision=WITHDRAWN.")
        if not self.sample_case_id and not self.kii_record_id:
            raise ValidationError("At least one of sample_case/kii_record must be set.")

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.consent_type}:{self.decision} ({self.sample_case_id})"
