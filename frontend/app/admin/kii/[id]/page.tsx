"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";
import { useState } from "react";

interface KIIRecord {
  id: number;
  kii_id: string;
  stakeholder_category: string;
  participant_name: string;
  participant_role: string;
  status: string;
  transcript_status: string;
  coding_status: string;
  participation_consent_decision: string | null;
  recording_consent_decision: string | null;
}

const STATUS_OPTIONS: Record<string, string[]> = {
  INVITED: ["SCHEDULED", "DECLINED"],
  SCHEDULED: ["COMPLETED", "NO_SHOW", "DECLINED"],
  NO_SHOW: ["SCHEDULED"],
};

const TRANSCRIPT_OPTIONS = ["NOT_STARTED", "IN_PROGRESS", "VERIFIED", "ANONYMISED"];
const CODING_OPTIONS = ["NOT_STARTED", "IN_PROGRESS", "COMPLETE"];

/**
 * A09-adjacent KII detail/workflow page: status transitions, separate
 * participation/recording consent capture, transcript and coding status --
 * docs/13_KII_MODULE.md.
 */
export default function KIIDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [withRecording, setWithRecording] = useState(false);

  const { data: record, isLoading } = useQuery({
    queryKey: ["kii-record", params.id],
    queryFn: () => adminFetch<KIIRecord>(`/kii/${params.id}/`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["kii-record", params.id] });

  const setStatus = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${params.id}/status/`, {
        method: "POST",
        body: JSON.stringify({ status, with_recording: withRecording }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const setConsent = useMutation({
    mutationFn: (consentType: "PARTICIPATION" | "KII_RECORDING") =>
      adminFetch(`/kii/${params.id}/consent/`, {
        method: "POST",
        body: JSON.stringify({
          consent_type: consentType,
          decision: "GIVEN",
          information_sheet_version: "v1.0",
          method: "VERBAL_RA_RECORDED",
        }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const setTranscript = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${params.id}/transcript-status/`, {
        method: "POST",
        body: JSON.stringify({ transcript_status: status }),
      }),
    onSuccess: invalidate,
  });

  const setCoding = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${params.id}/coding-status/`, {
        method: "POST",
        body: JSON.stringify({ coding_status: status }),
      }),
    onSuccess: invalidate,
  });

  if (isLoading || !record) {
    return (
      <AdminShell backHref="/admin/kii" backLabel="KII Register">
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  return (
    <AdminShell backHref="/admin/kii" backLabel="KII Register">
      <h2 className="font-semibold text-xl mb-1">{record.participant_name}</h2>
      <p className="text-text-muted text-sm mb-4">
        {record.kii_id} · {record.stakeholder_category} · {record.participant_role}
      </p>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <h3 className="font-medium">Status: {record.status}</h3>
          <div className="flex flex-wrap gap-2">
            {(STATUS_OPTIONS[record.status] ?? []).map((next) => (
              <Button key={next} variant="outline" onClick={() => setStatus.mutate(next)}>
                {next}
              </Button>
            ))}
          </div>
          {(STATUS_OPTIONS[record.status] ?? []).includes("COMPLETED") && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={withRecording}
                onChange={(e) => setWithRecording(e.target.checked)}
              />
              Recording made (requires separate recording consent)
            </label>
          )}
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Consent</h3>
          <p className="text-xs text-text-muted">
            Participation and recording consent are always captured separately --
            recording consent is never inferred from participation consent.
          </p>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setConsent.mutate("PARTICIPATION")}>
                Record participation consent
              </Button>
              <span className="text-sm text-text-muted">
                {record.participation_consent_decision ?? "Not recorded"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setConsent.mutate("KII_RECORDING")}>
                Record recording consent
              </Button>
              <span className="text-sm text-text-muted">
                {record.recording_consent_decision ?? "Not recorded"}
              </span>
            </div>
          </div>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Transcript: {record.transcript_status}</h3>
          <div className="flex flex-wrap gap-2">
            {TRANSCRIPT_OPTIONS.map((s) => (
              <Button key={s} variant="outline" onClick={() => setTranscript.mutate(s)}>
                {s}
              </Button>
            ))}
          </div>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Coding: {record.coding_status}</h3>
          <div className="flex flex-wrap gap-2">
            {CODING_OPTIONS.map((s) => (
              <Button key={s} variant="outline" onClick={() => setCoding.mutate(s)}>
                {s}
              </Button>
            ))}
          </div>
        </Card>
      </div>
    </AdminShell>
  );
}
