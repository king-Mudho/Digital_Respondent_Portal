"""Research assistants who phone both Main-400 respondents and key informants, and are paid per completion (apps/ra,
PI decision 8 Nov 2026). Under test:

- a Research Assistant (calls) sees only the Main-400 cases and KII records assigned to them, on Calls and
  Communications, and lands on My work;
- "fill in with them now" records verbal consent (and eligibility for the questionnaire), refuses a case not theirs
  or a locked Reserve, and stamps the form with a value only the portal can sign; a tampered or borrowed stamp
  credits nobody;
- each completion is credited ADMINISTERED (they filled it in), ASSISTED (their call or message came last within the
  window before the respondent's own submission) or UNCREDITED; the PI's own calls never credit an RA;
- the PI alone overrides a credit, with a reason; an RA sees only their own credits; the team pay sheet downloads.
"""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentMethod, ConsentRecord
from apps.contacts.models import ContactChannel, ContactEvent, ContactOutcome
from apps.kii.models import KIIStatus
from apps.kii.services import create_kii_record
from apps.kobo.models import QUANSubmission
from apps.ra import credit
from apps.ra.administer import ra_from_payload, sign_ra
from apps.ra.models import CreditKind, SubmissionCredit


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role, first_name=username.title())


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def team(db, settings):
    settings.KOBO_FORM_URL = "https://ee.kobotoolbox.org/x/Main"
    settings.KOBO_KII_FORM_URL = "https://ee.kobotoolbox.org/x/KII"
    settings.RA_ASSIST_CREDIT_DAYS = 14
    return {"pi": _user(Role.PI_ADMIN, "ra_pi"), "rudo": _user(Role.TELEPHONE_RA, "rudo"),
            "tino": _user(Role.TELEPHONE_RA, "tino"), "fc": _user(Role.FIELD_COORDINATOR, "ra_fc")}


@pytest.fixture
def work(team, main_case, organisation, stratum):
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_sample_case

    other = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    main_case.assigned_ra, other.assigned_ra = team["rudo"], team["tino"]
    main_case.save(update_fields=["assigned_ra"])
    other.save(update_fields=["assigned_ra"])
    kii_mine = create_kii_record(participant_name="Tendai Moyo", participant_role="Head", stakeholder_category="Bank",
                                 metadata={"organisation_name": "CBZ Bank"}, phone="0772222222")
    kii_other = create_kii_record(participant_name="Rudo Chari", participant_role="Head", stakeholder_category="Bank",
                                  metadata={"organisation_name": "AFC"}, phone="0773333333")
    return {"main": main_case, "other_main": other, "kii": kii_mine, "other_kii": kii_other}


def _assign_kii(client, ra, kii_ids):
    return client.post("/api/v1/ra/assign-kii/", {"ra_id": ra.id, "kii_ids": kii_ids}, format="json")


def test_an_ra_sees_only_the_cases_and_kii_records_assigned_to_them(team, work):
    assert _assign_kii(_client(team["pi"]), team["rudo"], [work["kii"].kii_id]).status_code == 200
    from apps.messaging.communications import visible_cases, visible_records

    assert list(visible_cases(team["rudo"])) == [work["main"]]
    assert list(visible_records(team["rudo"])) == [work["kii"]]
    assert list(visible_records(team["tino"])) == []
    me = _client(team["rudo"]).get("/api/v1/auth/me/").json()
    assert me["landing_path"] == "/admin/my-work"
    assert {s["id"] for s in me["screens"]} == {"my_work", "calls", "follow_ups", "conversations", "appointments", "sample_register"}
    assert _client(team["rudo"]).get("/api/v1/ra/team/").status_code == 403
    # KII records go only to a Research Assistant (calls).
    assert _assign_kii(_client(team["pi"]), team["fc"], [work["other_kii"].kii_id]).status_code == 400


