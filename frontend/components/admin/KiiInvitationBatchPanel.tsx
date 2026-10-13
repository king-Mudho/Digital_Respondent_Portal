"use client";

import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

type Channel = "EMAIL" | "SMS" | "WHATSAPP";
type Group = "CORE_60" | "RESERVE_30" | "ADDITIONAL";
const CHANNELS: Channel[] = ["EMAIL", "SMS", "WHATSAPP"];
const CHANNEL_LABEL: Record<Channel, string> = { EMAIL: "Email", SMS: "SMS", WHATSAPP: "WhatsApp" };
const GROUPS: Group[] = ["CORE_60", "RESERVE_30", "ADDITIONAL"];
const GROUP_LABEL: Record<Group, string> = { CORE_60: "Core-60", RESERVE_30: "Reserve-30", ADDITIONAL: "Additional organisations" };

interface Batch {
  id: number;
  requested: number;
  channels?: Channel[];
  status: "RUNNING" | "DONE" | "FAILED";
  sent: number;
  failed: number;
  skipped: number;
  results: { kii_id: string; outcome: string; detail: string }[];
  error: string;
}

interface BatchInfo {
  candidates: number;
  unnamed: number;
  preview: { kii_id: string; organisation: string; informant: string; group: string; email: string; mobile: string; channels: Channel[] }[];
  groups: Record<Group, number>;
  channels: Record<Channel, { configured: boolean; ready: number; left_today: number; daily_max: number; template_waiting?: string }>;
  max_per_batch: number;
  introductions: { configured: boolean; channel: "WHATSAPP" | "SMS" | ""; ready: number; left_today: number; template_waiting: string; template_set: boolean };
  latest: Batch | null;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/**
 * Batch KII invitations (backend apps/kii/batch.py, PI request 2026-10-13), the KII counterpart of the Sample screen's
 * "Send invitations". Records never invited, from the groups chosen, Core-60 first: each gets one self-service link,
 * sent on every way chosen that it has a contact for, and moves to Invited. From there everything the informant does
 * is recorded by itself. PI and Field Coordinator only; the endpoint refuses everyone else.
 */
export function KiiInvitationBatchPanel() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"INTRO" | "INVITE" | null>(null);
  const [channels, setChannels] = useState<Channel[]>(["EMAIL"]);
  const [groups, setGroups] = useState<Group[]>(["CORE_60"]);
  const [namedOnly, setNamedOnly] = useState(false);
  const [count, setCount] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = `channels=${channels.join(",") || "EMAIL"}&groups=${groups.join(",") || GROUPS.join(",")}&named_only=${namedOnly ? 1 : 0}`;
  const { data: info } = useQuery({
    queryKey: ["kii-invitation-batch", query],
    queryFn: () => adminFetch<BatchInfo>(`/kii-invitations/batch/?${query}`),
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.latest?.status === "RUNNING" ? 3000 : false),
  });
  const send = useMutation({
    mutationFn: ({ limit, asFirst }: { limit: number; asFirst: boolean }) =>
      adminFetch<Batch>("/kii-invitations/batch/", {
        method: "POST",
        body: JSON.stringify(asFirst ? { limit, mode: "INTRO", groups, named_only: namedOnly } : { limit, channels, groups, named_only: namedOnly }),
      }),
    onSuccess: () => {
      setError(null);
      setConfirming(false);
      setCount("");
      queryClient.invalidateQueries({ queryKey: ["kii-invitation-batch"] });
      queryClient.invalidateQueries({ queryKey: ["kii-records"] });
    },
    onError: (err) => {
      setConfirming(false);
      setError(err instanceof Error ? err.message : "Could not start sending.");
    },
  });
  if (!info) return null;

  const latest = info.latest;
  const sending = latest?.status === "RUNNING";
  const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  const intro = info.introductions;
  const askFirst = (mode ?? (intro.configured ? "INTRO" : "INVITE")) === "INTRO";
  const blocked = askFirst ? [] : channels.filter((c) => !info.channels[c].configured || info.channels[c].template_waiting);
  const allowed = askFirst
    ? Math.min(info.max_per_batch, intro.ready, intro.left_today)
    : Math.min(info.max_per_batch, info.candidates, ...channels.map((c) => info.channels[c].left_today));
  const limit = Number(count || 0);
  const valid = (askFirst ? intro.configured : channels.length > 0 && blocked.length === 0) && groups.length > 0 && limit >= 1 && limit <= allowed;
  const ways = channels.map((c) => CHANNEL_LABEL[c]).join(" and ");
  const from = groups.map((g) => GROUP_LABEL[g]).join(", ");

  return (
    <Card className="mb-4 space-y-2" aria-label="Send KII invitations">
      <h3 className="font-medium text-sm">Send KII invitations</h3>
      <p className="text-xs text-text-muted">
        KII records not yet invited, with no open link. Each gets <strong>one</strong> self-service link (valid 14 days)
        and phone code, sent on every way you choose that it has a contact for, and moves to Invited. After that the
        informant&apos;s consent, fact check, KII Guide and coding are recorded by themselves. A record with no named
        informant goes to the organisation, asking for the role the study would like to interview.
      </p>

      <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <legend className="text-xs text-text-muted mb-1">How</legend>
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" name="kii-batch-mode" checked={askFirst} onChange={() => { setMode("INTRO"); setConfirming(false); }} />
          Ask first (introduction)
          <span className="text-xs text-text-muted">
            {intro.configured
              ? `(${intro.ready} ready · ${intro.left_today} left today${intro.channel === "SMS" ? " · by SMS until Meta approves the template" : ""})`
              : "(not set up yet)"}
          </span>
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" name="kii-batch-mode" checked={!askFirst} onChange={() => { setMode("INVITE"); setConfirming(false); }} />
          Send the invitation now
        </label>
      </fieldset>
      {askFirst && (
        <p className="text-xs text-text-muted">
          Each record never invited, with a mobile and no introduction yet, gets a short WhatsApp message in your name
          about a confidential interview of about 30 minutes, asking whether they will take part. A YES reply sends their
          personal link automatically and the record moves to Invited; NO records Declined; anything else goes to
          Communications. No reply after 3 days gets one reminder, then the record is listed below to phone.
          {!intro.configured && " Not set up yet: it needs the study\u2019s WhatsApp number on Twilio."}
          {intro.template_set && intro.template_waiting ? ` The KII introduction template is ${intro.template_waiting} at Meta.` : ""}
        </p>
      )}

      <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <legend className="text-xs text-text-muted mb-1">From</legend>
        {GROUPS.map((group) => (
          <label key={group} className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={groups.includes(group)} onChange={() => { setGroups(toggle(groups, group)); setConfirming(false); }} />
            {GROUP_LABEL[group]} <span className="text-xs text-text-muted">({info.groups[group]} ready)</span>
          </label>
        ))}
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={namedOnly} onChange={() => { setNamedOnly(!namedOnly); setConfirming(false); }} />
          Named informants only
        </label>
      </fieldset>

      {!askFirst && (
      <>
      <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <legend className="text-xs text-text-muted mb-1">Send by</legend>
        {CHANNELS.map((channel) => {
          const c = info.channels[channel];
          return (
            <label key={channel} className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={channels.includes(channel)} onChange={() => { setChannels(toggle(channels, channel)); setConfirming(false); }} />
              {CHANNEL_LABEL[channel]}
              <span className="text-xs text-text-muted">
                {!c.configured
                  ? "(not set up yet)"
                  : c.template_waiting
                    ? `(template ${c.template_waiting} at Meta)`
                    : `(${c.ready} ready · ${c.left_today} of ${c.daily_max} left today)`}
              </span>
            </label>
          );
        })}
      </fieldset>

      {blocked.length > 0 && (
        <p className="text-sm">
          {blocked.map((c) =>
            !info.channels[c].configured
              ? `${CHANNEL_LABEL[c]} isn’t set up on the server yet (${c === "EMAIL" ? "deploy/configure-email.sh" : "deploy/configure-twilio.sh"}).`
              : `${CHANNEL_LABEL[c]} waits for Meta to approve the KII invitation template (it is ${info.channels[c].template_waiting}).`,
          ).join(" ")}{" "}
          Untick it to send the rest.
        </p>
      )}
      <p className="text-xs text-text-muted">
        {plural(info.candidates, "record")} can be reached by {ways || "the ways chosen"}
        {info.unnamed > 0 && !namedOnly ? `, ${info.unnamed} of them with no named informant` : ""}.
      </p>

      </>
      )}
      {!askFirst && info.preview.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-muted">Next in line ({Math.min(info.preview.length, info.candidates)} shown)</summary>
          <ul className="mt-1 space-y-0.5">
            {info.preview.map((row) => (
              <li key={row.kii_id} className="break-words">
                <span className="font-mono">{row.kii_id}</span> · {row.organisation}
                {row.informant ? ` · ${row.informant}` : " · (organisation)"} · {row.group}
                {row.channels.length > 0 && ` · ${row.channels.map((c) => CHANNEL_LABEL[c]).join(", ")}`}
                {row.email && ` · ${row.email}`}
                {row.mobile && ` · ${row.mobile}`}
              </li>
            ))}
          </ul>
        </details>
      )}
      {error && <p role="alert" className="text-danger text-sm">{error}</p>}

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
              ? `Send the introduction to ${plural(limit, "informant")} now, from ${from}, in KII ID order? Their links go out only when they reply YES. This can\u2019t be undone.`
              : <>Send {plural(limit, "KII invitation")} now by {ways}, from {from}, in KII ID order? This can&rsquo;t be undone,
            but any single link can be revoked from its record page.</>}
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

      {latest && (
        <div className="text-sm space-y-1">
          <p>
            {sending ? "Sending…" : latest.status === "FAILED" ? "The last batch stopped early." : "Last batch:"} {latest.sent} sent,{" "}
            {latest.failed} failed, {latest.skipped} skipped of {latest.requested}
            {latest.channels?.length ? ` (by ${latest.channels.map((c) => CHANNEL_LABEL[c]).join(", ")})` : ""}.
          </p>
          {latest.error && <p className="text-danger text-xs">{latest.error}</p>}
          {latest.results.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-text-muted">Record by record</summary>
              <ul className="mt-1 space-y-0.5">
                {latest.results.map((row) => (
                  <li key={row.kii_id} className="break-words">
                    <span className="font-mono">{row.kii_id}</span>: {row.outcome}
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
