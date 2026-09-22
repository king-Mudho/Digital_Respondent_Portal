// Step-by-step procedures. Each export is a list of blocks, reused by the
// system manual and by whichever role guides need that task.
const { SITE, MODES_TABLE } = require("./common");

const T = {};

T.dashboards = [
  ["h2", "Reading the dashboards"],
  ["p", "Dashboards are for monitoring; nothing on them changes data. Figures refresh whenever the screen is opened."],
  ["img", "adm_exec_dashboard.jpg", "Executive Dashboard: completions against the 400 / 60 / 50–75 targets, days to data lock, spend, and the lowest-filled strata."],
  ["table", ["Dashboard", "What it tells you", "Use it to"], [
    ["Executive", "QUAN completed out of 400, KII completed out of 60, documents coded against 50–75, days to the 30 November 2026 data lock, spend to date, lowest-filled strata.", "See overall progress and where fieldwork attention is most needed."],
    ["Sampling", "Main cases by province, verified/total by stratum, Reserve activations by reason.", "Check the design stays balanced across strata."],
    ["Contact", "Organisations verified, eligible respondents identified, invitations sent and opened, upcoming appointments, refusals, unreachable cases.", "Track outreach and spot stalled contact."],
    ["QA Dashboard", "Submissions today and in total, the open QA queue, decisions recorded, completions by administration mode.", "Keep the QA backlog under control."],
    ["KII/Doc Dashboard", "KII completed against 60; KIIs by status; documents by type and QA status.", "Track the qualitative and documentary strands."],
  ], [0.18, 0.5, 0.32]],
  ["tip", "Targets versus records", "The registers hold more records than the targets (for example 90 KII records for 60 completed interviews). The surplus is reserve depth for non-response, not extra work."],
];

T.reports = [
  ["h2", "Using Reports (analytics and charts)"],
  ["steps", [
    { text: "Select **Reports** in the top bar.", img: "adm_reports_top.jpg", caption: "Reports: headline figures for the chosen period." },
    "Choose the period with **Last 7 days**, **Last 30 days**, **Last 90 days** or **All time**. Case progress (the funnel and workflow) is always cumulative; time-based figures such as submissions per day follow the period.",
    { text: "Read the headline cards: questionnaires submitted, passed QA, response rate (submitted ÷ invited), median completion time, follow-ups sent, withdrawals, Reserves activated, and fieldwork cost per QA-passed case.", img: "adm_reports_funnel.jpg", caption: "Case funnel: each case counted once at every stage it has reached." },
    { text: "Select **Show table** on any chart to see the exact numbers, for example to copy them into a progress report.", img: "adm_reports_funnel_table.jpg", caption: "The same chart as a table." },
    { text: "Use **Coverage** to see, by province, organisation type and size, what share of cases have been invited and have submitted. Short bars show where contact effort should go next.", img: "adm_reports_coverage.jpg", caption: "Coverage by group." },
    { text: "Check **How questionnaires were completed**. If one administration mode dominates (more than 70% once at least 10 questionnaires are in), the chart shows an imbalance alert so the team can review the mix.", img: "adm_reports_modes.jpg", caption: "Administration modes." },
    { text: "Review **Time to complete the questionnaire** and **QA outcomes**. Very short or very long completions are what the QA duration rules flag.", img: "adm_reports_duration.jpg", caption: "Completion-time distribution." },
  ]],
  ["p", "Reports show counts and rates only — never names or answers — so they are safe to discuss with supervisors."],
];

T.bulkVerify = [
  ["h2", "Moving cases through verification (bulk)"],
  ["p", "Every Main case must reach **S03 Eligible respondent identified** before it is invited, otherwise its status will not follow the respondent and no reminders are offered. Verification (S00 → S01 → S02 → S03) can be done for all cases at a step at once."],
  ["steps", [
    "Open **Main-400 Register**.",
    { text: "In **Move cases through verification**, choose the step, for example **S00 Selected → S01 Verification required**. The button shows how many Main cases are at that step, e.g. **Move all 48**.", img: "adm_bulk_verification.jpg", caption: "The bulk verification tool on the register." },
    "Select the button and confirm. Each case is moved individually and each move is written to the audit log under your name.",
    "Repeat for **S01 → S02** and **S02 → S03**.",
  ]],
  ["warn", "Only verification is bulk", "Statuses from S04 onwards follow real events (invitation sent, link opened, questionnaire submitted, QA decision) or an individual decision on the case page. They are never changed in bulk."],
];

T.registerOrg = [
  ["h2", "Registering a new organisation and its sample case"],
  ["p", "The approved registers are already loaded. Use this only for a late addition, replacement or correction."],
  ["steps", [
    { text: "Select **Organisations** in the top bar.", img: "adm_organisations.jpg", caption: "Register Organisation: the form (top) and the list of registered organisations (below)." },
    "Complete **Name**, **District**, **Province**, **Entity type**, **Actor family**, **Value chain** and **Size class**. Province, actor family and size class decide the stratum, so check them carefully.",
    "Select **Register organisation**. The Master ID (e.g. MID-HA-000012) is generated automatically.",
    "When offered, choose **Main** or **Reserve** and select **Create sample case**. The Sample ID is generated and the new case page opens. You can also create the case later from the organisation's row in the list.",
    "For a Main case, register its Reserve counterpart in the **same province, actor family and size class**, then pair them (next procedure).",
  ]],
];

T.pairAssign = [
  ["h2", "Pairing a Main case with its Reserve, and assigning a Contact RA"],
  ["steps", [
    "Open the Main case (**Main-400 Register → View**).",
    { text: "In **Assigned Contact RA**, choose the RA from the list. The change saves straight away and shows **Currently: <name>**. That RA now sees the case; other Contact RAs do not.", img: "adm_case_assign.jpg", caption: "Assigned Contact RA." },
    { text: "In **Matched Reserve case**, choose the Reserve. Only locked Reserves not already paired are offered, same-stratum ones first. A cross-stratum choice is allowed but flagged in the audit log.", img: "adm_case_reserve.jpg", caption: "Matched Reserve case." },
  ]],
];

