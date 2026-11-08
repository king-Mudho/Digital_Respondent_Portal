"""Who gets credit for each completed submission (PI decision, 8 Nov 2026): the research assistants are paid per
completed questionnaire or KII, so every completion is credited to one RA -- or to nobody -- with the evidence for it.

ADMINISTERED: the RA filled in the form with the respondent, opened from the portal, which stamped the RA into it
(a signed value for the questionnaire, the interviewer recorded on the KII record).
ASSISTED: the respondent completed it themselves, and an RA's call, message or other logged contact with them came
last within settings.RA_ASSIST_CREDIT_DAYS before the submission.
UNCREDITED: neither -- the respondent completed it with no RA involved in that window.

apps/ra/credit.py keeps one row per completion and recomputes it as evidence arrives, until the PI overrides it
(with a reason, audited); an overridden row is never recomputed.
"""

from django.db import models


class Study(models.TextChoices):
    QUAN = "QUAN", "Main-400 questionnaire"
    KII = "KII", "Key informant interview"


class CreditKind(models.TextChoices):
    ADMINISTERED = "ADMINISTERED", "Administered by the RA"
    ASSISTED = "ASSISTED", "Assisted by the RA"
    UNCREDITED = "UNCREDITED", "No RA involved"


class SubmissionCredit(models.Model):
    study = models.CharField(max_length=8, choices=Study.choices)
    # The completion itself: a QUANSubmission, or a KII record whose guide reached KoboToolbox.
    quan_submission = models.OneToOneField("kobo.QUANSubmission", null=True, blank=True, on_delete=models.CASCADE,
                                           related_name="ra_credit")
    kii_record = models.OneToOneField("kii.KIIRecord", null=True, blank=True, on_delete=models.CASCADE, related_name="ra_credit")
    sample_case = models.ForeignKey("sampling.SampleCase", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    submitted_at = models.DateTimeField()
    ra = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="ra_credits")
    kind = models.CharField(max_length=16, choices=CreditKind.choices)
    evidence = models.CharField(max_length=300, blank=True)  # e.g. "WhatsApp voice call 3 Nov 2026 14:05: Reached"
    evidence_at = models.DateTimeField(null=True, blank=True)
    overridden_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    overridden_at = models.DateTimeField(null=True, blank=True)
    override_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(quan_submission__isnull=False, kii_record__isnull=True)
                           | models.Q(quan_submission__isnull=True, kii_record__isnull=False)),
                name="ra_credit_one_completion",
            ),
        ]

    def __str__(self):
        return f"SubmissionCredit({self.study} {self.kind} {self.ra_id})"
