// Builds the Screen and Button Reference (one document for everyone) and the per-role appendix
// ("Every screen and button for your role") that closes each Role Guide, from one source of truth:
// reference_a.js and reference_b.js. A screen lists its controls; a control may be limited to some roles
// (`only`) and may change data (`write`), in which case read-only roles do not see it.
const C = require("./common");
const { R, screens: partA } = require("./reference_a");
const { screens: partB } = require("./reference_b");

const SCREENS = [...partA, ...partB];
const READ_ONLY = new Set([R.SUP, R.AN]);

const ROLE_NAME = {
  [R.PI]: "PI / System Admin", [R.FC]: "Field / Digital Coordinator", [R.CRA]: "Contact RA", [R.QA]: "QUAN/Kobo QA RA",
  [R.KII]: "KII RA", [R.DOC]: "Documentary RA", [R.AN]: "Data Analyst", [R.SUP]: "Supervisor",
};
const ROLE_SHORT = {
  [R.PI]: "PI", [R.FC]: "FC", [R.CRA]: "CRA", [R.QA]: "QA", [R.KII]: "KII", [R.DOC]: "DOC", [R.AN]: "AN", [R.SUP]: "SUP",
};
const ROLE_PLAIN = {
  [R.PI]: "the PI", [R.FC]: "the Field Coordinator", [R.CRA]: "Contact RAs", [R.QA]: "QA RAs", [R.KII]: "KII RAs",
  [R.DOC]: "Documentary RAs", [R.AN]: "Analysts", [R.SUP]: "Supervisors",
};

const HEADERS = ["Control", "What it does and when to use it", "Why it exists", "What happens next"];
const WIDTHS = [0.2, 0.32, 0.26, 0.22];

function visibleRows(screen, role) {
  return screen.rows.filter((row) => {
    const opts = row[4] ?? {};
    if (role) {
      if (opts.only && !opts.only.includes(role)) return false;
      if (opts.write && READ_ONLY.has(role)) return false;
    }
    return true;
  });
}

function rowCells(row, role) {
  const [control, does, why, next, opts = {}] = row;
  const who = !role && opts.only ? ` (${opts.only.map((r) => ROLE_PLAIN[r]).join(", ")} only)` : "";
  return [`**${control}**${who}`, does, why, next];
}

function whoLine(screen) {
  const who = screen.roles.length === Object.keys(ROLE_NAME).length ? "every role" : screen.roles.map((r) => ROLE_NAME[r]).join(", ");
  return `**Who can open it:** ${who}.  **Where:** \`${screen.path}\``;
}

function screenBlocks(screen, number, role) {
  const rows = visibleRows(screen, role);
  if (rows.length === 0) return [];
  const blocks = [["h2", `${number} ${screen.title}`], ["p", whoLine(screen)], ["p", screen.purpose]];
  blocks.push(["table", HEADERS, rows.map((r) => rowCells(r, role)), WIDTHS]);
  return blocks;
}

/** The closing appendix of a Role Guide. */
function roleAppendix(role, sectionNumber = 8) {
  const mine = SCREENS.filter((s) => s.roles.includes(role));
  const readOnly = READ_ONLY.has(role);
  const blocks = [
    ["h1", `${sectionNumber}. Every screen and button for your role`],
    ["p", `This section lists every screen you can open as ${ROLE_NAME[role]}, and for each control: what it does and when to use it, why it exists (the rule behind it), and what you will see next. It is the same material as the Screen and Button Reference, cut down to your role.`],
  ];
  if (readOnly) {
    blocks.push(["tip", "Your role is read-only", "Buttons that change anything are not shown to you: the screen shows “Your role has read-only access” instead. Only the controls you can see are listed here."]);
  }
  blocks.push(["tip", "Reading the tables", "**Control** is the label you see on screen. **Why it exists** explains the rule or risk behind it; if a button is greyed out, this column usually says why. A control that needs a note or a confirmation says so."]);
  let n = 0;
  for (const screen of mine) {
    const sb = screenBlocks(screen, `${sectionNumber}.${n + 1}`, role);
    if (sb.length) {
      blocks.push(...sb);
      n += 1;
    }
  }
  return blocks;
}

