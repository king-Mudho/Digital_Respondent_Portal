from rest_framework import serializers

from .models import ClearanceDocument


class ClearanceDocumentSerializer(serializers.ModelSerializer):
    """Admin view: every field, including is_public/active -- the controls that decide what a respondent sees."""

    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    has_file = serializers.SerializerMethodField()
    forbidden_phrase = serializers.SerializerMethodField()
    has_wording_exception = serializers.BooleanField(read_only=True)
    wording_exception_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ClearanceDocument
        fields = [
            "id", "title", "issuing_body", "document_type", "document_type_display", "reference_number",
            "issue_date", "description", "is_public", "active", "in_study_brief", "display_order",
            "has_file", "file_name", "file_size", "file_uploaded_at", "created_at", "updated_at",
            "forbidden_phrase", "has_wording_exception", "wording_exception_reason", "wording_exception_by_name",
            "wording_exception_at",
        ]
        read_only_fields = ["id", "file_name", "file_size", "file_uploaded_at", "created_at", "updated_at",
                            "wording_exception_reason", "wording_exception_at"]

    def get_has_file(self, obj):
        return bool(obj.file_ref)

    def get_forbidden_phrase(self, obj):
        """The phrase participants must never see that this document contains (AGENTS.md rule 2), or ""."""
        from .brief import blocked_phrase_in

        return blocked_phrase_in(obj) if obj.file_ref else ""

    def get_wording_exception_by_name(self, obj):
        user = obj.wording_exception_by if obj.has_wording_exception else None
        return (user.get_full_name() or user.username) if user else ""


class RespondentClearanceDocumentSerializer(serializers.ModelSerializer):
    """Public view: only what a respondent needs to decide whether to trust the study. No internal storage
    path, no is_public/active flags (obviously true of everything returned here), no created_by."""

    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = ClearanceDocument
        fields = ["id", "title", "issuing_body", "document_type_display", "reference_number", "issue_date", "description"]
