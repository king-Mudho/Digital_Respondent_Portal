"use client";

import { Fragment } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface EvidenceSource {
  id: number;
  source_record_id: string;
  source_title: string;
  source_authority: string;
  source_confidence: string;
  source_conflict: boolean;
  locator: string;
  source_date: string | null;
  access_date: string | null;
}

interface PreProfileField {
  id: number;
  field_id: string;
  label: string;
  preliminary_documentary_value: string;
  confidence: string;
  gap_classification: string;
  sources: EvidenceSource[];
}

interface PreProfile {
  id: number;
  sample_case: number | null;
  kii_record: number | null;
  sample_id: string | null;
  kii_id: string | null;
  researcher_reviewed: boolean;
  prepopulation_locked_at: string | null;
  background_questions_avoided: number;
  burden_reduction_score: string | null;
  unresolved_gaps: string;
  contradictions: string;
  priority_probe_questions: string;
  role_specific_module: string;
  executive_short_form: boolean;
  fields: PreProfileField[];
}

interface SampleCaseDetail {
  sample_id: string;
  organisation_name: string;
  organisation_master_id: string;
  stratum_code: string;
  sample_type: string;
}

interface KIIRecordDetail {
  kii_id: string;
  stakeholder_category: string;
  participant_name: string;
  participant_role: string;
}

// document Section 13's "Researcher Pre-Profile Screen" -- the one
// consolidated card meant to be reviewed just before an interview. Every
// field below already exists and is editable elsewhere in the panel; this
// page is a read-only composition of it, grouped the way the document
// specifies (Case / Organisation / Evidence / Bankability context / Gap
// summary / Interview plan), not new data.
const ORGANISATION_CARD_FIELD_IDS = [
  "legal_name", "trading_name", "organisation_type", "hq_province", "hq_district",
  "primary_value_chain", "value_chain_role", "geographic_coverage",
];
const BANKABILITY_CARD_FIELD_IDS = [
  "public_finance_facilities", "public_collateral_tenure", "audited_reports_available",
  "public_insurance", "known_offtake_contracts", "market_reach", "infrastructure_assets_public",
];
const GAP_CLASSIFICATION_ORDER = ["VERIFY_ONLY", "VERIFY_AND_PROBE", "ASK_FULL", "SKIP_BACKGROUND_ONLY"];
const GAP_CLASSIFICATION_LABELS: Record<string, string> = {
  VERIFY_ONLY: "Verify only",
  VERIFY_AND_PROBE: "Verify + probe",
  ASK_FULL: "Ask full",
  SKIP_BACKGROUND_ONLY: "Skip (background only)",
};

function fieldByIds(fields: PreProfileField[], ids: string[]) {
  const byId = new Map(fields.map((f) => [f.field_id, f]));
  return ids.map((id) => byId.get(id)).filter((f): f is PreProfileField => !!f);
}

