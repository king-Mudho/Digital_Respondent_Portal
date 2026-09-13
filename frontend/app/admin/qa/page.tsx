"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

const QA_DECISIONS = [
  { decision: "ACCEPT", label: "Accept", variant: "primary" },
  { decision: "QUERY", label: "Re-query", variant: "outline" },
  { decision: "REJECT", label: "Reject", variant: "outline" },
] as const;

interface QueueSubmission {
  id: number;
  sample_id: string;
  kobo_submission_uuid: string;
  administration_mode: string;
  qa_status: string;
  submitted_at: string;
  completion_seconds: number | null;
}

interface ReconciliationStatus {
  id: number;
  run_started_at: string;
  run_finished_at: string | null;
  submissions_pulled: number;
  new_submissions: number;
  updated_submissions: number;
  mismatches_flagged: number;
  triggered_by: string;
  error_message: string;
}

function KoboSyncPanel() {
  const queryClient = useQueryClient();
  const { data: status } = useQuery({
    queryKey: ["kobo-reconciliation-status"],
    queryFn: () => adminFetch<ReconciliationStatus | null>("/kobo/reconciliation-status/"),
  });

  const sync = useMutation({
    mutationFn: () => adminFetch<ReconciliationStatus>("/kobo/reconcile/", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kobo-reconciliation-status"] });
      queryClient.invalidateQueries({ queryKey: ["qa-queue"] });
    },
  });

  // adminFetch throws ApiError on a non-2xx response (including the 502 a
  // failed Kobo call returns) -- surface that alongside whatever the last
  // known-good run recorded, rather than only ever showing stale status.
  const syncError = sync.isError
    ? sync.error instanceof Error
      ? sync.error.message
      : "Sync failed."
    : null;

  return (
    <Card className="mb-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-sm">KoboToolbox sync</h3>
        <WriteOnly note={null}>
          <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending ? "Syncing…" : "Sync now"}
          </Button>
        </WriteOnly>
      </div>
      {(syncError || status?.error_message) && (
        <p className="text-danger text-sm">Last sync failed: {syncError ?? status?.error_message}</p>
      )}
      {status && !status.error_message && (
        <p className="text-text-muted text-xs">
          Last synced {new Date(status.run_finished_at ?? status.run_started_at).toLocaleString()} ({status.triggered_by.toLowerCase()}) --{" "}
          {status.submissions_pulled} pulled, {status.new_submissions} new, {status.updated_submissions} updated
          {status.mismatches_flagged > 0 ? `, ${status.mismatches_flagged} mismatched` : ""}.
        </p>
      )}
      {!status && !syncError && <p className="text-text-muted text-xs">No reconciliation run yet.</p>}
    </Card>
  );
}

export default function QAQueuePage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["qa-queue"],
    queryFn: () => adminFetch<{ results: QueueSubmission[] } | QueueSubmission[]>("/qa/queue/"),
  });
  const [notes, setNotes] = useState<Record<number, string>>({});

  const [error, setError] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: ({ id, decision, note }: { id: number; decision: string; note: string }) =>
      adminFetch(`/qa/submission/${id}/decision/`, {
        method: "POST",
        body: JSON.stringify({ decision, note }),
      }),
    onSuccess: (_data, variables) => {
      setError(null);
      setNotes((prev) => ({ ...prev, [variables.id]: "" }));
      queryClient.invalidateQueries({ queryKey: ["qa-queue"] });
    },
    // record_human_decision rejects an empty note with a 400. Without this
    // the click did nothing at all and said nothing about why.
    onError: (err) => setError(err instanceof Error ? err.message : "Could not record the decision."),
  });

  const items = Array.isArray(data) ? data : data?.results ?? [];

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">QUAN QA Queue</h2>
      <KoboSyncPanel />
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {isLoading ? (
        <p className="text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">No submissions pending QA decision.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((submission) => (
            <Card key={submission.id} className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-sm">{submission.sample_id}</p>
                  <p className="text-xs text-text-muted">
                    Submitted {new Date(submission.submitted_at).toLocaleString()} · Mode{" "}
                    {submission.administration_mode} ·{" "}
                    {submission.completion_seconds
                      ? `${Math.round(submission.completion_seconds / 60)} min`
                      : "duration unknown"}
                  </p>
                </div>
                <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                  {submission.qa_status}
                </span>
              </div>
              <WriteOnly note="Read-only role — QA decisions are recorded by the QUAN QA RA, Field Coordinator or PI.">
                <textarea
                  placeholder="Note (required)"
                  value={notes[submission.id] ?? ""}
                  onChange={(e) => setNotes((prev) => ({ ...prev, [submission.id]: e.target.value }))}
                  className="w-full rounded-md border border-border px-3 py-2 text-sm"
                  rows={2}
                />
                <div className="flex gap-2">
                  {QA_DECISIONS.map(({ decision, label, variant }) => (
                    <Button
                      key={decision}
                      variant={variant}
                      disabled={!notes[submission.id]?.trim() || decide.isPending}
                      onClick={() =>
                        decide.mutate({
                          id: submission.id,
                          decision,
                          note: notes[submission.id].trim(),
                        })
                      }
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                {!notes[submission.id]?.trim() && (
                  <p className="text-text-muted text-xs">A note is required before recording a decision.</p>
                )}
              </WriteOnly>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
