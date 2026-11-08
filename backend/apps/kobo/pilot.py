"""The Zimbabwe Agricultural Show pilot (ZAS 2026) as its own strand beside the main study (PI decision, 8 Nov 2026).

The pilot (25-31 August 2026) used its own KoboToolbox forms -- a questionnaire, two KII guides and a document
analysis tool -- with different questions from the main-study forms, and recruited respondents at the Show rather
than from the Main-400 frame. The PI chose to bring it into the portal as a separate, labelled strand rather than
merge it into the main records: every pilot submission becomes a PilotRecord, the dashboards show main + pilot with
the split, and nothing about the Main-400 sample, its records or its exports changes. Pooling the answers with the
main study's (a crosswalk, or construct-level averages) stays an analysis decision, made outside the database.

sync() copies every submission of the forms in settings.KOBO_PILOT_FORMS. It is safe to run again: a record is
updated in place, and the PI's include/exclude decision on it is kept. A respondent who declined consent is never
counted. Questionnaire records whose interview ID is non-standard or shared are flagged for the PI to decide.
"""

import re
from collections import Counter
from datetime import timezone as dt_timezone

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.audit.utils import log_action

from .models import PilotRecord, PilotStrand

# What each form's reference, date and consent questions are called, and the non-identifying answers the list shows.
SPEC = {
    "quan": {"ref": "ADM01", "date": "ADM02", "consent": "CONSENT01",
             "summary": [("RA", "ADM03"), ("Where", "ADM04"), ("Organisation type", "PROF01"), ("Province", "PROF06"),
                         ("Value chain", "PROF04")]},
    "kii_show": {"ref": "kii_code", "date": "interview_date", "consent": "consent",
                 "summary": [("Institution category", "institution_category"), ("Interview type", "interview_type")]},
    "kii_exec": {"ref": "interview_id", "date": "interview_date", "consent": "consent",
                 "summary": [("Respondent category", "respondent_category"), ("Audio recording", "recording_consent")]},
    "docs": {"ref": "DOC01", "date": "DOC10", "consent": None,
             "summary": [("Title", "DOC02"), ("Issued by", "DOC03"), ("Type", "DOC06"), ("Year", "DOC05")]},
}
FORM_TITLE = {"quan": "Pilot questionnaire", "kii_show": "Show KII (full guide)", "kii_exec": "Executive KII (15 minutes)",
              "docs": "Pilot document analysis"}
STANDARD_QUAN_ID = re.compile(r"^ZAS26-\d{3}$", re.IGNORECASE)
DECLINED = "Declined consent: no answers were collected."
GONE = "No longer in KoboToolbox (deleted there)."


class PilotError(Exception):
    pass


def forms() -> list[tuple[str, str, str]]:
    """[(form_key, strand, asset_uid)] from settings.KOBO_PILOT_FORMS ("key:STRAND:uid")."""
    out = []
    for entry in settings.KOBO_PILOT_FORMS:
        key, strand, uid = (entry.split(":") + ["", "", ""])[:3]
        if key in SPEC and strand in PilotStrand.values and uid:
            out.append((key, strand, uid))
    return out


def _field(payload: dict, name: str):
    """An answer by question name, wherever its group puts it ("admin_consent/ADM01")."""
    for key, value in payload.items():
        if key.split("/")[-1] == name:
            return value
    return None


def _choice_labels(content: dict) -> dict:
    """{question name: {answer code: label}} from a form's definition."""
    def label(row):
        lab = row.get("label")
        return next((x for x in lab if x), "") if isinstance(lab, list) else lab or ""

    lists = {}
    for choice in content.get("choices", []):
        lists.setdefault(choice.get("list_name"), {})[str(choice.get("name"))] = label(choice)
    return {row.get("name"): lists.get(row.get("select_from_list_name"), {}) for row in content.get("survey", [])
            if row.get("select_from_list_name")}


def _shown(value, labels: dict) -> str:
    if value in (None, ""):
        return ""
    return " / ".join(labels.get(part, part) for part in str(value).split())[:200] if labels else str(value)[:200]


def _get(url: str, get):
    response = get(url, headers={"Authorization": f"Token {settings.KOBO_API_TOKEN}"}, timeout=120)
    if response.status_code != 200:
        raise PilotError(f"KoboToolbox answered {response.status_code} for {url.split('?')[0]}.")
    return response.json()


def _submitted_at(row: dict):
    """Kobo's _submission_time is UTC without a zone."""
    when = parse_datetime(row.get("_submission_time") or "")
    if when is not None and timezone.is_naive(when):
        when = timezone.make_aware(when, dt_timezone.utc)
    return when


def _consent(payload: dict, spec: dict):
    if not spec["consent"]:
        return None
    answer = str(_field(payload, spec["consent"]) or "").strip().lower()
    return True if answer == "yes" else False if answer == "no" else None