T.respondents = [
  ["h2", "Recording the respondent and their contact details"],
  ["p", "Invitations and reminders need a phone or WhatsApp number. Record the eligible person as soon as they are identified."],
  ["steps", [
    "Open the case (**Main-400 Register → View**) and find **Respondents and contact details**.",
    { text: "Select **Add a person**. Enter **Full name**, **Phone**, **WhatsApp number**, **Email**, and a **Gatekeeper name** and **Gatekeeper contact** if you reach the person through a PA or receptionist.", img: "adm_case_add_person.jpg", caption: "Adding a person to a case." },
    "Choose their **role** and the eligibility decision: **Eligible (I screened them)**, **Not eligible**, or **Not yet screened**.",
    "Select **Save person**. To correct details later, select **Edit** beside the person, change the fields, then **Save changes**.",
    "Write WhatsApp numbers in international form, e.g. **+263 77 123 4567**, so the WhatsApp buttons open the right chat.",
  ]],
  ["tip", "Who is eligible?", "Owner or founder, CEO or managing director, finance/credit/risk, operations, strategy/business development, supply chain/commercial, or another senior manager who can answer for the organisation. Anyone else should nominate the right person."],
];

T.invite = [
  ["h2", "Sending an invitation"],
  ["steps", [
    "Open the case. Check the status is **S03** and a respondent with a number is recorded.",
    { text: "In **Invitations**, leave **Channel** as **WHATSAPP** (or choose EMAIL, SMS, PRINTED_CODE or QR to record how it was delivered) and **Wave** as **1**. Select **Send invitation**.", img: "cra_case_invitations_before.jpg", caption: "Invitations panel before sending, with the history of earlier invitations." },
    { text: "The personal link and 8-character manual code appear **once**, with the invitation already written for each channel. Choose **WhatsApp message**, **SMS message** or **Email message** to see exactly what will be sent: the personal link, its expiry date, the manual code and the study contact line.", img: "cra_case_invitation_sent.jpg", caption: "The link, manual code and ready-written messages are shown once, with a send button for each channel." },
    { text: "Send it on the channel that suits the respondent:", sub: [
      "**Send via WhatsApp** opens that respondent's chat (their WhatsApp number, or phone number if none) with the message ready. Check you are on the study WhatsApp number, then press Send.",
      "**Send by SMS** opens the phone's messages app addressed to the respondent, with the shorter SMS message. Use it on a phone.",
      "**Email from study address** sends the email from abffst.research@gmail.com to the respondent's email on file; replies go to the study inbox. The email is recorded in the audit log.",
      "**Open in email app** opens the same email in your own mail program, if you need to add something first.",
      "**Copy message** copies the message shown, for any other channel.",
    ] },
    "If a button says no number or email is on file, add it under **Respondents and contact details**, then send a new invitation.",
    "The case moves to **S05 Invitation sent** automatically. Log the attempt in **Contact timeline** (see Logging a contact attempt).",
  ]],
  ["warn", "The link is shown only once", [
    "The portal stores only a scrambled fingerprint of the link, so nobody can display it again. If you close the page before sending, select **Send new invitation (replaces current)**: this issues a fresh link and the old one stops working immediately.",
    "Links are valid for **14 days**. Each link belongs to one organisation; never forward one respondent's link to another organisation.",
  ]],
  ["h3", "Revoking an invitation"],
  ["p", "In the invitation history, select **Revoke** on an open invitation (for example, if it was sent to the wrong number). The link stops working at once. Issue a new one if the case should still be invited."],
];

T.phoneAssisted = [
  ["h2", "Phone, WhatsApp-call or face-to-face administration"],
  ["p", "When the respondent prefers help, the researcher completes the questionnaire with them. The respondent must still hear the participant information and agree before any question is asked."],
  ["steps", [
    "Agree a time. If the respondent booked through the portal, it is in **Appointments**.",
    "At the start of the call, confirm the organisation and the person's role, read or summarise the Participant Information Sheet (v1.3) and ask for consent. Stop if they decline.",
    "Open the respondent's personal invitation link on your device and go through the portal screens with them (organisation, role, information, consent), choosing the answers they give you.",
    "Open the questionnaire from the portal so the case identifiers travel with the form, and complete it with the respondent. Never start the KoboToolbox form from a bookmark: a submission without the portal's link is set aside and not matched.",
    "After submitting, log the contact attempt with outcome **COMPLETED**, and mark the appointment **COMPLETED**.",
  ]],
  ["table", ["Code", "Mode", "What happens"], MODES_TABLE, [0.1, 0.35, 0.55]],
];

T.logContact = [
  ["h2", "Logging a contact attempt"],
  ["p", "Record **every** attempt, successful or not. The Contact Dashboard, Reports and any later replacement decision rely on it."],
  ["steps", [
    { text: "On the case page, scroll to **Contact timeline → Log a contact attempt**.", img: "adm_case_timeline.jpg", caption: "Contact timeline and the form for logging an attempt." },
    "Choose the **channel** (WHATSAPP, EMAIL, PHONE, SMS, FACE_TO_FACE) and the **outcome** (REACHED, NO_ANSWER, WRONG_NUMBER, REFUSED, RESCHEDULED, COMPLETED).",
    "Add a short, factual note (optional), e.g. \"PA says MD travelling; call back Thursday\". Do not record opinions about the person.",
    "Select **Log contact attempt**. The entry appears at the top of the timeline with the date and time.",
  ]],
];

T.followUps = [
  ["h2", "Sending follow-up reminders"],
  ["p", "Approved reminders fall due on **Day 2** and **Day 7** after an invitation for respondents who have not yet submitted. Until automatic WhatsApp sending is connected, a person sends each one."],
  ["steps", [
    { text: "Select **Follow-ups**. Each card shows the case, organisation, which reminder is due, when the invitation went out, the respondent and their number, and the exact approved message.", img: "cra_follow_ups.jpg", caption: "Follow-ups due. Contact RAs see only their own cases." },
    "Select **Open in WhatsApp**. WhatsApp opens with the message ready for that number; send it. If the card says **no number on file**, the button reads **Open WhatsApp (choose contact)** — pick the chat yourself, and add the number to the case afterwards.",
    "Come back and select **Mark as sent**. The card disappears and the reminder is recorded under your name.",
  ]],
  ["warn", "Mark as sent only after sending", "A case can become **S13 Nonresponse** (and be replaced by its Reserve) only after every reminder has been recorded as sent. Marking a reminder you did not send could lead to an organisation being replaced without being contacted."],
];

