"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface QueueRow {
  pre_profile_id: number;
  kii_record_id: number;
  kii_id: string;
  organisation: string;
  to_reconcile: number;
  not_verified: number;
  total: number;
}

/**
 * KII interviews that are in but not finished (backend proit.views.ReconciliationQueueView, 2026-10-13): facts the
 * informant corrected or answered as open questions wait for a researcher's reconciled value, and facts never checked
 * (they skipped the step) need one too, or a protocol deviation. Everything else a self-service informant does is
 * recorded by itself, so this list is the only place a person is needed. Shows nothing when it is empty.
 */
export function ReconciliationQueuePanel() {
  const { data } = useQuery({
    queryKey: ["reconciliation-queue"],
    queryFn: () => adminFetch<{ count: number; results: QueueRow[] }>("/proit/reconciliation-queue/"),
    refetchInterval: 60000,
  });
  if (!data || data.count === 0) return null;
  return (
    <Card className="mb-4 space-y-3 border-warning" aria-label="Needs reconciling">
      <div>
        <h3 className="font-semibold">
          Needs reconciling <span className="ml-1 rounded-full bg-warning px-2 py-px text-xs font-semibold text-white">{data.count}</span>
        </h3>
        <p className="text-xs text-text-muted">
          These informants finished the KII Guide, but some background facts need a researcher: they corrected them,
          answered an open question, or skipped the check. Open the record&apos;s Interview sheet to record the final value,
          or a protocol deviation if it can&apos;t be settled. Coding completes by itself once they&apos;re all done.
        </p>
      </div>
      <ul className="divide-y divide-border text-sm">
        {data.results.map((row) => (
          <li key={row.pre_profile_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <Link href={`/admin/kii/${row.kii_record_id}`} className="min-w-0 underline">
              <span className="font-mono text-xs">{row.kii_id}</span> · {row.organisation}
            </Link>
            <span className="text-xs text-text-muted tabular-nums">
              {row.to_reconcile > 0 && `${row.to_reconcile} to reconcile`}
              {row.to_reconcile > 0 && row.not_verified > 0 && " · "}
              {row.not_verified > 0 && `${row.not_verified} not checked`}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
