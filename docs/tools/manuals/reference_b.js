// Screen and Button Reference, part B: quality, KII, documents, completed forms, cost, audit and export.
// Row format as in reference_a.js: [control, what it does and when to use it, why it exists, what happens next, options]
const { R } = require("./reference_a");
const w = { write: true };

const screens = [
  {
    id: "qa_queue", group: "Quality checking", title: "QA Queue (with the KoboToolbox sync panel)", path: "/admin/qa",
    roles: [R.PI, R.FC, R.QA, R.SUP],
    purpose: "Every completed questionnaire waits here for a human quality decision. Nothing is ever passed automatically.",
    rows: [
      ["KoboToolbox sync → Sync now", "Pulls completed questionnaires from KoboToolbox right now, instead of waiting for the automatic check (every 15 minutes).", "KoboToolbox is where the questionnaire is answered; the portal has to fetch what was submitted. A new or edited submission enters the queue when it is fetched.", "A summary shows how many were new or changed. “Not connected” or “Last sync failed” explains a problem; the automatic check keeps trying.", w],
      ["Note (required)", "Write what you checked and found (for example “duration 28 min plausible, no duplicate”).", "A decision nobody explained looks the same as one nobody made; the note is what a later reviewer relies on.", "The decision buttons stay off until there is a note."],
      ["Accept", "Records that the submission passed quality checking.", "Only a person can pass a questionnaire; even one that triggered no rule is not passed until someone accepts it.", "The submission is marked QA passed, the case moves on, and the decision is audited.", w],
      ["Re-query", "Sends the submission back with a question about what needs confirming or fixing.", "Some problems (an odd answer, a very short time) need the respondent or interviewer to clarify before a decision.", "The submission is marked as queried and the case moves to “QA query”. If the answers are edited in KoboToolbox, the next sync puts it back in the queue.", w],
      ["Reject", "Records that the submission fails and will not be used.", "Fabricated, duplicate or unusable data must be kept out of the analysis, but never silently deleted.", "The submission is marked rejected. It is kept and the decision and your note are audited.", w],
    ],
  },
  {
    id: "qa_exceptions", group: "Quality checking", title: "QA Exceptions", path: "/admin/qa/exceptions",
    roles: [R.PI, R.FC, R.QA, R.SUP],
    purpose: "Flags the automatic quality rules raised (for example a very short completion time). Each waits for someone to deal with it and explain what was done.",
    rows: [
      ["Only mine", "Shows just the exceptions assigned to you.", "Lets each QA person work their own list.", "The list narrows and returns to page 1."],
      ["Include resolved", "Also shows exceptions that were already closed.", "Useful for checking what was done before, or how similar flags were handled.", "Closed exceptions appear with who closed them, when and why."],
      ["Assign to", "Chooses who deals with the exception, or Unassigned.", "So each flag has an owner and none is left for “someone”.", "The exception appears in that person's “Only mine” list.", w],
      ["What was done about it? (required to close)", "Write what you did (what you checked, who you contacted).", "A closure nobody explained looks the same as one nobody looked at.", "The two closing buttons stay off until there is a note.", w],
      ["Resolved", "Closes the exception because you dealt with a real problem.", "Distinguishes “there was a problem and it was fixed” from a false alarm, so rules can be tuned.", "The exception is closed with your name, the time and your note.", w],
      ["Not a real problem", "Closes the exception because the flag was a false alarm.", "False alarms are information too: many of them means a rule threshold may be wrong.", "The exception is closed as dismissed, with your note.", w],
    ],
  },

  {
    id: "kii_register", group: "Key Informant Interviews", title: "KII Register", path: "/admin/kii",
    roles: [R.PI, R.FC, R.KII, R.SUP],
    purpose: "All Key Informant Interview records. Each record identifies a real person, so nothing here leaves the study team.",
    rows: [
      ["New KII record", "Opens the form to create a KII record.", "Each interview gets its own record and KII ID from the start of contact.", "The New KII Record screen opens.", { only: [R.PI, R.FC, R.KII], write: true }],
      ["Search KII ID, name or role", "Filters the list as you type.", "Finding one participant among dozens.", "Only matching records are listed."],
      ["Manage", "Opens the KII record.", "All work on an interview happens on its own record.", "The KII record opens."],
      ["Show / page numbers", "Choose rows per page and move between pages.", "As on every register.", "The list redraws."],
    ],
  },
  {
    id: "kii_new", group: "Key Informant Interviews", title: "New KII Record", path: "/admin/kii/new",
    roles: [R.PI, R.FC, R.KII],
    purpose: "Starts the record for one interview.",
    rows: [
      ["Stakeholder category, Participant name, Participant role, Preferred mode", "Say who the participant is and how they prefer to be interviewed.", "The category places the interview in the KII design; the name and role are needed to arrange it. They stay in the portal and are never put into web addresses.", "Nothing is saved until you select Create KII record.", w],
      ["Create KII record", "Saves the record.", "The KII ID (for example KII-0026) is generated by the system so it is never typed or reused.", "The record opens at its starting status, with no consent recorded yet.", w],
    ],
  },
  {
    id: "kii_record", group: "Key Informant Interviews", title: "KII record", path: "/admin/kii/{id}",
    roles: [R.PI, R.FC, R.KII, R.SUP],
    purpose: "The whole life of one interview: status, consent, the interview itself, transcript and coding.",
    rows: [
      ["Status buttons (INVITED, SCHEDULED, COMPLETED, DECLINED, NO_SHOW)", "Move the interview to the next status as things happen. Only valid next statuses are shown: a prospect can be invited or decline; an invited person scheduled or decline; a scheduled interview completed, no-show or decline; a no-show can be rescheduled.", "A status should only follow what really happened, and COMPLETED, DECLINED are final.", "The status changes and is audited. A final status shows no more buttons.", w],
      ["Recording made (tick box, when marking COMPLETED)", "Tick it only if the interview was audio-recorded.", "A recorded interview needs the participant's separate recording consent; the portal refuses to complete it as recorded without that.", "If recording consent is missing you are told, and the status does not change.", w],
      ["Record participation consent", "Records that the participant agreed to take part, after you read or summarised the information sheet.", "Nobody is interviewed without consent. The interview link stays hidden until this is recorded.", "The consent is recorded (with the information sheet version). Continue this interview appears.", w],
      ["Record recording consent", "Records that the participant agreed to be audio-recorded.", "Recording consent is always a separate decision; it is never assumed from taking part.", "Recording consent is recorded and a recorded interview can be completed.", w],
      ["Continue this interview", "Opens the KoboToolbox KII Guide in a new tab with this record's KII ID already filled in.", "So the completed form always matches this record and the ID can never be mistyped. Only the ID and your username are sent, never the participant's name.", "The KoboToolbox form opens. When submitted, the completed form appears under Completed KII form.", { only: [R.PI, R.FC, R.KII], write: true }],
      ["Transcript status (NOT_STARTED, IN_PROGRESS, VERIFIED, ANONYMISED)", "Record how far the transcript has got.", "A transcript must be verified and anonymised before it can be analysed or quoted.", "The status changes and cannot go backwards.", w],
      ["Coding status (NOT_STARTED, IN_PROGRESS, COMPLETE)", "Record how far the coding has got. It moves to COMPLETE by itself when the completed KII Guide is synced for this KII ID.", "Shows what has and has not been analysed.", "The status changes and cannot go backwards.", w],
      ["Completed KII form → Download PDF", "Downloads the completed KII Guide for this record as a readable PDF.", "A readable copy without opening KoboToolbox.", "A PDF downloads; the download is audited."],
    ],
  },

  {
    id: "docs_register", group: "Documentary evidence", title: "Documents (the corpus)", path: "/admin/documents",
    roles: [R.PI, R.FC, R.DOC, R.SUP],
    purpose: "The register of documentary evidence (target 50–75 coded, included documents).",
    rows: [
      ["New document", "Opens the New Documentary Evidence Record screen.", "Every source needs a record with a document ID before it can be coded.", "The New document screen opens.", { only: [R.PI, R.FC, R.DOC], write: true }],
      ["Search title, ID or author", "Filters the list as you type.", "Finding one document in 100 or more.", "Only matching documents are listed."],
      ["Manage", "Opens the document record.", "All work on a document happens on its own record.", "The document record opens."],
      ["Show / page numbers", "Choose rows per page and move between pages.", "As on every register.", "The list redraws."],
    ],
  },
  {
    id: "docs_new", group: "Documentary evidence", title: "New Documentary Evidence Record", path: "/admin/documents/new",
    roles: [R.PI, R.FC, R.DOC],
    purpose: "Creates a document record. The fastest way is to upload the file and let the AI fill in the record and draft the coding form.",
    rows: [
      ["Choose file (Fastest: upload the document)", "Choose the document: PDF, Word, Excel, text or CSV, or a JPG/PNG scan or photo (up to 20 MB).", "The AI can read all of these, so you do not retype details that are already on the first page.", "Nothing is sent until you select Upload and auto-fill.", w],
      ["Optional: Title", "Type a title of your own.", "You may want a specific name, for example for one chapter of a report.", "A typed title is kept; the AI does not replace it.", w],
      ["Optional: Pages to read", "Enter the pages of a long PDF that make up this evidence unit, for example 290-340.", "The AI reads at most 100 pages at a time, and a long report holds several evidence units.", "Only those pages are read. With no title, the AI names the part.", w],
      ["Optional: Read the whole document in parts", "Ticks the option to read a PDF longer than 100 pages in parts of about 80 pages, then combine them.", "For a document you want coded as one unit; slower and dearer, and the ratings need extra checking.", "The screen shows how many parts and asks you to confirm before it starts.", w],
      ["Upload and auto-fill", "Creates the record, uploads the file, and starts the AI: first it fills in the record's details, then it drafts the whole coding form.", "Saves typing every detail and every answer; a person still reviews and submits.", "The review screen opens and shows “Step 1 of 2… Step 2 of 2”. If the file cannot be used, nothing is created.", w],
      ["Title, Author / speaker, Source URL / reference, Document type, Geographic scope, Evidence extract → Create document record", "The manual way: type the details yourself and save.", "For a source with no file yet, or when AI drafting is switched off.", "The record is created with a document ID (for example DOC-0025) and opens.", w],
    ],
  },
  {
    id: "doc_record", group: "Documentary evidence", title: "Document record", path: "/admin/documents/{id}",
    roles: [R.PI, R.FC, R.DOC, R.SUP],
    purpose: "Everything about one document: authenticity, the decision to include it, its file, its details, its coding and its memo.",
    rows: [
      ["Mark verified / Mark disputed", "Records your judgement of whether the document is what it claims to be: the right author, date and content.", "Documents are evidence; a forged or doubtful one must not enter the corpus unnoticed. Disputed documents are kept and explained, not deleted.", "The authenticity changes and is audited. Include becomes available once assessed.", w],
      ["Include / Exclude", "Decides whether the document counts in the corpus.", "A document cannot be Included until authenticity has been assessed, so unassessed evidence never counts.", "The QA status changes; Include stays greyed out while authenticity is Unverified.", w],
      ["Source file → Choose File", "Uploads or replaces the source (up to 20 MB). Replacing removes the old file and any unsubmitted draft made from it.", "The record keeps one current source. A draft of the wrong document must never be submitted for the right one.", "A bar shows progress, then the file name appears. With Start Auto-fill ticked, the review screen opens.", w],
      ["Start Auto-fill as soon as the file is uploaded (tick box)", "When ticked, uploading immediately starts the AI draft.", "Saves a step for the common case.", "After the upload, the review screen opens and the AI starts reading.", w],
      ["Remove file", "Deletes the source file from the server.", "For a wrong upload. It also discards the unsubmitted AI draft made from it; a draft already submitted is kept as the record of what was filed.", "A confirmation names what goes. The record says “No file uploaded yet”.", w],
      ["Copy for another chapter (Chapter title, Pages to read, Copy and auto-fill)", "Makes another record for a different part of the same source: same author, date, source and type, and its own copy of the file.", "A long report holds several evidence units, each of which should be coded, judged and exported on its own.", "A new record is created (and, with AI on, drafted) and opens. Authenticity and inclusion are not copied.", w],
      ["Record details → Save details", "Edits the title, author, date, source, scope, value chain and type.", "These feed Section A of the coding form; if the AI filled them in from the document, this is where you check and correct them.", "“Details saved.” The draft and the submission use the corrected values.", w],
      ["Code this document", "Opens the KoboToolbox Document Analysis Tool with the document ID and details filled in.", "For coding by hand, or when the AI cannot read the source.", "The KoboToolbox form opens in a new tab.", w],
      ["Auto-fill", "Opens the review screen for the AI draft of the whole coding form.", "A fast first draft that a person then checks.", "The Auto-fill review screen opens.", w],
      ["Interpretive memo → Save memo", "Writes down your reasoning: why authenticity was disputed, how you read the document.", "The memo is the audit trail of your judgement, needed for the dissertation.", "A “saved” message; the memo stays on the record.", w],
      ["Completed coding form → Download PDF", "Downloads the completed coding form for this document.", "A readable copy of what was submitted.", "A PDF downloads (only if a form was submitted with this document ID)."],
    ],
  },
  {
    id: "doc_autofill", group: "Documentary evidence", title: "Auto-fill review screen", path: "/admin/documents/{id}/ai-draft",
    roles: [R.PI, R.FC, R.DOC, R.SUP],
    purpose: "Where you review the AI's draft of the KoboToolbox coding form, edit it and submit it. Nothing reaches KoboToolbox until you select Submit.",
    rows: [
      ["Pages to read", "For a PDF over 100 pages, enter the pages that make up this evidence unit.", "The AI reads at most 100 pages at a time.", "Only those pages are drafted; locators keep the original page numbers.", w],
      ["Read the whole document in parts", "Reads the whole PDF (or a long range) in parts of about 80 pages and combines them.", "For one coding of a long document; costs about the number of parts plus one times an ordinary draft.", "You are asked to confirm. Progress shows “Read part 3 of 8”, then “Combining the parts”.", w],
      ["Generate AI draft / Regenerate draft", "Starts the AI reading the source. Regenerate replaces the current draft and any unsaved edits.", "Each draft is a paid request, so it starts only when you ask; regenerating asks first because it discards your edits.", "The AI works in the background (usually one to five minutes) and you can leave the page. The draft appears here when ready.", w],
      ["The draft fields (sections A to L)", "Every question of the form, with the AI's answer. Edit any grey-free field: text, choices, tick boxes, dates.", "The AI drafts; you are responsible for the judgements (strength ratings, hypothesis codes) that are the study's documentary analysis.", "Edits are kept in the browser until you select Save changes.", w],
      ["Section A grey fields (DOC ID, author, title, date, source)", "Come from the record and cannot be edited here; use “edit the record details”.", "The draft must agree with the record it is attached to.", "Corrections on the record show here at once and are the values submitted."],
      ["Add metric / Remove this metric (Section J)", "Adds or deletes a row of the quantitative metrics table.", "Numbers in the source (percentages, amounts, targets) are recorded one per row with a locator.", "The row is added or removed in the draft.", w],
      ["Save changes", "Saves your edits to the draft on the server.", "Lets you stop and finish later without submitting.", "“Changes saved.” The button is unavailable after submission.", w],
      ["Submit to KoboToolbox", "Sends the reviewed draft to KoboToolbox as a completed record, after you confirm. It saves your edits first.", "The one place the portal writes to KoboToolbox, and only on this deliberate click: a person, not the AI, submits the study's documentary analysis. Once only, so no duplicate.", "“Submitted to KoboToolbox, and a copy is now held in the portal.” The answers lock and the screen says “Already submitted”. A second click is refused.", w],
    ],
  },

  {
    id: "forms", group: "Completed forms and exports", title: "Completed forms (Form PDFs)", path: "/admin/submissions",
    roles: [R.PI, R.FC, R.QA, R.KII, R.DOC, R.SUP],
    purpose: "The completed KoboToolbox forms for your role (the questionnaire, the KII Guide or the Document Analysis Tool; the PI, coordinator and supervisor can switch between all three).",
    rows: [
      ["Form (drop-down)", "Chooses which form to list. Shown only to roles that may see more than one.", "Each role sees only its own form, because raw answers can identify organisations and people.", "The list and the sync panel change to that form.", { only: [R.PI, R.FC, R.SUP] }],
      ["Sync panel: “In sync with KoboToolbox”", "Shows how many submissions KoboToolbox holds and how many the portal holds, and when they were last matched.", "The portal keeps its own copy of the completed forms. If the two numbers differ, the portal is behind.", "Read only. “Not in sync” means press Sync now."],
      ["Sync now", "Pulls that form from KoboToolbox now and updates the portal's copy.", "The automatic sync runs every 15 minutes; this brings it up to date immediately. It also notices edits and deletions made in KoboToolbox.", "The counts refresh. A KII record's coding can move to COMPLETE; a document whose submission was deleted in KoboToolbox unlocks.", w],
      ["✓ saved in portal (on each row)", "Says the portal holds an identical copy of that submission.", "Proof, row by row, that nothing was lost or changed between KoboToolbox and the portal.", "Read only. It is missing until the next sync for a new or edited row."],
      ["Download PDF", "Downloads that completed form as a readable PDF (sections, questions, answers as words).", "A readable copy for records, meetings and checking.", "A PDF downloads; the download is audited.", { }],
      ["Email to me", "Emails that PDF to the address on your own account.", "A PDF is a full research record, so it goes only to you, never to a typed-in address.", "“Sent to …” (address masked). Recorded in the audit log.", w],
      ["Email to respondent (questionnaire only)", "Emails the respondent a copy of their own answers, at the address on their case, after you confirm.", "Respondents may ask for their answers; the copy goes only to the address on file and only while their consent stands.", "A confirmation first; then “Sent to …”. Refused if consent was withdrawn or no email is on file.", { only: [R.PI, R.FC, R.QA], write: true }],
      ["Excel workbook", "Downloads every submission of the form as an analysis-ready workbook: answers as codes and as labels, a question dictionary, choice lists, a sheet for each repeating group.", "Analysis in SPSS, Stata or R needs the answers, not just the portal's case data.", "An .xlsx file downloads; the download is audited.", { only: [R.PI] }],
      ["All as PDFs (ZIP)", "Downloads every completed form as a PDF in one ZIP with a manifest.", "An archive of the completed forms for the data lock.", "The download starts at once and grows as each form is added.", { only: [R.PI] }],
      ["Show / page numbers", "Choose rows per page and move between pages.", "As on every register.", "The list redraws."],
    ],
  },
  {
    id: "cost", group: "Study administration", title: "Cost Dashboard", path: "/admin/cost",
    roles: [R.PI, R.FC, R.AN, R.SUP],
    purpose: "What the fieldwork has cost, by category, so cost per completed case can be reported.",
    rows: [
      ["Spend by category", "Shows spend for RA allowance, airtime/data, transport, accommodation, hosting, messaging and other.", "Funders and the dissertation need the real cost of each completed case.", "Read only."],
      ["Log a cost event: Date, Category, Amount → Log cost", "Records one expense.", "Costs are logged as they happen so the total stays true, and each event records who approved it.", "The event is added and the total increases by that amount.", { only: [R.PI, R.FC], write: true }],
    ],
  },
  {
    id: "audit", group: "Study administration", title: "Audit Log", path: "/admin/audit",
    roles: [R.PI],
    purpose: "The permanent record of who did what and when: QA decisions, downloads, emails of copies, submissions to KoboToolbox, withdrawals, reserve activations, status changes and other changes to records.",
    rows: [
      ["The list of events", "Shows each action with who did it, what it was done to and when, newest first.", "Research governance needs to be able to show who handled sensitive data and made key decisions. Entries are added by the system and cannot be edited or deleted.", "Read only."],
      ["Show / page numbers", "Choose rows per page and move between pages.", "The log grows quickly; a larger page helps when searching for one event.", "The list redraws."],
    ],
  },
  {
    id: "export", group: "Study administration", title: "Export", path: "/admin/export",
    roles: [R.PI, R.FC, R.AN],
    purpose: "Downloads of data for analysis and for the data lock. Every download is audited, and the disclaimer at the foot applies to everything exported.",
    rows: [
      ["Download analysis export (CSV)", "Downloads case-level data with no contact-identifying fields (no names, phone numbers or emails). Withdrawn participants' answers are left out.", "The version that is safe for analysis and for sharing with the wider research team.", "A CSV downloads."],
      ["Download operational export (CSV)", "Downloads the full operational data including contact details. PI only.", "Needed for fieldwork administration; never to be passed outside the study.", "A CSV downloads; the download is audited.", { only: [R.PI] }],
      ["KoboToolbox data → Excel workbook / All completed forms (PDF ZIP), for each form", "Downloads the full answers of the Questionnaire, the KII Guide or the Document Analysis Tool, as a workbook or as PDFs. PI only.", "Raw answers can identify organisations and, in the KII Guide, people, so only the PI may take them out.", "The file downloads; the download is audited.", { only: [R.PI] }],
    ],
  },
];

module.exports = { screens };
