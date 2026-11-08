"""Who sees only the work assigned to them (PI decision, 8 Nov 2026).

A Contact RA has always seen only their assigned Main-400 cases. The Research Assistant (calls) role -- the two
telephone RAs who phone both Main-400 respondents and key informants -- sees only the Main-400 cases and the KII
records assigned to them. Every scoping check asks these functions rather than comparing role names itself, so a
new place that scopes cases cannot forget one of the roles.
"""

CONTACT_RA = "CONTACT_RA"
TELEPHONE_RA = "TELEPHONE_RA"
# Roles limited to the Main-400 cases assigned to them.
ASSIGNED_CASE_ROLES = {CONTACT_RA, TELEPHONE_RA}
# Roles whose calls, messages and administered forms earn completion credit (apps/ra/credit.py).
RA_ROLES = {CONTACT_RA, TELEPHONE_RA, "KII_RA"}


def role_name(user) -> str:
    return getattr(getattr(user, "role", None), "name", None) or ""


def assigned_cases_only(user) -> bool:
    return role_name(user) in ASSIGNED_CASE_ROLES


def assigned_kii_only(user) -> bool:
    """The telephone RA sees only the KII records assigned to them; a KII RA still sees every KII record."""
    return role_name(user) == TELEPHONE_RA
