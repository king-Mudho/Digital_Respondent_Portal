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

    sample_case = models.ForeignKey(
        "sampling.SampleCase", on_delete=models.CASCADE, related_name="consent_records"
    )
    respondent = models.ForeignKey(
        "contacts.Respondent", null=True, blank=True, on_delete=models.SET_NULL,
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

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.consent_type}:{self.decision} ({self.sample_case_id})"
