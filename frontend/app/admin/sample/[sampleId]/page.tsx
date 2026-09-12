"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface SampleCaseDetail {
  sample_id: string;
  organisation: number;
  organisation_name: string;
  organisation_master_id: string;
  stratum_code: string;
  sample_type: string;
  status: string;
  workflow_status: string | null;
}

interface ContactEvent {
  id: number;
  channel: string;
  occurred_at: string;
  outcome: string;
  notes: string;
}

// Mirrors backend/apps/sampling/services.py WORKFLOW_TRANSITIONS -- the
// frontend never invents its own transition rules, it just offers the
// options the backend will actually accept; the backend re-validates and
// rejects anything else regardless (docs/09_IDENTIFIER_AND_SAMPLING_CONTROL.md).
const WORKFLOW_TRANSITIONS: Record<string, string[]> = {
  S00: ["S01"],
  S01: ["S02", "S15"],
  S02: ["S03", "S14", "S15"],
  S03: ["S04", "S14"],
  S04: ["S05"],
  S05: ["S06", "S12", "S13"],
  S06: ["S07", "S12", "S13"],
  S07: ["S08", "S12", "S13"],
  S08: ["S09", "S10"],
  S09: ["S10"],
  S10: ["S11"],
  S12: ["S16"],
  S13: ["S16"],
  S14: ["S16"],
  S15: ["S16"],
};

const CONTACT_CHANNELS = ["WHATSAPP", "EMAIL", "PHONE", "SMS", "FACE_TO_FACE"];
const CONTACT_OUTCOMES = ["REACHED", "NO_ANSWER", "WRONG_NUMBER", "REFUSED", "RESCHEDULED", "COMPLETED"];

export default function SampleCaseDetailPage() {
  const params = useParams<{ sampleId: string }>();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [contactForm, setContactForm] = useState({ channel: "PHONE", outcome: "REACHED", notes: "" });

  const { data: sampleCase, isLoading } = useQuery({
    queryKey: ["sample-case", params.sampleId],
    queryFn: () => adminFetch<SampleCaseDetail>(`/sample-cases/${params.sampleId}/`),
  });

  const { data: contactEvents } = useQuery({
    queryKey: ["contact-events", params.sampleId],
    queryFn: () => adminFetch<{ results: ContactEvent[] }>(`/contacts/${params.sampleId}/events/`),
    enabled: !!sampleCase,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["sample-case", params.sampleId] });
    queryClient.invalidateQueries({ queryKey: ["contact-events", params.sampleId] });
  };

  const transition = useMutation({
    mutationFn: (workflow_status: string) =>
      adminFetch(`/sample-cases/${params.sampleId}/transition/`, {
        method: "POST",
        body: JSON.stringify({ workflow_status }),
      }),
    onSuccess: () => {
      setError(null);
      invalidateAll();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Transition failed."),
  });

  const addContactEvent = useMutation({
    mutationFn: () =>
      adminFetch(`/contacts/${params.sampleId}/events/`, {
        method: "POST",
        body: JSON.stringify({ ...contactForm, occurred_at: new Date().toISOString() }),
      }),
    onSuccess: () => {
      setError(null);
      setContactForm({ channel: "PHONE", outcome: "REACHED", notes: "" });
      invalidateAll();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to log contact event."),
  });

  if (isLoading || !sampleCase) {
    return (
      <AdminShell>
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  const currentStatus = sampleCase.workflow_status ?? sampleCase.status;
  const nextOptions = WORKFLOW_TRANSITIONS[currentStatus] ?? [];

  return (
    <AdminShell>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      <div className="space-y-6">
        <Card>
          <h2 className="font-semibold text-lg">{sampleCase.organisation_name}</h2>
          <dl className="grid grid-cols-2 gap-2 text-sm mt-3">
            <dt className="text-text-muted">Sample ID</dt>
            <dd className="font-mono">{sampleCase.sample_id}</dd>
            <dt className="text-text-muted">Master ID</dt>
            <dd className="font-mono">{sampleCase.organisation_master_id}</dd>
            <dt className="text-text-muted">Stratum</dt>
            <dd>{sampleCase.stratum_code}</dd>
            <dt className="text-text-muted">Type</dt>
            <dd>{sampleCase.sample_type}</dd>
            <dt className="text-text-muted">Status</dt>
            <dd>{currentStatus}</dd>
          </dl>
        </Card>

        {sampleCase.sample_type === "MAIN" && (
          <Card className="space-y-3">
            <h3 className="font-medium">Advance workflow status</h3>
            {nextOptions.length === 0 ? (
              <p className="text-text-muted text-sm">No further transitions from {currentStatus}.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {nextOptions.map((s) => (
                  <Button key={s} variant="outline" onClick={() => transition.mutate(s)}>
                    → {s}
                  </Button>
                ))}
              </div>
            )}
          </Card>
        )}

        <Card>
          <h3 className="font-medium mb-3">Contact timeline</h3>
          {!contactEvents || contactEvents.results.length === 0 ? (
            <p className="text-text-muted text-sm">No contact events recorded yet.</p>
          ) : (
            <ul className="space-y-2 text-sm mb-4">
              {contactEvents.results.map((event) => (
                <li key={event.id} className="border-t border-border pt-2">
                  <span className="font-medium">{event.channel}</span> — {event.outcome} (
                  {new Date(event.occurred_at).toLocaleString()})
                  {event.notes && <p className="text-text-muted">{event.notes}</p>}
                </li>
              ))}
            </ul>
          )}

          <div className="border-t border-border pt-4 space-y-3">
            <h4 className="text-sm font-medium">Log a contact attempt</h4>
            <div className="flex flex-wrap gap-2">
              <select
                value={contactForm.channel}
                onChange={(e) => setContactForm((f) => ({ ...f, channel: e.target.value }))}
                className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
              >
                {CONTACT_CHANNELS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                value={contactForm.outcome}
                onChange={(e) => setContactForm((f) => ({ ...f, outcome: e.target.value }))}
                className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
              >
                {CONTACT_OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
            <input
              placeholder="Notes (optional)"
              value={contactForm.notes}
              onChange={(e) => setContactForm((f) => ({ ...f, notes: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
            <Button onClick={() => addContactEvent.mutate()} disabled={addContactEvent.isPending}>
              Log contact attempt
            </Button>
          </div>
        </Card>
      </div>
    </AdminShell>
  );
}
