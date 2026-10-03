"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ROLE_OPTIONS } from "@/components/admin/RespondentsPanel";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

interface Source {
  title: string;
  url: string;
  quote: string;
}

interface Proposal {
  id: number;
  kind: "ORG_PHONE" | "ORG_EMAIL" | "WEBSITE" | "OFFICE_LOCATION" | "PERSON";
  kind_label: string;
  value: string;
  person_name: string;
  person_title: string;
  person_email: string;
  person_phone: string;
  sources: Source[];
  confidence: string;
  flags: string[];
  status: "PROPOSED" | "ACCEPTED" | "REJECTED";
}

interface Run {
  id: number;
  status: "RUNNING" | "DONE" | "FAILED";
  searches_used: number;
  summary: string;
  error: string;
  dropped: { reason: string }[];
}

interface FinderState {
  configured: boolean;
  run: Run | null;
  proposals: Proposal[];
  public_contacts: Record<string, { value: string; source: string }>;
}

function describe(p: Proposal) {
  if (p.kind !== "PERSON") return p.value;
  return [`${p.person_name}, ${p.person_title}`, p.person_email, p.person_phone].filter(Boolean).join(" · ");
}

/**
 * AI finds the organisation's PUBLISHED contact details (backend/apps/contacts/contact_finder.py). Every finding
 * carries the page it came from and the passage that shows it; nothing is saved until the PI or Field Coordinator
 * accepts it. Organisation phone/email go to the "Organisation contact (to be identified)" respondent; a named
 * person becomes a new respondent.
 */
export function ContactFinderPanel({ sampleId, invitable }: { sampleId: string; invitable: boolean }) {
  const queryClient = useQueryClient();
  const key = ["contact-search", sampleId];
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Record<number, string>>({});

  const { data } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<FinderState>(`/contacts/${sampleId}/contact-search/`),
    // The search runs for a minute or two in the background; keep checking until it stops.
    refetchInterval: (query) => (query.state.data?.run?.status === "RUNNING" ? 4000 : false),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
    queryClient.invalidateQueries({ queryKey: ["respondents", sampleId] });
  };
  const failed = (fallback: string) => (err: unknown) => setError(err instanceof ApiError ? err.message : fallback);

  const start = useMutation({
    mutationFn: () => adminFetch<Run>(`/contacts/${sampleId}/contact-search/`, { method: "POST" }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: key });
    },
    onError: failed("Could not start the search."),
  });
  const accept = useMutation({
    mutationFn: (p: Proposal) =>
      adminFetch(`/contacts/contact-proposals/${p.id}/accept/`, {
        method: "POST",
        body: JSON.stringify(p.kind === "PERSON" ? { role_category: roles[p.id] ?? "" } : {}),
      }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: failed("Could not accept that detail."),
  });
  const reject = useMutation({
    mutationFn: (p: Proposal) =>
      adminFetch(`/contacts/contact-proposals/${p.id}/reject/`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: failed("Could not reject that detail."),
  });

  if (!data) return null;
  const running = data.run?.status === "RUNNING";
  const pending = data.proposals.filter((p) => p.status === "PROPOSED");
  const decided = data.proposals.filter((p) => p.status !== "PROPOSED");
  const publicContacts = Object.entries(data.public_contacts ?? {});

  return (
    <Card className="space-y-3" aria-label="Find contact details">
      <div className="space-y-1">
        <h3 className="font-semibold">Find contact details with AI</h3>
        <p className="text-xs text-text-muted">
          Searches public sources for this organisation&rsquo;s published phone, email, website and office location, and
          senior staff the organisation itself names. Every detail comes with the page it was found on and the passage
          that shows it. Nothing is saved until you accept it: an organisation phone or email goes to &ldquo;Organisation
          contact (to be identified)&rdquo;, and a named person becomes a new respondent. Only the organisation&rsquo;s
          name, province, district and value chain are sent to the AI provider.
        </p>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!data.configured && <p className="text-sm">AI research hasn&rsquo;t been set up yet. Ask the administrator.</p>}
      {!invitable && <p className="text-sm">This is a locked Reserve, so it is not searched for contact details.</p>}

      <WriteOnly note={null}>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={!data.configured || !invitable || running || start.isPending}
            onClick={() => start.mutate()}
          >
            {running || start.isPending ? "Searching…" : data.run ? "Search again" : "Find contact details"}
          </Button>
          {running && <span className="text-xs text-text-muted">This takes a minute or two. You can leave this page and come back.</span>}
        </div>
      </WriteOnly>

      {data.run?.status === "FAILED" && <p className="text-danger text-sm">The last search failed: {data.run.error}</p>}
      {data.run?.status === "DONE" && (
        <p className="text-xs text-text-muted">
          {data.run.summary} ({data.run.searches_used} searches
          {data.run.dropped.length > 0 ? `; ${data.run.dropped.length} item(s) removed automatically as private or not shown on their page` : ""}.)
        </p>
      )}

      {publicContacts.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {publicContacts.map(([name, item]) => (
            <div key={name} className="contents">
              <dt className="text-text-muted">{name === "website" ? "Website" : "Office location"}</dt>
              <dd className="min-w-0 break-words">
                {name === "website" ? (
                  <a href={item.value} target="_blank" rel="noopener noreferrer" className="underline text-header">
                    {item.value}
                  </a>
                ) : (
                  item.value
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {pending.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium">To review ({pending.length})</h4>
          {pending.map((p) => (
            <div key={p.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span className="text-sm font-medium">{p.kind_label}</span>
                {p.confidence && <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">{p.confidence}</span>}
              </div>
              <p className="text-sm break-words">{describe(p)}</p>
              {p.flags.includes("webmail") && (
                <p className="text-xs text-text-muted">A personal-style email service. Check the page shows it as the organisation&rsquo;s own address.</p>
              )}
              <ul className="text-xs space-y-1">
                {p.sources.map((s) => (
                  <li key={s.url} className="break-words">
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline text-header">
                      {s.title}
                    </a>
                    {s.quote && <span className="block text-text-muted">&ldquo;{s.quote}&rdquo;</span>}
                  </li>
                ))}
              </ul>
              <WriteOnly note={null}>
                <div className="flex flex-wrap items-end gap-2">
                  {p.kind === "PERSON" && (
                    <label className="text-xs text-text-muted">
                      Role
                      <select
                        className="block mt-1 rounded-md border border-border px-2 py-1.5 text-sm"
                        value={roles[p.id] ?? ""}
                        onChange={(e) => setRoles((r) => ({ ...r, [p.id]: e.target.value }))}
                      >
                        {ROLE_OPTIONS.map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <Button onClick={() => accept.mutate(p)} disabled={accept.isPending}>
                    Accept
                  </Button>
                  <Button variant="outline" onClick={() => reject.mutate(p)} disabled={reject.isPending}>
                    Reject
                  </Button>
                </div>
              </WriteOnly>
            </div>
          ))}
        </div>
      )}

      {decided.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-muted">Already decided ({decided.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {decided.map((p) => (
              <li key={p.id} className="break-words">
                {p.kind_label}: {describe(p)} ({p.status === "REJECTED" ? "rejected" : "accepted"})
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
