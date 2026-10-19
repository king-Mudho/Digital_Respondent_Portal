"""The study's clearance letters go with the invitation (PI, 19 Oct 2026): a key informant who left an invitation
unanswered agreed to meet once he was sent the letters. Under test:

- an emailed invitation (Main-400 and KII) carries the letters a participant may see -- public, active, with a file --
  as attachments, says so in the text, and records which files went; a private or switched-off letter never goes,
  and with no letters there is neither an attachment nor the sentence;
- the combined PDF WhatsApp shows above the introduction is served only at the address holding STUDY_LETTERS_KEY.
"""

from io import BytesIO

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APIClient

from apps.clearance import services as clearance
from apps.clearance.models import ClearanceDocument
from apps.contacts.models import Respondent
from apps.invitations.messages import email_invitation
from apps.invitations.services import issue_invitation
from apps.kii.messages import email_kii_invitation
from apps.kii.services import create_kii_record, issue_kii_invitation
from apps.messaging.models import ProviderMessage

pytestmark = pytest.mark.django_db
SITE = "https://research.agribizframework.com"


def _pdf(pages=1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def letters(settings, tmp_path):
    settings.PRIVATE_DATA_ROOT = str(tmp_path)
    clearance._pack_cache.clear()
    made = {}
    for title, public, active in (("Research Ethics Clearance Letter", True, True), ("Approval of Research Proposal", True, True),
                                  ("Confirmation of PhD Research Supervision", False, True), ("Old Letter", True, False)):
        doc = ClearanceDocument.objects.create(title=title, issuing_body="CUT", document_type="OTHER", is_public=public, active=active)
        clearance.save_file(doc, SimpleUploadedFile(title.replace(" ", "_") + ".pdf", _pdf(), content_type="application/pdf"), user=None)
        made[title] = doc
    return made


def test_an_emailed_main_invitation_carries_only_the_letters_participants_may_see(letters, main_case):
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", email="jane@farmco.co.zw")
    raw, code, token = issue_invitation(main_case, channel="EMAIL", issued_by=None)
    email_invitation(token, link=f"{SITE}/i/{raw}", manual_code=code, user=None)
    sent = mail.outbox[0]
    assert sorted(name for name, _, _ in sent.attachments) == ["Approval_of_Research_Proposal.pdf", "Research_Ethics_Clearance_Letter.pdf"]
    assert "research clearance letters are attached: Research Ethics Clearance Letter; Approval of Research Proposal" in sent.body
    assert "Supervision" not in sent.body and "Old Letter" not in sent.body
    assert "[Attached: " in ProviderMessage.objects.get().body  # the timeline says what went with it


def test_an_emailed_kii_invitation_carries_the_letters_too(letters):
    record = create_kii_record(participant_name="Tendai Moyo", participant_role="Director", stakeholder_category="Bank",
                               email="tendai@bank.co.zw", metadata={"organisation_name": "Agri Bank"})
    raw, code, token = issue_kii_invitation(record)
    email_kii_invitation(token, link=f"{SITE}/ki/{raw}", manual_code=code, user=None)
    assert len(mail.outbox[0].attachments) == 2 and "research clearance letters are attached" in mail.outbox[0].body


def test_with_no_letters_there_is_neither_an_attachment_nor_the_sentence(settings, tmp_path, main_case):
    settings.PRIVATE_DATA_ROOT = str(tmp_path)
    Respondent.objects.create(sample_case=main_case, full_name="Jane Doe", email="jane@farmco.co.zw")
    raw, code, token = issue_invitation(main_case, channel="EMAIL", issued_by=None)
    email_invitation(token, link=f"{SITE}/i/{raw}", manual_code=code, user=None)
    assert not mail.outbox[0].attachments and "clearance letters are attached" not in mail.outbox[0].body


def test_the_combined_letters_pdf_is_served_only_at_the_keyed_address(letters, settings):
    client = APIClient()
    path = f"/api/v1/study-letters/s3cret-key/{clearance.PACK_NAME}"
    settings.STUDY_LETTERS_KEY = ""
    assert client.get(path).status_code == 404  # not served until a key is set
    settings.STUDY_LETTERS_KEY = "another-key"
    assert client.get(path).status_code == 404
    settings.STUDY_LETTERS_KEY = "s3cret-key"
    resp = client.get(path)
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    assert len(PdfReader(BytesIO(resp.content)).pages) == 2  # the two public, active letters only
    assert clearance.letters_pack_url().endswith(f"/api/v1/study-letters/s3cret-key/{clearance.PACK_NAME}")
