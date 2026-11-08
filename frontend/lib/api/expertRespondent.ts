// An ABI panel expert's own link (backend apps/experts, 2026-11-08): the token on GET as ?t=, in the JSON body on POST,
// no admin proxy -- the same shape as the KII flow (kiiRespondent.ts).
import { apiFetch } from "./client";

export interface ExpertInvitation {
  status: "valid";
  expert_name: string;
  expert_id: string;
  consented: boolean;
  completed: boolean;
  information: { title: string; text: string }[];
  ethics_line: string;
  consent_statements: string[];
  information_sheet_version: string;
}

export function validateExpertToken(token: string) {
  return apiFetch<ExpertInvitation>(`/expert-invitations/validate/?t=${encodeURIComponent(token)}`);
}

export function submitExpertConsent(params: { token: string; decision: "GIVEN" | "DECLINED"; informationSheetVersion: string }) {
  return apiFetch<{ id: number; decision: string }>("/expert-consent/", {
    method: "POST",
    body: JSON.stringify({ token: params.token, decision: params.decision, information_sheet_version: params.informationSheetVersion }),
  });
}

export function getExpertQuestionnaireUrl(token: string) {
  return apiFetch<{ kobo_form_url: string }>(`/expert-invitations/kobo-redirect-url/?t=${encodeURIComponent(token)}`);
}
