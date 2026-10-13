"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface OutreachEntry {
  id: number;
  status: "INTRO_SENT" | "REMINDED" | "ACCEPTED" | "DECLINED" | "NO_REPLY" | "NOT_DELIVERED";
  status_label: string;
  channel: "WHATSAPP" | "SMS";
  number: string;
  intro_sent_at: string;
  reminded_at: string | null;
  replied_at: string | null;
  sms_fallback_sent: boolean;
  messages: { received_at: string; body: string; kind: "YES" | "NO" | "OTHER"; auto_reply: string }[];
}

const INTRODUCED: OutreachEntry["status"][] = ["INTRO_SENT", "REMINDED", "ACCEPTED", "DECLINED"];

type Target = { kind: "case"; sampleId: string } | { kind: "kii"; kiiId: string };

/**
 * "Ask first" (backend apps/messaging/outreach.py): a short introduction to the study asking whether they will take
 * part. A YES reply on WhatsApp sends the personal link automatically; a NO records the refusal -- S12 for a Main-400
 * case, DECLINED for a KII record (KII added 2026-10-14). Hidden until Twilio's WhatsApp number is set up, unless there
 * is already an introduction to show.
 */
export function IntroductionPanel({ target }: { target: Target }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const kii = target.kind === "kii";
  const path = kii ? "/kii-outreach/" : "/outreach/";
  const body = kii ? { kii_id: target.kiiId } : { sample_id: target.sampleId };
  const query = kii ? `kii_id=${encodeURIComponent(target.kiiId)}` : `sample_id=${encodeURIComponent(target.sampleId)}`;
  const key = ["outreach", target.kind, kii ? target.kiiId : target.sampleId];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<{ intro_channel: "WHATSAPP" | "SMS" | null; results: OutreachEntry[] }>(`${path}?${query}`),
  });
  const send = useMutation({
    mutationFn: () => adminFetch(path, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "The introduction could not be sent."),
  });
  if (!data || (!data.intro_channel && data.results.length === 0)) return null;
  const alreadyIntroduced = data.results.some((o) => INTRODUCED.includes(o.status));

  return (
    <div className="rounded-md border border-border p-3 space-y-2 text-sm" aria-label="Ask first">
      <p className="font-medium">Ask first (introduction)</p>
      {data.results.length === 0 && (
        <p className="text-xs text-text-muted">
          Sends a short message about the study asking whether they will take part
          {data.intro_channel === "SMS" ? " (by SMS, with a link to answer on WhatsApp)" : " on WhatsApp"}. If they reply
          YES, the portal sends their personal {kii ? "interview link" : "invitation link"} automatically; NO records the
          refusal ({kii ? "Declined" : "S12"}).
        </p>
      )}
      {data.results.map((o) => (
        <div key={o.id} className="space-y-1">
          <p>
            <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">{o.status_label}</span>{" "}
            <span className="text-xs text-text-muted">
              {o.channel === "SMS" ? "SMS" : "WhatsApp"} to {o.number}, {new Date(o.intro_sent_at).toLocaleDateString()}
              {o.reminded_at ? ` · reminded ${new Date(o.reminded_at).toLocaleDateString()}` : ""}
              {o.sms_fallback_sent ? " · re-sent by SMS" : ""}
            </span>
          </p>
          {o.messages.map((m, i) => (
            <p key={i} className="text-xs border-l-2 border-border pl-2 whitespace-pre-wrap break-words">
              <span className="text-text-muted">{new Date(m.received_at).toLocaleString()}:</span> {m.body || "(no text)"}
              {m.auto_reply ? <span className="block text-text-muted">Automatic reply: {m.auto_reply}</span> : null}
            </p>
          ))}
        </div>
      ))}
      {error && <p className="text-danger text-xs">{error}</p>}
      {data.intro_channel && !alreadyIntroduced && (
        <WriteOnly note={null}>
          <Button variant="outline" onClick={() => send.mutate()} disabled={send.isPending}>
            {send.isPending ? "Sending…" : "Send introduction"}
          </Button>
        </WriteOnly>
      )}
    </div>
  );
}