T.appointments = [
  ["h2", "Managing appointments"],
  ["steps", [
    { text: "Select **Appointments**. Each row shows the case (Sample ID and organisation) or KII, the requested time, the mode (PHONE, WHATSAPP_VOICE, ZOOM, …) and the status.", img: "cra_appointments.jpg", caption: "Appointment Queue." },
    "Use **Filter by status** to show, for example, only **REQUESTED** appointments.",
    "Contact the respondent to confirm, then select **CONFIRMED**.",
    "After the session select **COMPLETED**, or **MISSED** if they did not attend, or **CANCELLED**. Only valid next steps are shown; a finished appointment shows **No further action**.",
  ]],
];

T.reassign = [
  ["h2", "Reassigning cases between Contact RAs"],
  ["p", "Use **Reassign cases** on the Main-400 Register to hand many cases to a Contact RA at once — for example when new RAs start, or when an RA leaves. For a single case, use **Assigned Contact RA** on the case page."],
  ["steps", [
    "Open **Main-400 Register** and find **Reassign cases** (below the verification tool).",
    { text: "Choose **From** (Anyone, Unassigned, or a Contact RA), a **Province** or All provinces, and **To** (the Contact RA receiving the cases, or Nobody to unassign).", img: "adm_reassign.jpg", caption: "Reassign cases: the button shows how many cases will move." },
    "To split a large province, type a number in **How many**. Cases move in Sample ID order, so move part of the province to one RA, then the rest to the next.",
    "Select **Move N cases** and confirm. The move is written to the audit log with every Sample ID.",
  ]],
  ["tip", "What the RA sees", "A Contact RA sees only the cases assigned to them, including on Follow-ups. Reassigning a case moves its reminders with it."],
];

T.workflow = [
  ["h2", "Changing a case's status by hand"],
  ["p", "Most statuses move automatically. Use **Advance workflow status** on the case page only for decisions a person makes, such as recording that an organisation is ineligible or has refused."],
  ["steps", [
    { text: "On the case page, find **Advance workflow status**. Only the transitions allowed from the current status are shown, e.g. **→ S04** or **→ S14**.", img: "adm_case_workflow.jpg", caption: "Only valid next statuses are offered." },
    "Log a contact attempt or note explaining the decision first.",
    "Select the new status. The change is audited.",
  ]],
  ["table", ["From", "Can move to"], [
    ["S00", "S01"], ["S01", "S02, S15"], ["S02", "S03, S14, S15"], ["S03", "S04, S14"], ["S04", "S05"],
    ["S05, S06, S07", "Next step, S12 Refused, S13 Nonresponse"], ["S08", "S09, S10"], ["S09", "S10"], ["S10", "S11"],
    ["S12–S15", "S16 Reserve eligible for activation"],
  ], [0.3, 0.7]],
];

T.withdrawal = [
  ["h2", "Recording a withdrawal"],
  ["p", "A participant may withdraw at any time, for any reason, without giving one."],
  ["steps", [
    "Stop contacting the person immediately.",
    { text: "On the case page, in **Record a withdrawal**, choose **How they told us** — **By phone or in person**, or **In writing (WhatsApp, email, letter)** — and type the reason or their own words.", img: "adm_case_withdrawal.jpg", caption: "Record a withdrawal." },
    "Select **Record withdrawal** and confirm.",
  ]],
  ["p", "In one step the portal records the withdrawal, stops the invitation link and all reminders, moves the case to **S12 Refused** where allowed, erases the phone, WhatsApp, email and gatekeeper contact, and flags the case as `consent_withdrawn` in every export. This cannot be undone."],
  ["tip", "Answers already submitted", "PI decision (15 September 2026): a questionnaire submitted before the withdrawal is **kept for the audit trail but never analysed**. It is left out of the de-identified analysis export automatically, flagged `consent_withdrawn` in the operational export, and marked in the PI's KoboToolbox workbook (README count and `portal_consent_withdrawn` = TRUE) and PDF ZIP (file name starts `WITHDRAWN-`)."],
];

T.notEligible = [
  ["h2", "When the person is not the right respondent"],
  ["bullets", [
    "If someone chooses **None of these describe me**, the portal thanks them and the questionnaire never opens. No answers are recorded.",
    "Ask them politely to nominate the right senior person, record that person under **Respondents and contact details**, and send a new invitation.",
    "If nobody suitable exists, record the reason in the contact timeline and move the case to **S14 Ineligible** (Field Coordinator or PI).",
  ]],
];

T.reserve = [
  ["h2", "Activating a Reserve case"],
  ["p", "A Reserve replaces its Main case only after the Main case reaches a drop state (S12 Refused, S13 Nonresponse, S14 Ineligible or S15 Duplicate/inactive) and there is evidence."],
  ["steps", [
    { text: "Select **Reserve Activation**. Every locked Reserve is listed with a search box.", img: "adm_reserve.jpg", caption: "Reserve Activation." },
    "Find the Reserve matched to the dropped Main case (the Main case page shows the pairing).",
    "Choose the authorised reason: **Ineligible**, **Inactive**, **Duplicate**, **Refusal** or **Nonresponse exhausted**. There is deliberately no \"other\".",
    "Write the **Evidence note (required)**, e.g. \"MD declined by phone 12 Sep, logged in contact timeline\".",
    "Select **Activate this reserve**. The Reserve becomes invitable and is worked like any Main case, starting with verification.",
  ]],
];

