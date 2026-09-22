"""apps/audit/tasks.py:check_test_data_smells_task -- the daily emailed version of the same smell check."""

import pytest
from django.core import mail

from apps.accounts.models import Role, User
from apps.audit.tasks import check_test_data_smells_task
from apps.proit.models import PreProfile


@pytest.fixture
def pi(db):
    role, _ = Role.objects.get_or_create(name=Role.PI_ADMIN)
    return User.objects.create_user(username="pi_test", password="x", email="pi@example.org", role=role)


def test_a_clean_database_still_sends_an_all_clear_email(pi, main_case, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    check_test_data_smells_task()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["pi@example.org"]
    assert "no test-data smells" in mail.outbox[0].subject.lower()
    assert "No test/pilot-data smells found today" in mail.outbox[0].body


def test_a_flagged_item_is_named_in_the_email(pi, main_case, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    PreProfile.objects.create(sample_case=main_case)
    check_test_data_smells_task()
    body = mail.outbox[0].body
    assert "1 test-data item(s) to review" in mail.outbox[0].subject
    assert main_case.sample_id in body
    assert "Nothing has been changed" in body


def test_no_active_pi_admin_sends_nothing(db, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    check_test_data_smells_task()
    assert len(mail.outbox) == 0


def test_an_inactive_pi_admin_is_not_emailed(pi, settings):
    pi.is_active = False
    pi.save(update_fields=["is_active"])
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    check_test_data_smells_task()
    assert len(mail.outbox) == 0
