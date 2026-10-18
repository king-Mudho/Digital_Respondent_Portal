"""Thanking participants who completed the study, and their choice of findings / workshop (PI, 18 Oct 2026;
apps/messaging/thanks.py). Twilio is a fake requests.post; replies arrive as signed webhook posts. Under test:

- a Main case whose questionnaire was submitted, and a KII record marked completed, are thanked once: on WhatsApp
  with the approved template (who, and what they completed), else by email with the PI's full letter; a case with
  only a mobile waits while the template is not approved; a skipped case or a withdrawn one is never thanked;
- a thank-you button answer records the choice, is acknowledged, and is never read as YES to an introduction.
"""

from unittest.mock import Mock

import pytest
from django.core import mail
from django.utils import timezone

from apps.consent.models import ConsentDecision, ConsentMethod, ConsentRecord, ConsentType
from apps.contacts.models import Respondent, RoleCategory
from apps.invitations.models import InvitationToken, TokenStatus
from apps.invitations.services import issue_invitation
from apps.kii.models import KIIStatus
from apps.kii.services import create_kii_record
from apps.messaging import outreach, tasks, thanks
from apps.messaging import twilio_client as tw
from apps.messaging.models import InboundMessage, MessagePurpose, Outreach, OutreachStatus, ProviderMessage
from apps.sampling.services import transition_workflow_status
from tests.test_outreach import _reply

pytestmark = pytest.mark.django_db
THANKS_SID = "HXthanks"


@pytest.fixture
def twilio(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret-token"
    settings.TWILIO_SMS_FROM, settings.TWILIO_WHATSAPP_FROM = "", "+15550001111"
    settings.TWILIO_WA_CONTENT_INTRO, settings.TWILIO_WA_CONTENT_INTRO_REMINDER = "HXintro", ""
    settings.TWILIO_WA_CONTENT_THANK_YOU = THANKS_SID
    settings.EMAIL_HOST, settings.DEFAULT_FROM_EMAIL = "smtp.example", "abffst.research@gmail.com"
    settings.AI_TRANSIENT_RETRY_DELAYS = []
    sent = []

    def post(url, data=None, auth=None, timeout=None):
        sent.append(data)
        return Mock(status_code=201, json=Mock(return_value={"sid": f"SM{len(sent):04d}", "status": "queued"}))

    monkeypatch.setattr(tw.requests, "post", post)
    monkeypatch.setattr(tasks.handle_inbound_message, "delay", lambda *args: outreach.handle_inbound(*args))
    return sent


def _meta(monkeypatch, status):
    monkeypatch.setattr(tw, "template_approvals", lambda **kw: [{"sid": THANKS_SID, "status": status}])


def _completed(case, *, phone="0771234567", email=""):
    for status in ("S01", "S02", "S03"):
        transition_workflow_status(case, status)
    Respondent.objects.create(sample_case=case, full_name="Jane Doe", role_category=RoleCategory.CEO_MD, is_eligible=True,
                              phone=phone, email=email)
    raw, code, token = issue_invitation(case, channel="WHATSAPP", issued_by=None)
    InvitationToken.objects.filter(pk=token.pk).update(status=TokenStatus.SUBMITTED)
    return case


def test_a_case_that_submitted_is_thanked_once_on_whatsapp_with_the_approved_template(twilio, monkeypatch, main_case):
    _meta(monkeypatch, "approved")
    _completed(main_case)
    assert thanks.send_due_thanks() == {"whatsapp": 1}
    assert twilio[-1]["ContentSid"] == THANKS_SID and twilio[-1]["To"] == "whatsapp:+263771234567"
    assert '"2": "questionnaire"' in twilio[-1]["ContentVariables"] and main_case.organisation.name in twilio[-1]["ContentVariables"]
    shown = ProviderMessage.objects.get(purpose=MessagePurpose.THANK_YOU).body
    assert "Thank you for completing the questionnaire" in shown
    assert thanks.send_due_thanks() == {} and len(twilio) == 1  # once only


def test_while_the_template_waits_it_goes_by_email_or_waits_for_a_mobile_only_case(twilio, monkeypatch, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    _meta(monkeypatch, "pending")
    _completed(main_case, email="jane@farmco.co.zw")
    mobile_only = _completed(create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026), phone="0772000123")
    outcomes = thanks.send_due_thanks()
    assert outcomes == {"email": 1, "waiting for the template": 1} and not twilio
    letter = mail.outbox[0]
    assert letter.to == ["jane@farmco.co.zw"] and letter.subject == "Thank you for contributing to the Agribusiness Bankability Study"
    assert "Dear Jane Doe," in letter.body and "BOTH —" in letter.body and "https://agribizframework.com/" in letter.body
    mobile_only.refresh_from_db()
    assert "thank_you" not in (mobile_only.metadata or {})  # tried again once Meta approves
    _meta(monkeypatch, "approved")
    assert thanks.send_due_thanks() == {"whatsapp": 1}


def test_a_skipped_case_and_one_that_withdrew_are_never_thanked(twilio, monkeypatch, main_case, organisation, stratum):
    from apps.sampling.services import create_sample_case

    _meta(monkeypatch, "approved")
    _completed(main_case)
    main_case.metadata = {"thank_you": {"skip": "possible test case"}}
    main_case.save(update_fields=["metadata"])
    withdrew = _completed(create_sample_case(organisation=organisation, stratum=stratum, sample_type="MAIN", year=2026), phone="0772000456")
    ConsentRecord.objects.create(sample_case=withdrew, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.WITHDRAWN,
                                 information_sheet_version="v1.3", method=ConsentMethod.WEB_CLICKTHROUGH, timestamp=timezone.now())
    assert thanks.send_due_thanks() == {"withdrawn": 1} and not twilio


def test_a_completed_kii_informant_is_thanked_for_the_interview(twilio, monkeypatch):
    _meta(monkeypatch, "approved")
    create_kii_record(participant_name="Tendai Moyo", participant_role="Director", stakeholder_category="Bank",
                      status=KIIStatus.COMPLETED, phone="0771234567", metadata={"organisation_name": "Agri Bank"})
    assert thanks.send_due_thanks() == {"whatsapp": 1}
    assert '"2": "key informant interview"' in twilio[-1]["ContentVariables"] and "Tendai Moyo (Agri Bank)" in twilio[-1]["ContentVariables"]


def test_a_thank_you_button_records_the_choice_and_is_never_read_as_yes_to_an_introduction(twilio, monkeypatch, main_case):
    _meta(monkeypatch, "approved")
    _completed(main_case)
    intro = Outreach.objects.create(sample_case=main_case, channel="WHATSAPP", number_hash=outreach.number_hash("263771234567"),
                                    number_masked="+263 ••• 567", intro_sent_at=timezone.now())
    thanks.send_due_thanks()
    tokens_before = InvitationToken.objects.count()
    _reply("Findings only", payload="THANKS_FINDINGS")
    main_case.refresh_from_db()
    intro.refresh_from_db()
    assert main_case.metadata["thank_you"]["preference"] == "FINDINGS"
    assert InboundMessage.objects.get().kind == "PREF" and InboundMessage.objects.get().needs_person is False
    assert "the findings summary when ready" in twilio[-1]["Body"]
    assert intro.status == OutreachStatus.INTRO_SENT and InvitationToken.objects.count() == tokens_before  # not a YES


def test_thanking_the_same_case_directly_a_second_time_sends_nothing(twilio, monkeypatch, main_case):
    _meta(monkeypatch, "approved")
    _completed(main_case)
    assert thanks.thank(main_case) == "whatsapp"
    assert thanks.thank(main_case) == "already" and len(twilio) == 1
