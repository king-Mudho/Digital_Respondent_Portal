"use client";

import { useState } from "react";
import { CHANNEL_LABEL, fullTime, type Channel, type Summary } from "@/lib/api/communications";

const STATUS_PILL: Record<string, string> = {
  approved: "bg-success text-white",
  pending: "bg-warning text-white",
  received: "bg-warning text-white",
  rejected: "bg-danger text-white",
  paused: "bg-danger text-white",
  disabled: "bg-danger text-white",
};

function Stat({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <div className="min-w-0">
      <div className={`text-lg font-semibold tabular-nums leading-tight ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-text-muted">{label}</div>
    </div>
  );
}

function ChannelCard({
  channel,
  state,
  stateTone,
  note,
  week,
  received,
  onFailed,
  children,
}: {
  channel: Channel;
  state: string;
  stateTone: "good" | "warn" | "off";
  note: React.ReactNode;
  week: Record<string, number>;
  received: number;
  onFailed: () => void;
  children?: React.ReactNode;
}) {
  const delivered = (week.DELIVERED ?? 0) + (week.READ ?? 0);
  const failed = (week.UNDELIVERED ?? 0) + (week.FAILED ?? 0);
  const sent = Object.values(week).reduce((a, b) => a + b, 0);
  const dot = stateTone === "good" ? "bg-success" : stateTone === "warn" ? "bg-warning" : "bg-border";
  const failedStat = (
    <button type="button" onClick={onFailed} className="-m-1 rounded p-1 text-left hover:bg-bg" title="Show conversations whose last message did not arrive">
      <Stat label={channel === "EMAIL" ? "Bounced" : "Not delivered"} value={failed} tone={failed ? "text-danger" : ""} />
    </button>
  );
  return (
    <section className="min-w-0 rounded-lg border border-border bg-surface p-4" aria-label={`${CHANNEL_LABEL[channel]} status`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{CHANNEL_LABEL[channel]}</h3>
        <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
          <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
          {state}
        </span>
      </div>
      <p className="mt-1 text-xs text-text-muted">{note}</p>
      <div className={`mt-3 grid gap-2 border-t border-border pt-3 ${channel === "WHATSAPP" ? "grid-cols-4" : "grid-cols-3"}`}>
        <Stat label="Sent" value={sent} />
        {channel === "EMAIL" ? <Stat label="Replies" value={received} /> : <Stat label="Delivered" value={delivered} />}
        {channel === "WHATSAPP" && <Stat label="Read" value={week.READ ?? 0} />}
        {failedStat}
      </div>
      {children}
    </section>
  );
}

/**
 * The top strip: is each channel switched on, what is holding it back, and the last seven days' messages. WhatsApp
 * shows Meta's decision on each template, read live from Twilio, because nothing can be sent first until they are
 * approved.
 */
export function ChannelHealth({ summary, onShowFailed }: { summary: Summary | undefined; onShowFailed: () => void }) {
  const [showTemplates, setShowTemplates] = useState(false);
  if (!summary) {
    return <div className="h-[132px] rounded-lg border border-border bg-surface animate-pulse" aria-label="Loading channel status" />;
  }
  const wa = summary.whatsapp;
  const templates = wa.templates.filter((t) => t.sid);
  const waState = !wa.configured ? "Not set up" : templates.length && wa.templates_approved < templates.length ? "Waiting for Meta" : "On";
  const inbox = summary.email.inbox_sync;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <ChannelCard
        channel="WHATSAPP"
        state={waState}
        stateTone={waState === "On" ? "good" : waState === "Not set up" ? "off" : "warn"}
        week={summary.week.WHATSAPP}
        received={summary.received_week.WHATSAPP}
        onFailed={onShowFailed}
        note={
          wa.configured ? (
            <>
              {templates.length ? (
                <button type="button" className="underline" onClick={() => setShowTemplates((s) => !s)} aria-expanded={showTemplates}>
                  {wa.templates_approved} of {templates.length} templates approved
                </button>
              ) : (
                "No templates set up"
              )}
              {" · "}
              {wa.left_today} of {wa.daily_max} left today
            </>
          ) : (
            "Needs the study's WhatsApp number on Twilio (deploy/configure-twilio.sh)."
          )
        }
      >
        {showTemplates && (
          <ul className="mt-3 space-y-1 border-t border-border pt-3 text-xs">
            {templates.map((t) => (
              <li key={t.sid} className="flex items-center justify-between gap-2">
                <span className="truncate" title={t.name}>{t.label}</span>
                <span className={`shrink-0 rounded-full px-2 py-px text-[10px] font-semibold uppercase ${STATUS_PILL[t.status] ?? "bg-bg border border-border"}`}>
                  {t.status}
                </span>
              </li>
            ))}
            {wa.templates_approved < templates.length && (
              <li className="pt-1 text-text-muted">
                Meta usually decides within 24 hours. Until a template is approved, messages that use it are refused.
              </li>
            )}
          </ul>
        )}
      </ChannelCard>
      <ChannelCard
        channel="SMS"
        state={summary.sms.configured ? "On" : "Off"}
        stateTone={summary.sms.configured ? "good" : "off"}
        week={summary.week.SMS}
        received={summary.received_week.SMS}
        onFailed={onShowFailed}
        note={
          summary.sms.configured
            ? `${summary.sms.left_today} of ${summary.sms.daily_max} left today`
            : "Off: Zimbabwean numbers need a registered sender name first. Replies only ever come on WhatsApp."
        }
      />
      <ChannelCard
        channel="EMAIL"
        state={summary.email.configured ? "On" : "Not set up"}
        stateTone={summary.email.configured ? (inbox.last_error ? "warn" : "good") : "off"}
        week={summary.week.EMAIL}
        received={summary.received_week.EMAIL}
        onFailed={onShowFailed}
        note={
          !inbox.configured ? (
            "Sending on. Replies stay in Gmail until reading the inbox is switched on."
          ) : inbox.last_error ? (
            <span className="text-danger">Inbox not read: {inbox.last_error}</span>
          ) : inbox.last_synced_at ? (
            `Inbox checked ${fullTime(inbox.last_synced_at)}`
          ) : (
            "Inbox not checked yet"
          )
        }
      />
    </div>
  );
}
