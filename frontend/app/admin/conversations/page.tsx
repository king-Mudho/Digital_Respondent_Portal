"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface Conversation {
  id: number;
  received_at: string;
  from: string;
  body: string;
  kind: "YES" | "NO" | "OTHER";
  auto_reply: string;
  needs_person: boolean;
  handled_by: string;
  handled_at: string | null;
  sample_id: string;
  organisation_name: string;
  outreach_status: string;
  can_reply: boolean;
}

const KIND_LABEL: Record<Conversation["kind"], string> = { YES: "Said yes", NO: "Said no", OTHER: "Message" };

/**
 * WhatsApp messages people sent to the study's Twilio number (backend apps/messaging/outreach.py). YES and NO replies
 * to an introduction are acted on automatically; everything else -- questions, other words, unknown numbers -- waits
 * here for a person. The study's Twilio number is on no phone, so replies are written here, and WhatsApp allows them
 * only within 24 hours of the person's own last message.
 */
export default function ConversationsPage() {
  const queryClient = useQueryClient();
  const [show, setShow] = useState<"open" | "all">("open");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["conversations", show],
    queryFn: () => adminFetch<{ results: Conversation[] }>(`/conversations/?show=${show}`),
    refetchInterval: 30000,
  });
  const done = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };
  const handled = useMutation({
    mutationFn: (id: number) => adminFetch(`/conversations/${id}/handled/`, { method: "POST", body: "{}" }),
    onSuccess: done,
    onError: (err) => setError(err instanceof Error ? err.message : "Could not mark it handled."),
  });
  const reply = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) =>
      adminFetch(`/conversations/${id}/reply/`, { method: "POST", body: JSON.stringify({ text }) }),
    onSuccess: (_data, { id }) => {
      setDrafts((d) => ({ ...d, [id]: "" }));
      done();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The reply could not be sent."),
  });
  const items = data?.results ?? [];

  return (
    <AdminShell backHref="/admin/follow-ups" backLabel="Follow-ups">
      <h2 className="font-semibold text-xl mb-1">Conversations</h2>
      <p className="text-text-muted text-sm mb-3">
        WhatsApp messages sent to the study&apos;s number. Yes and no replies to an introduction are handled
        automatically; these need a person. Reply here (within 24 hours of their message), or phone them.
      </p>
      <div className="flex gap-2 mb-4" role="tablist" aria-label="Show">
        {(["open", "all"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={show === key}
            onClick={() => setShow(key)}
            className={`rounded-md border px-3 py-1 text-xs ${show === key ? "border-header bg-header text-white" : "border-border bg-surface"}`}
          >
            {key === "open" ? "Waiting for a person" : "All messages"}
          </button>
        ))}
      </div>
      {error && <p className="text-danger text-sm mb-3">{error}</p>}
      {isLoading ? (
        <p className="text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">{show === "open" ? "Nothing is waiting for a person." : "No messages yet."}</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((m) => (
            <article key={m.id} aria-label={`Message from ${m.from}`}>
              <Card className="space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    {m.sample_id ? (
                      <>
                        <Link href={`/admin/sample/${m.sample_id}`} className="font-mono text-sm underline">{m.sample_id}</Link>
                        <span className="text-sm"> · {m.organisation_name}</span>
                      </>
                    ) : (
                      <span className="text-sm">A number the study has no record of</span>
                    )}
                    <p className="text-xs text-text-muted">
                      {m.from} · {new Date(m.received_at).toLocaleString()}
                      {m.outreach_status ? ` · introduction: ${m.outreach_status}` : ""}
                    </p>
                  </div>
                  <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">{KIND_LABEL[m.kind]}</span>
                </div>
                <p className="rounded-md bg-bg border border-border p-2 text-sm whitespace-pre-wrap break-words">{m.body || "(no text)"}</p>
                {m.auto_reply && <p className="text-xs text-text-muted whitespace-pre-wrap">Automatic reply: {m.auto_reply}</p>}
                {m.handled_at && (
                  <p className="text-xs text-text-muted">Handled by {m.handled_by} on {new Date(m.handled_at).toLocaleString()}</p>
                )}
                <WriteOnly note={null}>
                  {m.can_reply ? (
                    <div className="space-y-2">
                      <textarea
                        aria-label="Reply"
                        value={drafts[m.id] ?? ""}
                        onChange={(e) => setDrafts((d) => ({ ...d, [m.id]: e.target.value }))}
                        rows={2}
                        className="w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
                        placeholder="Write a reply on WhatsApp…"
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button
                          onClick={() => reply.mutate({ id: m.id, text: drafts[m.id] ?? "" })}
                          disabled={reply.isPending || !(drafts[m.id] ?? "").trim()}
                        >
                          Send reply
                        </Button>
                        {!m.handled_at && (
                          <Button variant="outline" onClick={() => handled.mutate(m.id)} disabled={handled.isPending}>
                            Mark handled
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-xs text-text-muted">
                        More than 24 hours since their last message, so WhatsApp won&apos;t take a reply. Phone them instead.
                      </p>
                      {!m.handled_at && (
                        <Button variant="outline" onClick={() => handled.mutate(m.id)} disabled={handled.isPending}>
                          Mark handled
                        </Button>
                      )}
                    </div>
                  )}
                </WriteOnly>
              </Card>
            </article>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
