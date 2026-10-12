"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IfRole } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { useAdminUser } from "@/lib/auth/session";

interface Replacement {
  reserve: string;
  organisation: string;
  replaces: string;
  trigger: string;
  reason: string;
  activated_at: string;
  evidence: string;
  state: string;
  label: string;
  note: string;
}

interface ReplacementData {
  policy: { enabled: boolean; triggers: string[]; daily_max: number; enabled_by: string; enabled_at: string | null };
  trigger_choices: { value: string; label: string }[];
  due_now: number;
  replacements: Replacement[];
}

const STATE_TONE: Record<string, string> = {
  ACCEPTED: "text-success",
  DECLINED: "text-danger",
  NO_REPLY: "text-warning",
  NOT_DELIVERED: "text-danger",
  NEEDS_CONTACT: "text-warning",
};

/**
 * Automatic Reserve replacement (backend apps/sampling/replacement.py, PI decision 2026-10-12). The PI switches it on
 * once; that is the standing authorisation named on every automatic activation (AGENTS.md rule 4). Every morning at
 * 08:00 each Main case that did not take part has its own paired Reserve activated and introduced on WhatsApp.
 */
export function AutoReplacementPanel() {
  const queryClient = useQueryClient();
  const user = useAdminUser();
  const isPi = user?.role === "PI_ADMIN";
  const { data } = useQuery({
    queryKey: ["reserve-replacement"],
    queryFn: () => adminFetch<ReplacementData>("/reserve-replacement/"),
  });
  const [draft, setDraft] = useState<{ triggers: string[]; daily_max: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (body: { enabled: boolean; triggers: string[]; daily_max: number }) =>
      adminFetch<ReplacementData>("/reserve-replacement/", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (next) => {
      setError(null);
      setDraft(null);
      queryClient.setQueryData(["reserve-replacement"], next);
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The change was not saved."),
  });

  if (!data) return <div className="h-24 rounded-lg border border-border bg-surface animate-pulse mb-4" aria-label="Loading" />;
  const { policy } = data;
  const triggers = draft?.triggers ?? policy.triggers;
  const dailyMax = draft?.daily_max ?? policy.daily_max;
  const edited = draft !== null;
  const toggle = (value: string) =>
    setDraft({ daily_max: dailyMax, triggers: triggers.includes(value) ? triggers.filter((t) => t !== value) : [...triggers, value] });

  return (
    <div className="space-y-4 mb-6">
      <Card className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <h3 className="font-semibold">Automatic replacement</h3>
            <p className="text-sm text-text-muted">
              Every morning at 08:00, each Main case that did not take part (the outcomes ticked below) has its own paired
              Reserve activated and introduced on WhatsApp. A YES sends the invitation link automatically. The Main case keeps
              its outcome; its open link is cancelled.
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              policy.enabled ? "bg-success text-white" : "border border-border text-text-muted"
            }`}
          >
            {policy.enabled ? "On" : "Off"}
          </span>
        </div>

        {policy.enabled && policy.enabled_by && (
          <p className="text-xs text-text-muted">
            Switched on by <b>{policy.enabled_by}</b>
            {policy.enabled_at && ` on ${new Date(policy.enabled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`}.
            Each activation is recorded under that standing authorisation, with its reason and what happened.
          </p>
        )}

        <fieldset className="space-y-2" disabled={!isPi}>
          <legend className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1">Replace when the Main case</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {data.trigger_choices.map((choice) => (
              <label key={choice.value} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={triggers.includes(choice.value)} onChange={() => toggle(choice.value)} />
                {choice.label}
              </label>
            ))}
          </div>
          <label className="flex flex-wrap items-center gap-2 text-sm pt-1">
            At most
            <input
              type="number"
              min={1}
              max={100}
              value={dailyMax}
              onChange={(e) => setDraft({ triggers, daily_max: Number(e.target.value) })}
              className="w-20 rounded-md border border-border bg-surface px-2 py-1 text-sm"
              aria-label="Most Reserves activated per day"
            />
            Reserves a day
          </label>
        </fieldset>

        <p className="text-sm">
          {edited
            ? "Save to see how many Main cases these outcomes would replace."
            : data.due_now > 0
            ? `${data.due_now} Main case${data.due_now === 1 ? "" : "s"} would be replaced at the next 08:00 run with these outcomes.`
            : "No Main case is waiting to be replaced with these outcomes."}
        </p>

        {error && <p role="alert" className="text-sm text-danger">{error}</p>}

        <IfRole roles={["PI_ADMIN"]}>
          <div className="flex flex-wrap gap-2">
            {edited && (
              <Button
                variant="outline"
                disabled={save.isPending}
                onClick={() => save.mutate({ enabled: policy.enabled, triggers, daily_max: dailyMax })}
              >
                Save changes
              </Button>
            )}
            {policy.enabled ? (
              <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate({ enabled: false, triggers, daily_max: dailyMax })}>
                Switch off
              </Button>
            ) : (
              <Button disabled={save.isPending || triggers.length === 0} onClick={() => save.mutate({ enabled: true, triggers, daily_max: dailyMax })}>
                Switch on automatic replacement
              </Button>
            )}
          </div>
        </IfRole>
        {!isPi && <p className="text-xs text-text-muted">Only the PI can switch this on or off or change it.</p>}
      </Card>

      {data.replacements.length > 0 && (
        <Card className="space-y-3">
          <h3 className="font-semibold">Replaced automatically</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-text-muted">
                  <th className="py-2 pr-3 font-medium">When</th>
                  <th className="py-2 pr-3 font-medium">Main case</th>
                  <th className="py-2 pr-3 font-medium">Reason</th>
                  <th className="py-2 pr-3 font-medium">Reserve</th>
                  <th className="py-2 font-medium">Contact</th>
                </tr>
              </thead>
              <tbody>
                {data.replacements.map((r) => (
                  <tr key={r.reserve} className="border-t border-border align-top">
                    <td className="py-2 pr-3 whitespace-nowrap tabular-nums">{new Date(r.activated_at).toLocaleDateString([], { day: "numeric", month: "short" })}</td>
                    <td className="py-2 pr-3">
                      <Link href={`/admin/sample/${r.replaces}`} className="font-mono text-xs underline">{r.replaces}</Link>
                    </td>
                    <td className="py-2 pr-3" title={r.evidence}>{r.reason}</td>
                    <td className="py-2 pr-3">
                      <Link href={`/admin/sample/${r.reserve}`} className="font-mono text-xs underline">{r.reserve}</Link>
                      <div className="text-xs text-text-muted">{r.organisation}</div>
                    </td>
                    <td className="py-2">
                      <span className={STATE_TONE[r.state] ?? ""}>{r.label}</span>
                      {r.note && <div className="text-xs text-text-muted">{r.note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
