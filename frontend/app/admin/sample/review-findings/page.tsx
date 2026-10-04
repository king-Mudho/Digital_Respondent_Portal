"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { ROLE_OPTIONS } from "@/components/admin/RespondentsPanel";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useAdminUser } from "@/lib/auth/session";

type Kind = "ORG_PHONE" | "ORG_EMAIL" | "WEBSITE" | "OFFICE_LOCATION" | "PERSON";

interface Finding {
  id: number;
  kind: Kind;
  kind_label: string;
  value: string;
  person_name: string;
  person_title: string;
  person_email: string;
  person_phone: string;
  sources: { title: string; url: string; quote: string }[];
  confidence: string;
  flags: string[];
  site: string;
}

interface ReviewCase {
  sample_id: string;
  organisation: string;
  workflow_status: string;
  current: { phone: string; email: string };
  proposals: Finding[];
}

interface ReviewData {
  facets: { kind: Partial<Record<Kind, number>>; confidence: Record<string, number>; site: [string, number][] };
  total_waiting: number;
  total_shown: number;
  total_cases: number;
  page: number;
  pages: number;
  cases: ReviewCase[];
}

const KINDS: [Kind, string][] = [
  ["ORG_PHONE", "Phones"],
  ["ORG_EMAIL", "Emails"],
  ["PERSON", "Named people"],
  ["WEBSITE", "Websites"],
  ["OFFICE_LOCATION", "Office locations"],
];
const CONFIDENCES = ["HIGH", "MODERATE", "LOW"];

function describe(f: Finding) {
  if (f.kind !== "PERSON") return f.value;
  return [`${f.person_name}, ${f.person_title}`, f.person_email, f.person_phone].filter(Boolean).join(" · ");
}

/** Why "Accept all shown" can't be used for a case, or null when it can. */
function acceptAllBlocked(c: ReviewCase): string | null {
  const count = (kind: Kind) => c.proposals.filter((p) => p.kind === kind).length;
  if (count("PERSON")) return "Accept named people one at a time, with their role.";
  if (count("ORG_PHONE") > 1) return "More than one phone: accept the right one.";
  if (count("ORG_EMAIL") > 1) return "More than one email: accept the right one.";
  return null;
}

/**
 * Every AI contact finding still waiting for a decision, on one page, grouped by case
 * (backend/apps/contacts/contact_finder.py review_queue). Decisions use the same accept/reject endpoints as the case
 * page, one finding at a time, so each is audited under the reviewer's name. "Accept all shown" is only a shortcut
 * for accepting what the reviewer can see on screen; nothing is ever accepted without a person choosing it.
 */
