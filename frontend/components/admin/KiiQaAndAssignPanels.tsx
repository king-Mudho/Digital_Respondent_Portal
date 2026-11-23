"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IfRole, WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

export interface Caller {
  id: number;
  username: string;
  name: string;
}

/** The active Research Assistant (calls) accounts (GET /ra/callers/; PI, Field Coordinator, Supervisor). */
export function useCallers(enabled = true) {
  return useQuery({
    queryKey: ["ra-callers"],
    queryFn: () => adminFetch<Caller[]>("/ra/callers/"),
    enabled,
    staleTime: 60_000,
  });
}

export const QA_LABEL: Record<string, string> = {
  PENDING: "Awaiting QA",
  QUERY: "Query",
  QA_PASSED: "QA passed",
  REJECTED: "Rejected",
};

export const QA_TONE: Record<string, string> = {
  PENDING: "bg-bg border border-border text-text-muted",
  QUERY: "bg-warning text-white",
  QA_PASSED: "bg-success text-white",
  REJECTED: "bg-danger text-white",
};

/**
 * Which Research Assistant (calls) phones this informant (23 Nov 2026), set from the record's own page through
 * /ra/assign-kii/ -- the same audited assignment as the Research assistants screen. PI and Field Coordinator assign;
 * the Supervisor sees it. A completed or declined interview is not reassigned (its credit is settled on Research
 * assistants instead).
 */
export function KiiAssignPanel({
  kiiId,
  status,
  assignedRa,
  assignedRaName,
  onChanged,
}: {
  kiiId: string;
  status: string;
  assignedRa: number | null;
  assignedRaName: string;
  onChanged: () => void;
}) {
  const { data: callers } = useCallers();
  const [choice, setChoice] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const closed = status === "COMPLETED" || status === "DECLINED";
  const selected = choice ?? (assignedRa ? String(assignedRa) : "");

  const assign = useMutation({
    mutationFn: (raId: number | null) =>
      adminFetch<{ count: number }>("/ra/assign-kii/", {
        method: "POST",
        body: JSON.stringify({ ra_id: raId, kii_ids: [kiiId] }),
      }),
    onSuccess: (data, raId) => {
      setChoice(null);
      if (data.count === 0) {
        setMessage("Not changed: a completed or declined interview keeps the Research Assistant it had.");
      } else {
        const name = callers?.find((c) => c.id === raId)?.name;
        setMessage(raId ? `Assigned to ${name ?? "the Research Assistant"}. It is on their Calls list now.` : "Unassigned.");
      }
      onChanged();
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Could not change the Research Assistant."),
  });

  return (
    <Card className="space-y-2 mb-4">
      <h3 className="font-medium">Research Assistant (calls)</h3>
      <p className="text-sm">
        {assignedRaName ? (
          <>Assigned to <span className="font-medium">{assignedRaName}</span>.</>
        ) : (
          <span className="text-text-muted">Not assigned to a Research Assistant.</span>
        )}
      </p>
      <WriteOnly note={null}>
        {closed ? (
          <p className="text-xs text-text-muted">
            This interview is {status === "COMPLETED" ? "completed" : "declined"}, so it is not reassigned. To change who is
            credited, use Research assistants.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs text-text-muted">
              Assign to
              <select
                value={selected}
                onChange={(e) => {
                  setChoice(e.target.value);
                  setMessage(null);
                }}
                className="block mt-1 min-h-11 rounded-md border border-border bg-surface px-2 text-sm text-text"
                aria-label="Research Assistant (calls) to assign"
              >
                <option value="">Nobody (unassigned)</option>
                {(callers ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
            <Button
              variant="outline"
              disabled={assign.isPending || selected === (assignedRa ? String(assignedRa) : "")}
              onClick={() => assign.mutate(selected ? Number(selected) : null)}
            >
              {assign.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        )}
      </WriteOnly>
      {message && <p className="text-sm" role="status">{message}</p>}
    </Card>
  );
}

/**
 * The PI's quality check of a completed interview (23 Nov 2026): Pass, Query or Reject, with a note for the last two.
 * The Research Assistant's commission for the interview is paid only once it is QA passed. Everyone who opens the
 * record sees the decision; only the PI records it (the endpoint refuses everyone else).
 */
export function KiiQaPanel({
  recordId,
  qaStatus,
  qaNote,
  qaByName,
  qaAt,
  onChanged,
}: {
  recordId: number;
  qaStatus: string;
  qaNote: string;
  qaByName: string;
  qaAt: string | null;
  onChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${recordId}/qa/`, { method: "POST", body: JSON.stringify({ qa_status: status, note }) }),
    onSuccess: () => {
      setNote("");
      setError(null);
      onChanged();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not record the QA decision."),
  });

  return (
    <Card className="space-y-2 mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">Quality check (QA)</h3>
        <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${QA_TONE[qaStatus] ?? QA_TONE.PENDING}`}>
          {QA_LABEL[qaStatus] ?? qaStatus}
        </span>
      </div>
      {qaAt && (
        <p className="text-xs text-text-muted">
          {QA_LABEL[qaStatus]} by {qaByName || "the PI"} on {new Date(qaAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
          {qaNote && <span className="block text-text">&ldquo;{qaNote}&rdquo;</span>}
        </p>
      )}
      <p className="text-xs text-text-muted">The Research Assistant&rsquo;s commission for this interview is paid once it is QA passed.</p>
      <IfRole roles={["PI_ADMIN"]}>
        <div className="space-y-2">
          <label className="block text-xs text-text-muted">
            Note (needed for Query or Reject)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              maxLength={500}
              className="block mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={decide.isPending || qaStatus === "QA_PASSED"} onClick={() => decide.mutate("QA_PASSED")}>
              Pass QA
            </Button>
            <Button variant="outline" disabled={decide.isPending || !note.trim()} onClick={() => decide.mutate("QUERY")}>
              Query
            </Button>
            <Button variant="outline" disabled={decide.isPending || !note.trim()} onClick={() => decide.mutate("REJECTED")}>
              Reject
            </Button>
          </div>
          {error && <p className="text-sm text-danger" role="alert">{error}</p>}
        </div>
      </IfRole>
    </Card>
  );
}