def sync(*, user=None, get=None) -> dict:
    """Copy every pilot submission into PilotRecord. Returns {form_key: {"added", "updated", "gone"}}."""
    if not settings.KOBO_API_TOKEN:
        raise PilotError("KoboToolbox isn't connected on the server (KOBO_API_TOKEN).")
    get = get or requests.get
    base = settings.KOBO_API_BASE_URL.rstrip("/")
    now = timezone.now()
    stats = {}
    for key, strand, uid in forms():
        spec = SPEC[key]
        content = _get(f"{base}/api/v2/assets/{uid}/?format=json", get).get("content", {})
        labels = _choice_labels(content)
        rows = _get(f"{base}/api/v2/assets/{uid}/data/?format=json&limit=10000", get).get("results", [])
        refs = Counter(str(_field(r, spec["ref"]) or "").strip().upper() for r in rows)
        added = updated = 0
        seen = set()
        with transaction.atomic():
            for row in rows:
                kobo_id = int(row["_id"])
                seen.add(kobo_id)
                ref = str(_field(row, spec["ref"]) or "").strip()
                consented = _consent(row, spec)
                flags = []
                if key == "quan":
                    if not ref:
                        flags.append("No interview ID written")
                    elif not STANDARD_QUAN_ID.match(ref):
                        flags.append("Non-standard interview ID (RA practice, or a real respondent?)")
                    if ref and refs[ref.upper()] > 1:
                        flags.append(f"Interview ID shared by {refs[ref.upper()]} submissions")
                summary = {name: _shown(_field(row, q), labels.get(q, {})) for name, q in spec["summary"]}
                values = {
                    "strand": strand, "form_key": key, "reference": ref[:120],
                    "collected_on": parse_date(str(_field(row, spec["date"]) or "")[:10]) if _field(row, spec["date"]) else None,
                    "submitted_at": _submitted_at(row),
                    "consented": consented, "summary": {k: v for k, v in summary.items() if v}, "flags": flags,
                    "payload": {k: v for k, v in row.items() if not k.startswith("_attachments")}, "last_synced_at": now,
                }
                record = PilotRecord.objects.filter(asset_uid=uid, kobo_id=kobo_id).first()
                if record is None:
                    record = PilotRecord(asset_uid=uid, kobo_id=kobo_id, **values)
                    record.included = consented is not False
                    record.exclusion_reason = "" if record.included else DECLINED
                    record.save()
                    added += 1
                    log_action("pilot.record_added", record, {"form": key, "kobo_id": kobo_id, "included": record.included,
                                                             "flags": flags}, user=user)
                else:
                    for field, value in values.items():
                        setattr(record, field, value)
                    if consented is False:  # never counted, whatever was decided before
                        record.included, record.exclusion_reason = False, DECLINED
                    elif record.decided_by_id is None:
                        record.included, record.exclusion_reason = True, ""
                    record.save()
                    updated += 1
            gone = 0
            for record in PilotRecord.objects.filter(asset_uid=uid).exclude(kobo_id__in=seen).exclude(exclusion_reason=GONE):
                record.included, record.exclusion_reason = False, GONE
                record.save(update_fields=["included", "exclusion_reason"])
                log_action("pilot.record_removed", record, {"form": key, "kobo_id": record.kobo_id}, user=user)
                gone += 1
        stats[key] = {"added": added, "updated": updated, "gone": gone}
    return stats


def counts() -> dict:
    """Included pilot records per strand: what the dashboards add beside the main study's figures."""
    found = Counter(PilotRecord.objects.filter(included=True).values_list("strand", flat=True))
    return {"quan": found.get(PilotStrand.QUAN, 0), "kii": found.get(PilotStrand.KII, 0),
            "documents": found.get(PilotStrand.DOCUMENT, 0)}


def decide(user, pk: int, *, included: bool, reason: str = "") -> PilotRecord:
    """The PI includes or excludes one pilot record, with a reason for an exclusion. Audited."""
    record = PilotRecord.objects.filter(pk=pk).first()
    if record is None:
        raise PilotError("That pilot record was not found.")
    reason = (reason or "").strip()[:300]
    if included and record.consented is False:
        raise PilotError("This person declined consent, so their record can't be counted.")
    if not included and not reason:
        raise PilotError("Write why this record is left out.")
    before = record.included
    record.included, record.exclusion_reason = included, "" if included else reason
    record.decided_by, record.decided_at = user, timezone.now()
    record.save(update_fields=["included", "exclusion_reason", "decided_by", "decided_at"])
    log_action("pilot.decision", record, {"form": record.form_key, "kobo_id": record.kobo_id, "reference": record.reference,
                                          "included_before": before, "included": included, "reason": reason}, user=user)
    return record


def listing(strand: str = "", show: str = "") -> dict:
    """What the ZAS 2026 pilot screen shows: totals per strand and form, and the records (no answers)."""
    records = PilotRecord.objects.select_related("decided_by")
    by_form = Counter((r.form_key, r.included) for r in records)
    totals = []
    for key, strand_key, _ in forms():
        totals.append({"form": key, "title": FORM_TITLE[key], "strand": strand_key,
                       "included": by_form.get((key, True), 0), "excluded": by_form.get((key, False), 0)})
    if strand in PilotStrand.values:
        records = records.filter(strand=strand)
    if show == "flagged":
        records = records.exclude(flags=[])
    elif show == "excluded":
        records = records.filter(included=False)
    return {
        "counts": counts(), "totals": totals,
        "results": [{
            "id": r.pk, "strand": r.strand, "form": r.form_key, "form_title": FORM_TITLE.get(r.form_key, r.form_key),
            "kobo_id": r.kobo_id, "reference": r.reference, "collected_on": r.collected_on, "consented": r.consented,
            "summary": r.summary, "flags": r.flags, "included": r.included, "exclusion_reason": r.exclusion_reason,
            "decided_by": r.decided_by.username if r.decided_by_id else "", "decided_at": r.decided_at,
        } for r in records],
        "last_synced_at": PilotRecord.objects.order_by("-last_synced_at").values_list("last_synced_at", flat=True).first(),
    }
