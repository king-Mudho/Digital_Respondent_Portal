"use client";

import { useState } from "react";
import Link from "next/link";
import { IfScreen } from "@/components/admin/RoleGate";
import { fullTime, type ContactCardData, type DialNumber } from "@/lib/api/communications";

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[84px_1fr] gap-2 text-xs">
      <dt className="text-text-muted">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return <h4 className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{children}</h4>;
}

/** One number: tap to phone it, open it in WhatsApp (to chat or call there), or copy it. */
function DialRow({ n }: { n: DialNumber }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(n.number);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard refused: the number is on screen to copy by hand */
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      <span className="font-medium tabular-nums">{n.number}</span>
      {n.tel && (
        <a href={n.tel} className="text-header underline">
          Phone
        </a>
      )}
      {n.whatsapp_link && (
        <a href={n.whatsapp_link} target="_blank" rel="noreferrer" className="text-success underline">
          WhatsApp
        </a>
      )}
      <button type="button" onClick={copy} className="text-text-muted underline">
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

/**
 * Who this conversation is with, in full (2026-11-04): the organisation and where it is, every person with every
 * number (each one a phone link, a WhatsApp link and a copy button), gatekeepers, the public contact details found
 * for them, and where they stand -- the link, consent, calls, the last message they read.
 */
export function ContactCard({ card }: { card: ContactCardData }) {
  return (
    <div className="space-y-4 p-4">
      <div>
        <p className="text-[11px] uppercase tracking-wide text-text-muted">{card.kind === "main" ? card.sample_type : "Key informant"}</p>
        <h3 className="font-semibold leading-snug">{card.organisation}</h3>
        <p className="font-mono text-xs text-text-muted">{card.ref}</p>
      </div>
      <dl className="space-y-1.5">
        <Row label="Status" value={card.status} />
        <Row label="Province" value={card.province} />
        {card.details?.map((d) => <Row key={d.label} label={d.label} value={d.value} />)}
        <Row label="Assigned" value={card.assigned_to} />
      </dl>

      <div className="space-y-3">
        <Heading>{card.people.length === 1 ? "Person" : "People"}</Heading>
        {card.people.length === 0 && <p className="text-xs text-text-muted">No one is recorded yet.</p>}
        {card.people.map((p, i) => (
          <div key={`${p.name}-${i}`} className="space-y-1.5 rounded-md border border-border p-2.5">
            <p className="text-sm font-medium">
              {p.name || "(name not recorded)"}
              {p.eligible && <span className="ml-1.5 text-[10px] font-semibold uppercase text-success">eligible</span>}
            </p>
            {p.role && <p className="text-xs text-text-muted">{p.role}</p>}
            {p.numbers && p.numbers.length > 0 ? (
              <div className="space-y-1">
                {p.numbers.map((n) => <DialRow key={n.number} n={n} />)}
              </div>
            ) : (
              <dl className="space-y-1">
                <Row label="Phone" value={p.phone} />
                <Row label="WhatsApp" value={p.whatsapp} />
              </dl>
            )}
            {!p.phone && !p.whatsapp && !p.numbers?.length && <p className="text-xs text-text-muted">No number recorded.</p>}
            {p.email && (
              <p className="break-all text-xs">
                <a href={`mailto:${p.email}`} className="underline">{p.email}</a>
              </p>
            )}
            {p.gatekeeper && <Row label="Gatekeeper" value={p.gatekeeper} />}
          </div>
        ))}
        {card.other_emails && card.other_emails.length > 0 && (
          <dl className="space-y-1">
            <Row label="Other emails" value={card.other_emails.join(", ")} />
          </dl>
        )}
      </div>

      {card.progress && card.progress.length > 0 && (
        <div className="space-y-1.5">
          <Heading>Where they stand</Heading>
          <dl className="space-y-1.5">
            {card.progress.map((row) => (
              <div key={row.label} className="grid grid-cols-[84px_1fr] gap-2 text-xs">
                <dt className="text-text-muted">{row.label}</dt>
                <dd>
                  {row.value}
                  {row.at && <span className="text-text-muted"> · {fullTime(row.at)}</span>}
                  {row.detail && <span className="block text-text-muted">{row.detail}</span>}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {(card.public_contacts || card.source_url) && (
        <div className="space-y-1.5">
          <Heading>Found publicly</Heading>
          {card.public_contacts && <p className="whitespace-pre-wrap break-words text-xs">{card.public_contacts}</p>}
          {card.source_url && /^https?:\/\//.test(card.source_url) && (
            <a href={card.source_url} target="_blank" rel="noreferrer" className="block break-all text-xs underline">
              Where it was found
            </a>
          )}
        </div>
      )}

      <IfScreen path={card.page}>
        <Link href={card.page} className="inline-block text-sm text-header underline">
          Open the {card.kind === "main" ? "case" : "KII record"} page
        </Link>
      </IfScreen>
    </div>
  );
}
