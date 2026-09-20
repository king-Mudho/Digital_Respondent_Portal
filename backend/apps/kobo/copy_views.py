from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pagination import PAGE_SIZE_OPTIONS
from apps.audit.utils import log_action

from . import submission_copies as copies


def _error(exc: copies.CopyError) -> Response:
    return Response({"error": {"code": exc.code, "message": str(exc), "field_errors": {}}}, status=exc.status)


class KoboFormsView(APIView):
    """GET /api/v1/kobo/forms/ -- the main-study forms this role may open, and
    whether email is set up."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        forms = copies.forms_for(request.user)
        if not forms:  # the nav doesn't offer this screen to the role; say so rather than show an empty page
            return _error(copies.CopyError("permission_denied", "No KoboToolbox forms are part of your role.", 403))
        return Response({"forms": forms, "email_configured": copies.email_is_configured()})


class KoboFormSubmissionsView(APIView):
    """GET /api/v1/kobo/forms/{key}/submissions/?page= -- newest first, from KoboToolbox."""

    permission_classes = [IsAuthenticated]
    PAGE_SIZE = 20  # the default; ?page_size= overrides it, as on every other list

    def get(self, request, key):
        try:
            copies.require_form(key, request.user)
            page = max(int(request.query_params.get("page", 1)), 1)
            size = min(max(int(request.query_params.get("page_size", self.PAGE_SIZE)), 1), max(PAGE_SIZE_OPTIONS))
            return Response(copies.list_submissions(key, start=(page - 1) * size, limit=size))
        except copies.CopyError as exc:
            return _error(exc)
        except ValueError:
            return _error(copies.CopyError("invalid_input", "Invalid page."))


class KoboSubmissionPDFView(APIView):
    """GET /api/v1/kobo/forms/{key}/submissions/{id}/pdf/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, key, submission_id):
        try:
            copies.require_form(key, request.user)
            pdf, filename, payload = copies.build_pdf(key, submission_id, user=request.user)
        except copies.CopyError as exc:
            return _error(exc)
        log_action("kobo.submission_pdf_downloaded", copies._SubmissionRef(key, submission_id), {
            "form": key, "record": copies.record_label(key, payload), "user_id": request.user.id,
        })
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response


class KoboSubmissionEmailView(APIView):
    """POST /api/v1/kobo/forms/{key}/submissions/{id}/email/ {recipient: "me" | "respondent"}"""

    permission_classes = [IsAuthenticated]

    def post(self, request, key, submission_id):
        try:
            return Response(copies.email_submission(
                key, submission_id, recipient=request.data.get("recipient", ""), user=request.user,
            ))
        except copies.CopyError as exc:
            return _error(exc)


def _pi_only(request):
    if copies.role_of(request.user) != "PI_ADMIN":
        raise copies.CopyError("permission_denied", "Full KoboToolbox data exports are for the PI only.", 403)


class KoboFormDataExportView(APIView):
    """GET /api/v1/kobo/forms/{key}/export/xlsx/ -- every submission with codes,
    labels and a data dictionary. PI only."""

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        from .data_export import build_workbook

        try:
            _pi_only(request)
            content, filename = build_workbook(key, user=request.user)
        except copies.CopyError as exc:
            return _error(exc)
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response


class KoboFormPDFZipView(APIView):
    """GET /api/v1/kobo/forms/{key}/export/pdfs/ -- every completed form as a
    PDF, streamed as a ZIP with a manifest. PI only."""

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        from .data_export import stream_pdf_zip

        try:
            _pi_only(request)
            chunks, filename = stream_pdf_zip(key, user=request.user)
        except copies.CopyError as exc:
            return _error(exc)
        response = StreamingHttpResponse(chunks, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Accel-Buffering"] = "no"
        return response


class KoboRecordLookupView(APIView):
    """GET /api/v1/kobo/forms/{key}/lookup/?record=<Sample_ID|KII ID|DOC-ID> --
    the completed forms for one portal record, so its page can link to them."""

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        record = (request.query_params.get("record") or "").strip()
        try:
            copies.require_form(key, request.user)
            if not record:
                raise copies.CopyError("invalid_input", "record is required.")
            return Response({"results": copies.find_submissions(key, record)})
        except copies.CopyError as exc:
            return _error(exc)


class KoboSyncStatusView(APIView):
    """GET /api/v1/kobo/sync/status/ -- for each form this role may open: how
    many submissions KoboToolbox holds, how many the portal holds, and whether
    they agree."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .form_sync import form_status

        forms = copies.forms_for(request.user)
        if not forms:
            return _error(copies.CopyError("permission_denied", "No KoboToolbox forms are part of your role.", 403))
        return Response({"forms": [form_status(f["key"]) for f in forms]})


class KoboSyncView(APIView):
    """POST /api/v1/kobo/sync/ {form?} -- pull the named form (or every form
    this role may open) from KoboToolbox now. Read-only roles cannot."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .form_sync import form_status, sync_all
        from .models import ReconciliationTrigger

        allowed = [f["key"] for f in copies.forms_for(request.user)]
        if not allowed or copies.role_of(request.user) in copies.READ_ONLY_ROLES:
            return _error(copies.CopyError("permission_denied", "Your role can't run a sync.", 403))
        requested = (request.data.get("form") or "").strip()
        if requested and requested not in allowed:
            return _error(copies.CopyError("permission_denied", "This form isn't part of your role.", 403))
        keys = [requested] if requested else allowed
        logs = sync_all(triggered_by=ReconciliationTrigger.MANUAL, keys=keys)
        failed = [log.error_message for log in logs if log.error_message]
        if not logs:
            return _error(copies.CopyError("kobo_not_configured", "This form isn't connected to KoboToolbox yet.", 503))
        if failed and len(failed) == len(logs):
            return _error(copies.CopyError("kobo_unreachable", f"KoboToolbox couldn't be reached: {failed[0]}", 502))
        return Response({"forms": [form_status(key) for key in keys]})
