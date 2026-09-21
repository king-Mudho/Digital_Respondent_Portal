"""Sends a case's finished pre-interview profile to KoboToolbox as one record in the PROIT Interview Profile
form, so what was known beforehand, what the respondent said and the reconciled value are all held in KoboToolbox
alongside the interview itself. Same OpenRosa route as the Document form (apps/evidence/kobo_submit.py).

Automatic, once per profile, when the profile reaches RECONCILED (or a coordinator records a protocol deviation).
Never blocks the interview or the reconciliation: a failure is logged and can be retried with
`manage.py push_proit_to_kobo`. Inactive (no error) until KOBO_PROIT_ASSET_UID is set."""

import logging
import uuid
from xml.etree import ElementTree as ET

import requests
from django.conf import settings
from django.utils import timezone

from apps.audit.utils import log_action

from . import kobo_form as F
from .models import AIProposalStatus, PreProfile

logger = logging.getLogger(__name__)


class ProitKoboError(Exception):
    pass


def is_configured() -> bool:
    return bool((settings.KOBO_PROIT_ASSET_UID or "").strip() and (settings.KOBO_ACCOUNT_USERNAME or "").strip())


def _text(parent, tag, value):
    el = ET.SubElement(parent, tag)
    el.text = "" if value is None else str(value)


def _iso(value):
    return value.isoformat() if value else ""


def _sources(field) -> str:
    rows = []
    for s in field.sources.all():
        rows.append(" | ".join([s.source_title, s.publisher, _iso(s.source_date), s.source_authority, s.locator]))
    return "\n".join(rows)


def profile_values(profile: PreProfile) -> dict:
    fields = list(profile.fields.all().prefetch_related("sources").order_by("id"))
    if profile.sample_case_id:
        record_id, record_type, org = profile.sample_case.sample_id, "QUAN", profile.sample_case.organisation.name
    else:
        record_id, record_type, org = profile.kii_record.kii_id, "KII", profile.kii_record.organisation.name if profile.kii_record.organisation_id else ""
    ai = profile.ai_proposals.filter(status__in=[AIProposalStatus.ACCEPTED, AIProposalStatus.EDITED]).exists()
    return {
        "record_id": record_id, "record_type": record_type, "organisation": org,
        "reconciliation_status": profile.reconciliation_status,
        "protocol_deviation": "yes" if profile.protocol_deviation else "no",
        "deviation_note": profile.deviation_note,
        "locked_at": _iso(profile.prepopulation_locked_at), "interview_completed_at": _iso(profile.interview_completed_at),
        "ai_assisted": "yes" if ai else "no",
        "facts_total": len(fields), "facts_verified": sum(1 for f in fields if f.verification_status),
        "facts_reconciled": sum(1 for f in fields if f.reconciled_value),
        "background_questions_avoided": profile.background_questions_avoided,
        "burden_reduction_score": profile.burden_reduction_score if profile.burden_reduction_score is not None else "",
        "known_evidence_summary": profile.known_evidence_summary, "unresolved_gaps": profile.unresolved_gaps,
        "contradictions": profile.contradictions, "priority_probe_questions": profile.priority_probe_questions,
    }, fields


def _form_version(asset_uid: str) -> str:
    """The deployed form's version id. The OpenRosa route rejects a submission whose version is not the live one."""
    explicit = (getattr(settings, "KOBO_PROIT_FORM_VERSION", "") or "").strip()
    if explicit:
        return explicit
    r = requests.get(
        f"{settings.KOBO_API_BASE_URL.rstrip('/')}/api/v2/assets/{asset_uid}/?format=json",
        headers={"Authorization": f"Token {settings.KOBO_API_TOKEN}"}, timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("deployment__active") and body.get("version_id") or body.get("version_id") or ""


def build_xml(profile: PreProfile, *, instance_uuid: str, submitted_by, version: str) -> str:
    values, facts = profile_values(profile)
    uid = settings.KOBO_PROIT_ASSET_UID
    root = ET.Element(uid, attrib={"id": uid, "version": version})
    now = timezone.now()
    _text(root, "start", now.isoformat())
    _text(root, "end", now.isoformat())
    _text(root, "today", now.date().isoformat())
    _text(root, "username", getattr(submitted_by, "username", "") or "portal")
    group = ET.SubElement(root, F.GROUP_NAME)
    for name, _t, _l, _r in F.PROFILE_FIELDS:
        _text(group, name, values.get(name, ""))
    for f in facts:
        item = ET.SubElement(root, F.REPEAT_NAME)
        row = {
            "fact_id": f.field_id, "fact_label": f.label, "fact_module": f.module,
            "documentary_value": f.preliminary_documentary_value, "confidence": f.confidence,
            "gap_classification": f.gap_classification, "sources": _sources(f),
            "verification_status": f.verification_status, "respondent_value": f.respondent_value,
            "verification_comment": f.verification_comment, "reconciled_value": f.reconciled_value,
        }
        for name, _t, _l, _r in F.REPEAT_FIELDS:
            _text(item, name, row.get(name, ""))
    meta = ET.SubElement(root, "meta")
    _text(meta, "instanceID", f"uuid:{instance_uuid}")
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")


def push_profile(profile_id: int, *, user=None, force: bool = False) -> str:
    """Returns 'sent', 'already_sent', 'not_configured' or 'not_ready'. Raises ProitKoboError on a failed send."""
    profile = PreProfile.objects.select_related("sample_case__organisation", "kii_record__organisation").get(pk=profile_id)
    if not is_configured():
        return "not_configured"
    if profile.kobo_submitted_at and not force:
        return "already_sent"
    if profile.reconciliation_status not in ("RECONCILED", "UNRESOLVED") or not profile.fields.exists():
        return "not_ready"
    instance_uuid = str(uuid.uuid4())
    try:
        xml = build_xml(profile, instance_uuid=instance_uuid, submitted_by=user, version=_form_version(settings.KOBO_PROIT_ASSET_UID))
        url = f"{settings.KOBO_OPENROSA_BASE_URL.rstrip('/')}/{settings.KOBO_ACCOUNT_USERNAME}/submission"
        response = requests.post(
            url, headers={"Authorization": f"Token {settings.KOBO_API_TOKEN}"},
            files={"xml_submission_file": ("submission.xml", xml, "text/xml")}, timeout=60,
        )
    except requests.RequestException as exc:
        raise ProitKoboError(f"KoboToolbox couldn't be reached: {exc.__class__.__name__}.") from exc
    if response.status_code not in (201, 202):
        raise ProitKoboError(f"KoboToolbox rejected the profile (HTTP {response.status_code}): {response.text[:300]}")
    profile.kobo_submission_uuid = instance_uuid
    profile.kobo_submitted_at = timezone.now()
    profile.save(update_fields=["kobo_submission_uuid", "kobo_submitted_at"])
    log_action("proit.kobo_submission_created", profile, {"instance_uuid": instance_uuid, "user_id": getattr(user, "id", None)})
    return "sent"
