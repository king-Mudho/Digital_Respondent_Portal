from rest_framework import serializers

from .models import DocumentRecord


class DocumentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRecord
        fields = [
            "id", "document_id", "organisation", "title", "author_or_speaker",
            "publication_or_event_date", "source_url_or_reference", "document_type",
            "authenticity_assessment", "verified_at", "geographic_scope", "value_chain",
            "construct_tags", "evidence_extract", "interpretive_memo", "reviewer", "qa_status",
        ]
        read_only_fields = ["id", "document_id"]
