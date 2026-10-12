"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { adminFetch } from "@/lib/api/admin";
import { fullTime, type UnknownMessage } from "@/lib/api/communications";

/**
 * WhatsApp messages from numbers that are on no case or KII record (PI and Field Coordinator only). Answered from
 * here within WhatsApp's 24 hours, through the existing conversation endpoints.
 */
export function UnknownSenders() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["communications", "unknown"],
    queryFn: () => adminFetch<{ results: UnknownMessage[] }>("/communications/unknown/"),
    refetchInterval: 15000,
  });
  const refresh = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["communications"] });
  };
  const reply = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) =>
      adminFetch(`/conversations/${id}/reply/`, { method: "POST", body: JSON.stringify({ text }) }),
    onSuccess: (_d, { id }) => {
      setDrafts((d) => ({ ...d, [id]: "" }));
      refresh();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The reply could not be sent."),
  });
  const handled = useMutation({
    mutationFn: (id: number) => adminFetch(`/conversations/${id}/handled/`, { method: "POST", body: "{}" }),
    onSuccess: refresh,
    onError: (err) => setError(err instanceof Error ? err.message : "Could not mark it handled."),
  });
  const items = data?.results ?? [];

  return (
    <div className="space-y-3 p-4">
      <div>
        <h3 className="font-semibold">Numbers not on any record</h3>
        <p className="text-xs text-text-muted">
          If one of these is a respondent, add the number to their case first: their messages then appear in that conversation.
        </p>
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {isLoading && <p className="text-sm text-text-muted">Loading…</p>}
      {!isLoading && items.length === 0 && <p className="text-sm text-text-muted">No messages from unknown numbers.</p>}
      {items.map((m) => (
        <article key={m.message_id} className={`space-y-2 rounded-lg border bg-surface p-3 ${m.waiting ? "border-header" : "border-border"}`}>
          <p className="text-xs text-text-muted">
            {m.from} · {fullTime(m.at)}
            {!m.waiting && m.handled_by && ` · handled by ${m.handled_by}`}
          </p>
          <p className="whitespace-pre-wrap break-words text-sm">{m.body || "(no text)"}</p>
          <WriteOnly note={null}>
            {m.can_reply ? (
              <div className="space-y-2">
                <textarea
                  aria-label="Reply"
                  rows={2}
                  value={drafts[m.message_id] ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [m.message_id]: e.target.value }))}
                  className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
                  placeholder="Reply on WhatsApp…"
                />
                <div className="flex gap-2">
                  <Button className="min-h-9 py-1.5" disabled={reply.isPending || !(drafts[m.message_id] ?? "").trim()}
                    onClick={() => reply.mutate({ id: m.message_id, text: drafts[m.message_id] ?? "" })}>
                    Send reply
                  </Button>
                  {m.waiting && (
                    <Button variant="outline" className="min-h-9 py-1.5" disabled={handled.isPending} onClick={() => handled.mutate(m.message_id)}>
                      Mark handled
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              m.waiting && (
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs text-text-muted">More than 24 hours ago, so WhatsApp won&apos;t take a reply.</p>
                  <Button variant="outline" className="min-h-9 py-1.5" disabled={handled.isPending} onClick={() => handled.mutate(m.message_id)}>
                    Mark handled
                  </Button>
                </div>
              )
            )}
          </WriteOnly>
        </article>
      ))}
    </div>
  );
}
