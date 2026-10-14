"use client";

import { useEffect, useRef, useState } from "react";
import { fullTime, shortTime, type EventItem, type InAttachment, type InItem, type OutItem, type TimelineItem } from "@/lib/api/communications";
import { ChannelBadge, StatusTicks } from "./Marks";

const EVENT_TONE: Record<EventItem["tone"], string> = {
  info: "text-text-muted",
  good: "text-success",
  warn: "text-warning",
  muted: "text-text-muted",
};

function dayLabel(iso: string): string {
  const when = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today.getTime() - 86400000);
  if (when.toDateString() === today.toDateString()) return "Today";
  if (when.toDateString() === yesterday.toDateString()) return "Yesterday";
  return when.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function Event({ item }: { item: EventItem }) {
  return (
    <li className="flex justify-center px-6">
      <div className="max-w-md text-center">
        <p className={`text-xs ${EVENT_TONE[item.tone]}`}>
          <span className="tabular-nums">{shortTime(item.at)}</span> · {item.text}
        </p>
        {item.detail && <p className="text-[11px] text-text-muted">{item.detail}</p>}
      </div>
    </li>
  );
}

function Outgoing({ item }: { item: OutItem }) {
  const failed = item.status === "UNDELIVERED" || item.status === "FAILED";
  return (
    <li className="flex justify-end pl-10 sm:pl-24">
      <article className="max-w-full" aria-label={`${item.purpose_label} sent ${fullTime(item.at)}`}>
        <div
          className={`rounded-2xl rounded-br-sm border px-3.5 py-2.5 text-sm ${
            failed ? "border-danger bg-surface" : "border-transparent bg-[color-mix(in_srgb,var(--color-accent)_14%,var(--color-surface))]"
          }`}
        >
          <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] text-text-muted">
            <ChannelBadge channel={item.channel} />
            <span>{item.purpose_label}</span>
            <span>· to {item.to}</span>
          </div>
          {item.subject && <p className="font-medium">{item.subject}</p>}
          <p className="whitespace-pre-wrap break-words">{item.body || <i className="text-text-muted">(text erased)</i>}</p>
        </div>
        <div className="mt-1 flex items-center justify-end gap-1.5 text-[11px] text-text-muted">
          <span title={fullTime(item.at)} className="tabular-nums">{shortTime(item.at)}</span>
          {item.by && <span>· {item.by === "automatic" ? "sent automatically" : item.by}</span>}
          <StatusTicks status={item.status} />
          <span className={failed ? "font-medium text-danger" : ""}>{item.status_label}</span>
        </div>
        {item.problem && <p className="mt-0.5 text-right text-[11px] text-danger">{item.problem}</p>}
      </article>
    </li>
  );
}

const PROXY = "/api/proxy";

/** A voice note plays here, a picture shows here, a shared contact reads as text; anything else opens in a new tab. */
export function Attachment({ attachment: a }: { attachment: InAttachment }) {
  const src = a.url ? `${PROXY}${a.url}` : "";
  return (
    <div className="mt-1.5 space-y-1">
      <p className="text-[11px] font-medium text-text-muted">{a.label}</p>
      {a.error ? (
        <p className="text-[11px] text-danger">{a.error}</p>
      ) : a.kind === "CONTACT" ? (
        <p className="whitespace-pre-wrap break-words rounded-md border border-border px-2 py-1">{a.contact || "(no details in the card)"}</p>
      ) : a.kind === "VOICE" && src ? (
        <audio controls preload="none" src={src} className="w-full max-w-xs" />
      ) : a.kind === "IMAGE" && src ? (
        <a href={src} target="_blank" rel="noreferrer">
          {/* eslint-disable-next-line @next/next/no-img-element -- a private, authenticated file, not a static asset */}
          <img src={src} alt="Picture they sent" className="max-h-60 max-w-full rounded-md border border-border" />
        </a>
      ) : src ? (
        <a href={src} target="_blank" rel="noreferrer" className="text-xs underline">Open the {a.label.toLowerCase()}</a>
      ) : null}
    </div>
  );
}

