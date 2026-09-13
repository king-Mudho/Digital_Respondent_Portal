"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface QADashboard {
  submissions_today: number;
  submissions_cumulative: number;
  mode_distribution: Record<string, number>;
  qa_queue_open: number;
  qa_events_recorded: number;
}

/** docs/16_DASHBOARDS_AND_REPORTING.md "QA dashboard". GET /dashboards/qa/
 * has existed since phase 6 but nothing consumed it -- QUAN QA RAs had a
 * nav entry pointing at a 404. Counts only, no respondent-level data; the
 * individual submissions live behind the QA queue link below. */
export default function QADashboardPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard-qa"],
    queryFn: () => adminFetch<QADashboard>("/dashboards/qa/"),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Executive Dashboard">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">QA Dashboard</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-sm rounded-md border border-border px-3 py-2 min-h-11 disabled:opacity-50"
          >
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
          <Link
            href="/admin/qa"
            className="text-sm rounded-md bg-header text-white px-3 py-2 min-h-11 inline-flex items-center"
          >
            Open QA queue
          </Link>
        </div>
      </div>

      {isError ? (
        <Card className="space-y-3">
          <p className="text-danger text-sm">
            {error instanceof Error ? error.message : "Could not load the QA dashboard."}
          </p>
          <button onClick={() => refetch()} className="text-sm underline text-header">
            Try again
          </button>
        </Card>
      ) : isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Submissions today" value={data.submissions_today} />
            <StatCard label="Submissions cumulative" value={data.submissions_cumulative} />
            <StatCard label="QA queue open" value={data.qa_queue_open} />
            <StatCard label="QA events recorded" value={data.qa_events_recorded} />
          </div>
          <Card>
            <h3 className="font-medium mb-2">Administration mode</h3>
            {Object.keys(data.mode_distribution).length === 0 ? (
              <p className="text-text-muted text-sm">No submissions recorded yet.</p>
            ) : (
              Object.entries(data.mode_distribution).map(([mode, count]) => (
                <p key={mode} className="text-sm">
                  {mode}: <span className="tabular-nums">{count}</span>
                </p>
              ))
            )}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
