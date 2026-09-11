from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "user_display", "action", "object_type", "object_id", "metadata", "created_at"]
