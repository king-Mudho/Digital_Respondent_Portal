from datetime import timedelta

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageDocuments
from apps.audit.utils import log_action

from .ai_coding import (
    DETERMINISTIC_FIELDS,
    MAX_PDF_PAGES,
    AIDraftError,
    ai_coding_is_configured,
    parse_page_range,
    pdf_page_count,
)
from .document_tool_schema import SCHEMA
from .kobo_submit import KoboSubmitError, kobo_submit_is_configured, submit_to_kobo
from .models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord
from .serializers import DocumentRecordSerializer
from .services import (
    DocumentFileError,
    DocumentWorkflowError,
    generate_document_id,
    open_source_file,
    record_authenticity_assessment,
    remove_source_file,
    save_source_file,
    set_qa_status,
)
from .tasks import RUNNING, generate_ai_draft


def _error(code, message, status=400):
    return Response({"error": {"code": code, "message": message, "field_errors": {}}}, status=status)


class DocumentRecordListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/documents/ (docs/06_API_ARCHITECTURE.md)."""

    permission_classes = [CanManageDocuments]
    serializer_class = DocumentRecordSerializer
    filterset_fields = ["document_type", "authenticity_assessment", "qa_status"]
    search_fields = ["document_id", "title", "author_or_speaker", "value_chain"]
    # DocumentRecord has no Meta.ordering -- an unordered queryset makes
    # PageNumberPagination's page boundaries arbitrary.
    queryset = DocumentRecord.objects.order_by("document_id")

    def perform_create(self, serializer):
        serializer.save(document_id=generate_document_id())


class DocumentRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [CanManageDocuments]
    serializer_class = DocumentRecordSerializer
    queryset = DocumentRecord.objects.all()


class DocumentAuthenticityView(APIView):
    """POST /api/v1/documents/{id}/authenticity/ -- always records a
    reviewer (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md)."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        assessment = request.data.get("assessment")
        if assessment not in AuthenticityAssessment.values:
            return Response({"error": {"code": "invalid_assessment", "message": "Invalid assessment.", "field_errors": {}}}, status=400)
        record_authenticity_assessment(document, assessment, reviewer=request.user)
        return Response(DocumentRecordSerializer(document).data)


