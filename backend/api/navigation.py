"""
Which internal screens each role may open -- the single source of truth for
the Research Operations Centre's navigation.

This exists because the frontend used to render *every* nav link to *every*
role: a Contact RA saw "Audit Log", "Export", "QA Queue" and every
dashboard, clicked them, and got a 403 or an empty broken screen. The server
was enforcing correctly; the UI just wasn't telling the truth about it.

Each entry here is deliberately paired with the DRF permission class that
actually guards that screen's endpoints (api/permissions.py), so the nav can
never drift into offering a screen the API will refuse. If you change a
permission class, change its row here in the same commit.

`GET /api/v1/auth/me/` serves this to the frontend; AdminNav renders exactly
what it returns and AdminShell refuses to render a screen that isn't in it.
It is a UX contract, never the security boundary -- every endpoint still
enforces its own permission class server-side regardless of what the nav
shows (AGENTS.md, docs/08_BACKEND_ARCHITECTURE.md "Permissions").
"""

from apps.accounts.models import Role

# Roles whose entire grant is read-only (docs/18's access matrix): the UI
# hides write controls for these rather than offering buttons that always
# 403. Supervisor is "Read-only, all"; Analyst is dashboards + de-identified
# export with "No write access anywhere".
READ_ONLY_ROLES = {Role.SUPERVISOR_READONLY, Role.ANALYST}

# screen id -> (path, nav label, roles that may open it)
SCREENS = {
    "dashboard_executive": (
        "/admin/dashboard", "Executive",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST, Role.SUPERVISOR_READONLY},
    ),
    "dashboard_sampling": (
        "/admin/dashboard/sampling", "Sampling",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST, Role.SUPERVISOR_READONLY},
    ),
    "dashboard_contact": (
        "/admin/dashboard/contact", "Contact",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST, Role.SUPERVISOR_READONLY},
    ),
    # docs/18: QUAN/Kobo QA RA gets "QA dashboard only".
    "dashboard_qa": (
        "/admin/dashboard/qa", "QA Dashboard",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.QUAN_QA_RA, Role.SUPERVISOR_READONLY},
    ),
    # docs/18: KII RA and Documentary RA each get "KII/document dashboard only".
    "dashboard_kii_documents": (
        "/admin/dashboard/kii-documents", "KII/Doc Dashboard",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST, Role.SUPERVISOR_READONLY,
         Role.KII_RA, Role.DOCUMENTARY_RA},
    ),
    "sample_register": (
        "/admin/sample", "Main-400 Register",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.CONTACT_RA, Role.SUPERVISOR_READONLY},
    ),
    # Registering an organisation is a create-only screen; Contact RA can read
    # sample cases but never creates organisations, so it stays out of its nav
    # (the Main-400 Register already gives it the read view it needs).
    "organisations": (
        "/admin/organisations", "Organisations",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.SUPERVISOR_READONLY},
    ),
    "appointments": (
        "/admin/appointments", "Appointments",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.CONTACT_RA, Role.SUPERVISOR_READONLY},
    ),
    # Reminders due for sending by hand (messaging.views, CanManageContact).
    "follow_ups": (
        "/admin/follow-ups", "Follow-ups",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.CONTACT_RA, Role.SUPERVISOR_READONLY},
    ),
    # PDF copies of completed Kobo forms; each role sees only its own form
    # (kobo.submission_copies.FORMS), enforced server-side per request.
    "kobo_submissions": (
        "/admin/submissions", "Form PDFs",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.QUAN_QA_RA, Role.KII_RA, Role.DOCUMENTARY_RA,
         Role.SUPERVISOR_READONLY},
    ),
    "qa_queue": (
        "/admin/qa", "QA Queue",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.QUAN_QA_RA, Role.SUPERVISOR_READONLY},
    ),
    "qa_exceptions": (
        "/admin/qa/exceptions", "QA Exceptions",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.QUAN_QA_RA, Role.SUPERVISOR_READONLY},
    ),
    "kii_register": (
        "/admin/kii", "KII Register",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.KII_RA, Role.SUPERVISOR_READONLY},
    ),
    "documents": (
        "/admin/documents", "Documents",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.DOCUMENTARY_RA, Role.SUPERVISOR_READONLY},
    ),
    "reserve": (
        "/admin/reserve", "Reserve Activation",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.SUPERVISOR_READONLY},
    ),
    "cost": (
        "/admin/cost", "Cost",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST, Role.SUPERVISOR_READONLY},
    ),
    "audit": (
        "/admin/audit", "Audit Log",
        {Role.PI_ADMIN},
    ),
    "export": (
        "/admin/export", "Export",
        {Role.PI_ADMIN, Role.FIELD_COORDINATOR, Role.ANALYST},
    ),
}

# Screens every signed-in role may open, and which never appear in the main
# nav bar (the account screen sits next to "Sign out" instead).
UNIVERSAL_PATHS = ("/admin/account",)

# Detail/sub-screens reached from a listed screen rather than the nav bar.
# Guarding these by prefix keeps a Contact RA out of, say, a KII record it
# has no business opening, without needing a nav entry per detail route.
CHILD_PATH_PARENTS = {
    "/admin/sample/": "sample_register",
    "/admin/kii/": "kii_register",
    "/admin/documents/": "documents",
    "/admin/proit/": "sample_register",
}


def screens_for_role(role_name: str | None) -> list[dict]:
    """Nav entries this role may open, in the order declared above."""
    if not role_name:
        return []
    return [
        {"id": screen_id, "path": path, "label": label}
        for screen_id, (path, label, roles) in SCREENS.items()
        if role_name in roles
    ]


def landing_path_for_role(role_name: str | None) -> str:
    """Where this role lands after signing in. The old hardcoded
    /admin/dashboard sent Contact/QA/KII/Documentary RAs straight to a screen
    their own role is refused -- four of eight roles landed on a dead end."""
    screens = screens_for_role(role_name)
    return screens[0]["path"] if screens else "/admin/account"


def can_open_path(role_name: str | None, path: str) -> bool:
    """Whether this role may open an arbitrary admin path, including detail
    routes not in the nav (see CHILD_PATH_PARENTS)."""
    if not role_name:
        return False
    if any(path == p or path.startswith(p.rstrip("/") + "/") for p in UNIVERSAL_PATHS):
        return True

    allowed_ids = {s["id"] for s in screens_for_role(role_name)}
    for prefix, parent_id in CHILD_PATH_PARENTS.items():
        if path.startswith(prefix):
            return parent_id in allowed_ids

    return any(SCREENS[screen_id][0] == path for screen_id in allowed_ids)