function ReviewFindings() {
  const user = useAdminUser();
  const queryClient = useQueryClient();
  const [kinds, setKinds] = useState<Kind[]>(["ORG_PHONE", "ORG_EMAIL"]);
  const [confidences, setConfidences] = useState<string[]>([]);
  const [site, setSite] = useState("");
  const [page, setPage] = useState(1);
  const [roles, setRoles] = useState<Record<number, string>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmReject, setConfirmReject] = useState<string | null>(null);

  const params = new URLSearchParams({ page: String(page) });
  if (kinds.length) params.set("kind", kinds.join(","));
  if (confidences.length) params.set("confidence", confidences.join(","));
  if (site) params.set("site", site);
  const key = ["contact-review", params.toString()];
  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<ReviewData>(`/contacts/contact-proposals/review/?${params.toString()}`),
    placeholderData: keepPreviousData,
    enabled: user?.role !== "CONTACT_RA",
  });

  if (user?.role === "CONTACT_RA") {
    return <p className="text-sm">Reviewing AI findings is for the PI and Field Coordinator.</p>;
  }

  const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["contact-review"] });
    queryClient.invalidateQueries({ queryKey: ["contact-search-batch"] });
  };

  async function decide(findings: Finding[], action: "accept" | "reject", label: string) {
    setBusy(label);
    const failed: Record<number, string> = {};
    for (const f of findings) {
      try {
        await adminFetch(`/contacts/contact-proposals/${f.id}/${action}/`, {
          method: "POST",
          body: JSON.stringify(action === "accept" && f.kind === "PERSON" ? { role_category: roles[f.id] ?? "" } : {}),
        });
      } catch (err) {
        failed[f.id] = err instanceof ApiError ? err.message : `Could not ${action} this finding.`;
      }
    }
    setErrors((e) => {
      const next = { ...e };
      for (const f of findings) delete next[f.id];
      return { ...next, ...failed };
    });
    setBusy(null);
    setConfirmReject(null);
    refresh();
  }

  const chip = (on: boolean) =>
    `rounded-full border px-3 py-1 text-xs ${on ? "bg-header text-white border-header" : "bg-surface border-border"}`;

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div className="space-y-1">
          <p className="text-xs text-text-muted">Show</p>
          <div className="flex flex-wrap gap-2">
            {KINDS.map(([kind, label]) => (
              <button key={kind} type="button" className={chip(kinds.includes(kind))} aria-pressed={kinds.includes(kind)}
                onClick={() => { setKinds(toggle(kinds, kind)); setPage(1); }}>
                {label} ({data?.facets.kind[kind] ?? 0})
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-text-muted">Confidence (none chosen = all)</p>
          <div className="flex flex-wrap gap-2">
            {CONFIDENCES.map((c) => (
              <button key={c} type="button" className={chip(confidences.includes(c))} aria-pressed={confidences.includes(c)}
                onClick={() => { setConfidences(toggle(confidences, c)); setPage(1); }}>
                {c.charAt(0) + c.slice(1).toLowerCase()} ({data?.facets.confidence[c] ?? 0})
              </button>
            ))}
          </div>
        </div>
        <label className="block text-xs text-text-muted">
          Source site
          <select value={site} onChange={(e) => { setSite(e.target.value); setPage(1); }}
            className="block mt-1 w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm">
            <option value="">All sites</option>
            {data?.facets.site.map(([host, n]) => (
              <option key={host} value={host}>{host || "(no source)"} ({n})</option>
            ))}
          </select>
        </label>
        {data && (
          <p className="text-sm" role="status">
            Showing {data.total_shown} of {data.total_waiting} waiting findings, in {data.total_cases} case{data.total_cases === 1 ? "" : "s"}.
          </p>
        )}
      </Card>

      {error && <p className="text-danger text-sm">{error instanceof Error ? error.message : "Could not load the findings."}</p>}
      {isLoading && <p className="text-text-muted text-sm">Loading…</p>}
      {data && data.cases.length === 0 && (
        <Card><p className="text-sm text-text-muted">Nothing waiting with these filters.</p></Card>
      )}

      {data?.cases.map((c) => {
        const blocked = acceptAllBlocked(c);
        const n = c.proposals.length;
        return (
          <Card key={c.sample_id} className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="min-w-0">
                <h3 className="font-semibold break-words">{c.organisation}</h3>
                <p className="text-xs text-text-muted">
                  <span className="font-mono">{c.sample_id}</span> · {c.workflow_status}
                  {(c.current.phone || c.current.email) &&
                    ` · on file: ${[c.current.phone, c.current.email].filter(Boolean).join(", ")}`}
                </p>
              </div>
              <Link href={`/admin/sample/${c.sample_id}`} className="text-header underline text-xs whitespace-nowrap">
                Open case
              </Link>
            </div>

            <ul className="space-y-2">
              {c.proposals.map((f) => (
                <li key={f.id} className="border border-border rounded-md p-3 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm">
                      <span className="text-text-muted">{f.kind_label}: </span>
                      <span className="font-medium break-words">{describe(f)}</span>
                    </span>
                    <span className="flex gap-1 text-xs">
                      <span className="rounded-full bg-bg border border-border px-2 py-0.5">{f.confidence || "LOW"}</span>
                      {f.site && <span className="rounded-full bg-bg border border-border px-2 py-0.5">{f.site}</span>}
                    </span>
                  </div>
                  {f.flags.includes("webmail") && (
                    <p className="text-xs text-text-muted">A personal-style email service: check the page presents it as the organisation&rsquo;s own.</p>
                  )}
                  {f.sources.slice(0, 2).map((s) => (
                    <p key={s.url} className="text-xs break-words">
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline text-header">{s.title || s.url}</a>
                      {s.quote && <span className="block text-text-muted">&ldquo;{s.quote}&rdquo;</span>}
                    </p>
                  ))}
                  {errors[f.id] && <p className="text-danger text-xs">{errors[f.id]}</p>}
                  <WriteOnly note={null}>
                    <div className="flex flex-wrap items-end gap-2 pt-1">
                      {f.kind === "PERSON" && (
                        <label className="text-xs text-text-muted">
                          Role
                          <select value={roles[f.id] ?? ""} onChange={(e) => setRoles((r) => ({ ...r, [f.id]: e.target.value }))}
                            className="block mt-1 rounded-md border border-border px-2 py-1.5 text-sm">
                            {ROLE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                          </select>
                        </label>
                      )}
                      <Button disabled={!!busy} onClick={() => decide([f], "accept", `f${f.id}`)}>Accept</Button>
                      <Button variant="outline" disabled={!!busy} onClick={() => decide([f], "reject", `f${f.id}`)}>Reject</Button>
                    </div>
                  </WriteOnly>
                </li>
              ))}
            </ul>

            <WriteOnly note={null}>
              {confirmReject === c.sample_id ? (
                <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                  <span className="text-sm">Reject all {n} finding{n === 1 ? "" : "s"} shown for this case?</span>
                  <Button variant="outline" disabled={!!busy} onClick={() => decide(c.proposals, "reject", c.sample_id)}>
                    {busy === c.sample_id ? "Rejecting…" : `Reject ${n}`}
                  </Button>
                  <Button variant="outline" disabled={!!busy} onClick={() => setConfirmReject(null)}>Cancel</Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                  <Button disabled={!!busy || !!blocked} onClick={() => decide(c.proposals, "accept", c.sample_id)}>
                    {busy === c.sample_id ? "Accepting…" : `Accept all ${n} shown`}
                  </Button>
                  <Button variant="outline" disabled={!!busy} onClick={() => setConfirmReject(c.sample_id)}>
                    Reject all shown
                  </Button>
                  {blocked && <span className="text-xs text-text-muted">{blocked}</span>}
                </div>
              )}
            </WriteOnly>
          </Card>
        );
      })}

      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <span className="text-sm">Page {data.page} of {data.pages}</span>
          <Button variant="outline" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}

export default function ReviewFindingsPage() {
  return (
    <AdminShell backHref="/admin/sample" backLabel="Main-400 Register">
      <h2 className="font-semibold text-xl mb-1">Review AI contact findings</h2>
      <p className="text-text-muted text-sm mb-4">
        Every finding still waiting for a decision. Check the quoted passage, or open the page, then accept or reject.
        Nothing is saved until you do: an organisation phone or email goes to &ldquo;Organisation contact (to be
        identified)&rdquo;, a named person becomes a new respondent.
      </p>
      <ReviewFindings />
    </AdminShell>
  );
}
