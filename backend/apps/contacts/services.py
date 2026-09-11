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
