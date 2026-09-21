"""
PROIT AI desk research (apps/proit/ai_research.py) and the interview-side verification and reconciliation
it feeds. The web search and the model are mocked: what is under test is that the server never trusts the
AI (only URLs the search returned, nothing private, nothing without a source), that a researcher decides
what enters the profile, and that a case cannot count as complete until its profile is reconciled.
"""

from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.kii.models import CodingStatus
from apps.kii.services import InvalidKIITransition, advance_coding_status, create_kii_record
from apps.proit.ai_research import ai_fields, call_model, case_context, clean_findings
from apps.proit.models import (
    AIProposal,
    AIResearchRun,
    AIResearchStatus,
    PreProfile,
    ReconciliationStatus,
)
from apps.proit.services import (
    add_evidence,
    add_field,
    create_pre_profile,
    lock_pre_profile,
    reconciliation_blocker,
    reconciliation_state,
)

FIELDS = ai_fields()
URL = "https://www.example.co.zw/about-us"


def _client(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role))
    return client


def _found(field_id="legal_name", value="Test Organisation (Pvt) Ltd, registered in Harare.", url=URL, **extra):
    return {
        "field_id": field_id, "status": "found", "value": value, "confidence": "HIGH", "notes": "",
        "sources": [{"title": "About us", "url": url, "publisher": "Test Organisation", "published": "2025-03-01",
                     "quote": "Test Organisation (Pvt) Ltd", "authority": "TIER_2_INSTITUTIONAL"}], **extra,
    }


# --- The server never trusts the AI ------------------------------------------------------------------

def test_the_ai_can_only_propose_descriptive_fields_never_identity_or_study_items():
    assert "respondent_name" not in FIELDS and "organisation_selected" not in FIELDS
    assert {"legal_name", "job_title", "public_finance_facilities"} <= set(FIELDS)


def test_a_source_the_search_never_returned_is_dropped_and_the_fact_becomes_not_found():
    proposals, dropped = clean_findings({"findings": [_found(url="https://made-up.example/page")]}, {URL}, FIELDS)
    p = next(p for p in proposals if p["field_id"] == "legal_name")
    assert p["status"] == "not_found" and p["value"] == "" and p["sources"] == []
    assert any(d["reason"] == "url was not returned by the search" for d in dropped)


def test_a_real_source_is_kept_and_a_single_non_statutory_source_is_capped_at_moderate():
    proposals, dropped = clean_findings({"findings": [_found()]}, {URL}, FIELDS)
    p = next(p for p in proposals if p["field_id"] == "legal_name")
    assert p["status"] == "found" and p["sources"][0]["url"] == URL and not dropped
    assert p["confidence"] == "MODERATE"  # the model said HIGH on one institutional source


def test_personal_and_social_pages_are_never_a_source():
    finding = _found(url="https://www.linkedin.com/in/some-person")
    proposals, dropped = clean_findings({"findings": [finding]}, {"https://www.linkedin.com/in/some-person"}, FIELDS)
    assert next(p for p in proposals if p["field_id"] == "legal_name")["status"] == "not_found"
    assert any("personal or social" in d["reason"] for d in dropped)


@pytest.mark.parametrize("value", [
    "He is a member of the ZANU party.", "Treated for cancer in 2019.", "Call the owner on +263 77 123 4567.",
    "Email the director at someone@example.com.", "Lives at his home address in Borrowdale.",
])
def test_anything_that_reads_as_private_is_removed(value):
    proposals, dropped = clean_findings({"findings": [_found(field_id="public_professional_experience", value=value)]}, {URL}, FIELDS)
    p = next(p for p in proposals if p["field_id"] == "public_professional_experience")
    assert p["status"] == "not_found" and p["value"] == ""
    assert any("private" in d["reason"] for d in dropped)