T.proit = [
  ["h2", "Building a pre-interview profile (PROIT), with AI research"],
  ["p", "PROIT lets the respondent confirm facts already on public record instead of answering them from scratch, and lets the interviewer ask only what is **not** public. It never pre-fills, skips or infers any scale item (ABI, NFM, Digital Readiness, FST): only descriptive background. This applies to the questionnaire and to the KIIs alike."],
  ["h3", "Step 1: let the AI search public sources"],
  ["steps", [
    "On the case page (or KII page), in **Pre-Interview Profile (PROIT)**, select **Start background research**.",
    { text: "In the **AI research from public sources** box, select **Research with AI**. The AI searches the public web for the organisation, and for the respondent's published professional role, and works in the background for a few minutes. You can leave the page and come back.", img: "proit_ai_research.jpg", caption: "AI research: proposals to review, each with its sources." },
    "Under **To review**, read each proposal. It gives the fact, a confidence level, and every source it used with the publisher, the date, the authority tier and a short quote copied from the page. Select the source title to open the page and check it yourself.",
    "Decide on each one. **Accept** puts it into the profile with its sources. Edit the wording first if it needs correcting, then **Accept**. **Reject** discards it. Nothing enters the profile until you accept it. Take special care where the note says the organisation may be a different one with a similar name.",
    "Read **Not found publicly: ask the respondent**. These are the facts the AI could not find in any public source. They become the questions the interviewer asks in full.",
  ]],
  ["tip", "Cost", "PROIT research is a paid request on the study's AI account, run on a lower-cost model than document drafting (about USD 1-3 per organisation researched). Research the organisations that need it rather than re-running it on the same one."],
  ["warn", "The AI proposes, you decide", [
    "The AI only suggests. Every fact still needs a source, a person to accept it and a second person to lock the profile, exactly as if you had typed it in.",
    "Only sources the search actually returned can be cited. A fact with no verifiable source is turned into “not found publicly”, and anything that looks private is removed automatically. The AI never records health, religion, ethnicity, politics, family, home addresses, personal phone numbers or emails, private finances, or anything from personal social-media pages.",
    "What is sent to the AI provider's search: the organisation's name, province, district and type, and the respondent's name and role. Never a phone number, email, gatekeeper or any other contact detail.",
  ]],
  ["h3", "Step 2: add or correct facts by hand"],
  ["steps", [
    { text: "Under **Add a background field**, choose a field in **Select a field…**, type **What was found (documentary value)**, and select **Add field**.", img: "adm_case_proit_draft.jpg", caption: "A draft profile: each fact needs at least one source." },
    "For each field, type the **Source title** (e.g. companies registry entry), choose the confidence (HIGH, MODERATE, LOW) and the authority tier — Tier 1 statutory register or audited report, Tier 2 official website or association record, Tier 3 reputable media or professional profile, Tier 4 corroborated public platform content — then select **Add source**.",
    "Use **Researcher review screen** to check the whole profile, including gaps and contradictions.",
    "A second researcher reviews it and selects **Lock pre-profile**. Only a locked profile is used with the respondent, who confirms, corrects, or says they don't know, prefer not to say, or it is not applicable. The public value, the respondent's answer and the reconciled value are kept separately.",
  ]],
];

T.proitInterview = [
  ["h2", "Verifying a profile with the respondent, and reconciling it afterwards"],
  ["p", "Once a profile is locked, the interview has two duties: confirm what is public, and ask what is not. The **Interview sheet** is where you do both, and where the results are reconciled afterwards. It appears on the locked profile on the case page (coordinator and PI), on the case page of an assisted interview (Contact RA) and on the KII record (KII RA). Nothing here changes the public value."],
  ["steps", [
    { text: "Open the case (or the KII record) and find **Interview sheet: confirm what is public, ask what is not**. Each row is one fact and is marked **Confirm**, **Confirm, then probe** or **Ask**.", img: "proit_interview_sheet.jpg", caption: "The interview sheet: confirm what is public, ask what is not." },
    "For a **Confirm** row, read the public fact to the respondent, with its source shown under it, and ask whether it is right. Never state a fact on an **Ask** row: it is a question, not something established. A weak source's value is deliberately hidden.",
    "In **What the respondent said**, choose the answer: confirmed, corrected, partly correct or out of date, does not know, prefers not to say, or does not apply. For a correction, type **Their answer**. Add a comment if useful, then select **Save answer**.",
    "For an **Ask** row, choose **They told us** and type what they said, or record that they do not know or would rather not say.",
    "When the interview is over, select **Interview finished**.",
  ]],
  ["h3", "After the interview: reconcile (coordinator and PI)"],
  ["steps", [
    { text: "Rows where the respondent corrected or qualified a fact show **Differs from the public source**. Under **Reconciled value (required)**, type the value you code for analysis, then select **Save reconciled value**. A plain confirmation or “does not apply” needs no reconciled value.", img: "proit_reconcile.jpg", caption: "Reconciling a corrected fact: the three values stay separate." },
    "The status at the top of the sheet counts up: “Verified 6 of 8 · settled 5 of 8”, then **Reconciled** when every fact is settled. At that moment the portal also sends the whole profile (what was known, what the respondent said, the reconciled value, and the sources) to KoboToolbox, in the **ABF-FST PROIT Interview Profile** form, and the status shows **Saved to KoboToolbox**.",
    "If reconciliation truly cannot be finished (for example the respondent cannot be reached again), select **Record a protocol deviation** and give the reason. The case is released but stays flagged.",
  ]],
  ["warn", "A case is not complete until its profile is reconciled", [
    "QA cannot **Accept** a questionnaire, and a KII's coding cannot become COMPLETE, while a locked profile still has facts not verified with the respondent or not reconciled. The message says how many are outstanding. Re-query and Reject are never blocked.",
    "This applies only to a case that has a locked profile with facts on it. A case with no profile is not held up.",
  ]],
];

