"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface BriefInfo {
  documents: { id: number; title: string; file_name: string; blocked_phrase: string }[];
  problem: string;
  whatsapp_to: string;
  whatsapp_to_name: string;
  whatsapp_window_open: boolean;
  whatsapp_configured: boolean;
  email_to: string;
  email_configured: boolean;
  by_hand_link: string;
  message: string;
}

export type BriefTarget = { kind: "main" | "kii"; id: string };

/**
 * "Send study information" (backend apps/clearance/brief.py, 19 Nov 2026): the documents the PI marked on Research
 * Clearance go to someone who asked to read about the study first -- from the study's WhatsApp number (only within 24
 * hours of their own last message), by email with the documents attached, or from the research assistant's own
 * WhatsApp with a link, which is then recorded. Every failure says why, so a button never just does nothing.
 */
export function StudyBriefPanel({ target, compact = false }: { target: BriefTarget; compact?: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(!compact);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const key = ["study-brief", target.kind, target.id];
  const { data, isError } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<BriefInfo>(`/study-brief/?kind=${target.kind}&id=${encodeURIComponent(target.id)}`),
    enabled: open,
  });
  const send = useMutation({
    mutationFn: (channel: "WHATSAPP" | "EMAIL") =>
      adminFetch<{ sent_to: string }>("/study-brief/", {
        method: "POST",
        body: JSON.stringify({ kind: target.kind, id: target.id, channel }),
      }),
    onSuccess: (res, channel) => {
      setError(null);
      setDone(`Sent ${channel === "EMAIL" ? "by email" : "on WhatsApp"} to ${res.sent_to}.`);
      queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (err) => {
      setDone(null);
      setError(err instanceof ApiError ? err.message : "The documents could not be sent.");
    },
  });
  const byHand = useMutation({
    mutationFn: () =>
      adminFetch("/study-brief/sent-by-hand/", { method: "POST", body: JSON.stringify({ kind: target.kind, id: target.id }) }),
    onSuccess: () => {
      setError(null);
      setDone("Recorded: you sent the study information from your phone.");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "The portal could not record that. Log it as a call note."),
  });

  if (compact && !open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Send study information
      </Button>
    );
  }

  return (
    <div className="rounded-md border border-border p-3 space-y-2 text-sm" aria-label="Send study information">
      <p className="font-medium">Send study information</p>
      <p className="text-xs text-text-muted">
        For someone who asks to read about the study before taking part. It does not replace consent: that is still asked
        on their link.
      </p>
      {isError && <p className="text-danger text-xs">The study information could not be loaded.</p>}
      {!data ? (
        !isError && <p className="text-xs text-text-muted">Loading…</p>
      ) : (
        <>
          {data.documents.length > 0 && (
            <ul className="list-disc pl-5 text-xs">
              {data.documents.map((d) => (
                <li key={d.id}>{d.title}</li>
              ))}
            </ul>
          )}
          {data.problem ? (
            <p className="text-danger text-xs">{data.problem}</p>
          ) : (
            <WriteOnly note={null}>
              <div className="flex flex-wrap gap-2">
                {data.whatsapp_to && data.whatsapp_configured && (
                  <Button
                    variant="outline"
                    disabled={send.isPending || !data.whatsapp_window_open}
                    onClick={() => send.mutate("WHATSAPP")}
                    title={data.whatsapp_window_open ? "" : "Only within 24 hours of their own last WhatsApp message"}
                  >
                    WhatsApp from the study number
                  </Button>
                )}
                {data.email_to && data.email_configured && (
                  <Button variant="outline" disabled={send.isPending} onClick={() => send.mutate("EMAIL")}>
                    Email ({data.email_to})
                  </Button>
                )}
                {data.by_hand_link && (
                  <a
                    href={data.by_hand_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => byHand.mutate()}
                    className="inline-flex min-h-11 items-center rounded-md border border-border px-3"
                  >
                    Send from my phone (WhatsApp)
                  </a>
                )}
              </div>
              {data.whatsapp_to && data.whatsapp_configured && !data.whatsapp_window_open && (
                <p className="text-xs text-text-muted">
                  The study number can write to them only within 24 hours of their own last WhatsApp message. Use Send from
                  my phone instead.
                </p>
              )}
              {!data.whatsapp_to && !data.email_to && (
                <p className="text-xs text-text-muted">No WhatsApp number or email is on file. Add one under contact details.</p>
              )}
            </WriteOnly>
          )}
        </>
      )}
      {done && <p className="text-xs text-success" role="status">{done}</p>}
      {error && <p className="text-danger text-xs" role="alert">{error}</p>}
    </div>
  );
}
