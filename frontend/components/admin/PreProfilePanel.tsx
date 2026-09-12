"use client";

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
  fields: PreProfileField[];
}

type FieldCatalog = Record<string, { label: string; module: string; route: string }>;

const CONFIDENCE_LEVELS = ["HIGH", "MODERATE", "LOW"];

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
  const [evidenceDrafts, setEvidenceDrafts] = useState<Record<number, { title: string; confidence: string }>>({});

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
    mutationFn: (fieldId: number) =>
      adminFetch(`/proit/fields/${fieldId}/evidence/`, {
        method: "POST",
        body: JSON.stringify({
          source_title: evidenceDrafts[fieldId]?.title ?? "",
          source_confidence: evidenceDrafts[fieldId]?.confidence ?? "MODERATE",
        }),
      }),
    onSuccess: (_data, fieldId) => {
      setError(null);
      setEvidenceDrafts((d) => ({ ...d, [fieldId]: { title: "", confidence: "MODERATE" } }));
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
      <div className="flex items-center justify-between">
        <h3 className="font-medium">Pre-Interview Profile (PROIT)</h3>
        {locked ? (
          <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
            Locked {new Date(profile.prepopulation_locked_at!).toLocaleDateString()}
          </span>
        ) : (
          <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">Draft</span>
        )}
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
                    {s.source_conflict ? ", conflicts with another source" : ""})
                  </li>
                ))}
              </ul>
            )}
            {!locked && (
              <div className="flex flex-wrap items-end gap-2 pt-1">
                <input
                  placeholder="Source title (e.g. PRAZ registry entry)"
                  value={evidenceDrafts[field.id]?.title ?? ""}
                  onChange={(e) =>
                    setEvidenceDrafts((d) => ({ ...d, [field.id]: { title: e.target.value, confidence: d[field.id]?.confidence ?? "MODERATE" } }))
                  }
                  className="flex-1 min-w-[12rem] rounded-md border border-border px-2 py-1 text-xs"
                />
                <select
                  value={evidenceDrafts[field.id]?.confidence ?? "MODERATE"}
                  onChange={(e) =>
                    setEvidenceDrafts((d) => ({ ...d, [field.id]: { title: d[field.id]?.title ?? "", confidence: e.target.value } }))
                  }
                  className="rounded-md border border-border px-2 py-1 text-xs bg-surface"
                >
                  {CONFIDENCE_LEVELS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <Button
                  variant="outline"
                  onClick={() => addEvidence.mutate(field.id)}
                  disabled={addEvidence.isPending || !evidenceDrafts[field.id]?.title}
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
    </Card>
  );
}
