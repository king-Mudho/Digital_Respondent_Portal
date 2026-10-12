"use client";

import { Suspense, useDeferredValue, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AdminShell } from "@/components/admin/AdminShell";
import { ChannelHealth } from "@/components/admin/communications/ChannelHealth";
import { Composer, type Draft } from "@/components/admin/communications/Composer";
import { ContactCard } from "@/components/admin/communications/ContactCard";
import { ThreadList, type ListFilters } from "@/components/admin/communications/ThreadList";
import { Timeline } from "@/components/admin/communications/Timeline";
import { UnknownSenders } from "@/components/admin/communications/UnknownSenders";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { adminFetch } from "@/lib/api/admin";
import { parseThreadKey, type Summary, type ThreadData, type ThreadPage } from "@/lib/api/communications";
import { useAdminUser } from "@/lib/auth/session";

/**
 * Communications (backend apps/messaging/communications.py, 2026-10-12): every message to and from participants on
 * WhatsApp, SMS and email in one place, with what happened to each one, and the events around them (invitations,
 * the link opened, consent, the questionnaire submitted). Replaced the WhatsApp-only Conversations screen.
 *
 * Which conversations a role sees is decided by the backend: a Contact RA gets their own Main-400 cases, a KII RA
 * the KII records, the Supervisor reads everything.
 */
export default function CommunicationsPage() {
  return (
    <AdminShell>
      <Suspense fallback={<p className="text-text-muted">Loading…</p>}>
        <Communications />
      </Suspense>
    </AdminShell>
  );
}

const SEE_UNKNOWN = ["PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"];