def test_unknown_fields_are_ignored_duplicates_dedupe_and_skipped_fields_are_not_found():
    raw = {"findings": [_found(), _found(value="A second answer for the same field."),
                        {"field_id": "NFM1", "status": "found", "value": "x", "confidence": "HIGH", "sources": []}]}
    proposals, _ = clean_findings(raw, {URL}, FIELDS)
    assert [p["field_id"] for p in proposals].count("legal_name") == 1
    assert "NFM1" not in {p["field_id"] for p in proposals}  # a study construct item can never be proposed
    assert {p["field_id"] for p in proposals} == set(FIELDS)  # every allowed field has an answer, if only "not found"
    assert next(p for p in proposals if p["field_id"] == "trading_name")["status"] == "not_found"


def test_an_ambiguous_organisation_is_low_confidence_for_the_researcher_to_judge():
    finding = _found(status="ambiguous", notes="Two companies share this name.")
    proposals, _ = clean_findings({"findings": [finding]}, {URL}, FIELDS)
    p = next(p for p in proposals if p["field_id"] == "legal_name")
    assert p["status"] == "ambiguous" and p["confidence"] == "LOW"


# --- Talking to the model ----------------------------------------------------------------------------

def _response(content, stop_reason, searches=0):
    usage = Mock(input_tokens=1000, output_tokens=200, server_tool_use=Mock(web_search_requests=searches))
    return Mock(content=content, stop_reason=stop_reason, usage=usage)


def _search_block(*urls):
    return Mock(type="web_search_tool_result", content=[Mock(url=u, title="t") for u in urls])


def test_the_search_conversation_continues_through_a_pause_and_collects_the_urls_it_returned(main_case, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    findings = Mock(type="tool_use", input={"summary": "Found it.", "findings": [_found(fid) for fid in list(FIELDS)[:20]]})
    findings.name = "record_findings"
    first = _response([_search_block(URL, "https://other.example/x")], "pause_turn", searches=3)
    second = _response([findings], "tool_use", searches=2)
    with patch("anthropic.Anthropic") as client_cls:
        stream = client_cls.return_value.messages.stream
        stream.return_value.__enter__.return_value.get_final_message.side_effect = [first, second]
        raw, seen, usage = call_model({"organisation": {"name": "Test Organisation"}, "person": {}}, FIELDS)
        tools = stream.call_args.kwargs["tools"]
        sent = stream.call_args.kwargs
    assert sent["model"] == "claude-sonnet-5"  # PROIT research runs on the cheaper model
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}  # the prompt is cached across the search turns
    assert raw["summary"] == "Found it." and seen == {URL, "https://other.example/x"}
    assert usage == {"in": 2000, "out": 400, "searches": 5, "cache_read": 0, "cache_write": 0}
    assert tools[0]["name"] == "web_search" and "facebook.com" in tools[0]["blocked_domains"]  # social pages are excluded up front
    assert stream.call_count == 2


def test_the_prompt_carries_only_what_is_needed_never_contact_details(main_case):
    from apps.contacts.models import Respondent

    Respondent.objects.create(sample_case=main_case, full_name="Chipo Moyo", phone="0771234567", email="c@example.com",
                              whatsapp_number="0771234567", is_eligible=True, role_category="OWNER_FOUNDER")
    profile = create_pre_profile(sample_case=main_case)
    context = case_context(profile)
    from apps.proit.ai_research import build_prompt

    text = build_prompt(context, FIELDS)
    assert "Test Organisation" in text and "Chipo Moyo" in text and "Owner/founder" in text
    assert "0771234567" not in text and "c@example.com" not in text


# --- The run, and what the researcher does with it ---------------------------------------------------

@pytest.fixture
def profile(main_case):
    return create_pre_profile(sample_case=main_case)


def _run_ai(client, profile, settings, findings=None):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    raw = {"summary": "Looked at the company site.", "findings": findings if findings is not None else [_found()]}
    with patch("apps.proit.ai_research.call_model", return_value=(raw, {URL}, {"in": 1000, "out": 100, "searches": 4})):
        return client.post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/")


