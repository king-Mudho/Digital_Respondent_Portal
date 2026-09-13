/**
 * Participant Information Sheet text, version v1.2.
 *
 * History:
 *   v1.0  Placeholder draft pending PI/ethics-office confirmation
 *         (docs/27_AGENT_EXECUTION_PLAN.md Phase 0).
 *   v1.1  Added the PI's real contact details and the ethics clearance
 *         reference (docs/00_PROJECT_MASTER.md, docs/18).
 *   v1.2  Added the PROIT disclosure (2026-09-13, PI-directed). PROIT is
 *         live and respondent-facing: the team may compile a profile of the
 *         respondent's organisation from public sources before contact, and
 *         the respondent is then asked to verify it. The verification screen
 *         explained this at the point of use, but the sheet the respondent
 *         consents on the basis of did not mention it at all -- a consent
 *         gap, not a UI one (docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md B2.1).
 *
 * IMPORTANT: this version bump closes that gap in the *text*. It does not
 * make the wording approved -- the PIS as a whole is still awaiting
 * PI/ethics-office sign-off (docs/31, docs/28). Bump the version whenever
 * the text changes; it is recorded against every ConsentRecord, so consent
 * stays traceable to the exact wording the respondent saw.
 */
export const PARTICIPANT_INFORMATION_SHEET_VERSION = "v1.2";

export const PARTICIPANT_INFORMATION_SHEET = `
This study is being carried out by Happyson Saina, a doctoral researcher at
Chinhoyi University of Technology, supervised by Dr L. Chikazhe and
Dr J. Kanyepe. It looks at how agribusinesses in Zimbabwe can become better
prepared for financing and investment. This study has received ethics
clearance from Chinhoyi University of Technology (Research Ethics Clearance
Letter, Annex 19, Form GRSD 17 SEBS/06/2025).

Your organisation has been selected to take part. If you agree, you will be
asked to complete a questionnaire about your organisation (around 15-25
minutes), either yourself online, or with help from a researcher by phone
or WhatsApp if you prefer.

Before contacting you, we may look up information about your organisation
that is already publicly available — for example from official registers,
published reports, or reputable news sources — so that we do not ask you
for facts that are already on record. Where we have done this, you will be
shown what we found and asked to confirm or correct it. You can also tell us
you do not know, that you would rather not say, or skip this step
altogether. It is there to save you time, not to test you. What you tell us
is always recorded separately from what we found, and your own answers take
precedence over it.

Taking part is voluntary. You can decline, or stop at any time, without any
consequence. Your answers are used for research purposes only — no score,
rating, or financing decision is generated or shown to you, and your
individual answers will never be shared with any lender or financial
institution.

Your name and contact details are kept separately from your answers and are
only used to manage your participation in this study (for example, to send
a reminder or arrange a call). Only the research team can see this
information. Results will only ever be reported in combined, anonymised
form.

If you have any questions, you can contact the research team: Happyson
Saina, phone 0773943709, email sales.proagromark2@gmail.com. The same
details are also included in your invitation message.
`.trim();
