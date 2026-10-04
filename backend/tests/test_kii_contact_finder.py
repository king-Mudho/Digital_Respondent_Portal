"""
KII contact finder (apps/contacts/kii_finder.py). The web search and the model are mocked. Under test: only the
organisation and the informant's name and role are sent; a named record keeps only findings about THAT person, and only
with a published work contact; accepting never overwrites what is on the record, and replaces a placeholder name only
when the record is still a placeholder; the PI, Field Coordinator and KII RA decide, the Supervisor reads; KII and
Main-400 findings, batches and endpoints never mix.
"""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts import contact_finder as cf
from apps.contacts import kii_finder as kf
from apps.contacts.models import ContactProposal, ContactProposalStatus, ContactSearchRun, ContactSearchStatus
from apps.kii.services import create_kii_record

URL = "https://www.cbz.co.zw/leadership"
USAGE = {"in": 2000, "out": 300, "searches": 2, "cache_read": 0, "cache_write": 0}
BATCH_DELAY = "apps.contacts.tasks.search_contacts.delay"
DELAY = "apps.contacts.kii_views.search_contacts.delay"


def _meta(settings):
    settings.AI_PROIT_PROVIDER, settings.AI_PROIT_API_KEY, settings.AI_PROIT_RESEARCH_MODEL = "meta", "meta-key", "muse-spark-1.3"


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _user(role_name="KII_RA", username="kcf_ra"):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


def _record(name="Tendai Moyo", role="Head of Agribusiness", **fields):
    fields.setdefault("status", "PROSPECT")
    fields.setdefault("metadata", {"organisation_name": "CBZ Bank", "value_chain_activity": "Agricultural lending"})
    return create_kii_record(participant_name=name, participant_role=role, stakeholder_category="Bank, DFI & MFI", **fields)


@pytest.fixture
def named(db):
    return _record()


@pytest.fixture
def placeholder(db):
    return _record(name="CBZ Agro-Yield (contact not yet identified)", role="Head of Agri-finance")


def _finding(record, kind="ORG_PHONE", status=ContactProposalStatus.PROPOSED, **fields):
    run = record.contact_searches.first() or ContactSearchRun.objects.create(kii_record=record, status=ContactSearchStatus.DONE)
    return ContactProposal.objects.create(
        run=run, kii_record=record, kind=kind, status=status,
        sources=[{"title": "Leadership", "url": URL, "quote": "quoted"}], **fields,
    )


# --- What is sent, and what is kept ------------------------------------------------------------------------------

def test_the_brief_names_the_organisation_and_informant_and_never_a_contact_on_file(named, placeholder):
    named.phone, named.email = "0773943709", "t.moyo@example.com"
    prompt = kf.build_prompt(named)
    assert "CBZ Bank" in prompt and "Tendai Moyo" in prompt and "Head of Agribusiness" in prompt
    assert "0773943709" not in prompt and "t.moyo@example.com" not in prompt
    blank = kf.build_prompt(placeholder)
    assert "Not yet identified" in blank and "Head of Agri-finance" in blank and "contact not yet identified" not in blank
    assert kf.organisation_name(placeholder) == "CBZ Bank"  # from the register metadata


def test_a_placeholder_without_metadata_takes_the_organisation_from_its_name(db):
    record = _record(name="Grain Marketing Board (contact not yet identified)", metadata={})
    assert kf.organisation_name(record) == "Grain Marketing Board"


@pytest.mark.parametrize("found, same", [
    ("Dr Tendai Moyo", True), ("T. Moyo", True), ("Tendai P. Moyo", True), ("Grace Moyo", False), ("Tendai Ncube", False),
])
def test_names_match_on_surname_and_first_initial(found, same):
    assert kf.names_match("Tendai Moyo", found) is same


def test_a_named_record_keeps_only_that_person_and_only_with_a_work_contact(named, placeholder):
    found = [
        {"kind": "PERSON", "person_name": "Tendai Moyo", "person_email": "tmoyo@cbz.co.zw", "person_phone": ""},
        {"kind": "PERSON", "person_name": "Grace Ncube", "person_email": "gncube@cbz.co.zw", "person_phone": ""},
        {"kind": "PERSON", "person_name": "T. Moyo", "person_email": "", "person_phone": ""},
        {"kind": "ORG_PHONE", "value": "0242700000", "person_name": "", "person_email": "", "person_phone": ""},
    ]
    kept, dropped = kf.keep_the_informant(named, [dict(f) for f in found], [])
    assert [(k["kind"], k["person_name"]) for k in kept] == [("PERSON", "Tendai Moyo"), ("ORG_PHONE", "")]
    assert {d["reason"] for d in dropped} == {"not the named informant", "no published work contact for the informant"}
    kept, _ = kf.keep_the_informant(placeholder, [dict(f) for f in found], [])
    assert len(kept) == 4  # a placeholder keeps every person found in the role, for someone to choose


