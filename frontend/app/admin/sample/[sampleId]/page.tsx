"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
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
  activation_reason: string | null;
  activated_at: string | null;
}

interface ContactEvent {
  id: number;
  channel: string;
  occurred_at: string;
  outcome: string;
  notes: string;
}

export default function SampleCaseDetailPage() {
  const params = useParams<{ sampleId: string }>();

  const { data: sampleCase, isLoading } = useQuery({
    queryKey: ["sample-case", params.sampleId],
    queryFn: () => adminFetch<SampleCaseDetail>(`/sample-cases/${params.sampleId}/`),
  });

  const { data: contactEvents } = useQuery({
    queryKey: ["contact-events", params.sampleId],
    queryFn: () => adminFetch<{ results: ContactEvent[] }>(`/contacts/${params.sampleId}/events/`),
    enabled: !!sampleCase,
  });

  return (
    <AdminShell>
      {isLoading || !sampleCase ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
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
              <dd>{sampleCase.workflow_status ?? sampleCase.status}</dd>
            </dl>
          </Card>

          <Card>
            <h3 className="font-medium mb-3">Contact timeline</h3>
            {!contactEvents || contactEvents.results.length === 0 ? (
              <p className="text-text-muted text-sm">No contact events recorded yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {contactEvents.results.map((event) => (
                  <li key={event.id} className="border-t border-border pt-2">
                    <span className="font-medium">{event.channel}</span> — {event.outcome} (
                    {new Date(event.occurred_at).toLocaleString()})
                    {event.notes && <p className="text-text-muted">{event.notes}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
