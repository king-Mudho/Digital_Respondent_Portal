"use client";

import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, type Paginated } from "@/components/admin/Pagination";
import { StatCard } from "@/components/dashboard/StatCard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface QAException {
  id: number;
  rule_triggered: string;
  note: string;
  created_at: string;
  age_days: number;
  subject_type: string;
  subject_ref: string | null;
  status: "OPEN" | "IN_PROGRESS" | "RESOLVED" | "DISMISSED";
  assigned_to: number | null;
  assigned_to_username: string | null;
  resolution_note: string;
  resolved_at: string | null;
  resolved_by_username: string | null;
}

interface QAUser {
  id: number;
  username: string;
  role: string | null;
}

const STATUS_LABEL: Record<QAException["status"], string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  RESOLVED: "Resolved",
  DISMISSED: "Dismissed",
};

/**
 * A06 daily exception queue (ResearchOS brief A6). Before this, a triggered
 * QA rule produced a row nobody owned: there was no way to say who was
 * looking at an exception or whether anyone had, so it was a list rather
 * than a workflow. Oldest first, because the point is the backlog.
 */
export default function QAExceptionQueuePage() {
  const queryClient = useQueryClient();
  const [mine, setMine] = useState(false);
  const [includeResolved, setIncludeResolved] = useState(false);
  const { page, setPage, pageSize, setPageSize } = usePaging();
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});

  const query = `?page=${page}&page_size=${pageSize}${mine ? "&mine=1" : ""}${includeResolved ? "&include_resolved=1" : ""}`;

  const { data, isLoading } = useQuery({
    queryKey: ["qa-exceptions", mine, includeResolved, page, pageSize],
    queryFn: () => adminFetch<Paginated<QAException>>(`/qa/exceptions/${query}`),
    placeholderData: keepPreviousData,
  });

  // Not /auth/contact-ras/: a QA exception belongs with someone who can work
  // QA, and that endpoint is permissioned for the sampling roles, so a QUAN
  // QA RA calling it got a 403 and an empty assignee list.
  const { data: raList } = useQuery({
    queryKey: ["qa-assignees"],
    queryFn: () => adminFetch<{ results: QAUser[] }>("/auth/qa-assignees/"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["qa-exceptions"] });

  const assign = useMutation({
    mutationFn: ({ id, assignedTo }: { id: number; assignedTo: number | null }) =>
      adminFetch(`/qa/exceptions/${id}/assign/`, {
        method: "POST",
        body: JSON.stringify({ assigned_to: assignedTo }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not reassign."),
  });

  const resolve = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: string; note: string }) =>
      adminFetch(`/qa/exceptions/${id}/resolve/`, {
        method: "POST",
        body: JSON.stringify({ status, note }),
      }),
    onSuccess: (_d, v) => {
      setError(null);
      setNotes((n) => ({ ...n, [v.id]: "" }));
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not close the exception."),
  });

  const rows = data?.results ?? [];
  const openCount = rows.filter((r) => r.status === "OPEN").length;
  const inProgress = rows.filter((r) => r.status === "IN_PROGRESS").length;
  const oldest = rows.length > 0 ? Math.max(...rows.map((r) => r.age_days)) : 0;

  return (
    <AdminShell backHref="/admin/qa" backLabel="QA Queue">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div>
          <h2 className="font-semibold text-xl">QA Exception Queue</h2>
          <p className="text-text-muted text-sm">
            Automated QA flags awaiting someone. Oldest first.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={mine} onChange={(e) => { setMine(e.target.checked); setPage(1); }} />
            Only mine
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeResolved}
              onChange={(e) => { setIncludeResolved(e.target.checked); setPage(1); }}
            />
            Show closed
          </label>
        </div>
      </div>

      {error && <p className="text-danger text-sm mb-4">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="Open on this page" value={openCount} />
        <StatCard label="In progress" value={inProgress} />
        <StatCard label="Oldest here" value={oldest === 0 ? "today" : `${oldest} days`} />
      </div>

      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">
            {mine ? "Nothing is assigned to you." : "No open QA exceptions. Nothing needs attention."}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {rows.map((row) => {
            const closed = row.status === "RESOLVED" || row.status === "DISMISSED";
            return (
              <Card key={row.id} className="space-y-3">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <p className="font-medium font-mono text-sm">{row.rule_triggered}</p>
                    <p className="text-text-muted text-xs">
                      {row.subject_type}{" "}
                      {row.subject_ref && <span className="font-mono">{row.subject_ref}</span>} ·{" "}
                      raised {new Date(row.created_at).toLocaleDateString()}
                      {row.age_days > 0 && ` · ${row.age_days} days old`}
                    </p>
                  </div>
                  <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                    {STATUS_LABEL[row.status]}
                  </span>
                </div>

                {closed ? (
                  <p className="text-text-muted text-sm">
                    {STATUS_LABEL[row.status]} by {row.resolved_by_username ?? "—"} on{" "}
                    {row.resolved_at ? new Date(row.resolved_at).toLocaleDateString() : "—"}
                    {row.resolution_note && `: ${row.resolution_note}`}
                  </p>
                ) : (
                  <WriteOnly note="Read-only role — QA exceptions are worked by the QUAN QA RA, Field Coordinator or PI.">
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="text-sm text-text-muted">
                        <span className="sr-only">Assign to</span>
                        <select
                          value={row.assigned_to ?? ""}
                          disabled={assign.isPending}
                          onChange={(e) =>
                            assign.mutate({
                              id: row.id,
                              assignedTo: e.target.value ? Number(e.target.value) : null,
                            })
                          }
                          className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
                        >
                          <option value="">Unassigned</option>
                          {(raList?.results ?? []).map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.username}
                            </option>
                          ))}
                        </select>
                      </label>
                      {row.assigned_to_username && (
                        <span className="text-text-muted text-xs">
                          with {row.assigned_to_username}
                        </span>
                      )}
                    </div>

                    <textarea
                      placeholder="What was done about it? (required to close)"
                      value={notes[row.id] ?? ""}
                      onChange={(e) => setNotes((n) => ({ ...n, [row.id]: e.target.value }))}
                      className="w-full rounded-md border border-border px-3 py-2 text-sm"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <Button
                        disabled={!notes[row.id]?.trim() || resolve.isPending}
                        onClick={() =>
                          resolve.mutate({ id: row.id, status: "RESOLVED", note: notes[row.id].trim() })
                        }
                      >
                        Resolved
                      </Button>
                      <Button
                        variant="outline"
                        disabled={!notes[row.id]?.trim() || resolve.isPending}
                        onClick={() =>
                          resolve.mutate({ id: row.id, status: "DISMISSED", note: notes[row.id].trim() })
                        }
                      >
                        Not a real problem
                      </Button>
                    </div>
                    {!notes[row.id]?.trim() && (
                      <p className="text-text-muted text-xs">
                        A note is required before closing — a closure nobody explained looks the
                        same as one nobody looked at.
                      </p>
                    )}
                  </WriteOnly>
                )}
              </Card>
            );
          })}
          <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="exceptions" />
        </div>
      )}
    </AdminShell>
  );
}
