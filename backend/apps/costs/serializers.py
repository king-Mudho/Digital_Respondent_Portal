from rest_framework import serializers

from .models import CostEvent


class CostEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostEvent
        fields = ["id", "date", "category", "amount", "currency", "sample_case", "kii_record", "approved_by", "created_at"]
        read_only_fields = ["id", "approved_by", "created_at"]
