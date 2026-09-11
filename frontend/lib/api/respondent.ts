import { apiFetch } from "./client";

export interface ValidateTokenResponse {
  status: "valid";
  organisation_name_confirmation: string;
  requires_eligibility_check: boolean;
}

export function validateToken(token: string) {
  return apiFetch<ValidateTokenResponse>(`/invitations/validate/?t=${encodeURIComponent(token)}`);
}

export interface EligibilityResponse {
  respondent_id: number;
  is_eligible: boolean;
}

export function submitEligibility(params: { token: string; fullName: string; roleCategory: string }) {
  return apiFetch<EligibilityResponse>("/eligibility/", {
    method: "POST",
    body: JSON.stringify({
      token: params.token,
      full_name: params.fullName,
      role_category: params.roleCategory,
    }),
  });
}

export type ConsentType = "PARTICIPATION" | "KII_RECORDING";
export type ConsentDecision = "GIVEN" | "DECLINED" | "WITHDRAWN";

export interface ConsentResponse {
  id: number;
  consent_type: ConsentType;
  decision: ConsentDecision;
}

export function submitConsent(params: {
  token: string;
  consentType: ConsentType;
  decision: ConsentDecision;
  informationSheetVersion: string;
}) {
  return apiFetch<ConsentResponse>("/consent/", {
    method: "POST",
    body: JSON.stringify({
      token: params.token,
      consent_type: params.consentType,
      decision: params.decision,
      information_sheet_version: params.informationSheetVersion,
      method: "WEB_CLICKTHROUGH",
    }),
  });
}

export interface KoboRedirectResponse {
  kobo_form_url: string;
  administration_mode: string;
}

export function getKoboRedirectUrl(params: {
  token: string;
  administrationMode: string;
  respondentRoleCategory: string;
  consentVersion: string;
}) {
  const query = new URLSearchParams({
    t: params.token,
    administration_mode: params.administrationMode,
    respondent_role_category: params.respondentRoleCategory,
    consent_version: params.consentVersion,
  });
  return apiFetch<KoboRedirectResponse>(`/kobo/redirect-url/?${query.toString()}`);
}

export interface AppointmentResponse {
  id: number;
  scheduled_for: string;
  mode: string;
  status: string;
}

export function requestAppointment(params: { token: string; scheduledFor: string; mode: string }) {
  return apiFetch<AppointmentResponse>("/appointments/", {
    method: "POST",
    body: JSON.stringify({
      token: params.token,
      scheduled_for: params.scheduledFor,
      mode: params.mode,
    }),
  });
}
