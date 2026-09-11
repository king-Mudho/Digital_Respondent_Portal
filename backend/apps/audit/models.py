from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """docs/18_DATA_PRIVACY_AND_COMPLIANCE.md: an AuditEvent is created for
    every sampling, consent, response-acceptance, reserve-activation and
    data-lock action."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=128)
    object_type = models.CharField(max_length=128)
    object_id = models.CharField(max_length=64)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.object_type}:{self.object_id}"
