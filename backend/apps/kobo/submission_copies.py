"""
Completed KoboToolbox submissions as PDFs: list, download, email.

Covers the three main-study forms. The Questionnaire is also reconciled into
QUANSubmission; the KII Guide and the Document Analysis Tool are read from
KoboToolbox on demand only (the portal stores nothing for them here).

Email goes to exactly two kinds of address, never a typed-in one, because a
PDF is a full research record:
  - "me": the signed-in staff member's own account email;
  - "respondent" (Questionnaire only): an email address recorded for the
    matched case, and only while participation consent stands.
Every download and send is audited (recipient type and a masked address,
never the answers).
"""

import json
import re

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.utils.text import slugify

from apps.audit.utils import log_action

from .pdf import render_submission_pdf

FORMS = {
    "questionnaire": {
        "title": "ABF-FST Main Study Questionnaire",
        "asset_setting": "KOBO_ASSET_UID",
        "record_field": "SAMPLE_ID_FINAL",
        "record_fallbacks": ("sample_id", "admin_consent/SAMPLE_ID"),
        "roles": {"PI_ADMIN", "FIELD_COORDINATOR", "QUAN_QA_RA", "SUPERVISOR_READONLY"},
    },
    "kii": {
        "title": "ABF-FST Main Study KII Guide",
        "asset_setting": "KOBO_KII_ASSET_UID",
        "record_field": "part_a/KII_ID",
        "record_fallbacks": ("KII_ID",),
        "roles": {"PI_ADMIN", "FIELD_COORDINATOR", "KII_RA", "SUPERVISOR_READONLY"},
    },
    "documents": {
        "title": "ABF-FST Document, Digital Platform & Media Analysis Tool",
        "asset_setting": "KOBO_DOCUMENTS_ASSET_UID",
        "record_field": "section_a/DOC_ID",
        "record_fallbacks": ("DOC_ID",),
        "roles": {"PI_ADMIN", "FIELD_COORDINATOR", "DOCUMENTARY_RA", "SUPERVISOR_READONLY"},
    },
}
READ_ONLY_ROLES = {"SUPERVISOR_READONLY"}


class CopyError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def role_of(user) -> str | None:
    return getattr(getattr(user, "role", None), "name", None)


def forms_for(user) -> list[dict]:
    role = role_of(user)
    return [
        {"key": key, "title": spec["title"], "configured": bool(asset_uid(key)) and bool((settings.KOBO_API_TOKEN or "").strip()),
         "can_email": role not in READ_ONLY_ROLES, "can_email_respondent": key == "questionnaire"}
        for key, spec in FORMS.items() if role in spec["roles"]
    ]


def asset_uid(key: str) -> str:
    return (getattr(settings, FORMS[key]["asset_setting"], "") or "").strip()


def require_form(key: str, user, *, write: bool = False) -> dict:
    spec = FORMS.get(key)
    if spec is None:
        raise CopyError("not_found", "Unknown form.", 404)
    if role_of(user) not in spec["roles"] or (write and role_of(user) in READ_ONLY_ROLES):
        raise CopyError("permission_denied", "This form isn't part of your role.", 403)
    if not asset_uid(key) or not (settings.KOBO_API_TOKEN or "").strip():
        raise CopyError("kobo_not_configured", "This form isn't connected to KoboToolbox yet.", 503)
    return spec


def email_is_configured() -> bool:
    backend = settings.EMAIL_BACKEND
    if backend.endswith(("console.EmailBackend", "locmem.EmailBackend", "filebased.EmailBackend")):
        return True
    return bool((settings.EMAIL_HOST or "").strip()) and backend.endswith("smtp.EmailBackend")


# --- KoboToolbox ------------------------------------------------------------

