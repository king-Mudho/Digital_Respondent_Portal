import { ApiError } from "./client";

/**
 * Turns any failure on the respondent-facing flow into something a
 * respondent can actually act on.
 *
 * Every step of this flow previously wrapped its submit in try/finally
 * with no catch, so a failed request -- an expired token, a throttled
 * request, a dropped connection -- left the button re-enabled and the
 * page unchanged. The respondent has no support channel open in front of
 * them and no reason to suspect an error happened at all; they just see
 * a button that does nothing, and abandon.
 *
 * These messages deliberately avoid HTTP or backend vocabulary and never
 * blame the respondent.
 */
const MESSAGES: Record<string, string> = {
  token_invalid: "This invitation link is no longer valid. Please contact the research team using the details in your invitation.",
  token_expired: "This invitation link has expired. Please contact the research team for a new one.",
  token_revoked: "This invitation is no longer active. Please contact the research team if you think this is a mistake.",
  throttled: "We've had a lot of requests from your connection. Please wait about a minute and try again.",
  consent_required: "We couldn't confirm your consent was recorded. Please go back and try the consent step again.",
  eligibility_required: "We couldn't confirm your role for this study. Please contact the research team using the details in your invitation.",
};

const FALLBACK = "Something went wrong on our side. Please try again in a moment — if it keeps happening, contact the research team using the details in your invitation.";

export function respondentErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? FALLBACK;
  }
  return FALLBACK;
}
