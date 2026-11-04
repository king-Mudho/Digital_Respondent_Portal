"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { CHANNEL_LABEL, messageParts, type Channel, type ComposerData } from "@/lib/api/communications";
import { WhatsAppTools, type SharedContact } from "./WhatsAppTools";

const ORDER: Channel[] = ["WHATSAPP", "EMAIL", "SMS"];
const KEY: Record<Channel, "whatsapp" | "sms" | "email"> = { WHATSAPP: "whatsapp", SMS: "sms", EMAIL: "email" };

export interface Draft {
  channel: Channel;
  recipient: string;
  subject: string;
  text: string;
}

/**
 * Writing to them. Each channel says whether it can be used right now and why not: WhatsApp takes a written message
 * only within 24 hours of their own last WhatsApp message (otherwise an approved message is offered instead), SMS
 * needs a registered sender, email needs an address on the record. The server checks all of this again.
 *
 * On WhatsApp the same 24 hours also allow documents, photos and videos, a voice note recorded here, and a contact
 * (2026-11-04); with files chosen, what is written becomes the caption.
 */
export function Composer({
  composer,
  sending,
  error,
  onSend,
  onAction,
  actionBusy,
  onSendFiles,
  onSendRecording,
  onShareContact,
}: {
  composer: ComposerData;
  sending: boolean;
  error: string | null;
  onSend: (draft: Draft) => Promise<boolean>;
  onAction: (key: "introduction") => void;
  actionBusy: boolean;
  onSendFiles: (files: File[], caption: string, recipient: string) => Promise<boolean>;
  onSendRecording: (blob: Blob, type: string, recipient: string) => Promise<boolean>;
  onShareContact: (contact: SharedContact, recipient: string) => Promise<boolean>;
}) {
  const firstOpen = ORDER.find((c) => composer[KEY[c]].available) ?? "WHATSAPP";
  const [channel, setChannel] = useState<Channel>(firstOpen);
  const [chosen, setRecipient] = useState("");
  const [subject, setSubject] = useState(composer.email.reply_subject ?? "");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [fileProblem, setFileProblem] = useState("");
  const option = composer[KEY[channel]];
  const media = channel === "WHATSAPP" && option.media?.available ? option.media : null;
  const withFiles = !!media && files.length > 0;
  // The chosen number or address while it is still on offer for this channel, otherwise the first one.
  const recipient = option.recipients.some((r) => r.value === chosen) ? chosen : (option.recipients[0]?.value ?? "");

  if (composer.blocked) {
    return <p className="border-t border-border bg-bg px-4 py-3 text-sm text-text-muted">{composer.blocked}</p>;
  }

  const submit = async () => {
    setFileProblem("");
    if (withFiles) {
      const ok = await onSendFiles(files, text, recipient);
      if (ok) {
        setFiles([]);
        setText("");
      }
      return;
    }
    const ok = await onSend({ channel, recipient, subject, text });
    if (ok) setText("");
  };
  const over = text.length > (withFiles ? media!.caption_max : composer.max_length);
  // WhatsApp and SMS take at most 1,600 characters a message: a longer text goes as numbered parts (2026-10-17).
  const parts = channel === "EMAIL" ? 1 : messageParts(text.length, composer.part_max);

  return (
    <div className="border-t border-border bg-surface">
      <div className="flex gap-1 overflow-x-auto px-3 pt-2" role="tablist" aria-label="Send by">
        {ORDER.map((c) => {
          const open = composer[KEY[c]].available;
          return (
            <button
              key={c}
              role="tab"
              type="button"
              aria-selected={channel === c}
              onClick={() => setChannel(c)}
              className={`shrink-0 whitespace-nowrap rounded-t-md border-b-2 px-3 py-1.5 text-xs font-medium ${
                channel === c ? "border-header text-text" : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              {CHANNEL_LABEL[c]}
              {!open && <span className="ml-1 text-text-muted">·&nbsp;unavailable</span>}
            </button>
          );
        })}
      </div>

      <div className="space-y-2 p-3">
        {!option.available ? (
          <div className="space-y-2">
            <p className="text-sm text-text-muted">
              {option.reason}
              {channel === "WHATSAPP" && option.reason.includes("24 hours") &&
                " Documents, photos, voice notes and contacts can be sent the same way once they write."}
            </p>
            {channel === "WHATSAPP" && composer.actions.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {composer.actions.map((action) =>
                  action.href ? (
                    <Link key={action.key} href={action.href} className="inline-flex min-h-9 items-center rounded-md border border-border px-3 text-sm hover:bg-bg">
                      {action.label} →
                    </Link>
                  ) : (
                    <Button key={action.key} variant="outline" className="min-h-9 py-1.5" disabled={actionBusy} onClick={() => onAction("introduction")}>
                      {actionBusy ? "Sending…" : action.label}
                    </Button>
                  ),
                )}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {option.recipients.length > 1 ? (
                <select
                  aria-label="To"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                  className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
                >
                  {option.recipients.map((r) => (
                    <option key={r.value} value={r.value}>To {r.label}</option>
                  ))}
                </select>
              ) : (
                <span className="py-1.5 text-xs text-text-muted">To {option.recipients[0]?.label}</span>
              )}
              {channel === "EMAIL" && (
                <input
                  aria-label="Subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Subject"
                  className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
                />
              )}
            </div>
            {media && (
              <WhatsAppTools
                media={media}
                files={files}
                busy={sending}
                onFiles={(next, problem) => {
                  setFiles(next);
                  setFileProblem(problem);
                }}
                onSendRecording={(blob, type) => onSendRecording(blob, type, recipient)}
                onShareContact={(contact) => onShareContact(contact, recipient)}
              />
            )}
            {fileProblem && <p role="alert" className="text-xs text-danger">{fileProblem}</p>}
            <textarea
              aria-label="Message"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && (text.trim() || withFiles) && !sending && !over) submit();
              }}
              rows={3}
              placeholder={withFiles ? "Add a caption (optional)…" : `Write a ${CHANNEL_LABEL[channel]} message…`}
              className="w-full resize-y rounded-md border border-border bg-surface px-3 py-2 text-sm"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className={`text-[11px] tabular-nums ${over ? "text-danger" : "text-text-muted"}`}>
                {text.length} / {withFiles ? media!.caption_max : composer.max_length} · Ctrl+Enter sends
                {channel === "SMS" && ` · about ${Math.max(1, Math.ceil(text.length / 153))} SMS part(s)`}
                {!withFiles && parts > 1 && ` · will be sent as ${parts} ${CHANNEL_LABEL[channel]} messages, numbered (1/${parts})…`}
              </p>
              <Button onClick={submit} disabled={sending || (!withFiles && !text.trim()) || over || !recipient} className="min-h-9 py-1.5">
                {sending ? "Sending…" : withFiles ? `Send ${files.length} file${files.length === 1 ? "" : "s"}` : `Send ${CHANNEL_LABEL[channel]}`}
              </Button>
            </div>
          </>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
