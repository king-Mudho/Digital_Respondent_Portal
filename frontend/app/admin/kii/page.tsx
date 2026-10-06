"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, SearchBox, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface KIIRecord {
  id: number;
  kii_id: string;
  stakeholder_category: string;
  participant_role: string;
  status: string;
  transcript_status: string;
  coding_status: string;
}

interface KiiBatchInfo {
  configured: boolean;
  without_contacts: number;
  max: number;
  cost_per_case_usd: [number, number];
  progress: { total: number; queued: number; running: number; done: number; failed: number; active: boolean } | null;
  to_review_total: number;
  to_review: { id: number; kii_id: string; participant: string; findings: number }[];
}

/**
 * Queues the AI contact finder for KII records with no phone, WhatsApp or email (backend/apps/contacts/kii_finder.py),
 * one batch at a time, and lists the records whose findings are waiting for a decision on their own page. The PI,
 * Field Coordinator and KII RA may start a batch; the Supervisor sees the progress and the list.
 */
function KiiContactBatchPanel() {
  const queryClient = useQueryClient();
  const [count, setCount] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const { data: info } = useQuery({
    queryKey: ["kii-contact-batch"],
    queryFn: () => adminFetch<KiiBatchInfo>("/contacts/kii-contact-search/batch/"),
    refetchInterval: (query) => (query.state.data?.progress?.active ? 10000 : false),
  });
  const run = useMutation({
    mutationFn: (limit: number) =>
      adminFetch<{ queued: number; estimated_cost_usd: [number, number] }>("/contacts/kii-contact-search/batch/", {
        method: "POST",
        body: JSON.stringify({ limit }),
      }),
    onSuccess: (data) => {
      const [low, high] = data.estimated_cost_usd;
      setCount("");
      setResult(
        `Queued ${data.queued} search${data.queued === 1 ? "" : "es"} (estimated US$${low.toFixed(2)}–${high.toFixed(2)}). ` +
          "They run one at a time, about a minute each; findings appear below as they come in.",
      );
      queryClient.invalidateQueries({ queryKey: ["kii-contact-batch"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not start the searches."),
  });
  if (!info) return null;
  const progress = info.progress;
  const active = !!progress?.active;
  const max = Math.min(info.max, info.without_contacts);
  const limit = Number(count || 0);
  const [low, high] = info.cost_per_case_usd;
  const left = progress ? progress.queued + progress.running : 0;

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Find contact details with AI</h3>
      <p className="text-xs text-text-muted">
        {info.without_contacts} informant{info.without_contacts === 1 ? "" : "s"} not yet interviewed ha
        {info.without_contacts === 1 ? "s" : "ve"} no phone, WhatsApp or email on file. The AI looks for their
        organisation&rsquo;s published phone and email and their own work phone or email where the organisation publishes it, and for
        whoever holds the role where the contact is not yet identified. Nothing is saved until it is accepted on the
        record&rsquo;s page. Roughly US${low.toFixed(2)}–{high.toFixed(2)} per record.
      </p>
      {!info.configured && <p className="text-sm">AI research hasn&rsquo;t been set up yet. Ask the administrator.</p>}
      {progress && (
        <p className="text-sm" role="status">
          {active ? "Batch in progress: " : "Last batch: "}
          {progress.done} done{progress.running ? ", 1 searching now" : ""}
          {progress.queued ? `, ${progress.queued} waiting` : ""}
          {progress.failed ? `, ${progress.failed} failed` : ""} (of {progress.total}).
          {active && ` About ${left} minute${left === 1 ? "" : "s"} once it reaches the front of the line.`}
        </p>
      )}
      <WriteOnly note={null}>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs text-text-muted">
            How many records (up to {max})
            <input
              type="number"
              min={1}
              max={max}
              value={count}
              disabled={active}
              onChange={(e) => setCount(e.target.value)}
              className="block mt-1 w-28 rounded-md border border-border px-3 py-2 bg-surface text-sm"
            />
          </label>
          <Button
            variant="outline"
            disabled={!info.configured || active || max < 1 || limit < 1 || limit > max || run.isPending}
            onClick={() => run.mutate(limit)}
          >
            {run.isPending ? "Starting…" : "Find contacts"}
          </Button>
        </div>
        {active && <p className="text-xs text-text-muted">Start the next batch when this one has finished.</p>}
      </WriteOnly>
      {result && <p className="text-sm">{result}</p>}
      {info.to_review_total > 0 && (
        <details open className="text-sm">
          <summary className="cursor-pointer font-medium">
            Findings to review ({info.to_review_total} record{info.to_review_total === 1 ? "" : "s"})
          </summary>
          <ul className="mt-1 divide-y divide-border">
            {info.to_review.map((row) => (
              <li key={row.id} className="py-1.5 flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words">
                  <span className="font-mono text-xs">{row.kii_id}</span> · {row.participant}
                </span>
                <Link href={`/admin/kii/${row.id}`} className="text-header underline text-xs whitespace-nowrap">
                  Review {row.findings} finding{row.findings === 1 ? "" : "s"}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

/**
 * A basic register view -- scheduling, consent and transcript workflow UI
 * land in Phase 7 alongside the rest of the KII module's build-out
 * (docs/27_AGENT_EXECUTION_PLAN.md Phase 7).
 */
export default function KIIRegisterPage() {
  const [search, setSearch] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();

  const { data, isLoading } = useQuery({
    queryKey: ["kii-records", search, page, pageSize],
    queryFn: () =>
      adminFetch<Paginated<KIIRecord>>(
        `/kii/?page=${page}&page_size=${pageSize}` + (search ? `&search=${encodeURIComponent(search)}` : ""),
      ),
    placeholderData: keepPreviousData,
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">KII Register</h2>
        <div className="flex items-center gap-3 flex-wrap">
          <SearchBox
            value={search}
            onChange={(v) => {
              setSearch(v);
              setPage(1);
            }}
            placeholder="Search KII ID, name or role"
          />
          <WriteOnly note={null}>
            <Link href="/admin/kii/new">
              <Button>New KII record</Button>
            </Link>
          </WriteOnly>
        </div>
      </div>
      <KiiContactBatchPanel />
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">
            {search ? `No KII records match "${search}".` : "No KII records yet."}
          </p>
        ) : (
          <>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-2 pr-4">KII ID</th>
                <th className="py-2 pr-4">Stakeholder category</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Transcript</th>
                <th className="py-2 pr-4">Coding</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((k) => (
                <tr key={k.id} className="border-t border-border">
                  <td className="py-2 pr-4 font-mono text-xs">{k.kii_id}</td>
                  <td className="py-2 pr-4">{k.stakeholder_category}</td>
                  <td className="py-2 pr-4">{k.status}</td>
                  <td className="py-2 pr-4">{k.transcript_status}</td>
                  <td className="py-2 pr-4">{k.coding_status}</td>
                  <td className="py-2">
                    <Link href={`/admin/kii/${k.id}`} className="text-header underline text-xs">
                      Manage
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="KII records" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
