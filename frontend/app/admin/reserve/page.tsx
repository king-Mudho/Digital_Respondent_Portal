"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface SampleCase {
  id: number;
  sample_id: string;
  organisation_name: string;
  status: string;
}

const ACTIVATION_REASONS = [
  { value: "INELIGIBLE", label: "Ineligible" },
  { value: "INACTIVE", label: "Inactive" },
  { value: "DUPLICATE", label: "Duplicate" },
  { value: "REFUSAL", label: "Refusal" },
  { value: "NONRESPONSE_EXHAUSTED", label: "Nonresponse exhausted" },
];

/**
 * A09 -- reserve activation. Deliberately no "swap" shortcut: activation
 * always requires one of the five authorised reasons, with a note, per
 * docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md -- there is no free-text
 * "other" escape hatch.
 */
export default function ReserveActivationPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["sample-cases", "RESERVE", "LOCKED"],
    queryFn: () => adminFetch<{ results: SampleCase[] }>("/sample-cases/?sample_type=RESERVE&status=LOCKED"),
  });

  const [reasonByCase, setReasonByCase] = useState<Record<string, string>>({});
  const [noteByCase, setNoteByCase] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const activate = useMutation({
    mutationFn: ({ sampleId, reason, note }: { sampleId: string; reason: string; note: string }) =>
      adminFetch(`/sample-cases/${sampleId}/activate-reserve/`, {
        method: "POST",
        body: JSON.stringify({ activation_reason: reason, activation_evidence_note: note }),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Activation failed."),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Reserve Activation</h2>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : data.results.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">No locked Reserve cases.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {data.results.map((sc) => (
            <Card key={sc.id} className="space-y-3">
              <p className="font-medium">
                {sc.organisation_name} <span className="font-mono text-xs text-text-muted">({sc.sample_id})</span>
              </p>
              <select
                value={reasonByCase[sc.sample_id] ?? ""}
                onChange={(e) => setReasonByCase((prev) => ({ ...prev, [sc.sample_id]: e.target.value }))}
                className="w-full rounded-md border border-border px-3 py-2 text-sm bg-surface"
              >
                <option value="" disabled>
                  Select authorised reason
                </option>
                {ACTIVATION_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <textarea
                placeholder="Evidence note (required)"
                value={noteByCase[sc.sample_id] ?? ""}
                onChange={(e) => setNoteByCase((prev) => ({ ...prev, [sc.sample_id]: e.target.value }))}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
                rows={2}
              />
              <Button
                disabled={!reasonByCase[sc.sample_id] || !noteByCase[sc.sample_id]}
                onClick={() =>
                  activate.mutate({
                    sampleId: sc.sample_id,
                    reason: reasonByCase[sc.sample_id],
                    note: noteByCase[sc.sample_id],
                  })
                }
              >
                Activate this reserve
              </Button>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
