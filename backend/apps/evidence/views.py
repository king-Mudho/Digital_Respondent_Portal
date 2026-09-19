from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanManageDocuments
from apps.audit.utils import log_action

from .ai_coding import DETERMINISTIC_FIELDS, AIDraftError, ai_coding_is_configured, generate_draft
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
        document = get_object_or_404(DocumentRecord, pk=pk)
        try:
            source_path, _, source_content_type = open_source_file(document)
        except DocumentFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)

        try:
            draft = generate_draft(
                document, source_path=source_path, source_content_type=source_content_type, user=request.user,
            )
        except AIDraftError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)

        document.ai_draft = draft
        document.ai_draft_generated_at = timezone.now()
        document.ai_draft_model = draft.get("_generated_by_model", "")
        document.save(update_fields=["ai_draft", "ai_draft_generated_at", "ai_draft_model"])
        log_action("document.ai_draft_generated", document, {
            "model": document.ai_draft_model, "user_id": request.user.id,
        })
        return Response(DocumentRecordSerializer(document).data)

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
