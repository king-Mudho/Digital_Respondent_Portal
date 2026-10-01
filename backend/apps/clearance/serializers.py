from rest_framework import serializers

from .models import ClearanceDocument


class ClearanceDocumentSerializer(serializers.ModelSerializer):
    """Admin view: every field, including is_public/active -- the controls that decide what a respondent sees."""

    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = ClearanceDocument
        fields = [
            "id", "title", "issuing_body", "document_type", "document_type_display", "reference_number",
            "issue_date", "description", "is_public", "active", "display_order",
            "has_file", "file_name", "file_size", "file_uploaded_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "file_name", "file_size", "file_uploaded_at", "created_at", "updated_at"]

    def get_has_file(self, obj):
        return bool(obj.file_ref)


class RespondentClearanceDocumentSerializer(serializers.ModelSerializer):
    """Public view: only what a respondent needs to decide whether to trust the study. No internal storage
    path, no is_public/active flags (obviously true of everything returned here), no created_by."""

    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = ClearanceDocument
        fields = ["id", "title", "issuing_body", "document_type_display", "reference_number", "issue_date", "description"]
