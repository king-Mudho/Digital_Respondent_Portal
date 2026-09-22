// Content shared by the system manual and the role guides.

const REVISION = "Version 1.10 · 22 September 2026";
const SITE = "https://research.agribizframework.com";

const ROLE_TABLE = [
  ["PI / System Admin", "All 19 screens, including the Audit Log and every export", "Executive Dashboard"],
  ["Field / Digital Coordinator", "18 screens — everything except the Audit Log. No full operational export and no KoboToolbox data download", "Executive Dashboard"],
  ["Contact RA", "Main-400 Register, Appointments, Follow-ups — only the cases assigned to you", "Main-400 Register"],
  ["QUAN/Kobo QA RA", "QA Dashboard, Form PDFs (questionnaire), QA Queue, QA Exceptions", "QA Dashboard"],
  ["KII RA", "KII/Doc Dashboard, Form PDFs (KII Guide), KII Register", "KII/Doc Dashboard"],
  ["Documentary RA", "KII/Doc Dashboard, Form PDFs (Document Analysis Tool), Documents", "KII/Doc Dashboard"],
  ["Data Analyst", "Executive, Sampling, Reports, Contact and KII/Doc dashboards, Cost, Export (de-identified only). Read-only", "Executive Dashboard"],
  ["Supervisor (read-only)", "17 screens — everything except the Audit Log and Export. Read-only", "Executive Dashboard"],
];

const STATUS_TABLE = [
  ["S00", "Selected Main", "The case is in the Main-400 sample. Starting point for every Main case."],
  ["S01", "Verification required", "The organisation's details are being checked."],
  ["S02", "Organisation verified", "The organisation exists, is active and is the right one."],
  ["S03", "Eligible respondent identified", "A knowledgeable senior person has been identified. Ready to invite."],
  ["S04", "Invitation prepared", "Optional manual step before sending."],
  ["S05", "Invitation sent", "Set automatically when an invitation is issued."],
  ["S06", "Invitation opened", "Set automatically when the respondent opens the link."],
  ["S07", "Survey started", "Set automatically when the respondent opens the questionnaire."],
  ["S08", "Survey submitted", "Set automatically when the questionnaire arrives from KoboToolbox."],
  ["S09", "QA query", "Set automatically when a QA reviewer re-queries the submission."],
  ["S10", "QA passed", "Set automatically when a QA reviewer accepts the submission."],
  ["S11", "Completed", "Final: the case is finished."],
  ["S12", "Refused", "Drop state: the organisation declined or withdrew."],
  ["S13", "Nonresponse", "Drop state: no response after every approved reminder was sent."],
  ["S14", "Ineligible", "Drop state: the organisation or respondent does not qualify."],
  ["S15", "Duplicate / inactive", "Drop state: duplicate record or organisation no longer operating."],
  ["S16", "Reserve eligible for activation", "The matched Reserve may now be activated to replace this case."],
];

const MODES_TABLE = [
  ["01", "Web self-administration", "The respondent completes the questionnaire alone from the link."],
  ["02", "WhatsApp link, self-completion", "The link is sent by WhatsApp; the respondent completes it alone."],
  ["03", "Telephone, interviewer-administered", "A researcher calls and completes the form while the respondent answers."],
  ["04", "WhatsApp call, interviewer-assisted", "As 03, over a WhatsApp voice or video call."],
  ["05", "Video call, interviewer-assisted", "As 03, over Teams, Zoom or Google Meet."],
  ["06", "Face to face", "In person; the researcher operates the device."],
];

