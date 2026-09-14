"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

interface Respondent {
  id: number;
  full_name: string;
  role_category: string;
  is_eligible: boolean | null;
  eligibility_checked_by: string | null;
  phone: string;
  whatsapp_number: string;
  email: string;
  gatekeeper_name: string;
  gatekeeper_contact: string;
}

const ROLE_OPTIONS: Array<[string, string]> = [
  ["", "Not known"],
  ["OWNER_FOUNDER", "Owner/founder"],
  ["CEO_MD", "CEO/MD"],
  ["FINANCE_CREDIT_RISK", "Finance/credit/risk"],
  ["OPERATIONS", "Operations"],
  ["STRATEGY_BD", "Strategy/BD"],
  ["SUPPLY_CHAIN_COMMERCIAL", "Supply chain/commercial"],
  ["OTHER_SENIOR_MANAGER", "Other senior manager"],
];

const FIELDS: Array<[keyof Respondent, string, string]> = [
  ["full_name", "Full name", "text"],
  ["phone", "Phone", "tel"],
  ["whatsapp_number", "WhatsApp number", "tel"],
  ["email", "Email", "email"],
  ["gatekeeper_name", "Gatekeeper name", "text"],
  ["gatekeeper_contact", "Gatekeeper contact", "text"],
];

type Draft = Partial<Respondent>;

function eligibilityLabel(r: Respondent) {
  if (r.is_eligible === true) return `Eligible${r.eligibility_checked_by ? ` (checked by ${r.eligibility_checked_by})` : ""}`;
  if (r.is_eligible === false) return "Not eligible";
  return "Not yet screened";
}

function RespondentForm({
  initial,
  submitLabel,
  pending,
  onSubmit,
  onCancel,
}: {
  initial: Draft;
  submitLabel: string;
  pending: boolean;
  onSubmit: (draft: Draft) => void;
  onCancel?: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(initial);
  const set = (key: keyof Respondent, value: string | boolean | null) => setDraft((d) => ({ ...d, [key]: value }));

  return (
    <form
      className="grid gap-2 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(draft);
      }}
    >
      {FIELDS.map(([key, label, type]) => (
        <label key={key} className="text-sm">
          {label}
          <input
            type={type}
            value={(draft[key] as string | undefined) ?? ""}
            onChange={(e) => set(key, e.target.value)}
            required={key === "full_name"}
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm"
          />
        </label>
      ))}
      <label className="text-sm">
        Role
        <select
          value={draft.role_category ?? ""}
          onChange={(e) => set("role_category", e.target.value)}
          className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
        >
          {ROLE_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        Eligibility
        <select
          value={draft.is_eligible === true ? "yes" : draft.is_eligible === false ? "no" : ""}
          onChange={(e) => set("is_eligible", e.target.value === "yes" ? true : e.target.value === "no" ? false : null)}
          className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
        >
          <option value="">Not yet screened</option>
          <option value="yes">Eligible (I screened them)</option>
          <option value="no">Not eligible</option>
        </select>
      </label>
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" disabled={pending || !draft.full_name?.trim()}>
          {pending ? "Saving…" : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

/**
 * The people at a case and how to reach them. Until 2026-09-14 staff could
 * not add or correct these at all -- most Main cases had no phone number, so
 * neither WhatsApp invitations nor reminders could reach them.
 */
export function RespondentsPanel({ sampleId }: { sampleId: string }) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = ["respondents", sampleId];

  const { data, isLoading } = useQuery({
    queryKey: key,
    queryFn: () => adminFetch<Respondent[]>(`/contacts/${sampleId}/respondents/`),
  });

  const save = useMutation({
    mutationFn: ({ id, draft }: { id?: number; draft: Draft }) =>
      adminFetch(id ? `/contacts/respondents/${id}/` : `/contacts/${sampleId}/respondents/`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(draft),
      }),
    onSuccess: () => {
      setError(null);
      setAdding(false);
      setEditing(null);
      queryClient.invalidateQueries({ queryKey: key });
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save the contact."),
  });

  const respondents = data ?? [];

  return (
    <section aria-labelledby={`respondents-${sampleId}`}>
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id={`respondents-${sampleId}`} className="font-medium">Respondents and contact details</h3>
        <WriteOnly note={null}>
          {!adding && (
            <Button variant="outline" onClick={() => setAdding(true)}>
              Add a person
            </Button>
          )}
        </WriteOnly>
      </div>
      {error && <p className="text-danger text-sm">{error}</p>}
      {adding && (
        <RespondentForm
          initial={{ is_eligible: null }}
          submitLabel="Save person"
          pending={save.isPending}
          onSubmit={(draft) => save.mutate({ draft })}
          onCancel={() => setAdding(false)}
        />
      )}
      {isLoading ? (
        <p className="text-text-muted text-sm">Loading…</p>
      ) : respondents.length === 0 ? (
        <p className="text-text-muted text-sm">No one recorded for this case yet.</p>
      ) : (
        <ul className="divide-y divide-border">
          {respondents.map((r) => (
            <li key={r.id} className="py-2 space-y-1">
              {editing === r.id ? (
                <RespondentForm
                  initial={r}
                  submitLabel="Save changes"
                  pending={save.isPending}
                  onSubmit={(draft) => save.mutate({ id: r.id, draft })}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="text-sm">
                    <p className="font-medium">{r.full_name}</p>
                    <p className="text-xs text-text-muted">
                      {ROLE_OPTIONS.find(([v]) => v === r.role_category)?.[1] ?? "Role not known"} ·{" "}
                      {eligibilityLabel(r)}
                    </p>
                    <p className="text-xs">
                      {[r.phone && `Phone ${r.phone}`, r.whatsapp_number && `WhatsApp ${r.whatsapp_number}`, r.email]
                        .filter(Boolean)
                        .join(" · ") || <span className="text-text-muted">No contact details</span>}
                    </p>
                    {(r.gatekeeper_name || r.gatekeeper_contact) && (
                      <p className="text-xs text-text-muted">
                        Gatekeeper: {[r.gatekeeper_name, r.gatekeeper_contact].filter(Boolean).join(", ")}
                      </p>
                    )}
                  </div>
                  <WriteOnly note={null}>
                    <Button variant="outline" onClick={() => setEditing(r.id)}>
                      Edit
                    </Button>
                  </WriteOnly>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
    </section>
  );
}
