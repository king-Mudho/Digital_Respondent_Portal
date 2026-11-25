"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { adminFetch } from "@/lib/api/admin";
import { usd, type PausedRA } from "@/lib/api/ra";

/**
 * Paused (deactivated) research assistants, in red, and the PI's pause / reactivate control (PI, 25 Nov 2026).
 * Shown on Research assistants and, for the PI only, on My work. The backend decides who may change an account.
 */

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "never";
}

/** Deactivated RAs (PI, 25 Nov 2026), in red: they cannot sign in and are told to contact the PI. */
export function PausedList({ paused, canChange }: { paused: PausedRA[]; canChange: boolean }) {
  return (
    <div className="space-y-2 rounded-lg border-2 border-danger bg-surface p-3">
      <h3 className="font-medium text-danger">Paused research assistants ({paused.length})</h3>
      <p className="text-xs text-text-muted">
        These accounts are deactivated: they cannot sign in, and are told to contact the PI. Reactivating one gives them
        no work by itself — give them work with the form below.
      </p>
      <ul className="divide-y divide-border">
        {paused.map((p) => (
          <li key={p.id} className="flex flex-wrap items-start justify-between gap-3 py-2">
            <div className="text-sm">
              <span className="font-semibold text-danger">{p.name}</span>{" "}
              <span className="rounded bg-danger px-1.5 py-0.5 text-xs font-medium text-white">Paused</span>
              <span className="block text-xs text-text-muted">
                {p.role_label} · paused {day(p.paused_at)} · last signed in {day(p.last_login)}
              </span>
              {p.paused_reason && <span className="block text-xs text-text-muted">Reason: {p.paused_reason}</span>}
              <span className="block text-xs text-text-muted">
                Still on the account: {p.workload.main_assigned} Main · {p.workload.kii_assigned} KII
                {(p.open.main > 0 || p.open.kii > 0) && <> ({p.open.main + p.open.kii} open)</>} · {p.total} completed · {usd(p.earned_usd)} earned
              </span>
            </div>
            {canChange && <StatusChange id={p.id} name={p.name} active={false} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Pause an active RA, or reactivate a paused one -- the PI only, with a reason (backend checks both). */
export function StatusChange({ id, name, active }: { id: number; name: string; active: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      adminFetch(`/ra/accounts/${id}/status/`, { method: "POST", body: JSON.stringify({ active: !active, reason }) }),
    onSuccess: () => {
      setOpen(false);
      setReason("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["ra-team"] });
      queryClient.invalidateQueries({ queryKey: ["my-work"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Not changed."),
  });
  if (!open) {
    return active ? (
      <button type="button" className="text-xs text-danger underline" onClick={() => setOpen(true)}>Pause</button>
    ) : (
      <Button className="min-h-8 px-3 py-1 text-sm" onClick={() => setOpen(true)}>Reactivate</Button>
    );
  }
  return (
    <div className="mt-1 w-64 space-y-1 text-left text-xs">
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder={active ? `Why pause ${name}? (required)` : `Why reactivate ${name}? (required)`}
        className="w-full rounded-md border border-border bg-surface px-2 py-1"
      />
      {error && <p role="alert" className="text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button className="min-h-7 px-2 py-0.5 text-xs" disabled={!reason.trim() || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : active ? "Pause account" : "Reactivate account"}
        </Button>
        <button type="button" className="underline" onClick={() => { setOpen(false); setError(null); }}>Cancel</button>
      </div>
    </div>
  );
}
