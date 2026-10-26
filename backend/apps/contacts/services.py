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


OPEN_APPOINTMENT_STATUSES = ("REQUESTED", "CONFIRMED")


def open_appointment_exists():
    """An Exists() subquery for querysets of SampleCase: the respondent asked for a call or interview (an appointment
    REQUESTED or CONFIRMED). Such a case is never waiting for a reminder, never becomes Nonresponse and is never
    replaced automatically, until the appointment is completed, missed or cancelled (2026-10-06 for reminders;
    2026-10-26 for automatic replacement, which had missed it)."""
    from django.db.models import Exists, OuterRef

    from .models import Appointment

    return Exists(Appointment.objects.filter(sample_case=OuterRef("pk"), status__in=OPEN_APPOINTMENT_STATUSES))


def has_open_appointment(sample_case) -> bool:
    from .models import Appointment

    return Appointment.objects.filter(sample_case=sample_case, status__in=OPEN_APPOINTMENT_STATUSES).exists()