def test_a_research_run_records_proposals_and_puts_nothing_in_the_profile(profile, settings):
    coordinator = _client(Role.FIELD_COORDINATOR, "ai_fc")
    resp = _run_ai(coordinator, profile, settings)
    assert resp.status_code == 202
    run = AIResearchRun.objects.get(pk=resp.data["id"])
    assert run.status == AIResearchStatus.DONE and run.searches_used == 4 and run.summary.startswith("Looked at")
    assert profile.fields.count() == 0  # the AI only proposes
    body = coordinator.get(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/").json()
    by_field = {p["field_id"]: p for p in body["proposals"]}
    assert by_field["legal_name"]["status"] == "PROPOSED" and by_field["legal_name"]["sources"][0]["url"] == URL
    assert by_field["trading_name"]["status"] == "NOT_FOUND"  # what to ask the respondent about
    assert AuditEvent.objects.filter(action="proit.ai_research_completed").exists()


def test_research_is_refused_up_front_when_ai_is_off_the_profile_is_locked_or_it_is_already_running(profile, settings):
    coordinator = _client(Role.FIELD_COORDINATOR, "ai_fc2")
    settings.ANTHROPIC_API_KEY = ""
    assert coordinator.post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/").status_code == 503
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    AIResearchRun.objects.create(pre_profile=profile, status=AIResearchStatus.RUNNING)
    assert coordinator.post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/").status_code == 409
    AIResearchRun.objects.all().delete()
    field = add_field(profile, "legal_name", documentary_value="Test Organisation")
    add_evidence(field, source_title="Registry", source_confidence="HIGH")
    lock_pre_profile(profile, reviewer=User.objects.first())
    locked = coordinator.post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/")
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "locked"


def test_only_the_coordinator_and_pi_may_run_or_decide_ai_research(profile, settings):
    resp = _run_ai(_client(Role.CONTACT_RA, "ai_cra"), profile, settings)
    assert resp.status_code == 403
    assert _client(Role.SUPERVISOR_READONLY, "ai_sup").post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/").status_code == 403


def test_a_failed_search_is_recorded_not_left_running(profile, settings):
    from apps.proit.ai_research import AIResearchError

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    with patch("apps.proit.ai_research.call_model", side_effect=AIResearchError("ai_request_failed", "down", 502)):
        resp = _client(Role.FIELD_COORDINATOR, "ai_fc3").post(f"/api/v1/proit/pre-profiles/{profile.pk}/ai-research/")
    run = AIResearchRun.objects.get(pk=resp.data["id"])
    assert run.status == AIResearchStatus.FAILED and run.error == "down"


def test_accepting_a_finding_creates_the_field_with_its_source_and_it_still_needs_the_lock(profile, settings):
    coordinator = _client(Role.FIELD_COORDINATOR, "ai_fc4")
    _run_ai(coordinator, profile, settings)
    proposal = AIProposal.objects.get(pre_profile=profile, field_id="legal_name")
    resp = coordinator.post(f"/api/v1/proit/ai-proposals/{proposal.pk}/accept/", {}, format="json")
    assert resp.status_code == 200 and resp.json()["status"] == "ACCEPTED"
    field = profile.fields.get(field_id="legal_name")
    assert field.preliminary_documentary_value.startswith("Test Organisation (Pvt) Ltd")
    source = field.sources.get()
    assert source.locator == URL and source.source_type == "WEB" and str(source.source_date) == "2025-03-01"
    assert "AI-found; researcher accepted" in source.researcher_notes and "Test Organisation (Pvt) Ltd" in source.researcher_notes
    assert field.confidence in ("MODERATE", "HIGH")
    assert profile.prepopulation_locked_at is None  # accepting is not locking
    assert coordinator.post(f"/api/v1/proit/ai-proposals/{proposal.pk}/accept/", {}, format="json").status_code == 400  # not twice


def test_an_edited_value_is_recorded_as_edited_and_a_rejection_adds_nothing(profile, settings):
    coordinator = _client(Role.FIELD_COORDINATOR, "ai_fc5")
    _run_ai(coordinator, profile, settings, findings=[_found(), _found("hq_province", "Harare Province.")])
    a = AIProposal.objects.get(pre_profile=profile, field_id="legal_name")
    b = AIProposal.objects.get(pre_profile=profile, field_id="hq_province")
    edited = coordinator.post(f"/api/v1/proit/ai-proposals/{a.pk}/accept/", {"value": "Test Organisation (Private) Limited"}, format="json")
    assert edited.json()["status"] == "EDITED" and edited.json()["final_value"] == "Test Organisation (Private) Limited"
    rejected = coordinator.post(f"/api/v1/proit/ai-proposals/{b.pk}/reject/", {"reason": "wrong company"}, format="json")
    assert rejected.json()["status"] == "REJECTED" and not profile.fields.filter(field_id="hq_province").exists()


def test_a_not_found_field_cannot_be_accepted_and_nothing_is_accepted_after_the_lock(profile, settings):
    coordinator = _client(Role.FIELD_COORDINATOR, "ai_fc6")
    _run_ai(coordinator, profile, settings)
    nf = AIProposal.objects.get(pre_profile=profile, field_id="trading_name")
    assert coordinator.post(f"/api/v1/proit/ai-proposals/{nf.pk}/accept/", {"value": "invented"}, format="json").status_code == 400
    found = AIProposal.objects.get(pre_profile=profile, field_id="legal_name")
    field = add_field(profile, "legal_name", documentary_value="typed by hand")
    add_evidence(field, source_title="Registry", source_confidence="HIGH")
    lock_pre_profile(profile, reviewer=User.objects.first())
    assert coordinator.post(f"/api/v1/proit/ai-proposals/{found.pk}/accept/", {}, format="json").status_code == 409


# --- Verification with the respondent, and reconciliation after ---------------------------------------

def _locked_profile(main_case, values=(("legal_name", "Test Organisation"), ("hq_province", "Harare"))):
    profile = create_pre_profile(sample_case=main_case)
    for fid, value in values:
        field = add_field(profile, fid, documentary_value=value)
        add_evidence(field, source_title="Registry entry", source_confidence="HIGH", source_authority="TIER_1_STATUTORY",
                     source_type="WEB", locator="https://registry.example/x")
    lock_pre_profile(profile, reviewer=User.objects.create_user(username=f"rev{profile.pk}", password="x"))
    return profile


def test_the_interview_sheet_shows_only_a_locked_profile_and_never_states_a_low_confidence_fact(main_case):
    profile = create_pre_profile(sample_case=main_case)
    add_field(profile, "legal_name", documentary_value="Test Organisation")  # no source yet
    coordinator = _client(Role.FIELD_COORDINATOR, "iv_fc")
    assert coordinator.get(f"/api/v1/proit/interview-sheet/?sample_case={main_case.pk}").json()["locked"] is False
    profile.delete()

    profile = _locked_profile(main_case)
    weak = add_field.__globals__["PreProfileField"].objects.filter(pre_profile=profile, field_id="hq_province").update(confidence="LOW")
    assert weak == 1
    sheet = coordinator.get(f"/api/v1/proit/interview-sheet/?sample_case={main_case.pk}").json()["profile"]
    by_id = {f["field_id"]: f for f in sheet["fields"]}
    assert by_id["legal_name"]["documentary_value"] == "Test Organisation" and by_id["legal_name"]["sources"][0]["url"]
    assert by_id["hq_province"]["documentary_value"] == "" and by_id["hq_province"]["withheld_low_confidence"] is True


def test_an_interviewer_verifies_each_fact_and_a_correction_never_erases_the_documentary_value(main_case):
    profile = _locked_profile(main_case)
    fc = _client(Role.FIELD_COORDINATOR, "iv_fc2")
    legal, hq = profile.fields.get(field_id="legal_name"), profile.fields.get(field_id="hq_province")
    ok = fc.post(f"/api/v1/proit/fields/{legal.pk}/verify/", {"status": "YES_CORRECT"}, format="json")
    assert ok.status_code == 200 and ok.json()["settled"] is True  # a plain confirmation needs no further coding
    fixed = fc.post(f"/api/v1/proit/fields/{hq.pk}/verify/", {"status": "NO_CORRECT_VALUE_PROVIDED", "respondent_value": "Mashonaland East"}, format="json")
    assert fixed.json()["settled"] is False  # corrected: a researcher must still record the reconciled value
    hq.refresh_from_db()
    assert hq.preliminary_documentary_value == "Harare" and hq.respondent_value == "Mashonaland East"
    assert fc.post(f"/api/v1/proit/fields/{hq.pk}/verify/", {"status": "MADE_UP"}, format="json").status_code == 400


def test_verification_is_refused_before_the_lock(main_case):
    profile = create_pre_profile(sample_case=main_case)
    field = add_field(profile, "legal_name", documentary_value="x")
    resp = _client(Role.FIELD_COORDINATOR, "iv_fc3").post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json")
    assert resp.status_code == 409


def test_a_contact_ra_reaches_only_the_profile_of_a_case_assigned_to_them_and_a_kii_ra_only_kii_profiles(main_case):
    profile = _locked_profile(main_case)
    field = profile.fields.first()
    cra = _client(Role.CONTACT_RA, "iv_cra")
    assert cra.get(f"/api/v1/proit/interview-sheet/?sample_case={main_case.pk}").status_code == 404  # not assigned
    assert cra.post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json").status_code == 404
    main_case.assigned_ra = User.objects.get(username="iv_cra")
    main_case.save()
    assert cra.get(f"/api/v1/proit/interview-sheet/?sample_case={main_case.pk}").status_code == 200
    assert cra.post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json").status_code == 200
    kii_ra = _client(Role.KII_RA, "iv_kii")
    assert kii_ra.post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json").status_code == 404
    assert _client(Role.QA if hasattr(Role, "QA") else Role.QUAN_QA_RA, "iv_qa").get(f"/api/v1/proit/interview-sheet/?sample_case={main_case.pk}").status_code == 403


def test_reconciling_needs_a_verification_first_and_then_completes_the_profile(main_case):
    profile = _locked_profile(main_case)
    fc = _client(Role.FIELD_COORDINATOR, "iv_fc4")
    legal, hq = profile.fields.get(field_id="legal_name"), profile.fields.get(field_id="hq_province")
    assert fc.post(f"/api/v1/proit/fields/{hq.pk}/reconcile/", {"reconciled_value": "Harare"}, format="json").status_code == 409
    fc.post(f"/api/v1/proit/fields/{legal.pk}/verify/", {"status": "YES_CORRECT"}, format="json")
    fc.post(f"/api/v1/proit/fields/{hq.pk}/verify/", {"status": "PARTLY_CORRECT", "respondent_value": "Harare and Marondera"}, format="json")
    state = reconciliation_state(profile)
    assert not state["complete"] and state["pending_reconciliation"] == [hq.id]
    assert fc.post(f"/api/v1/proit/fields/{hq.pk}/reconcile/", {"reconciled_value": ""}, format="json").status_code == 400
    assert fc.post(f"/api/v1/proit/fields/{hq.pk}/reconcile/", {"reconciled_value": "Harare (head office); also Marondera"}, format="json").status_code == 200
    profile.refresh_from_db()
    assert reconciliation_state(profile)["complete"] and profile.reconciliation_status == ReconciliationStatus.RECONCILED
    # the three values stay separate
    hq.refresh_from_db()
    assert (hq.preliminary_documentary_value, hq.respondent_value, hq.reconciled_value) == (
        "Harare", "Harare and Marondera", "Harare (head office); also Marondera")


def test_a_plain_patch_cannot_mark_a_profile_reconciled_or_completed(main_case):
    profile = _locked_profile(main_case)
    fc = _client(Role.FIELD_COORDINATOR, "iv_fc5")
    fc.patch(f"/api/v1/proit/pre-profiles/{profile.pk}/", {"reconciliation_status": "RECONCILED", "protocol_deviation": True,
                                                            "interview_completed_at": timezone.now().isoformat()}, format="json")
    profile.refresh_from_db()
    assert profile.reconciliation_status == ReconciliationStatus.PENDING and not profile.protocol_deviation
    assert profile.interview_completed_at is None


# --- A case is not complete until its profile is reconciled -------------------------------------------

def _submission(main_case):
    from apps.kobo.models import AdministrationMode, QAStatus, QUANSubmission

    return QUANSubmission.objects.create(
        sample_case=main_case, kobo_submission_uuid="uuid-gate", administration_mode=AdministrationMode.WEB_SELF,
        submitted_at=timezone.now(), completion_seconds=1500, raw_payload_ref="", qa_status=QAStatus.PENDING,
    )


def test_qa_cannot_accept_a_questionnaire_until_the_pre_interview_profile_is_reconciled(main_case):
    profile = _locked_profile(main_case)
    submission = _submission(main_case)
    qa = _client(Role.QUAN_QA_RA, "gate_qa")
    blocked = qa.post(f"/api/v1/qa/submission/{submission.pk}/decision/", {"decision": "ACCEPT", "note": "Checked."}, format="json")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "reconciliation_required"
    assert "2 fact(s) not yet verified" in blocked.json()["error"]["message"]
    # a re-query or reject is not "counting as complete", so it is never blocked
    assert qa.post(f"/api/v1/qa/submission/{submission.pk}/decision/", {"decision": "QUERY", "note": "Check the duration."}, format="json").status_code == 200

    fc = _client(Role.FIELD_COORDINATOR, "gate_fc")
    for field in profile.fields.all():
        fc.post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json")
    ok = qa.post(f"/api/v1/qa/submission/{submission.pk}/decision/", {"decision": "ACCEPT", "note": "All checked."}, format="json")
    assert ok.status_code == 200 and ok.json()["qa_status"] == "QA_PASSED"


def test_a_recorded_protocol_deviation_releases_the_case_but_stays_flagged(main_case):
    profile = _locked_profile(main_case)
    submission = _submission(main_case)
    fc = _client(Role.FIELD_COORDINATOR, "gate_fc2")
    assert fc.post(f"/api/v1/proit/pre-profiles/{profile.pk}/deviation/", {"note": ""}, format="json").status_code == 400
    assert fc.post(f"/api/v1/proit/pre-profiles/{profile.pk}/deviation/", {"note": "Respondent unreachable after the interview."}, format="json").status_code == 200
    profile.refresh_from_db()
    assert profile.reconciliation_status == ReconciliationStatus.UNRESOLVED and profile.protocol_deviation
    qa = _client(Role.QUAN_QA_RA, "gate_qa2")
    assert qa.post(f"/api/v1/qa/submission/{submission.pk}/decision/", {"decision": "ACCEPT", "note": "Deviation recorded."}, format="json").status_code == 200
    assert AuditEvent.objects.filter(action="proit.protocol_deviation_recorded").exists()


def test_a_case_with_no_profile_or_an_empty_one_is_never_held_up(main_case):
    assert reconciliation_blocker(sample_case=main_case) is None
    profile = create_pre_profile(sample_case=main_case)
    lock_pre_profile(profile, reviewer=User.objects.create_user(username="rev-empty", password="x"))
    assert reconciliation_blocker(sample_case=main_case) is None  # PROIT is optional per case


def test_a_kii_coding_cannot_complete_until_reconciled_and_the_sync_completes_it_afterwards(db):
    record = create_kii_record(stakeholder_category="Financial institution representative", participant_name="A", participant_role="r",
                               preferred_mode="PHONE")
    profile = create_pre_profile(kii_record=record)
    field = add_field(profile, "legal_name", documentary_value="Test Bank")
    add_evidence(field, source_title="Annual report", source_confidence="HIGH", source_authority="TIER_1_STATUTORY")
    lock_pre_profile(profile, reviewer=User.objects.create_user(username="rev-kii", password="x"))

    with pytest.raises(InvalidKIITransition) as exc:
        advance_coding_status(record, CodingStatus.COMPLETE)
    assert "Reconcile the pre-interview profile first" in str(exc.value)

    # the automatic completion from a synced KII Guide skips it, and finishes the job once reconciled
    from apps.kobo.form_sync import _complete_kii_coding

    payloads = [{"part_a/KII_ID": record.kii_id, "_id": 1}]
    _complete_kii_coding(payloads)
    record.refresh_from_db()
    assert record.coding_status != CodingStatus.COMPLETE
    _client(Role.KII_RA, "kii_ra_v").post(f"/api/v1/proit/fields/{field.pk}/verify/", {"status": "YES_CORRECT"}, format="json")
    _complete_kii_coding(payloads)
    record.refresh_from_db()
    assert record.coding_status == CodingStatus.COMPLETE


def test_a_kii_ra_can_run_the_interview_sheet_for_a_kii_profile(db):
    record = create_kii_record(stakeholder_category="Financial institution representative", participant_name="A", participant_role="r",
                               preferred_mode="PHONE")
    profile = create_pre_profile(kii_record=record)
    field = add_field(profile, "legal_name", documentary_value="Test Bank")
    add_evidence(field, source_title="Annual report", source_confidence="HIGH", source_authority="TIER_1_STATUTORY")
    lock_pre_profile(profile, reviewer=User.objects.create_user(username="rev-kii2", password="x"))
    ra = _client(Role.KII_RA, "kii_ra_sheet")
    sheet = ra.get(f"/api/v1/proit/interview-sheet/?kii_record={record.pk}").json()["profile"]
    assert sheet["kii_id"] == record.kii_id and sheet["fields"][0]["field_id"] == "legal_name"
    done = ra.post(f"/api/v1/proit/pre-profiles/{profile.pk}/interview-complete/")
    assert done.status_code == 200 and done.json()["interview_completed_at"] is not None
    assert PreProfile.objects.get(pk=profile.pk).interview_completed_at is not None


# --- Robustness found by the first live run ------------------------------------------------------------

def _findings_call(findings, tool_id="tu_1"):
    block = Mock(type="tool_use", input={"summary": "s", "findings": findings}, id=tool_id)
    block.name = "record_findings"
    return _response([block], "tool_use")


def test_an_empty_answer_is_sent_back_to_be_completed_instead_of_accepted(settings):
    """A live run on a well-documented listed company once came back with no findings at all and the
    researcher accepted it as 'nothing found publicly'. An incomplete answer is now sent back, twice at most."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    complete = [_found(fid) for fid in list(FIELDS)[:20]]
    first = _findings_call([])
    second = _findings_call(complete, "tu_2")
    with patch("anthropic.Anthropic") as client_cls:
        stream = client_cls.return_value.messages.stream
        stream.return_value.__enter__.return_value.get_final_message.side_effect = [first, second]
        raw, _seen, _usage = call_model({"organisation": {"name": "X"}, "person": {}}, FIELDS)
        sent = stream.call_args.kwargs["messages"]
    assert len(raw["findings"]) == 20 and stream.call_count == 2
    reminder = sent[-1]["content"][0]
    assert reminder["type"] == "tool_result" and reminder["is_error"] is True and reminder["tool_use_id"] == "tu_1"
    assert "Incomplete" in reminder["content"]


def test_a_model_that_keeps_returning_nothing_is_stopped_after_two_reminders(settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    with patch("anthropic.Anthropic") as client_cls:
        stream = client_cls.return_value.messages.stream
        stream.return_value.__enter__.return_value.get_final_message.side_effect = [_findings_call([], f"t{i}") for i in range(5)]
        raw, _s, _u = call_model({"organisation": {"name": "X"}, "person": {}}, FIELDS)
    assert raw["findings"] == [] and stream.call_count == 3  # the answer, then two reminders, then it gives up: all fields "not found"


def test_findings_sent_as_a_json_string_are_still_read():
    import json

    raw = {"findings": json.dumps([_found()])}
    proposals, _ = clean_findings(raw, {URL}, FIELDS)
    assert next(p for p in proposals if p["field_id"] == "legal_name")["status"] == "found"


@pytest.mark.parametrize("value", [
    "Christian Care is a church-linked development partner in the sector.",
    "Listed on the ZSE; share prices 1970 1980 1990 in the archive.", "Revenue was USD 1 200 000 000 in 2024.",
    "Joined in December 1996; Group CEO from 1 July 2021; head office at Sable House, Borrowdale.",
])
def test_ordinary_organisational_facts_are_not_mistaken_for_private_ones(value):
    proposals, dropped = clean_findings({"findings": [_found(field_id="key_products", value=value)]}, {URL}, FIELDS)
    assert next(p for p in proposals if p["field_id"] == "key_products")["status"] == "found" and not dropped