export default function PreProfileReviewPage() {
  const params = useParams<{ id: string }>();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["pre-profile-detail", params.id],
    queryFn: () => adminFetch<PreProfile>(`/proit/pre-profiles/${params.id}/`),
  });

  const { data: sampleCase } = useQuery({
    queryKey: ["sample-case-for-review", profile?.sample_id],
    queryFn: () => adminFetch<SampleCaseDetail>(`/sample-cases/${profile!.sample_id}/`),
    enabled: !!profile?.sample_id,
  });

  const { data: kiiRecord } = useQuery({
    queryKey: ["kii-for-review", profile?.kii_record],
    queryFn: () => adminFetch<KIIRecordDetail>(`/kii/${profile!.kii_record}/`),
    enabled: !!profile?.kii_record,
  });

  if (isLoading || !profile) {
    return (
      <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  const isKii = !!profile.kii_record;
  const backHref = isKii ? `/admin/kii/${profile.kii_record}` : `/admin/sample/${profile.sample_id}`;
  const backLabel = isKii ? "KII record" : "sample case";

  const organisationFields = fieldByIds(profile.fields, ORGANISATION_CARD_FIELD_IDS);
  const bankabilityFields = fieldByIds(profile.fields, BANKABILITY_CARD_FIELD_IDS);
  const allSources = profile.fields.flatMap((f) => f.sources.map((s) => ({ field: f, source: s })));
  const unknownFields = profile.fields.filter((f) => f.gap_classification === "ASK_FULL");
  const conflictedFields = profile.fields.filter((f) => f.sources.some((s) => s.source_conflict));
  const fieldsByClassification = (cls: string) => profile.fields.filter((f) => f.gap_classification === cls);

  return (
    <AdminShell backHref={backHref} backLabel={backLabel}>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-semibold text-xl">Researcher Pre-Profile Review</h2>
        {profile.prepopulation_locked_at ? (
          <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
            Locked {new Date(profile.prepopulation_locked_at).toLocaleDateString()}
          </span>
        ) : (
          <span className="rounded-full bg-warning/10 border border-warning text-warning px-2 py-0.5 text-xs">
            Not yet locked — preview only, do not use for an interview yet
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-2">
          <h3 className="font-medium">Case</h3>
          <dl className="grid grid-cols-2 gap-1 text-sm">
            <dt className="text-text-muted">Route</dt>
            <dd>{isKii ? "KII" : "QUAN"}</dd>
            {sampleCase && (
              <>
                <dt className="text-text-muted">Sample ID</dt>
                <dd className="font-mono">{sampleCase.sample_id}</dd>
                <dt className="text-text-muted">Master ID</dt>
                <dd className="font-mono">{sampleCase.organisation_master_id}</dd>
                <dt className="text-text-muted">Organisation</dt>
                <dd>{sampleCase.organisation_name}</dd>
                <dt className="text-text-muted">Stratum</dt>
                <dd>{sampleCase.stratum_code}</dd>
                <dt className="text-text-muted">Sample type</dt>
                <dd>{sampleCase.sample_type}</dd>
              </>
            )}
            {kiiRecord && (
              <>
                <dt className="text-text-muted">KII ID</dt>
                <dd className="font-mono">{kiiRecord.kii_id}</dd>
                <dt className="text-text-muted">Stakeholder group</dt>
                <dd>{kiiRecord.stakeholder_category}</dd>
                <dt className="text-text-muted">Respondent</dt>
                <dd>{kiiRecord.participant_name}</dd>
                <dt className="text-text-muted">Respondent role</dt>
                <dd>{kiiRecord.participant_role}</dd>
              </>
            )}
          </dl>
        </Card>

        <Card className="space-y-2">
          <h3 className="font-medium">Organisation</h3>
          {organisationFields.length === 0 ? (
            <p className="text-text-muted text-sm">No organisation-profile background fields recorded.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-1 text-sm">
              {organisationFields.map((f) => (
                <Fragment key={f.id}>
                  <dt className="text-text-muted">{f.label}</dt>
                  <dd>{f.preliminary_documentary_value || <em className="text-text-muted">—</em>}</dd>
                </Fragment>
              ))}
            </dl>
          )}
        </Card>

        <Card className="space-y-2 lg:col-span-2">
          <h3 className="font-medium">Evidence</h3>
          {allSources.length === 0 ? (
            <p className="text-text-muted text-sm">No evidence sources recorded.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-1 pr-4">Field</th>
                    <th className="py-1 pr-4">Source</th>
                    <th className="py-1 pr-4">Authority</th>
                    <th className="py-1 pr-4">Confidence</th>
                    <th className="py-1 pr-4">Date / accessed</th>
                    <th className="py-1">Conflict</th>
                  </tr>
                </thead>
                <tbody>
                  {allSources.map(({ field, source }) => (
                    <tr key={source.id} className="border-t border-border">
                      <td className="py-1 pr-4">{field.label}</td>
                      <td className="py-1 pr-4">{source.source_record_id}: {source.source_title}</td>
                      <td className="py-1 pr-4">{source.source_authority.replace(/^TIER_(\d)_.*/, "Tier $1") || "—"}</td>
                      <td className="py-1 pr-4">{source.source_confidence}</td>
                      <td className="py-1 pr-4 text-xs text-text-muted">
                        {source.source_date ?? "—"} / {source.access_date ?? "—"}
                      </td>
                      <td className="py-1">{source.source_conflict ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="space-y-2">
          <h3 className="font-medium">Bankability context</h3>
          <p className="text-text-muted text-xs">
            Only publicly documented finance, tenure/collateral, audited reports, insurance, market/offtake and
            infrastructure — never a private or inferred figure.
          </p>
          {bankabilityFields.length === 0 ? (
            <p className="text-text-muted text-sm">No bankability-context fields recorded.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-1 text-sm">
              {bankabilityFields.map((f) => (
                <Fragment key={f.id}>
                  <dt className="text-text-muted">{f.label}</dt>
                  <dd>{f.preliminary_documentary_value || <em className="text-text-muted">—</em>}</dd>
                </Fragment>
              ))}
            </dl>
          )}
        </Card>

        <Card className="space-y-2">
          <h3 className="font-medium">Gap summary</h3>
          <div className="text-sm space-y-2">
            <p>
              <span className="text-text-muted">Unknowns ({unknownFields.length}): </span>
              {unknownFields.length > 0 ? unknownFields.map((f) => f.label).join(", ") : "none"}
            </p>
            <p>
              <span className="text-text-muted">Fields with conflicting sources ({conflictedFields.length}): </span>
              {conflictedFields.length > 0 ? conflictedFields.map((f) => f.label).join(", ") : "none"}
            </p>
            {profile.unresolved_gaps && (
              <p><span className="text-text-muted">Noted gaps: </span>{profile.unresolved_gaps}</p>
            )}
            {profile.contradictions && (
              <p><span className="text-text-muted">Noted contradictions: </span>{profile.contradictions}</p>
            )}
          </div>
          <div className="border-t border-border pt-2">
            <p className="text-xs text-text-muted font-medium mb-1">Sensitive items to avoid (docs/30, Section 12)</p>
            <p className="text-xs text-text-muted">
              Health, religion, ethnicity, political affiliation, sexual orientation, or any inferred private
              financial exposure — never collect or infer these, regardless of what a source appears to suggest.
            </p>
          </div>
        </Card>

        <Card className="space-y-2 lg:col-span-2">
          <h3 className="font-medium">Interview plan</h3>
          {profile.role_specific_module && (
            <p className="text-sm"><span className="text-text-muted">Role-specific module: </span>{profile.role_specific_module}</p>
          )}
          {profile.executive_short_form && (
            <p className="text-sm text-text-muted">Approved executive short form applies.</p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
            {GAP_CLASSIFICATION_ORDER.map((cls) => {
              const fields = fieldsByClassification(cls);
              if (fields.length === 0) return null;
              return (
                <div key={cls}>
                  <p className="text-xs font-medium text-text-muted mb-1">{GAP_CLASSIFICATION_LABELS[cls]} ({fields.length})</p>
                  <ul className="text-sm list-disc list-inside">
                    {fields.map((f) => <li key={f.id}>{f.label}</li>)}
                  </ul>
                </div>
              );
            })}
          </div>
          {profile.priority_probe_questions && (
            <div className="border-t border-border pt-2 mt-2">
              <p className="text-xs font-medium text-text-muted mb-1">Priority probe questions</p>
              <p className="text-sm whitespace-pre-line">{profile.priority_probe_questions}</p>
            </div>
          )}
        </Card>
      </div>
    </AdminShell>
  );
}
