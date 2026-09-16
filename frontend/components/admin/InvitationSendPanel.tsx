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
  messages: { whatsapp: string; sms: string; email_subject: string; email_body: string };
}

type Channel = "whatsapp" | "sms" | "email";

const LABELS: Record<Channel, string> = { whatsapp: "WhatsApp", sms: "SMS", email: "Email" };
const linkClass = "inline-flex items-center rounded-md border border-border px-3 py-1.5 text-sm bg-surface";

/**
 * Sends a just-issued invitation with its message on any channel (added
 * 2026-09-16). The texts come from the server (invitations/messages.py), so
 * WhatsApp, SMS, email and the study-address email all say the same thing:
 * link, expiry, manual code and the study contact line.
 */
export function InvitationSendPanel({ invitation, preferred }: { invitation: IssuedInvitation; preferred?: string }) {
  // Open on the channel the RA chose when issuing it (EMAIL, SMS); WhatsApp otherwise.
  const [channel, setChannel] = useState<Channel>(
    preferred === "EMAIL" ? "email" : preferred === "SMS" ? "sms" : "whatsapp",
  );
  const [copied, setCopied] = useState(false);
  const [emailResult, setEmailResult] = useState<string | null>(null);
  const m = invitation.messages;
  const preview = channel === "email" ? `Subject: ${m.email_subject}\n\n${m.email_body}` : m[channel];

  const sendEmail = useMutation({
    mutationFn: () =>
      adminFetch<{ sent_to: string }>(`/invitations/${invitation.token_id}/send-email/`, {
        method: "POST",
        body: JSON.stringify({ link: invitation.link, manual_code: invitation.raw_manual_code }),
      }),
    onSuccess: (data) => setEmailResult(`Invitation emailed to ${data.sent_to} from the study address.`),
    onError: (err) => setEmailResult(err instanceof ApiError ? err.message : "The email could not be sent."),
  });

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

      <div className="flex flex-wrap gap-2">
        {channel === "whatsapp" && (
          <a href={wa} target="_blank" rel="noopener noreferrer" className={linkClass}>Send via WhatsApp</a>
        )}
        {channel === "sms" && <a href={sms} className={linkClass}>Send by SMS</a>}
        {channel === "email" && (
          <>
            <Button onClick={() => sendEmail.mutate()} disabled={!!emailBlocked || sendEmail.isPending || sendEmail.isSuccess}>
              {sendEmail.isPending ? "Sending…" : sendEmail.isSuccess ? "Emailed" : "Email from study address"}
            </Button>
            <a href={mailto} className={linkClass}>Open in email app</a>
          </>
        )}
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

      <p className="text-text-muted text-xs">
        {channel === "whatsapp" &&
          (invitation.whatsapp_to
            ? `Opens the chat with ${invitation.whatsapp_to_name} (+${invitation.whatsapp_to}). Send it from the study WhatsApp number.`
            : "No WhatsApp number on file, so WhatsApp will ask you to choose the chat. Add the number under Respondents and contact details.")}
        {channel === "sms" &&
          (invitation.sms_to
            ? `Opens your phone's messages app addressed to +${invitation.sms_to}. Use this on a phone.`
            : "No phone number on file; your messages app will ask for one. Use this on a phone.")}
        {channel === "email" &&
          (emailBlocked ?? `Goes to ${invitation.email_to_name} (${invitation.email_to}) from the study address, with replies to the study inbox.`)}
      </p>
      {emailResult && <p className="text-sm">{emailResult}</p>}
      <p className="text-text-muted text-xs">After sending, log it under Contact timeline.</p>
    </div>
  );
}
