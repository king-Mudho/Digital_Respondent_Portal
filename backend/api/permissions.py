"""
Role-based DRF permission classes.

Role/access matrix is docs/18_DATA_PRIVACY_AND_COMPLIANCE.md "Access control
matrix". These are enforced server-side on every internal endpoint -- never
relying on the frontend hiding a button as the only protection (AGENTS.md,
docs/08_BACKEND_ARCHITECTURE.md "Permissions").

Public respondent endpoints (invitation validation, eligibility, consent,
Kobo redirect) use AllowAny at the DRF layer, but every query within them is
scoped to the single SampleCase resolved from the validated invitation
token by the view/service itself -- never a list endpoint for anonymous
callers (docs/06_API_ARCHITECTURE.md "Security").
"""

from rest_framework.permissions import BasePermission

ADMIN_ROLES = {"PI_ADMIN"}


def _role_name(user):
    role = getattr(user, "role", None)
    return getattr(role, "name", None)


class IsFieldCoordinatorOrAdmin(BasePermission):
    """Sample import, invitation issuance, reserve activation."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_name(request.user) in ADMIN_ROLES | {"FIELD_COORDINATOR"}


class IsQAOrAdmin(BasePermission):
    """QA queue read/write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_name(request.user) in ADMIN_ROLES | {
            "FIELD_COORDINATOR",
            "QUAN_QA_RA",
            "KII_RA",
            "DOCUMENTARY_RA",
        }


class IsAnalystOrAdmin(BasePermission):
    """De-identified export, dashboard reads."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_name(request.user) in ADMIN_ROLES | {
            "ANALYST",
            "FIELD_COORDINATOR",
            "SUPERVISOR_READONLY",
        }


class IsAdminOnly(BasePermission):
    """Operational export (contact data included), audit log, role/threshold config."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_name(request.user) in ADMIN_ROLES


class IsSupervisorReadOnly(BasePermission):
    """Read-only access to everything, per the access matrix -- never write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if _role_name(request.user) in ADMIN_ROLES:
            return True
        if _role_name(request.user) != "SUPERVISOR_READONLY":
            return False
        return request.method in ("GET", "HEAD", "OPTIONS")
