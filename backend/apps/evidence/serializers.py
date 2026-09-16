from rest_framework import serializers

from .models import DocumentRecord
from .services import build_document_coding_url


class DocumentRecordSerializer(serializers.ModelSerializer):
    # Computed, never stored -- reflects KOBO_DOCUMENTS_FORM_URL and the
    # record's own fields at read time (services.build_document_coding_url).
    coding_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRecord
        fields = [
            "id", "document_id", "organisation", "title", "author_or_speaker",
            "publication_or_event_date", "source_url_or_reference", "document_type",
            "authenticity_assessment", "verified_at", "geographic_scope", "value_chain",
            "construct_tags", "evidence_extract", "interpretive_memo", "reviewer", "qa_status",
            "coding_url", "source_file_name", "source_file_content_type",
            "source_file_size", "source_file_uploaded_at",
        ]
        read_only_fields = [
            "id", "document_id", "coding_url", "source_file_name",
            "source_file_content_type", "source_file_size", "source_file_uploaded_at",
        ]

    def get_coding_url(self, obj):
        return build_document_coding_url(obj)
