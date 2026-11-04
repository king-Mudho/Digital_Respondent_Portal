"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { CallChannel, CallOptions } from "@/lib/api/communications";

export interface CallLog {
  channel: CallChannel;
  outcome: string;
  notes: string;
  next_action_date: string;
}

const BUTTONS: { channel: CallChannel; label: string; hint: string }[] = [
  { channel: "WHATSAPP_CALL", label: "Voice call", hint: "Opens their chat in WhatsApp on this computer or phone: press the phone icon there to call." },
  { channel: "WHATSAPP_VIDEO", label: "Video call", hint: "Opens their chat in WhatsApp on this computer or phone: press the camera icon there to video call." },
  { channel: "PHONE", label: "Phone", hint: "Dials the number on this device (a phone, or a computer set up for calls)." },
];

/**
 * Calling them (2026-11-04). WhatsApp lets a business number send messages but not start a video call, so a WhatsApp
 * voice or video call is made in the caller's own WhatsApp: the button opens the person's chat there, and the call
 * is then logged here like a phone call -- which is what the "Called" filter and the Calls screen count.
 */
export function CallBar({
  calls,
  logging,
  error,
  onLog,
}: {
  calls: CallOptions;
  logging: boolean;
  error: string | null;
  onLog: (log: CallLog) => Promise<boolean>;
}) {
  const [chosen, setChosen] = useState(calls.numbers[0]?.number ?? "");
  const [form, setForm] = useState<CallLog | null>(null);
  const [done, setDone] = useState("");
  const number = calls.numbers.find((n) => n.number === chosen) ?? calls.numbers[0];

  if (!calls.numbers.length) {
    return <p className="border-b border-border px-4 py-2 text-xs text-text-muted">No phone number is recorded, so they can&apos;t be called from here.</p>;
  }

  const start = (channel: CallChannel) => {
    const href = channel === "PHONE" ? number?.tel : number?.whatsapp_link;
    if (href) window.open(href, channel === "PHONE" ? "_self" : "_blank", "noopener");
    setDone("");
    if (calls.can_log) setForm({ channel, outcome: "", notes: "", next_action_date: "" });
  };

  const submit = async () => {
    if (!form) return;
    const ok = await onLog(form);
    if (ok) {
      setDone(`${calls.channels.find((c) => c.value === form.channel)?.label ?? "Call"} logged.`);
      setForm(null);
    }
  };

  return (
    <div className="space-y-2 border-b border-border bg-surface px-4 py-2">
      <div className="flex flex-wrap items-center gap-2">
        {calls.numbers.length > 1 ? (
          <select
            aria-label="Number to call"
            value={number?.number}
            onChange={(e) => setChosen(e.target.value)}
            className="max-w-[14rem] rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
          >
            {calls.numbers.map((n) => (
              <option key={n.number} value={n.number}>
                {n.number}
                {n.person ? ` · ${n.person}` : ""}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-xs tabular-nums text-text-muted">{number?.number}</span>
        )}
        {BUTTONS.map((b) => {
          const usable = b.channel === "PHONE" ? !!number?.tel : !!number?.whatsapp_link;
          return (
            <Button
              key={b.channel}
              type="button"
              variant="outline"
              title={b.hint}
              disabled={!usable}
              onClick={() => start(b.channel)}
              className="min-h-8 px-2.5 py-1 text-xs"
            >
              {b.label}
            </Button>
          );
        })}
        {calls.can_log && !form && (
          <button type="button" className="text-xs text-text-muted underline" onClick={() => setForm({ channel: "PHONE", outcome: "", notes: "", next_action_date: "" })}>
            Log a call
          </button>
        )}
        {done && <span role="status" className="text-xs text-success">{done}</span>}
      </div>

      {form && (
        <div className="space-y-2 rounded-md border border-border bg-bg p-2.5">
          <p className="text-xs font-medium">After the call, record what happened</p>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="How you called"
              value={form.channel}
              onChange={(e) => setForm({ ...form, channel: e.target.value as CallChannel })}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
            >
              {calls.channels.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            <select
              aria-label="What happened"
              value={form.outcome}
              onChange={(e) => setForm({ ...form, outcome: e.target.value })}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
            >
              <option value="">What happened…</option>
              {calls.outcomes.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <label className="flex items-center gap-1 text-xs text-text-muted">
              Call back
              <input
                type="date"
                value={form.next_action_date}
                onChange={(e) => setForm({ ...form, next_action_date: e.target.value })}
                className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-text"
              />
            </label>
          </div>
          <textarea
            aria-label="Notes"
            rows={2}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Notes: who you spoke to, what was agreed"
            className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
          />
          <div className="flex items-center gap-2">
            <Button type="button" onClick={submit} disabled={logging || !form.outcome} className="min-h-8 px-3 py-1 text-xs">
              {logging ? "Saving…" : "Save the call"}
            </Button>
            <button type="button" className="text-xs text-text-muted underline" onClick={() => setForm(null)}>
              Not now
            </button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
    </div>
  );
}