def test_filling_in_with_them_records_consent_and_stamps_the_ra(team, work):
    rudo = _client(team["rudo"])
    url = "/api/v1/ra/administer/main/{}/"
    refused = rudo.post(url.format(work["other_main"].sample_id), {"mode": "PHONE", "respondent_name": "X", "role_category": "CEO_MD"}, format="json")
    assert refused.status_code == 404  # not assigned to them
    assert rudo.post(url.format(work["main"].sample_id), {"mode": "PHONE"}, format="json").json()["error"]["code"] == "eligibility_required"

    resp = rudo.post(url.format(work["main"].sample_id), {"mode": "WHATSAPP_CALL", "respondent_name": "Jane Doe",
                                                          "role_category": "CEO_MD", "information_sheet_version": "v1.5"}, format="json")
    assert resp.status_code == 200, resp.content
    query = parse_qs(urlparse(resp.json()["kobo_form_url"]).query)
    assert query["d[administration_mode]"] == ["04"]
    assert ra_from_payload({"ra_id": query["d[ra_id]"][0]}, work["main"].sample_id) == team["rudo"]
    consent = ConsentRecord.objects.get(sample_case=work["main"])
    assert (consent.method, consent.decision) == (ConsentMethod.VERBAL_RA_RECORDED, "GIVEN")
    event = ContactEvent.objects.get(sample_case=work["main"])
    assert (event.ra, event.outcome, event.channel) == (team["rudo"], ContactOutcome.ADMINISTERED, ContactChannel.WHATSAPP_CALL)


def test_a_locked_reserve_is_never_administered(team, locked_reserve_case):
    locked_reserve_case.assigned_ra = team["rudo"]
    locked_reserve_case.save(update_fields=["assigned_ra"])
    resp = _client(team["rudo"]).post(f"/api/v1/ra/administer/main/{locked_reserve_case.sample_id}/",
                                      {"mode": "PHONE", "respondent_name": "X", "role_category": "CEO_MD"}, format="json")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "not_invitable"


def test_only_the_portals_own_stamp_credits_an_ra(team, work):
    stamp = sign_ra(team["rudo"], work["main"].sample_id)
    assert ra_from_payload({"ra_id": stamp}, work["main"].sample_id) == team["rudo"]
    assert ra_from_payload({"ra_id": stamp}, work["other_main"].sample_id) is None  # borrowed from another case
    assert ra_from_payload({"ra_id": stamp[:-3] + "abc"}, work["main"].sample_id) is None  # tampered
    assert ra_from_payload({"ra_id": "rudo"}, work["main"].sample_id) is None  # typed in
    assert ra_from_payload({}, work["main"].sample_id) is None


def _submission(case, *, ra=None, days_ago=0, uuid="u-1"):
    return QUANSubmission.objects.create(sample_case=case, kobo_submission_uuid=uuid, administration_mode="03" if ra else "01",
                                         submitted_at=timezone.now() - timedelta(days=days_ago), ra=ra)


def _call(case, user, days_ago, outcome=ContactOutcome.REACHED):
    ContactEvent.objects.create(sample_case=case, channel=ContactChannel.PHONE, outcome=outcome, ra=user,
                                occurred_at=timezone.now() - timedelta(days=days_ago))


def test_each_completion_is_credited_administered_assisted_or_to_nobody(team, work, organisation, stratum):
    from apps.sampling.models import SampleType
    from apps.sampling.services import create_sample_case

    def case():
        return create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)

    administered = _submission(work["main"], ra=team["rudo"], uuid="adm")
    assisted_case = case()
    _call(assisted_case, team["tino"], days_ago=5)
    _call(assisted_case, team["rudo"], days_ago=3)  # the latest RA contact before the submission wins
    _call(assisted_case, team["tino"], days_ago=0.5)  # after the submission: never counts
    assisted = _submission(assisted_case, days_ago=1, uuid="ast")
    pi_case = case()
    _call(pi_case, team["pi"], days_ago=1)  # the PI's own call credits no RA
    pi_only = _submission(pi_case, uuid="pi")
    old_case = case()
    _call(old_case, team["rudo"], days_ago=20)  # outside the 14-day window
    too_old = _submission(old_case, uuid="old")

    credit.refresh()
    got = {c.quan_submission_id: (c.kind, c.ra) for c in SubmissionCredit.objects.all()}
    assert got[administered.pk] == (CreditKind.ADMINISTERED, team["rudo"])
    assert got[assisted.pk] == (CreditKind.ASSISTED, team["rudo"])
    assert got[pi_only.pk] == (CreditKind.UNCREDITED, None)
    assert got[too_old.pk] == (CreditKind.UNCREDITED, None)
    assert credit.refresh() == {"created": 0, "updated": 0}  # idempotent