const signIn = (landing, role) => [
  ["h2", "Signing in"],
  ["steps", [
    `Open **${SITE}/admin/login** in any modern browser (Chrome, Edge, Firefox or Safari), on a computer, tablet or phone.`,
    { text: "Type your **Username** and **Password**, then select **Sign in**.", img: "adm_login.jpg", caption: "The sign-in screen for all internal staff." },
    `You arrive on your start screen: **${landing}**. The bar across the top lists only the screens your role (${role}) can open.`,
  ]],
  ["tip", "Accounts", "There is no self-registration. The PI / System Admin creates every account and sets its role. Ask the PI if you need an account, a different role, or a password reset."],
  ["h2", "Finding your way around"],
  ["bullets", [
    "The **top bar** shows your username and role, and the screens you can use. It is not a full menu with some items greyed out: anything absent is simply not part of your role.",
    "Most screens have a **← Back to …** link at the top that returns you to the screen you came from.",
    "Registers show **20 rows per page** to begin with. At the foot of the list, **Show** lets you choose 10, 20, 50, 100 or 200 rows per page (the portal remembers your choice), and the page numbers, **Previous**, **Next** and the double arrows take you to any page. The **Search** box above the list narrows it.",
    "**Change password** (top right) lets you set a new password at any time. Choose a long password you do not use anywhere else.",
    "**Sign out** (top right) ends your session. Always sign out on a shared or public computer.",
    "If you are inactive for a while you may be asked to sign in again. This protects research data on unattended devices.",
  ]],
  ["img", "adm_not_your_role.jpg", "Opening a screen outside your role (for example from an old bookmark) shows this card instead of the screen."],
];

const changePassword = [
  ["h2", "Changing your password"],
  ["steps", [
    "Select **Change password** in the top right corner.",
    { text: "Enter your **Current password**, then the **New password** twice, and select **Change password**.", img: "adm_account.jpg", caption: "Change Password screen." },
    "Use the new password next time you sign in. If you have forgotten your password, ask the PI to reset it.",
  ]],
];

const DATA_RULES = [
  "Treat everything in the portal as **confidential research data**. Do not screenshot, copy, print or forward names, phone numbers, email addresses or answers except as your role requires.",
  "Never share your username or password, and never sign in for someone else.",
  "Use the respondent's contact details **only** to manage their participation in this study (invitations, reminders, appointments).",
  "Never tell a respondent, lender or anyone else that answers affect financing. The study generates **no score, rating or financing decision**.",
  "If a respondent asks to withdraw, stop contacting them and tell the Field Coordinator or PI the same day so the withdrawal is recorded.",
  "Report a lost device, a suspected account compromise, or data sent to the wrong person to the PI immediately.",
];

const INTERNAL_TROUBLE = [
  ["\"This screen isn't part of your role\"", "The screen belongs to another role (often an old bookmark or shared link).", "Select **Go to my start screen**. If you need that screen, ask the PI about your role."],
  ["\"Too many sign-in attempts from this network\"", "Sign-in is rate-limited per network; an office shares one address.", "Wait a minute and try again. A wrong password says so explicitly."],
  ["A register shows fewer rows than expected", "Registers show 20 rows per page to begin with; a Contact RA sees only assigned cases.", "Choose more rows under **Show** at the foot of the list, use the page numbers or **Next**, or search. Ask the Field Coordinator to assign the case."],
  ["A button is greyed out", "A required step is missing (a note, an authenticity decision, a selection).", "Read the message beside the button; complete the missing step first."],
  ["\"KoboToolbox couldn't be reached\"", "KoboToolbox is slow or the connection token has changed.", "Try again in a few minutes. If it persists, tell the PI."],
  ["Form PDFs says \"Not in sync with KoboToolbox yet\"", "The counts differ: a form was submitted or changed in KoboToolbox since the last sync (it runs every 15 minutes).", "Select **Sync now**. If it still differs, or says it couldn't reach KoboToolbox, try again in a few minutes and tell the PI if it persists."],
  ["A document says \"Already submitted\" and its answers are locked", "Its coding was already sent to KoboToolbox; changing it here would not change that record.", "To redo the coding, delete that record in KoboToolbox, then select **Sync now** on Form PDFs. The document unlocks."],
  ["A page keeps loading", "A slow or dropped connection.", "Refresh the page. Your saved work is not lost; unsaved typing may be."],
  ["A file upload seems stuck", "A large file on a slow connection takes time; the bar shows how much has been sent.", "Wait for **Saving…** and the file name. If it fails, try again or upload a smaller version."],
];