def test_a_kii_search_saves_its_findings_on_the_record_and_never_on_a_case(named, settings):
    _meta(settings)
    run = kf.start_search(named, user=_user())
    raw = {"summary": "Found the leadership page.", "contacts": [
        {"kind": "PERSON", "person_name": "Tendai Moyo", "person_title": "Head of Agribusiness", "person_email": "tmoyo@cbz.co.zw",
         "sources": [{"title": "Leadership", "url": URL, "quote": "Tendai Moyo, Head of Agribusiness, tmoyo@cbz.co.zw"}]},
        {"kind": "PERSON", "person_name": "Grace Ncube", "person_title": "CFO", "person_email": "gncube@cbz.co.zw",
         "sources": [{"title": "Leadership", "url": URL, "quote": "Grace Ncube, CFO, gncube@cbz.co.zw"}]},
    ]}
    with patch("apps.proit.ai_research.research_conversation", return_value=(raw, {URL}, USAGE)) as conv:
        cf.run_search(run.pk)
    run.refresh_from_db()
    assert run.status == ContactSearchStatus.DONE and run.sample_case_id is None
    assert list(run.proposals.values_list("person_name", "kii_record_id", "sample_case_id")) == [("Tendai Moyo", named.pk, None)]
    assert "Key informant" in conv.call_args.kwargs["prompt"] and conv.call_args.kwargs["system"] == kf.SYSTEM_PROMPT
    event = AuditEvent.objects.get(action="contacts.search_completed")
    assert event.object_type == "KIIRecord" and event.object_id == str(named.pk)


def test_an_interviewed_or_declined_informant_is_not_searched(db, settings):
    _meta(settings)
    for status in ("COMPLETED", "DECLINED"):
        with pytest.raises(cf.ContactFinderError) as refused:
            kf.start_search(_record(status=status), user=_user("KII_RA", f"kcf_{status}"))
        assert refused.value.code == "not_searchable"


# --- A person decides --------------------------------------------------------------------------------------------

def test_accepting_organisation_contacts_fills_the_record_and_never_overwrites(named):
    user = _user()
    kf.accept_proposal(_finding(named, kind="ORG_PHONE", value="0242700000"), user=user)
    kf.accept_proposal(_finding(named, kind="ORG_EMAIL", value="info@cbz.co.zw"), user=user)
    named.refresh_from_db()
    assert (named.phone, named.email) == ("0242700000", "info@cbz.co.zw")
    kf.accept_proposal(_finding(named, kind="ORG_PHONE", value="+263 242 700 000"), user=user)  # same number: fine
    with pytest.raises(cf.ContactFinderError) as refused:
        kf.accept_proposal(_finding(named, kind="ORG_PHONE", value="0242999999"), user=user)
    assert refused.value.code == "would_overwrite"
    named.refresh_from_db()
    assert named.phone == "0242700000"
    event = AuditEvent.objects.filter(action="contacts.kii_proposal_accepted").first()
    assert "0242700000" not in str(event.metadata) and event.metadata["filled"] == ["phone"]


def test_accepting_the_named_informants_work_contact_fills_it_but_a_different_person_is_refused(named):
    user = _user()
    kf.accept_proposal(_finding(named, kind="PERSON", person_name="Dr T. Moyo", person_title="Head", person_email="tmoyo@cbz.co.zw"), user=user)
    named.refresh_from_db()
    assert named.email == "tmoyo@cbz.co.zw" and named.participant_name == "Tendai Moyo"  # the name is not changed
    with pytest.raises(cf.ContactFinderError) as refused:
        kf.accept_proposal(_finding(named, kind="PERSON", person_name="Grace Ncube", person_title="CFO", person_phone="0242700001"), user=user)
    assert refused.value.code == "different_person"


def test_accepting_a_person_for_a_placeholder_names_the_informant_once(placeholder):
    user = _user()
    kf.accept_proposal(_finding(placeholder, kind="PERSON", person_name="Rudo Chari", person_title="Head of Agri-finance",
                                person_email="rchari@cbz.co.zw"), user=user)
    placeholder.refresh_from_db()
    assert (placeholder.participant_name, placeholder.participant_role, placeholder.email) == (
        "Rudo Chari", "Head of Agri-finance", "rchari@cbz.co.zw")
    event = AuditEvent.objects.get(action="contacts.kii_proposal_accepted")
    assert event.metadata["replaced_placeholder"] is True and "Rudo" not in str(event.metadata)
    with pytest.raises(cf.ContactFinderError) as refused:  # no longer a placeholder: a second person is a different one
        kf.accept_proposal(_finding(placeholder, kind="PERSON", person_name="Peter Dube", person_title="Manager"), user=user)
    assert refused.value.code == "different_person"


def test_a_website_is_kept_on_the_record_with_its_source_and_rejecting_changes_nothing(named):
    user = _user()
    kf.accept_proposal(_finding(named, kind="WEBSITE", value="https://www.cbz.co.zw"), user=user)
    named.refresh_from_db()
    assert named.metadata["public_contacts"]["website"]["value"] == "https://www.cbz.co.zw"
    rejected = kf.reject_proposal(_finding(named, kind="ORG_PHONE", value="0242700000"), user=user)
    named.refresh_from_db()
    assert rejected.status == ContactProposalStatus.REJECTED and named.phone == ""
    with pytest.raises(cf.ContactFinderError):
        kf.reject_proposal(rejected, user=user)