function Incoming({ item }: { item: InItem }) {
  const [showQuoted, setShowQuoted] = useState(false);
  return (
    <li className="flex justify-start pr-10 sm:pr-24">
      <article className="max-w-full" aria-label={`Message received ${fullTime(item.at)}`}>
        <div className={`rounded-2xl rounded-bl-sm border bg-surface px-3.5 py-2.5 text-sm ${item.waiting ? "border-header" : "border-border"}`}>
          <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] text-text-muted">
            <ChannelBadge channel={item.channel} />
            <span>from {item.from}</span>
            {item.reply_kind === "PHONE" ? (
              <span className="rounded-full bg-header px-1.5 font-semibold text-white">Wants to answer by phone: call them</span>
            ) : item.reply_kind && (
              <span className={`rounded-full px-1.5 font-semibold ${item.reply_kind === "YES" ? "bg-success text-white" : "bg-warning text-white"}`}>
                Said {item.reply_kind.toLowerCase()}
              </span>
            )}
          </div>
          {item.subject && <p className="font-medium">{item.subject}</p>}
          {(item.body || !item.attachments?.length) && (
            <p className="whitespace-pre-wrap break-words">{item.body || <i className="text-text-muted">(no text)</i>}</p>
          )}
          {item.attachments?.map((a) => <Attachment key={a.id} attachment={a} />)}
          {item.quoted && (
            <div className="mt-1.5">
              <button type="button" className="text-[11px] text-text-muted underline" onClick={() => setShowQuoted((s) => !s)}>
                {showQuoted ? "Hide the earlier message" : "Show the earlier message they quoted"}
              </button>
              {showQuoted && (
                <p className="mt-1 whitespace-pre-wrap break-words border-l-2 border-border pl-2 text-xs text-text-muted">{item.quoted}</p>
              )}
            </div>
          )}
          {item.has_attachments && <p className="mt-1.5 text-[11px] text-text-muted">Has attachments: open the email in Gmail to see them.</p>}
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-muted">
          <span title={fullTime(item.at)} className="tabular-nums">{shortTime(item.at)}</span>
          {item.waiting ? <span className="font-medium text-header">· waiting for an answer</span> : item.handled_by && <span>· handled by {item.handled_by}</span>}
        </div>
      </article>
    </li>
  );
}

/** Every message and event in order, grouped by day, scrolled to the newest. */
export function Timeline({ items }: { items: TimelineItem[] }) {
  const end = useRef<HTMLDivElement>(null);
  const last = items.length ? items[items.length - 1].id : "";
  useEffect(() => {
    // Scroll the conversation pane itself, never the page around it.
    const pane = end.current?.closest("[data-scroll-pane]");
    if (pane) pane.scrollTop = pane.scrollHeight;
  }, [last]);

  if (!items.length) {
    return <p className="p-6 text-center text-sm text-text-muted">Nothing has been sent or received yet.</p>;
  }
  let day = "";
  return (
    <ol className="space-y-3 p-4" aria-label="Conversation">
      {items.map((item) => {
        const label = dayLabel(item.at);
        const header = label !== day ? (day = label) : null;
        return (
          <FragmentWithDay key={item.id} day={header}>
            {item.type === "event" ? <Event item={item} /> : item.type === "out" ? <Outgoing item={item} /> : <Incoming item={item} />}
          </FragmentWithDay>
        );
      })}
      <div ref={end} />
    </ol>
  );
}

function FragmentWithDay({ day, children }: { day: string | null; children: React.ReactNode }) {
  return (
    <>
      {day && (
        <li className="flex justify-center py-1" aria-hidden>
          <span className="rounded-full border border-border bg-surface px-3 py-0.5 text-[11px] font-medium text-text-muted shadow-sm">{day}</span>
        </li>
      )}
      {children}
    </>
  );
}
