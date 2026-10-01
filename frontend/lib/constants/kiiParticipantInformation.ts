/**
 * Participant Information Sheet text for the KII self-service invitation flow
 * (/ki/[token]/information), version v1.0.
 *
 * Deliberately a SEPARATE document and version line from
 * PARTICIPANT_INFORMATION_SHEET_VERSION (participantInformation.ts), not a shared
 * constant bumped in place: the two describe different things a respondent is
 * agreeing to (a questionnaire vs. a Key Informant Interview), and ConsentRecord.
 * information_sheet_version must point unambiguously at the exact text a given
 * participant actually read. Conflating them would make that traceability wrong for
 * whichever flow didn't just change.
 *
 * Shares its substance with the Main-400 sheet where the substance is genuinely the
 * same (the study, supervisors, ethics clearance, the PROIT/AI-research disclosure,
 * voluntariness, no score/rating/financing decision, how contact details are kept,
 * the contact line) -- only the paragraph describing what taking part involves is
 * rewritten for an interview rather than a questionnaire, using the real duration
 * figures on the live KoboToolbox KII Guide ("Standard duration: 30-45 minutes.
 * Executive short form: 12-15 minutes.", confirmed 2026-10-01) rather than invented
 * ones. Does not mention being recorded: the self-service path this sheet is shown
 * on is unsupervised by design (docs/27_AGENT_EXECUTION_PLAN.md "KII self-service
 * invitation link") -- nobody records that session, so there is nothing to disclose
 * here. Interviewer-administered KIIs go through a verbal information/consent
 * process instead (ConsentMethod.VERBAL_RA_RECORDED), not this screen.
 *
 * History:
 *   v1.0  First version, drafted 2026-10-01 (PI-directed in the build session,
 *         after the Main-400 sheet was found to be shown verbatim on this screen --
 *         accurate in substance, but its "complete a questionnaire" wording didn't
 *         fit an interview). See docs/31_QA_THRESHOLDS_AND_PIS_SIGNOFF.md Part B-KII.
 *
 * Bump the version whenever the text changes; it is recorded against every
 * ConsentRecord for a KII self-service consent, so consent stays traceable to the
 * exact wording the participant saw.
 */
export const KII_PARTICIPANT_INFORMATION_SHEET_VERSION = "KII-v1.0";

export const KII_PARTICIPANT_INFORMATION_SHEET = `
This study is being carried out by Happyson Saina, a doctoral researcher at
Chinhoyi University of Technology, supervised by Dr L. Chikazhe and
Dr J. Kanyepe. It looks at how agribusinesses in Zimbabwe can become better
prepared for financing and investment. This study has received ethics
clearance from Chinhoyi University of Technology (Research Ethics Clearance
Letter, Annex 19, Form GRSD 17 SEBS/06/2025).

You have been invited to take part in a Key Informant Interview because of
your knowledge and experience relevant to agribusiness financing and food
systems transformation in Zimbabwe. If you agree, you can complete the
interview yourself, in your own time, using your personal link, or arrange
for a researcher to go through it with you instead, by phone, WhatsApp or
video call. It usually takes 30-45 minutes; a shorter 12-15 minute version
is available where appropriate.

Before contacting you, we may look up information about your organisation
that is already publicly available — for example from official registers,
published reports, or reputable news sources — so that we do not ask you
for facts that are already on record. Where we have done this, you will be
shown what we found and asked to confirm or correct it. You can also tell us
you do not know, that you would rather not say, or skip this step
altogether. It is there to save you time, not to test you. What you tell us
is always recorded separately from what we found, and your own answers take
precedence over it.

To help with this search we use an AI tool provided by a company outside
Zimbabwe. It is given the name and details of your organisation and your name
and job title, so that it can find what is published about your organisation
and your professional role. It is never given your telephone number, email
address, or anything you tell us in the interview. A member of the research
team checks everything it finds against its source before we use it, and we
never record private information.

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
Saina, phone 0773943709, email abffst.research@gmail.com. The same
details are also included in your invitation message.
`.trim();
