"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { CreditList } from "@/components/admin/CreditList";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { firstOfMonth, periodQuery, type MyWork } from "@/lib/api/ra";

const SHORTCUTS = [
  { href: "/admin/calls", label: "Calls", text: "Everyone assigned to you, closest to finishing first. Phone them, fill in the form with them, log each call." },
  { href: "/admin/communications", label: "Communications", text: "WhatsApp, SMS and email with your people, and what they wrote back." },
  { href: "/admin/appointments", label: "Appointments", text: "Times people asked you to call them back." },
  { href: "/admin/follow-ups", label: "Follow-ups", text: "Reminders due for people who haven't finished." },
];

/**
 * A research assistant's own page (backend apps/ra, 2026-11-08): what is assigned to them, what they did this week,
 * and every completion credited to them -- the number they are paid on. Only ever their own.
 */
export default function MyWorkPage() {
  return (
    <AdminShell>
      <MyWorkView />
    </AdminShell>
  );
}

function MyWorkView() {
  const [since, setSince] = useState(firstOfMonth());
  const [until, setUntil] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["my-work", since, until],
    queryFn: () => adminFetch<MyWork>(`/ra/my-work/?${periodQuery(since, until)}`),
  });

  if (error) return <p className="text-danger">{error instanceof Error ? error.message : "Your work could not be loaded."}</p>;
  if (isLoading || !data) return <p className="text-text-muted">Loading…</p>;
  const t = data.totals;
  const w = data.workload;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">My work</h2>
        <p className="text-sm text-text-muted">{data.name} · the people assigned to you and the forms credited to you.</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-text-muted">Completed (credited to you)</p>
          <p className="text-3xl font-semibold tabular-nums">{t?.total ?? 0}</p>
          <p className="text-xs text-text-muted">in the period below</p>
        </Card>
        <Card className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-text-muted">Questionnaires</p>
          <p className="text-lg font-semibold tabular-nums">{(t?.quan_administered ?? 0) + (t?.quan_assisted ?? 0)}</p>
          <p className="text-xs text-text-muted">
            {t?.quan_administered ?? 0} filled in with you · {t?.quan_assisted ?? 0} assisted · {t?.quan_qa_passed ?? 0} passed QA
          </p>
        </Card>
        <Card className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-text-muted">Key informant interviews</p>
          <p className="text-lg font-semibold tabular-nums">{(t?.kii_administered ?? 0) + (t?.kii_assisted ?? 0)}</p>
          <p className="text-xs text-text-muted">{t?.kii_administered ?? 0} you conducted · {t?.kii_assisted ?? 0} assisted</p>
        </Card>
        <Card className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-text-muted">Assigned to you</p>
          <p className="text-lg font-semibold tabular-nums">{w.main_assigned} Main-400 · {w.kii_assigned} KII</p>
          <p className="text-xs text-text-muted">{w.calls_7d} calls and {w.contacts_7d} contacts logged in the last 7 days</p>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {SHORTCUTS.map((s) => (
          <Link key={s.href} href={s.href} className="rounded-lg border border-border bg-surface p-3 hover:border-header">
            <span className="font-medium text-header">{s.label} →</span>
            <span className="mt-1 block text-xs text-text-muted">{s.text}</span>
          </Link>
        ))}
      </div>

      <Card className="space-y-2 text-sm">
        <h3 className="font-medium">How a completion is credited to you</h3>
        <p className="text-text-muted">
          <span className="font-medium text-text">Administered:</span> you opened the form with <em>Fill in with them now</em> on
          Calls and completed it with them. <span className="font-medium text-text">Assisted:</span> they completed it themselves,
          and your call or message (logged on Calls, or sent from Communications) was the last one before it, within{" "}
          {data.assist_days} days. Log every call, including ones from your own phone, or it can&apos;t count.
        </p>
      </Card>

      <div className="space-y-2">
        <div className="flex flex-wrap items-end gap-3">
          <h3 className="font-medium">Completions credited to you</h3>
          <label className="text-xs text-text-muted">
            From <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="ml-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-text" />
          </label>
          <label className="text-xs text-text-muted">
            To <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="ml-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-text" />
          </label>
          <button type="button" className="text-xs underline" onClick={() => { setSince(""); setUntil(""); }}>All time</button>
        </div>
        <CreditList credits={data.credits} showRA={false} empty="Nothing credited to you in this period yet." />
      </div>
    </div>
  );
}
