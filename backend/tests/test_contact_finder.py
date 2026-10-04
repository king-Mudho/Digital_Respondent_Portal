"""
Contact finder (apps/contacts/contact_finder.py). The web search and the model are mocked: what is under test is that
the server never trusts the AI (a contact must be shown in the passage quoted from a page the search returned, never a
social page, nothing private), that only the PI or Field Coordinator decides, that accepting never overwrites what an
RA entered, and that a batch only ever picks cases that may be invited and still have no contact details.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts import contact_finder as cf
from apps.contacts.models import (
    ContactProposal,
    ContactProposalStatus,
    ContactSearchRun,
    ContactSearchStatus,
    Respondent,
)
from apps.sampling.models import SampleType
from apps.sampling.services import create_sample_case

URL = "https://www.testorg.co.zw/contact-us"
DELAY = "apps.contacts.finder_views.search_contacts.delay"  # a single-case search, queued by the view
BATCH_DELAY = "apps.contacts.tasks.search_contacts.delay"  # a batch, queued by start_batch once saved
USAGE = {"in": 2000, "out": 300, "searches": 2, "cache_read": 0, "cache_write": 0}


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _user(role_name="FIELD_COORDINATOR", username="cf_fc"):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


def _src(quote, url=URL):
    return [{"title": "Contact us", "url": url, "quote": quote}]


def _meta(settings):
    settings.AI_PROIT_PROVIDER, settings.AI_PROIT_API_KEY, settings.AI_PROIT_RESEARCH_MODEL = "meta", "meta-key", "muse-spark-1.3"


# --- The server never trusts the AI ------------------------------------------------------------------------------

def test_a_contact_shown_in_its_quote_survives_and_phone_formats_are_matched():
    raw = {"contacts": [
        {"kind": "ORG_PHONE", "value": "+263 77 394 3709", "sources": _src("Call us on 0773 943 709 today")},
        {"kind": "ORG_EMAIL", "value": "info@testorg.co.zw", "sources": _src("Email us: info@testorg.co.zw")},
        {"kind": "WEBSITE", "value": "https://www.testorg.co.zw", "sources": _src("Welcome to Test Organisation")},
    ]}
    proposals, dropped = cf.clean_contacts(raw, {URL})
    assert [p["kind"] for p in proposals] == ["ORG_PHONE", "ORG_EMAIL", "WEBSITE"] and dropped == []


def test_a_website_written_without_https_is_kept_with_https_added():
    # Muse wrote websites as "cottco.co.zw" for three real companies on 2026-10-03, and each was refused.
    raw = {"contacts": [{"kind": "WEBSITE", "value": "www.testorg.co.zw", "sources": _src("Visit www.testorg.co.zw")}]}
    proposals, dropped = cf.clean_contacts(raw, {URL})
    assert [p["value"] for p in proposals] == ["https://www.testorg.co.zw"] and dropped == []


def test_a_contact_missing_from_its_quoted_passage_is_dropped_as_unsupported():
    raw = {"contacts": [
        {"kind": "ORG_PHONE", "value": "0772 000 111", "sources": _src("Call us on 0773 943 709")},
        {"kind": "ORG_EMAIL", "value": "sales@testorg.co.zw", "sources": _src("Email us: info@testorg.co.zw")},
    ]}
    proposals, dropped = cf.clean_contacts(raw, {URL})
    assert proposals == []
    assert [d["reason"] for d in dropped] == ["the quoted page text does not show this detail"] * 2


def test_a_source_the_search_never_returned_or_a_social_page_is_dropped():
    facebook = "https://www.facebook.com/testorg"
    raw = {"contacts": [
        {"kind": "ORG_PHONE", "value": "0773943709", "sources": _src("0773943709", url="https://elsewhere.example/x")},
        {"kind": "ORG_EMAIL", "value": "info@testorg.co.zw", "sources": _src("info@testorg.co.zw", url=facebook)},
        {"kind": "WEBSITE", "value": facebook, "sources": _src("facebook.com/testorg")},
    ]}
    proposals, dropped = cf.clean_contacts(raw, {URL, facebook, "https://elsewhere.example/other"})
    assert proposals == []
    reasons = [d["reason"] for d in dropped]
    assert "url was not returned by the search" in reasons and "social page not shown to be the organisation's own" in reasons
    assert "not an organisation website" in reasons


def test_the_organisations_own_social_page_can_support_its_contacts_but_never_a_named_person():
    page = "https://www.facebook.com/testorganisationzw"
    profile = "https://www.facebook.com/profile.php?id=99"
    own = [{"title": "Test Organisation | Facebook", "url": page, "quote": "Test Organisation. Call us on 0773 943 709"}]
    raw = {"contacts": [
        {"kind": "ORG_PHONE", "value": "0773943709", "confidence": "HIGH", "sources": own},
        {"kind": "WEBSITE", "value": page, "sources": own},
        {"kind": "PERSON", "person_name": "Tendai Moyo", "person_title": "Owner",
         "sources": [{"title": "Test Organisation | Facebook", "url": page, "quote": "Tendai Moyo, Owner, Test Organisation"}]},
        {"kind": "ORG_EMAIL", "value": "info@testorg.co.zw", "sources": [{"title": "Profile", "url": profile, "quote": "info@testorg.co.zw"}]},
    ]}
    proposals, dropped = cf.clean_contacts(raw, {page, profile}, org_name="Test Organisation (Pvt) Ltd")
    assert [p["kind"] for p in proposals] == ["ORG_PHONE", "WEBSITE"]
    assert proposals[0]["confidence"] == "MODERATE"  # a social page alone is at most moderate
    reasons = {d["reason"] for d in dropped}
    assert "social pages are not used for a named person" in reasons and "personal or social page refused" in reasons


def test_a_person_needs_a_title_and_a_name_in_the_quote_and_unshown_details_are_cleared():
    raw = {"contacts": [
        {"kind": "PERSON", "person_name": "No Title", "sources": _src("No Title works here")},
        {"kind": "PERSON", "person_name": "Ghost Person", "person_title": "Director", "sources": _src("Our team")},
        {"kind": "PERSON", "person_name": "Tendai Moyo", "person_title": "Managing Director",
         "person_email": "tmoyo@testorg.co.zw", "person_phone": "0773943709",
         "sources": _src("Tendai Moyo, Managing Director. Tel 0773 943 709")},
    ]}
    proposals, dropped = cf.clean_contacts(raw, {URL})
    assert len(proposals) == 1
    kept = proposals[0]
    assert kept["person_name"] == "Tendai Moyo" and kept["person_phone"] == "0773943709"
    assert kept["person_email"] == ""  # the email was not in the quoted text, so it is not kept
    reasons = [d["reason"] for d in dropped]
    assert "a person needs a name and a published job title" in reasons
    assert "the quoted page text does not show this person" in reasons
    assert "work email not shown in the quoted text" in reasons


def test_anything_private_is_dropped():
    raw = {"contacts": [{"kind": "OFFICE_LOCATION", "value": "Home address: 12 Smith Road",
                         "sources": _src("Home address: 12 Smith Road")}]}
    proposals, dropped = cf.clean_contacts(raw, {URL})
    assert proposals == [] and dropped[0]["reason"] == "looked private"


def test_a_webmail_address_is_kept_but_flagged_for_the_reviewer():
    raw = {"contacts": [{"kind": "ORG_EMAIL", "value": "testorg@gmail.com", "sources": _src("Write to testorg@gmail.com")}]}
    proposals, _dropped = cf.clean_contacts(raw, {URL})
    assert proposals[0]["flags"] == ["webmail"]


# --- A person decides, and never overwrites an RA's entry --------------------------------------------------------

@pytest.fixture
def make_proposal(main_case):
    run = ContactSearchRun.objects.create(sample_case=main_case, status=ContactSearchStatus.DONE)

    def make(**fields):
        return ContactProposal.objects.create(run=run, sample_case=main_case, sources=_src("quoted"), **fields)
    return make


def test_accepting_organisation_contacts_fills_one_placeholder_contact_and_the_audit_omits_the_value(main_case, make_proposal):
    user = _user()
    cf.accept_proposal(make_proposal(kind="ORG_PHONE", value="0773943709"), user=user)
    cf.accept_proposal(make_proposal(kind="ORG_EMAIL", value="info@testorg.co.zw"), user=user)
    contact = main_case.respondents.get()
    assert contact.full_name == cf.PLACEHOLDER_NAME
    assert contact.phone == "0773943709" and contact.email == "info@testorg.co.zw"
    events = AuditEvent.objects.filter(action="contacts.proposal_accepted")
    assert events.count() == 2
    assert all("0773943709" not in str(e.metadata) and "info@" not in str(e.metadata) for e in events)


def test_accepting_never_overwrites_a_value_an_ra_entered(main_case, make_proposal):
    Respondent.objects.create(sample_case=main_case, full_name=cf.PLACEHOLDER_NAME, phone="0712345678")
    different = make_proposal(kind="ORG_PHONE", value="0773943709")
    with pytest.raises(cf.ContactFinderError) as exc:
        cf.accept_proposal(different, user=_user())
    assert exc.value.code == "would_overwrite"
    assert main_case.respondents.get().phone == "0712345678"
    different.refresh_from_db()
    assert different.status == ContactProposalStatus.PROPOSED
    same = make_proposal(kind="ORG_PHONE", value="+263 712 345 678")  # the same number, written differently
    assert cf.accept_proposal(same, user=_user("FIELD_COORDINATOR", "cf_fc2")).status == ContactProposalStatus.ACCEPTED


def test_accepting_a_person_creates_a_respondent_with_the_chosen_role_and_no_eligibility(main_case, make_proposal):
    person = dict(kind="PERSON", person_name="Tendai Moyo", person_title="Managing Director", person_email="tmoyo@testorg.co.zw")
    accepted = cf.accept_proposal(make_proposal(**person), user=_user(), role_category="CEO_MD")
    respondent = Respondent.objects.get(pk=accepted.respondent_id)
    assert respondent.full_name == "Tendai Moyo" and respondent.role_category == "CEO_MD"
    assert respondent.email == "tmoyo@testorg.co.zw" and respondent.is_eligible is None
    with pytest.raises(cf.ContactFinderError) as exc:
        cf.accept_proposal(make_proposal(**person), user=_user("FIELD_COORDINATOR", "cf_fc3"))
    assert exc.value.code == "duplicate"
    with pytest.raises(cf.ContactFinderError) as bad:
        cf.accept_proposal(make_proposal(**{**person, "person_name": "Other Person"}), user=_user("FIELD_COORDINATOR", "cf_fc4"), role_category="KING")
    assert bad.value.code == "bad_role"


def test_rejecting_changes_nothing_and_a_finding_cannot_be_decided_twice(main_case, make_proposal):
    finding = make_proposal(kind="ORG_PHONE", value="0773943709")
    cf.reject_proposal(finding, user=_user(), reason="Wrong company")
    assert main_case.respondents.count() == 0
    with pytest.raises(cf.ContactFinderError) as exc:
        cf.accept_proposal(finding, user=_user("FIELD_COORDINATOR", "cf_fc5"))
    assert exc.value.code == "already_decided"


def test_a_website_is_kept_on_the_organisation_with_its_source(main_case, make_proposal):
    cf.accept_proposal(make_proposal(kind="WEBSITE", value="https://www.testorg.co.zw"), user=_user())
    main_case.organisation.refresh_from_db()
    kept = main_case.organisation.metadata["public_contacts"]["website"]
    assert kept["value"] == "https://www.testorg.co.zw" and kept["source"] == URL
    assert main_case.respondents.count() == 0


# --- Who may run it, and what is sent where ----------------------------------------------------------------------

def test_only_the_pi_and_coordinator_may_search_or_decide_and_the_supervisor_may_read(main_case, make_proposal, settings):
    _meta(settings)
    finding = make_proposal(kind="ORG_PHONE", value="0773943709")
    search = f"/api/v1/contacts/{main_case.sample_id}/contact-search/"
    accept = f"/api/v1/contacts/contact-proposals/{finding.pk}/accept/"
    for role in ("CONTACT_RA", "KII_RA", "DOCUMENTARY_RA", "ANALYST"):
        client = _client(role, f"cf_{role.lower()}")
        assert client.post(search).status_code == 403, role
        assert client.post(accept).status_code == 403, role
    supervisor = _client("SUPERVISOR_READONLY", "cf_sup")
    assert supervisor.get(search).status_code == 200
    assert supervisor.post(search).status_code == 403
    assert APIClient().get(search).status_code == 401
    with patch(DELAY) as delay:
        resp = _client("FIELD_COORDINATOR", "cf_fc_api").post(search)
    assert resp.status_code == 202 and delay.call_count == 1
    assert ContactSearchRun.objects.get(pk=resp.data["id"]).provider == "meta"


def test_a_locked_reserve_is_never_searched_and_nothing_runs_without_a_key(locked_reserve_case, main_case, settings):
    _meta(settings)
    coordinator = _client("FIELD_COORDINATOR", "cf_fc_lock")
    with patch(DELAY) as delay:
        locked = coordinator.post(f"/api/v1/contacts/{locked_reserve_case.sample_id}/contact-search/")
        settings.AI_PROIT_API_KEY = ""
        unconfigured = coordinator.post(f"/api/v1/contacts/{main_case.sample_id}/contact-search/")
    assert locked.status_code == 409 and locked.data["error"]["code"] == "not_invitable"
    assert unconfigured.status_code == 503
    delay.assert_not_called()


def test_a_run_records_findings_provider_and_tokens_and_puts_nothing_in_a_respondent(main_case, settings):
    _meta(settings)
    run = cf.start_search(main_case, user=_user())
    raw = {"summary": "Found the contact page.", "contacts": [
        {"kind": "ORG_PHONE", "value": "0773943709", "sources": _src("Tel: 0773 943 709")}]}
    with patch("apps.proit.ai_research.research_conversation", return_value=(raw, {URL}, USAGE)) as conv:
        cf.run_search(run.pk)
    run.refresh_from_db()
    assert run.status == ContactSearchStatus.DONE and run.tokens_in == 2000 and run.searches_used == 2
    assert run.proposals.count() == 1 and main_case.respondents.count() == 0  # the AI only proposes
    kwargs = conv.call_args.kwargs
    assert kwargs["tool"]["name"] == "record_contacts" and "Test Organisation" in kwargs["prompt"]
    event = AuditEvent.objects.get(action="contacts.search_completed")
    assert event.metadata["provider"] == "meta" and event.metadata["tokens_in"] == 2000


def test_with_meta_the_search_uses_only_the_proit_meta_key_never_the_anthropic_one(main_case, settings):
    _meta(settings)
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    run = cf.start_search(main_case, user=_user())
    with patch("apps.proit.muse.search_conversation", return_value=({"summary": "", "contacts": []}, set(), USAGE, [])) as muse_call, \
            patch("anthropic.Anthropic") as anthropic_cls:
        cf.run_search(run.pk)
    assert muse_call.call_args.kwargs["key"] == "meta-key"
    anthropic_cls.assert_not_called()


def test_a_failed_search_is_recorded_not_left_running(main_case, settings):
    from apps.proit.ai_research import AIResearchError

    _meta(settings)
    run = cf.start_search(main_case, user=_user())
    with patch("apps.proit.ai_research.research_conversation", side_effect=AIResearchError("ai_request_failed", "Meta said no", 502)):
        cf.run_search(run.pk)
    run.refresh_from_db()
    assert run.status == ContactSearchStatus.FAILED and "Meta said no" in run.error


# --- Batches -----------------------------------------------------------------------------------------------------

def _case(organisation, stratum, **fields):
    case = create_sample_case(organisation=organisation, stratum=stratum, sample_type=SampleType.MAIN, year=2026)
    for key, value in fields.items():
        setattr(case, key, value)
    if fields:
        case.save(update_fields=list(fields))
    return case


def test_a_batch_picks_only_not_yet_invited_invitable_cases_still_without_contacts(
    main_case, organisation, stratum, locked_reserve_case,
):
    with_phone = _case(organisation, stratum)
    Respondent.objects.create(sample_case=with_phone, full_name="Someone", phone="0773943709")
    invited = _case(organisation, stratum, workflow_status="S05")
    searched_recently = _case(organisation, stratum)
    ContactSearchRun.objects.create(sample_case=searched_recently, status=ContactSearchStatus.DONE)
    failed_recently = _case(organisation, stratum)
    ContactSearchRun.objects.create(sample_case=failed_recently, status=ContactSearchStatus.FAILED)
    searched_long_ago = _case(organisation, stratum)
    old = ContactSearchRun.objects.create(sample_case=searched_long_ago, status=ContactSearchStatus.DONE)
    ContactSearchRun.objects.filter(pk=old.pk).update(started_at=timezone.now() - timedelta(days=31))
    name_only = _case(organisation, stratum)
    Respondent.objects.create(sample_case=name_only, full_name="Name but no contact")

    picked = set(cf.cases_without_contacts().values_list("sample_id", flat=True))
    assert picked == {main_case.sample_id, failed_recently.sample_id, searched_long_ago.sample_id, name_only.sample_id}
    assert not picked & {with_phone.sample_id, invited.sample_id, searched_recently.sample_id, locked_reserve_case.sample_id}


def test_a_batch_respects_the_cap_and_queues_one_search_per_case(main_case, organisation, stratum, settings, django_capture_on_commit_callbacks):
    _meta(settings)
    settings.CONTACT_FINDER_BATCH_MAX = 2
    _case(organisation, stratum)
    _case(organisation, stratum)
    coordinator = _client("FIELD_COORDINATOR", "cf_fc_batch")
    batch = "/api/v1/contacts/contact-search/batch/"
    assert coordinator.get(batch).data["without_contacts"] == 3
    with patch(BATCH_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        too_many = coordinator.post(batch, {"limit": 3}, format="json")
        ok = coordinator.post(batch, {"limit": 2}, format="json")
    assert too_many.status_code == 400 and too_many.data["error"]["code"] == "bad_limit"
    assert ok.status_code == 202 and ok.data["queued"] == 2 and delay.call_count == 2
    assert ok.data["without_contacts"] == 1  # the two just queued now count as searched
    assert _client("CONTACT_RA", "cf_cra_batch").post(batch, {"limit": 1}, format="json").status_code == 403


# --- The research lane: one search at a time, without holding up anything else ------------------------------------

def test_searches_have_their_own_queue_and_everything_else_stays_on_the_default_one():
    from config.celery import app

    route = app.amqp.router.route({}, "apps.contacts.tasks.search_contacts")
    assert route["queue"].name == "research"
    assert app.amqp.router.route({}, "apps.kobo.tasks.reconcile_kobo_submissions")["queue"].name == "celery"


def test_a_leftover_search_in_the_default_queue_is_handed_to_the_research_lane_not_run_there(main_case, settings):
    # Searches queued before the lane existed sit in the default queue; running them there is what held up the
    # Kobo sync for an hour on 2026-10-04.
    from apps.contacts.tasks import search_contacts

    _meta(settings)
    run = cf.start_search(main_case, user=_user())
    for queue, handed_over in (("celery", True), ("research", False)):
        search_contacts.push_request(delivery_info={"routing_key": queue})
        try:
            with patch.object(search_contacts, "apply_async") as apply_async, patch("apps.contacts.tasks.run_search") as run_search:
                search_contacts.run(run.pk)
        finally:
            search_contacts.pop_request()
        if handed_over:
            apply_async.assert_called_once_with(args=[run.pk], queue="research")
            run_search.assert_not_called()
        else:
            apply_async.assert_not_called()
            run_search.assert_called_once_with(run.pk)


def test_a_new_search_waits_queued_and_only_the_worker_marks_it_running(main_case, settings):
    _meta(settings)
    run = cf.start_search(main_case, user=_user())
    assert run.status == ContactSearchStatus.QUEUED and run.running_since is None
    seen = {}

    def conversation(**kwargs):
        seen["status"] = ContactSearchRun.objects.get(pk=run.pk).status
        return {"summary": "", "contacts": []}, set(), USAGE

    with patch("apps.proit.ai_research.research_conversation", side_effect=conversation):
        cf.run_search(run.pk)
    run.refresh_from_db()
    assert seen["status"] == ContactSearchStatus.RUNNING
    assert run.status == ContactSearchStatus.DONE and run.running_since is not None


def test_a_search_delivered_twice_or_already_closed_never_searches_again(main_case, settings):
    _meta(settings)
    for status in (ContactSearchStatus.RUNNING, ContactSearchStatus.DONE, ContactSearchStatus.FAILED):
        run = ContactSearchRun.objects.create(sample_case=main_case, status=status)
        with patch("apps.proit.ai_research.research_conversation") as conv:
            cf.run_search(run.pk)
        conv.assert_not_called()
        run.refresh_from_db()
        assert run.status == status


def test_lost_searches_are_closed_so_they_stop_blocking_the_case(main_case, organisation, stratum, settings):
    _meta(settings)
    now = timezone.now()
    lost = ContactSearchRun.objects.create(sample_case=main_case, status=ContactSearchStatus.QUEUED)
    ContactSearchRun.objects.filter(pk=lost.pk).update(started_at=now - timedelta(hours=4))
    stuck = ContactSearchRun.objects.create(
        sample_case=_case(organisation, stratum), status=ContactSearchStatus.RUNNING, running_since=now - timedelta(minutes=25),
    )
    waiting = ContactSearchRun.objects.create(sample_case=_case(organisation, stratum), status=ContactSearchStatus.QUEUED)
    working = ContactSearchRun.objects.create(
        sample_case=_case(organisation, stratum), status=ContactSearchStatus.RUNNING, running_since=now - timedelta(minutes=2),
    )

    assert cf.expire_stale_runs() == 2
    for run, status in ((lost, "FAILED"), (stuck, "FAILED"), (waiting, "QUEUED"), (working, "RUNNING")):
        run.refresh_from_db()
        assert run.status == status
    assert "Interrupted" in lost.error
    assert cf.start_search(main_case, user=_user()).status == ContactSearchStatus.QUEUED  # no longer blocked
    with pytest.raises(cf.ContactFinderError) as refused:
        cf.start_search(waiting.sample_case, user=_user("FIELD_COORDINATOR", "cf_fc_wait"))
    assert refused.value.code == "already_running"


def test_the_case_page_says_how_many_searches_are_ahead(main_case, organisation, stratum, settings):
    _meta(settings)
    ContactSearchRun.objects.create(
        sample_case=_case(organisation, stratum), status=ContactSearchStatus.RUNNING, running_since=timezone.now(),
    )
    first = ContactSearchRun.objects.create(sample_case=_case(organisation, stratum), status=ContactSearchStatus.QUEUED)
    mine = cf.start_search(main_case, user=_user())
    assert cf.queue_position(first) == 1 and cf.queue_position(mine) == 2
    data = _client("FIELD_COORDINATOR", "cf_fc_pos").get(f"/api/v1/contacts/{main_case.sample_id}/contact-search/").data
    assert data["run"]["status"] == "QUEUED" and data["run"]["queue_position"] == 2
    ContactSearchRun.objects.filter(pk=mine.pk).update(status=ContactSearchStatus.RUNNING)
    mine.refresh_from_db()
    assert cf.queue_position(mine) is None


def test_a_second_batch_is_refused_while_one_runs_but_a_single_case_search_is_not(main_case, organisation, stratum, settings):
    _meta(settings)
    _case(organisation, stratum)
    other = _case(organisation, stratum)
    coordinator = _client("FIELD_COORDINATOR", "cf_fc_twice")
    batch = "/api/v1/contacts/contact-search/batch/"
    with patch(DELAY), patch(BATCH_DELAY):
        first = coordinator.post(batch, {"limit": 1}, format="json")
        second = coordinator.post(batch, {"limit": 1}, format="json")
        single = coordinator.post(f"/api/v1/contacts/{other.sample_id}/contact-search/")
    assert first.status_code == 202 and first.data["queued"] == 1
    assert second.status_code == 409 and second.data["error"]["code"] == "batch_running"
    assert single.status_code == 202
    ContactSearchRun.objects.exclude(batch="").update(status=ContactSearchStatus.DONE)
    with patch(BATCH_DELAY):
        assert coordinator.post(batch, {"limit": 1}, format="json").status_code == 202


def test_the_register_shows_batch_progress_and_every_case_with_findings_to_review(main_case, organisation, stratum, settings):
    _meta(settings)
    _case(organisation, stratum)
    with patch(BATCH_DELAY):
        assert _client("FIELD_COORDINATOR", "cf_fc_prog").post(
            "/api/v1/contacts/contact-search/batch/", {"limit": 2}, format="json").status_code == 202
    done, waiting = ContactSearchRun.objects.exclude(batch="").order_by("sample_case__sample_id")
    ContactSearchRun.objects.filter(pk=done.pk).update(status=ContactSearchStatus.DONE)
    for status in (ContactProposalStatus.PROPOSED, ContactProposalStatus.PROPOSED, ContactProposalStatus.ACCEPTED):
        ContactProposal.objects.create(run=done, sample_case=done.sample_case, kind="ORG_PHONE", value="0773943709", status=status)
    ContactProposal.objects.create(
        run=waiting, sample_case=waiting.sample_case, kind="ORG_PHONE", value="0773000111", status=ContactProposalStatus.REJECTED,
    )

    data = _client("FIELD_COORDINATOR", "cf_fc_prog2").get("/api/v1/contacts/contact-search/batch/").data
    progress = data["progress"]
    assert (progress["total"], progress["done"], progress["queued"], progress["active"]) == (2, 1, 1, True)
    assert data["to_review_total"] == 1
    assert data["to_review"] == [
        {"sample_id": done.sample_case.sample_id, "organisation": done.sample_case.organisation.name, "findings": 2},
    ]


def test_the_migration_marks_searches_still_waiting_as_queued_and_groups_them(main_case, organisation, stratum):
    import importlib

    from django.apps import apps as django_apps

    migration = importlib.import_module("apps.contacts.migrations.0005_contact_search_queue")
    waiting = ContactSearchRun.objects.create(sample_case=main_case, status=ContactSearchStatus.RUNNING)
    finished = ContactSearchRun.objects.create(
        sample_case=_case(organisation, stratum), status=ContactSearchStatus.DONE, finished_at=timezone.now(),
    )
    migration.mark_waiting_runs_queued(django_apps, None)
    waiting.refresh_from_db()
    finished.refresh_from_db()
    assert waiting.status == ContactSearchStatus.QUEUED and waiting.batch == "queued-before-research-lane"
    assert finished.status == ContactSearchStatus.DONE and finished.batch == ""


# --- The review page: every waiting finding in one place -------------------------------------------------------

REVIEW = "/api/v1/contacts/contact-proposals/review/"


def _finding(case, kind="ORG_PHONE", value="0773943709", confidence="HIGH", url=URL, status=ContactProposalStatus.PROPOSED):
    run = case.contact_searches.first() or ContactSearchRun.objects.create(sample_case=case, status=ContactSearchStatus.DONE)
    return ContactProposal.objects.create(
        run=run, sample_case=case, kind=kind, value=value, confidence=confidence, status=status,
        sources=[{"title": "Listing", "url": url, "quote": f"Contact {value}"}],
    )


def test_the_review_page_lists_only_waiting_findings_grouped_by_case_in_sample_id_order(main_case, organisation, stratum):
    later = _case(organisation, stratum)
    _finding(later, kind="ORG_EMAIL", value="info@testorg.co.zw")
    _finding(main_case)
    _finding(main_case, kind="WEBSITE", value="https://www.testorg.co.zw")
    _finding(main_case, value="0772000111", status=ContactProposalStatus.REJECTED)
    _finding(later, value="0773000222", status=ContactProposalStatus.ACCEPTED)

    data = _client("FIELD_COORDINATOR", "cf_rev_fc").get(REVIEW).data
    assert [c["sample_id"] for c in data["cases"]] == sorted([main_case.sample_id, later.sample_id])
    by_case = {c["sample_id"]: [p["kind"] for p in c["proposals"]] for c in data["cases"]}
    assert by_case == {main_case.sample_id: ["ORG_PHONE", "WEBSITE"], later.sample_id: ["ORG_EMAIL"]}
    assert data["total_waiting"] == 3 and data["total_shown"] == 3
    assert data["cases"][0]["proposals"][0]["site"] == "testorg.co.zw"  # www. dropped
    assert data["cases"][0]["proposals"][0]["sources"][0]["quote"].startswith("Contact")


def test_the_filters_narrow_the_list_while_the_counts_cover_everything_waiting(main_case, organisation, stratum):
    other = _case(organisation, stratum)
    _finding(main_case, confidence="HIGH")
    _finding(main_case, kind="OFFICE_LOCATION", value="Harare", confidence="HIGH")
    _finding(other, kind="ORG_EMAIL", value="a@b.co.zw", confidence="LOW", url="https://www.findglocal.com/x")
    client = _client("FIELD_COORDINATOR", "cf_rev_filter")

    phones_emails = client.get(REVIEW, {"kind": "ORG_PHONE,ORG_EMAIL"}).data
    assert phones_emails["total_shown"] == 2 and phones_emails["total_waiting"] == 3
    assert phones_emails["facets"]["kind"] == {"ORG_PHONE": 1, "OFFICE_LOCATION": 1, "ORG_EMAIL": 1}
    high = client.get(REVIEW, {"kind": "ORG_PHONE,ORG_EMAIL", "confidence": "HIGH"}).data
    assert [p["kind"] for c in high["cases"] for p in c["proposals"]] == ["ORG_PHONE"]
    site = client.get(REVIEW, {"site": "findglocal.com"}).data
    assert [c["sample_id"] for c in site["cases"]] == [other.sample_id]
    assert ("findglocal.com", 1) in [tuple(row) for row in site["facets"]["site"]]
    assert client.get(REVIEW, {"kind": "NOT_A_KIND"}).data["total_shown"] == 3  # unknown values are ignored


def test_the_review_page_shows_the_contact_an_accept_would_sit_beside(main_case):
    Respondent.objects.create(sample_case=main_case, full_name=cf.PLACEHOLDER_NAME, phone="0773943709")
    _finding(main_case, value="0772000111")
    case = _client("FIELD_COORDINATOR", "cf_rev_cur").get(REVIEW).data["cases"][0]
    assert case["current"] == {"phone": "0773943709", "email": ""}


def test_the_review_page_pages_by_case(main_case, organisation, stratum):
    from apps.contacts import finder_views

    cases = [main_case] + [_case(organisation, stratum) for _ in range(finder_views.REVIEW_PAGE_CASES)]
    for case in cases:
        _finding(case)
    client = _client("FIELD_COORDINATOR", "cf_rev_page")
    first, second = client.get(REVIEW).data, client.get(REVIEW, {"page": 2}).data
    assert (first["pages"], len(first["cases"]), len(second["cases"])) == (2, finder_views.REVIEW_PAGE_CASES, 1)
    assert first["total_cases"] == len(cases)
    assert {c["sample_id"] for c in first["cases"]}.isdisjoint({c["sample_id"] for c in second["cases"]})


def test_only_the_pi_and_coordinator_review_and_the_supervisor_may_read(main_case):
    _finding(main_case)
    assert _client("PI_ADMIN", "cf_rev_pi").get(REVIEW).status_code == 200
    assert _client("SUPERVISOR_READONLY", "cf_rev_sup").get(REVIEW).status_code == 200
    assert _client("CONTACT_RA", "cf_rev_cra").get(REVIEW).status_code == 403
    assert APIClient().get(REVIEW).status_code in (401, 403)


# --- A batch is all or nothing -----------------------------------------------------------------------------------

def test_a_batch_queues_its_searches_only_once_they_are_saved(main_case, organisation, stratum, settings, django_capture_on_commit_callbacks):
    _meta(settings)
    _case(organisation, stratum)
    with patch(BATCH_DELAY) as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            runs = cf.start_batch(2, user=_user())
        delay.assert_not_called()  # nothing is queued before the runs are committed
        for callback in callbacks:
            callback()
    assert sorted(call.args[0] for call in delay.call_args_list) == sorted(run.pk for run in runs)


def test_a_batch_that_fails_part_way_leaves_nothing_behind(main_case, organisation, stratum, settings, django_capture_on_commit_callbacks):
    # 2026-10-04: a failure after the runs were created left 25 cases "waiting" for tasks never sent.
    _meta(settings)
    _case(organisation, stratum)
    real_log = cf.log_action

    def failing_log(action, *args, **kwargs):
        if action == "contacts.batch_started":
            raise RuntimeError("audit write failed")
        return real_log(action, *args, **kwargs)

    with patch(BATCH_DELAY) as delay, patch("apps.contacts.contact_finder.log_action", side_effect=failing_log),             django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            cf.start_batch(2, user=_user())
    assert ContactSearchRun.objects.count() == 0
    assert not AuditEvent.objects.filter(action="contacts.search_started").exists()
    delay.assert_not_called()


def test_a_batch_started_with_nobody_signed_in_is_audited_against_its_first_run(main_case, settings, django_capture_on_commit_callbacks):
    _meta(settings)
    with patch(BATCH_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        runs = cf.start_batch(1, user=None)
    event = AuditEvent.objects.get(action="contacts.batch_started")
    assert event.user_id is None and event.object_type == "ContactSearchRun" and event.object_id == str(runs[0].pk)
    assert event.metadata["batch"] == runs[0].batch and event.metadata["queued"] == 1
    delay.assert_called_once_with(runs[0].pk)
