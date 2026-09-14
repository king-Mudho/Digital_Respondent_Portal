"""
Which Kobo answers the QA "missing required fields" rule checks.

Derived from the deployed form rather than typed in: every question the form
itself marks required and shows to every consenting respondent, named the
way the Kobo API returns it (group path included, e.g. `abi_gr/GR1`).
Questions with their own display condition (an "If Other, please specify",
the eligibility follow-ups) are left out, because a missing answer there is
usually correct. The portal's own resolved Sample_ID is always included.
"""

ALWAYS_REQUIRED = ["SAMPLE_ID_FINAL"]
QUESTION_TYPES_SKIPPED = {"note", "hidden", "calculate", "start", "end", "today", "username", "deviceid"}


def required_field_names(survey: list[dict]) -> list[str]:
    path: list[str] = []
    names = list(ALWAYS_REQUIRED)
    for row in survey:
        row_type = (row.get("type") or "").strip()
        name = row.get("name") or row.get("$autoname") or ""
        if row_type in ("begin_group", "begin group"):
            path.append(name)
            continue
        if row_type in ("end_group", "end group"):
            if path:
                path.pop()
            continue
        if row_type.split(" ")[0] in QUESTION_TYPES_SKIPPED or row_type in ("begin_repeat", "end_repeat"):
            continue
        required = row.get("required")
        if required in (True, "true", "yes", "TRUE") and not row.get("relevant"):
            full = "/".join([*path, name])
            if full not in names:
                names.append(full)
    return names
