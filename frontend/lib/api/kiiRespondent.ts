// KII self-service invitation respondent flow (2026-10-01) -- same shape as
// lib/api/respondent.ts (token as ?t= on GET, in the JSON body on POST, no
// admin proxy), hitting the separate kii-invitations/ and kii-consent/
// endpoints (apps/kii/urls.py) rather than the Main-400 ones.
import { apiFetch } from "./client";

export interface ValidateKIITokenResponse {
  status: "valid";
  participant_name: string;
}

export function validateKIIToken(token: string) {
  return apiFetch<ValidateKIITokenResponse>(`/kii-invitations/validate/?t=${encodeURIComponent(token)}`);
}

export type ConsentDecision = "GIVEN" | "DECLINED";

export interface KIIConsentResponse {
  id: number;
  consent_type: string;
  decision: ConsentDecision;
}

export function submitKIIConsent(params: { token: string; decision: ConsentDecision; informationSheetVersion: string }) {
  return apiFetch<KIIConsentResponse>("/kii-consent/", {
    method: "POST",
    body: JSON.stringify({
      token: params.token,
      decision: params.decision,
      information_sheet_version: params.informationSheetVersion,
    }),
  });
}

export interface KIIKoboRedirectResponse {
  kobo_form_url: string;
}

export function getKIIKoboRedirectUrl(token: string) {
  return apiFetch<KIIKoboRedirectResponse>(`/kii-invitations/kobo-redirect-url/?t=${encodeURIComponent(token)}`);
}