function Communications() {
  const user = useAdminUser();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const selectedKey = params.get("t");
  const selected = parseThreadKey(selectedKey);
  const unknownOpen = selectedKey === "unknown";
  const [filters, setFilters] = useState<ListFilters>({ show: "all", register: "", channel: "", q: "", page: 1 });
  const q = useDeferredValue(filters.q);
  const [sendError, setSendError] = useState<string | null>(null);

  const select = (key: string | null) => {
    setSendError(null);
    router.replace(key ? `${pathname}?t=${key}` : pathname, { scroll: false });
  };

  const summary = useQuery({
    queryKey: ["communications", "summary"],
    queryFn: () => adminFetch<Summary>("/communications/summary/"),
    refetchInterval: 60000,
  });
  const listQuery = new URLSearchParams({
    show: filters.show, register: filters.register, channel: filters.channel, q, page: String(filters.page),
  });
  const list = useQuery({
    queryKey: ["communications", "threads", listQuery.toString()],
    queryFn: () => adminFetch<ThreadPage>(`/communications/threads/?${listQuery}`),
    refetchInterval: 15000,
    placeholderData: (previous) => previous,
  });
  const thread = useQuery({
    queryKey: ["communications", "thread", selectedKey],
    queryFn: () => adminFetch<ThreadData>(`/communications/threads/${selected!.kind}/${selected!.id}/`),
    enabled: !!selected,
    refetchInterval: 10000,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["communications"] });
  const send = useMutation({
    mutationFn: (draft: Draft) =>
      adminFetch(`/communications/threads/${selected!.kind}/${selected!.id}/send/`, {
        method: "POST",
        body: JSON.stringify({ channel: draft.channel, recipient: draft.recipient, subject: draft.subject, text: draft.text }),
      }),
    onSuccess: () => {
      setSendError(null);
      refresh();
    },
    onError: (err) => setSendError(err instanceof Error ? err.message : "The message was not sent."),
  });
  const handled = useMutation({
    mutationFn: () => adminFetch(`/communications/threads/${selected!.kind}/${selected!.id}/handled/`, { method: "POST", body: "{}" }),
    onSuccess: refresh,
    onError: (err) => setSendError(err instanceof Error ? err.message : "Could not mark it handled."),
  });
  const introduce = useMutation({
    mutationFn: () => adminFetch("/outreach/", { method: "POST", body: JSON.stringify({ sample_id: thread.data?.subject.ref }) }),
    onSuccess: () => {
      setSendError(null);
      refresh();
    },
    onError: (err) => setSendError(err instanceof Error ? err.message : "The introduction was not sent."),
  });

  const waitingHere = thread.data?.items.some((i) => i.type === "in" && i.waiting) ?? false;
  const paneOpen = !!selected || unknownOpen;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold">Communications</h2>
          <p className="text-sm text-text-muted">
            Every message to and from participants on WhatsApp, SMS and email, and what happened to it.
            {summary.data && summary.data.waiting > 0 && (
              <>
                {" "}
                <button type="button" className="font-medium text-header underline" onClick={() => setFilters((f) => ({ ...f, show: "waiting", page: 1 }))}>
                  {summary.data.waiting} waiting for an answer
                </button>
              </>
            )}
          </p>
        </div>
      </div>

      {/* On a phone the open conversation comes first; the channel cards return with the list. */}
      <div className={paneOpen ? "hidden md:block" : ""}>
        <ChannelHealth summary={summary.data} onShowFailed={() => setFilters((f) => ({ ...f, show: "failed", page: 1 }))} />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] overflow-hidden rounded-lg border border-border bg-surface lg:h-[calc(100vh-200px)] lg:min-h-[600px] lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)_280px]">
        <aside className={`min-h-0 border-border lg:border-r ${paneOpen ? "hidden lg:block" : ""}`} aria-label="Conversation list">
          <div className="h-[70vh] lg:h-full">
            <ThreadList
              data={list.data}
              loading={list.isLoading}
              filters={filters}
              onFilters={(next) => setFilters((f) => ({ ...f, ...next }))}
              selected={selectedKey}
              onSelect={select}
              showUnknown={SEE_UNKNOWN.includes(user?.role ?? "")}
              unknownSelected={unknownOpen}
              onSelectUnknown={() => select("unknown")}
            />
          </div>
        </aside>

        <section className={`flex min-h-0 flex-col ${paneOpen ? "" : "hidden lg:flex"}`} aria-label="Conversation">
          {unknownOpen ? (
            <div className="min-h-0 flex-1 overflow-y-auto" data-scroll-pane>
              <BackToList onBack={() => select(null)} />
              <UnknownSenders />
            </div>
          ) : !selected ? (
            <div className="flex flex-1 items-center justify-center p-8 text-center">
              <div className="max-w-sm space-y-1">
                <p className="font-medium">Choose a conversation</p>
                <p className="text-sm text-text-muted">
                  Conversations with someone waiting for an answer are listed first. Delivery ticks show what reached the phone.
                </p>
              </div>
            </div>
          ) : thread.isError ? (
            <div className="p-6">
              <BackToList onBack={() => select(null)} />
              <p role="alert" className="text-sm text-danger">
                {thread.error instanceof Error ? thread.error.message : "This conversation could not be opened."}
              </p>
            </div>
          ) : !thread.data ? (
            <p className="p-6 text-sm text-text-muted">Loading the conversation…</p>
          ) : (
            <>
              <header className="flex items-center gap-3 border-b border-border px-4 py-3">
                <button type="button" onClick={() => select(null)} className="rounded p-1 text-text-muted hover:bg-bg lg:hidden" aria-label="Back to the list">
                  ←
                </button>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-semibold">{thread.data.subject.organisation}</h3>
                  <p className="truncate text-xs text-text-muted">
                    <span className="font-mono">{thread.data.subject.ref}</span>
                    {thread.data.subject.person && ` · ${thread.data.subject.person}`}
                    {thread.data.subject.status && ` · ${thread.data.subject.status}`}
                  </p>
                </div>
                {waitingHere && (
                  <WriteOnly note={null}>
                    <Button variant="outline" className="min-h-9 py-1.5" onClick={() => handled.mutate()} disabled={handled.isPending}>
                      Mark handled
                    </Button>
                  </WriteOnly>
                )}
              </header>
              <div className="min-h-[50vh] flex-1 overflow-y-auto bg-bg lg:min-h-0" data-scroll-pane>
                <Timeline items={thread.data.items} />
              </div>
              <WriteOnly note={null}>
                {thread.data.composer.can_write && (
                  <Composer
                    key={selectedKey}
                    composer={thread.data.composer}
                    sending={send.isPending}
                    error={sendError}
                    onSend={(draft) => send.mutateAsync(draft).then(() => true, () => false)}
                    onAction={() => introduce.mutate()}
                    actionBusy={introduce.isPending}
                  />
                )}
              </WriteOnly>
              <details className="border-t border-border xl:hidden">
                <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-text-muted">Contact details</summary>
                <ContactCard card={thread.data.subject} />
              </details>
            </>
          )}
        </section>

        <aside className="hidden min-h-0 overflow-y-auto border-l border-border xl:block" aria-label="Contact details">
          {selected && thread.data ? (
            <ContactCard card={thread.data.subject} />
          ) : (
            <p className="p-4 text-xs text-text-muted">The people and contact details of the open conversation appear here.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function BackToList({ onBack }: { onBack: () => void }) {
  return (
    <button type="button" onClick={onBack} className="m-3 mb-0 text-sm text-text-muted hover:text-text lg:hidden">
      ← All conversations
    </button>
  );
}
