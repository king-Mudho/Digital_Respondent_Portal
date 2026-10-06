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
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED";
  queue_position: number | null;
  searches_used: number;
  summary: string;
  error: string;
  dropped: { reason: string }[];
}

interface FinderState {
  configured: boolean;
  searchable?: boolean; // KII: not yet interviewed or declined
  placeholder?: boolean; // KII: "(contact not yet identified)"
  run: Run | null;
  proposals: Proposal[];
  public_contacts: Record<string, { value: string; source: string }>;
}

function describe(p: Proposal) {
  if (p.kind !== "PERSON") return p.value;
  return [`${p.person_name}, ${p.person_title}`, p.person_email, p.person_phone].filter(Boolean).join(" · ");
}

interface CardProps {
  stateUrl: string; // GET state, POST to start a search
  decideBase: string; // {decideBase}/{id}/accept/ and /reject/
  queryKey: string[];
  alsoRefresh: string[][]; // queries an accept changes (the respondents list, the KII record)
  intro: React.ReactNode;
  blocked: (data: FinderState) => string | null; // why this one may not be searched, if so
  personRoles: boolean; // Main-400: choose the person's role category when accepting
  onDecided?: () => void; // e.g. the KII record page reloading the record an accept changed
}

/**
 * AI finds PUBLISHED contact details (backend/apps/contacts/contact_finder.py, kii_finder.py). Every finding carries
 * the page it came from and the passage that shows it; nothing is saved until a person accepts it.
 */
function ContactFinderCard({ stateUrl, decideBase, queryKey: key, alsoRefresh, intro, blocked, personRoles, onDecided }: CardProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Record<number, string>>({});

  const { data } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<FinderState>(stateUrl),
    // A search waits its turn (the research worker does one at a time), then runs for a minute or two; keep
    // checking until it stops.
    refetchInterval: (query) => {
      const status = query.state.data?.run?.status;
      return status === "RUNNING" ? 4000 : status === "QUEUED" ? 10000 : false;
    },
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
    for (const other of alsoRefresh) queryClient.invalidateQueries({ queryKey: other });
    onDecided?.();
  };
  const failed = (fallback: string) => (err: unknown) => setError(err instanceof ApiError ? err.message : fallback);

  const start = useMutation({
    mutationFn: () => adminFetch<Run>(stateUrl, { method: "POST" }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: key });
    },
    onError: failed("Could not start the search."),
  });
  const accept = useMutation({
    mutationFn: (p: Proposal) =>
      adminFetch(`${decideBase}/${p.id}/accept/`, {
        method: "POST",
        body: JSON.stringify(personRoles && p.kind === "PERSON" ? { role_category: roles[p.id] ?? "" } : {}),
      }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: failed("Could not accept that detail."),
  });
  const reject = useMutation({
    mutationFn: (p: Proposal) =>
      adminFetch(`${decideBase}/${p.id}/reject/`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: failed("Could not reject that detail."),
  });

  if (!data) return null;
  const queued = data.run?.status === "QUEUED";
  const running = queued || data.run?.status === "RUNNING";
  const ahead = data.run?.queue_position ?? 0;
  const pending = data.proposals.filter((p) => p.status === "PROPOSED");
  const decided = data.proposals.filter((p) => p.status !== "PROPOSED");
  const publicContacts = Object.entries(data.public_contacts ?? {});
  const blockedNote = blocked(data);

  return (
    <Card className="space-y-3" aria-label="Find contact details">
      <div className="space-y-1">
        <h3 className="font-semibold">Find contact details with AI</h3>
        <p className="text-xs text-text-muted">{intro}</p>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!data.configured && <p className="text-sm">AI research hasn&rsquo;t been set up yet. Ask the administrator.</p>}
      {blockedNote && <p className="text-sm">{blockedNote}</p>}

      <WriteOnly note={null}>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={!data.configured || !!blockedNote || running || start.isPending}
            onClick={() => start.mutate()}
          >
            {queued ? "Waiting in line…" : running || start.isPending ? "Searching…" : data.run ? "Search again" : "Find contact details"}
          </Button>
          {queued && (
            <span className="text-xs text-text-muted">
              {ahead === 0
                ? "Next in line. It starts by itself; you can leave this page and come back."
                : `${ahead} search${ahead === 1 ? " is" : "es are"} ahead of this one (about a minute each). It starts by itself; you can leave this page and come back.`}
            </span>
          )}
          {running && !queued && <span className="text-xs text-text-muted">This takes a minute or two. You can leave this page and come back.</span>}
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
                  {personRoles && p.kind === "PERSON" && (
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

/** Main-400 case page: organisation phone/email go to "Organisation contact (to be identified)"; a named person
 * becomes a new respondent. PI and Field Coordinator decide. */
export function ContactFinderPanel({ sampleId, invitable }: { sampleId: string; invitable: boolean }) {
  return (
    <ContactFinderCard
      stateUrl={`/contacts/${sampleId}/contact-search/`}
      decideBase="/contacts/contact-proposals"
      queryKey={["contact-search", sampleId]}
      alsoRefresh={[["respondents", sampleId]]}
      personRoles
      blocked={() => (invitable ? null : "This is a locked Reserve, so it is not searched for contact details.")}
      intro={
        <>
          Searches public sources for this organisation&rsquo;s published phone number and email, and for senior staff
          the organisation names, but only with their published phone or email. Every detail comes with the page it was
          found on and the passage that shows it. Nothing is saved until you accept it: an organisation phone or email goes to &ldquo;Organisation
          contact (to be identified)&rdquo;, and a named person becomes a new respondent. Only the organisation&rsquo;s
          name, province, district and value chain are sent to the AI provider.
        </>
      }
    />
  );
}

/** KII record page (backend/apps/contacts/kii_finder.py): the organisation's published contacts and the informant's
 * WORK contact where their organisation publishes it; for a placeholder record, the current holder of the role.
 * Accepting fills the record's phone and email (never over a different one). PI, Field Coordinator and KII RA decide. */
export function KiiContactFinderPanel({ kiiId, onChange }: { kiiId: number; onChange?: () => void }) {
  return (
    <ContactFinderCard
      stateUrl={`/contacts/kii/${kiiId}/contact-search/`}
      decideBase="/contacts/kii-proposals"
      queryKey={["kii-contact-search", String(kiiId)]}
      alsoRefresh={[["kii-contact-batch"]]}
      onDecided={onChange}
      personRoles={false}
      blocked={(data) => (data.searchable === false ? "This informant has already been interviewed or declined." : null)}
      intro={
        <>
          Searches public sources for the informant&rsquo;s organisation&rsquo;s published phone number and email, and
          the informant&rsquo;s work email or phone where their own organisation publishes it (never a personal number,
          personal email or personal social media). For a record still marked &ldquo;contact not yet identified&rdquo;, it
          looks for whoever currently holds the role, with their phone or email. Every detail comes with the page and the passage that shows it.
          Nothing is saved until you accept it: a phone or email fills the record (never over a different one), and a
          person found for an unidentified record becomes its informant. Only the organisation&rsquo;s name and type and
          the informant&rsquo;s name and role are sent to the AI provider.
        </>
      }
    />
  );
}