const GLOSSARY = [
  ["ABF-FST", "Agribusiness Bankability Framework for Food Systems Transformation — the doctoral study this portal supports."],
  ["Main-400 / Reserve-400", "The 400 selected organisations and their 400 locked, matched replacements."],
  ["Master ID", "System-generated organisation identifier, e.g. MID-HA-000001 (province code + sequence)."],
  ["Sample ID", "System-generated case identifier, e.g. SID-2026-000001. Never typed by hand, never reused."],
  ["Stratum", "The sampling cell: Province × Actor family × Size class."],
  ["Case", "One organisation's place in the sample (a Sample ID)."],
  ["Workflow status", "Where a Main case is, from S00 Selected to S11 Completed, or a drop state (S12–S15)."],
  ["Invitation", "A personal link (valid 14 days) plus an 8-character manual code, issued per case."],
  ["Eligibility", "The respondent's confirmation that they hold a senior, knowledgeable role."],
  ["Consent", "The respondent's recorded agreement to take part (participation consent). KII recording consent is separate."],
  ["PIS", "Participant Information Sheet, currently version 1.4."],
  ["AI research", "In PROIT, an AI searches public sources for an organisation and the respondent's published professional role and proposes background facts with sources. A researcher accepts or rejects each; nothing enters the profile automatically."],
  ["Interview sheet", "The locked pre-interview profile as the interviewer uses it: public facts to confirm, gaps to ask, and where the respondent's answers stand."],
  ["Reconciliation", "After the interview, the researcher's coded value for each fact the respondent corrected or qualified. A case is not complete until its profile is reconciled."],
  ["Protocol deviation", "A recorded reason why a profile could not be reconciled. It releases the case but leaves it flagged."],
  ["PROIT", "Pre-Interview Respondent & Organisation Intelligence and Verification Tool: background facts found before contact, confirmed by the respondent."],
  ["KoboToolbox", "The external data-collection service that hosts the three study forms."],
  ["Submission", "One completed KoboToolbox form."],
  ["Sync", "Bringing the portal's own copy of the three KoboToolbox forms level with KoboToolbox. Automatic every 15 minutes, or **Sync now**."],
  ["QA", "Quality assurance: automated checks plus a human decision on every questionnaire."],
  ["QA exception", "An automated flag raised by a QA rule, worked and closed by a person."],
  ["KII", "Key Informant Interview (target 60 completed)."],
  ["Documentary evidence", "Documents, digital platform and media sources analysed (target 50–75)."],
  ["Source file", "The uploaded scan, PDF, photo or document a documentary record is coded from. Stored privately; it can be removed or replaced."],
  ["Auto-fill", "A button on a document's page that has AI read the source file and draft the whole Document Analysis Tool for you to review. It never submits anything by itself."],
  ["AI draft", "The AI's proposed answers to the Document Analysis Tool: editable, reviewed by a person, and only sent to KoboToolbox when that person selects Submit."],
  ["Page range", "The pages of a long PDF that make up one evidence unit (up to 100), entered for Auto-fill."],
  ["Copy for another chapter", "A button on a document record: makes a new record for a different part of the same source, with the same details and its own copy of the file."],
  ["Quick add", "Documents → New document → upload a file: the AI fills in the record's details and drafts the coding form for you to review."],
  ["Record details", "A document's title, author, date, type, scope, value chain and source. They feed Section A of the coding form and can be corrected on the record page."],
  ["Read in parts", "Auto-fill option for a PDF over 100 pages: the AI codes each part of about 80 pages, then combines them into one draft."],
  ["Administration mode", "How the questionnaire was completed (codes 01–06)."],
  ["Follow-up", "An approved reminder due to be sent to an invited respondent (Day 2, Day 7)."],
  ["Withdrawal", "A participant's request to stop taking part, recorded once in the portal."],
  ["Audit log", "The permanent record of every sensitive action and who took it."],
  ["Data lock", "30 November 2026 — the date fieldwork data is frozen for analysis."],
];

module.exports = { REVISION, SITE, ROLE_TABLE, STATUS_TABLE, MODES_TABLE, signIn, changePassword, DATA_RULES, INTERNAL_TROUBLE, GLOSSARY };
