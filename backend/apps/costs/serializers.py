from decimal import Decimal

from rest_framework import serializers

from .models import CostEvent


class CostEventSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = CostEvent
        fields = ["id", "date", "category", "category_label", "description", "paid_to", "amount", "currency",
                  "sample_case", "kii_record", "approved_by", "recorded_by", "created_at"]
        read_only_fields = ["id", "approved_by", "created_at"]

    def get_recorded_by(self, obj) -> str:
        user = obj.approved_by
        return (user.get_full_name() or user.username) if user else ""

    def validate_description(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Say what the money was for, e.g. \u201cClaude subscription, October\u201d.")
        return value

    def validate_paid_to(self, value):
        return (value or "").strip()

    def validate_amount(self, value):
        if value is None or value <= Decimal("0"):
            raise serializers.ValidationError("Enter an amount above zero.")
        return value

    def validate(self, attrs):
        # A new cost must say what it was for; an edit that leaves the description out keeps the one it has.
        if self.instance is None and not attrs.get("description"):
            raise serializers.ValidationError({"description": ["Say what the money was for, e.g. \u201cClaude subscription, October\u201d."]})
        return attrs