T.qaReview = [
  ["h2", "Reviewing questionnaires in the QA Queue"],
  ["steps", [
    { text: "Select **QA Queue**. Each submission shows the Sample ID, when it was submitted, the administration mode, the completion time in minutes and its QA status (PENDING or QUERY).", img: "qa_queue.jpg", caption: "QUAN QA Queue with the KoboToolbox sync panel." },
    "Open the completed form to check the answers: **Form PDFs → Download PDF**, or the **Completed questionnaire** panel on the case page.",
    "Check it against the QA rules (table below) and any open QA exception for that case.",
    "Write a **Note (required)** explaining your decision.",
    "Select **Accept** (moves the case to S10 QA passed), **Re-query** (S09 QA query — follow up with the respondent or the RA who administered it) or **Reject** (not usable).",
  ]],
  ["table", ["Rule", "Setting", "Effect"], [
    ["Required answers missing", "65 required fields from the live questionnaire", "Hard stop: raises an exception; cannot pass without a human decision and note."],
    ["Too quick", "Completed in under 5 minutes (300 s)", "Soft flag for review."],
    ["Too slow", "Completed in over 90 minutes (5400 s)", "Soft flag for review."],
    ["Possible duplicate", "Another submission for the same organisation within 24 hours", "Soft flag for review."],
  ], [0.25, 0.4, 0.35]],
  ["tip", "Nothing passes automatically", "Even a submission with no flags needs a person to select Accept. Every decision and its note is audited."],
  ["h3", "Pulling new submissions now"],
  ["p", "Submissions arrive within seconds (KoboToolbox notifies the portal) and a full check runs every 15 minutes between 06:00 and 22:00 and hourly overnight. To check immediately, select **Sync now** in **KoboToolbox sync**; the panel shows the last run, how many were pulled and how many were new or updated. An edited submission returns to the queue for review."],
];

T.qaExceptions = [
  ["h2", "Working QA exceptions"],
  ["steps", [
    { text: "Select **QA Exceptions**. Each card shows the rule that fired (for example `hard_stop_missing_required_fields` or `min_plausible_duration_seconds`), the Sample ID, when it was raised and its status. Oldest first.", img: "qa_exceptions.jpg", caption: "QA Exception Queue." },
    "Tick **Only mine** to see exceptions assigned to you; tick **Show closed** to include resolved ones.",
    "Use **Assign to** to take ownership (or give it to a colleague). The status becomes **In progress**.",
    "Investigate: open the form PDF, check the case timeline, contact the respondent if needed.",
    "Type **What was done about it?** and select **Resolved**, or **Not a real problem** if the flag was a false alarm. A note is always required.",
  ]],
];

T.formPdfs = (formName, shot = "qa_form_pdfs.jpg", caption = "Completed form PDFs.") => [
  ["h2", "Downloading or emailing completed forms (Form PDFs)"],
  ["steps", [
    { text: `Select **Form PDFs**. You see the completed ${formName} forms from KoboToolbox, newest first, 20 per page to begin with (choose more under **Show** at the foot of the list).`, img: shot, caption },
    "Select **Download PDF** to save a readable copy: sections, questions, the chosen answers as words (not codes) and repeated groups.",
    "Select **Email to me** to send the PDF to the email address on your account.",
    "For the questionnaire only, select **Email to respondent** to send the respondent a copy of their own answers at the email address recorded on the case (only while their consent stands). You are asked to confirm first. Every email is audited with the address masked.",
  ]],
  ["p", "At the top of the page, a sync panel shows whether the portal holds the same forms as KoboToolbox, for example “✓ In sync with KoboToolbox — KoboToolbox holds 12 · the portal holds 12”. Each row also says “✓ saved in portal” once the portal has an identical copy. If the panel says “Not in sync”, select **Sync now** (read-only roles see the panel but not the button); it takes a few seconds."],
  ["p", "The same PDF is available from the record itself: the case page (questionnaire), the KII page (KII Guide) or the document page (coding form)."],
  ["tip", "How the sync works", "The portal keeps its own copy of the questionnaire, KII Guide and Document Analysis Tool, and refreshes it every 15 minutes and whenever someone selects Sync now. A submission edited in KoboToolbox is updated here; one deleted in KoboToolbox is flagged as removed. You never need to sync before downloading a PDF: the PDF is always read from KoboToolbox at that moment."],
];

T.kii = [
  ["h2", "Creating a KII record"],
  ["steps", [
    { text: "Select **KII Register → New KII record**.", img: "kii_new.jpg", caption: "New KII Record." },
    "Enter **Stakeholder category**, **Participant name**, **Participant role** and **Preferred mode**, then select **Create KII record**. The KII ID (e.g. KII-0026) is generated.",
  ]],
  ["h2", "Taking a KII from invitation to coded transcript"],
  ["steps", [
    { text: "In **KII Register**, select **Manage** on the record.", img: "kii_register.jpg", caption: "KII Register." },
    { text: "Move the **Status** as things happen: PROSPECT → INVITED → SCHEDULED → COMPLETED, or DECLINED / NO_SHOW. Only valid next statuses are shown; NO_SHOW can be rescheduled.", img: "kii_detail.jpg", caption: "KII record: status, consent, transcript and coding." },
    "Before the interview starts, select **Record participation consent**. If the interview will be recorded, also select **Record recording consent** — the two are always separate.",
    "When marking **COMPLETED**, tick **Recording made** only if a recording exists. The portal refuses a recorded completion without recording consent.",
    "Advance **Transcript** (NOT_STARTED → IN_PROGRESS → VERIFIED → ANONYMISED) and **Coding** (NOT_STARTED → IN_PROGRESS → COMPLETE) as the work progresses.",
    "Complete the **KII Guide** form in KoboToolbox using the KII ID (see the next section). The **Completed KII form (KoboToolbox)** panel then links to its PDF, and at the next sync (within 15 minutes, or at once with **Sync now** on **Form PDFs**) the portal sets **Coding** to COMPLETE for you.",
  ]],
  ["h2", "Opening the KII Guide with the KII ID filled in"],
  ["steps", [
    { text: "Record **participation consent** first. Until you do, the **Coding** panel says “Record participation consent first” and the interview link is withheld.", img: "kii_coding_locked.jpg", caption: "Before consent: no interview link." },
    { text: "Once consent is recorded, the panel offers **Continue this interview**. Select it: the KoboToolbox KII Guide opens in a new tab with the KII ID already entered, so it can never be mistyped and the completed form always matches this record.", img: "kii_coding_ready.jpg", caption: "After consent: Continue this interview." },
    "Complete the interview in the form as usual.",
  ]],
  ["tip", "What the link carries", "Only the KII ID and your own username. It never carries the participant's name, role or organisation, so nothing identifying is left in a web address or your browser history."],
];

