"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface Row {
  kii_id: string;
  kii_record_id: number;
  organisation: string;
  status: "NO_REPLY" | "NOT_DELIVERED";
  status_label: string;
  asked_on: string;
  number: string;
}

/**
 * KII informants asked first who never answered after the reminder, or whose introduction never arrived (backend
 * outreach.kii_unanswered, 2026-10-14): the people to phone. Shows nothing when the list is empty.
 */
export function KiiUnansweredPanel() {
  const { data } = useQuery({
    queryKey: ["kii-outreach-unanswered"],
    queryFn: () => adminFetch<{ count: number; results: Row[] }>("/kii-outreach/unanswered/"),
    refetchInterval: 60000,
  });
  if (!data || data.count === 0) return null;
  return (
    <Card className="mb-4 space-y-3" aria-label="Asked, no reply">
      <div>
        <h3 className="font-semibold">
          Asked, no reply: phone them <span className="ml-1 rounded-full bg-bg border border-border px-2 py-px text-xs">{data.count}</span>
        </h3>
        <p className="text-xs text-text-muted">
          These informants got the introduction and a reminder but never answered, or the message could not be delivered.
          Phone them; if they agree, send their link from the record page.
        </p>
      </div>
      <ul className="divide-y divide-border text-sm">
        {data.results.map((row) => (
          <li key={row.kii_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <Link href={`/admin/kii/${row.kii_record_id}`} className="min-w-0 underline">
              <span className="font-mono text-xs">{row.kii_id}</span> · {row.organisation}
            </Link>
            <span className="text-xs text-text-muted tabular-nums">
              {row.status_label} · asked {new Date(row.asked_on).toLocaleDateString()} · {row.number}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
