"use client";

import Link from "next/link";
import { IfScreen } from "@/components/admin/RoleGate";
import type { ContactCardData } from "@/lib/api/communications";

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[72px_1fr] gap-2 text-xs">
      <dt className="text-text-muted">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

/** Who this conversation is with: the organisation, its people and how to reach them, and where the case stands. */
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
        <Row label="Assigned" value={card.assigned_to} />
      </dl>
      <div className="space-y-3">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{card.people.length === 1 ? "Person" : "People"}</h4>
        {card.people.length === 0 && <p className="text-xs text-text-muted">No one is recorded yet.</p>}
        {card.people.map((p, i) => (
          <dl key={`${p.name}-${i}`} className="space-y-1 rounded-md border border-border p-2.5">
            <p className="text-sm font-medium">
              {p.name}
              {p.eligible && <span className="ml-1.5 text-[10px] font-semibold uppercase text-success">eligible</span>}
            </p>
            {p.role && <p className="text-xs text-text-muted">{p.role}</p>}
            <Row label="Phone" value={p.phone} />
            <Row label="WhatsApp" value={p.whatsapp} />
            <Row label="Email" value={p.email} />
          </dl>
        ))}
      </div>
      <IfScreen path={card.page}>
        <Link href={card.page} className="inline-block text-sm text-header underline">
          Open the {card.kind === "main" ? "case" : "KII record"} page
        </Link>
      </IfScreen>
    </div>
  );
}
