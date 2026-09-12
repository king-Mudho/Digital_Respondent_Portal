"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface EvidenceSource {
  id: number;
  source_record_id: string;
  source_title: string;
  source_authority: string;
  source_confidence: string;
  source_conflict: boolean;
  locator: string;
}

interface PreProfileField {
  id: number;
  field_id: string;
  label: string;
  module: string;
  preliminary_documentary_value: string;
  respondent_value: string;
  reconciled_value: string;
  confidence: string;
  gap_classification: string;
  verification_status: string;
  sources: EvidenceSource[];
}

interface PreProfile {
  id: number;
  researcher_reviewed: boolean;
  prepopulation_locked_at: string | null;
  background_questions_avoided: number;
  burden_reduction_score: string | null;
  known_evidence_summary: string;
  unresolved_gaps: string;
  contradictions: string;
  priority_probe_questions: string;
  role_specific_module: string;
  executive_short_form: boolean;
  fields: PreProfileField[];
}

type FieldCatalog = Record<string, { label: string; module: string; route: string }>;
type ProbeTemplates = Record<string, { trigger: string; template: string }>;

const CONFIDENCE_LEVELS = ["HIGH", "MODERATE", "LOW"];

// Mirrors backend/apps/proit/models.py SourceAuthority -- document Section
// 5's four-tier source priority hierarchy. A Tier 1 source rated HIGH
// confidence is what actually earns a field HIGH confidence on its own
// (see proit.services.compute_field_confidence); this is the one detail
// the confidence dropdown alone can't capture.
const SOURCE_AUTHORITY_TIERS = [
  { value: "", label: "Tier (optional)" },
  { value: "TIER_1_STATUTORY", label: "Tier 1 — statutory/official register or audited report" },
  { value: "TIER_2_INSTITUTIONAL", label: "Tier 2 — official website, investor report, association record" },
  { value: "TIER_3_MEDIA", label: "Tier 3 — reputable media, conference bio, professional profile" },
  { value: "TIER_4_SOCIAL", label: "Tier 4 — corroborated public social/platform content" },
];

// The document's own 7 stakeholder-role probe templates (Section 10) are
// keyed by these role IDs -- role_specific_module (Module I) picks one of
// them, and the probe-suggestion helper below renders that role's
// template with the researcher's own evidence substituted in.
const PROBE_TEMPLATE_ROLES: Record<string, string> = {
  FINANCE_LENDER: "Finance/Lender",
  FARMER_AGRIBUSINESS: "Farmer/Agribusiness",
  GOVERNMENT_POLICY: "Government/Policy",
  RDC_PROVINCE: "RDC/Province",
  PROCESSOR_AGGREGATOR: "Processor/Aggregator",
  INSURANCE_GUARANTEE: "Insurance/Guarantee",
  RESEARCH_ACADEMIC: "Research/Academic",
};

