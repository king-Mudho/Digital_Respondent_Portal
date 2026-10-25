"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfScreen, WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

type Stage = "started" | "consented" | "opened" | "not_opened";

interface Person {
  name: string;
  role: string;
  email: string;
  gatekeeper: string;
  numbers: { number: string; whatsapp_link: string }[];
}

interface LastCall {
  at: string;
  outcome: string;
  outcome_label: string;
  notes: string;
  by: string;
  next_action_date: string | null;
}

interface CallItem {
  kind: "main" | "kii";
  id: string;
  study: string;
  organisation: string;
  location: string;
  sector: string;
  stage: Stage;
  stage_label: string;
  link_sent: string | null;
  link_opened: string | null;
  link_expires: string | null;
  link_channel: string;
  people: Person[];
  public_contacts: string;
  reminders: number;
  calls: number;
  last_call: LastCall | null;
  detail_path: string;
}

interface CallList {
  results: CallItem[];
  count: number;
  stage_counts: Record<Stage, number>;
  stage_labels: Record<Stage, string>;
  studies: ("main" | "kii")[];
  outcomes: { value: string; label: string }[];
}

const STAGES: Stage[] = ["started", "consented", "opened", "not_opened"];
const STAGE_STYLE: Record<Stage, string> = {
  started: "bg-success text-white",
  consented: "bg-header text-white",
  opened: "bg-accent text-white",
  not_opened: "bg-bg border border-border",
};

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : "");

/**
 * Calls (2026-10-25): everyone whose link was sent but who has not finished -- Main 400 (with activated reserves)
 * and KII -- closest to finishing first, with every contact on file and a call log. Which people a role sees is
 * decided by the API (a Contact RA their assigned cases, a KII RA the KII records); this page shows what it gets.
 */
export default function CallsPage() {
  const [study, setStudy] = useState<"all" | "main" | "kii">("all");
  const [stage, setStage] = useState<Stage | "all">("all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["calls", study, stage, search],
    queryFn: () =>
      adminFetch<CallList>(`/calls/?${new URLSearchParams({ study, stage, q: search }).toString()}`),
  });
  const items = data?.results ?? [];
  const total = data ? STAGES.reduce((n, s) => n + (data.stage_counts[s] ?? 0), 0) : 0;

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-1">Calls</h2>
      <p className="text-text-muted text-sm mb-4">
        Everyone whose link was sent but who hasn&apos;t finished, closest to finishing first. Call, then log what
        happened. Never read out or change anyone&apos;s answers, and never describe the study as a loan, an approval,
        a credit rating or a guarantee.
      </p>

      <Card className="space-y-3 mb-4">
        {data && data.studies.length > 1 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Study">
            {(["all", "main", "kii"] as const).map((s) => (
              <Button key={s} variant={study === s ? "primary" : "outline"} onClick={() => setStudy(s)} aria-pressed={study === s}>
                {s === "all" ? "Main 400 and KII" : s === "main" ? "Main 400" : "KII"}
              </Button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2" role="group" aria-label="How far they got">
          <Button variant={stage === "all" ? "primary" : "outline"} onClick={() => setStage("all")} aria-pressed={stage === "all"}>
            All ({total})
          </Button>
          {STAGES.map((s) => (
            <Button key={s} variant={stage === s ? "primary" : "outline"} onClick={() => setStage(s)} aria-pressed={stage === s}>
              {data?.stage_labels[s] ?? s} ({data?.stage_counts[s] ?? 0})
            </Button>
          ))}
        </div>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q);
          }}
        >
          <label className="sr-only" htmlFor="calls-search">Search</label>
          <input
            id="calls-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Organisation, name, ID or phone number"
            className="min-h-11 flex-1 min-w-56 rounded-md border border-border bg-bg px-3 text-sm"
          />
          <Button type="submit" variant="outline">Search</Button>
          {search && (
            <Button type="button" variant="outline" onClick={() => { setQ(""); setSearch(""); }}>
              Clear
            </Button>
          )}
        </form>
      </Card>

      {error ? (
        <p className="text-danger text-sm">{error instanceof Error ? error.message : "The call list could not be loaded."}</p>
      ) : isLoading ? (
        <p className="text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-text-muted text-sm">Nobody to call here{search ? " for that search" : ""}.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-text-muted">{items.length} to call</p>
          {items.map((item) => (
            <CallCard key={`${item.kind}-${item.id}`} item={item} outcomes={data?.outcomes ?? []} />
          ))}
        </div>
      )}
    </AdminShell>
  );
}

