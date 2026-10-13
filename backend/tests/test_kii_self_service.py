"""A KII informant using their own link is recorded end to end (PI request, 2026-10-13). Under test:

- status follows the informant: invited -> INVITED, declined online -> DECLINED, KII Guide received -> COMPLETED
  (from PROSPECT too), never backwards; a KII Guide without participation consent is never counted;
- the informant checks their own locked facts after consent: only their own record, never before consent, never a
  low-confidence value (those come as open questions), nothing at all when there is nothing to check;
- coding completes by itself when every fact is confirmed; a correction keeps it open, puts the record on the
  "needs reconciling" list, and the researcher's reconciled value completes it.
"""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.kii.models import CodingStatus, KIIRecord
from apps.kii.services import create_kii_record, issue_kii_invitation
from apps.kobo.form_sync import _complete_kii_coding
from apps.proit.models import PreProfileField
from apps.proit.services import add_evidence, add_field, create_pre_profile, lock_pre_profile

PROFILE = "/api/v1/proit/kii-respondent-profile/"
VERIFY = "/api/v1/proit/kii-respondent-verify/"
QUEUE = "/api/v1/proit/reconciliation-queue/"


@pytest.fixture(autouse=True)
def proit_on(settings):
    settings.PROIT_ENABLED_FOR_RESPONDENTS = True


def _record(**fields):
    fields.setdefault("status", "PROSPECT")
    return create_kii_record(participant_name="Tendai Moyo", participant_role="Head of Agribusiness",
                             stakeholder_category="Bank, DFI & MFI", metadata={"organisation_name": "CBZ Bank"}, **fields)


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _profile(record, *, low=False):
    profile = create_pre_profile(kii_record=record)
    year = add_field(profile, "year_established", documentary_value="1980")
    add_evidence(year, source_title="Annual report", source_confidence="HIGH", source_authority="TIER_1_STATUTORY")
    if low:
        staff = add_field(profile, "key_products", documentary_value="about 300")
        add_evidence(staff, source_title="Old news item", source_confidence="LOW")
        PreProfileField.objects.filter(pk=staff.pk).update(confidence="LOW")
    lock_pre_profile(profile, reviewer=_user(Role.PI_ADMIN, f"lock_{record.pk}"))
    return profile


def _consent(raw, decision="GIVEN"):
    return APIClient().post("/api/v1/kii-consent/", {"token": raw, "decision": decision, "information_sheet_version": "1"},
                            format="json")


def _submitted(record):
    _complete_kii_coding([{"part_a/KII_ID": record.kii_id, "_id": record.pk}])
    record.refresh_from_db()
    return record


# --- Status follows the informant ------------------------------------------------------------------------------------

def test_issuing_the_link_makes_a_prospect_invited(db):
    record = _record()
    issue_kii_invitation(record)
    record.refresh_from_db()
    assert record.status == "INVITED"
    assert AuditEvent.objects.filter(action="kii.status_changed", metadata__automatic=True).exists()


def test_declining_online_marks_the_record_declined_and_nothing_moves_it_again(db):
    record = _record()
    raw, _, _ = issue_kii_invitation(record)
    assert _consent(raw, "DECLINED").status_code == 200
    record.refresh_from_db()
    assert record.status == "DECLINED"
    assert _submitted(record).status == "DECLINED"


def test_an_informant_who_changed_their_mind_and_sent_the_kii_guide_is_completed(db):
    record = _record()
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw, "DECLINED")
    _consent(raw, "GIVEN")
    assert _submitted(record).status == "COMPLETED"
    _consent(raw, "DECLINED")  # clicked again afterwards: a completed interview stays completed
    record.refresh_from_db()
    assert record.status == "COMPLETED"


def test_a_kii_guide_after_consent_completes_the_interview(db):
    record = _record()
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    assert _submitted(record).status == "COMPLETED"
    assert record.coding_status == CodingStatus.COMPLETE  # no locked facts to settle


def test_a_kii_guide_without_consent_is_never_counted(db):
    record = _record(status="INVITED")
    assert _submitted(record).status == "INVITED" and record.coding_status == CodingStatus.NOT_STARTED
    assert AuditEvent.objects.filter(action="kii.submission_without_consent").exists()


