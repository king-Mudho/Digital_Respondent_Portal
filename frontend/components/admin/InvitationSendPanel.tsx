"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

/** What POST /invitations/ returns: the link exists only in this response. */
export interface IssuedInvitation {
  token_id: number;
  raw_manual_code: string;
  expires_at: string;
  link: string;
  whatsapp_to: string;
  whatsapp_to_name: string;
  sms_to: string;
  email_to: string;
  email_to_name: string;
  email_configured: boolean;
  /** Twilio (backend apps/messaging/twilio_client.py): the portal can send the SMS / WhatsApp itself. */
  sms_configured?: boolean;
  whatsapp_configured?: boolean;
  messages: { whatsapp: string; sms: string; email_subject: string; email_body: string };
}

type TextChannel = "sms" | "whatsapp";
const TEXT_LABEL: Record<TextChannel, string> = { sms: "SMS", whatsapp: "WhatsApp" };

type Channel = "whatsapp" | "sms" | "email";

const LABELS: Record<Channel, string> = { whatsapp: "WhatsApp", sms: "SMS", email: "Email" };
const linkClass = "inline-flex items-center rounded-md border border-border px-3 py-1.5 text-sm bg-surface";

/**
 * Sends a just-issued invitation with its message on every channel (added
 * 2026-09-16). Every channel's send button shows at once, and the tabs only
 * switch the message preview: until 2026-10-06 each button sat behind its own
 * tab, so an RA who sent on WhatsApp and closed the page had to issue a second
 * invitation to email it, and the WhatsApp link stopped working. The texts come from the server (invitations/messages.py), so
 * WhatsApp, SMS, email and the study-address email all say the same thing:
 * link, expiry, manual code and the study contact line.
 *
 * `sendPathBase` defaults to the Main-400 endpoints (`/invitations/{id}`); the
 * KII invite panel (2026-10-01) passes `/kii-invitations/{id}` -- same response
 * shape (apps/kii/messages.py mirrors apps/invitations/messages.py), so this
 * one component serves both rather than a near-duplicate copy.
 *
 * Once Twilio is set up (2026-10-07) the portal can also send the SMS and the
 * WhatsApp itself, with delivery reported back on the invitation history.
 */
