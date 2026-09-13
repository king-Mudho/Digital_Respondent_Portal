from apps.audit.utils import log_action

from .models import Respondent


def record_eligibility_check(*, sample_case, full_name: str, role_category: str, is_eligible: bool) -> Respondent:
    """Create the Respondent row for this eligibility attempt. If ineligible,
    a later, separate Respondent row is created once the correct person is
    identified (docs/10_INVITATION_AND_CONSENT.md) -- this function never
    overwrites a prior attempt."""
    respondent = Respondent.objects.create(
        sample_case=sample_case,
        full_name=full_name,
        role_category=role_category,
        is_eligible=is_eligible,
    )
    log_action(
        "eligibility.checked",
        respondent,
        {"is_eligible": is_eligible, "sample_id": sample_case.sample_id},
    )
    return respondent


def has_passed_eligibility(sample_case) -> bool:
    """Whether an eligible respondent has been identified for this case.

    The eligibility counterpart to consent.services.has_given_consent, and
    the same rule applies: every eligibility-gated action calls this rather
    than inferring it from something adjacent. Because record_eligibility_
    check never overwrites a prior attempt, a case where a gatekeeper was
    screened out first and the right person was identified afterwards has
    both rows -- so this asks whether *any* eligible respondent exists, not
    what the most recent attempt said.

    Respondents imported from the sampling register have is_eligible NULL
    (not yet screened), which is correctly not eligible here.
    """
    return Respondent.objects.filter(sample_case=sample_case, is_eligible=True).exists()
