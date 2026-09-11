# 05 — Database architecture

PostgreSQL, own instance/schema (`drp_db`), separate from the ABI project's `abi_db`.
Each table below maps to one Django model (app shown in brackets). Use Django's default
`id` (BigAutoField) primary keys unless noted. All `created_at` / `updated_at` timestamp
pairs are implied on every model even where not listed, stored UTC (display converted to
Africa/Harare per `AGENTS.md`-equivalent display rule inherited from the original
blueprint's Appendix B).

## Entity list

```
User, Role                                         (accounts)
Organisation, StratumDefinition, SampleCase         (sampling)
Respondent, ContactEvent, Appointment               (contacts)
ConsentRecord                                       (consent)
InvitationToken                                     (invitations)
QUANSubmission, ReconciliationLog                   (kobo)
MessageTemplate, MessageLog                         (messaging)
KIIRecord                                           (kii)
DocumentRecord                                      (evidence)
QAEvent, QARuleThreshold                            (qa)
CostEvent                                           (costs)
AuditEvent                                          (audit)
```

## accounts

### User
Extend Django's `AbstractUser`.
| Field | Type | Notes |
|---|---|---|
| role | FK → Role | |
| phone | CharField, optional | |

### Role
| Field | Type | Notes |
|---|---|---|
| name | CharField, unique | PI_ADMIN, SUPERVISOR_READONLY, FIELD_COORDINATOR, CONTACT_RA, QUAN_QA_RA, KII_RA, DOCUMENTARY_RA, ANALYST |

## sampling

### StratumDefinition
| Field | Type | Notes |
|---|---|---|
| code | CharField, unique | e.g. combination of province/actor family/value chain/size class |
| province | CharField (choices) | Zimbabwe provinces |
| actor_family | CharField (choices) | |
| value_chain | CharField (choices) | |
| size_class | CharField (choices) | |
| target_count | PositiveIntegerField | Planned Main-400 allocation for this stratum |

### Organisation
| Field | Type | Notes |
|---|---|---|
| master_id | CharField, unique, immutable after creation | See `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` — persists across re-sampling |
| name | CharField | |
| entity_type | CharField (choices) | Sole trader, Partnership, Cooperative, Company, etc. |
| province | CharField (choices) | |
| district | CharField | |
| actor_family | CharField (choices) | |
| value_chain | CharField (choices) | |
| size_class | CharField (choices) | |
| verification_status | CharField (choices) | UNVERIFIED, VERIFIED, UNREACHABLE, DUPLICATE |
| verified_by | FK → User, nullable | |
| verified_at | DateTimeField, nullable | |

### SampleCase
| Field | Type | Notes |
|---|---|---|
| sample_id | CharField, unique, immutable after creation | See `09_IDENTIFIER_AND_SAMPLING_CONTROL.md` |
| organisation | FK → Organisation | |
| stratum | FK → StratumDefinition | |
| sample_type | CharField (choices) | MAIN, RESERVE |
| matched_case | FK → self, nullable | The paired Main↔Reserve case |
| status | CharField (choices) | For MAIN: mirrors the S00–S16 workflow engine, see `09_IDENTIFIER_AND_SAMPLING_CONTROL.md`. For RESERVE: `LOCKED` or `ACTIVATED` |
| workflow_status | CharField (choices), nullable for RESERVE | S00…S16 |
| activation_reason | CharField (choices), nullable | INELIGIBLE, INACTIVE, DUPLICATE, REFUSAL, NONRESPONSE_EXHAUSTED — set only on RESERVE activation |
| activated_by | FK → User, nullable | |
| activated_at | DateTimeField, nullable | |
| activation_evidence_note | TextField, optional | |

## contacts

### Respondent
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase | |
| full_name | CharField | Access-controlled — never in aggregate exports, see `18_DATA_PRIVACY_AND_COMPLIANCE.md` |
| role_category | CharField (choices) | Owner/founder, CEO/MD, Finance/credit/risk, Operations, Strategy/BD, Supply chain/commercial, Other senior manager |
| is_eligible | BooleanField, nullable | Set by the eligibility gate, not self-declared alone |
| eligibility_checked_by | FK → User, nullable | |
| phone | CharField, optional | |
| whatsapp_number | CharField, optional | |
| email | EmailField, optional | |
| gatekeeper_name | CharField, optional | |
| gatekeeper_contact | CharField, optional | |

### ContactEvent
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase | |
| channel | CharField (choices) | WHATSAPP, EMAIL, PHONE, SMS, FACE_TO_FACE |
| occurred_at | DateTimeField | |
| outcome | CharField (choices) | REACHED, NO_ANSWER, WRONG_NUMBER, REFUSED, RESCHEDULED, COMPLETED |
| notes | TextField, optional | |
| next_action_date | DateField, nullable | |
| ra | FK → User | |

### Appointment
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase, nullable | |
| kii_record | FK → KIIRecord, nullable | One of sample_case/kii_record is set |
| scheduled_for | DateTimeField | |
| mode | CharField (choices) | TEAMS, ZOOM, MEET, WHATSAPP_VOICE, WHATSAPP_VIDEO, PHONE, FACE_TO_FACE |
| status | CharField (choices) | REQUESTED, CONFIRMED, COMPLETED, MISSED, CANCELLED |

## consent

### ConsentRecord
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase | |
| respondent | FK → Respondent, nullable | Null before respondent identity is confirmed |
| consent_type | CharField (choices) | PARTICIPATION, KII_RECORDING — always separate rows, see `10_INVITATION_AND_CONSENT.md` |
| information_sheet_version | CharField | Versioned PIS text reference |
| decision | CharField (choices) | GIVEN, DECLINED, WITHDRAWN |
| method | CharField (choices) | WEB_CLICKTHROUGH, VERBAL_RA_RECORDED, WRITTEN |
| timestamp | DateTimeField | |
| withdrawn_at | DateTimeField, nullable | |

## invitations

### InvitationToken
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase | |
| token_hash | CharField, unique | Salted hash of the opaque token — see `10_INVITATION_AND_CONSENT.md`; the raw token is never stored |
| status | CharField (choices) | GENERATED, SENT, OPENED, ELIGIBILITY_PASSED, CONSENTED, SURVEY_STARTED, SUBMITTED, QA_PASSED, EXPIRED, REVOKED |
| channel | CharField (choices) | WHATSAPP, EMAIL, SMS, PRINTED_CODE, QR |
| invitation_wave | PositiveIntegerField | |
| issued_at | DateTimeField | |
| expires_at | DateTimeField | |
| revoked_at | DateTimeField, nullable | |
| revoked_reason | CharField, optional | |

*Note*: only the latest non-revoked, non-expired token for a `SampleCase` is valid;
issuing a new token does not delete the old row (audit trail), it supersedes it — see
`10_INVITATION_AND_CONSENT.md`.

## kobo

### QUANSubmission
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase | |
| kobo_submission_uuid | CharField, unique | Kobo's own submission identifier |
| administration_mode | CharField (choices) | 01–06, see `11_KOBOTOOLBOX_INTEGRATION.md` |
| ra | FK → User, nullable | Set for RA-assisted modes |
| started_at | DateTimeField, nullable | From Kobo metadata |
| submitted_at | DateTimeField | |
| last_edited_at | DateTimeField, nullable | Populated by reconciliation, not by the webhook |
| completion_seconds | PositiveIntegerField, nullable | |
| qa_status | CharField (choices) | PENDING, QUERY, QA_PASSED, REJECTED |
| raw_payload_ref | CharField, optional | Pointer to the stored full Kobo submission payload for QA drill-down |

### ReconciliationLog
| Field | Type | Notes |
|---|---|---|
| run_started_at | DateTimeField | |
| run_finished_at | DateTimeField | |
| submissions_pulled | PositiveIntegerField | |
| new_submissions | PositiveIntegerField | |
| updated_submissions | PositiveIntegerField | Submissions whose Kobo data changed since the last pull — this is the count that matters given the webhook's edit blind spot |
| mismatches_flagged | PositiveIntegerField | e.g. a submission with no matching `InvitationToken`/Sample_ID |
| triggered_by | CharField (choices) | SCHEDULE, WEBHOOK_HEADSUP, MANUAL |

## messaging

### MessageTemplate
| Field | Type | Notes |
|---|---|---|
| name | CharField, unique | |
| channel | CharField (choices) | WHATSAPP, EMAIL, SMS |
| category | CharField (choices) | UTILITY, MARKETING, AUTHENTICATION — WhatsApp Business Platform category, see `12_CONTACT_CRM_AND_MESSAGING.md` |
| meta_approval_status | CharField (choices), nullable | For WhatsApp templates: PENDING, APPROVED, REJECTED |
| body | TextField | |

### MessageLog
| Field | Type | Notes |
|---|---|---|
| sample_case | FK → SampleCase, nullable | |
| kii_record | FK → KIIRecord, nullable | |
| template | FK → MessageTemplate | |
| channel | CharField (choices) | |
| sent_at | DateTimeField | |
| status | CharField (choices) | QUEUED, SENT, DELIVERED, FAILED |
| triggered_by | FK → User, nullable | Null only for the approved automated reminder sequence |

## kii

### KIIRecord
| Field | Type | Notes |
|---|---|---|
| kii_id | CharField, unique | |
| stakeholder_category | CharField (choices) | |
| organisation | FK → Organisation, nullable | |
| participant_name | CharField | Access-controlled |
| participant_role | CharField | |
| status | CharField (choices) | INVITED, SCHEDULED, COMPLETED, DECLINED, NO_SHOW |
| preferred_mode | CharField (choices) | Same choice set as `Appointment.mode` |
| participation_consent | FK → ConsentRecord, nullable | |
| recording_consent | FK → ConsentRecord, nullable | |
| interview_date | DateField, nullable | |
| duration_minutes | PositiveIntegerField, nullable | |
| interviewer | FK → User, nullable | |
| recording_reference | CharField, optional | Pointer into the secure file store, not the file itself |
| field_notes | TextField, optional | |
| transcript_status | CharField (choices) | NOT_STARTED, IN_PROGRESS, VERIFIED, ANONYMISED |
| coding_status | CharField (choices) | NOT_STARTED, IN_PROGRESS, COMPLETE |
| thematic_coverage_tags | ArrayField(CharField) or M2M | ABF-FST construct tags |

## evidence

### DocumentRecord
| Field | Type | Notes |
|---|---|---|
| document_id | CharField, unique | |
| organisation | FK → Organisation, nullable | |
| title | CharField | |
| author_or_speaker | CharField, optional | |
| publication_or_event_date | DateField, nullable | |
| source_url_or_reference | CharField, optional | |
| document_type | CharField (choices) | Official, Secondary, Platform |
| authenticity_assessment | CharField (choices) | UNVERIFIED, VERIFIED, DISPUTED |
| verified_at | DateTimeField, nullable | |
| geographic_scope | CharField, optional | |
| value_chain | CharField (choices), optional | |
| construct_tags | ArrayField(CharField) or M2M | NFM, BANK, DGR, AGC, INS, FST + ABI-dimension relevance tags (tags only — never a score) |
| evidence_extract | TextField, optional | |
| interpretive_memo | TextField, optional | |
| triangulation_links | ManyToMany → QUANSubmission / KIIRecord | |
| reviewer | FK → User, nullable | |
| qa_status | CharField (choices) | PENDING, INCLUDED, EXCLUDED |

## qa

### QARuleThreshold
| Field | Type | Notes |
|---|---|---|
| code | CharField, unique | e.g. `min_plausible_duration_seconds` — see `15_QA_AND_DATA_QUALITY.md` for the full seeded set |
| value | JSONField | Numeric or structured threshold value |
| effective_from | DateTimeField | |
| set_by | FK → User | Config-driven per `AGENTS.md` ground rule 7 — never hardcoded in Python/TS |

### QAEvent
| Field | Type | Notes |
|---|---|---|
| submission | FK → QUANSubmission, nullable | |
| kii_record | FK → KIIRecord, nullable | |
| document_record | FK → DocumentRecord, nullable | One of the three is set |
| rule_triggered | CharField, optional | References a `QARuleThreshold.code`, blank for a manual flag |
| decision | CharField (choices) | ACCEPT, QUERY, REJECT |
| reviewer | FK → User | |
| note | TextField, optional | |

## costs

### CostEvent
| Field | Type | Notes |
|---|---|---|
| date | DateField | |
| category | CharField (choices) | RA_ALLOWANCE, AIRTIME_DATA, TRANSPORT, ACCOMMODATION, HOSTING, MESSAGING, OTHER |
| amount | DecimalField | |
| currency | CharField | Default USD |
| sample_case | FK → SampleCase, nullable | |
| kii_record | FK → KIIRecord, nullable | |
| approved_by | FK → User | |

## audit

### AuditEvent
| Field | Type | Notes |
|---|---|---|
| user | FK → User, nullable | |
| action | CharField | e.g. `invitation.issued`, `consent.given`, `reserve.activated`, `qa.decision`, `data.locked` |
| object_type | CharField | |
| object_id | CharField | |
| metadata | JSONField, optional | |
| created_at | DateTimeField | |

## Integrity rules

- A `SampleCase` with `sample_type = RESERVE` must be structurally unreachable by every
  invitation-issuing code path while `status = LOCKED` — enforced in the service layer
  and covered by a dedicated test, not left to the frontend (`AGENTS.md` ground rule 4).
- `SampleCase.activation_reason`, `activated_by` and `activated_at` must all be set
  together — enforce with a model `clean()`; reserve activation always writes a matching
  `AuditEvent`.
- `InvitationToken.token_hash` is the only representation of the token ever persisted;
  the raw token exists only in the URL/message sent to the respondent — see
  `10_INVITATION_AND_CONSENT.md`.
- `Organisation.name`, `Respondent.full_name` and any free-text contact/note field must
  never appear in an aggregate dashboard payload or the de-identified analysis export —
  see `18_DATA_PRIVACY_AND_COMPLIANCE.md`.
- `QUANSubmission.qa_status` and `KIIRecord`/`DocumentRecord` QA/coding status are
  **computed and written by the backend/QA workflow only**, never accepted as raw client
  input.
