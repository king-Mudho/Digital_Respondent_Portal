"""
Admin management of research-clearance documents, and the respondent-facing screen that lets someone who
opens their invitation link check who approved this study before they answer anything.

Admin side: PI/Admin only (IsAdminOnly) -- these are the study's own authorisation letters, not day-to-day
fieldwork data, and the register is small. Widen later if a Field Coordinator genuinely needs to upload them.

Respondent side: AllowAny + a valid invitation token, exactly the pattern every other respondent-facing step
uses (apps.invitations.services.validate_token) -- never a bare public URL, so a document ID cannot be
scraped by someone who was never invited (docs/06 "Security"). Only is_public=True, active documents with an
uploaded file are ever returned or served; everything else 404s as if it didn't exist.
"""

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminOnly
from api.throttling import PerTokenThrottle, RespondentRateThrottle
from apps.audit.utils import log_action
from apps.invitations.services import TokenValidationError, validate_token

from .models import ClearanceDocument
from .serializers import ClearanceDocumentSerializer, RespondentClearanceDocumentSerializer
from .services import ClearanceFileError, open_file, remove_file, save_file


def _resolve_token(request):
    """A Main-400 invitation link or, since 2026-10-06, a KII informant's link: both respondents see the same
    published letters before they consent. A Main-400 link that is expired or revoked keeps its own error; only a
    link no Main-400 invitation recognises is tried as a KII one."""
    from apps.kii.services import KIITokenValidationError, validate_kii_token

    raw_token = request.data.get("token") if request.method == "POST" else request.query_params.get("t")
    if not raw_token:
        return None, Response({"error": {"code": "token_missing", "message": "A token is required.", "field_errors": {}}}, status=400)
    try:
        return validate_token(raw_token), None
    except TokenValidationError as exc:
        if exc.code != "token_invalid":
            return None, Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)
    try:
        return validate_kii_token(raw_token), None
    except KIITokenValidationError as exc:
        return None, Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=400)


# --- Admin -------------------------------------------------------------------

class ClearanceDocumentListCreateView(APIView):
    """GET/POST /api/v1/clearance-documents/ -- the register. PI/Admin only."""

    permission_classes = [IsAdminOnly]

    def get(self, request):
        docs = ClearanceDocument.objects.all()
        return Response({"results": ClearanceDocumentSerializer(docs, many=True).data})

    def post(self, request):
        serializer = ClearanceDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(created_by=request.user)
        log_action("clearance.document_created", doc, {"title": doc.title, "user_id": request.user.id})
        return Response(ClearanceDocumentSerializer(doc).data, status=201)


class ClearanceDocumentDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/clearance-documents/{id}/. Deleting a document that was ever public is
    refused -- archive it (active=False) instead, so the fact that respondents were once shown it, and what
    it said, is never lost (docs/18 audit-trail convention, same as sample_case.deleted)."""

    permission_classes = [IsAdminOnly]

    def get(self, request, pk):
        return Response(ClearanceDocumentSerializer(get_object_or_404(ClearanceDocument, pk=pk)).data)

    def patch(self, request, pk):
        doc = get_object_or_404(ClearanceDocument, pk=pk)
        before_public = doc.is_public
        serializer = ClearanceDocumentSerializer(doc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if doc.is_public != before_public:
            log_action("clearance.visibility_changed", doc, {"is_public": doc.is_public, "user_id": request.user.id})
        return Response(ClearanceDocumentSerializer(doc).data)

    def delete(self, request, pk):
        from apps.audit.models import AuditEvent

        doc = get_object_or_404(ClearanceDocument, pk=pk)
        ever_shown = doc.is_public or AuditEvent.objects.filter(
            object_type="ClearanceDocument", object_id=str(doc.pk), action="clearance.file_viewed_by_respondent"
        ).exists()
        if ever_shown:
            return Response({
                "error": {"code": "was_public", "message": "This document is or was shown to respondents, so it can't be "
                                                             "deleted -- set it inactive instead.", "field_errors": {}},
            }, status=409)
        log_action("clearance.document_deleted", doc, {"title": doc.title, "user_id": request.user.id})
        doc.delete()
        return Response(status=204)


class ClearanceDocumentFileView(APIView):
    """POST (upload/replace) / GET (download, for staff to check what was uploaded) / DELETE (remove) the
    file for one clearance document. Same grant as the record itself."""

    permission_classes = [IsAdminOnly]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        doc = get_object_or_404(ClearanceDocument, pk=pk)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"error": {"code": "no_file", "message": "No file was sent.", "field_errors": {}}}, status=400)
        try:
            save_file(doc, uploaded, user=request.user)
        except ClearanceFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        log_action("clearance.file_uploaded", doc, {"filename": doc.file_name, "user_id": request.user.id})
        return Response(ClearanceDocumentSerializer(doc).data)

    def get(self, request, pk):
        doc = get_object_or_404(ClearanceDocument, pk=pk)
        try:
            path, filename, content_type = open_file(doc)
        except ClearanceFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        log_action("clearance.file_downloaded_by_staff", doc, {"filename": filename, "user_id": request.user.id})
        response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response

    def delete(self, request, pk):
        doc = get_object_or_404(ClearanceDocument, pk=pk)
        try:
            remove_file(doc)
        except ClearanceFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        log_action("clearance.file_removed", doc, {"user_id": request.user.id})
        return Response(ClearanceDocumentSerializer(doc).data)


# --- Respondent ----------------------------------------------------------------

class RespondentClearanceDocumentsView(APIView):
    """GET /api/v1/respondent-clearance-documents/?t=<token> -- the letters this respondent's invitation
    link entitles them to see: only public, active, uploaded ones. Never lists a title that has no file."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request):
        token, error = _resolve_token(request)
        if error:
            return error
        docs = [d for d in ClearanceDocument.objects.filter(is_public=True, active=True) if d.file_ref]
        return Response({"results": RespondentClearanceDocumentSerializer(docs, many=True).data})


class RespondentClearanceDocumentFileView(APIView):
    """GET /api/v1/respondent-clearance-documents/{id}/file/?t=<token> -- the PDF/image itself. A document
    that is not public, not active, or has no file 404s exactly as if the id did not exist -- it never
    reveals that a non-public clearance document happens to exist at that id."""

    permission_classes = [AllowAny]
    throttle_classes = [PerTokenThrottle, RespondentRateThrottle]

    def get(self, request, pk):
        token, error = _resolve_token(request)
        if error:
            return error
        doc = ClearanceDocument.objects.filter(pk=pk, is_public=True, active=True).first()
        if doc is None or not doc.file_ref:
            return Response({"error": {"code": "not_found", "message": "No such document.", "field_errors": {}}}, status=404)
        try:
            path, filename, content_type = open_file(doc)
        except ClearanceFileError as exc:
            return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)
        log_action("clearance.file_viewed_by_respondent", doc, {
            "sample_case_id": getattr(token, "sample_case_id", None), "kii_record_id": getattr(token, "kii_record_id", None),
        })
        response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response
