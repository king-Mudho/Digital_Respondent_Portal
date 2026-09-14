"""
Staff record and correct respondents' contact details (added 2026-09-14).
Before, only the register import and the respondent's own eligibility answer
created a Respondent, so most Main cases had no phone number and nowhere to
record one.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import record_consent
from apps.contacts.models import Respondent
from apps.contacts.services import has_passed_eligibility


def _user(role_name, username):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x", role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_an_assigned_contact_ra_adds_and_corrects_a_contact(main_case):
    ra = _user(Role.CONTACT_RA, "rc_ra")
    main_case.assigned_ra = ra
    main_case.save(update_fields=["assigned_ra"])
    client = _client(ra)
    url = f"/api/v1/contacts/{main_case.sample_id}/respondents/"

    resp = client.post(url, {"full_name": "Rudo Chari", "role_category": "CEO_MD", "phone": "0772 000 111"}, format="json")
    assert resp.status_code == 201, resp.json()
    assert not has_passed_eligibility(main_case)  # a contact is not a screened respondent

    rid = resp.json()["id"]
    resp = client.patch(f"/api/v1/contacts/respondents/{rid}/", {"whatsapp_number": "0772000111", "is_eligible": True}, format="json")
    assert resp.status_code == 200
    assert resp.json()["eligibility_checked_by"] == "rc_ra"
    assert has_passed_eligibility(main_case)

    assert [r["full_name"] for r in client.get(url).json()] == ["Rudo Chari"]
    events = AuditEvent.objects.filter(action__in=["contacts.respondent_added", "contacts.respondent_updated"]).order_by("id")
    assert [e.metadata["fields"] for e in events] == [["full_name", "phone", "role_category"], ["is_eligible", "whatsapp_number"]]
    assert "0772" not in str([e.metadata for e in events])  # names of fields, never the values


@pytest.mark.django_db
def test_contacts_respect_assignment_roles_and_withdrawal(main_case):
    url = f"/api/v1/contacts/{main_case.sample_id}/respondents/"
    body = {"full_name": "Someone", "phone": "0770000000"}

    assert _client(_user(Role.CONTACT_RA, "rc_unassigned")).post(url, body, format="json").status_code == 403
    assert _client(_user(Role.KII_RA, "rc_kii")).get(url).status_code == 403
    assert _client(_user(Role.SUPERVISOR_READONLY, "rc_sup")).post(url, body, format="json").status_code == 403

    fc = _client(_user(Role.FIELD_COORDINATOR, "rc_fc"))
    rid = fc.post(url, body, format="json").json()["id"]
    record_consent(
        sample_case=main_case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.WITHDRAWN,
        information_sheet_version="v1.2", method=ConsentMethod.VERBAL_RA_RECORDED,
    )
    assert fc.post(url, body, format="json").status_code == 409
    assert fc.patch(f"/api/v1/contacts/respondents/{rid}/", {"phone": "0779999999"}, format="json").status_code == 409
    assert Respondent.objects.get(pk=rid).phone == "0770000000"
