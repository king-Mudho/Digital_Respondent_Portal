"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";
import { useAdminUser } from "@/lib/auth/session";

interface SheetField {
  id: number;
  field_id: string;
  label: string;
  documentary_value: string;
  withheld_low_confidence: boolean;
  confidence: string;
  gap_classification: string;
  sources: { title: string; publisher: string; url: string; date: string }[];
  verification_status: string;
  respondent_value: string;
  verification_comment: string;
  reconciled_value: string;
  settled: boolean;
}

interface Reconciliation {
  total: number;
  verified: number;
  settled: number;
  pending_verification: number[];
  pending_reconciliation: number[];
  complete: boolean;
  interview_completed_at: string | null;
  reconciliation_status: string;
  protocol_deviation: boolean;
}

interface Sheet {
  locked?: boolean;
  profile: null | {
    id: number;
    priority_probe_questions: string;
    fields: SheetField[];
    reconciliation: Reconciliation;
    deviation_note: string;
  };
}

// Appendix A of the PROIT specification, in plain words.
const STATUS_CHOICES: { value: string; label: string; needsValue: boolean }[] = [
  { value: "YES_CORRECT", label: "Confirmed: it is correct", needsValue: false },
  { value: "NO_CORRECT_VALUE_PROVIDED", label: "Corrected: they gave the right value", needsValue: true },
  { value: "PARTLY_CORRECT", label: "Partly correct or out of date", needsValue: true },
  { value: "DO_NOT_KNOW", label: "They do not know", needsValue: false },
  { value: "PREFER_NOT_TO_SAY", label: "They prefer not to say", needsValue: false },
  { value: "NOT_APPLICABLE", label: "Does not apply", needsValue: false },
];
const GAP_CHOICES = [
  { value: "NO_CORRECT_VALUE_PROVIDED", label: "They told us", needsValue: true },
  ...STATUS_CHOICES.filter((s) => ["DO_NOT_KNOW", "PREFER_NOT_TO_SAY", "NOT_APPLICABLE"].includes(s.value)),
];
const LABEL = (v: string) => STATUS_CHOICES.find((s) => s.value === v)?.label ?? v;

function actionFor(f: SheetField) {
  if (!f.documentary_value) return "Ask";
  return f.gap_classification === "VERIFY_AND_PROBE" ? "Confirm, then probe" : "Confirm";
}

/**
 * The locked pre-interview profile as the interviewer uses it: each public fact to CONFIRM (with its source), each
 * gap to ASK, and where the respondent's answers stand. After the interview a coordinator records the reconciled
 * value where the respondent corrected or qualified a fact. The case cannot count as complete until every fact is
 * settled (or a protocol deviation is recorded with its reason).
 */
