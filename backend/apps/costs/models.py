from django.db import models


class CostCategory(models.TextChoices):
    RA_ALLOWANCE = "RA_ALLOWANCE", "RA allowance"
    AIRTIME_DATA = "AIRTIME_DATA", "Airtime/data"
    TRANSPORT = "TRANSPORT", "Transport"
    ACCOMMODATION = "ACCOMMODATION", "Accommodation"
    HOSTING = "HOSTING", "Hosting"
    MESSAGING = "MESSAGING", "Messaging"
    SOFTWARE_AI = "SOFTWARE_AI", "Software / AI tools"
    OTHER = "OTHER", "Other"


class CostEvent(models.Model):
    date = models.DateField()
    category = models.CharField(max_length=16, choices=CostCategory.choices)
    # What the money was for and who received it (PI, 18 Oct 2026): "Claude subscription, October" paid to "Anthropic";
    # "Fieldwork allowance, week 2" paid to the RA by name. A category alone could not say either.
    description = models.CharField(max_length=255, blank=True, default="")
    paid_to = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    sample_case = models.ForeignKey(
        "sampling.SampleCase", null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_events"
    )
    kii_record = models.ForeignKey(
        "kii.KIIRecord", null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_events"
    )
    approved_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="approved_costs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.category} {self.amount} {self.currency} ({self.date})"