T.documents = [
  ["h2", "The fastest way: upload the document (Quick add)"],
  ["p", "You do not need to type the details of a document. Upload it and the AI reads it, fills in the record, drafts the whole KoboToolbox coding form, and waits for you to review. (This needs AI drafting to be switched on; otherwise use “Adding a document by hand” below.)"],
  ["steps", [
    { text: "Select **Documents → New document**. At the top is the box **Fastest: upload the document**.", img: "doc_new.jpg", caption: "New document: upload the file and let the AI do the rest." },
    "Choose the file: a PDF, a Word (.docx) or Excel (.xlsx) file, a text or CSV file, or a JPG or PNG scan or photo (up to 20 MB). Nothing else is required.",
    "Optional (open **Optional: title, pages to read**): a **Title** if you want your own; **Pages to read** if you are coding one chapter of a long PDF, for example `290-340`; or tick **Read the whole document in parts** for a PDF over 100 pages (see “Coding a very long document” below).",
    "Select **Upload and auto-fill**. The record is created straight away and the review screen opens, showing “Step 1 of 2: reading the document’s details”, then “Step 2 of 2: drafting the coding form”. You can leave the page; the draft will be there when you return.",
    "The AI has filled in the title, author, date, document type, geographic scope, value chain and source it found in the document, and left blank anything the document does not state. Check them on the record page under **Record details** and correct anything wrong; a correction shows in the draft at once and is used when you submit.",
    "You still make the human decisions: assess **authenticity** (Verified or Disputed) and **Include** or **Exclude** the document, as described below.",
    "Review every section of the draft, **Save changes**, then **Submit to KoboToolbox** (see “Auto-fill: the AI drafts, you review”). The portal keeps its own copy of the completed form; **Sync now** on **Form PDFs** confirms the portal and KoboToolbox match.",
  ]],
  ["h2", "Coding another chapter of the same document (Copy for another chapter)"],
  ["p", "A long report holds several evidence units. Give each chapter you want coded its own record, so each gets its own ratings, its own DOC ID and its own row in the export. You do not upload the file again or retype the details:"],
  ["steps", [
    { text: "Open the record of the document and, under **Copy for another chapter**, enter the chapter's **Pages to read** (for example `290-340`) and, if you like, a **Chapter title**. Leave the title empty and the AI names the part from its pages, for example “Title – Chapter 6: Agriculture (pp. 290-340)”.", img: "doc_copy_chapter.jpg", caption: "Copy for another chapter: pages, and an optional title." },
    "Select **Copy and auto-fill** (or **Copy record** if AI drafting is not switched on). A new record is created with the same author, date, source, type and scope, and **its own copy of the file**, so removing or replacing one file never affects the other.",
    "With AI drafting on, the new record's review screen opens and the AI starts drafting that chapter. Review, save and submit it as usual.",
    "Authenticity and Include or Exclude are **not** copied: assess each chapter on its own. Repeat for every chapter you want coded.",
  ]],
  ["tip", "Copy needs a file", "The **Copy for another chapter** panel appears once a record has its source file. A title or pages is required, and a long PDF needs a page range (or the whole-document option). If the pages are not valid nothing is created."],
  ["h2", "Adding a document by hand"],
  ["steps", [
    "Select **Documents → New document** and, below **Or enter the details yourself**, fill in **Title**, **Author / speaker**, **Source URL / reference**, **Document type** (OFFICIAL, SECONDARY or PLATFORM), **Geographic scope** and an **Evidence extract**, then select **Create document record**. The document ID (e.g. DOC-0025) is generated.",
    "Then attach the source file (below). If AI drafting is on, ticking **Start Auto-fill as soon as the file is uploaded** sends you straight to the draft.",
  ]],
  ["h2", "Correcting a record's details"],
  ["steps", [
    { text: "Open the record. Under **Record details** you can edit the title, author, publication or event date, source URL or reference, geographic scope, value chain and document type.", img: "doc_record_details.jpg", caption: "Record details: the details the AI filled in, ready to check." },
    "Select **Save details**. The details appear in the coding form's Section A: on the review screen they show in grey, and the corrected values are the ones submitted to KoboToolbox.",
  ]],
  ["h2", "Attaching the source file, and removing a wrong one"],
  ["steps", [
    { text: "On the document's page, under **Source file**, select **Choose File** and pick the source: a PDF, a scan or photo (JPG or PNG), a Word (.docx) or Excel (.xlsx) file, or a text or CSV file. Audio and video can be attached as a reference. The limit is 20 MB. The file is stored privately on the server.", img: "doc_source_file.jpg", caption: "Source file: the file name, size and date, with Remove file beside it." },
    "A bar shows how much of the file has been sent. A large file on a slow connection can take a minute or two: wait until it says **Saving…** and the file name appears. If **Start Auto-fill as soon as the file is uploaded** is ticked (it is by default), the review screen then opens and the AI starts reading.",
    "Attached the wrong one? Select the red **Remove file** link beside the file name and confirm. The file is deleted from the server and the record says “No file uploaded yet”. Then choose the right file.",
    "Choosing another file straight away also replaces the old one.",
  ]],
  ["tip", "What goes with a removed file", "An AI draft (see below) made from the removed or replaced file is discarded too, so a draft of the wrong document can never be reviewed and submitted for the right one. A draft that has already been submitted to KoboToolbox is kept as the record of what was filed. Removals are recorded in the audit log with the file name."],
  ["h2", "Assessing and including a document"],
  ["steps", [
    { text: "In **Documents**, select **Manage** on the record.", img: "doc_register.jpg", caption: "Documentary Evidence Corpus." },
    { text: "Assess authenticity: select **Mark verified** or **Mark disputed**.", img: "doc_detail.jpg", caption: "Document record: authenticity, QA status, memo and coding form." },
    "Set the QA status: **Include** or **Exclude**. A document cannot be included until authenticity has been assessed.",
    "Write the **Interpretive memo** (dispute reasons, interpretation notes) and select **Save memo**.",
    "Code the document (next two sections). The completed form's PDF then appears on the record, under **Completed coding form (KoboToolbox)**.",
  ]],
  ["h2", "Coding a document: two ways"],
  ["p", "The **Coding** panel offers two buttons for the Document, Digital Platform & Media Analysis Tool:"],
  ["table", ["Button", "What it does", "Use it when"], [
    ["Code this document", "Opens the KoboToolbox Document Analysis Tool with the DOC ID, title, author, date and source already filled in. You answer every other question yourself.", "You code by hand, or the source cannot be read by the AI."],
    ["Auto-fill", "Has the AI read the uploaded source file and draft answers to the whole form. You review, edit and submit.", "A source file is uploaded and you want a fast first draft. The button only appears once the administrator has switched AI drafting on."],
  ], [0.2, 0.5, 0.3]],
  ["img", "doc_coding_buttons.jpg", "The Coding panel: Code this document, and Auto-fill."],
  ["h2", "Auto-fill: the AI drafts, you review"],
  ["steps", [
    "Attach the source file (above). Select **Auto-fill** in the **Coding** panel; the review screen opens.",
    { text: "If the file is a PDF of more than 100 pages, enter the **Pages to read**, for example `10-90`. The AI reads up to 100 pages at a time, so either choose the pages that make up this evidence unit, such as one chapter, or tick **Read the whole document in parts** (see “Coding a very long document” below). Its locators use the original page numbers. For shorter files, leave the box empty to read everything.", img: "doc_autofill_pages.jpg", caption: "A 240-page PDF: enter a page range, or read the whole document in parts." },
    { text: "Select **Generate AI draft**. The AI reads in the background, usually one to five minutes. You can leave the page and come back; the draft will be there.", img: "doc_autofill_running.jpg", caption: "The AI is reading the document." },
    { text: "Read the draft. It has every section of the KoboToolbox form, A to L. The DOC ID, author, title, date and source come from the record and cannot be changed here; everything else you can edit.", img: "doc_autofill_review.jpg", caption: "The review screen: the draft, ready to check and edit." },
    { text: "Check the judgements, not just the facts: the strength ratings (Sections D and H), the hypothesis codes (Section K) and the locators. Open the source and confirm a few page or paragraph references.", img: "doc_autofill_section_d.jpg", caption: "Section D: ratings and locators, all editable." },
    { text: "Check the numbers in Section J against the source. Add or remove metrics as needed.", img: "doc_autofill_section_j.jpg", caption: "Section J: quantitative metrics." },
    "Select **Save changes** to keep your edits and finish later. When you are satisfied, select **Submit to KoboToolbox** and confirm. Your reviewed answers are sent as a completed record.",
    "The record appears at once under **Completed coding form (KoboToolbox)** on the document page and in **Form PDFs**, found by its DOC ID. The portal's copy of the Document Analysis Tool is refreshed the moment you submit. If a coding you submitted is later deleted in KoboToolbox, the next sync (automatic, or **Sync now** on **Form PDFs**) unlocks the document so it can be coded again.",
  ]],
  ["warn", "The draft is a starting point, not a finding", [
    "Sections D to K are this study's documentary analysis. The AI drafts them; you are responsible for them. Change any rating you disagree with. A draft where everything is rated as strongly supportive deserves a second look.",
    "Nothing reaches KoboToolbox until you select **Submit**. Each draft and submission is recorded in the audit log, so the study can say exactly which records were AI-assisted.",
    "Submit once. A second submission would create a duplicate record for the document, and the screen shows “Already submitted” to stop it.",
  ]],
  ["table", ["File type", "Can the AI read it?", "Locators"], [
    ["PDF", "Yes, up to 100 pages at a time; longer files by page range, or read whole in parts (up to 1,500 pages).", "Original page and paragraph numbers."],
    ["JPG, PNG (scan or photo)", "Yes. Very large photos are shrunk automatically.", "Whatever the image shows."],
    ["Word (.docx), Excel (.xlsx), text, CSV", "Yes, as text.", "No page numbers: headings, paragraph or section numbers, sheet names."],
    ["Audio or video", "No. Upload a transcript (PDF, Word or text) and keep the recording as the source reference.", "-"],
    ["Old .doc or .xls", "No. Save as a PDF or as .docx / .xlsx and upload that.", "-"],
  ], [0.28, 0.44, 0.28]],
  ["h3", "Coding a very long document"],
  ["p", "The AI can take in 100 pages at a time. A report of several hundred or a thousand pages therefore needs one of two approaches:"],
  ["bullets", [
    "**One record per chapter (recommended).** Make a record for each part you want coded, for example “NDS2 – Agriculture chapter”: upload the PDF once, then use **Copy for another chapter** on that record for every further part, entering each part's page range (see “Coding another chapter of the same document” above). Review and submit each one. Each part gets its own DOC ID, its own coding and its own row in the Excel export.",
    "**Read the whole document in parts.** Tick **Read the whole document in parts**. Leave **Pages to read** empty for every page, or enter a longer range such as `1-600` (up to 1,500 pages). The AI codes each part of about 80 pages, then combines them into one draft for the record. The screen tells you how many parts it will take and asks you to confirm, then shows progress (“Read part 3 of 8”, then “Combining the parts into one draft”). Expect roughly ten to thirty minutes, and you can leave the page.",
  ]],
  ["warn", "A combined draft needs extra care", [
    "Because the ratings are judged across the parts rather than from every page at once, check the strength ratings (Sections D and H), the hypothesis codes (Section K) and the locators more carefully than for a single chapter. The draft states which pages it covers; confirm that this is the evidence unit you meant.",
    "A whole-document read costs about the number of parts plus one times an ordinary draft. If any part fails, the whole draft fails and nothing is saved, so you never receive a coding that silently skipped pages.",
    "Whether a whole-document coding is appropriate for a given source is a methodology decision for the PI; for a report that covers many topics, one record per chapter usually gives a sharper analysis.",
  ]],
  ["h3", "If Auto-fill shows a message"],
  ["table", ["You see", "What it means", "What to do"], [
    ["“Pages to read (required)”, or “This PDF has N pages…”", "The PDF is longer than 100 pages.", "Enter a page range of up to 100 pages, or tick **Read the whole document in parts**."],
    ["“…over the 1500-page ceiling…”", "The PDF is longer than the most that can be read in one draft.", "Enter a page range, or make one record per chapter."],
    ["“Step 1 of 2…” or “Step 2 of 2…”", "A record made by Quick add is being filled in and drafted. Nothing is wrong.", "Wait, or leave the page and come back."],
    ["A detail in Section A is wrong or blank", "The AI reads only what the document states, and can mistake a title or date.", "Correct it under **Record details** on the record page; the draft and the submission use the corrected value."],
    ["Quick add says the file can't be used", "Unsupported type (for example audio), a damaged file, or a long PDF with no pages chosen.", "Read the message: convert the file, enter a page range, or tick **Read the whole document in parts**. No record is created when this happens."],
    ["“Reconcile the pre-interview profile first…” when accepting a questionnaire, or a KII's coding will not complete", "The case has a locked pre-interview profile with facts not yet verified with the respondent or not reconciled.", "Open the case (or KII record) → Interview sheet; verify every fact, and ask the coordinator to reconcile the corrected ones."],
    ["“Read part 4 of 12” or “Combining the parts…”", "A long document is being read in parts. Nothing is wrong.", "Wait, or leave the page and come back."],
    ["“The AI's answer was cut off…”", "The range was too big to answer in one go.", "Try a narrower range."],
    ["“A draft is already being generated”", "You or a colleague already started one.", "Wait for it to finish (about five minutes; up to half an hour for a document read in parts)."],
    ["“The last attempt failed: …”", "The AI request did not complete.", "Select **Generate AI draft** again. If it keeps failing, tell the administrator the message."],
    ["“The AI account has run out of credit…”", "The study's AI account has no funds left.", "Tell the administrator to add credit in the Anthropic console; nothing else to do on this screen."],
    ["No **Auto-fill** button", "AI drafting has not been switched on, or there is no source file yet.", "Attach the file; otherwise ask the administrator."],
    ["**Submit** is refused by KoboToolbox", "KoboToolbox did not accept the record.", "Tell the administrator; your draft is kept."],
  ], [0.3, 0.35, 0.35]],
  ["tip", "Cost", "Each draft is a paid request on the study's AI account. A short chapter costs little; a full 100 pages costs several times more; a whole document read in parts costs about the number of parts plus one times an ordinary draft. Choose the pages you need."],
];

