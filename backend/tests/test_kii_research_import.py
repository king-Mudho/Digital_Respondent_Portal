"""Importing KII background research from a ChatGPT workbook (apps/proit/kii_import.py, 2026-10-11). The workbook has
the research pack's three Fill sheets. Under test: a preview keeps nothing; an import creates suggestions in the
existing review flows (contact suggestions and PROIT proposals), never facts on the record itself; example rows,
unknown records, non-catalogue fields and facts without a source are left out; a locked profile is untouched;
importing twice adds nothing; accepting an imported fact works like any AI finding; only the PI and FC may import."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.contacts.models import ContactProposal
from apps.kii.services import create_kii_record
from apps.proit.models import AIProposal, AIProposalStatus, PreProfile, PreProfileField
from apps.proit.services import accept_proposal, create_pre_profile

URL = "/api/v1/proit/kii-import/"
A = ["KII ID", "Organisation", "Website", "Main phone", "General email", "Head office address",
     "Person in the role (official source only)", "Their title", "Their published work phone", "Their published work email",
     "Source links", "Confidence", "Notes"]
B = ["KII ID", "Organisation", "field_id (sheet 4)", "Field label", "Value found (documentary)", "Confidence", "Source title",
     "Publisher", "Source date", "Link", "Source tier (sheet 5)", "Conflicting source?", "Notes"]
C = ["KII ID", "Organisation", "Known evidence summary", "Unresolved gaps", "Contradictions",
     "Priority probe questions (with KII Guide code)", "Suggested KII Guide module(s)", "Suggested PROIT role",
     "Executive short form? (Yes/No + why)", "Public documents to ask about (title, year, link)", "Notes"]


def _user(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    return User.objects.create_user(username=username, password="x", role=role_obj)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def record(db):
    return create_kii_record(participant_name="CBZ Bank (contact not yet identified)", participant_role="Head of Agribusiness",
                             stakeholder_category="Bank, DFI & MFI", metadata={"organisation_name": "CBZ Bank"})


def _workbook(kii_id, *, a=None, b=None, c=None) -> bytes:
    wb = Workbook()
    for title, header, rows in (("Fill A Contacts", A, a), ("Fill B PROIT facts", B, b), ("Fill C Interview prep", C, c)):
        ws = wb.create_sheet(title)
        ws.append(header)
        ws.append(["KII-0000", "Example Bank Ltd EXAMPLE (delete)"] + ["example"] * (len(header) - 2))
        for row in rows if rows is not None else []:
            ws.append(row)
    del wb["Sheet"]
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _full(kii_id):
    return _workbook(kii_id, a=[[kii_id, "CBZ Bank", "https://www.cbz.co.zw", "+263 242 748050", "info@cbz.co.zw",
                                 "Union Avenue, Harare", "Tendai Moyo", "Head of Agribusiness", "not found",
                                 "tmoyo@cbz.co.zw", "https://www.cbz.co.zw/management https://www.cbz.co.zw/contact",
                                 "HIGH", ""]],
                     b=[[kii_id, "CBZ Bank", "year_established", "Year established", "1980", "HIGH", "CBZ annual report 2024",
                         "CBZ Holdings", "2025-04-30", "https://www.cbz.co.zw/ar2024.pdf", "Tier 1", "No", ""],
                        [kii_id, "CBZ Bank", "key_products", "Key products", "Agri-loans for contract farmers", "MODERATE",
                         "Agribusiness page", "CBZ", "", "https://www.cbz.co.zw/agri", "TIER_2_INSTITUTIONAL", "No", ""],
                        [kii_id, "CBZ Bank", "public_insurance", "Insurance", "not found", "", "", "", "", "", "", "", ""],
                        [kii_id, "CBZ Bank", "credit_score_estimate", "Made up", "AA", "HIGH", "x", "", "", "https://x.example", "", "", ""],
                        [kii_id, "CBZ Bank", "trading_name", "Trading name", "CBZ", "MODERATE", "No link given", "", "", "", "", "", ""]],
                     c=[[kii_id, "CBZ Bank", "Runs an agri-loan book (2024).", "Collateral policy not public.", "",
                         "FP2: Which alternative evidence replaces collateral?", "finance_providers", "FINANCE_LENDER",
                         "No: head of unit", "Agri lending policy 2023, https://www.cbz.co.zw/policy.pdf", ""]])


def _post(user, data, *, dry_run, name="research.xlsx"):
    return _client(user).post(URL, {"file": SimpleUploadedFile(name, data), "dry_run": "true" if dry_run else "false"},
                              format="multipart")


@pytest.fixture
def pi(db):
    return _user(Role.PI_ADMIN, "imp_pi")


def test_a_preview_shows_what_would_happen_and_keeps_nothing(pi, record):
    resp = _post(pi, _full(record.kii_id), dry_run=True)
    assert resp.status_code == 200
    [row] = resp.json()["records"]
    assert (row["kii_id"], row["status"], row["contacts"], row["facts"], row["not_found"]) == (record.kii_id, "ready", 5, 2, 1)
    assert row["record_id"] == record.id  # the record page is addressed by number
    assert resp.json()["examples_skipped"] == 3
    assert not ContactProposal.objects.exists() and not AIProposal.objects.exists() and not PreProfile.objects.exists()
    assert not AuditEvent.objects.filter(action="proit.kii_research_imported").exists()


def test_an_import_creates_suggestions_for_review_never_facts_on_the_record(pi, record):
    resp = _post(pi, _full(record.kii_id), dry_run=False)
    assert resp.status_code == 201 and resp.json()["records"][0]["status"] == "imported"
    kinds = sorted(ContactProposal.objects.filter(kii_record=record).values_list("kind", flat=True))
    assert kinds == ["OFFICE_LOCATION", "ORG_EMAIL", "ORG_PHONE", "PERSON", "WEBSITE"]
    person = ContactProposal.objects.get(kind="PERSON")
    assert (person.person_name, person.person_email, person.status) == ("Tendai Moyo", "tmoyo@cbz.co.zw", "PROPOSED")
    assert len(person.sources) == 2
    record.refresh_from_db()
    assert record.phone == "" and record.email == ""  # nothing on the record until someone accepts
    profile = PreProfile.objects.get(kii_record=record)
    proposals = {p.field_id: p for p in AIProposal.objects.filter(pre_profile=profile)}
    assert set(proposals) == {"year_established", "key_products", "public_insurance"}
    assert proposals["year_established"].sources[0]["authority"] == "TIER_1_STATUTORY"
    assert proposals["public_insurance"].status == AIProposalStatus.NOT_FOUND
    assert not PreProfileField.objects.exists()
    assert "Collateral policy not public." in profile.unresolved_gaps and profile.role_specific_module == "FINANCE_LENDER"
    assert "Public documents to ask about" in profile.known_evidence_summary and "Imported from research.xlsx" in profile.known_evidence_summary
    warnings = " ".join(resp.json()["records"][0]["warnings"])
    assert "credit_score_estimate" in warnings and "trading_name: no source link" in warnings
    assert AuditEvent.objects.get(action="proit.kii_research_imported").metadata["facts"] == 2


def test_an_imported_fact_is_accepted_like_any_ai_finding(pi, record):
    _post(pi, _full(record.kii_id), dry_run=False)
    proposal = AIProposal.objects.get(field_id="year_established")
    field = accept_proposal(proposal, user=pi)
    assert field.preliminary_documentary_value == "1980" and field.sources.count() == 1


def test_importing_twice_adds_nothing_new(pi, record):
    _post(pi, _full(record.kii_id), dry_run=False)
    resp = _post(pi, _full(record.kii_id), dry_run=False)
    assert resp.json()["totals"]["contacts"] == 0 and resp.json()["totals"]["facts"] == 0
    assert ContactProposal.objects.count() == 5 and AIProposal.objects.exclude(status="NOT_FOUND").count() == 2


def test_a_locked_profile_is_never_changed(pi, record):
    from django.utils import timezone

    profile = create_pre_profile(kii_record=record)
    PreProfile.objects.filter(pk=profile.pk).update(prepopulation_locked_at=timezone.now(), unresolved_gaps="Original")
    resp = _post(pi, _full(record.kii_id), dry_run=False)
    profile.refresh_from_db()
    assert profile.unresolved_gaps == "Original" and not AIProposal.objects.exists()
    assert ContactProposal.objects.count() == 5  # contacts still go to review
    assert "locked" in " ".join(resp.json()["records"][0]["warnings"])


def test_unknown_records_and_example_rows_are_left_out(pi, record):
    data = _workbook("KII-0999", a=[["KII-0999", "Nobody", "", "+263 242 000000", "", "", "", "", "", "", "https://x.example", "", ""]])
    resp = _post(pi, data, dry_run=False)
    [row] = resp.json()["records"]
    assert row["status"] == "skipped" and "No KII record KII-0999" in row["warnings"][0]
    assert not ContactProposal.objects.exists()


def test_disagreeing_sources_become_one_proposal_that_says_so(pi, record):
    data = _workbook(record.kii_id, b=[
        [record.kii_id, "CBZ", "year_established", "", "1980", "HIGH", "Annual report", "", "", "https://a.example", "Tier 1", "No", ""],
        [record.kii_id, "CBZ", "year_established", "", "1981", "MODERATE", "News", "", "", "https://b.example", "Tier 3", "Yes", ""],
    ])
    _post(pi, data, dry_run=False)
    proposal = AIProposal.objects.get()
    assert proposal.proposed_value == "1980" and "Sources disagree: 1980 / 1981" in proposal.notes and len(proposal.sources) == 2


@pytest.mark.parametrize("role", [Role.KII_RA, Role.SUPERVISOR_READONLY, Role.CONTACT_RA, Role.ANALYST])
def test_only_the_pi_and_field_coordinator_import(record, role):
    assert _post(_user(role, f"imp_{role.lower()}"), _full(record.kii_id), dry_run=True).status_code == 403
    assert _post(_user(Role.FIELD_COORDINATOR, "imp_fc"), _full(record.kii_id), dry_run=True).status_code == 200


def test_a_file_that_is_not_the_workbook_is_refused_in_plain_words(pi):
    assert _post(pi, b"a,b,c", dry_run=True, name="research.csv").json()["error"]["code"] == "not_xlsx"
    resp = _post(pi, b"not really excel", dry_run=True)
    assert resp.status_code == 400 and "Excel" in resp.json()["error"]["message"]
