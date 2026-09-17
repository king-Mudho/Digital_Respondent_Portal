"""
Submits a reviewed AI draft to KoboToolbox as a completed Document Analysis
Tool record, via the OpenRosa submission API every ODK-compatible client
(KoboCollect, Enketo) uses -- POST {KOBO_OPENROSA_BASE_URL}/{account}/
submission with the form's own XML instance as multipart. A different host
and protocol from the kf. API v2 used elsewhere in apps/kobo/ (confirmed
2026-09-17 against the live project's deployment__data_download_links,
which are all served from kc., not kf.).

NEVER called automatically. apps/evidence/ai_coding.py only ever produces a
draft; this module is reached exclusively from a Documentary RA's explicit
"Submit to KoboToolbox" click on the reviewed draft (views.py
DocumentAISubmitView) -- see ai_coding.py's docstring for why that human
step is not optional for this particular form.
"""

import uuid
from xml.etree import ElementTree as ET

import requests
from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action

from .document_tool_schema import SCHEMA
from .models import DocumentRecord


class KoboSubmitError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code, self.status = code, status
        super().__init__(message)


def kobo_submit_is_configured() -> bool:
    return bool((settings.KOBO_ACCOUNT_USERNAME or "").strip())


def _set_text(parent: ET.Element, tag: str, value) -> None:
    el = ET.SubElement(parent, tag)
    el.text = "" if value is None else str(value)


def _group_element(root: ET.Element, cache: dict[tuple, ET.Element], path_parts: list[str]) -> ET.Element:
    """Returns the (creating if needed) nested group element for path_parts,
    e.g. ["section_a"] -> <section_a> under root. Cached so every field in
    the same group reuses one element instead of creating a duplicate."""
    key = tuple(path_parts)
    if key in cache:
        return cache[key]
    parent = root if len(path_parts) == 1 else _group_element(root, cache, path_parts[:-1])
    el = ET.SubElement(parent, path_parts[-1])
    cache[key] = el
    return el


def build_submission_xml(document: DocumentRecord, answers: dict, *, submitted_by, instance_uuid: str) -> str:
    """Builds a full OpenRosa/ODK instance XML for this form from a flat
    answers dict (field path -> value; select_multiple as a list; the
    repeat group as a list of dicts under "section_j/metric_repeat"),
    matching the deployed form's own field order and group nesting exactly
    (apps/evidence/document_tool_schema.json, generated from and verified
    against the live asset's own parsed $xpath values -- see
    build_document_tool_schema.py)."""
    doc_id_in_answers = answers.get("section_a/DOC_ID")
    if doc_id_in_answers and doc_id_in_answers != document.document_id:
        # A draft edited/regenerated out of step with its own record --
        # submitting it would create a Kobo record under one DOC-ID that
        # the portal files under a different one, breaking the DOC-ID match
        # the whole coding workflow depends on (docs/14).
        raise KoboSubmitError(
            "doc_id_mismatch",
            f"Draft DOC-ID '{doc_id_in_answers}' does not match this record's '{document.document_id}'.",
        )
    # The OpenRosa submission endpoint on this KoboToolbox deployment
    # (backend="openrosa", but no legacy KoboCAT-side XForm record --
    # confirmed 2026-09-17 by testing against the live project, then
    # cleaning up the two test submissions) routes a submission by the
    # root element's own tag/id attribute matching the asset UID, NOT the
    # XLSForm's id_string -- unlike a self-hosted/classic KoboCAT server,
    # where id_string is what matches. Using id_string here 404s.
    asset_uid = settings.KOBO_DOCUMENTS_ASSET_UID
    root = ET.Element(asset_uid, attrib={"id": asset_uid, "version": SCHEMA["version"]})
    group_cache: dict[tuple, ET.Element] = {}
    now = timezone.now()

    meta = SCHEMA["meta_fields"]
    _set_text(root, meta["start"], now.isoformat())
    _set_text(root, meta["end"], now.isoformat())
    _set_text(root, meta["today"], now.date().isoformat())
    _set_text(root, meta["deviceid"], "abf-fst-research-portal")
    _set_text(root, meta["username"], getattr(submitted_by, "username", ""))

    repeat_answers = answers.get("section_j/metric_repeat") or []
    for field in SCHEMA["fields"]:
        if field["in_repeat"]:
            continue  # handled once below, per repeat instance
        parts = field["path"].split("/")
        parent = root if len(parts) == 1 else _group_element(root, group_cache, parts[:-1])
        value = answers.get(field["path"])
        if field["type"] == "select_multiple" and isinstance(value, list):
            value = " ".join(str(v) for v in value)
        _set_text(parent, field["name"], value)

    section_j = _group_element(root, group_cache, ["section_j"])
    repeat_fields = [f for f in SCHEMA["fields"] if f["path"].startswith("section_j/metric_repeat/")]
    for item in repeat_answers:
        repeat_el = ET.SubElement(section_j, "metric_repeat")
        for field in repeat_fields:
            value = item.get(field["name"])
            _set_text(repeat_el, field["name"], value)

    meta_el = ET.SubElement(root, "meta")
    _set_text(meta_el, "instanceID", f"uuid:{instance_uuid}")

    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")


def submit_to_kobo(document: DocumentRecord, answers: dict, *, user) -> dict:
    """Submits the (reviewed) draft as a completed record and returns
    {"instance_uuid": ..., "status_code": ...}. Raises KoboSubmitError on
    any failure -- the caller (views.py) never marks a document as
    submitted unless this actually returns."""
    if not kobo_submit_is_configured():
        raise KoboSubmitError("kobo_submit_not_configured", "KOBO_ACCOUNT_USERNAME hasn't been set.", 503)

    instance_uuid = str(uuid.uuid4())
    xml = build_submission_xml(document, answers, submitted_by=user, instance_uuid=instance_uuid)
    url = f"{settings.KOBO_OPENROSA_BASE_URL.rstrip('/')}/{settings.KOBO_ACCOUNT_USERNAME}/submission"

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Token {settings.KOBO_API_TOKEN}"},
            files={"xml_submission_file": ("submission.xml", xml, "text/xml")},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise KoboSubmitError("kobo_unreachable", f"KoboToolbox couldn't be reached: {exc.__class__.__name__}.") from exc

    # OpenRosa: 201 Created is a fresh success; 202 means this instanceID
    # was already accepted (safe to treat as success -- a retry of the same
    # submission, not a duplicate record, since instance_uuid is unique per
    # call and only ever reused if this exact function call is retried).
    if response.status_code not in (201, 202):
        raise KoboSubmitError(
            "kobo_submission_rejected",
            f"KoboToolbox rejected the submission (HTTP {response.status_code}): {response.text[:300]}",
        )

    log_action("document.kobo_submission_created", document, {
        "instance_uuid": instance_uuid, "user_id": getattr(user, "id", None), "status_code": response.status_code,
    })
    return {"instance_uuid": instance_uuid, "status_code": response.status_code}
