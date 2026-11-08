"""An RA filling in the form with the respondent, on the phone or a WhatsApp call (PI, 8 Nov 2026).

The RA reads the participant information aloud and records the respondent's verbal consent (and, for the Main-400
questionnaire, which role they hold -- the eligibility check); the portal then opens the form with the RA stamped in
it. The form link still comes only from the single gates every caller uses -- kobo.services.build_redirect_url
(consent and eligibility) and kii.services.build_kii_coding_url (consent) -- so this path cannot open a questionnaire
those gates would refuse (AGENTS.md rule 6). Locked Reserves and withdrawn participants are refused (rule 4).

The questionnaire's stamp is a value only this server can sign (sign_ra), so a respondent cannot credit an RA by
editing the link; reconciliation reads it back with ra_from_payload().
"""

from django.core import signing
from django.utils import timezone

from apps.audit.utils import log_action

SALT = "drp.ra-administered"
MODES = {"PHONE": ("03", "PHONE"), "WHATSAPP_CALL": ("04", "WHATSAPP_CALL")}  # how they are talking -> (form code, contact channel)


class AdministerError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(message)


def sign_ra(user, sample_id: str) -> str:
    return signing.dumps({"u": user.id, "s": sample_id}, salt=SALT, compress=True)


def ra_from_payload(payload: dict, sample_id: str):
    """The RA who administered this questionnaire, from its signed ra_id -- or None (self-completed, unsigned,
    tampered, or signed for a different case)."""
    from apps.accounts.models import User

    raw = payload.get("ra_id") or next((v for k, v in payload.items() if k.split("/")[-1] == "ra_id"), "")
    if not raw:
        return None
    try:
        data = signing.loads(str(raw), salt=SALT)
    except signing.BadSignature:
        return None
    if data.get("s") != sample_id:
        return None
    return User.objects.filter(pk=data.get("u"), is_active=True).first()


def _log_contact(user, *, mode: str, notes: str, **link):
    from apps.contacts.models import ContactEvent, ContactOutcome

    return ContactEvent.objects.create(channel=MODES[mode][1], occurred_at=timezone.now(), outcome=ContactOutcome.ADMINISTERED,
                                       notes=notes, ra=user, **link)


def administer_main(user, sample_id: str, *, mode: str, respondent_name: str, role_category: str,
                    information_sheet_version: str) -> str:
    """Record eligibility and verbal consent if not already given, and return the questionnaire link stamped with
    this RA. The case must be one this user may see (their assigned cases, for an RA)."""
    from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
    from apps.consent.services import has_given_consent, latest_consent, record_consent
    from apps.contacts.models import RoleCategory
    from apps.contacts.services import has_passed_eligibility, record_eligibility_check
    from apps.invitations.models import InvitationToken, TokenStatus
    from apps.invitations.services import advance_token_status, issue_invitation
    from apps.kobo.services import KoboNotConfigured, KoboRedirectDenied, build_redirect_url
    from apps.messaging.communications import visible_cases
    from apps.sampling.models import WorkflowStatus
    from apps.sampling.services import advance_case_on_respondent_event, is_invitable

    if mode not in MODES:
        raise AdministerError("invalid_mode", "Choose a phone call or a WhatsApp call.")
    case = visible_cases(user).filter(sample_id=sample_id).first()
    if case is None:
        raise AdministerError("not_found", "That case was not found, or is not assigned to you.", 404)
    if not is_invitable(case):
        raise AdministerError("not_invitable", "This is a locked Reserve case: nobody is contacted until it is activated.", 409)
    current = latest_consent(case, ConsentType.PARTICIPATION)
    if current is not None and current.decision == ConsentDecision.WITHDRAWN:
        raise AdministerError("withdrawn", "This participant withdrew from the study.", 409)

    if not has_passed_eligibility(case):
        if role_category not in RoleCategory.values or not (respondent_name or "").strip():
            raise AdministerError("eligibility_required", "Record who you are speaking to and their role first.")
        record_eligibility_check(sample_case=case, full_name=respondent_name.strip(), role_category=role_category, is_eligible=True)
    if not has_given_consent(case):
        record_consent(sample_case=case, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
                       information_sheet_version=information_sheet_version or "", method=ConsentMethod.VERBAL_RA_RECORDED)

    open_statuses = [TokenStatus.GENERATED, TokenStatus.SENT, TokenStatus.OPENED, TokenStatus.ELIGIBILITY_PASSED,
                     TokenStatus.CONSENTED, TokenStatus.SURVEY_STARTED]
    token = InvitationToken.objects.filter(sample_case=case, status__in=open_statuses, expires_at__gt=timezone.now()).order_by("-issued_at").first()
    if token is None:
        _, _, token = issue_invitation(case, issued_by=user)
    try:
        payload = build_redirect_url(case, token_id=token.id, invitation_wave=token.invitation_wave,
                                     administration_mode=MODES[mode][0], respondent_role_category=role_category or "",
                                     consent_version=information_sheet_version or "", ra_id=sign_ra(user, case.sample_id))
    except KoboRedirectDenied as exc:
        raise AdministerError(exc.code, str(exc), 403) from exc
    except KoboNotConfigured as exc:
        raise AdministerError("kobo_not_configured", str(exc), 503) from exc
    advance_token_status(token, TokenStatus.SURVEY_STARTED)
    advance_case_on_respondent_event(case, WorkflowStatus.S07_SURVEY_STARTED)
    _log_contact(user, mode=mode, notes="Filled in the questionnaire with the respondent", sample_case=case)
    log_action("ra.administered", case, {"study": "QUAN", "sample_id": case.sample_id, "mode": mode, "ra_id": user.id}, user=user)
    return payload["kobo_form_url"]


