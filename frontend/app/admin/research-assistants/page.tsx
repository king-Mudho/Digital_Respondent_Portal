"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { CreditList } from "@/components/admin/CreditList";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { firstOfMonth, periodQuery, type CreditRow, type Team } from "@/lib/api/ra";

/**
 * The research assistants (backend apps/ra, 2026-11-08): who is assigned what, how many forms each one administered
 * or assisted -- the pay sheet -- and every completion with the RA who earned it. The PI and Field Coordinator assign
 * work; only the PI changes a credit, with a reason.
 */
export default function ResearchAssistantsPage() {
  return (
    <AdminShell>
      <TeamView />
    </AdminShell>
  );
}

function TeamView() {
  const [since, setSince] = useState(firstOfMonth());
  const [until, setUntil] = useState("");
  const query = periodQuery(since, until);
  const { data, isLoading, error } = useQuery({ queryKey: ["ra-team", query], queryFn: () => adminFetch<Team>(`/ra/team/?${query}`) });

  if (error) return <p className="text-danger">{error instanceof Error ? error.message : "The team could not be loaded."}</p>;
  if (isLoading || !data) return <p className="text-text-muted">Loading…</p>;
  const telephone = data.team.filter((m) => m.role === "TELEPHONE_RA");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <h2 className="text-xl font-semibold">Research assistants</h2>
          <p className="text-sm text-text-muted">
            Each completed questionnaire or KII is credited to the RA who <b>administered</b> it (filled it in with the
            respondent from the portal) or <b>assisted</b> it (their call or message was the last before the respondent
            completed it, within {data.assist_days} days) — or to nobody.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2 text-xs text-text-muted">
          <label>From <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="ml-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-text" /></label>
          <label>To <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="ml-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-text" /></label>
          <button type="button" className="underline" onClick={() => { setSince(""); setUntil(""); }}>All time</button>
          <a href={`/api/proxy/ra/team/?${query}${query ? "&" : ""}download=csv`} className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text hover:bg-bg">
            Download pay sheet (CSV)
          </a>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-text-muted">
              <th className="px-3 py-2">Research assistant</th>
              <th className="px-3 py-2">Assigned</th>
              <th className="px-3 py-2">Calls (7 days)</th>
              <th className="px-3 py-2 text-right">Questionnaires<span className="block font-normal">administered / assisted</span></th>
              <th className="px-3 py-2 text-right">KIIs<span className="block font-normal">administered / assisted</span></th>
              <th className="px-3 py-2 text-right">Passed QA</th>
              <th className="px-3 py-2 text-right">Total completed</th>
            </tr>
          </thead>
          <tbody>
            {data.team.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-3 text-text-muted">No RA accounts yet.</td></tr>
            )}
            {data.team.map((m) => (
              <tr key={m.id} className="border-b border-border last:border-0">
                <td className="px-3 py-2">
                  <span className="font-medium">{m.name}</span>
                  <span className="block text-xs text-text-muted">{m.role_label}</span>
                </td>
                <td className="px-3 py-2 tabular-nums">{m.workload.main_assigned} Main · {m.workload.kii_assigned} KII</td>
                <td className="px-3 py-2 tabular-nums">{m.workload.calls_7d}</td>
                <td className="px-3 py-2 text-right tabular-nums">{m.credits.quan_administered} / {m.credits.quan_assisted}</td>
                <td className="px-3 py-2 text-right tabular-nums">{m.credits.kii_administered} / {m.credits.kii_assisted}</td>
                <td className="px-3 py-2 text-right tabular-nums">{m.credits.quan_qa_passed}</td>
                <td className="px-3 py-2 text-right text-lg font-semibold tabular-nums">{m.credits.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.others.length > 0 && (
        <p className="text-xs text-text-muted">
          Also filled in by staff who are not RAs: {data.others.map((o) => `${o.name} (${o.total})`).join(", ")}.
        </p>
      )}
      <p className="text-xs text-text-muted">{data.uncredited} completion{data.uncredited === 1 ? "" : "s"} in this period had no RA involved.</p>

      <WriteOnly note={null}>
        <AssignWork telephone={telephone} unassigned={data.unassigned} holders={data.main_holders ?? []} />
      </WriteOnly>

      <div className="space-y-2">
        <h3 className="font-medium">Completed submissions and who earned them</h3>
        <CreditList
          credits={data.credits}
          showRA
          empty="No completions in this period."
          action={data.can_override ? (c) => <Override credit={c} team={data.team} /> : undefined}
        />
      </div>
    </div>
  );
}

function AssignWork({
  telephone,
  unassigned,
  holders,
}: {
  telephone: Team["team"];
  unassigned: Team["unassigned"];
  holders: NonNullable<Team["main_holders"]>;
}) {
  const queryClient = useQueryClient();
  const [ra, setRa] = useState("");
  const [study, setStudy] = useState<"main" | "kii">("main");
  const [from, setFrom] = useState("unassigned");
  const [count, setCount] = useState("20");
  const [result, setResult] = useState<string | null>(null);
  const assign = useMutation({
    mutationFn: () =>
      study === "main"
        ? adminFetch<{ count: number }>("/ra/assign-main/", {
            method: "POST",
            body: JSON.stringify({ ra_id: Number(ra), from, limit: Number(count) }),
          })
        : adminFetch<{ count: number }>("/ra/assign-kii/", {
            method: "POST",
            body: JSON.stringify({ ra_id: Number(ra), from_unassigned: true, limit: Number(count) }),
          }),
    onSuccess: (data) => {
      setResult(`${data.count} ${study === "main" ? "Main-400 cases" : "KII records"} assigned.`);
      queryClient.invalidateQueries({ queryKey: ["ra-team"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Nothing was assigned."),
  });

  return (
    <Card className="space-y-3">
      <h3 className="font-medium">Give work to a research assistant</h3>
      <p className="text-xs text-text-muted">
        Unassigned now: {unassigned.main} open Main-400 cases (activated Reserves included) and {unassigned.kii} open KII
        records{holders.length > 0 && <>; held by accounts: {holders.map((h) => `${h.username} ${h.count}`).join(", ")}</>}.
        Each RA sees and calls only what is assigned to them.
      </p>
      {telephone.length === 0 ? (
        <p className="text-sm text-text-muted">There is no Research Assistant (calls) account yet.</p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            Research assistant
            <select value={ra} onChange={(e) => setRa(e.target.value)} className="mt-1 block min-h-10 rounded-md border border-border bg-surface px-2">
              <option value="">Choose…</option>
              {telephone.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Study
            <select value={study} onChange={(e) => setStudy(e.target.value as "main" | "kii")} className="mt-1 block min-h-10 rounded-md border border-border bg-surface px-2">
              <option value="main">Main-400 cases</option>
              <option value="kii">KII records</option>
            </select>
          </label>
          {study === "main" && (
            <label className="text-sm">
              Take from
              <select value={from} onChange={(e) => setFrom(e.target.value)} className="mt-1 block min-h-10 rounded-md border border-border bg-surface px-2">
                <option value="unassigned">Unassigned ({unassigned.main})</option>
                {holders.map((h) => (
                  <option key={h.id} value={String(h.id)}>{h.username} ({h.count})</option>
                ))}
              </select>
            </label>
          )}
          <label className="text-sm">
            How many
            <input value={count} onChange={(e) => setCount(e.target.value)} inputMode="numeric" className="mt-1 block min-h-10 w-24 rounded-md border border-border bg-surface px-2" />
          </label>
          <Button onClick={() => assign.mutate()} disabled={!ra || !Number(count) || assign.isPending}>
            {assign.isPending ? "Assigning…" : "Assign"}
          </Button>
        </div>
      )}
      {result && <p role="status" className="text-sm">{result}</p>}
    </Card>
  );
}

function Override({ credit, team }: { credit: CreditRow; team: Team["team"] }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [ra, setRa] = useState("");
  const [kind, setKind] = useState("ASSISTED");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      adminFetch(`/ra/credits/${credit.id}/override/`, {
        method: "POST",
        body: JSON.stringify({ ra_id: kind === "UNCREDITED" ? null : Number(ra), kind, reason }),
      }),
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["ra-team"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Not changed."),
  });
  if (!open) return <button type="button" className="text-xs underline" onClick={() => setOpen(true)}>Change</button>;
  return (
    <div className="w-56 space-y-1 text-left text-xs">
      <select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full rounded-md border border-border bg-surface px-1 py-1">
        <option value="ADMINISTERED">Administered</option>
        <option value="ASSISTED">Assisted</option>
        <option value="UNCREDITED">No RA</option>
      </select>
      {kind !== "UNCREDITED" && (
        <select value={ra} onChange={(e) => setRa(e.target.value)} className="w-full rounded-md border border-border bg-surface px-1 py-1">
          <option value="">Research assistant…</option>
          {team.map((m) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
      )}
      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why (required)" className="w-full rounded-md border border-border bg-surface px-1 py-1" />
      {error && <p className="text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button className="min-h-7 px-2 py-0.5 text-xs" disabled={!reason.trim() || (kind !== "UNCREDITED" && !ra) || save.isPending} onClick={() => save.mutate()}>Save</Button>
        <button type="button" className="underline" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}