# --- The informant checks their own facts ---------------------------------------------------------------------------

def test_facts_are_shown_only_after_consent_and_only_for_their_own_record(db):
    record, other = _record(), _record()
    _profile(record)
    other_field = _profile(other).fields.get()
    raw, _, _ = issue_kii_invitation(record)
    assert APIClient().get(PROFILE, {"t": raw}).status_code == 403  # before consent
    _consent(raw)
    body = APIClient().get(PROFILE, {"t": raw}).json()
    assert [f["preliminary_documentary_value"] for f in body["fields"]] == ["1980"]
    resp = APIClient().post(VERIFY, {"token": raw, "field_id": other_field.pk, "status": "YES_CORRECT"}, format="json")
    assert resp.status_code == 404  # another informant's fact


def test_a_low_confidence_fact_is_asked_as_an_open_question_never_shown(db):
    record = _record()
    profile = _profile(record, low=True)
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    body = APIClient().get(PROFILE, {"t": raw}).json()
    assert "about 300" not in str(body)
    question = body["questions"][0]
    assert question["field_id"] == "key_products"
    resp = APIClient().post(VERIFY, {"token": raw, "field_id": question["id"], "status": "YES_CORRECT"}, format="json")
    assert resp.status_code == 400  # nothing was shown to confirm
    ok = APIClient().post(VERIFY, {"token": raw, "field_id": question["id"], "status": "NO_CORRECT_VALUE_PROVIDED",
                                   "respondent_value": "420"}, format="json")
    assert ok.status_code == 200
    assert profile.fields.get(field_id="key_products").respondent_value == "420"


@override_settings(PROIT_ENABLED_FOR_RESPONDENTS=True)
def test_nothing_to_check_means_the_step_skips_itself(db):
    record = _record()
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    resp = APIClient().get(PROFILE, {"t": raw})
    assert resp.status_code == 200 and resp.content in (b"", b"null")  # null: the page goes straight on


# --- Coding completes by itself, or waits visibly for a researcher ---------------------------------------------------

def test_confirmations_alone_complete_coding_with_no_one_involved(db):
    record = _record()
    field = _profile(record).fields.get()
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    APIClient().post(VERIFY, {"token": raw, "field_id": field.pk, "status": "YES_CORRECT"}, format="json")
    assert _submitted(record).coding_status == CodingStatus.COMPLETE


def test_a_correction_waits_on_the_list_and_the_reconciled_value_completes_it(db):
    record = _record()
    field = _profile(record).fields.get()
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    APIClient().post(VERIFY, {"token": raw, "field_id": field.pk, "status": "NO_CORRECT_VALUE_PROVIDED",
                              "respondent_value": "1982"}, format="json")
    assert _submitted(record).status == "COMPLETED" and record.coding_status != CodingStatus.COMPLETE
    fc = APIClient()
    fc.force_authenticate(_user(Role.FIELD_COORDINATOR, "q_fc"))
    rows = fc.get(QUEUE).json()["results"]
    assert [(r["kii_id"], r["to_reconcile"]) for r in rows] == [(record.kii_id, 1)]
    fc.post(f"/api/v1/proit/fields/{field.pk}/reconcile/", {"reconciled_value": "1982"}, format="json")
    record.refresh_from_db()
    assert record.coding_status == CodingStatus.COMPLETE
    assert fc.get(QUEUE).json()["results"] == []


def test_a_skipped_check_is_listed_as_not_verified(db):
    record = _record()
    _profile(record)
    raw, _, _ = issue_kii_invitation(record)
    _consent(raw)
    _submitted(record)
    fc = APIClient()
    fc.force_authenticate(_user(Role.PI_ADMIN, "q_pi"))
    assert fc.get(QUEUE).json()["results"][0]["not_verified"] == 1


def test_the_queue_is_refused_to_roles_without_interview_work(db):
    for role in (Role.ANALYST, Role.DOCUMENTARY_RA, Role.QUAN_QA_RA):
        client = APIClient()
        client.force_authenticate(_user(role, f"q_{role.lower()}"))
        assert client.get(QUEUE).status_code == 403
    assert KIIRecord.objects.count() == 0