def _kobo_get(path: str, **params):
    try:
        response = requests.get(
            f"{settings.KOBO_API_BASE_URL.rstrip('/')}{path}",
            headers={"Authorization": f"Token {settings.KOBO_API_TOKEN}"},
            params={"format": "json", **params},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise CopyError("kobo_unreachable", f"KoboToolbox couldn't be reached: {exc.__class__.__name__}.", 502) from exc
    if response.status_code == 404:
        if re.search(r"/data/\d+/$", path):
            raise CopyError("not_found", "That submission doesn't exist in KoboToolbox.", 404)
        # The form itself is missing: a wrong or deleted asset UID, not a
        # missing submission, and something only an administrator can fix.
        raise CopyError("kobo_form_not_found", "This form wasn't found in KoboToolbox. Check the portal's form setting.", 502)
    if response.status_code in (401, 403):
        raise CopyError("kobo_auth_failed", "KoboToolbox refused the portal's API token. It may have been changed.", 502)
    if not response.ok:
        raise CopyError("kobo_error", f"KoboToolbox answered HTTP {response.status_code}.", 502)
    return response.json()


def form_content(key: str) -> dict:
    """The deployed form's XLSForm content, cached briefly: labels change only on redeploy."""
    cache_key = f"kobo-form-content:{asset_uid(key)}"
    content = cache.get(cache_key)
    if content is None:
        content = _kobo_get(f"/api/v2/assets/{asset_uid(key)}/")["content"]
        cache.set(cache_key, content, 600)
    return content


def record_label(key: str, payload: dict) -> str:
    spec = FORMS[key]
    for field in (spec["record_field"], *spec["record_fallbacks"]):
        if payload.get(field):
            return str(payload[field])
    return f"Record {payload.get('_id', '')}"


def list_submissions(key: str, *, start: int = 0, limit: int = 25) -> dict:
    body = _kobo_get(
        f"/api/v2/assets/{asset_uid(key)}/data/",
        start=start, limit=limit, sort=json.dumps({"_submission_time": -1}),
    )
    from .form_sync import portal_copy_flags

    rows = body.get("results", [])
    in_portal = portal_copy_flags(key, rows)
    return {
        "count": body.get("count", 0),
        "results": [
            {"id": row.get("_id"), "record": record_label(key, row),
             "submitted_at": row.get("_submission_time"), "submitted_by": row.get("_submitted_by") or "",
             "portal_copy": in_portal.get(row.get("_id"), False)}
            for row in rows
        ],
    }


def find_submissions(key: str, record: str) -> list[dict]:
    """Completed submissions for one portal record (a Sample_ID, KII ID or
    DOC-ID), matched on the form's own identifier field."""
    spec = FORMS[key]
    fields = (spec["record_field"], *spec["record_fallbacks"])
    query = {"$or": [{field: record} for field in fields]}
    body = _kobo_get(
        f"/api/v2/assets/{asset_uid(key)}/data/",
        query=json.dumps(query), fields=json.dumps(["_id", "_submission_time", "_submitted_by"]),
        sort=json.dumps({"_submission_time": -1}), limit=20,
    )
    return [
        {"id": row.get("_id"), "submitted_at": row.get("_submission_time"), "submitted_by": row.get("_submitted_by") or ""}
        for row in body.get("results", [])
    ]


def fetch_submission(key: str, submission_id: int) -> dict:
    return _kobo_get(f"/api/v2/assets/{asset_uid(key)}/data/{int(submission_id)}/")


def build_pdf(key: str, submission_id: int, *, user) -> tuple[bytes, str, dict]:
    payload = fetch_submission(key, submission_id)
    label = record_label(key, payload)
    pdf = render_submission_pdf(
        form_content=form_content(key), payload=payload, form_title=FORMS[key]["title"], record_label=label,
    )
    filename = f"{slugify(key)}-{slugify(label) or submission_id}.pdf"
    return pdf, filename, payload


# --- Email ------------------------------------------------------------------

def _mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _respondent_email(payload: dict) -> str:
    """The respondent's own address, from the case this submission matched."""
    from apps.consent.services import has_given_consent
    from apps.contacts.models import Respondent
    from apps.sampling.models import SampleCase

    from .services import _payload_sample_id

    sample_id = _payload_sample_id(payload)
    case = SampleCase.objects.filter(sample_id=sample_id).first() if sample_id else None
    if case is None:
        raise CopyError("no_case", "This submission isn't matched to a case, so there is no respondent address.")
    if not has_given_consent(case):
        raise CopyError("no_consent", "The participant's consent isn't in place, so nothing can be sent to them.", 409)
    respondent = (
        Respondent.objects.filter(sample_case=case, is_eligible=True).exclude(email="").order_by("-id").first()
        or Respondent.objects.filter(sample_case=case).exclude(email="").order_by("-id").first()
    )
    if respondent is None:
        raise CopyError("no_email", "No email address is recorded for this respondent. Add one on the case page.")
    return respondent.email


def email_submission(key: str, submission_id: int, *, recipient: str, user) -> dict:
    require_form(key, user, write=True)
    if not email_is_configured():
        raise CopyError("email_not_configured", "Email isn't set up on the server yet.", 503)
    if recipient not in ("me", "respondent"):
        raise CopyError("invalid_input", "Choose who receives the copy.")
    if recipient == "respondent" and key != "questionnaire":
        raise CopyError("invalid_input", "Only questionnaire copies can go to a respondent.")

    pdf, filename, payload = build_pdf(key, submission_id, user=user)
    label = record_label(key, payload)
    if recipient == "me":
        address = (user.email or "").strip()
        if not address:
            raise CopyError("no_email", "Your account has no email address. Ask the PI to add one.")
        subject = f"{FORMS[key]['title']} - {label}"
        body = (
            f"Attached is the completed {FORMS[key]['title']} record {label}, as requested from the "
            "ABF-FST Research Operations Centre.\n\nThis is a confidential research record. Do not forward it."
        )
    else:
        address = _respondent_email(payload)
        subject = "Your ABF-FST research questionnaire responses"
        body = (
            "Thank you for taking part in the ABF-FST research study at Chinhoyi University of Technology.\n\n"
            "As requested, a copy of the answers you submitted is attached. It contains no score, rating or "
            "financing decision. If anything in it is wrong, or you have questions about the study, reply to "
            "this email.\n\nABF-FST research team"
        )

    message = EmailMessage(
        subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[address],
        reply_to=[settings.STUDY_REPLY_TO_EMAIL] if settings.STUDY_REPLY_TO_EMAIL else None,
    )
    message.attach(filename, pdf, "application/pdf")
    message.send(fail_silently=False)

    log_action("kobo.submission_copy_emailed", _SubmissionRef(key, submission_id), {
        "form": key, "record": label, "recipient_type": recipient, "recipient": _mask(address),
        "user_id": user.id,
    })
    return {"sent_to": _mask(address), "recipient_type": recipient}


class _SubmissionRef:
    def __init__(self, key, submission_id):
        self.pk = f"{key}:{submission_id}"
