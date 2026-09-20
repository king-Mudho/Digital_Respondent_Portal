import logging
from datetime import timedelta
from pathlib import Path

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
    MAX_WHOLE_DOCUMENT_PAGES,
    AIDraftError,
    ai_coding_is_configured,
    parse_page_range,
    pdf_page_count,
    with_current_record_details,
)
from .document_tool_schema import SCHEMA
from .kobo_submit import KoboSubmitError, kobo_submit_is_configured, submit_to_kobo
from .models import AuthenticityAssessment, DocumentQAStatus, DocumentRecord
from .serializers import DocumentRecordSerializer
from .services import (
    DocumentFileError,
    DocumentWorkflowError,
    discard_new_document,
    generate_document_id,
    open_source_file,
    record_authenticity_assessment,
    remove_source_file,
    save_source_file,
    set_qa_status,
)
from .tasks import RUNNING, generate_ai_draft

logger = logging.getLogger(__name__)


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


PARTS_PROGRESS = ("Starting", "Read part", "Reading part", "Combining")


def _reads_in_parts(document: DocumentRecord) -> bool:
    """A long, in-parts read legitimately runs much longer than a single one."""
    return document.ai_draft_progress.startswith(PARTS_PROGRESS)


def _already_running(document: DocumentRecord) -> bool:
    return bool(
        document.ai_draft_status == RUNNING
        and document.ai_draft_started_at
        and timezone.now() - document.ai_draft_started_at < timedelta(minutes=75 if _reads_in_parts(document) else 12)
    )


def _check_readable(source_path: str, page_range: str, whole_document: bool) -> int | None:
    """Refuses, before any AI call, a read that cannot work; returns how many
    pages the draft will read (None for files without pages)."""
    pages = pdf_page_count(source_path) if source_path.lower().endswith(".pdf") else None
    if pages is None:
        return None
    limit = MAX_WHOLE_DOCUMENT_PAGES if whole_document else MAX_PDF_PAGES
    if page_range:
        first, last = parse_page_range(page_range, pages, limit)
        return last - first + 1
    if pages > limit:
        raise AIDraftError(
            "pdf_too_long",
            f"This PDF has {pages} pages, and the AI can read at most {MAX_PDF_PAGES} at a time. "
            "Enter the pages that make up this evidence unit (for example 1-100)"
            + (
                ", or tick \u201cRead the whole document in parts\u201d."
                if pages <= MAX_WHOLE_DOCUMENT_PAGES
                else f". This one is also over the {MAX_WHOLE_DOCUMENT_PAGES}-page ceiling for a whole-document read."
            ),
        )
    return pages


class DocumentQuickCreateView(APIView):
    """POST /api/v1/documents/quick-create/ (multipart: file, and optionally
    pages, whole_document, title, document_type) -- the fast way in: upload the
    document and the AI fills in the record's details, then drafts the coding
    form, all in the background. The person reviews the draft and submits.
    Nothing is retyped; nothing reaches KoboToolbox until they submit."""

    permission_classes = [CanManageDocuments]

    def post(self, request):
        if not ai_coding_is_configured():
            return _error("ai_not_configured", "AI drafting hasn't been set up (ANTHROPIC_API_KEY).", 503)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return _error("no_file", "Choose the document to upload.", 400)
        page_range = str(request.data.get("pages") or "").strip()
        whole_document = request.data.get("whole_document") in (True, "true", "1", 1)
        title = str(request.data.get("title") or "").strip()
        given_type = str(request.data.get("document_type") or "").strip().upper()
        if given_type and given_type not in ("OFFICIAL", "SECONDARY", "PLATFORM"):
            return _error("invalid_input", "Document type must be OFFICIAL, SECONDARY or PLATFORM.", 400)

        stem = Path(uploaded.name).stem.replace("_", " ").replace("-", " ").strip()
        document = DocumentRecord.objects.create(
            document_id=generate_document_id(), title=(title or stem or "Untitled document")[:512],
            document_type=given_type or "OFFICIAL",
        )
        try:
            save_source_file(document, uploaded, user=request.user)
            source_path, _, _ = open_source_file(document)
            span = _check_readable(source_path, page_range, whole_document)
        except (DocumentFileError, AIDraftError) as exc:
            # Nothing is left behind: no half-made record for a file that can't be read.
            discard_new_document(document)
            return _error(exc.code, str(exc), exc.status)

        document.ai_draft_status = RUNNING
        document.ai_draft_started_at = timezone.now()
        document.ai_draft_progress = "Starting" if whole_document and span and span > MAX_PDF_PAGES else "Step 1 of 2: reading the document\u2019s details"
        document.save(update_fields=["ai_draft_status", "ai_draft_started_at", "ai_draft_progress"])
        log_action("document.created_from_file", document, {"filename": uploaded.name, "user_id": request.user.id})
        generate_ai_draft.delay(
            document.pk, request.user.id, page_range, whole_document, True, bool(title), bool(given_type),
        )
        document.refresh_from_db()
        return Response(DocumentRecordSerializer(document).data, status=202)


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
        if _already_running(document):
            return _error("already_running", "A draft is already being generated for this document.", 409)
        try:
            source_path, _, _ = open_source_file(document)
        except DocumentFileError as exc:
            return _error(exc.code, str(exc), exc.status)

        page_range = str(request.data.get("pages") or "").strip()
        whole_document = request.data.get("whole_document") in (True, "true", "1", 1)
        try:
            span = _check_readable(source_path, page_range, whole_document)
        except AIDraftError as exc:
            return _error(exc.code, str(exc), exc.status)

        document.ai_draft_status = RUNNING
        document.ai_draft_error = ""
        document.ai_draft_started_at = timezone.now()
        document.ai_draft_progress = "Starting" if whole_document and span and span > MAX_PDF_PAGES else ""
        document.save(update_fields=["ai_draft_status", "ai_draft_error", "ai_draft_started_at", "ai_draft_progress"])
        generate_ai_draft.delay(document.pk, request.user.id, page_range, whole_document)
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
        if document.kobo_submitted_at:
            # A second submission would be a second, duplicate record in KoboToolbox.
            # (If the first was deleted in Kobo, the next sync unlocks the document.)
            return _error("already_submitted", "This document's coding was already submitted to KoboToolbox.", 409)
        if document.ai_draft_status == RUNNING:
            return _error("already_running", "A new draft is being generated. Wait for it to finish before submitting.", 409)
        try:
            result = submit_to_kobo(document, with_current_record_details(document, document.ai_draft), user=request.user)
        except KoboSubmitError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)

        document.kobo_submission_uuid = result["instance_uuid"]
        document.kobo_submitted_at = timezone.now()
        document.kobo_submitted_by = request.user
        document.save(update_fields=["kobo_submission_uuid", "kobo_submitted_at", "kobo_submitted_by"])
        # Bring the portal's own copy of the Document form level with Kobo now,
        # rather than at the next scheduled sync. Never blocks the submission.
        try:
            from apps.kobo.form_sync import sync_form
            from apps.kobo.models import ReconciliationTrigger

            sync_form("documents", ReconciliationTrigger.MANUAL)
        except Exception:  # noqa: BLE001
            logger.warning("Post-submission sync of the Document form failed", exc_info=True)
        return Response(DocumentRecordSerializer(document).data)
