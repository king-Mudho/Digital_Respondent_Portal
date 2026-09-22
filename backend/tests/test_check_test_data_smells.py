"""apps/audit/management/commands/check_test_data_smells.py -- a read-only scan for the kinds of test/
pilot data found and cleaned up by hand on 2026-09-22. Never writes anything."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.contacts.models import Respondent
from apps.kii.models import KIIRecord
from apps.proit.models import PreProfile, PreProfileField


def _run(**opts):
    out = StringIO()
    call_command("check_test_data_smells", stdout=out, **opts)
    return out.getvalue()


@pytest.mark.django_db
def test_a_clean_database_flags_nothing(main_case):
    output = _run()
    assert "0 item(s) flagged" in output


@pytest.mark.django_db
def test_an_empty_unlocked_preprofile_is_flagged(main_case):
    PreProfile.objects.create(sample_case=main_case)
    output = _run()
    assert "Empty, unlocked pre-interview profiles (1)" in output
    assert main_case.sample_id in output


@pytest.mark.django_db
def test_a_locked_or_populated_preprofile_is_not_flagged(main_case):
    p = PreProfile.objects.create(sample_case=main_case, prepopulation_locked_at="2026-01-01T00:00:00Z")
    output = _run()
    assert "Empty, unlocked" not in output
    p.delete()
    p2 = PreProfile.objects.create(sample_case=main_case)
    PreProfileField.objects.create(pre_profile=p2, field_id="legal_name", module="B", label="Legal name")
    output = _run()
    assert "Empty, unlocked" not in output


@pytest.mark.django_db
def test_a_kii_record_named_after_a_staff_member_is_flagged():
    Role.objects.get_or_create(name=Role.FIELD_COORDINATOR)
    User.objects.create_user(username="dr_smith", password="x", first_name="Dr", last_name="Smith")
    KIIRecord.objects.create(
        kii_id="KII-0500", stakeholder_category="x", participant_name="Dr Smith", participant_role="CEO",
    )
    output = _run()
    assert "matches staff account 'dr_smith'" in output


@pytest.mark.django_db
def test_a_respondent_email_matching_staff_is_flagged(main_case):
    User.objects.create_user(username="jsmith", password="x", email="j.smith@example.org")
    Respondent.objects.create(sample_case=main_case, email="j.smith@example.org")
    output = _run()
    assert "email matches staff account 'jsmith'" in output


@pytest.mark.django_db
def test_since_filter_excludes_older_records(main_case):
    PreProfile.objects.create(sample_case=main_case)
    output = _run(since="2099-01-01")
    assert "0 item(s) flagged" in output


@pytest.mark.django_db
def test_nothing_is_ever_written(main_case):
    PreProfile.objects.create(sample_case=main_case)
    _run()
    assert PreProfile.objects.filter(sample_case=main_case).exists()
