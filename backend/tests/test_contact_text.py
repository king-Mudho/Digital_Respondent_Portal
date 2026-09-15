"""Imported contact text split into name, phone, WhatsApp and email (2026-09-15)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.contacts.contact_text import NOT_IDENTIFIED, UNNAMED, split_contact_text
from apps.contacts.models import Respondent, RoleCategory
from apps.messaging.services import whatsapp_digits


@pytest.mark.parametrize("raw, name, phone, whatsapp, email", [
    ("​+263715261525", UNNAMED, "+263715261525", "+263715261525", ""),
    ("0772686106, 0773626999, 0242 665183.", UNNAMED, "0772686106, 0773626999, 0242 665183", "+263772686106", ""),
    ("+263 9 888616, 71363 / 5; +263 773 142 761, 772 830 867", UNNAMED,
     "+263 9 888616, 71363 / 5; +263 773 142 761, 772 830 867", "+263773142761", ""),
    ("Mr J. Mushandu +263772922485/715012852; shamvaagric@gmail.com", "Mr J. Mushandu",
     "+263772922485/715012852", "+263772922485", "shamvaagric@gmail.com"),
    ("+263 institutional contacts; farm@watershed.ac.zw", UNNAMED, "", "", "farm@watershed.ac.zw"),
    ("Institutional contact to verify", NOT_IDENTIFIED, "", "", ""),
    ("+263 4 754613 / 6 / 7 / 8 / 9", UNNAMED, "+263 4 754613 / 6 / 7 / 8 / 9", "", ""),
    ("​+447852325073", UNNAMED, "+447852325073", "+447852325073", ""),
])
def test_register_contact_cells_are_split_into_their_parts(raw, name, phone, whatsapp, email):
    parts = split_contact_text(raw)
    assert (parts.name, parts.phone, parts.whatsapp, parts.email) == (name, phone, whatsapp, email)


@pytest.mark.parametrize("raw, expected", [
    ("+263 778840932; +263719502023", "263778840932"),  # was 263778840932263719502023
    ("​+263712761382", "263712761382"),
    ("+263 4 749153 - 4; +263 772 965 397, 773 248 965", "263772965397"),  # a mobile before a landline
    ("0242 665183", "263242665183"),
])
def test_wa_me_uses_one_number_from_a_multi_number_field(raw, expected):
    assert whatsapp_digits(raw) == expected


@pytest.mark.django_db
def test_cleanup_moves_contact_text_out_of_the_name_and_leaves_edited_people_alone(main_case, tmp_path):
    imported = Respondent.objects.create(sample_case=main_case, full_name="0772324322; chamisaa@gmail.com",
                                         phone="0772324322", email="chamisaa@gmail.com")
    screened = Respondent.objects.create(sample_case=main_case, full_name="+263 77 123 4567", phone="+263 77 123 4567",
                                         role_category=RoleCategory.CEO_MD, is_eligible=True)
    real_name = Respondent.objects.create(sample_case=main_case, full_name="Tendai Moyo", phone="0771234567")

    call_command("clean_imported_contacts", "--dry-run", stdout=StringIO())
    imported.refresh_from_db()
    assert imported.full_name == "0772324322; chamisaa@gmail.com"

    call_command("clean_imported_contacts", "--backup-dir", str(tmp_path), stdout=StringIO())
    imported.refresh_from_db()
    assert (imported.full_name, imported.phone, imported.whatsapp_number, imported.email) == (
        UNNAMED, "0772324322", "+263772324322", "chamisaa@gmail.com")
    screened.refresh_from_db()
    real_name.refresh_from_db()
    assert screened.full_name == "+263 77 123 4567" and real_name.whatsapp_number == ""

    # A second run finds nothing to do, including email-only contacts whose
    # placeholder name must not be re-read as contact text.
    email_only = Respondent.objects.create(sample_case=main_case, full_name="farm@watershed.ac.zw", email="farm@watershed.ac.zw")
    call_command("clean_imported_contacts", "--backup-dir", str(tmp_path), stdout=StringIO())
    out = StringIO()
    call_command("clean_imported_contacts", "--dry-run", stdout=out)
    assert "'respondents_changed': 0" in out.getvalue()
    email_only.refresh_from_db()
    assert email_only.full_name == UNNAMED

    backup = sorted(tmp_path.glob("imported-contacts-before-cleanup-*.json"))[0]
    assert json.loads(backup.read_text())[0]["full_name"] == "0772324322; chamisaa@gmail.com"
    event = AuditEvent.objects.filter(action="contacts.imported_contacts_cleaned").earliest("created_at")
    assert event.metadata["respondent_ids"] == [imported.id] and "0772324322" not in json.dumps(event.metadata)
