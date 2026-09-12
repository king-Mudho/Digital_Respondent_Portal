# 29 — Respondent guide & invitation messaging

Practical, non-technical companion to `10_INVITATION_AND_CONSENT.md`'s specification.
This is what to actually tell a respondent, and what to send them alongside the link
issued from the "Send Invitation" panel (`/admin/sample/[sampleId]`) — neither the panel
nor `docs/10` currently give a Field Coordinator/RA anything ready to hand over.

## What a respondent experiences, step by step (plain language)

Give this to Field Coordinators/RAs as a script, or adapt it into the message sent with
the link. It mirrors the actual screens (`R02`–`R10`) in `README.md` "How the portal
works", written for the respondent rather than a developer.

1. **They open the link** (`https://research.agribizframework.com/i/<token>`) on their
   phone or computer — no app to install, no account to create.
2. **Confirm the organisation** — "Is this [Organisation Name]?" They tap Yes.
3. **Say who they are** — pick their role from a fixed list: Owner/founder, CEO/MD,
   Finance/credit/risk, Operations, Strategy/BD, Supply chain/commercial, Other senior
   manager, or "None of these." If none fit, they see a thank-you message and the
   questionnaire never opens — this is intentional (only knowledgeable organisational
   respondents proceed); ask them to pass the link on, or nominate, the right person
   instead.
4. **Read the study information** — a short participant information page: what the
   study is for, confidentiality, and their rights.
5. **Give consent** — an explicit "I agree to take part" action (never a pre-ticked
   box). They can decline at any point, before or during.
6. **Choose how to answer** — complete it themselves right now online, request a
   telephone-assisted session, request WhatsApp-assisted participation, or ask a
   researcher to contact them to arrange a time.
7. **Answer the questionnaire** (if completing it themselves) — opens the actual
   KoboToolbox form in a new step. Let them know roughly how long to expect (your Field
   Coordinator can give you the current estimate for this instrument) so they can find a
   proper sitting rather than starting somewhere they'll be interrupted.
8. **Done** — a short, neutral thank-you screen. No score, rating, or financing
   decision is ever calculated or shown to them, at this step or any other.

**Link validity**: 14 days from issue. An expired or already-superseded link shows a
clear "not valid" message, not a broken page — if that happens, ask your Field
Coordinator to issue a fresh one from the case's detail page.

## Message templates to send alongside the link

The "Send Invitation" panel hands you the raw link and an 8-character manual code — it
does not compose a message. Use one of these, filling in the bracketed fields.
`[researcher name / phone / email]` and `[RA phone number]` default to the PI's own
contact details (Happyson Saina, 0773943709, sales.proagromark2@gmail.com —
`docs/00_PROJECT_MASTER.md`) unless the sending RA has their own line to give instead.

### WhatsApp / SMS

```
Hello [Contact Name], this is [RA Name] from the Agribusiness Bankability Framework
research team at Chinhoyi University of Technology. [Organisation Name] has been
selected to take part in a doctoral research study on agribusiness financing readiness
in Zimbabwe. Please tap this secure, personal link to learn more and take part:

[LINK]

This link is unique to you and expires on [EXPIRY DATE]. Your participation is
voluntary and confidential -- no score or financing decision is generated from this
study. Questions? Contact Happyson Saina, 0773943709,
sales.proagromark2@gmail.com.
```

### Email

Subject: `Invitation to participate in a Chinhoyi University of Technology research study`

```
Dear [Contact Name],

[Organisation Name] has been selected to take part in a doctoral research study,
"Developing and Validating the Agribusiness Bankability Framework for Food Systems
Transformation through Novel Financing Models in Zimbabwe," conducted by Happyson
Saina (Doctor of Strategic Management candidate, Chinhoyi University of Technology).

Please use the secure, personal link below to review the study information, provide
consent, and take part:

[LINK]

If you would prefer a telephone-assisted session or a WhatsApp-assisted session
instead of completing it online yourself, the link will offer you that choice, or you
may reply to this email / call 0773943709 to arrange one directly.

This link is unique to you and expires on [EXPIRY DATE]. Your participation is
voluntary and confidential. No score, rating, or financing decision is generated or
shown to you as part of this process.

Kind regards,
[RA Name]
Agribusiness Bankability Framework research team
Chinhoyi University of Technology
```

### Manual/printed code (no link sent — dictated over the phone, or printed on paper)

```
Your invitation code is: [MANUAL CODE]

To take part: visit research.agribizframework.com on any phone or computer, choose
"Have an invitation code?", and enter the code above. Or call 0773943709 and we
will complete it together over the phone. This code expires on [EXPIRY DATE].
```

## Administering the different participation modes

| Mode | Administration code | What the RA does |
|---|---|---|
| Web self-administration | 01 | Send the link; respondent completes it unassisted. |
| WhatsApp link, self-completion | 02 | Send the link specifically via WhatsApp (the WhatsApp template above). |
| Telephone interviewer-administered | 03 | Call the respondent; walk them through eligibility/information/consent verbally, then complete the KoboToolbox form on their behalf during the call. |
| WhatsApp call, interviewer-assisted | 04 | Same as phone-assisted, over a WhatsApp voice/video call instead. |
| Video call, interviewer-assisted | 05 | Same, over Teams/Zoom/Meet. |
| Face to face | 06 | In person; the RA operates the device while the respondent answers. |

Record every contact attempt on the case's detail page ("Log a contact attempt")
regardless of outcome — reached, no answer, wrong number, refused, rescheduled — this
feeds the Contact Dashboard and the Day 0/2/4-5/7 reminder sequence.

## Troubleshooting for RAs

| Respondent says... | Likely cause | What to do |
|---|---|---|
| "The link says it's not valid." | Typo in the link, or it expired/was superseded by a newer one. | Open the case's detail page and use "Send new invitation" — this issues a fresh link and immediately invalidates the old one. |
| "I already did this." | The token was already used to completion, or a new wave was issued since. | Check the case's Invitations history for the current status before re-issuing. |
| "I'm not the right person to answer this." | They don't fit any listed role category. | This is the intended ineligible-respondent path — no answers are recorded from them. Ask them to nominate the correct person and issue that person their own invitation once identified. |
| "Will my company's financing be affected by my answers?" | Understandable concern given the study's subject matter. | No — this is explicitly not the case. No score, rating, or financing decision is generated or shown at any point (see the consent screen's own wording, and `docs/18_DATA_PRIVACY_AND_COMPLIANCE.md`). |

## What still needs the PI's input before this goes out to real respondents

- ~~The actual researcher contact details~~ — provided 2026-09-12 and filled in above
  (`docs/00_PROJECT_MASTER.md`).
- A stated expected completion time for the questionnaire, if the PI wants one quoted
  to respondents (the system only has QA plausibility bounds — 5 to 90 minutes — not a
  target time).
- Sign-off that the message wording above matches the approved Participant Information
  Sheet's tone and any required disclosures verbatim (`docs/18_DATA_PRIVACY_AND_COMPLIANCE.md`).
