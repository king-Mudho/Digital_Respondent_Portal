const C = require("./common");
const { T } = require("./tasks");

const renum = (blocks, prefix) => {
  let n = 0;
  return blocks.map((b) => (b[0] === "h2" ? ["h2", `${prefix}.${++n} ${b[1]}`] : b));
};

function guide({ n, key, role, title, audience, purpose, can, cannot, landing, screens, routine, tasks, extraRules = [], trouble = [], quick }) {
  let tn = 0;
  const taskBlocks = [];
  for (const t of tasks) {
    for (const b of t) {
      if (b[0] === "h2") taskBlocks.push(["h2", `4.${++tn} ${b[1]}`]);
      else taskBlocks.push(b);
    }
  }
  return {
    file: `Role_Guide_${n}_${key}`,
    meta: {
      title: `Role Guide ${n}: ${title}`,
      short: `Role Guide ${n} · ${title}`,
      subtitle: `Step-by-step instructions for the ${role} role in the ABF-FST Digital Respondent Portal.`,
      audience,
      revision: C.REVISION,
    },
    blocks: [
      ["h1", "1. Your role at a glance", { newPage: false }],
      ["p", purpose],
      ["h3", "You can"],
      ["bullets", can],
      ["h3", "You cannot"],
      ["bullets", cannot],
      ["tip", "Where this fits", "The System Manual explains how the whole system works. This guide covers only what you do. Ask the Field Coordinator or PI when something is outside your role."],

      ["h1", "2. Signing in and your screens"],
      ...C.signIn(landing, role),
      ["h2", "Your screens"],
      ["table", ["Screen", "What you use it for"], screens, [0.3, 0.7]],
      ...C.changePassword,

      ["h1", "3. Your routine"],
      ["p", "A suggested rhythm. Adjust it to the Field Coordinator's plan."],
      ["table", ["When", "What to do"], routine, [0.22, 0.78]],

      ["h1", "4. Step-by-step tasks"],
      ...taskBlocks,

      ["h1", "5. Rules you must follow"],
      ["bullets", [...extraRules, ...C.DATA_RULES]],

      ["h1", "6. Troubleshooting"],
      ["table", ["Situation", "Likely cause", "What to do"], [...trouble, ...C.INTERNAL_TROUBLE], [0.28, 0.34, 0.38]],

      ["h1", "7. Quick reference"],
      ["kv", [
        ["Sign in", `${C.SITE}/admin/login`],
        ["You start on", landing],
        ...quick,
        ["Help", "Field Coordinator; PI: Happyson Saina, 0773943709, abffst.research.cut@gmail.com"],
      ]],
    ],
  };
}

