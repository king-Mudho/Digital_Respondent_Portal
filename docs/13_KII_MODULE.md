# 13 — KII module

The KII module is kept separate from QUAN because the sampling logic, consent,
recording and evidence products differ.

## Fields and workflow

Per `KIIRecord` (`05_DATABASE_ARCHITECTURE.md`): KII_ID and stakeholder
quota/category; organisation and participant role; invitation and appointment status;
preferred mode (Teams/Zoom/Meet, WhatsApp voice/video, telephone, or face-to-face
contingency); participation consent and a **separate** recording consent (never implied
by the other — see `10_INVITATION_AND_CONSENT.md`); interview date, duration and
interviewer; recording file reference, field notes and transcript status; transcript
verification and anonymisation status; ABF-FST thematic coverage and coding status;
information-power/saturation monitoring note where relevant.

## Status flow

`INVITED → SCHEDULED → COMPLETED` (or `DECLINED`/`NO_SHOW`), independent of
`transcript_status` (`NOT_STARTED → IN_PROGRESS → VERIFIED → ANONYMISED`) and
`coding_status` (`NOT_STARTED → IN_PROGRESS → COMPLETE`), which progress after the
interview itself is complete.

## Recording storage

`KIIRecord.recording_reference` is a pointer into the secure controlled file store
(`23_DEPLOYMENT_ARCHITECTURE.md`), never the file itself in the database, and never a
generic cloud file-sharing link outside the approved store — see
`18_DATA_PRIVACY_AND_COMPLIANCE.md`.

## Written qualitative responses

Asynchronous email or WhatsApp text responses are transparently classified and stored
as written qualitative responses, not as `KIIRecord`s, unless the approved protocol
explicitly treats them as KIIs — this distinction is enforced at data-entry time by the
KII RA, not inferred automatically.

## Target and monitoring

60 KIIs, or a justified information-power/saturation endpoint (`00_PROJECT_MASTER.md`).
Quota coverage by stakeholder category is tracked on the KII/document dashboard
(`16_DASHBOARDS_AND_REPORTING.md`) and flagged by the KII Coordinator Agent
(`17_AI_FIELD_COORDINATOR.md`) when a category is falling behind target with limited
runway remaining before data lock.
