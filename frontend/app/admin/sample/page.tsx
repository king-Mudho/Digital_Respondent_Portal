"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, IfScreen, WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, SearchBox, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface SampleCase {
  id: number;
  sample_id: string;
  organisation_name: string;
  organisation_master_id: string;
  sample_type: string;
  status: string;
  workflow_status: string | null;
}

const VERIFICATION_STEPS: Record<string, { to: string; label: string }> = {
  S00: { to: "S01", label: "S00 Selected → S01 Verification required" },
  S01: { to: "S02", label: "S01 Verification required → S02 Organisation verified" },
  S02: { to: "S03", label: "S02 Organisation verified → S03 Eligible respondent identified" },
};

/**
 * Moves every Main case at one verification step to the next. All 400 cases
 * start at S00, and a case's status only follows its respondent (and
 * reminders are only offered) from S03 onward -- one case at a time that was
 * about 1,200 clicks. Each case still gets its own audited transition.
 */
function BulkVerificationPanel() {
  const queryClient = useQueryClient();
  const [from, setFrom] = useState("S00");
  const [result, setResult] = useState<string | null>(null);
  const { data: counts } = useQuery({
    queryKey: ["sample-cases-at-step", from],
    queryFn: () => adminFetch<Paginated<SampleCase>>(`/sample-cases/?sample_type=MAIN&workflow_status=${from}&page=1`),
  });
  const count = counts?.count ?? 0;
  const move = useMutation({
    mutationFn: () =>
      adminFetch<{ moved: number }>("/sample-cases/bulk-transition/", {
        method: "POST",
        body: JSON.stringify({ from_status: from }),
      }),
    onSuccess: (data) => {
      setResult(`Moved ${data.moved} case${data.moved === 1 ? "" : "s"} to ${VERIFICATION_STEPS[from].to}.`);
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
      queryClient.invalidateQueries({ queryKey: ["sample-cases-at-step"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not move the cases."),
  });

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Move cases through verification</h3>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm w-full sm:w-auto min-w-0">
          <span className="sr-only">Verification step</span>
          <select
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setResult(null);
            }}
            className="w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm"
          >
            {Object.entries(VERIFICATION_STEPS).map(([key, step]) => (
              <option key={key} value={key}>
                {step.label}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="outline"
          disabled={count === 0 || move.isPending}
          onClick={() => {
            if (window.confirm(`Move all ${count} Main cases at ${from} to ${VERIFICATION_STEPS[from].to}?`)) {
              move.mutate();
            }
          }}
        >
          {move.isPending ? "Moving…" : `Move all ${count}`}
        </Button>
      </div>
      {result && <p className="text-sm text-text-muted">{result}</p>}
    </Card>
  );
}

interface ContactRA {
  id: number;
  username: string;
  full_name: string;
}

const PROVINCES: Array<[string, string]> = [
  ["BULAWAYO", "Bulawayo"], ["HARARE", "Harare"], ["MANICALAND", "Manicaland"],
  ["MASHONALAND_CENTRAL", "Mashonaland Central"], ["MASHONALAND_EAST", "Mashonaland East"],
  ["MASHONALAND_WEST", "Mashonaland West"], ["MASVINGO", "Masvingo"], ["MATABELELAND_NORTH", "Matabeleland North"],
  ["MATABELELAND_SOUTH", "Matabeleland South"], ["MIDLANDS", "Midlands"],
];

const raName = (ra: ContactRA) => (ra.full_name ? `${ra.full_name} (${ra.username})` : ra.username);

/**
 * Hands Main cases to a Contact RA in bulk (added 2026-09-15). All 400
 * started on one shared account; one case page at a time that was 400
 * dropdowns. "How many" splits a big province between several RAs.
 */
interface WhatsAppRow {
  sample_id: string;
  organisation: string;
  to_name: string;
  number: string;
}

interface PreparedInvitation {
  sample_id: string;
  whatsapp_url: string;
  message: string;
}

/**
 * WhatsApp send queue (backend/apps/invitations/whatsapp_queue.py). With no WhatsApp Business account nothing can be
 * sent automatically, so each verified case gets its invitation prepared here and the RA sends it from their own
 * phone with one tap. A Contact RA sees only their assigned cases.
 */
function WhatsAppQueuePanel() {
  const queryClient = useQueryClient();
  const [prepared, setPrepared] = useState<Record<string, PreparedInvitation>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["whatsapp-queue"],
    queryFn: () => adminFetch<{ results: WhatsAppRow[]; waiting: number }>("/invitations/whatsapp-queue/"),
  });
  const prepare = useMutation({
    mutationFn: (sampleId: string) =>
      adminFetch<PreparedInvitation>(`/invitations/whatsapp-queue/${sampleId}/prepare/`, {
        method: "POST",
        body: JSON.stringify({ link_base: window.location.origin }),
      }),
    onSuccess: (result) => {
      setError(null);
      setPrepared((p) => ({ ...p, [result.sample_id]: result }));
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not prepare that invitation."),
  });
  if (!data) return null;
  const copy = (item: PreparedInvitation) => {
    navigator.clipboard
      .writeText(item.message)
      .then(() => setCopied(item.sample_id))
      .catch(() => setError("Copying isn't available here. Open WhatsApp instead."));
  };

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">WhatsApp invitations</h3>
      <p className="text-xs text-text-muted">
        {data.waiting} verified case{data.waiting === 1 ? "" : "s"} (S03 or S04) {data.waiting === 1 ? "has" : "have"} a WhatsApp or
        phone number and no open invitation. <strong>Prepare</strong> creates the case&rsquo;s personal link and marks it sent, so open
        WhatsApp and send it straight away. If you can&rsquo;t, revoke it on the case page.
      </p>
      {error && <p className="text-danger text-sm">{error}</p>}
      {data.results.length > 0 && (
        <ul className="divide-y divide-border text-sm">
          {data.results.map((row) => {
            const ready = prepared[row.sample_id];
            return (
              <li key={row.sample_id} className="py-2 flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words">
                  <span className="font-mono">{row.sample_id}</span> · {row.organisation}
                  <span className="block text-xs text-text-muted">
                    {row.to_name} · {row.number}
                  </span>
                </span>
                <WriteOnly note={null}>
                  {ready ? (
                    <span className="flex flex-wrap gap-2">
                      <a
                        href={ready.whatsapp_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center rounded-md bg-header text-white px-3 py-1.5 text-sm"
                      >
                        Open WhatsApp
                      </a>
                      <Button variant="outline" onClick={() => copy(ready)}>
                        {copied === row.sample_id ? "Copied" : "Copy message"}
                      </Button>
                    </span>
                  ) : (
                    <Button variant="outline" disabled={prepare.isPending} onClick={() => prepare.mutate(row.sample_id)}>
                      Prepare
                    </Button>
                  )}
                </WriteOnly>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

interface InvitationBatch {
  id: number;
  requested: number;
  status: "RUNNING" | "DONE" | "FAILED";
  sent: number;
  failed: number;
  skipped: number;
  results: { sample_id: string; outcome: "sent" | "failed" | "skipped"; detail: string }[];
  error: string;
}

interface EmailBatchInfo {
  email_configured: boolean;
  candidates: number;
  preview: { sample_id: string; organisation: string; email: string }[];
  max_per_batch: number;
  daily_max: number;
  left_today: number;
  latest: InvitationBatch | null;
}

/**
 * Emails invitations to verified cases (S03/S04) with an email and no open invitation, through the same issue and
 * email steps as the case-page Email button (backend/apps/invitations/batch.py). Sending needs a second, explicit
 * click: the viewer has no confirm() dialog, so the confirmation is part of the page.
 */
function EmailInvitationsPanel() {
  const queryClient = useQueryClient();
  const [count, setCount] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: info } = useQuery({
    queryKey: ["invitation-batch"],
    queryFn: () => adminFetch<EmailBatchInfo>("/invitations/batch/"),
    refetchInterval: (query) => (query.state.data?.latest?.status === "RUNNING" ? 3000 : false),
  });
  const send = useMutation({
    mutationFn: (limit: number) =>
      adminFetch<InvitationBatch>("/invitations/batch/", { method: "POST", body: JSON.stringify({ limit }) }),
    onSuccess: () => {
      setError(null);
      setConfirming(false);
      setCount("");
      queryClient.invalidateQueries({ queryKey: ["invitation-batch"] });
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => {
      setConfirming(false);
      setError(err instanceof Error ? err.message : "Could not start sending.");
    },
  });
  if (!info) return null;
  const latest = info.latest;
  const sending = latest?.status === "RUNNING";
  const allowed = Math.min(info.max_per_batch, info.left_today, info.candidates);
  const limit = Number(count || 0);
  const valid = limit >= 1 && limit <= allowed;
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Email invitations</h3>
      <p className="text-xs text-text-muted">
        {plural(info.candidates, "verified case")} (S03 or S04) {info.candidates === 1 ? "has" : "have"} a respondent email and no
        open invitation. Each gets the approved invitation email from the study address with its own link (valid 14 days)
        and phone code, and moves to &ldquo;Invitation sent&rdquo;. {info.left_today} of {info.daily_max} emails left today. Day 2 and
        Day 7 reminders appear on Follow-ups to send by hand.
      </p>
      {error && <p className="text-danger text-sm">{error}</p>}
      {!info.email_configured && (
        <p className="text-sm">
          Email isn&rsquo;t set up on the server yet. The administrator runs <code>deploy/configure-email.sh</code> with the
          study&rsquo;s email account first.
        </p>
      )}

      {info.preview.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-muted">Next in line ({Math.min(info.preview.length, info.candidates)} shown)</summary>
          <ul className="mt-1 space-y-0.5">
            {info.preview.map((row) => (
              <li key={row.sample_id} className="break-words">
                <span className="font-mono">{row.sample_id}</span> · {row.organisation} · {row.email}
              </li>
            ))}
          </ul>
        </details>
      )}

      {!confirming ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs text-text-muted">
            How many (up to {Math.max(allowed, 0)})
            <input
              type="number"
              min={1}
              max={allowed}
              value={count}
              onChange={(e) => setCount(e.target.value)}
              className="block mt-1 w-28 rounded-md border border-border px-3 py-2 bg-surface text-sm"
            />
          </label>
          <Button variant="outline" disabled={!info.email_configured || sending || !valid} onClick={() => setConfirming(true)}>
            Review and send
          </Button>
        </div>
      ) : (
        <div className="rounded-md border border-border p-3 space-y-2">
          <p className="text-sm">
            Email {plural(limit, "invitation")} now, to the respondents on file, in Sample ID order? This can&rsquo;t be undone, but any
            single invitation can be revoked from its case page.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => send.mutate(limit)} disabled={send.isPending}>
              {send.isPending ? "Starting…" : `Send ${plural(limit, "invitation")}`}
            </Button>
            <Button variant="outline" onClick={() => setConfirming(false)} disabled={send.isPending}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {latest && (
        <div className="text-sm space-y-1">
          <p>
            {sending ? "Sending…" : latest.status === "FAILED" ? "The last batch stopped early." : "Last batch:"} {latest.sent} sent,{" "}
            {latest.failed} failed, {latest.skipped} skipped of {latest.requested}.
          </p>
          {latest.error && <p className="text-danger text-xs">{latest.error}</p>}
          {latest.results.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-text-muted">Case by case</summary>
              <ul className="mt-1 space-y-0.5">
                {latest.results.map((row) => (
                  <li key={row.sample_id} className="break-words">
                    <span className="font-mono">{row.sample_id}</span>: {row.outcome}
                    {row.detail ? ` (${row.detail})` : ""}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </Card>
  );
}

interface BatchProgress {
  batch: string;
  total: number;
  queued: number;
  running: number;
  done: number;
  failed: number;
  active: boolean;
}

interface BatchInfo {
  configured: boolean;
  without_contacts: number;
  max: number;
  cost_per_case_usd: [number, number];
  progress: BatchProgress | null;
  to_review_total: number;
  to_review: { sample_id: string; organisation: string; findings: number }[];
}

/**
 * Queues the AI contact finder (backend/apps/contacts/contact_finder.py) for cases that may be invited but have no
 * phone, WhatsApp or email on file yet, one batch at a time. The research worker does one search at a time, so the
 * panel shows the batch's progress, and lists every case whose findings are waiting to be accepted or rejected on
 * its case page -- nothing is saved until then.
 */
function ContactFinderBatchPanel() {
  const queryClient = useQueryClient();
  const [count, setCount] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const { data: info } = useQuery({
    queryKey: ["contact-search-batch"],
    queryFn: () => adminFetch<BatchInfo>("/contacts/contact-search/batch/"),
    refetchInterval: (query) => (query.state.data?.progress?.active ? 10000 : false),
  });
  const run = useMutation({
    mutationFn: (limit: number) =>
      adminFetch<{ queued: number; without_contacts: number; estimated_cost_usd: [number, number] }>(
        "/contacts/contact-search/batch/",
        { method: "POST", body: JSON.stringify({ limit }) },
      ),
    onSuccess: (data) => {
      const [low, high] = data.estimated_cost_usd;
      setCount("");
      setResult(
        `Queued ${data.queued} search${data.queued === 1 ? "" : "es"} (estimated US$${low.toFixed(2)}–${high.toFixed(2)}). ` +
          "They run one at a time, about a minute each; findings appear below as they come in.",
      );
      queryClient.invalidateQueries({ queryKey: ["contact-search-batch"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not start the searches."),
  });
  if (!info) return null;
  const progress = info.progress;
  const active = !!progress?.active;
  const max = Math.min(info.max, info.without_contacts);
  const limit = Number(count || 0);
  const [low, high] = info.cost_per_case_usd;
  const left = progress ? progress.queued + progress.running : 0;

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Find contact details with AI</h3>
      <p className="text-xs text-text-muted">
        {info.without_contacts} case{info.without_contacts === 1 ? "" : "s"} not yet invited ha{info.without_contacts === 1 ? "s" : "ve"} no
        phone, WhatsApp or email on file. The AI searches public sources for each organisation&rsquo;s published contact
        details; nothing is saved until you accept it on the case page. Roughly US${low.toFixed(2)}–{high.toFixed(2)} per case.
      </p>
      {!info.configured && <p className="text-sm">AI research hasn&rsquo;t been set up yet. Ask the administrator.</p>}

      {progress && (
        <p className="text-sm" role="status">
          {active ? "Batch in progress: " : "Last batch: "}
          {progress.done} done{progress.running ? ", 1 searching now" : ""}
          {progress.queued ? `, ${progress.queued} waiting` : ""}
          {progress.failed ? `, ${progress.failed} failed` : ""} (of {progress.total}).
          {active && ` About ${left} minute${left === 1 ? "" : "s"} left.`}
        </p>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-text-muted">
          How many cases (up to {max})
          <input
            type="number"
            min={1}
            max={max}
            value={count}
            disabled={active}
            onChange={(e) => setCount(e.target.value)}
            className="block mt-1 w-28 rounded-md border border-border px-3 py-2 bg-surface text-sm"
          />
        </label>
        <Button
          variant="outline"
          disabled={!info.configured || active || max < 1 || limit < 1 || limit > max || run.isPending}
          onClick={() => run.mutate(limit)}
        >
          {run.isPending ? "Starting…" : "Find contacts"}
        </Button>
      </div>
      {active && <p className="text-xs text-text-muted">Start the next batch when this one has finished.</p>}
      {result && <p className="text-sm">{result}</p>}

      {info.to_review_total > 0 && (
        <details open className="text-sm">
          <summary className="cursor-pointer font-medium">
            Findings to review ({info.to_review_total} case{info.to_review_total === 1 ? "" : "s"})
          </summary>
          <p className="text-xs text-text-muted mt-1">Open each case to accept or reject what was found.</p>
          <ul className="mt-1 divide-y divide-border">
            {info.to_review.map((row) => (
              <li key={row.sample_id} className="py-1.5 flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words">
                  <span className="font-mono text-xs">{row.sample_id}</span> · {row.organisation}
                </span>
                <Link href={`/admin/sample/${row.sample_id}`} className="text-header underline text-xs whitespace-nowrap">
                  Review {row.findings} finding{row.findings === 1 ? "" : "s"}
                </Link>
              </li>
            ))}
          </ul>
          {info.to_review_total > info.to_review.length && (
            <p className="text-xs text-text-muted mt-1">Showing the first {info.to_review.length}.</p>
          )}
        </details>
      )}
    </Card>
  );
}

function BulkAssignmentPanel() {
  const queryClient = useQueryClient();
  const [from, setFrom] = useState("any");
  const [province, setProvince] = useState("");
  const [limit, setLimit] = useState("");
  const [to, setTo] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const { data: ras } = useQuery({
    queryKey: ["contact-ras"],
    queryFn: () => adminFetch<{ results: ContactRA[] }>("/auth/contact-ras/"),
  });
  const filters = {
    from,
    province,
    limit: limit ? Number(limit) : null,
    to_ra: to === "none" ? null : to ? Number(to) : null,
  };
  const { data: preview } = useQuery({
    queryKey: ["bulk-assign-preview", filters],
    queryFn: () =>
      adminFetch<{ count: number }>("/sample-cases/bulk-assign/", {
        method: "POST",
        body: JSON.stringify({ ...filters, preview: true }),
      }),
    enabled: to !== "",
  });
  const count = preview?.count ?? 0;
  const target = to === "none" ? "nobody (unassigned)" : raName(ras?.results.find((r) => String(r.id) === to) ?? { id: 0, username: "", full_name: "" });
  const move = useMutation({
    mutationFn: () =>
      adminFetch<{ moved: number }>("/sample-cases/bulk-assign/", { method: "POST", body: JSON.stringify(filters) }),
    onSuccess: (data) => {
      setResult(`Moved ${data.moved} case${data.moved === 1 ? "" : "s"} to ${target}.`);
      queryClient.invalidateQueries({ queryKey: ["bulk-assign-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sample-cases"] });
    },
    onError: (err) => setResult(err instanceof Error ? err.message : "Could not move the cases."),
  });
  const select = "w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm";

  return (
    <Card className="mb-4 space-y-2">
      <h3 className="font-medium text-sm">Reassign cases</h3>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          From
          <select value={from} onChange={(e) => { setFrom(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="any">Anyone</option>
            <option value="unassigned">Unassigned</option>
            {ras?.results.map((ra) => <option key={ra.id} value={ra.id}>{raName(ra)}</option>)}
          </select>
        </label>
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          Province
          <select value={province} onChange={(e) => { setProvince(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="">All provinces</option>
            {PROVINCES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="text-xs text-text-muted w-full sm:w-28 min-w-0">
          How many
          <input
            type="number"
            min={1}
            value={limit}
            placeholder="All"
            onChange={(e) => { setLimit(e.target.value); setResult(null); }}
            className={`${select} block mt-1 sm:w-28`}
          />
        </label>
        <label className="text-xs text-text-muted w-full sm:w-auto min-w-0">
          To
          <select value={to} onChange={(e) => { setTo(e.target.value); setResult(null); }} className={`${select} block mt-1`}>
            <option value="">Choose a Contact RA…</option>
            {ras?.results.map((ra) => <option key={ra.id} value={ra.id}>{raName(ra)}</option>)}
            <option value="none">Nobody (unassign)</option>
          </select>
        </label>
        <Button
          variant="outline"
          disabled={!to || count === 0 || move.isPending}
          onClick={() => {
            if (window.confirm(`Move ${count} Main case${count === 1 ? "" : "s"} to ${target}?`)) move.mutate();
          }}
        >
          {move.isPending ? "Moving…" : to ? `Move ${count} case${count === 1 ? "" : "s"}` : "Move cases"}
        </Button>
      </div>
      <p className="text-xs text-text-muted">
        Cases move in Sample ID order. To split a large province, move part of it with &quot;How many&quot;, then the rest to the next RA.
      </p>
      {result && <p className="text-sm text-text-muted">{result}</p>}
    </Card>
  );
}

export default function SampleRegisterPage() {
  const [sampleType, setSampleType] = useState("MAIN");
  const [search, setSearch] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();

  const { data, isLoading } = useQuery({
    queryKey: ["sample-cases", sampleType, search, page, pageSize],
    queryFn: () =>
      adminFetch<Paginated<SampleCase>>(
        `/sample-cases/?sample_type=${sampleType}&page=${page}&page_size=${pageSize}` +
          (search ? `&search=${encodeURIComponent(search)}` : ""),
      ),
    // Without this the table blanks to "Loading…" on every keystroke and
    // every page step, which makes the register feel broken.
    placeholderData: keepPreviousData,
  });

  function changeFilter(fn: () => void) {
    fn();
    setPage(1); // page 3 of Main is rarely page 3 of Reserve
  }

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">
          {sampleType === "MAIN" ? "Main-400 Register" : "Reserve Register"}
        </h2>
        <div className="flex items-center gap-3 flex-wrap">
          <SearchBox
            value={search}
            onChange={(v) => changeFilter(() => setSearch(v))}
            placeholder="Search ID or organisation"
          />
          <label className="text-sm text-text-muted">
            <span className="sr-only">Sample type</span>
            <select
              value={sampleType}
              onChange={(e) => changeFilter(() => setSampleType(e.target.value))}
              className="rounded-md border border-border px-3 py-2 bg-surface text-sm"
            >
              <option value="MAIN">Main</option>
              <option value="RESERVE">Reserve</option>
            </select>
          </label>
          {/* Cases are created from an organisation, so this is the route
              in -- but only for the roles that hold that screen. */}
          <IfScreen path="/admin/organisations">
            <Link href="/admin/organisations">
              <Button variant="outline">Register organisation</Button>
            </Link>
          </IfScreen>
        </div>
      </div>
      {sampleType === "MAIN" && (
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR"]}>
          <BulkVerificationPanel />
          <BulkAssignmentPanel />
          <ContactFinderBatchPanel />
          <EmailInvitationsPanel />
        </IfRole>
      )}
      {sampleType === "MAIN" && (
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "CONTACT_RA", "SUPERVISOR_READONLY"]}>
          <WhatsAppQueuePanel />
        </IfRole>
      )}
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-2 pr-4">Sample ID</th>
                    <th className="py-2 pr-4">Master ID</th>
                    <th className="py-2 pr-4">Organisation</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((sc) => (
                    <tr key={sc.id} className="border-t border-border">
                      <td className="py-2 pr-4 font-mono text-xs">{sc.sample_id}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{sc.organisation_master_id}</td>
                      <td className="py-2 pr-4">{sc.organisation_name}</td>
                      <td className="py-2 pr-4">
                        <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                          {sc.workflow_status ?? sc.status}
                        </span>
                      </td>
                      <td className="py-2">
                        <Link href={`/admin/sample/${sc.sample_id}`} className="text-header underline text-xs">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.results.length === 0 && (
                <p className="text-text-muted text-sm py-4">
                  {search ? `No cases match "${search}".` : "No cases found."}
                </p>
              )}
            </div>
            <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="cases" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
