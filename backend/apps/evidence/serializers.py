import os

from django.conf import settings
from rest_framework import serializers

from .ai_coding import ai_coding_is_configured, pdf_page_count, with_current_record_details
from .kobo_submit import kobo_submit_is_configured
from .models import DocumentRecord
from .services import build_document_coding_url


class DocumentRecordSerializer(serializers.ModelSerializer):
    # Computed, never stored -- reflects KOBO_DOCUMENTS_FORM_URL and the
    # record's own fields at read time (services.build_document_coding_url).
    coding_url = serializers.SerializerMethodField()
    ai_coding_configured = serializers.SerializerMethodField()
    kobo_submit_configured = serializers.SerializerMethodField()
    # The full draft (~110 fields) is only useful on the single-record
    # review screen -- omitted from the list serialization the same way
    # apps/kii/serializers.py omits coding_url from the KII register, so a
    # page of the Documents register never pays for a payload nobody reads.
    ai_draft = serializers.SerializerMethodField()
    # Page count of a PDF source, so the screen can ask for a page range when
    # it is longer than the AI can read at once. Detail view only: it opens the file.
    source_file_pages = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRecord
        fields = [
            "id", "document_id", "organisation", "title", "author_or_speaker",
            "publication_or_event_date", "source_url_or_reference", "document_type",
            "authenticity_assessment", "verified_at", "geographic_scope", "value_chain",
            "construct_tags", "evidence_extract", "interpretive_memo", "reviewer", "qa_status",
            "coding_url", "source_file_name", "source_file_content_type",
            "source_file_size", "source_file_uploaded_at",
            "ai_draft", "ai_draft_generated_at", "ai_draft_model", "ai_coding_configured",
            "ai_draft_status", "ai_draft_error", "ai_draft_progress", "source_file_pages",
            "kobo_submission_uuid", "kobo_submitted_at", "kobo_submitted_by", "kobo_submit_configured",
        ]
        read_only_fields = [
            # authenticity, verification time and QA status change only through their own
            # endpoints, which enforce the rule that authenticity is assessed before a
            # document can be Included -- a plain PATCH must not be a way round it.
            "authenticity_assessment", "verified_at", "qa_status",
            "id", "document_id", "coding_url", "source_file_name",
            "source_file_content_type", "source_file_size", "source_file_uploaded_at",
            "ai_draft", "ai_draft_generated_at", "ai_draft_model", "ai_coding_configured",
            "ai_draft_status", "ai_draft_error", "ai_draft_progress", "source_file_pages",
            "kobo_submission_uuid", "kobo_submitted_at", "kobo_submitted_by", "kobo_submit_configured",
        ]

    def get_coding_url(self, obj):
        return build_document_coding_url(obj)

    def get_ai_coding_configured(self, obj):
        return ai_coding_is_configured()

    def get_kobo_submit_configured(self, obj):
        return kobo_submit_is_configured()

    def get_ai_draft(self, obj):
        if isinstance(self.parent, serializers.ListSerializer):
            return None
        # {} (the model's default) must serialize as null, not {} -- an
        # empty *object* is truthy in JavaScript, so the frontend's "has a
        # draft ever been generated?" check would otherwise see a brand
        # new, never-drafted document the same as one with real answers.
        return with_current_record_details(obj, obj.ai_draft) if obj.ai_draft else None

    def get_source_file_pages(self, obj):
        if isinstance(self.parent, serializers.ListSerializer) or not obj.source_file_ref:
            return None
        if not obj.source_file_name.lower().endswith(".pdf"):
            return None
        return pdf_page_count(os.path.join(settings.PRIVATE_DATA_ROOT, obj.source_file_ref))
