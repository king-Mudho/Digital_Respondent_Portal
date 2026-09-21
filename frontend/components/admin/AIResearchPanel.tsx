"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface Source {
  title: string;
  url: string;
  publisher: string;
  published: string;
  quote: string;
  authority: string;
}

interface Proposal {
  id: number;
  field_id: string;
  label: string;
  status: "PROPOSED" | "NOT_FOUND" | "ACCEPTED" | "EDITED" | "REJECTED";
  proposed_value: string;
  final_value: string;
  confidence: string;
  sources: Source[];
  notes: string;
}

interface Run {
  id: number;
  status: "RUNNING" | "DONE" | "FAILED";
  started_at: string;
  finished_at: string | null;
  searches_used: number;
  summary: string;
  error: string;
  dropped: { reason: string; field_id?: string }[];
}

interface ResearchState {
  configured: boolean;
  run: Run | null;
  proposals: Proposal[];
}

const TIER = (a: string) => a.replace(/^TIER_(\d)_.*/, "Tier $1");

/**
 * AI desk research for one pre-profile. The AI searches public sources for the organisation (and the respondent's
 * published professional role) and PROPOSES values; nothing enters the profile until a researcher accepts it.
 * What it could not find publicly is listed as what to ask the respondent (backend/apps/proit/ai_research.py).
 */
export function AIResearchPanel({ profileId, onChanged }: { profileId: number; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const key = ["proit-ai-research", profileId];
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<number, string>>({});

  const { data } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<ResearchState>(`/proit/pre-profiles/${profileId}/ai-research/`),
    // The AI searches for a few minutes in the background; keep checking until it stops.
    refetchInterval: (query) => (query.state.data?.run?.status === "RUNNING" ? 4000 : false),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
    onChanged();
  };

  const start = useMutation({
    mutationFn: () => adminFetch<Run>(`/proit/pre-profiles/${profileId}/ai-research/`, { method: "POST" }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not start the research."),
  });
  const accept = useMutation({
    mutationFn: (p: Proposal) => {
      const edited = edits[p.id];
      return adminFetch(`/proit/ai-proposals/${p.id}/accept/`, {
        method: "POST",
        body: JSON.stringify(edited !== undefined && edited.trim() !== p.proposed_value ? { value: edited } : {}),
      });
    },
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not accept that finding."),
  });
  const reject = useMutation({
    mutationFn: (p: Proposal) => adminFetch(`/proit/ai-proposals/${p.id}/reject/`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not reject that finding."),
  });

  if (!data) return null;
  const running = data.run?.status === "RUNNING";
  const proposals = data.proposals;
  const pending = proposals.filter((p) => p.status === "PROPOSED");
  const decided = proposals.filter((p) => ["ACCEPTED", "EDITED", "REJECTED"].includes(p.status));
  const notFound = proposals.filter((p) => p.status === "NOT_FOUND");

  return (
    <section className="border border-border rounded-md p-3 space-y-3" aria-label="AI research">
      <div className="space-y-1">
        <h4 className="text-sm font-medium">AI research from public sources</h4>
        <p className="text-xs text-text-muted">
          The AI searches the public web for this organisation and the respondent&rsquo;s published professional role, and
          proposes background facts with a source and a quote for each. Nothing enters the profile until you accept it. The
          organisation name, and the respondent&rsquo;s name and role, are sent to the AI provider&rsquo;s search. It never
          records anything private.
        </p>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!data.configured && <p className="text-sm">AI research hasn&rsquo;t been set up yet (ANTHROPIC_API_KEY). Ask the administrator.</p>}

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={!data.configured || running || start.isPending} onClick={() => start.mutate()}>
          {running || start.isPending ? "Searching…" : data.run ? "Research again" : "Research with AI"}
        </Button>
        {running && <span className="text-xs text-text-muted">This takes a few minutes. You can leave this page and come back.</span>}
      </div>

      {data.run?.status === "FAILED" && <p className="text-danger text-sm">The last search failed: {data.run.error}</p>}
      {data.run?.status === "DONE" && (
        <p className="text-xs text-text-muted">
          {data.run.summary} ({data.run.searches_used} searches
          {data.run.dropped.length > 0 ? `; ${data.run.dropped.length} item(s) removed automatically as private or unverifiable` : ""}.)
        </p>
      )}

      {pending.length > 0 && (
        <div className="space-y-3">
          <h5 className="text-sm font-medium">To review ({pending.length})</h5>
          {pending.map((p) => (
            <div key={p.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span className="text-sm font-medium">{p.label}</span>
                {p.confidence && <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">{p.confidence}</span>}
              </div>
              <label className="block text-xs text-text-muted" htmlFor={`proposal-${p.id}`}>
                Proposed value (edit before accepting if needed)
              </label>
              <textarea
                id={`proposal-${p.id}`}
                rows={2}
                value={edits[p.id] ?? p.proposed_value}
                onChange={(e) => setEdits((d) => ({ ...d, [p.id]: e.target.value }))}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              />
              <ul className="text-xs space-y-1">
                {p.sources.map((s) => (
                  <li key={s.url}>
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline text-header">
                      {s.title}
                    </a>
                    <span className="text-text-muted">
                      {[s.publisher, s.published, TIER(s.authority)].filter(Boolean).map((x) => ` · ${x}`)}
                    </span>
                    {s.quote && <span className="block text-text-muted">&ldquo;{s.quote}&rdquo;</span>}
                  </li>
                ))}
              </ul>
              {p.notes && <p className="text-xs text-text-muted">{p.notes}</p>}
              <div className="flex gap-2">
                <Button onClick={() => accept.mutate(p)} disabled={accept.isPending || !(edits[p.id] ?? p.proposed_value).trim()}>
                  Accept
                </Button>
                <Button variant="outline" onClick={() => reject.mutate(p)} disabled={reject.isPending}>
                  Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {decided.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-muted">Already decided ({decided.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {decided.map((p) => (
              <li key={p.id}>
                {p.label}: {p.status === "REJECTED" ? "rejected" : p.status === "EDITED" ? "accepted with edits" : "accepted"}
              </li>
            ))}
          </ul>
        </details>
      )}

      {notFound.length > 0 && data.run?.status === "DONE" && (
        <div className="space-y-1">
          <h5 className="text-sm font-medium">Not found publicly: ask the respondent ({notFound.length})</h5>
          <p className="flex flex-wrap gap-1.5 text-xs">
            {notFound.map((p) => (
              <span key={p.id} className="rounded-full bg-bg border border-border px-2 py-0.5">
                {p.label}
              </span>
            ))}
          </p>
        </div>
      )}
    </section>
  );
}