/** The standalone Screen and Button Reference. */
function referenceDoc() {
  const groups = [];
  for (const screen of SCREENS) {
    let g = groups.find((x) => x.name === screen.group);
    if (!g) groups.push((g = { name: screen.group, screens: [] }));
    g.screens.push(screen);
  }

  const roleCols = Object.keys(ROLE_NAME);
  const matrixRows = SCREENS.filter((s) => !["login", "header", "account"].includes(s.id)).map((s) => [
    s.title, ...roleCols.map((r) => (s.roles.includes(r) ? "✓" : "")),
  ]);

  const blocks = [
    ["h1", "1. About this reference", { newPage: false }],
    ["p", "The other manuals tell you how to do a task, step by step. This one is the opposite: it takes every screen of the ABF-FST Research Operations Centre and, for each button, field and choice on it, says what it does, when to use it, **why it exists** and **what you will see next**."],
    ["p", "Use it when you wonder “what does this button do?”, “why is it greyed out?” or “what happens if I press it?”. It is written from the actual screens, so the labels are the ones you see."],
    ["h3", "How each table works"],
    ["table", ["Column", "What it tells you"], [
      ["**Control**", "The label of the button, field or choice, exactly as on screen. If only some roles see it, the roles are named."],
      ["**What it does and when to use it**", "The action, and the situation it is for."],
      ["**Why it exists**", "The rule, risk or research requirement behind it. When a button is greyed out, this is usually where the reason is."],
      ["**What happens next**", "What you will see or what will have changed afterwards, including any confirmation and whether it is audited."],
    ], [0.28, 0.72]],
    ["h3", "The other manuals"],
    ["bullets", [
      "**Role Guides 1 to 8** teach each role its routine, step by step. Each ends with this reference cut down to that role.",
      "**System Manual**: how the whole system works and how the parts fit together.",
      "**RA Training Manual**: learn by doing, with practice exercises.",
    ]],

    ["h1", "2. Rules that apply on every screen"],
    ["bullets", [
      "**The menu shows only your screens.** The server builds it from your role. A screen that is not yours says “This screen isn't part of your role”.",
      "**Read-only roles see no write buttons.** Supervisors and Analysts can open their screens but every button that would change something is replaced by a note. Each Role Guide's appendix lists only what its role can see.",
      "**A greyed-out button is waiting for something.** Usually a required note, a required choice, or a step that must come first (for example Include is greyed out until authenticity is assessed). The “Why it exists” column says which.",
      "**Confirmations protect what cannot be undone.** Moving many cases, recording a withdrawal, removing a file, regenerating a draft and submitting to KoboToolbox all ask first.",
      "**Notes are required where a decision needs a reason.** QA decisions, closing a QA exception, activating a Reserve case and recording a withdrawal cannot be saved without one.",
      "**Important actions are audited.** Decisions, downloads, submissions, withdrawals, activations and status changes are recorded with who, what and when. The audit log cannot be edited.",
      "**Nothing personal goes into web addresses.** Links that open KoboToolbox carry only system IDs, never a name.",
      "**Lists share one set of controls.** Every register has a **Show** choice (10, 20, 50, 100 or 200 rows per page; your choice is remembered), page numbers, **Previous** and **Next** and first/last page arrows, and usually a **Search** box.",
    ]],

    ["h1", "3. Who can open which screen"],
    ["p", "A tick means the role can open the screen. Detail screens (a case, a KII record, a document) follow their register. The columns are: PI, Field Coordinator (FC), Contact RA (CRA), QA RA (QA), KII RA (KII), Documentary RA (DOC), Analyst (AN), Supervisor (SUP). Supervisors and Analysts open screens read-only."],
    ["table", ["Screen", ...roleCols.map((r) => ROLE_SHORT[r])], matrixRows, [0.36, ...roleCols.map(() => 0.08)]],
  ];

  let gn = 3;
  for (const group of groups) {
    gn += 1;
    blocks.push(["h1", `${gn}. ${group.name}`]);
    let sn = 0;
    for (const screen of group.screens) {
      sn += 1;
      blocks.push(...screenBlocks(screen, `${gn}.${sn}`, null));
    }
  }

  return {
    file: "ABF-FST_Screen_and_Button_Reference",
    meta: {
      title: "ABF-FST Digital Respondent Portal — Screen and Button Reference",
      short: "Screen and Button Reference",
      subtitle: "Every screen and every button: what it does, when to use it, why it exists and what happens next.",
      audience: "Everyone who uses the portal: PI, coordinators, research assistants, analysts and supervisors",
      revision: C.REVISION,
    },
    blocks,
  };
}

module.exports = { SCREENS, roleAppendix, referenceDoc, ROLE_NAME };
