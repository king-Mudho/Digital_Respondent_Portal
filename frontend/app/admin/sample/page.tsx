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
  token_id: number;
  whatsapp_url: string;
  message: string;
  link: string;
  manual_code: string;
  email_to: string;
  email_configured: boolean;
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
  const [emailed, setEmailed] = useState<Record<string, string>>({});
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
  // The same invitation by email: same link and code, checked against the invitation's fingerprint server-side.
  const sendEmail = useMutation({
    mutationFn: (item: PreparedInvitation) =>
      adminFetch<{ sent_to: string }>(`/invitations/${item.token_id}/send-email/`, {
        method: "POST",
        body: JSON.stringify({ link: item.link, manual_code: item.manual_code }),
      }).then((result) => ({ sampleId: item.sample_id, sentTo: result.sent_to })),
    onSuccess: ({ sampleId, sentTo }) => {
      setError(null);
      setEmailed((e) => ({ ...e, [sampleId]: sentTo }));
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The email could not be sent."),
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
        WhatsApp and send it straight away. If you can&rsquo;t, revoke it on the case page. Where the case also has an email
        address, <strong>Email the same link</strong> sends it there too: one invitation, both channels.
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
                      {ready.email_to && ready.email_configured && (
                        <Button
                          variant="outline"
                          disabled={sendEmail.isPending || !!emailed[row.sample_id]}
                          onClick={() => sendEmail.mutate(ready)}
                        >
                          {emailed[row.sample_id] ? `Emailed to ${emailed[row.sample_id]}` : `Email the same link (${ready.email_to})`}
                        </Button>
                      )}
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
  channels?: BatchChannel[];
  mode?: "INVITE" | "INTRO";
  status: "RUNNING" | "DONE" | "FAILED";
  sent: number;
  failed: number;
  skipped: number;
  results: { sample_id: string; outcome: "sent" | "failed" | "skipped"; detail: string }[];
  error: string;
}

type BatchChannel = "EMAIL" | "SMS" | "WHATSAPP";
const BATCH_CHANNELS: BatchChannel[] = ["EMAIL", "SMS", "WHATSAPP"];
const BATCH_LABEL: Record<BatchChannel, string> = { EMAIL: "Email", SMS: "SMS", WHATSAPP: "WhatsApp" };

interface ChannelInfo {
  configured: boolean;
  ready: number;
  left_today: number;
  daily_max: number;
  cost_usd_all?: number;
}

interface SendBatchInfo {
  candidates: number;
  preview: { sample_id: string; organisation: string; email: string; mobile: string; channels: BatchChannel[] }[];
  channels: Record<BatchChannel, ChannelInfo>;
  introductions: { configured: boolean; channel: "" | "WHATSAPP" | "SMS"; ready: number; left_today: number };
  max_per_batch: number;
  latest: InvitationBatch | null;
}

/**
 * Sends invitations to verified cases (S03/S04) with no open invitation, by email and -- once Twilio is set up --
 * SMS and WhatsApp (backend/apps/invitations/batch.py). Each case gets ONE invitation, sent on every chosen channel
 * it has a contact for, so every message carries the same working link. Or, "ask first": a short introduction asking
 * whether they will take part, the link following automatically on a YES (backend/apps/messaging/outreach.py).
 * Sending needs a second, explicit click: the viewer has no confirm() dialog, so the confirmation is part of the page.
 */
function SendInvitationsPanel() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"INTRO" | "INVITE" | null>(null);
  const [chosen, setChosen] = useState<BatchChannel[]>(["EMAIL"]);
  const [count, setCount] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: info } = useQuery({
    queryKey: ["invitation-batch", chosen],
    queryFn: () => adminFetch<SendBatchInfo>(`/invitations/batch/?channels=${chosen.join(",") || "EMAIL"}`),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.latest?.status === "RUNNING" ? 3000 : false),
  });
  const send = useMutation({
    mutationFn: ({ limit, asFirst }: { limit: number; asFirst: boolean }) =>
      adminFetch<InvitationBatch>("/invitations/batch/", {
        method: "POST",
        body: JSON.stringify(asFirst ? { limit, mode: "INTRO" } : { limit, channels: chosen }),
      }),
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
  const toggle = (channel: BatchChannel) =>
    setChosen((current) => (current.includes(channel) ? current.filter((c) => c !== channel) : [...current, channel]));
  const intro = info.introductions;
  const askFirst = (mode ?? (intro.configured ? "INTRO" : "INVITE")) === "INTRO";
  const notSetUp = askFirst ? [] : chosen.filter((c) => !info.channels[c].configured);
  const allowed = askFirst
    ? Math.min(info.max_per_batch, intro.ready, intro.left_today)
    : Math.min(info.max_per_batch, info.candidates, ...chosen.map((c) => info.channels[c].left_today));
  const limit = Number(count || 0);
  const valid = (askFirst ? intro.configured : chosen.length > 0 && notSetUp.length === 0) && limit >= 1 && limit <= allowed;
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  const sms = info.channels.SMS;
  const smsCost = chosen.includes("SMS") && sms.ready > 0 && sms.cost_usd_all
    ? (sms.cost_usd_all / sms.ready) * Math.min(limit || 0, sms.ready)
    : 0;
  const ways = chosen.map((c) => BATCH_LABEL[c]).join(" and ");

  return (
    <Card className="mb-4 space-y-2" aria-label="Send invitations">
      <h3 className="font-medium text-sm">Send invitations</h3>
      <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <legend className="text-xs text-text-muted mb-1">How</legend>
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" name="batch-mode" checked={askFirst} onChange={() => { setMode("INTRO"); setConfirming(false); }} />
          Ask first (introduction)
          <span className="text-xs text-text-muted">
            {intro.configured ? `(${intro.ready} ready · ${intro.left_today} left today)` : "(not set up yet)"}
          </span>
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" name="batch-mode" checked={!askFirst} onChange={() => { setMode("INVITE"); setConfirming(false); }} />
          Send the invitation now
        </label>
      </fieldset>
      {askFirst ? (
        <p className="text-xs text-text-muted">
          Each verified case (S03 or S04) with a mobile and no invitation yet gets a short message about the study asking
          whether it will take part{intro.channel === "SMS" ? ", by SMS with a link to answer on WhatsApp" : ", on WhatsApp"}.
          A YES reply sends the personal invitation link automatically; NO records the refusal (S12); anything else
          goes to <Link href="/admin/conversations" className="underline">Conversations</Link>. No reply after 3 days
          gets one reminder, then the case is listed on Follow-ups to phone.
          {!intro.configured && " Not set up yet: it needs the study\u2019s WhatsApp number on Twilio (deploy/configure-twilio.sh)."}
        </p>
      ) : (
      <>
      <p className="text-xs text-text-muted">
        Verified cases (S03 or S04) with no open invitation. Each gets <strong>one</strong> invitation with its own link
        (valid 14 days) and phone code, sent on every way you choose that it has a contact for, and moves to
        &ldquo;Invitation sent&rdquo;. SMS and WhatsApp go to mobiles only and are sent by the portal through Twilio.
      </p>

      <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <legend className="text-xs text-text-muted mb-1">Send by</legend>
        {BATCH_CHANNELS.map((channel) => {
          const c = info.channels[channel];
          return (
            <label key={channel} className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={chosen.includes(channel)} onChange={() => toggle(channel)} />
              {BATCH_LABEL[channel]}
              <span className="text-xs text-text-muted">
                {c.configured ? `(${c.ready} ready · ${c.left_today} of ${c.daily_max} left today)` : "(not set up yet)"}
              </span>
            </label>
          );
        })}
      </fieldset>

      {notSetUp.length > 0 && (
        <p className="text-sm">
          {notSetUp.map((c) => BATCH_LABEL[c]).join(" and ")} {notSetUp.length === 1 ? "isn\u2019t" : "aren\u2019t"} set up on the server
          yet. The administrator runs{" "}
          <code>{notSetUp.includes("EMAIL") ? "deploy/configure-email.sh" : "deploy/configure-twilio.sh"}</code>
          {notSetUp.includes("EMAIL") && notSetUp.length > 1 ? <> and <code>deploy/configure-twilio.sh</code></> : null} first.
        </p>
      )}
      <p className="text-xs text-text-muted">
        {plural(info.candidates, "case")} can be reached by {ways || "the ways chosen"}.
        {chosen.includes("SMS") && sms.ready > 0 && ` SMS costs about US$${(sms.cost_usd_all! / sms.ready).toFixed(2)} per invitation.`}
      </p>

      {info.preview.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-muted">Next in line ({Math.min(info.preview.length, info.candidates)} shown)</summary>
          <ul className="mt-1 space-y-0.5">
            {info.preview.map((row) => (
              <li key={row.sample_id} className="break-words">
                <span className="font-mono">{row.sample_id}</span> · {row.organisation}
                {row.channels.length > 0 && ` · ${row.channels.map((c) => BATCH_LABEL[c]).join(", ")}`}
                {row.email && ` · ${row.email}`}
                {row.mobile && ` · ${row.mobile}`}
              </li>
            ))}
          </ul>
        </details>
      )}
      </>
      )}
      {error && <p className="text-danger text-sm">{error}</p>}

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
          <Button variant="outline" disabled={sending || !valid} onClick={() => setConfirming(true)}>
            Review and send
          </Button>
        </div>
      ) : (
        <div className="rounded-md border border-border p-3 space-y-2">
          <p className="text-sm">
            {askFirst
              ? `Send the introduction to ${plural(limit, "organisation")} now, in Sample ID order? Their invitation links go out only when they reply YES.`
              : `Send ${plural(limit, "invitation")} now by ${ways}, to the respondents on file, in Sample ID order?`}
            {!askFirst && smsCost > 0 && ` The SMS will cost about US$${smsCost.toFixed(2)}.`} This can&rsquo;t be undone
            {askFirst ? "." : ", but any single invitation can be revoked from its case page."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => send.mutate({ limit, asFirst: askFirst })} disabled={send.isPending}>
              {send.isPending ? "Starting…" : askFirst ? `Send ${plural(limit, "introduction")}` : `Send ${plural(limit, "invitation")}`}
            </Button>
            <Button variant="outline" onClick={() => setConfirming(false)} disabled={send.isPending}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <p className="text-xs text-text-muted">
        Day 2 and Day 7 reminders go out automatically each morning by WhatsApp or SMS once Twilio is set up; until then,
        and for anyone without a mobile, they wait on Follow-ups.
      </p>

      {latest && (
        <div className="text-sm space-y-1">
          <p>
            {sending ? "Sending…" : latest.status === "FAILED" ? "The last batch stopped early." : "Last batch:"} {latest.sent} sent,{" "}
            {latest.failed} failed, {latest.skipped} skipped of {latest.requested}
            {latest.mode === "INTRO" ? " introductions" : ""}
            {latest.channels?.length ? ` (by ${latest.channels.map((c) => BATCH_LABEL[c]).join(", ")})` : ""}.
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
        phone, WhatsApp or email on file. The AI searches public sources for each organisation&rsquo;s published phone
        number and email, and senior staff with their phone or email; nothing is saved until you accept it on the case page. Roughly US${low.toFixed(2)}–{high.toFixed(2)} per case.
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
          <p className="text-xs mt-1">
            <Link href="/admin/sample/review-findings" className="text-header underline font-medium">
              Review them all on one page
            </Link>
            <span className="text-text-muted"> with filters for phones and emails, confidence and source, or open a case below.</span>
          </p>
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
          <SendInvitationsPanel />
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
