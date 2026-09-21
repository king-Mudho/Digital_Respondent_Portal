"""
KII scheduling, consent gating and status-flow transitions
(docs/13_KII_MODULE.md). Status flow: PROSPECT (identified in the sampling
frame, not yet approached) -> INVITED -> SCHEDULED -> COMPLETED (or
DECLINED/NO_SHOW), independent of transcript_status and coding_status,
which progress after the interview itself is complete.
"""

from urllib.parse import quote

from django.conf import settings

from apps.audit.utils import log_action
from apps.consent.models import ConsentType
from apps.consent.services import has_given_consent
from apps.sampling.services import next_sequence

from .models import CodingStatus, KIIRecord, KIIStatus, TranscriptStatus


def generate_kii_id() -> str:
    """KII-<sequence(4)>, e.g. KII-0042. System-generated, never user-entered,
    same DB-sequence approach as Master_ID/Sample_ID (docs/09_IDENTIFIER_
    AND_SAMPLING_CONTROL.md)."""
    seq = next_sequence("KII_ID")
    return f"KII-{seq:04d}"


def create_kii_record(**fields) -> KIIRecord:
    record = KIIRecord(kii_id=generate_kii_id(), **fields)
    record.full_clean()
    record.save()
    return record


KII_STATUS_TRANSITIONS = {
    KIIStatus.PROSPECT: {KIIStatus.INVITED, KIIStatus.DECLINED},
    KIIStatus.INVITED: {KIIStatus.SCHEDULED, KIIStatus.DECLINED},
    KIIStatus.SCHEDULED: {KIIStatus.COMPLETED, KIIStatus.NO_SHOW, KIIStatus.DECLINED},
    KIIStatus.COMPLETED: set(),
    KIIStatus.DECLINED: set(),
    KIIStatus.NO_SHOW: {KIIStatus.SCHEDULED},  # can be rescheduled
}


class InvalidKIITransition(Exception):
    pass


class KIIRecordingConsentRequired(Exception):
    pass


def transition_kii_status(record: KIIRecord, new_status: str) -> KIIRecord:
    allowed = KII_STATUS_TRANSITIONS.get(record.status, set())
    if new_status not in allowed:
        raise InvalidKIITransition(f"Cannot transition {record.status} -> {new_status}.")
    record.status = new_status
    record.save(update_fields=["status"])
    log_action("kii.status_changed", record, {"new_status": new_status})
    return record


def mark_completed(record: KIIRecord, *, with_recording: bool) -> KIIRecord:
    """Recording consent is always a separate, explicit decision from
    participation consent (AGENTS.md ground rule 6) -- a KII cannot be
    marked completed with a recording unless that separate consent was
    given."""
    if with_recording and not has_given_consent(record, ConsentType.KII_RECORDING):
        raise KIIRecordingConsentRequired("Recording consent was not given for this KII.")

    return transition_kii_status(record, KIIStatus.COMPLETED)


def advance_transcript_status(record: KIIRecord, new_status: str) -> KIIRecord:
    order = [TranscriptStatus.NOT_STARTED, TranscriptStatus.IN_PROGRESS, TranscriptStatus.VERIFIED, TranscriptStatus.ANONYMISED]
    if order.index(new_status) < order.index(record.transcript_status):
        raise InvalidKIITransition("Transcript status cannot move backwards.")
    record.transcript_status = new_status
    record.save(update_fields=["transcript_status"])
    return record


def advance_coding_status(record: KIIRecord, new_status: str) -> KIIRecord:
    order = [CodingStatus.NOT_STARTED, CodingStatus.IN_PROGRESS, CodingStatus.COMPLETE]
    if order.index(new_status) < order.index(record.coding_status):
        raise InvalidKIITransition("Coding status cannot move backwards.")
    if new_status == CodingStatus.COMPLETE and record.coding_status != CodingStatus.COMPLETE:
        # Coding is complete only once the pre-interview profile (if the interview had one) is reconciled.
        from apps.proit.services import reconciliation_blocker

        blocker = reconciliation_blocker(kii_record=record)
        if blocker:
            raise InvalidKIITransition(blocker)
    record.coding_status = new_status
    record.save(update_fields=["coding_status"])
    return record


# --- KoboToolbox KII Guide: prefilled interview link ------------------------

def kii_form_is_configured() -> bool:
    return bool((settings.KOBO_KII_FORM_URL or "").strip())


def build_kii_coding_url(record: KIIRecord) -> str | None:
    """Prefills the KoboToolbox Main Study KII Guide with this record's
    KII-ID, so a KII RA doesn't retype it and a typo can't make the
    completed interview fail to match back up with this record
    (docs/13_KII_MODULE.md), the same ?d[<data column>]=value mechanism as
    the other two forms (apps/kobo/services.py, apps/evidence/services.py).

    Deliberately narrower than the document coding link: a KIIRecord
    identifies a real person, so nothing participant-identifying
    (participant_name, organisation, role) goes into the URL -- only the
    system-generated ID and the interviewer's own username, mirroring
    apps/kobo/services.py build_redirect_url()'s minimal-identifiers
    pattern for the respondent questionnaire link. And unlike a document,
    the link is withheld entirely until participation consent is GIVEN --
    there is no legitimate reason to open the interview instrument on
    someone before they have consented to take part.

    Returns None when KOBO_KII_FORM_URL isn't set, or when participation
    consent hasn't been given yet.
    """
    if not kii_form_is_configured():
        return None
    if not has_given_consent(record, ConsentType.PARTICIPATION):
        return None
    form_url = settings.KOBO_KII_FORM_URL.strip().rstrip("/")
    fields = {"part_a/KII_ID": record.kii_id}
    if record.interviewer_id and record.interviewer.username:
        fields["part_a/interviewer_code"] = record.interviewer.username
    if record.interview_date:
        fields["part_a/interview_date"] = record.interview_date.isoformat()
    query = "&".join(f"d[{key}]={quote(str(value), safe='')}" for key, value in fields.items() if value)
    separator = "&" if "?" in form_url else "?"
    return f"{form_url}{separator}{query}"