def test_a_kii_the_ra_conducted_is_credited_to_them(team, work):
    _assign_kii(_client(team["pi"]), team["rudo"], [work["kii"].kii_id])
    resp = _client(team["rudo"]).post(f"/api/v1/ra/administer/kii/{work['kii'].kii_id}/",
                                      {"mode": "PHONE", "information_sheet_version": "KII-v1.0"}, format="json")
    assert resp.status_code == 200, resp.content
    assert "interviewer_code%5D=rudo" in resp.json()["kobo_form_url"].replace("]", "%5D") or "interviewer_code]=rudo" in resp.json()["kobo_form_url"]
    work["kii"].refresh_from_db()
    assert work["kii"].interviewer == team["rudo"]
    work["kii"].status = KIIStatus.COMPLETED
    work["kii"].save(update_fields=["status"])
    credit.refresh()
    kii_credit = SubmissionCredit.objects.get(kii_record=work["kii"])
    assert (kii_credit.kind, kii_credit.ra) == (CreditKind.ADMINISTERED, team["rudo"])
    # Another RA's KII can't be opened.
    assert _client(team["tino"]).post(f"/api/v1/ra/administer/kii/{work['kii'].kii_id}/", {"mode": "PHONE"}, format="json").status_code == 404


def test_the_pi_alone_overrides_a_credit_and_it_stays(team, work):
    _submission(work["main"], days_ago=1)
    credit.refresh()
    c = SubmissionCredit.objects.get()
    assert c.kind == CreditKind.UNCREDITED
    url = f"/api/v1/ra/credits/{c.pk}/override/"
    body = {"ra_id": team["rudo"].id, "kind": "ASSISTED", "reason": "Rudo phoned from her own phone and forgot to log it"}
    assert _client(team["fc"]).post(url, body, format="json").status_code == 403
    assert _client(team["pi"]).post(url, {**body, "reason": ""}, format="json").status_code == 400
    assert _client(team["pi"]).post(url, body, format="json").status_code == 200
    credit.refresh()
    c.refresh_from_db()
    assert (c.kind, c.ra, c.override_reason[:4]) == (CreditKind.ASSISTED, team["rudo"], "Rudo")
    assert AuditEvent.objects.filter(action="ra_credit.overridden").count() == 1


def test_an_ra_sees_only_their_own_credits_and_the_pi_gets_the_pay_sheet(team, work):
    _submission(work["main"], ra=team["rudo"], uuid="r1")
    _submission(work["other_main"], ra=team["tino"], uuid="t1")
    mine = _client(team["rudo"]).get("/api/v1/ra/my-work/").json()
    assert [c["ref"] for c in mine["credits"]] == [work["main"].sample_id]
    assert mine["totals"]["quan_administered"] == 1 and mine["workload"]["main_assigned"] == 1
    sheet = _client(team["pi"]).get("/api/v1/ra/team/").json()
    by_name = {t["username"]: t["credits"]["total"] for t in sheet["team"]}
    assert by_name == {"rudo": 1, "tino": 1}
    csv_resp = _client(team["fc"]).get("/api/v1/ra/team/", {"download": "csv"})
    assert csv_resp.status_code == 200 and b"Rudo" in csv_resp.content and b"Administered by the RA" in csv_resp.content
    assert _client(team["rudo"]).get("/api/v1/ra/my-work/", {"since": "2099-01-01"}).json()["credits"] == []