export function InterviewSheet({ sampleCaseId, kiiRecordId }: { sampleCaseId?: number; kiiRecordId?: number }) {
  const queryClient = useQueryClient();
  const user = useAdminUser();
  const canReconcile = user?.role === "PI_ADMIN" || user?.role === "FIELD_COORDINATOR";
  const key = ["interview-sheet", sampleCaseId ?? `kii-${kiiRecordId}`];
  const param = sampleCaseId ? `sample_case=${sampleCaseId}` : `kii_record=${kiiRecordId}`;
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, { status: string; value: string; comment: string }>>({});
  const [reconciled, setReconciled] = useState<Record<number, string>>({});

  const { data } = useQuery({ queryKey: key, queryFn: () => adminFetch<Sheet>(`/proit/interview-sheet/?${param}`), retry: false });
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });
  const fail = (msg: string) => (err: unknown) => setError(err instanceof ApiError ? err.message : msg);

  const verify = useMutation({
    mutationFn: (f: SheetField) => {
      const d = drafts[f.id];
      return adminFetch(`/proit/fields/${f.id}/verify/`, {
        method: "POST",
        body: JSON.stringify({ status: d.status, respondent_value: d.value, comment: d.comment }),
      });
    },
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: fail("Could not save that answer."),
  });
  const reconcile = useMutation({
    mutationFn: (f: SheetField) =>
      adminFetch(`/proit/fields/${f.id}/reconcile/`, { method: "POST", body: JSON.stringify({ reconciled_value: reconciled[f.id] ?? "" }) }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: fail("Could not save the reconciled value."),
  });
  const finish = useMutation({
    mutationFn: (profileId: number) => adminFetch(`/proit/pre-profiles/${profileId}/interview-complete/`, { method: "POST" }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: fail("Could not record that the interview is finished."),
  });
  const deviate = useMutation({
    mutationFn: ({ profileId, note }: { profileId: number; note: string }) =>
      adminFetch(`/proit/pre-profiles/${profileId}/deviation/`, { method: "POST", body: JSON.stringify({ note }) }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: fail("Could not record the deviation."),
  });

  const profile = data?.profile;
  if (!profile) return null;
  const rec = profile.reconciliation;
  const draftFor = (f: SheetField) => drafts[f.id] ?? { status: f.verification_status, value: f.respondent_value, comment: f.verification_comment };
  const setDraft = (f: SheetField, patch: Partial<{ status: string; value: string; comment: string }>) =>
    setDrafts((d) => ({ ...d, [f.id]: { ...draftFor(f), ...patch } }));

  return (
    <section className="border border-border rounded-md p-3 space-y-3" aria-label="Interview verification">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Interview sheet: confirm what is public, ask what is not</h4>
        <span
          role="status"
          className={`rounded-full border px-2 py-0.5 text-xs ${rec.reconciliation_status === "RECONCILED" ? "border-header" : "border-border"}`}
        >
          {rec.reconciliation_status === "RECONCILED"
            ? "Reconciled"
            : rec.reconciliation_status === "UNRESOLVED"
              ? "Released with a recorded deviation"
              : `Verified ${rec.verified} of ${rec.total} · settled ${rec.settled} of ${rec.total}`}
        </span>
      </div>
      <p className="text-xs text-text-muted">
        Read each public fact to the respondent and record what they say. Never state a fact shown as “Ask”. It is a question,
        not something established. Their answer is kept separately and never replaces the public value.
      </p>
      {profile.priority_probe_questions && (
        <p className="text-xs whitespace-pre-wrap rounded-md bg-bg border border-border p-2">
          <span className="font-medium">Priority probes: </span>
          {profile.priority_probe_questions}
        </p>
      )}
      {error && <p className="text-danger text-sm">{error}</p>}

      <div className="space-y-3">
        {profile.fields.map((f) => {
          const d = draftFor(f);
          const choices = f.documentary_value ? STATUS_CHOICES : GAP_CHOICES;
          const chosen = choices.find((c) => c.value === d.status);
          const differs = ["NO_CORRECT_VALUE_PROVIDED", "PARTLY_CORRECT"].includes(f.verification_status) && !!f.documentary_value;
          const needsReconcile = !!f.verification_status && !f.settled;
          return (
            <div key={f.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-1">
                <span className="text-sm font-medium">{f.label}</span>
                <span className="flex gap-1 text-xs">
                  <span className="rounded-full bg-bg border border-border px-2 py-0.5">{actionFor(f)}</span>
                  {differs && <span className="rounded-full bg-bg border border-danger text-danger px-2 py-0.5">Differs from the public source</span>}
                  {f.settled && <span className="rounded-full bg-bg border border-border px-2 py-0.5">Settled</span>}
                </span>
              </div>
              {f.documentary_value ? (
                <p className="text-sm">
                  <span className="text-text-muted">Public source says: </span>
                  {f.documentary_value}
                </p>
              ) : (
                <p className="text-sm text-text-muted">
                  {f.withheld_low_confidence ? "A weak source suggested a value; it is not to be stated. Ask this in full." : "Not found publicly. Ask this in full."}
                </p>
              )}
              {f.sources.length > 0 && f.documentary_value && (
                <ul className="text-xs text-text-muted">
                  {f.sources.map((s) => (
                    <li key={s.url + s.title}>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">
                          {s.title}
                        </a>
                      ) : (
                        s.title
                      )}
                      {[s.publisher, s.date].filter(Boolean).map((x) => ` · ${x}`)}
                    </li>
                  ))}
                </ul>
              )}

              <WriteOnly note={null}>
                <div className="flex flex-wrap items-end gap-2">
                  <div>
                    <label className="block text-xs text-text-muted" htmlFor={`vs-${f.id}`}>
                      What the respondent said
                    </label>
                    <select
                      id={`vs-${f.id}`}
                      value={d.status}
                      onChange={(e) => setDraft(f, { status: e.target.value })}
                      className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
                    >
                      <option value="">Choose…</option>
                      {choices.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {chosen?.needsValue && (
                    <input
                      aria-label={`Respondent's answer for ${f.label}`}
                      placeholder="Their answer"
                      value={d.value}
                      onChange={(e) => setDraft(f, { value: e.target.value })}
                      className="flex-1 min-w-[12rem] rounded-md border border-border px-2 py-1.5 text-sm"
                    />
                  )}
                  <input
                    aria-label={`Comment on ${f.label}`}
                    placeholder="Comment (optional)"
                    value={d.comment}
                    onChange={(e) => setDraft(f, { comment: e.target.value })}
                    className="flex-1 min-w-[10rem] rounded-md border border-border px-2 py-1.5 text-sm"
                  />
                  <Button
                    variant="outline"
                    disabled={verify.isPending || !d.status || (!!chosen?.needsValue && !d.value.trim())}
                    onClick={() => verify.mutate(f)}
                  >
                    Save answer
                  </Button>
                </div>
              </WriteOnly>
              {f.verification_status && (
                <p className="text-xs text-text-muted">
                  Recorded: {LABEL(f.verification_status)}
                  {f.respondent_value ? ` — “${f.respondent_value}”` : ""}
                </p>
              )}

              {canReconcile && f.verification_status && (
                <div className="flex flex-wrap items-end gap-2 border-t border-border pt-2">
                  <div className="flex-1 min-w-[14rem]">
                    <label className="block text-xs text-text-muted" htmlFor={`rc-${f.id}`}>
                      Reconciled value{needsReconcile ? " (required)" : ""}
                    </label>
                    <input
                      id={`rc-${f.id}`}
                      value={reconciled[f.id] ?? f.reconciled_value}
                      onChange={(e) => setReconciled((r) => ({ ...r, [f.id]: e.target.value }))}
                      placeholder="The value you code for analysis"
                      className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
                    />
                  </div>
                  <Button
                    variant="outline"
                    disabled={reconcile.isPending || !(reconciled[f.id] ?? f.reconciled_value).trim()}
                    onClick={() => reconcile.mutate(f)}
                  >
                    Save reconciled value
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <WriteOnly note={null}>
        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
          {!rec.interview_completed_at ? (
            <Button variant="outline" disabled={finish.isPending} onClick={() => finish.mutate(profile.id)}>
              Interview finished
            </Button>
          ) : (
            <span className="text-xs text-text-muted">Interview finished {new Date(rec.interview_completed_at).toLocaleString()}</span>
          )}
          {canReconcile && rec.reconciliation_status !== "RECONCILED" && rec.reconciliation_status !== "UNRESOLVED" && (
            <Button
              variant="outline"
              onClick={() => {
                const note = window.prompt("Why can't this profile be reconciled? (recorded, and the case stays flagged)");
                if (note && note.trim()) deviate.mutate({ profileId: profile.id, note: note.trim() });
              }}
            >
              Record a protocol deviation
            </Button>
          )}
          {rec.protocol_deviation && profile.deviation_note && (
            <span className="text-xs text-text-muted">Deviation: {profile.deviation_note}</span>
          )}
        </div>
      </WriteOnly>
      {rec.reconciliation_status !== "RECONCILED" && rec.reconciliation_status !== "UNRESOLVED" && (
        <p className="text-xs text-text-muted">
          The case cannot be passed by QA (questionnaire) or have its coding completed (KII) until every fact here is verified with the
          respondent and, where they corrected or qualified it, reconciled.
        </p>
      )}
    </section>
  );
}