function CallCard({ item, outcomes }: { item: CallItem; outcomes: { value: string; label: string }[] }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [callBack, setCallBack] = useState("");
  const [error, setError] = useState<string | null>(null);
  const expired = item.link_expires ? new Date(item.link_expires) < new Date() : false;

  const log = useMutation({
    mutationFn: () =>
      adminFetch(`/calls/${item.kind}/${item.id}/`, {
        method: "POST",
        body: JSON.stringify({ outcome, notes, next_action_date: callBack || null }),
      }),
    onSuccess: () => {
      setError(null);
      setOpen(false);
      setOutcome("");
      setNotes("");
      setCallBack("");
      queryClient.invalidateQueries({ queryKey: ["calls"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The call could not be logged."),
  });

  return (
    <article aria-label={`Call ${item.id}`}>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm">
              <IfScreen path={item.detail_path}>
                <Link href={item.detail_path} className="font-mono underline mr-2">{item.id}</Link>
              </IfScreen>
              <span className="text-text-muted">{item.study}</span>
            </p>
            <p className="font-semibold">{item.organisation}</p>
            <p className="text-xs text-text-muted">{[item.sector, item.location].filter(Boolean).join(" · ")}</p>
          </div>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STAGE_STYLE[item.stage]}`}>{item.stage_label}</span>
        </div>

        <div className="space-y-2">
          {item.people.length === 0 && <p className="text-sm text-danger">No contact person on file.</p>}
          {item.people.map((p, i) => (
            <div key={i} className="rounded-md border border-border bg-bg p-2 text-sm">
              <p className="font-medium">
                {p.name || "Contact not named"}
                {p.role && <span className="font-normal text-text-muted"> · {p.role}</span>}
              </p>
              {p.numbers.length === 0 && !p.email && <p className="text-xs text-danger">No phone number or email on file.</p>}
              <ul className="flex flex-wrap gap-2 mt-1">
                {p.numbers.map((n) => (
                  <li key={n.number} className="flex flex-wrap items-center gap-2">
                    <a href={`tel:${n.number.replace(/[^\d+]/g, "")}`} className="inline-flex min-h-11 items-center rounded-md border border-border px-3 font-mono underline">
                      Call {n.number}
                    </a>
                    {n.whatsapp_link && (
                      <a href={n.whatsapp_link} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center rounded-md border border-border px-3">
                        WhatsApp
                      </a>
                    )}
                  </li>
                ))}
              </ul>
              {p.email && (
                <p className="mt-1 text-xs">
                  Email: <a href={`mailto:${p.email}`} className="underline">{p.email}</a>
                </p>
              )}
              {p.gatekeeper && <p className="text-xs">Gatekeeper: {p.gatekeeper}</p>}
            </div>
          ))}
          {item.public_contacts && <p className="text-xs text-text-muted">Other public contacts: {item.public_contacts}</p>}
        </div>

        <p className="text-xs text-text-muted">
          Link sent {day(item.link_sent)} by {item.link_channel}
          {item.link_opened ? ` · opened ${day(item.link_opened)}` : " · not opened yet"}
          {item.link_expires ? ` · ${expired ? "expired" : "works until"} ${day(item.link_expires)}` : ""}
          {` · ${item.reminders} reminder${item.reminders === 1 ? "" : "s"} · ${item.calls} call${item.calls === 1 ? "" : "s"} logged`}
        </p>
        {expired && (
          <p className="text-xs text-danger">This link has expired: issue a new one from the {item.kind === "main" ? "case" : "KII record"} page before asking them to continue.</p>
        )}
        {item.last_call && (
          <p className="text-xs">
            Last call {day(item.last_call.at)} by {item.last_call.by}: <strong>{item.last_call.outcome_label}</strong>
            {item.last_call.next_action_date ? ` · call back ${day(item.last_call.next_action_date)}` : ""}
            {item.last_call.notes ? ` · “${item.last_call.notes}”` : ""}
          </p>
        )}

        <WriteOnly note={null}>
          {open ? (
            <form
              className="space-y-2 rounded-md border border-border p-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (!outcome) {
                  setError("Choose what happened on the call.");
                  return;
                }
                log.mutate();
              }}
            >
              <label className="block text-sm">
                What happened
                <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className="mt-1 block min-h-11 w-full rounded-md border border-border bg-bg px-2">
                  <option value="">Choose…</option>
                  {outcomes.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Notes
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="mt-1 block w-full rounded-md border border-border bg-bg px-2 py-1" placeholder="e.g. Will finish tonight; asked for the link again" />
              </label>
              <label className="block text-sm">
                Call back on (optional)
                <input type="date" value={callBack} onChange={(e) => setCallBack(e.target.value)} className="mt-1 block min-h-11 rounded-md border border-border bg-bg px-2" />
              </label>
              {outcome === "REFUSED" && (
                <p className="text-xs">A refusal is noted on the call only. To close the case as Refused, use its page.</p>
              )}
              {error && <p className="text-danger text-sm">{error}</p>}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={log.isPending}>{log.isPending ? "Saving…" : "Save call"}</Button>
                <Button type="button" variant="outline" onClick={() => { setOpen(false); setError(null); }}>Cancel</Button>
              </div>
            </form>
          ) : (
            <Button variant="outline" onClick={() => setOpen(true)}>Log a call</Button>
          )}
        </WriteOnly>
      </Card>
    </article>
  );
}