# --- Who may do what, and Main-400 never mixes with KII -----------------------------------------------------------

def test_the_pi_coordinator_and_kii_ra_decide_the_supervisor_reads_and_others_are_refused(named, settings):
    _meta(settings)
    base = f"/api/v1/contacts/kii/{named.pk}/contact-search/"
    for role in ("PI_ADMIN", "FIELD_COORDINATOR", "KII_RA"):
        finding = _finding(named, kind="WEBSITE", value=f"https://{role.lower()}.example.com")
        client = _client(role, f"kcf_{role}")
        assert client.get(base).status_code == 200
        assert client.post(f"/api/v1/contacts/kii-proposals/{finding.pk}/reject/", {}, format="json").status_code == 200
    supervisor = _client("SUPERVISOR_READONLY", "kcf_sup")
    assert supervisor.get(base).status_code == 200
    with patch(DELAY) as delay:
        assert supervisor.post(base).status_code == 403
        assert _client("CONTACT_RA", "kcf_cra").get(base).status_code == 403
    delay.assert_not_called()
    assert APIClient().get(base).status_code in (401, 403)


def test_kii_and_main_findings_each_use_only_their_own_endpoints(named, main_case):
    kii_finding = _finding(named, kind="ORG_PHONE", value="0242700000")
    run = ContactSearchRun.objects.create(sample_case=main_case, status=ContactSearchStatus.DONE)
    main_finding = ContactProposal.objects.create(run=run, sample_case=main_case, kind="ORG_PHONE", value="0773943709", sources=[])
    pi = _client("PI_ADMIN", "kcf_pi_mix")
    assert pi.post(f"/api/v1/contacts/contact-proposals/{kii_finding.pk}/accept/", {}, format="json").status_code == 404
    assert pi.post(f"/api/v1/contacts/kii-proposals/{main_finding.pk}/accept/", {}, format="json").status_code == 404
    main_review = pi.get("/api/v1/contacts/contact-proposals/review/").data
    assert main_review["total_waiting"] == 1  # the KII finding is not on the Main-400 review page
    assert cf.batch_status()["to_review_total"] == 1 and kf.batch_status()["to_review_total"] == 1


def test_a_search_and_a_finding_belong_to_exactly_one_of_a_case_or_a_kii_record(named, main_case):
    from django.db import IntegrityError, transaction

    for fields in ({}, {"sample_case": main_case, "kii_record": named}):
        with pytest.raises(IntegrityError), transaction.atomic():
            ContactSearchRun.objects.create(status=ContactSearchStatus.DONE, **fields)


# --- Batches -----------------------------------------------------------------------------------------------------

def test_a_kii_batch_picks_only_searchable_records_still_without_contacts(named, placeholder, db):
    _record(name="Has Phone", phone="0242700000")
    _record(name="Done Already", status="COMPLETED")
    recently = _record(name="Searched Recently")
    ContactSearchRun.objects.create(kii_record=recently, status=ContactSearchStatus.DONE)
    failed = _record(name="Search Failed")
    ContactSearchRun.objects.create(kii_record=failed, status=ContactSearchStatus.FAILED)
    assert set(kf.records_without_contacts().values_list("pk", flat=True)) == {named.pk, placeholder.pk, failed.pk}


def test_one_kii_batch_at_a_time_queued_once_saved_and_main_batches_are_not_blocked(
    named, placeholder, main_case, settings, django_capture_on_commit_callbacks,
):
    _meta(settings)
    with patch(BATCH_DELAY) as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            runs = kf.start_batch(5, user=_user())
        delay.assert_not_called()
        for callback in callbacks:
            callback()
    assert len(runs) == 2 and sorted(c.args[0] for c in delay.call_args_list) == sorted(r.pk for r in runs)
    with pytest.raises(cf.ContactFinderError) as refused:
        kf.start_batch(5, user=_user("KII_RA", "kcf_ra2"))
    assert refused.value.code == "batch_running"
    with patch(BATCH_DELAY):
        assert len(cf.start_batch(1, user=_user("FIELD_COORDINATOR", "kcf_fc"))) == 1  # a Main batch is not blocked
    progress = kf.batch_status()["progress"]
    assert (progress["total"], progress["queued"], progress["active"]) == (2, 2, True)
    assert cf.batch_status()["progress"]["total"] == 1  # each register shows its own batch


def test_the_kii_batch_endpoint_is_open_to_the_kii_ra_and_reads_for_the_supervisor(named, settings, django_capture_on_commit_callbacks):
    _meta(settings)
    batch = "/api/v1/contacts/kii-contact-search/batch/"
    assert _client("SUPERVISOR_READONLY", "kcf_sup_b").get(batch).data["without_contacts"] == 1
    assert _client("SUPERVISOR_READONLY", "kcf_sup_b2").post(batch, {"limit": 1}, format="json").status_code == 403
    with patch(BATCH_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        started = _client("KII_RA", "kcf_ra_b").post(batch, {"limit": 1}, format="json")
    assert started.status_code == 202 and started.data["queued"] == 1 and delay.call_count == 1
