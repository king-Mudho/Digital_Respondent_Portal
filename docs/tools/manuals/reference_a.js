// Screen and Button Reference, part A: signing in, dashboards, the sample and contact screens.
// Each row: [control, what it does and when to use it, why it exists (the rule behind it), what happens next, options]
// options: { write: true } = hidden from read-only roles; { only: [roles] } = only those roles see it.
const R = {
  PI: "PI_ADMIN", FC: "FIELD_COORDINATOR", CRA: "CONTACT_RA", QA: "QUAN_QA_RA",
  KII: "KII_RA", DOC: "DOCUMENTARY_RA", AN: "ANALYST", SUP: "SUPERVISOR_READONLY",
};
const ALL = Object.values(R);
const w = { write: true };

const screens = [
  {
    id: "login", group: "Signing in and your account", title: "Sign in", path: "/admin/login", roles: ALL,
    purpose: "Where every staff member starts. Staff accounts are created by the PI; there is no self-registration.",
    rows: [
      ["Username", "Type the username the PI gave you.", "Every action in the portal is recorded against a named person, so accounts are never shared.", "Nothing yet; you also need the password."],
      ["Password", "Type your password. The characters are hidden.", "Passwords are never shown or emailed; the PI can reset yours but cannot read it.", "Nothing yet; select Sign in."],
      ["Sign in", "Checks your username and password and opens your start screen (the first screen your role uses).", "Repeated wrong attempts from one network are refused for a minute, to stop password guessing.", "Your start screen opens. A wrong password says so. “Too many sign-in attempts” means wait a minute."],
    ],
  },
  {
    id: "header", group: "Signing in and your account", title: "The header and menu bar (every screen)", path: "(top of every screen)", roles: ALL,
    purpose: "Shown at the top of every signed-in screen. The menu bar lists only the screens your role may open.",
    rows: [
      ["Menu bar (Executive, Sampling, … Audit)", "Opens a screen. The current screen is underlined.", "The list is built by the server from your role, so you never see a screen that would refuse you.", "The screen opens. A screen not in your list shows “This screen isn't part of your role”."],
      ["Change password", "Opens the Change Password screen.", "You should change the first password you were given, and any password you think someone saw.", "The Change Password screen opens."],
      ["Sign out", "Ends your session on this device.", "Protects the data if the device is shared or lost. Always sign out on a shared device.", "Your session on this device ends and you return to the Sign in screen."],
      ["← Back to … (top left)", "Returns to the parent screen (for example from a case to the register).", "A consistent way back that does not lose your place in the menu.", "The parent screen opens."],
      ["Go to my start screen", "Appears on the “This screen isn't part of your role” page and takes you to your own start screen.", "An old bookmark or shared link may point at a screen that belongs to another role; this gets you out safely.", "Your start screen opens."],
    ],
  },
  {
    id: "account", group: "Signing in and your account", title: "Change Password", path: "/admin/account", roles: ALL,
    purpose: "Change your own password.",
    rows: [
      ["Current password", "Type the password you use now.", "Proves it is really you before a change, in case a signed-in device was left open.", "Nothing yet."],
      ["New password", "Type the new password.", "It must be long enough, not a common password, not all digits and not similar to your username or name; the screen says which rule failed.", "Nothing yet."],
      ["Confirm new password", "Type the new password again.", "Catches a typing slip that would lock you out.", "Nothing yet."],
      ["Change password", "Saves the new password.", "Your old password stops working straight away, and other people (including the PI) never see your new one.", "A confirmation appears. Use the new password next time."],
    ],
  },

  {
    id: "dash_exec", group: "Dashboards and Reports (read-only)", title: "Executive Dashboard", path: "/admin/dashboard",
    roles: [R.PI, R.FC, R.AN, R.SUP],
    purpose: "The one-page picture of the study: how many cases are where in the funnel, response and quality headlines, and the weakest parts of the sample. Counts and rates only; never a name.",
    rows: [
      ["Tiles: QUAN completed, KII completed, Documents coded, Days to data lock, Fieldwork expenditure to date", "Show the headline counts against their targets, the days left to the data lock (30 November 2026) and the spend so far. Read them; there is nothing to press.", "Aggregates only, so the dashboards are safe to show to people who must not see respondent identities.", "Numbers update whenever the screen is opened or refreshed."],
      ["Highest-risk coverage gaps", "Lists the strata (province × organisation type × size) with the lowest fill so far.", "Tells the coordinator where fieldwork effort is most needed to meet the sample design.", "Use it to decide where to send Contact RAs next."],
      ["Links: Sampling, Contact, QA, KII / Documents, Cost", "Open the related dashboards.", "Saves hunting through the menu.", "The linked screen opens."],
    ],
  },
  {
    id: "dash_sampling", group: "Dashboards and Reports (read-only)", title: "Sampling Dashboard", path: "/admin/dashboard/sampling",
    roles: [R.PI, R.FC, R.AN, R.SUP],
    purpose: "How the Main-400 and Reserve-400 samples stand.",
    rows: [
      ["Main-400 by province", "Shows how many Main cases each province holds and how many are verified.", "The design fixes how many organisations each province must contribute.", "Read only."],
      ["Verified / total by stratum", "Shows verification progress in each stratum.", "A stratum that cannot be verified may need a Reserve replacement.", "Read only."],
      ["Reserve activations by reason", "Counts Reserve cases activated, by the authorised reason.", "Reserve replacement is controlled and audited; this shows how often and why it happens.", "Read only. “No reserve activations yet” until one is made."],
    ],
  },
  {
    id: "dash_contact", group: "Dashboards and Reports (read-only)", title: "Contact Dashboard", path: "/admin/dashboard/contact",
    roles: [R.PI, R.FC, R.AN, R.SUP],
    purpose: "Contact activity: how many are invited, reminded, reached, and how appointments stand.",
    rows: [
      ["Contact figures", "Show counts of contacts, reminders and appointments by status.", "Lets the coordinator see whether contact is on schedule without opening cases.", "Read only."],
    ],
  },
  {
    id: "dash_qa", group: "Dashboards and Reports (read-only)", title: "QA Dashboard", path: "/admin/dashboard/qa",
    roles: [R.PI, R.FC, R.QA, R.SUP],
    purpose: "Quality checking at a glance: how many questionnaires wait for a decision and how the completed ones were done.",
    rows: [
      ["Refresh", "Re-reads the figures now.", "The page does not update by itself while you watch it.", "The numbers reload; the button says Refreshing… briefly."],
      ["Administration mode", "Shows how many questionnaires were completed by each mode (web, telephone, WhatsApp-assisted, face to face).", "Mode balance is a quality and method question for the study.", "Read only."],
      ["Open QA queue", "Goes to the QA Queue.", "Takes you from the overview to the work.", "The QA Queue opens."],
      ["Try again", "Appears if the figures could not load; tries once more.", "A dropped connection should not leave a blank page.", "The figures load, or the message stays."],
    ],
  },
  {
    id: "dash_kiidoc", group: "Dashboards and Reports (read-only)", title: "KII / Document Dashboard", path: "/admin/dashboard/kii-documents",
    roles: [R.PI, R.FC, R.AN, R.SUP, R.KII, R.DOC],
    purpose: "Progress of the two qualitative strands against their targets (about 60 KIIs, 50–75 documents).",
    rows: [
      ["KII by status", "Counts KII records at each stage (prospect, invited, scheduled, completed, declined, no-show).", "Shows how far the interview target has come.", "Read only."],
      ["Documents by type / by QA status", "Counts documents by type (official, secondary, platform) and by decision (pending, included, excluded).", "Only included documents count towards the corpus target.", "Read only."],
    ],
  },
  {
    id: "reports", group: "Dashboards and Reports (read-only)", title: "Reports", path: "/admin/reports",
    roles: [R.PI, R.FC, R.AN, R.SUP],
    purpose: "Charts for supervision meetings and progress reports: funnel, submissions per day, coverage, time to complete, QA outcomes, modes and workflow. Counts and rates only.",
    rows: [
      ["Last 7 days / Last 30 days / Last 90 days / All time", "Sets the period the time-based charts cover.", "Meetings usually ask “what happened this week or month”. Case progress is always cumulative.", "Every time-based chart redraws for that period."],
      ["Province / Organisation type / Size", "Changes what the coverage chart is broken down by.", "Coverage matters along all three design dimensions.", "The coverage chart redraws."],
      ["Show table / Show chart", "Switches one chart between its picture and the numbers behind it.", "Every chart is available as a table so numbers can be read out, copied or checked.", "The chart is replaced by a table (and back)."],
    ],
  },

  {
    id: "sample", group: "The sample and contact", title: "Main-400 Register (and Reserve)", path: "/admin/sample",
    roles: [R.PI, R.FC, R.CRA, R.SUP],
    purpose: "The list of sample cases. A Contact RA sees only the cases assigned to them. From here you open a case, and the coordinator moves or reassigns cases in bulk.",
    rows: [
      ["Main / Reserve (sample type)", "Switches the list between the 400 Main cases and the 400 locked Reserve cases.", "Reserve cases are locked replacements and are handled differently from Main cases.", "The list changes and returns to page 1."],
      ["Search ID or organisation", "Filters the list as you type.", "Finding one case among hundreds should not need paging.", "Only matching cases are listed."],
      ["Register organisation", "Opens Register Organisation to add an organisation that is not yet in the sample.", "Late additions must get a proper Master ID and a sample case.", "The Register Organisation screen opens.", { only: [R.PI, R.FC], write: true }],
      ["View", "Opens the case page for that row.", "All work on a case happens on its own page.", "The case page opens."],
      ["Move through verification: step, How many, Move all N", "Moves every Main case at one verification step (S00→S01, S01→S02, S02→S03) to the next after you confirm.", "All 400 cases start at S00; verifying them one by one would take days, and a status should only advance when the checks behind it are done.", "A confirmation asks first. Then “Moved N cases”, and the register updates.", { only: [R.PI, R.FC], write: true }],
      ["Reassign cases: From, Province, How many, To, Move cases", "Moves a chosen number of cases (in Sample ID order) from one Contact RA, or from Unassigned, to another RA (or to nobody).", "Workload has to be balanced; moving in ID order lets you split a large province between RAs in two steps.", "A confirmation asks first, then the cases appear in the new RA's register.", { only: [R.PI, R.FC], write: true }],
      ["Show / page numbers / Previous / Next", "Chooses how many rows to see (10, 20, 50, 100 or 200) and moves between pages.", "Different jobs need different views; your choice is remembered.", "The list redraws at the chosen size."],
    ],
  },
  {
    id: "case", group: "The sample and contact", title: "Case page", path: "/admin/sample/{Sample ID}",
    roles: [R.PI, R.FC, R.CRA, R.SUP],
    purpose: "Everything about one organisation's place in the sample: who to contact, the invitation, the questionnaire, the timeline and the case's status.",
    rows: [
      ["Advance workflow status (→ S0x buttons)", "Moves the case to the next valid status, for example from Eligible respondent identified to Invitation prepared.", "The workflow is a fixed sequence (S00–S16): a case cannot skip steps, and each move is recorded. Only statuses that are allowed next are shown.", "The status changes and the change is added to the audit log. “No further transitions” appears at a final status.", w],
      ["Respondents and contact details → Add a person", "Records a person at the organisation: name, role, phone, WhatsApp, email, gatekeeper, and whether they are eligible.", "Invitations, reminders and phone-assisted interviews all need to know who to contact and whether they are the right (senior, knowledgeable) person.", "A form opens. After Save, the person is listed on the case.", w],
      ["Respondents panel → Edit / Save / Cancel", "Corrects a person's details. Save keeps the change; Cancel discards it.", "Contact details go stale, and a wrong number wastes a whole reminder sequence.", "The person's details update; Cancel leaves them unchanged.", w],
      ["Eligibility (Not yet screened / Eligible / Not eligible)", "Records the outcome of your eligibility screening of that person.", "Someone not eligible must never receive the questionnaire: the system will not hand out the questionnaire link without a passed eligibility check and the person's consent.", "Eligible lets the questionnaire link work once consent is given. Not eligible sends the respondent to a referral instead.", w],
      ["Assigned Contact RA", "Chooses which Contact RA works this case (or Unassigned).", "A Contact RA sees only their assigned cases.", "The RA's register now shows (or no longer shows) the case.", { only: [R.PI, R.FC], write: true }],
      ["Matched Reserve case", "Pairs this Main case with a locked Reserve case from the same stratum.", "If the Main organisation drops out, its matched Reserve is the replacement, keeping the sample balanced.", "The pair is saved. Activating the Reserve later still needs an authorised reason and an evidence note.", { only: [R.PI, R.FC], write: true }],
      ["Invitations → Issue invitation (Channel, Wave)", "Creates a personal invitation link (valid 14 days) and an 8-character manual code, for the chosen channel and wave.", "Respondents are invited by a private, expiring link. The link is shown once and only a scrambled form is stored, so a stolen database cannot reveal live links. A new invitation replaces the old one.", "The link and code appear once, ready to send. If the case cannot be invited (for example a locked Reserve case) you are told why.", w],
      ["Send via WhatsApp / Send by SMS / Open in email app", "Opens WhatsApp, your SMS app or your email program with the invitation message already written.", "The portal does not send messages itself: you send from the study's own account so replies come to you.", "Your messaging app opens with the text. Send it, then log it on the Contact timeline."],
      ["Send email (from the portal) / Copy message", "Sends the invitation email from the portal (if email is set up), or copies the text so you can paste it anywhere.", "Some respondents prefer email; copying is the fallback for any other channel.", "“Sent to …” or “Copied”.", w],
      ["Revoke", "Cancels an invitation so its link stops working.", "Use if it went to the wrong person or the wrong address; it is also how a wrong send is undone.", "The link stops working at once and the invitation is shown as revoked.", w],
      ["Log a contact attempt (Channel, Outcome, Notes, Log contact attempt)", "Adds an entry to the Contact timeline: how you tried, what happened (Reached, No answer, Wrong number, Refused, Rescheduled, Completed) and a note.", "The timeline is the study's record of effort. It shows why a case is nonresponsive and protects respondents from being contacted twice by mistake.", "The entry appears at the top of the timeline with your name and the time.", w],
      ["Record a withdrawal (Reason, How they told us, Record withdrawal)", "Records that the participant wants to withdraw. You give the reason and whether they told you by phone or in person, or in writing.", "A participant's right to withdraw must take effect at once and completely: their consent is recorded as withdrawn, every open invitation is revoked, reminders stop, and their phone, WhatsApp, email and gatekeeper contact are erased.", "A confirmation warns that it cannot be undone. The case moves to Refused (a case already submitted keeps its status). Any answers already submitted are kept but left out of the analysis export and flagged.", w],
      ["Completed questionnaire → Download PDF", "Downloads the participant's completed questionnaire as a readable PDF.", "A readable copy is needed for QA notes and for the participant if they ask.", "A PDF downloads. The download is recorded in the audit log."],
      ["Pre-Interview Profile (PROIT) panel", "Coordinator's tool for background research on the organisation before an interview. See the PROIT screen entry.", "Public facts are found before contact so the respondent is asked to confirm them, not to repeat them.", "See the PROIT entry.", { only: [R.PI, R.FC, R.SUP] }],
    ],
  },
  {
    id: "proit", group: "The sample and contact", title: "Pre-Interview Profile (PROIT) and its review screen", path: "(panel on the case page) · /admin/proit/{id}",
    roles: [R.PI, R.FC, R.SUP],
    purpose: "Records what is publicly known about an organisation and its respondent, each fact with a source, so the interview confirms facts instead of asking for them again. Never a private or inferred fact.",
    rows: [
      ["Start background research", "Creates the pre-profile for this case.", "Research is recorded only when someone deliberately starts it for a case.", "The panel opens with an empty list of background fields.", w],
      ["Research with AI / Research again", "The AI searches public sources for the organisation and the respondent's published professional role, and proposes background facts. It works in the background for a few minutes; you can leave the page.", "Finding what is already public is slow desk work; the AI does the searching so the interview can confirm facts instead of asking for them. It only proposes, never records.", "A list of proposals appears under “To review”, and a list of what was not found publicly. The organisation name, and the respondent's name and role, are sent to the AI provider's search; never contact details.", w],
      ["Proposed value (editable)", "The fact the AI found, in plain words. Edit it if the wording needs correcting.", "The researcher is responsible for what enters the profile, so the wording is theirs to fix.", "Nothing changes until you select Accept.", w],
      ["Proposal sources (title, publisher, date, tier, quote)", "Every source the AI used, each with a short exact quote. Select the title to open the page and check it.", "Only pages the search actually returned can be cited, so there are no invented references. Checking the page is how you confirm it is the right organisation.", "The page opens in a new tab.", w],
      ["Accept (a proposal)", "Puts the fact into the profile as a background field, with all its sources and your name as the person who accepted it.", "Every fact needs a source and a person's decision before it can reach a respondent. If you edited the wording it is recorded as “accepted with edits”.", "The field appears in the profile with its sources; the proposal moves to “Already decided”. It still needs the lock.", w],
      ["Reject (a proposal)", "Discards the proposal, for example when it is a different organisation with a similar name.", "A wrong fact put to a respondent damages trust and the data.", "The proposal is marked rejected; nothing enters the profile.", w],
      ["Not found publicly: ask the respondent", "Lists the fields the AI could not find in any public source.", "These are the questions to ask in full at the interview, so the respondent is not asked what is already public.", "Read only. Add any you find yourself with “Add a background field”.", w],
      ["Add a background field (Select a field, What was found, Add field)", "Adds one fact, for example a working capital facility, from a fixed catalogue of allowed fields.", "Only listed, documented kinds of fact can be recorded; health, religion, ethnicity, politics and inferred finances are never collected.", "The field appears in the list, waiting for a source.", w],
      ["Add source", "Attaches the source that shows the fact (for example a registry entry).", "Every fact with a documentary value needs at least one source so it can be checked.", "The source is listed under the field.", w],
      ["Insert suggestion", "Inserts a suggested probe question for the chosen role, using your evidence.", "Saves writing role-specific questions from scratch and keeps interviews consistent.", "The suggestion is added above for you to keep, edit or delete.", w],
      ["Gap-engine notes: Known, Unknown, Contradictions, Priority probe questions, Role-specific module, short form → Save gap-engine notes", "Records what is already established, what is missing, where sources disagree, and what to ask first.", "Focuses the interview on real gaps and reduces the burden on the respondent.", "The notes are saved; the panel shows how many background questions became verifications.", w],
      ["Lock pre-profile", "Finalises the profile.", "A locked profile is the version the interview is planned from; it cannot be quietly changed afterwards. It cannot be locked while a fact still has no source.", "The profile becomes read-only.", w],
      ["Researcher review screen (link)", "Opens a one-page summary: case, organisation, evidence, bankability context, gap summary and interview plan.", "One readable page for the researcher to read before the interview.", "Read only; sensitive items to avoid are listed at the bottom."],
    ],
  },
  {
    id: "interview_sheet", group: "The sample and contact", title: "Interview sheet (verifying a locked profile)", path: "(on the case page, and on the KII record)",
    roles: [R.PI, R.FC, R.CRA, R.KII, R.SUP],
    purpose: "The locked pre-interview profile as the interviewer uses it: confirm what is public, ask what is not, record what the respondent says, and after the interview reconcile it. The coordinator and PI see it inside the PROIT panel; a Contact RA sees it on a case assigned to them; a KII RA on a KII record.",
    rows: [
      ["Status (Verified x of y · settled x of y / Reconciled)", "Counts how many facts have been verified with the respondent and how many are settled. It reads Reconciled when all are.", "A case is not complete until every fact is verified and, where corrected, reconciled.", "Read only. It updates as answers are saved."],
      ["Confirm / Confirm, then probe / Ask (label on each row)", "Tells you what to do with that row: confirm a public fact, confirm it and probe (sources disagree), or ask the question in full because nothing reliable is public.", "Asking only what is not public reduces the burden on the respondent.", "Read only."],
      ["Public source says (with source links)", "Shows the public fact and where it came from. A weak source's value is hidden and the row says to ask in full.", "A weak or uncorroborated fact must never be put to a respondent as if it were established.", "Read only. Select a source to open it."],
      ["What the respondent said", "Record the answer: confirmed, corrected, partly correct or out of date, does not know, prefers not to say, or does not apply. For a gap, “They told us”.", "The respondent's answer is kept separately from the public value and never replaces it; that separation is what lets the analysis compare the two.", "Nothing is saved until Save answer.", w],
      ["Their answer / Comment", "Type what the respondent said when they corrected or supplied a value, and any comment.", "The exact answer is the research data; the comment explains it.", "Kept with the row.", w],
      ["Save answer", "Saves the answer for that fact.", "Each answer is recorded as it is given, so nothing depends on memory after the interview.", "The status updates; “Recorded: …” appears under the row. A correction shows “Differs from the public source”.", w],
      ["Differs from the public source (label)", "Marks a fact the respondent corrected or qualified.", "Contradictions between public sources and respondents are findings, not errors to hide.", "Read only. The coordinator reconciles it.", w],
      ["Interview finished", "Records that the interview and its verification are over, so reconciliation can begin.", "Separates what was said in the interview from the researcher's later coding.", "It shows the time it was recorded.", w],
      ["Reconciled value (required) → Save reconciled value", "The coordinator or PI types the value that is coded for analysis, where the respondent corrected, qualified, did not know or declined. Not needed for a plain confirmation.", "The reconciled value is the researcher's coded position; it never overwrites the public value or the respondent's answer.", "The fact becomes settled. When all are, the status reads Reconciled.", { only: [R.PI, R.FC], write: true }],
      ["Record a protocol deviation", "Releases the case when reconciliation truly cannot be finished, after you give the reason.", "A lost respondent must not block a completed interview forever, but the exception has to be visible and explained.", "The case is released and stays flagged, with the reason kept.", { only: [R.PI, R.FC], write: true }],
    ],
  },
  {
    id: "orgs", group: "The sample and contact", title: "Register Organisation", path: "/admin/organisations",
    roles: [R.PI, R.FC, R.SUP],
    purpose: "Adds an organisation that is not already in the sample and gives it a Master ID and, if wanted, a sample case.",
    rows: [
      ["Name, District, Province, Entity type, Actor family, Value chain, Size class", "Describe the organisation. Name is required.", "These are the sample's design dimensions (province × organisation type × size) so the new organisation lands in the right stratum.", "Nothing is saved until you select Register organisation.", w],
      ["Register organisation", "Saves the organisation.", "The Master ID is generated automatically from the province, so IDs are never typed or reused.", "“{name} registered — {Master ID}” appears with the option to create its case.", w],
      ["Sample type (Main / Reserve) and Create sample case", "Creates the organisation's case as a Main or a Reserve case.", "Only an organisation with a case can be worked; Reserve cases start locked.", "The case is created with a Sample ID; a link to the Main-400 Register appears.", w],
      ["Search name, Master ID or district", "Filters the list of registered organisations.", "Avoids registering the same organisation twice.", "Only matching organisations are listed."],
      ["Create sample case (per row)", "Creates a case later for an organisation registered without one.", "Registering and creating the case are separate steps so neither is forced.", "The case is created.", w],
    ],
  },
  {
    id: "appts", group: "The sample and contact", title: "Appointment Queue", path: "/admin/appointments",
    roles: [R.PI, R.FC, R.CRA, R.SUP],
    purpose: "Calls that respondents have asked for, and their progress.",
    rows: [
      ["Filter by status", "Shows all appointments, or only Requested, Confirmed, Completed, Missed or Cancelled.", "Coordinators mostly need the ones still to be acted on.", "The list changes and returns to page 1."],
      ["CONFIRMED / CANCELLED (on a Requested appointment)", "Confirm the time with the respondent and select CONFIRMED, or CANCELLED if it will not happen.", "A respondent's request is only a request until a person confirms it.", "The appointment's status changes.", w],
      ["COMPLETED / MISSED / CANCELLED (on a Confirmed appointment)", "Record what happened at the appointment time.", "Missed calls need to be rescheduled and counted; completed ones move the case forward.", "The status changes; finished appointments show no more buttons.", w],
      ["Show / page numbers", "Choose rows per page and move between pages.", "As on every register.", "The list redraws."],
    ],
  },
  {
    id: "followups", group: "The sample and contact", title: "Follow-ups due", path: "/admin/follow-ups",
    roles: [R.PI, R.FC, R.CRA, R.SUP],
    purpose: "Approved reminders (on days 0, 2, 4–5 and 7 after an invitation) for invited cases that have not responded.",
    rows: [
      ["Case link (Sample ID)", "Opens the case the reminder is for.", "Lets you check the case before you send.", "The case page opens."],
      ["Open in WhatsApp", "Opens WhatsApp with the reminder text already written for that respondent.", "Reminders are sent by a person from the study's WhatsApp account: nothing is sent automatically, so a person always decides.", "WhatsApp opens with the message. If the button says “Open WhatsApp (choose contact)”, there is no number on file: pick the contact in WhatsApp, and add the number on the case afterwards."],
      ["Mark as sent", "Tells the portal you sent the reminder.", "Otherwise the same reminder stays due and could be sent twice.", "It is recorded as sent by you and leaves the list.", w],
    ],
  },
  {
    id: "reserve", group: "The sample and contact", title: "Reserve Activation", path: "/admin/reserve",
    roles: [R.PI, R.FC, R.SUP],
    purpose: "Where a locked Reserve case is activated to replace a Main case that has dropped out.",
    rows: [
      ["Search ID or organisation", "Finds a locked Reserve case.", "There are 400 locked cases.", "Only matching cases are listed."],
      ["Select authorised reason", "Chooses why: Ineligible, Inactive, Duplicate, Refusal or Nonresponse exhausted.", "A Reserve case is a scarce, matched replacement. Only these reasons are allowed so replacement cannot be used to swap in a friendlier organisation.", "Nothing yet; you also need an evidence note.", w],
      ["Evidence note (required)", "Write what shows the reason is true.", "Every activation must be defensible later, in the dissertation or an audit.", "Nothing yet; select Activate.", w],
      ["Activate", "Unlocks the Reserve case so it can be invited.", "The one controlled way a Reserve case becomes usable. The reason, note and your name are kept.", "The case leaves the locked list and can be invited; the activation is audited.", w],
    ],
  },
];

module.exports = { R, ALL, screens };