def administer_kii(user, kii_id: str, *, mode: str, information_sheet_version: str, recording_consent: bool = False) -> str:
    """Record the informant's verbal participation consent if not already given (and recording consent, separately,
    only if they agreed to it), make this RA the interviewer, and return the KII Guide link."""
    from apps.consent.models import ConsentDecision, ConsentMethod, ConsentType
    from apps.consent.services import has_given_consent, latest_consent, record_consent
    from apps.kii.models import KIIStatus
    from apps.kii.services import build_kii_coding_url, kii_form_is_configured
    from apps.messaging.communications import visible_records

    if mode not in MODES:
        raise AdministerError("invalid_mode", "Choose a phone call or a WhatsApp call.")
    record = visible_records(user).filter(kii_id=kii_id).first()
    if record is None:
        raise AdministerError("not_found", "That KII record was not found, or is not assigned to you.", 404)
    if record.status in (KIIStatus.COMPLETED, KIIStatus.DECLINED):
        raise AdministerError("closed", f"This interview is {record.get_status_display().lower()}.", 409)
    current = latest_consent(record, ConsentType.PARTICIPATION)
    if current is not None and current.decision == ConsentDecision.WITHDRAWN:
        raise AdministerError("withdrawn", "This informant withdrew from the study.", 409)
    if not kii_form_is_configured():
        raise AdministerError("kobo_not_configured", "The KII Guide isn't connected yet.", 503)
    if not has_given_consent(record):
        consent = record_consent(kii_record=record, consent_type=ConsentType.PARTICIPATION, decision=ConsentDecision.GIVEN,
                                 information_sheet_version=information_sheet_version or "", method=ConsentMethod.VERBAL_RA_RECORDED)
        record.participation_consent = consent
    if recording_consent and not has_given_consent(record, ConsentType.KII_RECORDING):
        record.recording_consent = record_consent(kii_record=record, consent_type=ConsentType.KII_RECORDING,
                                                  decision=ConsentDecision.GIVEN, information_sheet_version=information_sheet_version or "",
                                                  method=ConsentMethod.VERBAL_RA_RECORDED)
    record.interviewer = user
    record.interview_date = record.interview_date or timezone.localdate()
    record.save()
    url = build_kii_coding_url(record)
    if url is None:
        raise AdministerError("consent_required", "Participation consent is required before the interview opens.", 403)
    _log_contact(user, mode=mode, notes="Interviewed the informant with the KII Guide", kii_record=record)
    log_action("ra.administered", record, {"study": "KII", "kii_id": record.kii_id, "mode": mode, "ra_id": user.id}, user=user)
    return url
