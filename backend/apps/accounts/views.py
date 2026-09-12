from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import CanViewSampleCases

from .models import Role, User


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/ -- any authenticated user changes
    their own password. Not role-gated (everyone should be able to rotate
    their own credentials); there is no admin-set-another-user's-password
    endpoint here, only Django admin for that."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password", "")
        new_password = request.data.get("new_password", "")

        if not request.user.check_password(current_password):
            return Response(
                {"error": {"code": "invalid_current_password", "message": "Current password is incorrect.", "field_errors": {}}},
                status=400,
            )

        try:
            validate_password(new_password, user=request.user)
        except ValidationError as exc:
            return Response(
                {"error": {"code": "invalid_new_password", "message": " ".join(exc.messages), "field_errors": {}}},
                status=400,
            )

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        return Response({"status": "password_changed"})


class ContactRAListView(APIView):
    """GET /api/v1/auth/contact-ras/ -- usernames of every Contact RA
    account, for the "Assigned RA" dropdown on the sample case detail page.
    CanViewSampleCases: whoever can see the assignment field (Field
    Coordinator/Admin to set it, Contact RA/Supervisor to see who it is)
    can also see the list of possible assignees."""

    permission_classes = [CanViewSampleCases]

    def get(self, request):
        role = Role.objects.filter(name=Role.CONTACT_RA).first()
        users = User.objects.filter(role=role, is_active=True).order_by("username") if role else []
        return Response({"results": [{"id": u.id, "username": u.username} for u in users]})