T.cost = [
  ["h2", "Logging fieldwork costs"],
  ["steps", [
    { text: "Select **Cost**. The top shows total spend, cost per QA-passed questionnaire and cost per completed KII, with spend by category.", img: "adm_cost.jpg", caption: "Cost Dashboard and the Log a cost event form." },
    "In **Log a cost event**, enter the date, choose the category (RA_ALLOWANCE, AIRTIME_DATA, TRANSPORT, ACCOMMODATION, HOSTING, MESSAGING, OTHER) and the amount in USD.",
    "Select **Log cost**. Keep the receipt as the study's finance rules require.",
  ]],
];

T.exports = (who) => {
  const blocks = [
    ["h2", "Downloading data"],
    ["img", who === "analyst" ? "an_export.jpg" : "adm_export.jpg", "Data Export."],
    ["table", ["Download", "Contains", "Who"], [
      ["**De-identified analysis export (CSV)**", "One row per questionnaire: sample_id, master_id, province, actor_family, value_chain, size_class, administration_mode, qa_status, submitted_at, completion_seconds. No names or contact details. Participants who withdrew are left out.", "PI, Field Coordinator, Analyst"],
      ["**Full operational export (CSV)**", "Every questionnaire, including withdrawn ones (consent_withdrawn), plus organisation name, respondent name, phone, email and gatekeeper details. Internal operations only.", "PI only"],
      ["**KoboToolbox data: Excel workbook**", "Every submission's answers for one form: data_codes (codes for SPSS/Stata/R), data_labels, a sheet per repeat group, the questions dictionary, the choices lists, and for the questionnaire the matched case, QA status, withdrawal flag and workflow status.", "PI only"],
      ["**KoboToolbox data: All completed forms (PDF ZIP)**", "Every completed form as a PDF, with manifest.csv listing file, record, KoboToolbox id and submission time.", "PI only"],
    ], [0.27, 0.53, 0.2]],
  ];
  if (who === "pi") blocks.push(
    ["h3", "Getting all the data for cleaning and analysis"],
    ["steps", [
      "Select **Export**.",
      "Under **KoboToolbox data — every completed form**, select **Excel workbook** for the **Main Study Questionnaire**. Repeat for the **Main Study KII Guide** and the **Document, Digital Platform & Media Analysis Tool**.",
      "Select **All completed forms (PDF ZIP)** for each form you need as PDFs. A large ZIP starts at once and grows while it downloads — let it finish.",
      "Open the workbook's **README** sheet first. Use `data_codes` for statistical software and `data_labels` for reading. `meta/rootUuid` identifies a submission across edits; `_parent_id` links repeat rows to their submission.",
      "For analysis without identities, share only the **De-identified analysis export** and the workbook columns you have checked contain no names or contact details.",
    ]],
    ["warn", "Handle raw data carefully", "Workbooks and PDFs contain the answers themselves, and the KII Guide identifies people. Store them only on encrypted, access-controlled storage as the data management plan requires. Every download is recorded in the audit log."],
  );
  return blocks;
};

T.audit = [
  ["h2", "Checking the audit log"],
  ["steps", [
    { text: "Select **Audit Log**. Each row shows when, the action (e.g. `invitation.issued`, `consent.recorded`, `sampling.bulk_workflow_transition`, `kobo.data_exported`), the record, and the user.", img: "adm_audit.jpg", caption: "Audit Log, newest first." },
    "Page through with **Previous** and **Next**. Actions taken by scheduled jobs or by respondents themselves show **system**.",
  ]],
];

module.exports = { T, SITE };
