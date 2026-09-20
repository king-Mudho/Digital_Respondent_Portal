"""
Sync of all three main-study KoboToolbox forms into the portal.

`reconcile()` (services.py) turns Questionnaire submissions into the QA
workflow. This module is the broader promise: for the Questionnaire, the KII
Guide and the Document Analysis Tool alike, the portal ends up holding the
same submissions, with the same answers, that KoboToolbox holds -- and can
prove it (a content hash per submission; a count comparison per form).

After each pull it also acts on what it found:
  - KII Guide: a completed guide for a KII ID marks that interview's coding
    COMPLETE (never backwards, and never by guessing -- only an exact ID match);
  - Document Analysis Tool: a portal-submitted coding that has since been
    deleted in KoboToolbox unlocks the document again, so the coding can be
    redone -- otherwise the review screen would say "already submitted" about
    a record that no longer exists.

Edited submissions are recognised by a changed content hash, exactly as in
reconcile(); a submission deleted in Kobo is flagged, not silently kept.
"""

import logging

import requests
from django.utils import timezone

from apps.audit.utils import log_action

from . import submission_copies as copies
from .client import KoboClient
from .models import FormSyncLog, KoboFormSubmission, ReconciliationTrigger
from .services import KoboNotConfigured, _content_hash, _parse_kobo_datetime, _submission_identity

logger = logging.getLogger(__name__)


def form_is_configured(key: str) -> bool:
    from django.conf import settings

    return bool(copies.asset_uid(key)) and bool((settings.KOBO_API_TOKEN or "").strip())


def payload_hash(payload: dict) -> str:
    return _content_hash(payload)


def sync_form(key: str, triggered_by: str = ReconciliationTrigger.MANUAL) -> FormSyncLog:
    """Pulls every submission of one form and makes the portal's copy match.
    Raises KoboNotConfigured (writing nothing) when the form isn't connected."""
    if key not in copies.FORMS:
        raise KeyError(key)
    if not form_is_configured(key):
        raise KoboNotConfigured(f"{copies.FORMS[key]['title']} isn't connected to KoboToolbox yet.")

    started = timezone.now()
    try:
        payloads = KoboClient(asset_uid=copies.asset_uid(key)).fetch_submissions()
    except requests.exceptions.RequestException as exc:
        logger.warning("Kobo form sync (%s) failed: %s", key, exc)
        return FormSyncLog.objects.create(
            form_key=key, run_started_at=started, run_finished_at=timezone.now(),
            triggered_by=triggered_by, error_message=f"{exc.__class__.__name__}: {exc}"[:500],
        )

    existing = {row.kobo_id: row for row in KoboFormSubmission.objects.filter(form_key=key)}
    new = updated = 0
    seen: set[int] = set()
    for payload in payloads:
        kobo_id = payload.get("_id")
        if kobo_id is None:
            continue
        seen.add(kobo_id)
        digest = payload_hash(payload)
        fields = {
            "kobo_uuid": _submission_identity(payload) or "",
            "record": copies.record_label(key, payload)[:120],
            "submitted_at": _parse_kobo_datetime(payload.get("_submission_time")),
            "submitted_by": (payload.get("_submitted_by") or "")[:150],
            "payload": payload,
            "payload_hash": digest,
            "last_synced_at": started,
            "removed_at": None,
        }
        row = existing.get(kobo_id)
        if row is None:
            KoboFormSubmission.objects.create(form_key=key, kobo_id=kobo_id, **fields)
            new += 1
        elif row.payload_hash != digest:
            for name, value in fields.items():
                setattr(row, name, value)
            row.last_changed_at = started
            row.save()
            updated += 1
        else:
            # Unchanged: only the sync stamp moves (and a reappearing row is un-removed).
            KoboFormSubmission.objects.filter(pk=row.pk).update(last_synced_at=started, removed_at=None)

    gone = KoboFormSubmission.objects.filter(form_key=key, removed_at__isnull=True).exclude(kobo_id__in=seen)
    removed = gone.update(removed_at=started)

    _link_records(key, payloads)

    return FormSyncLog.objects.create(
        form_key=key, run_started_at=started, run_finished_at=timezone.now(), pulled=len(payloads),
        new=new, updated=updated, removed=removed, triggered_by=triggered_by,
    )