module.exports = [
  guide({
    n: 1, key: "PI_Admin", role: "PI / System Admin", title: "PI / System Admin",
    audience: "The Principal Investigator (full access)",
    purpose: "As PI you own the study and the system. You see every screen, approve how fieldwork runs, create accounts, decide replacements and withdrawals, review the audit trail, and are the only person who can download the full operational data and the complete KoboToolbox data for cleaning and analysis.",
    can: [
      "Open all 19 screens, including the Audit Log and every export.",
      "Create, change and deactivate staff accounts and roles.",
      "Do everything the Field Coordinator can: register organisations, assign Contact RAs, verify cases in bulk, invite, activate Reserves, record withdrawals, take QA decisions, manage KII and document records, log costs.",
      "Download the full operational export, and each KoboToolbox form as an Excel workbook and a PDF ZIP.",
      "Manage the KoboToolbox forms and the connection to them.",
    ],
    cannot: [
      "Change a Sample ID or Master ID, or move a case through statuses the rules do not allow — nobody can.",
      "Pass a questionnaire QA without writing a note.",
      "Invite a locked Reserve.",
    ],
    landing: "Executive Dashboard",
    screens: [
      ["Executive, Sampling, Contact, QA, KII/Doc dashboards", "Monitor progress against targets."],
      ["Reports", "Analytics and charts for supervision meetings and progress reports."],
      ["Main-400 Register, Organisations", "The sample: cases, bulk verification, new organisations."],
      ["Appointments, Follow-ups", "Oversee contact and reminders."],
      ["Form PDFs", "Completed forms for all three KoboToolbox forms."],
      ["QA Queue, QA Exceptions", "Quality decisions and flags."],
      ["KII Register, Documents", "Qualitative and documentary strands."],
      ["Reserve Activation", "Replace dropped cases."],
      ["Cost", "Fieldwork spend."],
      ["Audit Log", "Who did what, when."],
      ["Export", "All data downloads."],
    ],
    routine: [
      ["Daily", "Executive Dashboard and Reports (last 7 days); QA Exceptions older than two days; Follow-ups backlog."],
      ["Weekly", "Coverage and administration-mode balance in Reports; Reserve activations; Audit Log review; cost review; download the questionnaire workbook to monitor data quality."],
      ["When staff change", "Create or deactivate accounts; reassign cases."],
      ["Before data lock (30 Nov 2026)", "Close QA decisions and exceptions; final exports; store them securely."],
    ],
    tasks: [
      [["h2", "Creating staff accounts"], ["steps", [
        `Open **${C.SITE}/django-admin/** and sign in with your PI account.`,
        "Select **Users → Add user**. Enter a username (e.g. firstname.lastname) and a strong temporary password; save.",
        "Fill in the name and **email address**, choose the **Role** under **ABF-FST role**, and save.",
        "Give the username and temporary password to the person separately (e.g. username by email, password by phone) and ask them to change it at first sign-in.",
        "To remove access, untick **Active** and save. Do not delete users; their audit history must remain.",
      ]]],
      T.dashboards, T.reports,
      [["h2", "Assigning cases to named Contact RAs"], ["p", "All 400 Main cases are currently assigned to the shared `contact_ra` account. Once individual Contact RA accounts exist, assign each case to its RA from the case page (**Assigned Contact RA**), then deactivate the shared account."]],
      T.pairAssign, T.bulkVerify, T.exports("pi"), T.audit, T.withdrawal, T.reserve, T.qaReview, T.qaExceptions,
      T.formPdfs("questionnaire, KII Guide and document", "adm_form_pdfs.jpg"),
      [["h2", "KoboToolbox: rotating credentials and changing forms"], ["steps", [
        "Change the KoboToolbox password, then create a new API token (**Account settings → Security**).",
        "On the server run `sudo bash /srv/agribiz-drp/deploy/configure-kobo.sh` and paste the new token when asked.",
        "In **QA Queue**, select **Sync now** and check the run succeeds.",
        "When editing a form, keep the identifier fields unchanged (see System Manual 9.2), test with a test invitation, and delete the test submission.",
      ]]],
      [["h2", "Before the first live invitation"], ["bullets", [
        "Collect respondent phone numbers on the case pages (many Main cases have none yet).",
        "Rotate the KoboToolbox password and API token.",
        "Add the Gmail App Password with `configure-email.sh` so **Email** buttons work.",
        "Complete the one-time Google Drive sign-in for offsite backups and store the encryption key in a password manager.",
        "Create named accounts for each RA and reassign cases.",
        "Run one user-acceptance invitation end to end on a real phone.",
      ]]],
    ],
    extraRules: [
      "Download raw KoboToolbox data only to encrypted, access-controlled storage; every download is audited.",
      "Share only the de-identified analysis export beyond the core team.",
    ],
    trouble: [
      ["Email buttons missing or failing", "Outgoing email not configured, or the Gmail App Password revoked.", "Run `configure-email.sh` on the server."],
      ["Workbook shows NOT_IN_PORTAL in portal_qa_status", "A submission that was not matched to a case (e.g. a test or a direct public-link submission).", "Check it in KoboToolbox; exclude or delete test submissions."],
    ],
    quick: [["Account admin", `${C.SITE}/django-admin/`], ["KoboToolbox", "https://kf.kobotoolbox.org"], ["Your exports", "Export → KoboToolbox data (Excel workbook, PDF ZIP)"]],
  }),

  guide({
    n: 2, key: "Field_Coordinator", role: "Field / Digital Coordinator", title: "Field / Digital Coordinator",
    audience: "Field and digital coordinators running day-to-day fieldwork",
    purpose: "You run fieldwork day to day: keep the sample moving through verification, make sure every case has a Contact RA and contact details, keep follow-ups and appointments on schedule, make replacement and withdrawal decisions with the PI, and oversee QA, KII and documentary work.",
    can: [
      "Open 18 screens — everything except the Audit Log.",
      "Register organisations, pair Reserves, assign Contact RAs and verify cases in bulk.",
      "Record respondents, invite, log contacts, send follow-ups, manage appointments.",
      "Record withdrawals and activate Reserves.",
      "Take QA decisions and work QA exceptions; manage KII and document records; log costs.",
      "Download the de-identified analysis export.",
    ],
    cannot: [
      "Open the Audit Log.",
      "Download the full operational export or the KoboToolbox data workbooks (PI only).",
      "Create staff accounts (ask the PI).",
    ],
    landing: "Executive Dashboard",
    screens: [
      ["Dashboards and Reports", "Track progress, coverage and bottlenecks."],
      ["Main-400 Register", "Cases, bulk verification."],
      ["Organisations", "Late additions and replacements."],
      ["Appointments, Follow-ups", "Keep contact on schedule."],
      ["Form PDFs", "Completed forms for all three forms."],
      ["QA Queue, QA Exceptions", "Support and cover the QA RA."],
      ["KII Register, Documents", "Oversee the other strands."],
      ["Reserve Activation", "Replace dropped cases."],
      ["Cost", "Log and monitor spend."],
      ["Export", "De-identified analysis export."],
    ],
    routine: [
      ["Morning", "Follow-ups due (make sure RAs send them); Appointments for today; QA Exceptions still open."],
      ["During the day", "Unblock cases with no phone number; answer RA questions; handle refusals and withdrawals."],
      ["End of day", "Reports (last 7 days): submissions, response rate, coverage; note strata falling behind."],
      ["Weekly", "Cases stuck at S05–S07 beyond Day 7; Reserve activations; cost entries; brief the PI."],
    ],
    tasks: [T.dashboards, T.reports, T.bulkVerify, T.pairAssign, T.respondents, T.invite, T.followUps, T.appointments, T.logContact, T.workflow, T.notEligible, T.withdrawal, T.reserve, T.registerOrg, T.proit, T.qaReview, T.qaExceptions, T.formPdfs("questionnaire, KII Guide and document", "adm_form_pdfs.jpg"), T.cost, T.exports("fc")],
    extraRules: ["Record a withdrawal the same day you hear of it.", "Activate a Reserve only with an authorised reason and written evidence."],
    trouble: [
      ["\"Move all\" shows 0", "No Main cases are at that step.", "Choose the next step in the list."],
      ["A case gets no reminders", "It was invited before reaching S03, or has no invitation.", "Verify it to S03 and issue a new invitation."],
    ],
    quick: [["Bulk verification", "Main-400 Register → Move cases through verification"], ["Replacement", "Reserve Activation → reason + evidence note"]],
  }),

  guide({
    n: 3, key: "Contact_RA", role: "Contact RA", title: "Contact Research Assistant",
    audience: "Research assistants who contact organisations and invite respondents",
    purpose: "You are the study's voice to the organisations assigned to you. You find the right senior person, record their contact details, send their personal invitation, log every attempt, send the approved reminders, and arrange calls for respondents who want help.",
    can: [
      "See the Main-400 Register — only the cases assigned to you — and open their case pages.",
      "Add and edit respondents and contact details.",
      "Send, resend and revoke invitations.",
      "Log contact attempts and change a case's status where allowed.",
      "Send follow-up reminders and manage appointments for your cases.",
    ],
    cannot: [
      "See cases assigned to other RAs, dashboards, QA, KII, documents, costs or exports.",
      "Assign cases, verify in bulk, activate Reserves or record a withdrawal (tell the Field Coordinator).",
      "See an invitation link again after leaving the page.",
    ],
    landing: "Main-400 Register",
    screens: [
      ["Main-400 Register", "Your assigned cases; select **View** to work on one."],
      ["Appointments", "Calls and sessions respondents have requested."],
      ["Follow-ups", "Reminders due today for your cases."],
    ],
    routine: [
      ["Start of day", "**Follow-ups**: send every reminder due and mark each sent. **Appointments**: confirm today's."],
      ["Main work", "Cases at **S03**: record the respondent and number, send invitations. Cases with no number: phone the organisation to identify the right person."],
      ["After every call or message", "Log the contact attempt with outcome and a short note."],
      ["End of day", "Anything unusual (refusal, withdrawal, wrong organisation) reported to the Field Coordinator."],
    ],
    tasks: [
      [["h2", "Finding your cases"], ["steps", [
        { text: "Select **Main-400 Register**. Only cases assigned to you are listed.", img: "cra_register.jpg", caption: "Main-400 Register for a Contact RA." },
        "Type a Sample ID, Master ID or organisation name in **Search**, or page through with **Next**.",
        "Select **View** to open the case page.",
      ]]],
      T.respondents, T.invite, T.logContact, T.followUps, T.appointments, T.phoneAssisted, T.notEligible,
      [["h2", "When someone refuses or asks to withdraw"], ["steps", [
        "Thank them politely and do not try to persuade them.",
        "Log the contact attempt with outcome **REFUSED** and their words in the note.",
        "Tell the Field Coordinator the same day. They record the withdrawal or refusal and decide on the Reserve.",
        "Do not contact the person again.",
      ]]],
      [["h2", "What to say to a respondent"], ["bullets", [
        "Who you are: a research assistant on the ABF-FST study at Chinhoyi University of Technology, led by Happyson Saina.",
        "Why them: their organisation was selected to take part in a doctoral study on agribusiness financing readiness.",
        "What it involves: a questionnaire of about 15–25 minutes, online or with a researcher by phone or WhatsApp.",
        "It is voluntary and confidential; no score, rating or financing decision is produced, and answers are never shared with lenders.",
        "Questions: Happyson Saina, 0773943709, abffst.research.cut@gmail.com.",
      ]]],
    ],
    extraRules: ["Contact only the cases assigned to you.", "Never send one organisation's link to another, and never post links in groups.", "Mark a reminder as sent only after you have sent it."],
    trouble: [
      ["The case is not in my register", "It is assigned to someone else or unassigned.", "Ask the Field Coordinator to assign it."],
      ["No **Send invitation** button", "Your role is read-only here, or the case is a locked Reserve.", "Check with the Field Coordinator."],
      ["WhatsApp opens the wrong chat", "The number is missing the country code.", "Edit the person: +263 followed by the number without the first 0."],
      ["I closed the page before copying the link", "Links are shown once.", "Select **Send new invitation (replaces current)**."],
    ],
    quick: [["Invitation valid", "14 days"], ["Reminders", "Day 2 and Day 7, from Follow-ups"], ["Outcome codes", "REACHED, NO_ANSWER, WRONG_NUMBER, REFUSED, RESCHEDULED, COMPLETED"]],
  }),

  guide({
    n: 4, key: "QUAN_QA_RA", role: "QUAN/Kobo QA RA", title: "Questionnaire QA Research Assistant",
    audience: "Research assistants who check the quality of questionnaire submissions",
    purpose: "You make sure every questionnaire counted towards the 400 target is complete, plausible and genuine. The system checks each submission automatically, but nothing passes QA until you (or the Field Coordinator or PI) decide, with a note.",
    can: [
      "See the QA Dashboard, QA Queue and QA Exceptions.",
      "Accept, re-query or reject submissions with a note.",
      "Assign, work and close QA exceptions.",
      "Run a KoboToolbox sync.",
      "Download and email PDFs of completed questionnaires.",
    ],
    cannot: [
      "See names, contact details or case pages; KII or document records; dashboards other than QA; exports.",
      "Change answers — corrections are made in KoboToolbox by whoever administered the questionnaire.",
      "Pass a submission without a note.",
    ],
    landing: "QA Dashboard",
    screens: [
      ["QA Dashboard", "Submissions today and in total, queue size, decisions, modes."],
      ["Form PDFs", "Readable copies of completed questionnaires."],
      ["QA Queue", "Take decisions; run a KoboToolbox sync."],
      ["QA Exceptions", "Automated flags to investigate and close."],
    ],
    routine: [
      ["Start of day", "QA Dashboard: how many are waiting. **Sync now** on the QA Queue if you expect new submissions."],
      ["Main work", "Oldest QA exceptions first, then the QA Queue oldest first."],
      ["For each submission", "Open the PDF, check the rules, decide with a clear note."],
      ["End of day", "Queue and exceptions no older than two days; report patterns (e.g. many short completions from one mode) to the Field Coordinator."],
    ],
    tasks: [
      [["h2", "Reading the QA Dashboard"], ["steps", [
        { text: "Select **QA Dashboard**. It shows submissions today and cumulatively, the open queue, decisions recorded, and completions by administration mode (01–06).", img: "qa_dashboard.jpg", caption: "QA Dashboard." },
        "Select **Refresh** to update the figures, or **Open QA queue** to start work.",
      ]]],
      T.qaReview, T.qaExceptions, T.formPdfs("questionnaire"),
      [["h2", "Writing good QA notes"], ["bullets", [
        "State what you checked and what you found: \"Duration 3 min; answers straight-lined in Sections 4–6; re-queried with RA\".",
        "For Accept: \"All required answers present; duration 28 min plausible; no duplicate\".",
        "For Re-query: say exactly what needs confirming or completing.",
        "Never include personal opinions about the respondent.",
      ]]],
    ],
    extraRules: ["Decide on evidence, not on who the organisation is.", "Never download PDFs to personal devices or share them outside the team."],
    trouble: [
      ["Accept / Re-query / Reject are greyed out", "No note written yet.", "Type the note first."],
      ["A submission I expected is not in the queue", "It has not been pulled yet, or it was set aside (not launched from the portal).", "Select **Sync now**; if still missing, tell the Field Coordinator."],
    ],
    quick: [["Duration limits", "5 to 90 minutes"], ["Duplicate window", "24 hours"], ["Required fields", "65 from the live questionnaire"]],
  }),

  guide({
    n: 5, key: "KII_RA", role: "KII RA", title: "Key Informant Interview Research Assistant",
    audience: "Research assistants who arrange, conduct and process Key Informant Interviews",
    purpose: "You take each Key Informant Interview from first contact to a coded transcript: keep the KII record's status current, record participation and recording consent separately, and complete the KII Guide in KoboToolbox so the interview can be analysed.",
    can: [
      "See the KII/Doc Dashboard, the KII Register and KII records.",
      "Create KII records; change status; record participation and recording consent; update transcript and coding progress.",
      "Download PDFs of completed KII Guide forms.",
    ],
    cannot: [
      "See or edit documents, questionnaire QA, the Main-400 register, costs or exports.",
      "Mark an interview completed with a recording unless recording consent was recorded.",
    ],
    landing: "KII/Doc Dashboard",
    screens: [
      ["KII/Doc Dashboard", "KIIs completed against the target of 60; KIIs by status."],
      ["Form PDFs", "Completed KII Guide forms."],
      ["KII Register", "All KII records; create and manage."],
    ],
    routine: [
      ["Weekly planning", "KII Register filtered mentally by status: PROSPECT and INVITED need contact; SCHEDULED need preparation."],
      ["Before each interview", "Check the record and any PROIT gap-engine questions; prepare the KII Guide."],
      ["At the interview", "Record participation consent, and recording consent if recording."],
      ["After each interview", "Mark COMPLETED (tick Recording made only if recorded); complete the KII Guide in KoboToolbox; update transcript and coding as work progresses."],
    ],
    tasks: [
      [["h2", "Reading the KII/Doc Dashboard"], ["img", "kii_dashboard.jpg", "KII / Document Dashboard."]],
      T.kii, T.formPdfs("KII Guide", "kii_register.jpg").map((b) => (b[0] === "steps" ? ["steps", b[1].map((s, i) => (i === 0 ? "Select **Form PDFs**. You see the completed KII Guide forms from KoboToolbox, newest first." : s)).filter((s) => !String(s.text ?? s).includes("For the questionnaire only"))] : b)),
      [["h2", "Consent in interviews"], ["bullets", [
        "Read or summarise the information sheet and ask for agreement **before** the first question.",
        "Ask separately whether the interview may be recorded. If they say no, take notes only.",
        "Record each decision on the KII record straight away with the matching button.",
        "If they later ask to stop or withdraw, stop, and tell the PI the same day.",
      ]]],
    ],
    extraRules: ["Keep recordings and transcripts only in the study's approved storage.", "Anonymise transcripts before they are shared for coding beyond the core team."],
    trouble: [
      ["COMPLETED with recording is refused", "Recording consent not recorded.", "Record recording consent first, or untick Recording made."],
      ["No PDF on the KII record", "The KII Guide has not been submitted with this KII ID.", "Check the KII ID in the KoboToolbox form."],
    ],
    quick: [["Target", "60 completed KIIs"], ["Status order", "PROSPECT → INVITED → SCHEDULED → COMPLETED"], ["Transcript", "NOT_STARTED → IN_PROGRESS → VERIFIED → ANONYMISED"], ["Coding", "NOT_STARTED → IN_PROGRESS → COMPLETE"]],
  }),

  guide({
    n: 6, key: "Documentary_RA", role: "Documentary RA", title: "Documentary Evidence Research Assistant",
    audience: "Research assistants who collect, assess and code documentary evidence",
    purpose: "You build the documentary corpus of 50–75 coded sources: record each document, judge its authenticity before it can be included, explain your reasoning in a memo, and code it with the Document, Digital Platform & Media Analysis Tool in KoboToolbox.",
    can: [
      "See the KII/Doc Dashboard, the Documents register and document records.",
      "Create document records, assess authenticity, include or exclude, write memos.",
      "Download PDFs of completed document coding forms.",
    ],
    cannot: [
      "See or edit KII records, questionnaire QA, the Main-400 register, costs or exports.",
      "Include a document before its authenticity has been assessed.",
    ],
    landing: "KII/Doc Dashboard",
    screens: [
      ["KII/Doc Dashboard", "Documents by type and QA status against the 50–75 target."],
      ["Form PDFs", "Completed document coding forms."],
      ["Documents", "The corpus; create and manage records."],
    ],
    routine: [
      ["When you find a source", "Create the record with a precise reference and an evidence extract."],
      ["Assessment", "Verify authenticity against the source; mark Verified or Disputed; write the memo."],
      ["Inclusion", "Include or Exclude with reasons in the memo."],
      ["Coding", "Complete the Document Analysis Tool in KoboToolbox using the DOC ID."],
    ],
    tasks: [
      [["h2", "Reading the dashboard"], ["img", "kii_dashboard.jpg", "Documents by type and by QA status."]],
      T.documents,
      T.formPdfs("document coding", "doc_register.jpg").map((b) => (b[0] === "steps" ? ["steps", b[1].map((s, i) => (i === 0 ? "Select **Form PDFs**. You see the completed Document Analysis Tool forms from KoboToolbox, newest first." : s)).filter((s) => !String(s.text ?? s).includes("For the questionnaire only"))] : b)),
      [["h2", "Judging authenticity"], ["bullets", [
        "**Official**: from a government body, regulator or the organisation itself — check it on the issuer's own site or registry.",
        "**Secondary**: reports, studies, articles — check the publisher, author and date.",
        "**Platform**: websites, social media, digital platforms — capture the URL and date accessed; corroborate claims elsewhere.",
        "Mark **Disputed** when authorship, date or content cannot be confirmed, and say why in the memo.",
      ]]],
    ],
    extraRules: ["Record the exact source reference so another researcher can find the same document.", "Do not store copyrighted documents outside the study's approved storage."],
    trouble: [
      ["**Include** is greyed out", "Authenticity not assessed.", "Mark verified or disputed first."],
      ["No coding form PDF on the record", "The form was not submitted with this DOC ID.", "Check the DOC ID in the KoboToolbox form."],
    ],
    quick: [["Target", "50–75 coded documents"], ["Types", "OFFICIAL, SECONDARY, PLATFORM"], ["Order", "Create → assess authenticity → include/exclude → memo → code"]],
  }),

  guide({
    n: 7, key: "Analyst", role: "Data Analyst", title: "Data Analyst",
    audience: "Analysts monitoring progress and working with de-identified data",
    purpose: "You monitor fieldwork through the dashboards and Reports and prepare analysis from the de-identified export. Your role is read-only: you cannot change any record, and you never see names or contact details.",
    can: [
      "Open the Executive, Sampling, Contact and KII/Doc dashboards, Reports and Cost (view).",
      "Download the de-identified analysis export (CSV).",
    ],
    cannot: [
      "Change any record anywhere.",
      "See case pages, respondent names, contact details or completed forms.",
      "Download the operational export or the KoboToolbox data (ask the PI for the de-identified extracts you need).",
    ],
    landing: "Executive Dashboard",
    screens: [
      ["Executive, Sampling, Contact, KII/Doc", "Progress and coverage."],
      ["Reports", "Analytics with charts and tables."],
      ["Cost", "Spend and cost per completed case (view only)."],
      ["Export", "De-identified analysis export."],
    ],
    routine: [
      ["Weekly", "Reports for the last 7 and 30 days; coverage by province, organisation type and size; mode balance; completion times."],
      ["Monthly", "Download the analysis export; update progress tables for the PI and supervisors."],
      ["Before data lock", "Agree the final export and cleaning plan with the PI."],
    ],
    tasks: [
      [["h2", "Your start screen"], ["img", "an_dashboard.jpg", "Executive Dashboard as seen by the Analyst."]],
      T.dashboards, T.reports, T.exports("analyst"),
      [["h2", "Working with the analysis export"], ["bullets", [
        "One row per questionnaire submission. `sample_id` links to the case; `master_id` to the organisation.",
        "`qa_status`: use only **QA_PASSED** rows for the main analysis unless the PI says otherwise.",
        "`consent_withdrawn` = True marks a participant who later withdrew; follow the PI's decision on how to treat these.",
        "`completion_seconds` is the time taken; `administration_mode` is 01–06 (see the table in the Quick reference).",
        "Store exports only on encrypted, access-controlled storage and delete working copies when no longer needed.",
      ]]],
    ],
    extraRules: ["Never try to re-identify organisations or people from exported data."],
    trouble: [["Export button missing", "Only the de-identified export is available to Analysts.", "Ask the PI for any further extract."]],
    quick: [["Administration modes", C.MODES_TABLE.map((m) => `${m[0]} ${m[1]}`).join("; ")]],
  }),

  guide({
    n: 8, key: "Supervisor", role: "Supervisor (read-only)", title: "Supervisor (read-only)",
    audience: "Academic supervisors and others overseeing the study",
    purpose: "You oversee the study with read-only access to almost every screen: progress, the sample, contact activity, QA, the KII and documentary strands, and costs. You can open case pages and completed-form PDFs, but you cannot change anything.",
    can: [
      "Open 17 screens: all dashboards, Reports, Main-400 Register and case pages, Organisations, Appointments, Follow-ups, Form PDFs, QA Queue, QA Exceptions, KII Register, Documents, Reserve Activation and Cost.",
      "Download PDFs of completed forms for all three forms.",
    ],
    cannot: [
      "Change, send, assign, decide or log anything — forms and buttons are replaced by \"Your role has read-only access\" notes.",
      "Open the Audit Log or Export.",
    ],
    landing: "Executive Dashboard",
    screens: [
      ["Dashboards and Reports", "Progress, coverage, quality."],
      ["Main-400 Register and case pages", "How individual cases are being handled."],
      ["Appointments, Follow-ups", "Whether contact is on schedule."],
      ["Form PDFs", "Completed questionnaires, KII Guides and document coding forms."],
      ["QA Queue, QA Exceptions", "Quality decisions and flags."],
      ["KII Register, Documents", "Qualitative and documentary strands."],
      ["Reserve Activation, Cost", "Replacements and spend."],
    ],
    routine: [
      ["Before supervision meetings", "Reports (last 30 days): funnel, response rate, coverage, QA outcomes, mode balance."],
      ["Spot checks", "Open a few case pages and completed-form PDFs; read QA notes and exceptions."],
      ["Monthly", "Cost per QA-passed case; Reserve activations and their evidence notes."],
    ],
    tasks: [
      T.dashboards, T.reports,
      [["h2", "Reviewing a case read-only"], ["steps", [
        "Select **Main-400 Register**, search for a case, and select **View**.",
        { text: "Review the respondent, invitation history, completed questionnaire, status and contact timeline. Controls are replaced by read-only notes.", img: "sup_case.jpg", caption: "A case page in read-only view." },
      ]]],
      [["h2", "Reviewing QA"], ["img", "sup_qa_queue.jpg", "QA Queue in read-only view."], ["p", "Check that notes explain decisions and that exceptions are closed with reasons."]],
      T.formPdfs("questionnaire, KII Guide and document", "adm_form_pdfs.jpg").map((b) => (b[0] === "steps" ? ["steps", [b[1][0], b[1][1]]] : b)),
    ],
    extraRules: ["Raise any concern about how a case, consent or data was handled with the PI directly."],
    trouble: [["\"Your role has read-only access to this screen\"", "Expected for the Supervisor role.", "No action needed."]],
    quick: [["Most useful screen", "Reports"]],
  }),
];
