from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from api.navigation import (
    CHILD_PATH_PARENTS,
    READ_ONLY_ROLES,
    UNIVERSAL_PATHS,
    can_open_path,
    landing_path_for_role,
    screens_for_role,
)
from api.permissions import CanViewSampleCases
from api.throttling import LoginRateThrottle

from .models import Role, User


class InternalTokenObtainView(TokenObtainPairView):
    """POST /api/v1/auth/token/ -- internal sign-in.

    Only exists to replace the default throttles: sharing the generic
    "anon" bucket with the public respondent endpoints meant a research
    team behind one office IP could exhaust its own sign-in allowance on
    respondent traffic, and DRF's 429 reached the login screen as
    "Invalid username or password".
    """

    throttle_classes = [LoginRateThrottle]


class CurrentUserView(APIView):
    """GET /api/v1/auth/me/ -- who am I, and which screens may I open.

    The Research Operations Centre's nav bar renders exactly the `screens`
    list this returns, and AdminShell refuses to render a screen not in it.
    Before this existed the frontend showed every nav link to every role,
    so (for example) a Contact RA saw "Audit Log" and "Export" and got a
    403 on click. This is a UX contract only -- api/permissions.py is still
    what actually protects each endpoint."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role_name = getattr(getattr(request.user, "role", None), "name", None)
        screens = screens_for_role(role_name)
        return Response({
            "username": request.user.username,
            "role": role_name,
            "role_label": dict(Role.NAME_CHOICES).get(role_name, ""),
            "screens": screens,
            "landing_path": landing_path_for_role(role_name),
            # Shipped so the frontend guard is generic and driven by server
            # data -- the path policy lives in api/navigation.py only, and
            # can't drift into a second hardcoded copy in the UI.
            "universal_paths": list(UNIVERSAL_PATHS),
            "child_paths": CHILD_PATH_PARENTS,
            # Coarse "this role never writes anywhere" flag, so a screen
            # that mixes a read view with a write form (cost, reserve) can
            # hide the form rather than offer a button that always 403s.
            "read_only": role_name in READ_ONLY_ROLES,
        })


class AccessCheckView(APIView):
    """GET /api/v1/auth/can-open/?path=/admin/x -- may this role open this
    admin path, including detail routes that have no nav entry of their own
    (e.g. /admin/kii/12)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role_name = getattr(getattr(request.user, "role", None), "name", None)
        path = request.query_params.get("path", "")
        return Response({"path": path, "allowed": can_open_path(role_name, path)})


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
