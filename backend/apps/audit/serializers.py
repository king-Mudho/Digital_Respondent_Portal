from rest_framework import serializers

from .labels import describe
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """`label`/`detail` are what the Audit Log screen shows; `action` (the raw code, e.g.
    "sampling.status_reset_after_test_cleanup") and the full `metadata` stay in the response too, for
    anyone who wants the exact machine value rather than the human-readable summary."""

    user_display = serializers.CharField(source="user.username", default=None, read_only=True)
    label = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ["id", "user_display", "action", "label", "detail", "object_type", "object_id", "metadata", "created_at"]

    def get_label(self, obj):
        return describe(obj.action, obj.metadata)[0]

    def get_detail(self, obj):
        return describe(obj.action, obj.metadata)[1]
