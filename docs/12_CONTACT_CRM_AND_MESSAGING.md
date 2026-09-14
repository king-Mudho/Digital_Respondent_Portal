# 12 — Contact CRM & messaging

The portal functions as a lightweight research CRM, holding only the contact
information needed for study operations, with a complete contact-attempt audit trail.
This document closes the QC review gap: WhatsApp Business Platform account/template
provisioning was not listed as a Phase 0 dependency despite its lead time.

## Contact register fields

Per `Respondent`/`ContactEvent`/`Appointment` (`05_DATABASE_ARCHITECTURE.md`): named
respondent and exact role; professional email and telephone/WhatsApp number; gatekeeper
name, office and contact details; primary and backup access route; date/time/channel of
each contact attempt; contact outcome and notes; next permitted follow-up date;
appointment date/time/mode; refusal/nonresponse/ineligibility reason; RA/owner
responsible for the case.

## Reminder sequence

The reminder engine creates queues for human/scheduled dispatch — it never sends
uncontrolled messages. Default sequence (config-driven, adjustable per the approved
field SOP, not hardcoded): Day 0 invitation, Day 2 reminder, Day 4–5 telephone
follow-up, Day 7 final routine attempt. After Day 7 with no contact, the case becomes
`S13` (Nonresponse) and, once the sequence is exhausted, `S16`-eligible for reserve
activation per `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`.

## WhatsApp Business Platform — Phase 0 dependency

WhatsApp Business Platform (Meta Cloud API, directly or via a Business Solution
Provider such as Twilio, 360dialog, or Africa's Talking) prices per template message
(since July 2025), not per conversation:

- **Utility-category** templates (the natural fit for invitations/reminders/appointment
  confirmations) are charged only for business-initiated messages sent *outside* an
  open customer-service window (a window opened by the respondent's own reply); within
  that window, replies are free.
- **Authentication-category** templates follow the same outside-window charging model.
- **Marketing-category** templates are always charged and are **not used** by this
  portal — every outbound message here is utility, not marketing.
- **Service** conversations (respondent-initiated) have been free since November 2024.
- All outbound templates must be **pre-approved by Meta** before use, a review process
  that can take **3–5 business days** and is not something a developer can shortcut at
  build time.

**Action, not just a note**: `27_AGENT_EXECUTION_PLAN.md` Phase 0 includes "WhatsApp
Business Platform account provisioned and utility-category templates (invitation,
reminder, appointment-confirmation) submitted for Meta approval" as an explicit,
dated task — not a Phase 1 assumption — with a 3–5 business day buffer built into the
`26_MVP_PHASING_AND_ROADMAP.md` schedule.

## Fallback channels

Email and SMS are supported fallback channels for respondents without WhatsApp, and
telephone/face-to-face remain available per `11_KOBOTOOLBOX_INTEGRATION.md`'s
administration-mode list. SMS is treated as optional cost (`23_DEPLOYMENT_ARCHITECTURE.md`
budget note) unless the contact dashboard shows material WhatsApp unreachability.

## Messaging governance

Automated (human-unsupervised) sending is limited strictly to the approved reminder
sequence above; every other outbound message is triggered by an RA action and recorded
against that RA in `MessageLog.triggered_by` (`AGENTS.md` ground rule — messaging is
never a silent background process beyond the one approved queue).

## Sending by hand until the WhatsApp Business Platform is connected (2026-09-14)

Before this date every due reminder was written as a FAILED `MessageLog` that no screen
showed, so no reminder could reach anyone, and a case became S13 Nonresponse on day 8 by
the calendar alone.

- **Invitations.** After issuing, the case page offers *Send via WhatsApp* (wa.me with the
  invitation text, link, expiry and manual code) and *Copy message*. The wording lives in
  `frontend/app/admin/sample/[sampleId]/page.tsx` (`invitationMessage`) and still needs PI
  approval.
- **Follow-ups screen** (`/admin/follow-ups`; PI, Field Coordinator, Contact RA;
  Supervisor read-only) lists every case at S04–S06 whose live invitation has a reminder
  due and not yet sent — only the latest due step, so a missed Day 2 is superseded by Day
  7 rather than sent twice. *Open in WhatsApp* uses the respondent's number (Zimbabwean
  07… numbers get 263); *Mark as sent* records a SENT `MessageLog` against the RA and
  audits it.
- **Automated dispatch** sends only when the WhatsApp client is configured and writes
  nothing otherwise.
- **S13 Nonresponse** only after every step in the sequence was sent for the live
  invitation.
- **Contact details are editable.** The case page's *Respondents and contact details* panel
  adds and corrects people, phone, WhatsApp, email and gatekeeper (Contact RA on assigned
  cases, Field Coordinator, PI). On 2026-09-14 only 51 of the 400 Main cases had any phone
  number and none had a WhatsApp number, with no way to record one; collecting these is
  now the main fieldwork-readiness task (`33_GO_LIVE_READINESS.md`).
