"""The Calls screen (apps/contacts/calls.py, PI 25 Oct 2026): everyone whose link was sent but who has not finished,
with every contact on file, for a person to phone. Under test:

- who is listed: a live link that started, consented, opened or was only sent -- closest to finishing first; never a
  submitted or QA-passed case, a case marked as a duplicate, or a KII record not invited;
- every contact shown: each person's numbers (several in one field split apart) with a WhatsApp link, and email;
- filters: study, stage (counts per stage for the chips) and search by name, ID or number;
- who sees what: a Contact RA only their assigned Main-400 cases and no KII; a KII RA only KII records; the QUAN QA
  RA, Documentary RA and Analyst are refused; the Supervisor reads but cannot log a call;
- a logged call is a PHONE contact event on the case or KII record, audited, and shows as the last call.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import ContactEvent, Respondent, RoleCategory
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation
from apps.kii.models import KIIInvitationToken
from apps.kii.services import create_kii_record, issue_kii_invitation
from apps.sampling.services import create_organisation, create_sample_case, transition_workflow_status

pytestmark = pytest.mark.django_db
URL = "/api/v1/calls/"


def _client(role, username):
    r, _ = Role.objects.get_or_create(name=role)
    user = User.objects.create_user(username=username, password="x", role=r)
    c = APIClient()
    c.force_authenticate(user)
    c.user = user
    return c


def _invited(case, status=TokenStatus.SENT, *, phone="0771234567; +263 77 765 4321", name="Jane Doe"):
    for s in ("S01", "S02", "S03"):
        transition_workflow_status(case, s)
    Respondent.objects.create(sample_case=case, full_name=name, role_category=RoleCategory.CEO_MD, is_eligible=True,
                              phone=phone, email="jane@farmco.co.zw")
    _, _, token = issue_invitation(case, channel="WHATSAPP", issued_by=None)
    InvitationToken.objects.filter(pk=token.pk).update(status=status)
    return case


def _another_case(organisation, stratum, name):
    org = create_organisation(province=organisation.province, name=name, entity_type="Private Limited Company",
                              district="Harare", actor_family=organisation.actor_family, value_chain="Horticulture",
                              size_class=organisation.size_class)
    return create_sample_case(organisation=org, stratum=stratum, sample_type="MAIN", year=2026)


def _kii(status=None, name="Tendai Moyo"):
    r = create_kii_record(participant_name=name, participant_role="Director", stakeholder_category="Bank",
                          phone="0772000001", metadata={"organisation_name": "Agri Bank", "pool": "CORE_60"})
    _, _, token = issue_kii_invitation(r)
    if status:
        KIIInvitationToken.objects.filter(pk=token.pk).update(status=status)
    r.refresh_from_db()
    return r


@pytest.fixture
def pi():
    return _client(Role.PI_ADMIN, "calls_pi")


def test_people_who_have_not_finished_are_listed_closest_to_finishing_first(pi, main_case, organisation, stratum):
    _invited(main_case, TokenStatus.OPENED)
    started = _invited(_another_case(organisation, stratum, "Started Farm"), TokenStatus.SURVEY_STARTED)
    _invited(_another_case(organisation, stratum, "Sent Farm"), TokenStatus.SENT)
    done = _invited(_another_case(organisation, stratum, "Done Farm"), TokenStatus.SUBMITTED)
    # It also still holds an older link that was never opened: having submitted, it must not be called.
    old = InvitationToken.objects.get(sample_case=done)
    old.pk, old.token_hash, old.manual_code_hash, old.status = None, old.token_hash + "x", None, TokenStatus.SENT
    old.save()
    record = _kii("OPENED")
    data = pi.get(URL).json()
    ids = [r["id"] for r in data["results"]]
    assert ids[0] == started.sample_id and "Done Farm" not in [r["organisation"] for r in data["results"]]
    assert [r["stage"] for r in data["results"]] == ["started", "opened", "opened", "not_opened"]
    assert record.kii_id in ids and data["stage_counts"] == {"started": 1, "consented": 0, "opened": 2, "not_opened": 1}
    first = data["results"][0]
    assert first["stage_label"] == "Started, not finished" and first["detail_path"] == f"/admin/sample/{started.sample_id}"
    numbers = first["people"][0]["numbers"]
    assert [n["number"] for n in numbers] == ["0771234567", "+263 77 765 4321"]  # two numbers in one field, both shown
    assert numbers[0]["whatsapp_link"] == "https://wa.me/263771234567" and first["people"][0]["email"] == "jane@farmco.co.zw"


def test_filters_by_study_stage_and_search(pi, main_case, organisation, stratum):
    _invited(main_case, TokenStatus.CONSENTED)
    _invited(_another_case(organisation, stratum, "Other Farm"), TokenStatus.SENT, phone="0779998888", name="Peter Banda")
    _kii()
    assert {r["kind"] for r in pi.get(URL, {"study": "kii"}).json()["results"]} == {"kii"}
    assert [r["stage"] for r in pi.get(URL, {"study": "main", "stage": "consented"}).json()["results"]] == ["consented"]
    assert [r["organisation"] for r in pi.get(URL, {"q": "banda"}).json()["results"]] == ["Other Farm"]
    assert [r["organisation"] for r in pi.get(URL, {"q": "999 8888"}).json()["results"]] == ["Other Farm"]


def test_a_case_marked_as_a_duplicate_is_never_listed(pi, main_case):
    _invited(main_case, TokenStatus.OPENED)
    main_case.metadata = {"duplicate_of": {"of": "SID-2026-000999"}}
    main_case.save(update_fields=["metadata"])
    assert pi.get(URL).json()["results"] == []


def test_each_role_sees_only_its_own_people(main_case, organisation, stratum):
    mine = _invited(main_case, TokenStatus.OPENED)
    _invited(_another_case(organisation, stratum, "Someone Else's Farm"), TokenStatus.OPENED)
    _kii(None)
    ra = _client(Role.CONTACT_RA, "calls_ra")
    mine.assigned_ra = ra.user
    mine.save(update_fields=["assigned_ra"])
    data = ra.get(URL).json()
    assert [r["id"] for r in data["results"]] == [mine.sample_id] and data["studies"] == ["main"]
    kii = _client(Role.KII_RA, "calls_kii").get(URL).json()
    assert {r["kind"] for r in kii["results"]} == {"kii"} and kii["studies"] == ["kii"]
    for role in (Role.QUAN_QA_RA, Role.DOCUMENTARY_RA, Role.ANALYST):
        assert _client(role, f"calls_{role.lower()}").get(URL).status_code == 403


def test_a_logged_call_is_a_phone_contact_event_shown_as_the_last_call(pi, main_case):
    _invited(main_case, TokenStatus.OPENED)
    resp = pi.post(f"{URL}main/{main_case.sample_id}/", {"outcome": "RESCHEDULED", "notes": "Call back after 2pm",
                                                         "next_action_date": "2026-10-27"}, format="json")
    assert resp.status_code == 201
    event = ContactEvent.objects.get()
    assert (event.sample_case_id, event.channel, event.outcome, event.ra_id) == (main_case.pk, "PHONE", "RESCHEDULED", pi.user.id)
    assert AuditEvent.objects.filter(action="contacts.call_logged").exists()
    row = pi.get(URL).json()["results"][0]
    assert row["calls"] == 1 and row["last_call"]["outcome_label"] == "Rescheduled"
    assert row["last_call"]["notes"] == "Call back after 2pm" and row["last_call"]["next_action_date"] == "2026-10-27"


def test_a_kii_call_is_logged_on_the_kii_record(pi):
    r = _kii()
    assert pi.post(f"{URL}kii/{r.kii_id}/", {"outcome": "REACHED"}, format="json").status_code == 201
    assert ContactEvent.objects.get().kii_record_id == r.pk


def test_who_may_log_a_call(main_case, organisation, stratum):
    other = _invited(main_case, TokenStatus.OPENED)
    ra = _client(Role.CONTACT_RA, "calls_ra2")  # not assigned to this case
    assert ra.post(f"{URL}main/{other.sample_id}/", {"outcome": "REACHED"}, format="json").status_code == 404
    sup = _client(Role.SUPERVISOR_READONLY, "calls_sup")
    assert sup.get(URL).status_code == 200
    assert sup.post(f"{URL}main/{other.sample_id}/", {"outcome": "REACHED"}, format="json").status_code == 403
    kii_ra = _client(Role.KII_RA, "calls_kii2")  # a KII RA never logs a call on a Main case
    assert kii_ra.post(f"{URL}main/{other.sample_id}/", {"outcome": "REACHED"}, format="json").status_code == 404
    pi = _client(Role.PI_ADMIN, "calls_pi2")
    assert pi.post(f"{URL}main/{other.sample_id}/", {"outcome": "MAYBE"}, format="json").status_code == 400
    assert not ContactEvent.objects.exists()
