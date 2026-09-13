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

Sep 2026 hardening pass: CONTACT_RA was not included in any permission
class's allowed set at all -- every internal endpoint returned 403 for that
role, a confirmed total lockout with no corresponding note in docs/18 (which
documents it as having "assigned cases" access, not "no access anywhere").
SUPERVISOR_READONLY was similarly under-granted (missing read access to
sample cases, contacts, KII, documents, QA and invitations that docs/18's
"Read-only, all" calls for) *and* over-granted (included in
IsAnalystOrAdmin, which also gates the de-identified export -- docs/18 says
"No" for Supervisor there). Both are fixed below.

"Assigned cases" for Contact RA is literal, not a simplification:
SampleCase.assigned_ra records which Contact RA owns a case, and each
view's get_queryset() filters on it (a case assigned to someone else 404s
rather than 403s, so its existence isn't leaked either). These classes
answer "may this role touch this kind of thing at all"; the
assignment-scoping happens per-queryset alongside them.

Which *screens* each role sees in the Research Operations Centre is derived
from these same classes in api/navigation.py -- keep the two in step.
"""

from rest_framework.permissions import BasePermission

ADMIN_ROLES = {"PI_ADMIN"}
READ_ONLY_METHODS = ("GET", "HEAD", "OPTIONS")


def _authenticated_role(request):
    """The requesting user's Role.name, or None if not authenticated."""
    if not (request.user and request.user.is_authenticated):
        return None
    role = getattr(request.user, "role", None)
    return getattr(role, "name", None)


class IsFieldCoordinatorOrAdmin(BasePermission):
    """Sample-case state changes (reserve activation, workflow transition),
    fieldwork cost logging, and triggering a Kobo sync -- Field Coordinator/
    Admin authority per docs/18's access matrix. Supervisor gets read-only
    access to whatever GET-only view uses this class (its own "Read-only,
    all" grant); it never reaches the write actions gated by this class,
    since those views have no safe-method path to fall back to."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR"}:
            return True
        return role == "SUPERVISOR_READONLY" and request.method in READ_ONLY_METHODS


class CanViewSampleCases(BasePermission):
    """SampleCase list/detail: full read/write for Field Coordinator/Admin;
    read-only for Contact RA (needs to see which case and its current
    status to do contact work) and Supervisor (docs/18: "Read-only, all")."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR"}:
            return True
        if role in {"CONTACT_RA", "SUPERVISOR_READONLY"}:
            return request.method in READ_ONLY_METHODS
        return False


class CanManageContact(BasePermission):
    """Contact events, appointment status, and invitation issue/revoke --
    the actual job of a Contact RA (docs/18: "assigned cases"; see module
    docstring on why this grants all cases, not an assignment-scoped
    subset). Field Coordinator/Admin get full access too; Supervisor is
    read-only, matching every other class here."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR", "CONTACT_RA"}:
            return True
        return role == "SUPERVISOR_READONLY" and request.method in READ_ONLY_METHODS


class IsQAOrAdmin(BasePermission):
    """QUAN QA queue and QA dashboard. Supervisor gets read-only access.

    Sep 2026 role audit: this class previously also admitted KII_RA and
    DOCUMENTARY_RA, and gated the KII and Documents modules as well -- so a
    KII RA could edit documentary-evidence records and a Documentary RA
    could take QA decisions on QUAN submissions. docs/18's matrix is
    row-per-role and narrower than that ("KII RA: Assigned KII records";
    "Documentary RA: Assigned document records"; "QUAN/Kobo QA RA:
    QA-relevant fields"), so QA/KII/Documents are now three separate
    grants -- see CanManageKII and CanManageDocuments below."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR", "QUAN_QA_RA"}:
            return True
        return role == "SUPERVISOR_READONLY" and request.method in READ_ONLY_METHODS


class CanManageKII(BasePermission):
    """KII register/detail and its status, consent, transcript and coding
    actions -- docs/18: "KII RA: Assigned KII records"."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR", "KII_RA"}:
            return True
        return role == "SUPERVISOR_READONLY" and request.method in READ_ONLY_METHODS


class CanManageDocuments(BasePermission):
    """Documentary-evidence register/detail, authenticity assessment and QA
    status -- docs/18: "Documentary RA: Assigned document records"."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        if role in ADMIN_ROLES | {"FIELD_COORDINATOR", "DOCUMENTARY_RA"}:
            return True
        return role == "SUPERVISOR_READONLY" and request.method in READ_ONLY_METHODS


class CanViewKIIDocumentDashboard(BasePermission):
    """The KII/document aggregate dashboard. docs/18 grants this to KII RA
    and Documentary RA ("KII/document dashboard only") on top of the roles
    with general dashboard access -- IsAnalystOrAdmin alone excluded both,
    so neither could open the one dashboard its own row names."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        return role in ADMIN_ROLES | {
            "FIELD_COORDINATOR", "ANALYST", "SUPERVISOR_READONLY", "KII_RA", "DOCUMENTARY_RA",
        }


class IsAnalystOrAdmin(BasePermission):
    """Aggregate dashboard reads. Supervisor is included here (docs/18:
    dashboards "Yes") -- every view gated by this class is GET-only anyway,
    so there is no separate write path to carve out."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        return role in ADMIN_ROLES | {"ANALYST", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"}


class CanExportDeidentified(BasePermission):
    """De-identified analysis export. Supervisor is deliberately excluded
    here (docs/18: export column is "No" for Supervisor) even though it has
    dashboard access via IsAnalystOrAdmin -- export is a narrower, separate
    grant, not implied by the dashboard one."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        if role is None:
            return False
        return role in ADMIN_ROLES | {"ANALYST", "FIELD_COORDINATOR"}


class IsAdminOnly(BasePermission):
    """Operational export (contact data included), audit log, role/
    threshold config -- PI/Admin only. docs/18's "Framework/threshold
    config" column is "No" for every other role, Supervisor included, so
    this one is never widened."""

    def has_permission(self, request, view):
        role = _authenticated_role(request)
        return role is not None and role in ADMIN_ROLES