// Section 9's "Adaptive KII Gap Engine": five panels (KNOWN/VERIFY/
// UNKNOWN/CONTRADICTION/PROBE) so "the interviewer sees only high-value
// prompts generated from gaps while retaining the approved KII core
// domains." VERIFY is already covered by the per-field gap_classification
// badges above (VERIFY_ONLY/VERIFY_AND_PROBE); this panel covers the
// other four, which are free-text researcher judgement calls the document
// doesn't specify an algorithm for -- KNOWN/UNKNOWN/CONTRADICTION/PROBE
// are Module I fields on PreProfile itself, and the probe-template
// library (Section 10) is offered as a one-click starting point, not an
// automated generator (substituting evidence into a fixed template is
// mechanical; deciding a probe is worth asking is not).
function KIIGapEnginePanel({ profile, queryKey }: { profile: PreProfile; queryKey: (string | number)[] }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [known, setKnown] = useState(profile.known_evidence_summary);
  const [unresolved, setUnresolved] = useState(profile.unresolved_gaps);
  const [conflicts, setConflicts] = useState(profile.contradictions);
  const [probes, setProbes] = useState(profile.priority_probe_questions);
  const [roleModule, setRoleModule] = useState(profile.role_specific_module);
  const [shortForm, setShortForm] = useState(profile.executive_short_form);
  const [templateRole, setTemplateRole] = useState("");
  const [templateEvidence, setTemplateEvidence] = useState("");

  const { data: templates } = useQuery({
    queryKey: ["proit-probe-templates"],
    queryFn: () => adminFetch<ProbeTemplates>("/proit/probe-templates/"),
  });

  const save = useMutation({
    mutationFn: () =>
      adminFetch(`/proit/pre-profiles/${profile.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          known_evidence_summary: known,
          unresolved_gaps: unresolved,
          contradictions: conflicts,
          priority_probe_questions: probes,
          role_specific_module: roleModule,
          executive_short_form: shortForm,
        }),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to save gap-engine notes."),
  });

  function insertProbeSuggestion() {
    if (!templateRole || !templates?.[templateRole]) return;
    const rendered = templates[templateRole].template.replace("{evidence}", templateEvidence || "[evidence]");
    setProbes((p) => (p ? `${p}\n${rendered}` : rendered));
  }

  return (
    <div className="border-t border-border pt-3 space-y-3">
      <h4 className="text-sm font-medium">KII adaptive gap engine</h4>
      {error && <p className="text-danger text-sm">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-sm space-y-1">
          <span className="block text-text-muted text-xs">Known (what the evidence already establishes)</span>
          <textarea
            value={known}
            onChange={(e) => setKnown(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-sm space-y-1">
          <span className="block text-text-muted text-xs">Unknown (genuine gaps -- ask full)</span>
          <textarea
            value={unresolved}
            onChange={(e) => setUnresolved(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-sm space-y-1">
          <span className="block text-text-muted text-xs">Contradictions (verify + probe, neutrally)</span>
          <textarea
            value={conflicts}
            onChange={(e) => setConflicts(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-sm space-y-1">
          <span className="block text-text-muted text-xs">Priority probe questions</span>
          <textarea
            value={probes}
            onChange={(e) => setProbes(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      <div className="border border-border rounded-md p-3 space-y-2">
        <p className="text-xs text-text-muted">
          Insert a probe-template suggestion (document Section 10) -- substitutes your evidence into the role&apos;s
          template, then appends it above for you to keep, edit, or discard.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <select
            value={templateRole}
            onChange={(e) => setTemplateRole(e.target.value)}
            className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
          >
            <option value="">Select a stakeholder role…</option>
            {Object.entries(PROBE_TEMPLATE_ROLES).map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
          <input
            placeholder="What was found (e.g. a working capital facility)"
            value={templateEvidence}
            onChange={(e) => setTemplateEvidence(e.target.value)}
            className="flex-1 min-w-[14rem] rounded-md border border-border px-2 py-1.5 text-sm"
          />
          <Button variant="outline" onClick={insertProbeSuggestion} disabled={!templateRole}>
            Insert suggestion
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm space-y-1">
          <span className="block text-text-muted text-xs">Role-specific module</span>
          <select
            value={roleModule}
            onChange={(e) => setRoleModule(e.target.value)}
            className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
          >
            <option value="">None selected</option>
            {Object.entries(PROBE_TEMPLATE_ROLES).map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={shortForm} onChange={(e) => setShortForm(e.target.checked)} />
          Use approved executive short form
        </label>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          Save gap-engine notes
        </Button>
      </div>
    </div>
  );
}

// PROIT (ABF-FST_PROIT_v1.0_Portal_Deployment_Tool.docx): background
// desk-research on an organisation/respondent, gathered and provenance-
// tracked before the interview, so the respondent only has to confirm or
// correct it instead of answering from zero. The respondent-facing half of
// this stays inert until PROIT_ENABLED_FOR_RESPONDENTS is turned on
// (an ethics/change-control gate, not a bug) -- this panel is the
// researcher-side half, usable regardless.
interface PreProfilePanelProps {
  sampleCaseId?: number;
  kiiRecordId?: number;
}

// Exactly one of sampleCaseId/kiiRecordId should be given -- mirrors the
// backend's PreProfile model, which requires exactly one of
// sample_case/kii_record.
export function PreProfilePanel({ sampleCaseId, kiiRecordId }: PreProfilePanelProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [newFieldId, setNewFieldId] = useState("");
  const [newFieldValue, setNewFieldValue] = useState("");
  const [evidenceDrafts, setEvidenceDrafts] = useState<Record<number, { title: string; confidence: string; authority: string }>>({});
  const emptyDraft = { title: "", confidence: "MODERATE", authority: "" };
  const draftFor = (fieldId: number) => evidenceDrafts[fieldId] ?? emptyDraft;

  const queryKey = ["pre-profile", sampleCaseId ?? `kii-${kiiRecordId}`];
  const listQueryParam = sampleCaseId ? `sample_case=${sampleCaseId}` : `kii_record=${kiiRecordId}`;
  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  const { data: profiles, isLoading } = useQuery({
    queryKey,
    queryFn: () => adminFetch<{ results: PreProfile[] } | PreProfile[]>(`/proit/pre-profiles/?${listQueryParam}`),
  });
  const profileList = Array.isArray(profiles) ? profiles : profiles?.results ?? [];
  const profile = profileList[0] as PreProfile | undefined;

  const { data: catalog } = useQuery({
    queryKey: ["proit-field-catalog"],
    queryFn: () => adminFetch<FieldCatalog>("/proit/field-catalog/"),
    enabled: !!profile && !profile.prepopulation_locked_at,
  });

  const createProfile = useMutation({
    mutationFn: () =>
      adminFetch("/proit/pre-profiles/", {
        method: "POST",
        body: JSON.stringify(sampleCaseId ? { sample_case: sampleCaseId } : { kii_record: kiiRecordId }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to create pre-profile."),
  });

  const addField = useMutation({
    mutationFn: () =>
      adminFetch(`/proit/pre-profiles/${profile!.id}/fields/`, {
        method: "POST",
        body: JSON.stringify({ field_id: newFieldId, preliminary_documentary_value: newFieldValue }),
      }),
    onSuccess: () => {
      setError(null);
      setNewFieldId("");
      setNewFieldValue("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to add field."),
  });

  const addEvidence = useMutation({
    mutationFn: (fieldId: number) => {
      const draft = draftFor(fieldId);
      return adminFetch(`/proit/fields/${fieldId}/evidence/`, {
        method: "POST",
        body: JSON.stringify({
          source_title: draft.title,
          source_confidence: draft.confidence,
          source_authority: draft.authority,
        }),
      });
    },
    onSuccess: (_data, fieldId) => {
      setError(null);
      setEvidenceDrafts((d) => ({ ...d, [fieldId]: emptyDraft }));
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to add evidence."),
  });

  const lockProfile = useMutation({
    mutationFn: () => adminFetch(`/proit/pre-profiles/${profile!.id}/lock/`, { method: "POST" }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to lock pre-profile."),
  });

  if (isLoading) {
    return (
      <Card>
        <h3 className="font-medium">Pre-Interview Profile (PROIT)</h3>
        <p className="text-text-muted text-sm">Loading…</p>
      </Card>
    );
  }

  if (!profile) {
    return (
      <Card className="space-y-3">
        <h3 className="font-medium">Pre-Interview Profile (PROIT)</h3>
        <p className="text-text-muted text-sm">
          No background research has been started for this case yet. Creating one lets you record what&apos;s already
          publicly known about the organisation/respondent, with a source for each fact, before the interview.
        </p>
        {error && <p className="text-danger text-sm">{error}</p>}
        <Button onClick={() => createProfile.mutate()} disabled={createProfile.isPending}>
          Start background research
        </Button>
      </Card>
    );
  }

  const locked = !!profile.prepopulation_locked_at;
  const usedFieldIds = new Set(profile.fields.map((f) => f.field_id));
  const availableCatalog = Object.entries(catalog ?? {}).filter(([id]) => !usedFieldIds.has(id));

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-medium">Pre-Interview Profile (PROIT)</h3>
        <div className="flex items-center gap-2">
          <Link href={`/admin/proit/${profile.id}`} className="text-header underline text-xs">
            Researcher review screen
          </Link>
          {locked ? (
            <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
              Locked {new Date(profile.prepopulation_locked_at!).toLocaleDateString()}
            </span>
          ) : (
            <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">Draft</span>
          )}
        </div>
      </div>
      {error && <p className="text-danger text-sm">{error}</p>}
      {locked && profile.burden_reduction_score !== null && (
        <p className="text-text-muted text-xs">
          {profile.background_questions_avoided} background question(s) converted to verification — burden
          reduction score {profile.burden_reduction_score}%.
        </p>
      )}

      {profile.fields.length === 0 && (
        <p className="text-text-muted text-sm">No background fields recorded yet.</p>
      )}

      <div className="space-y-3">
        {profile.fields.map((field) => (
          <div key={field.id} className="border border-border rounded-md p-3 space-y-2">
            <div className="flex items-center justify-between flex-wrap gap-1">
              <span className="font-medium text-sm">{field.label}</span>
              <div className="flex gap-1">
                {field.confidence && (
                  <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                    {field.confidence}
                  </span>
                )}
                {field.gap_classification && (
                  <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                    {field.gap_classification.replaceAll("_", " ")}
                  </span>
                )}
              </div>
            </div>
            <p className="text-sm">
              <span className="text-text-muted">Documentary value: </span>
              {field.preliminary_documentary_value || <em className="text-text-muted">none entered</em>}
            </p>
            {field.respondent_value && (
              <p className="text-sm">
                <span className="text-text-muted">Respondent said: </span>
                {field.respondent_value} <span className="text-text-muted text-xs">({field.verification_status})</span>
              </p>
            )}
            {field.sources.length > 0 && (
              <ul className="text-xs text-text-muted space-y-0.5">
                {field.sources.map((s) => (
                  <li key={s.id}>
                    {s.source_record_id}: {s.source_title} ({s.source_confidence}
                    {s.source_authority ? `, ${s.source_authority.replace(/^TIER_(\d)_.*/, "Tier $1")}` : ""}
                    {s.source_conflict ? ", conflicts with another source" : ""})
                  </li>
                ))}
              </ul>
            )}
            {!locked && (
              <div className="flex flex-wrap items-end gap-2 pt-1">
                <input
                  placeholder="Source title (e.g. PRAZ registry entry)"
                  value={draftFor(field.id).title}
                  onChange={(e) => setEvidenceDrafts((d) => ({ ...d, [field.id]: { ...draftFor(field.id), title: e.target.value } }))}
                  className="flex-1 min-w-[12rem] rounded-md border border-border px-2 py-1 text-xs"
                />
                <select
                  value={draftFor(field.id).confidence}
                  onChange={(e) => setEvidenceDrafts((d) => ({ ...d, [field.id]: { ...draftFor(field.id), confidence: e.target.value } }))}
                  className="rounded-md border border-border px-2 py-1 text-xs bg-surface"
                >
                  {CONFIDENCE_LEVELS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <select
                  value={draftFor(field.id).authority}
                  onChange={(e) => setEvidenceDrafts((d) => ({ ...d, [field.id]: { ...draftFor(field.id), authority: e.target.value } }))}
                  className="rounded-md border border-border px-2 py-1 text-xs bg-surface max-w-[16rem]"
                >
                  {SOURCE_AUTHORITY_TIERS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <Button
                  variant="outline"
                  onClick={() => addEvidence.mutate(field.id)}
                  disabled={addEvidence.isPending || !draftFor(field.id).title}
                >
                  Add source
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      {!locked && (
        <div className="border-t border-border pt-3 space-y-2">
          <h4 className="text-sm font-medium">Add a background field</h4>
          <div className="flex flex-wrap items-end gap-2">
            <select
              value={newFieldId}
              onChange={(e) => setNewFieldId(e.target.value)}
              className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
            >
              <option value="">Select a field…</option>
              {availableCatalog.map(([id, meta]) => (
                <option key={id} value={id}>{meta.label}</option>
              ))}
            </select>
            <input
              placeholder="What was found (documentary value)"
              value={newFieldValue}
              onChange={(e) => setNewFieldValue(e.target.value)}
              className="flex-1 min-w-[14rem] rounded-md border border-border px-2 py-1.5 text-sm"
            />
            <Button onClick={() => addField.mutate()} disabled={addField.isPending || !newFieldId}>
              Add field
            </Button>
          </div>
          <p className="text-text-muted text-xs">
            Every field with a documentary value needs at least one source before this profile can be locked.
          </p>
          <Button onClick={() => lockProfile.mutate()} disabled={lockProfile.isPending || profile.fields.length === 0}>
            Lock pre-profile
          </Button>
        </div>
      )}

      {kiiRecordId && <KIIGapEnginePanel profile={profile} queryKey={queryKey} />}
    </Card>
  );
}