def test_an_ras_assigned_people_with_no_link_yet_are_on_their_call_list(team, work):
    """Assigned and not invited yet: listed for the RA to phone and fill in with them -- and not for anyone else."""
    from apps.sampling.models import WorkflowStatus

    work["main"].workflow_status = WorkflowStatus.S03_ELIGIBLE_RESPONDENT_IDENTIFIED
    work["main"].save(update_fields=["workflow_status"])
    _assign_kii(_client(team["pi"]), team["rudo"], [work["kii"].kii_id])
    body = _client(team["rudo"]).get("/api/v1/calls/", {"stage": "no_link"}).json()
    assert sorted(r["id"] for r in body["results"]) == sorted([work["main"].sample_id, work["kii"].kii_id])
    assert {r["assigned_to"] for r in body["results"]} == {"Rudo"}
    assert _client(team["tino"]).get("/api/v1/calls/", {"stage": "no_link"}).json()["results"] == []


def test_open_work_moves_from_the_shared_account_to_an_ra_reserves_included(team, work, activated_reserve_case):
    shared = _user(Role.CONTACT_RA, "contact_ra_shared")
    activated_reserve_case.assigned_ra = shared
    activated_reserve_case.save(update_fields=["assigned_ra"])
    work["main"].assigned_ra = shared
    work["main"].save(update_fields=["assigned_ra"])
    pi = _client(team["pi"])
    holders = {h["username"]: h["count"] for h in pi.get("/api/v1/ra/team/").json()["main_holders"]}
    assert holders["contact_ra_shared"] == 2
    resp = pi.post("/api/v1/ra/assign-main/", {"ra_id": team["rudo"].id, "from": shared.id, "limit": 5}, format="json")
    assert resp.status_code == 200 and sorted(resp.json()["sample_ids"]) == sorted([work["main"].sample_id, activated_reserve_case.sample_id])
    activated_reserve_case.refresh_from_db()
    assert activated_reserve_case.assigned_ra == team["rudo"]
    assert pi.post("/api/v1/ra/assign-main/", {"ra_id": team["pi"].id, "from": "unassigned"}, format="json").status_code == 400
    assert _client(team["rudo"]).post("/api/v1/ra/assign-main/", {"ra_id": team["rudo"].id, "from": "unassigned"}, format="json").status_code == 403


# --- Everyone given a link goes on the calling RA's list (apps/ra/assignment.py, PI 12 Nov 2026) --------------------

def _caller(username="chido", role="TELEPHONE_RA", active=True):
    from apps.accounts.models import Role, User

    r, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=r, is_active=active)


def test_a_newly_issued_link_puts_the_case_and_the_kii_record_on_the_named_ras_list(main_case, settings):
    from apps.audit.models import AuditEvent
    from apps.invitations.services import issue_invitation
    from apps.kii.services import create_kii_record, issue_kii_invitation

    ra = _caller()
    settings.RA_NEW_LINK_ASSIGNEE = "chido"
    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Director", stakeholder_category="Bank",
                               phone="0772000001", metadata={"organisation_name": "Agri Bank"})
    issue_invitation(main_case, channel="WHATSAPP", issued_by=None)
    issue_kii_invitation(record)
    main_case.refresh_from_db(), record.refresh_from_db()
    assert main_case.assigned_ra == ra and record.assigned_ra == ra
    logged = [e.metadata for e in AuditEvent.objects.filter(action="ra.assigned")]
    assert {m["study"] for m in logged} == {"QUAN", "KII"} and all(m["to"] == "chido" and m["from"] == "unassigned" for m in logged)


def test_a_link_assigns_nobody_while_the_setting_is_empty_or_names_no_calling_ra(main_case, settings):
    from apps.invitations.services import issue_invitation

    _caller()
    issue_invitation(main_case, channel="WHATSAPP", issued_by=None)  # RA_NEW_LINK_ASSIGNEE is empty by default
    main_case.refresh_from_db()
    assert main_case.assigned_ra is None
    for username, role, active in (("gone", "TELEPHONE_RA", False), ("analyst1", "ANALYST", True)):
        _caller(username, role, active)
        settings.RA_NEW_LINK_ASSIGNEE = username
        issue_invitation(main_case, channel="WHATSAPP", issued_by=None)
        main_case.refresh_from_db()
        assert main_case.assigned_ra is None
    settings.RA_NEW_LINK_ASSIGNEE = "nobody-by-this-name"
    issue_invitation(main_case, channel="WHATSAPP", issued_by=None)
    main_case.refresh_from_db()
    assert main_case.assigned_ra is None


