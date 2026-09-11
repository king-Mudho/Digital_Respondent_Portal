"""
docs/22_TESTING_STRATEGY.md: "no Kobo redirect URL is issued without a
passed eligibility check and a GIVEN participation consent; KII recording
consent is never inferred from participation consent."
"""

from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
from apps.consent.services import has_given_consent, record_consent


def test_no_consent_recorded_means_not_given(main_case):
    assert has_given_consent(main_case, ConsentType.PARTICIPATION) is False


def test_given_participation_consent_is_detected(main_case):
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    assert has_given_consent(main_case, ConsentType.PARTICIPATION) is True


def test_kii_recording_consent_never_inferred_from_participation(main_case):
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    assert has_given_consent(main_case, ConsentType.PARTICIPATION) is True
    assert has_given_consent(main_case, ConsentType.KII_RECORDING) is False


def test_withdrawal_supersedes_given_consent(main_case):
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.GIVEN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    record_consent(
        sample_case=main_case,
        consent_type=ConsentType.PARTICIPATION,
        decision=ConsentDecision.WITHDRAWN,
        information_sheet_version="v1.0",
        method=ConsentMethod.WEB_CLICKTHROUGH,
    )
    assert has_given_consent(main_case, ConsentType.PARTICIPATION) is False
