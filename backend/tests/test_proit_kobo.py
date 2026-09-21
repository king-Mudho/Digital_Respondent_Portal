"""A finished pre-interview profile is sent to KoboToolbox (apps/proit/kobo_submit.py): once, only when finished,
carrying what was known, what the respondent said and the reconciled value; never blocking the interview."""

from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

import pytest

from apps.accounts.models import User
from apps.proit import kobo_form as F
from apps.proit.kobo_submit import ProitKoboError, build_xml, push_profile
from apps.proit.services import (
    add_evidence, add_field, create_pre_profile, lock_pre_profile, reconcile_field, record_protocol_deviation,
    record_verification, refresh_reconciliation,
)
from django.utils import timezone


@pytest.fixture
def configured(settings):
    settings.KOBO_PROIT_ASSET_UID = "aPROITuid"
    settings.KOBO_PROIT_FORM_VERSION = "vTEST1"
    settings.KOBO_ACCOUNT_USERNAME = "acct"
    settings.KOBO_API_TOKEN = "t"


def _finished(main_case):
    profile = create_pre_profile(sample_case=main_case)
    for fid, value in (("legal_name", "Test Organisation (Pvt) Ltd"), ("hq_province", "Harare")):
        f = add_field(profile, fid, documentary_value=value)
        add_evidence(f, source_title="Registry entry", source_confidence="HIGH", source_authority="TIER_1_STATUTORY",
                     source_type="WEB", publisher="Registrar", locator="https://registry.example/x")
    lock_pre_profile(profile, reviewer=User.objects.create_user(username="rv", password="x"))
    fields = {f.field_id: f for f in profile.fields.all()}
    record_verification(fields["legal_name"], status="YES_CORRECT")
    record_verification(fields["hq_province"], status="PARTLY_CORRECT", respondent_value="Harare and Mashonaland East")
    reconcile_field(fields["hq_province"], reconciled_value="Harare (head office); depot in Mashonaland East")
    profile.interview_completed_at = timezone.now()
    profile.save(update_fields=["interview_completed_at"])
    return profile


def test_the_xml_carries_the_facts_the_respondents_answers_and_the_reconciled_value(main_case, configured):
    profile = _finished(main_case)
    refresh_reconciliation(profile)
    root = ET.fromstring(build_xml(profile, instance_uuid="u-1", submitted_by=None, version="vTEST1"))
    assert root.tag == "aPROITuid" and root.get("id") == "aPROITuid" and root.get("version") == "vTEST1"
    group = root.find(F.GROUP_NAME)
    assert group.find("record_id").text == main_case.sample_id and group.find("record_type").text == "QUAN"
    assert group.find("reconciliation_status").text == "RECONCILED" and group.find("facts_total").text == "2"
    facts = {i.find("fact_id").text: i for i in root.findall(F.REPEAT_NAME)}
    prov = facts["hq_province"]
    assert prov.find("documentary_value").text == "Harare"
    assert prov.find("verification_status").text == "PARTLY_CORRECT"
    assert prov.find("respondent_value").text == "Harare and Mashonaland East"
    assert "depot in Mashonaland East" in prov.find("reconciled_value").text
    assert "https://registry.example/x" in prov.find("sources").text
    assert root.find("meta/instanceID").text == "uuid:u-1"


def test_every_element_the_xml_sends_exists_in_the_form_definition(main_case, configured):
    profile = _finished(main_case)
    root = ET.fromstring(build_xml(profile, instance_uuid="u", submitted_by=None, version="v"))
    assert [e.tag for e in root.find(F.GROUP_NAME)] == [n for n, *_ in F.PROFILE_FIELDS]
    assert [e.tag for e in root.find(F.REPEAT_NAME)] == [n for n, *_ in F.REPEAT_FIELDS]


def test_it_is_sent_once_when_reconciled_and_never_twice(main_case, configured):
    profile = _finished(main_case)
    refresh_reconciliation(profile)
    with patch("apps.proit.kobo_submit.requests.post", return_value=Mock(status_code=201, text="")) as post:
        assert push_profile(profile.pk) == "sent"
        assert push_profile(profile.pk) == "already_sent"
    assert post.call_count == 1 and post.call_args.args[0] == "https://kc.kobotoolbox.org/acct/submission"
    profile.refresh_from_db()
    assert profile.kobo_submitted_at and profile.kobo_submission_uuid


def test_an_unfinished_profile_is_not_sent(main_case, configured):
    profile = create_pre_profile(sample_case=main_case)
    add_field(profile, "legal_name", documentary_value="X")
    with patch("apps.proit.kobo_submit.requests.post") as post:
        assert push_profile(profile.pk) == "not_ready"
    post.assert_not_called()


def test_nothing_is_sent_and_nothing_fails_while_the_form_is_not_configured(main_case, settings):
    settings.KOBO_PROIT_ASSET_UID = ""
    profile = _finished(main_case)
    refresh_reconciliation(profile)
    assert push_profile(profile.pk) == "not_configured"


def test_a_kobo_rejection_is_an_error_and_the_profile_stays_unsent_so_it_can_be_retried(main_case, configured):
    profile = _finished(main_case)
    refresh_reconciliation(profile)
    with patch("apps.proit.kobo_submit.requests.post", return_value=Mock(status_code=404, text="nope")):
        with pytest.raises(ProitKoboError):
            push_profile(profile.pk)
    profile.refresh_from_db()
    assert profile.kobo_submitted_at is None


def test_reaching_reconciled_queues_the_send_and_a_deviation_does_too(main_case, configured, django_capture_on_commit_callbacks):
    profile = _finished(main_case)
    with patch("apps.proit.tasks.push_profile_to_kobo.delay") as delay, django_capture_on_commit_callbacks(execute=True):
        refresh_reconciliation(profile)
    delay.assert_called_once_with(profile.pk)

    profile.reconciliation_status = "PENDING"
    profile.save(update_fields=["reconciliation_status"])
    with patch("apps.proit.tasks.push_profile_to_kobo.delay") as delay, django_capture_on_commit_callbacks(execute=True):
        record_protocol_deviation(profile, note="Respondent unreachable", user=None)
    delay.assert_called_once_with(profile.pk)