def sync_all(triggered_by: str = ReconciliationTrigger.MANUAL, keys=None) -> list[FormSyncLog]:
    """Every connected form (or just `keys`). An unconnected form is skipped,
    not an error; one form failing never stops the others."""
    logs = []
    for key in keys or copies.FORMS:
        if not form_is_configured(key):
            continue
        try:
            logs.append(sync_form(key, triggered_by))
        except Exception:  # noqa: BLE001 -- one form's bug must not block the other two
            logger.exception("Kobo form sync (%s) crashed", key)
    return logs


# --- What a sync does with what it found -------------------------------------

class _Ref:
    def __init__(self, pk):
        self.pk = pk


def _link_records(key: str, payloads: list[dict]) -> None:
    if key == "kii":
        _complete_kii_coding(payloads)
    elif key == "documents":
        _unlock_deleted_document_codings(payloads)


def _complete_kii_coding(payloads: list[dict]) -> None:
    from apps.kii.models import CodingStatus, KIIRecord
    from apps.kii.services import InvalidKIITransition, advance_coding_status

    ids = {copies.record_label("kii", p) for p in payloads}
    for record in KIIRecord.objects.filter(kii_id__in=ids).exclude(coding_status=CodingStatus.COMPLETE):
        try:
            advance_coding_status(record, CodingStatus.COMPLETE)
        except InvalidKIITransition:
            continue
        log_action("kii.coding_completed_from_kobo", record, {"kii_id": record.kii_id})


def _unlock_deleted_document_codings(payloads: list[dict]) -> None:
    from apps.evidence.models import DocumentRecord

    identities = set()
    for payload in payloads:
        for value in (payload.get("meta/rootUuid"), payload.get("_uuid"), payload.get("meta/instanceID")):
            if value:
                identities.add(str(value).removeprefix("uuid:"))
    for document in DocumentRecord.objects.exclude(kobo_submission_uuid=""):
        if document.kobo_submission_uuid in identities:
            continue
        log_action("document.kobo_submission_removed_in_kobo", document, {"instance_uuid": document.kobo_submission_uuid})
        document.kobo_submission_uuid = ""
        document.kobo_submitted_at = None
        document.kobo_submitted_by = None
        document.save(update_fields=["kobo_submission_uuid", "kobo_submitted_at", "kobo_submitted_by"])


# --- Status / parity ----------------------------------------------------------

def _serialize_log(log: FormSyncLog | None):
    if log is None:
        return None
    return {
        "started_at": log.run_started_at, "finished_at": log.run_finished_at, "pulled": log.pulled,
        "new": log.new, "updated": log.updated, "removed": log.removed, "triggered_by": log.triggered_by,
        "error_message": log.error_message,
    }


def form_status(key: str) -> dict:
    """One form's sync state: how many submissions KoboToolbox has (asked
    live), how many the portal holds, and whether those agree."""
    spec = copies.FORMS[key]
    status = {
        "key": key, "title": spec["title"], "configured": form_is_configured(key),
        "kobo_count": None, "portal_count": 0, "removed_count": 0, "in_sync": False,
        "kobo_error": "", "last_sync": None, "last_success": None,
    }
    active = KoboFormSubmission.objects.filter(form_key=key, removed_at__isnull=True)
    status["portal_count"] = active.count()
    status["removed_count"] = KoboFormSubmission.objects.filter(form_key=key, removed_at__isnull=False).count()
    logs = FormSyncLog.objects.filter(form_key=key)
    last = logs.first()
    status["last_sync"] = _serialize_log(last)
    status["last_success"] = _serialize_log(logs.filter(error_message="").first())
    if status["configured"]:
        try:
            status["kobo_count"] = copies._kobo_get(
                f"/api/v2/assets/{copies.asset_uid(key)}/data/", limit=1, fields='["_id"]'
            ).get("count", 0)
        except copies.CopyError as exc:
            status["kobo_error"] = str(exc)
    status["in_sync"] = (
        status["configured"] and status["kobo_count"] is not None
        and status["kobo_count"] == status["portal_count"] and last is not None and not last.error_message
    )
    return status


def portal_copy_flags(key: str, rows: list[dict]) -> dict[int, bool]:
    """{kobo id: portal holds an identical copy} for the rows a list page shows."""
    ids = [row.get("_id") for row in rows if row.get("_id") is not None]
    stored = dict(
        KoboFormSubmission.objects.filter(form_key=key, kobo_id__in=ids, removed_at__isnull=True)
        .values_list("kobo_id", "payload_hash")
    )
    return {row["_id"]: stored.get(row["_id"]) == payload_hash(row) for row in rows if row.get("_id") is not None}
