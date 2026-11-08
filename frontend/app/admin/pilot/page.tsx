"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import type { PilotListing, PilotRecordRow, PilotStrand } from "@/lib/api/pilot";

const STRANDS: { key: "" | PilotStrand; label: string }[] = [
  { key: "", label: "All" },
  { key: "QUAN", label: "Questionnaires" },
  { key: "KII", label: "KIIs" },
  { key: "DOCUMENT", label: "Documents" },
];

/**
 * The Zimbabwe Agricultural Show pilot (ZAS 2026), held beside the main study (backend apps/kobo/pilot.py, PI decision
 * 8 Nov 2026). Its records count next to the main figures on the dashboards, labelled, and never enter the Main-400
 * sample or its exports. Here the PI sees each pilot record -- a summary that identifies nobody -- and decides which
 * are counted; the cleaning flags say which need a decision.
 */
export default function PilotPage() {
  return (
    <AdminShell>
      <Pilot />
    </AdminShell>
  );
}

function Pilot() {
  const queryClient = useQueryClient();
  const [strand, setStrand] = useState<"" | PilotStrand>("");
  const [show, setShow] = useState<"" | "flagged" | "excluded">("");
  const [error, setError] = useState<string | null>(null);
  const params = new URLSearchParams({ strand, show });
  const { data, isLoading } = useQuery({
    queryKey: ["pilot", params.toString()],
    queryFn: () => adminFetch<PilotListing>(`/pilot/?${params}`),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["pilot"] });
  const sync = useMutation({
    mutationFn: () => adminFetch("/pilot/sync/", { method: "POST", body: "{}" }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The pilot data could not be fetched."),
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <h2 className="text-xl font-semibold">ZAS 2026 pilot</h2>
          <p className="text-sm text-text-muted">
            The Zimbabwe Agricultural Show pilot (25–31 August 2026), held beside the main study. Its records are counted
            next to the main figures on the dashboards, always shown as “main + pilot”, and never enter the Main-400
            sample or its exports. The answers stay in KoboToolbox; this screen shows a summary that identifies nobody.
          </p>
        </div>
        <IfRole roles={["PI_ADMIN"]}>
          <div className="flex flex-col items-end gap-1">
            <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending} className="min-h-9 py-1.5">
              {sync.isPending ? "Fetching…" : "Fetch again from KoboToolbox"}
            </Button>
            {data?.last_synced_at && (
              <span className="text-[11px] text-text-muted">Last fetched {new Date(data.last_synced_at).toLocaleString()}</span>
            )}
          </div>
        </IfRole>
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      {data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.totals.map((t) => (
            <Card key={t.form} className="space-y-1">
              <p className="text-xs uppercase tracking-wide text-text-muted">{t.title}</p>
              <p className="text-2xl font-semibold tabular-nums">{t.included}</p>
              <p className="text-sm text-text-muted">counted{t.excluded > 0 && ` · ${t.excluded} left out`}</p>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1" role="tablist" aria-label="Strand">
          {STRANDS.map((s) => (
            <button
              key={s.key || "all"}
              role="tab"
              aria-selected={strand === s.key}
              onClick={() => setStrand(s.key)}
              className={`rounded-md px-3 py-1.5 text-sm ${strand === s.key ? "bg-header text-white" : "text-text-muted hover:bg-bg"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <select
          aria-label="Show"
          value={show}
          onChange={(e) => setShow(e.target.value as typeof show)}
          className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        >
          <option value="">Every record</option>
          <option value="flagged">Needs a decision (flagged)</option>
          <option value="excluded">Left out</option>
        </select>
      </div>

      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : data.results.length === 0 ? (
        <p className="text-sm text-text-muted">
          {data.totals.every((t) => t.included + t.excluded === 0)
            ? "No pilot records yet. The PI can fetch them from KoboToolbox."
            : "No records match."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-muted">
                <th className="px-3 py-2">Form</th>
                <th className="px-3 py-2">ID on the form</th>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Summary</th>
                <th className="px-3 py-2">Needs a decision</th>
                <th className="px-3 py-2">Counted</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <Row key={r.id} record={r} onChanged={refresh} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ record: r, onChanged }: { record: PilotRecordRow; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const decide = useMutation({
    mutationFn: (body: { included: boolean; reason: string }) =>
      adminFetch(`/pilot/${r.id}/decision/`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      setEditing(false);
      setReason("");
      setError(null);
      onChanged();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The decision was not saved."),
  });

  return (
    <tr className={`border-b border-border align-top last:border-0 ${r.included ? "" : "bg-bg text-text-muted"}`}>
      <td className="px-3 py-2">
        <span className="block whitespace-nowrap">{r.form_title}</span>
        <span className="text-[11px] text-text-muted">Kobo #{r.kobo_id}</span>
      </td>
      <td className="px-3 py-2 font-mono text-xs">{r.reference || "—"}</td>
      <td className="whitespace-nowrap px-3 py-2 tabular-nums">{r.collected_on ?? "—"}</td>
      <td className="px-3 py-2 text-xs">
        {Object.entries(r.summary).map(([k, v]) => (
          <span key={k} className="block">
            <span className="text-text-muted">{k}:</span> {v}
          </span>
        ))}
      </td>
      <td className="px-3 py-2 text-xs">
        {r.flags.length ? r.flags.map((f) => <span key={f} className="block text-warning">{f}</span>) : <span className="text-text-muted">—</span>}
      </td>
      <td className="min-w-[13rem] px-3 py-2 text-xs">
        {r.included ? (
          <span className="font-medium text-success">Counted</span>
        ) : (
          <span>
            <span className="font-medium">Left out</span>
            {r.exclusion_reason && <span className="block">{r.exclusion_reason}</span>}
          </span>
        )}
        {r.decided_by && <span className="block text-text-muted">by {r.decided_by}</span>}
        {r.consented !== false && (
          <IfRole roles={["PI_ADMIN"]}>
            {editing ? (
              <span className="mt-1 block space-y-1">
                <input
                  aria-label="Why it is left out"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why it is left out"
                  className="w-full rounded-md border border-border bg-surface px-2 py-1 text-xs"
                />
                <span className="flex gap-2">
                  <Button
                    onClick={() => decide.mutate({ included: false, reason })}
                    disabled={decide.isPending || !reason.trim()}
                    className="min-h-7 px-2 py-0.5 text-xs"
                  >
                    Leave out
                  </Button>
                  <button type="button" className="underline" onClick={() => setEditing(false)}>Cancel</button>
                </span>
              </span>
            ) : r.included ? (
              <button type="button" className="mt-1 block underline" onClick={() => setEditing(true)}>Leave out…</button>
            ) : (
              <button type="button" className="mt-1 block underline" disabled={decide.isPending} onClick={() => decide.mutate({ included: true, reason: "" })}>
                Count it
              </button>
            )}
          </IfRole>
        )}
        {error && <span role="alert" className="block text-danger">{error}</span>}
      </td>
    </tr>
  );
}
