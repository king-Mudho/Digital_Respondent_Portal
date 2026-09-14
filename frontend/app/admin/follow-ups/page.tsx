"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface FollowUp {
  sample_id: string;
  organisation_name: string;
  workflow_status: string;
  invited_on: string;
  step_day: number;
  step_label: string;
  template: string;
  message: string;
  respondent_name: string;
  phone: string;
  whatsapp_link: string;
}

/**
 * Reminders that are due and not yet sent. Until the WhatsApp Business
 * Platform is connected nothing is sent automatically, so this is where the
 * approved Day 2 / Day 7 reminders actually go out: open WhatsApp with the
 * approved text, send it, then mark it sent. Marking it sent is what counts
 * the reminder toward the sequence -- a case only becomes Nonresponse once
 * every reminder has been sent.
 */
export default function FollowUpsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["follow-ups"],
    queryFn: () => adminFetch<{ results: FollowUp[] }>("/follow-ups/"),
  });

  const markSent = useMutation({
    mutationFn: (item: FollowUp) =>
      adminFetch("/follow-ups/mark-sent/", {
        method: "POST",
        body: JSON.stringify({ sample_id: item.sample_id, template: item.template }),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not record the reminder."),
  });

  const items = data?.results ?? [];

  return (
    <AdminShell backHref="/admin/sample" backLabel="Main-400 Register">
      <h2 className="font-semibold text-xl mb-1">Follow-ups due</h2>
      <p className="text-text-muted text-sm mb-4">
        Approved reminders for invited cases that haven&apos;t responded yet. Open WhatsApp, send the
        message, then mark it sent.
      </p>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {isLoading ? (
        <p className="text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">No reminders are due.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <article key={`${item.sample_id}-${item.template}`} aria-label={`Follow-up for ${item.sample_id}`}>
            <Card className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <Link href={`/admin/sample/${item.sample_id}`} className="font-mono text-sm underline">
                    {item.sample_id}
                  </Link>
                  <p className="text-sm">{item.organisation_name}</p>
                  <p className="text-xs text-text-muted">
                    {item.step_label} · invited {new Date(item.invited_on).toLocaleDateString()}
                    {item.respondent_name ? ` · ${item.respondent_name}` : ""}
                    {item.phone ? ` · ${item.phone}` : " · no number on file"}
                  </p>
                </div>
                <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                  {item.workflow_status}
                </span>
              </div>
              <p className="rounded-md bg-bg border border-border p-2 text-sm">{item.message}</p>
              <WriteOnly note={null}>
                <div className="flex flex-wrap gap-2">
                  <a
                    href={item.whatsapp_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm"
                  >
                    {item.phone ? "Open in WhatsApp" : "Open WhatsApp (choose contact)"}
                  </a>
                  <Button onClick={() => markSent.mutate(item)} disabled={markSent.isPending}>
                    Mark as sent
                  </Button>
                </div>
              </WriteOnly>
            </Card>
            </article>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
