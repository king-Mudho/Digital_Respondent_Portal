from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    PAGE_SIZE = 20  # frontend Pagination assumes the REST_FRAMEWORK page size

    def get(self, request, key):
        try:
            copies.require_form(key, request.user)
            page = max(int(request.query_params.get("page", 1)), 1)
            return Response(copies.list_submissions(key, start=(page - 1) * self.PAGE_SIZE, limit=self.PAGE_SIZE))
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
