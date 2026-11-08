"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { ExpertRow } from "@/lib/api/experts";

export type ExpertFields = Pick<
  ExpertRow,
  "full_name" | "title" | "institution" | "institution_category" | "panel_area" | "phone" | "whatsapp_number" | "email" | "conflicts_note" | "notes"
> & { years_experience: string };

const EMPTY: ExpertFields = {
  full_name: "", title: "", institution: "", institution_category: "", panel_area: "", years_experience: "", phone: "",
  whatsapp_number: "", email: "", conflicts_note: "", notes: "",
};

const input = "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm";

/** An expert's details: who they are, their panel area, how to reach them, and any conflict of interest. */
export function ExpertForm({
  initial,
  panelAreas,
  institutionCategories,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Partial<ExpertRow>;
  panelAreas: { value: string; label: string }[];
  institutionCategories: { value: string; label: string }[];
  submitLabel: string;
  busy: boolean;
  error: string | null;
  onSubmit: (fields: ExpertFields) => void;
  onCancel?: () => void;
}) {
  const [f, setF] = useState<ExpertFields>({
    ...EMPTY,
    ...Object.fromEntries(Object.entries(initial ?? {}).filter(([k, v]) => k in EMPTY && v != null).map(([k, v]) => [k, String(v)])),
  });
  const set = (key: keyof ExpertFields) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(f);
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span>Full name *</span>
          <input className={input} value={f.full_name} onChange={set("full_name")} required />
        </label>
        <label className="space-y-1 text-sm">
          <span>Panel area *</span>
          <select className={input} value={f.panel_area} onChange={set("panel_area")} required>
            <option value="">Choose…</option>
            {panelAreas.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>Position / title</span>
          <input className={input} value={f.title} onChange={set("title")} />
        </label>
        <label className="space-y-1 text-sm">
          <span>Institution</span>
          <input className={input} value={f.institution} onChange={set("institution")} />
        </label>
        <label className="space-y-1 text-sm">
          <span>Institution category</span>
          <select className={input} value={f.institution_category} onChange={set("institution_category")}>
            <option value="">—</option>
            {institutionCategories.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>Years of relevant experience</span>
          <input className={input} value={f.years_experience} onChange={set("years_experience")} inputMode="numeric" />
        </label>
        <label className="space-y-1 text-sm">
          <span>WhatsApp number</span>
          <input className={input} value={f.whatsapp_number} onChange={set("whatsapp_number")} inputMode="tel" />
        </label>
        <label className="space-y-1 text-sm">
          <span>Phone</span>
          <input className={input} value={f.phone} onChange={set("phone")} inputMode="tel" />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span>Email</span>
          <input className={input} type="email" value={f.email} onChange={set("email")} />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span>Conflict of interest (disclosed)</span>
          <textarea className={input} rows={2} value={f.conflicts_note} onChange={set("conflicts_note")} />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span>Notes</span>
          <textarea className={input} rows={2} value={f.notes} onChange={set("notes")} />
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={busy || !f.full_name.trim() || !f.panel_area}>
          {busy ? "Saving…" : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        )}
      </div>
    </form>
  );
}
