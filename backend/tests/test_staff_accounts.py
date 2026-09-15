"""Named staff accounts from the PI's spreadsheet, and bulk case reassignment (2026-09-15)."""

import csv
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.sampling.models import Province, SampleType
from apps.sampling.services import create_organisation, create_sample_case, resolve_stratum_for_organisation

HEADER = ["Full name", "Email", "Role", "Provinces (Contact RA only)", "Username (optional)"]


def _sheet(tmp_path, rows, name="staff.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Staff"
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    path = tmp_path / name
    wb.save(path)
    return path


def _user(username, role_name):
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(username=username, password="x-Long-Pass-2026", role=role)


def _cases(province, n, owner):
    ids = []
    for i in range(n):
        org = create_organisation(province=province, name=f"{province} org {i}", district="D", actor_family="PRODUCER_PRIMARY",
                                  size_class="SME")
        case = create_sample_case(organisation=org, stratum=resolve_stratum_for_organisation(org), sample_type=SampleType.MAIN, year=2026)
        case.assigned_ra = owner
        case.save(update_fields=["assigned_ra"])
        ids.append(case.sample_id)
    return ids


@pytest.mark.django_db
def test_accounts_are_created_and_cases_split_evenly_by_province(tmp_path):
    for code, _ in Role.NAME_CHOICES:
        Role.objects.get_or_create(name=code)
    shared = _user("contact_ra", Role.CONTACT_RA)
    already = _user("rudo.named", Role.CONTACT_RA)
    harare = _cases(Province.HARARE, 3, shared)
    bulawayo = _cases(Province.BULAWAYO, 1, shared)
    kept = _cases(Province.HARARE, 1, already)
    _user("existing.person", Role.KII_RA).__class__.objects.filter(username="existing.person").update(email="kii@example.org")

    sheet = _sheet(tmp_path, [
        ["Tendai Moyo", "tendai@example.org", "Contact RA", "Harare", ""],
        ["Dr Chipo Ncube", "chipo@example.org", "Contact RA", "Harare, Bulawayo", ""],
        ["Farai Dube", "farai@example.org", "Field Coordinator", "", ""],
        ["Existing Person", "KII@example.org", "KII RA", "", ""],
    ])

    call_command("create_staff_accounts", "--file", str(sheet), "--assign-cases", "--dry-run", stdout=StringIO())
    assert not User.objects.filter(email="tendai@example.org").exists()

    out = StringIO()
    call_command("create_staff_accounts", "--file", str(sheet), "--assign-cases", "--credentials-dir", str(tmp_path), stdout=out)

    tendai, farai = User.objects.get(username="tendai.moyo"), User.objects.get(username="farai.dube")
    assert User.objects.filter(username="chipo.ncube").exists()  # "Dr" left out of the username
    assert (tendai.role.name, farai.role.name, tendai.is_staff, tendai.get_full_name()) == (Role.CONTACT_RA, Role.FIELD_COORDINATOR, False, "Tendai Moyo")
    assert User.objects.filter(email__iexact="kii@example.org").count() == 1  # existing account left alone

    from apps.sampling.models import SampleCase

    owner = dict(SampleCase.objects.values_list("sample_id", "assigned_ra__username"))
    assert sorted(owner[s] for s in harare) == ["chipo.ncube", "tendai.moyo", "tendai.moyo"]
    assert owner[bulawayo[0]] == "chipo.ncube" and owner[kept[0]] == "rudo.named"

    [creds] = tmp_path.glob("staff-credentials-*.csv")
    rows = list(csv.DictReader(creds.open(encoding="utf-8")))
    assert {r["Username"] for r in rows} == {"tendai.moyo", "chipo.ncube", "farai.dube"}
    assert tendai.check_password(next(r for r in rows if r["Username"] == "tendai.moyo")["Temporary password"])
    passwords = [r["Temporary password"] for r in rows]
    assert not any(p in out.getvalue() for p in passwords)
    event = AuditEvent.objects.get(action="accounts.staff_accounts_created")
    assert not any(p in str(event.metadata) for p in passwords)
    assert event.metadata["cases_assigned"] == {"tendai.moyo": 2, "chipo.ncube": 2}


@pytest.mark.django_db
def test_a_sheet_with_mistakes_is_refused_before_anything_changes(tmp_path):
    sheet = _sheet(tmp_path, [
        ["Tendai Moyo", "not-an-email", "Contact RA", "Harare", ""],
        ["Chipo Ncube", "chipo@example.org", "Chief Wizard", "", ""],
        ["Farai Dube", "farai@example.org", "Analyst", "Harare", ""],
    ])
    with pytest.raises(CommandError) as err:
        call_command("create_staff_accounts", "--file", str(sheet), stdout=StringIO())
    message = str(err.value)
    assert "not a valid email" in message and "unknown role" in message and "only for Contact RAs" in message
    assert not User.objects.filter(email="chipo@example.org").exists()


@pytest.mark.django_db
def test_bulk_assign_previews_moves_a_limited_number_and_is_audited():
    pi = _user("pi_ba", Role.PI_ADMIN)
    shared = _user("shared_ba", Role.CONTACT_RA)
    target = _user("target_ba", Role.CONTACT_RA)
    ids = _cases(Province.HARARE, 3, shared)
    client = APIClient()
    client.force_authenticate(pi)
    body = {"to_ra": target.id, "from": shared.id, "province": "HARARE", "limit": 2}

    preview = client.post("/api/v1/sample-cases/bulk-assign/", {**body, "preview": True}, format="json").json()
    assert (preview["count"], preview["moved"]) == (2, 0)
    moved = client.post("/api/v1/sample-cases/bulk-assign/", body, format="json").json()
    assert moved["sample_ids"] == ids[:2]

    from apps.sampling.models import SampleCase

    assert SampleCase.objects.filter(assigned_ra=target).count() == 2
    assert AuditEvent.objects.filter(action="sampling.bulk_assignment").count() == 1

    analyst = _user("an_ba", Role.ANALYST)
    assert client.post("/api/v1/sample-cases/bulk-assign/", {"to_ra": analyst.id, "from": "any"}, format="json").status_code == 400
    ra_client = APIClient()
    ra_client.force_authenticate(target)
    assert ra_client.post("/api/v1/sample-cases/bulk-assign/", body, format="json").status_code == 403
