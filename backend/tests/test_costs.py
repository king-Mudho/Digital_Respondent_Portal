"""The cost register (PI, 18 Oct 2026): every cost says what it was for and, where it applies, who was paid; the
list shows each entry with its date, newest first, and the total of what it lists; entries can be corrected or
removed, always audited; the Supervisor reads it, the Analyst sees only the dashboard totals."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.costs.models import CostEvent

pytestmark = pytest.mark.django_db
URL = "/api/v1/costs/"


def _client(role, username):
    role_obj, _ = Role.objects.get_or_create(name=role)
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username, password="x", role=role_obj, first_name="Tendai"))
    return client


@pytest.fixture
def fc():
    return _client("FIELD_COORDINATOR", "cost_fc")


def _add(client, **kw):
    data = {"date": "2026-10-18", "category": "SOFTWARE_AI", "amount": "20.00", "description": "Claude subscription, October",
            "paid_to": "Anthropic", **kw}
    return client.post(URL, data, format="json")


def test_a_cost_must_say_what_it_was_for_and_is_listed_newest_first_with_the_total(fc):
    refused = _add(fc, description="  ")
    assert refused.status_code == 400 and "description" in refused.json()["error"]["field_errors"]
    assert _add(fc, amount="0").status_code == 400
    assert _add(fc).status_code == 201
    assert _add(fc, date="2026-09-30", category="RA_ALLOWANCE", amount="30.00", description="Fieldwork allowance, week 2",
                paid_to="Rudo Moyo").status_code == 201
    body = fc.get(URL).json()
    assert [r["description"] for r in body["results"]] == ["Claude subscription, October", "Fieldwork allowance, week 2"]
    assert body["total"] == "50.00" and body["count"] == 2
    first = body["results"][0]
    assert first["paid_to"] == "Anthropic" and first["category_label"] == "Software / AI tools" and first["recorded_by"] == "Tendai"
    october = fc.get(URL, {"month": "2026-10"}).json()
    assert october["count"] == 1 and october["total"] == "20.00"
    allowances = fc.get(URL, {"category": "RA_ALLOWANCE"}).json()
    assert [r["paid_to"] for r in allowances["results"]] == ["Rudo Moyo"]
    assert AuditEvent.objects.filter(action="cost.recorded").count() == 2


def test_an_entry_can_be_corrected_or_removed_and_both_are_audited(fc):
    pk = _add(fc).json()["id"]
    assert fc.patch(f"{URL}{pk}/", {"amount": "25.00"}, format="json").status_code == 200
    assert CostEvent.objects.get(pk=pk).description == "Claude subscription, October"  # kept when not sent
    changed = AuditEvent.objects.get(action="cost.updated").metadata["changed"]
    assert changed == {"amount": {"from": "20.00", "to": "25.00"}}
    assert fc.delete(f"{URL}{pk}/").status_code == 204 and not CostEvent.objects.exists()
    assert AuditEvent.objects.get(action="cost.deleted").metadata["description"] == "Claude subscription, October"


def test_the_supervisor_reads_the_register_and_the_analyst_only_the_dashboard_totals(fc):
    pk = _add(fc).json()["id"]
    sup = _client("SUPERVISOR_READONLY", "cost_sup")
    assert sup.get(URL).status_code == 200
    assert _add(sup).status_code == 403 and sup.delete(f"{URL}{pk}/").status_code == 403
    analyst = _client("ANALYST", "cost_analyst")
    assert analyst.get(URL).status_code == 403  # names of people paid stay with the PI and Field Coordinator
    dash = analyst.get("/api/v1/dashboards/cost/").json()
    assert dash["cost_by_category"][0]["label"] == "Software / AI tools" and dash["total_cost"] == "20.00"