class DocumentQAStatusView(APIView):
    """POST /api/v1/documents/{id}/qa-status/."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        qa_status = request.data.get("qa_status")
        if qa_status not in DocumentQAStatus.values:
            return Response({"error": {"code": "invalid_qa_status", "message": "Invalid qa_status.", "field_errors": {}}}, status=400)
        try:
            set_qa_status(document, qa_status, reviewer=request.user)
        except DocumentWorkflowError as exc:
            return Response({"error": {"code": "workflow_error", "message": str(exc), "field_errors": {}}}, status=400)
        return Response(DocumentRecordSerializer(document).data)


class DocumentFileView(APIView):
    """POST /api/v1/documents/{id}/file/ -- upload/replace the source file
    (multipart, field "file"). GET -- download it. Same CanManageDocuments
    grant as the rest of the register (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md);
    Supervisor's read-only access covers the download, not the upload."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"error": {"code": "no_file", "message": "No file was sent.", "field_errors": {}}}, status=400)
        try:
            save_source_file(document, uploaded, user=request.user)
        except DocumentFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        return Response(DocumentRecordSerializer(document).data)

    def get(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        try:
            path, filename, content_type = open_source_file(document)
        except DocumentFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        log_action("document.file_downloaded", document, {"filename": filename, "user_id": request.user.id})
        response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response

    def delete(self, request, pk):
        """DELETE /api/v1/documents/{id}/file/ -- remove the uploaded file
        (the wrong document was attached). Same write grant as uploading."""
        document = get_object_or_404(DocumentRecord, pk=pk)
        try:
            remove_source_file(document, user=request.user)
        except DocumentFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        return Response(DocumentRecordSerializer(document).data)


class DocumentAISchemaView(APIView):
    """GET /api/v1/documents/ai-draft-schema/ -- the Document Analysis
    Tool's field list, groups and choice lists, for the review screen to
    render a form from. Static per deployed form version; no pk."""

    permission_classes = [CanManageDocuments]

    def get(self, request):
        return Response({
            "schema": SCHEMA,
            "deterministic_fields": sorted(DETERMINISTIC_FIELDS.keys()),
            "ai_configured": ai_coding_is_configured(),
            "kobo_submit_configured": kobo_submit_is_configured(),
        })


class DocumentAIDraftView(APIView):
    """POST /api/v1/documents/{id}/ai-draft/ -- generate a fresh AI draft
    from the uploaded source file (replaces any existing draft).
    PUT -- save the RA's edits to the draft, without touching KoboToolbox.
    Both require CanManageDocuments write access; Supervisor read-only
    reads the draft through the ordinary document detail endpoint instead.
    ai_coding.py never submits anything -- see its docstring."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        """Starts generating a draft in the background and returns at once
        (202): the reading takes minutes, longer than nginx keeps a request
        open. The screen polls ai_draft_status. Everything cheap is checked
        here first so a mistake is refused immediately, not minutes later."""
        document = get_object_or_404(DocumentRecord, pk=pk)
        if not ai_coding_is_configured():
            return _error("ai_not_configured", "AI drafting hasn't been set up (ANTHROPIC_API_KEY).", 503)
        if (
            document.ai_draft_status == RUNNING
            and document.ai_draft_started_at
            and timezone.now() - document.ai_draft_started_at < timedelta(minutes=12)
        ):
            return _error("already_running", "A draft is already being generated for this document.", 409)
        try:
            source_path, _, _ = open_source_file(document)
        except DocumentFileError as exc:
            return _error(exc.code, str(exc), exc.status)

        page_range = str(request.data.get("pages") or "").strip()
        pages = pdf_page_count(source_path) if source_path.lower().endswith(".pdf") else None
        try:
            if pages is not None and page_range:
                parse_page_range(page_range, pages)
            elif pages is not None and pages > MAX_PDF_PAGES:
                raise AIDraftError(
                    "pdf_too_long",
                    f"This PDF has {pages} pages, and the AI can read at most {MAX_PDF_PAGES} at a time. "
                    "Enter the pages that make up this evidence unit (for example 1-100).",
                )
        except AIDraftError as exc:
            return _error(exc.code, str(exc), exc.status)

        document.ai_draft_status = RUNNING
        document.ai_draft_error = ""
        document.ai_draft_started_at = timezone.now()
        document.save(update_fields=["ai_draft_status", "ai_draft_error", "ai_draft_started_at"])
        generate_ai_draft.delay(document.pk, request.user.id, page_range)
        document.refresh_from_db()
        return Response(DocumentRecordSerializer(document).data, status=202)

    def put(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        if not document.ai_draft:
            return Response({"error": {"code": "no_draft", "message": "No draft to edit yet -- generate one first.", "field_errors": {}}}, status=400)
        answers = request.data.get("answers")
        if not isinstance(answers, dict):
            return Response({"error": {"code": "invalid_input", "message": "'answers' must be an object.", "field_errors": {}}}, status=400)
        document.ai_draft = {**document.ai_draft, **answers}
        document.save(update_fields=["ai_draft"])
        log_action("document.ai_draft_edited", document, {"user_id": request.user.id})
        return Response(DocumentRecordSerializer(document).data)


class DocumentAISubmitView(APIView):
    """POST /api/v1/documents/{id}/ai-draft/submit/ -- submits the current
    (reviewed) draft to KoboToolbox as a completed record. The one place in
    this module that ever writes to Kobo, and it only runs on this
    explicit, human-triggered call -- see ai_coding.py's docstring for why."""

    permission_classes = [CanManageDocuments]

    def post(self, request, pk):
        document = get_object_or_404(DocumentRecord, pk=pk)
        if not document.ai_draft:
            return Response({"error": {"code": "no_draft", "message": "No draft to submit -- generate one first.", "field_errors": {}}}, status=400)
        try:
            result = submit_to_kobo(document, document.ai_draft, user=request.user)
        except KoboSubmitError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)

        document.kobo_submission_uuid = result["instance_uuid"]
        document.kobo_submitted_at = timezone.now()
        document.kobo_submitted_by = request.user
        document.save(update_fields=["kobo_submission_uuid", "kobo_submitted_at", "kobo_submitted_by"])
        return Response(DocumentRecordSerializer(document).data)