export function InvitationSendPanel({
  invitation, preferred, sendPathBase,
}: {
  invitation: IssuedInvitation;
  preferred?: string;
  sendPathBase?: string;
}) {
  const base = sendPathBase ?? `/invitations/${invitation.token_id}`;
  // Open on the channel the RA chose when issuing it (EMAIL, SMS); WhatsApp otherwise.
  const [channel, setChannel] = useState<Channel>(
    preferred === "EMAIL" ? "email" : preferred === "SMS" ? "sms" : "whatsapp",
  );
  const [copied, setCopied] = useState(false);
  const [emailResult, setEmailResult] = useState<string | null>(null);
  const [textResult, setTextResult] = useState<Partial<Record<TextChannel, string>>>({});
  const [textSent, setTextSent] = useState<Partial<Record<TextChannel, boolean>>>({});
  const m = invitation.messages;
  const preview = channel === "email" ? `Subject: ${m.email_subject}\n\n${m.email_body}` : m[channel];

  const sendEmail = useMutation({
    mutationFn: () =>
      adminFetch<{ sent_to: string }>(`${base}/send-email/`, {
        method: "POST",
        body: JSON.stringify({ link: invitation.link, manual_code: invitation.raw_manual_code }),
      }),
    onSuccess: (data) => setEmailResult(`Invitation emailed to ${data.sent_to} from the study address.`),
    onError: (err) => setEmailResult(err instanceof ApiError ? err.message : "The email could not be sent."),
  });

  const sendText = useMutation({
    mutationFn: (via: TextChannel) =>
      adminFetch<{ sent_to: string; status: string }>(`${base}/send-${via}/`, {
        method: "POST",
        body: JSON.stringify({ link: invitation.link, manual_code: invitation.raw_manual_code }),
      }).then((data) => ({ via, data })),
    onSuccess: ({ via, data }) => {
      setTextSent((s) => ({ ...s, [via]: true }));
      setTextResult((r) => ({
        ...r,
        [via]: `${TEXT_LABEL[via]} sent from the portal to ${data.sent_to}. Delivery shows on the invitation history once Twilio reports it.`,
      }));
    },
    onError: (err, via) =>
      setTextResult((r) => ({ ...r, [via]: err instanceof ApiError ? err.message : `The ${TEXT_LABEL[via]} could not be sent.` })),
  });
  const textOn: TextChannel[] = [
    ...(invitation.sms_configured ? (["sms"] as const) : []),
    ...(invitation.whatsapp_configured ? (["whatsapp"] as const) : []),
  ];
  const noMobile = (via: TextChannel) => !(via === "sms" ? invitation.sms_to : invitation.whatsapp_to);

  const wa = `https://wa.me/${invitation.whatsapp_to}?text=${encodeURIComponent(m.whatsapp)}`;
  const sms = `sms:${invitation.sms_to ? `+${invitation.sms_to}` : ""}?&body=${encodeURIComponent(m.sms)}`;
  const mailto = `mailto:${invitation.email_to}?subject=${encodeURIComponent(m.email_subject)}&body=${encodeURIComponent(m.email_body)}`;
  const emailBlocked = !invitation.email_to
    ? "No email address on file. Add one under Respondents and contact details."
    : !invitation.email_configured
      ? "Email isn't set up on the server yet. Use \"Open in email app\"."
      : null;

  return (
    <div className="rounded-md border border-border bg-bg p-3 space-y-3 text-sm">
      <div className="space-y-1">
        <p className="font-medium">Invitation link (shown once -- send it now)</p>
        <input
          readOnly
          aria-label="Invitation link"
          value={invitation.link}
          onFocus={(e) => e.target.select()}
          className="w-full rounded-md border border-border px-2 py-1.5 font-mono text-xs bg-surface"
        />
        <p className="text-text-muted text-xs">
          Manual code (for phone-assisted administration): <span className="font-mono">{invitation.raw_manual_code}</span> ·
          expires {new Date(invitation.expires_at).toLocaleDateString()}
        </p>
      </div>

      <div className="space-y-1">
        <div role="tablist" aria-label="Message for" className="flex flex-wrap gap-1">
          {(Object.keys(LABELS) as Channel[]).map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={channel === key}
              onClick={() => { setChannel(key); setCopied(false); }}
              className={`rounded-md border px-3 py-1 text-xs ${channel === key ? "border-header bg-header text-white" : "border-border bg-surface"}`}
            >
              {LABELS[key]} message
            </button>
          ))}
        </div>
        <textarea
          readOnly
          aria-label="Message preview"
          value={preview}
          rows={Math.max(6, Math.min(18, preview.split("\n").length + 2))}
          className="w-full rounded-md border border-border px-2 py-1.5 text-xs bg-surface"
        />
      </div>

      <p className="text-xs font-medium">
        Send it on every channel they use, now: it is the same link on WhatsApp, SMS and email, and it can&apos;t be
        shown again once you leave this page.
      </p>
      <div className="flex flex-wrap gap-2">
        <a href={wa} target="_blank" rel="noopener noreferrer" className={linkClass}>Send via WhatsApp</a>
        <Button onClick={() => sendEmail.mutate()} disabled={!!emailBlocked || sendEmail.isPending || sendEmail.isSuccess}>
          {sendEmail.isPending ? "Sending…" : sendEmail.isSuccess ? "Emailed" : "Email from study address"}
        </Button>
        <a href={mailto} className={linkClass}>Open in email app</a>
        <a href={sms} className={linkClass}>Send by SMS</a>
        <Button
          variant="outline"
          onClick={() => {
            navigator.clipboard?.writeText(channel === "email" ? preview : m[channel]);
            setCopied(true);
          }}
        >
          {copied ? "Copied" : "Copy message"}
        </Button>
      </div>

      {textOn.length > 0 && (
        <div className="space-y-1" aria-label="Send from the portal">
          <p className="text-xs font-medium">Or let the portal send it (through Twilio), and see whether it was delivered:</p>
          <div className="flex flex-wrap gap-2">
            {textOn.map((via) => (
              <Button
                key={via}
                variant="outline"
                onClick={() => sendText.mutate(via)}
                disabled={noMobile(via) || sendText.isPending || !!textSent[via]}
              >
                {textSent[via] ? `${TEXT_LABEL[via]} sent` : `Send ${TEXT_LABEL[via]} from the portal`}
              </Button>
            ))}
          </div>
          {textOn.some(noMobile) && (
            <p className="text-text-muted text-xs">No mobile number on file, so the portal can&apos;t send SMS or WhatsApp.</p>
          )}
          {textOn.map((via) => textResult[via] && <p key={via} className="text-sm">{textResult[via]}</p>)}
        </div>
      )}

      <p className="text-text-muted text-xs space-y-1">
        <span className="block">
          WhatsApp:{" "}
          {invitation.whatsapp_to
            ? `Opens the chat with ${invitation.whatsapp_to_name} (+${invitation.whatsapp_to}). Send it from the study WhatsApp number.`
            : "No mobile number on file (a landline can't receive WhatsApp), so WhatsApp will ask you to choose the chat. Add a mobile under Respondents and contact details, or phone them."}
        </span>
        <span className="block">
          Email:{" "}
          {emailBlocked ?? `Goes to ${invitation.email_to_name} (${invitation.email_to}) from the study address, with replies to the study inbox.`}
        </span>
        {channel === "sms" &&
          (invitation.sms_to
            ? `Opens your phone's messages app addressed to +${invitation.sms_to}. Use this on a phone.`
            : "No mobile number on file (a landline can't receive SMS); your messages app will ask for one. Use this on a phone.")}
      </p>
      {emailResult && <p className="text-sm">{emailResult}</p>}
      <p className="text-text-muted text-xs">After sending, log it under Contact timeline.</p>
    </div>
  );
}

/** One message the portal sent for an invitation through Twilio, as the invitation history returns it. */
export interface Delivery {
  channel: "SMS" | "WHATSAPP";
  status: "QUEUED" | "SENT" | "DELIVERED" | "READ" | "UNDELIVERED" | "FAILED";
  to: string;
  sent_at: string;
  error: string;
}

const DELIVERY_WORDS: Record<Delivery["status"], string> = {
  QUEUED: "sending", SENT: "sent", DELIVERED: "delivered", READ: "read", UNDELIVERED: "not delivered", FAILED: "failed",
};

/** Under an invitation's status: each SMS / WhatsApp the portal sent for it and what Twilio reported. */
export function DeliveryList({ deliveries }: { deliveries?: Delivery[] }) {
  if (!deliveries?.length) return null;
  return (
    <ul className="text-xs text-text-muted">
      {deliveries.map((d, i) => (
        <li key={i} className={d.status === "UNDELIVERED" || d.status === "FAILED" ? "text-danger" : undefined}>
          {d.channel === "SMS" ? "SMS" : "WhatsApp"} to {d.to}: {DELIVERY_WORDS[d.status]}
          {d.error ? ` (${d.error})` : ""}
        </li>
      ))}
    </ul>
  );
}