def test_a_link_leaves_another_calling_ras_work_and_held_duplicates_where_they_are(main_case, organisation, stratum, settings):
    from apps.invitations.services import issue_invitation
    from apps.sampling.services import create_organisation, create_sample_case

    _caller()
    other = _caller("second_caller")
    shared = _caller("shared_contact", role="CONTACT_RA")
    settings.RA_NEW_LINK_ASSIGNEE = "chido"
    main_case.assigned_ra = other
    main_case.save(update_fields=["assigned_ra"])
    issue_invitation(main_case, channel="WHATSAPP", issued_by=None)
    main_case.refresh_from_db()
    assert main_case.assigned_ra == other  # already on an active calling RA's list

    def _case(name, **fields):
        org = create_organisation(province=organisation.province, name=name, entity_type="Private Limited Company",
                                  district="Harare", actor_family=organisation.actor_family, value_chain="Horticulture",
                                  size_class=organisation.size_class)
        case = create_sample_case(organisation=org, stratum=stratum, sample_type="MAIN", year=2026)
        for field, value in fields.items():
            setattr(case, field, value)
        case.save()
        return case

    held = _case("Held Duplicate Ltd", metadata={"duplicate_of": "SID-2026-000001"})
    issue_invitation(held, channel="WHATSAPP", issued_by=None)
    held.refresh_from_db()
    assert held.assigned_ra is None  # the PI keeps held duplicates off the call lists

    moved = _case("Shared Account Ltd", assigned_ra=shared)
    issue_invitation(moved, channel="WHATSAPP", issued_by=None)
    moved.refresh_from_db()
    assert moved.assigned_ra.username == "chido"  # the shared Contact RA account phones nobody


def test_new_links_are_shared_between_the_named_ras_shorter_list_first(main_case, organisation, stratum, settings):
    """PI, 12 Nov 2026: with two calling RAs, links alternate while their lists are level and a shorter list catches up
    first. Main-400 cases and KII records are counted separately."""
    from apps.invitations.services import issue_invitation
    from apps.kii.services import create_kii_record, issue_kii_invitation
    from apps.sampling.services import create_organisation, create_sample_case

    first, second = _caller("chido"), _caller("geyi")
    settings.RA_NEW_LINK_ASSIGNEE = "chido, geyi, somebody-who-left"

    def _case(name, assigned=None):
        org = create_organisation(province=organisation.province, name=name, entity_type="Private Limited Company",
                                  district="Harare", actor_family=organisation.actor_family, value_chain="Horticulture",
                                  size_class=organisation.size_class)
        case = create_sample_case(organisation=org, stratum=stratum, sample_type="MAIN", year=2026)
        case.assigned_ra = assigned
        case.save()
        return case

    for n in range(2):  # the first named starts two cases ahead
        _case(f"Already Chido {n} Ltd", assigned=first)
    got = []
    for case in [main_case, *[_case(f"New {n} Ltd") for n in range(4)]]:
        issue_invitation(case, channel="WHATSAPP", issued_by=None)
        case.refresh_from_db()
        got.append(case.assigned_ra.username)
    assert got == ["geyi", "geyi", "chido", "geyi", "chido"]  # geyi catches up, then they alternate, chido first on a tie

    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Director", stakeholder_category="Bank",
                               phone="0772000001", metadata={"organisation_name": "Agri Bank"})
    issue_kii_invitation(record)
    record.refresh_from_db()
    assert record.assigned_ra == first  # no KII work on either yet: the Main-400 counts above play no part
    assert second.pk != first.pk
