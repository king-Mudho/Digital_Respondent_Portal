"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, WriteOnly } from "@/components/admin/RoleGate";
import { KoboFormPanel } from "@/components/admin/KoboFormPanel";
import { PreProfilePanel } from "@/components/admin/PreProfilePanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";
import { PARTICIPANT_INFORMATION_SHEET_VERSION } from "@/lib/constants/participantInformation";
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
  kii_form_configured: boolean;
  coding_url: string | null;
}

const STATUS_OPTIONS: Record<string, string[]> = {
  PROSPECT: ["INVITED", "DECLINED"],
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
          // Was hardcoded "v1.0", so every KII consent record claimed a
          // version of the sheet that had not been current since the PI's
          // contact details were added. The version exists so a consent is
          // traceable to the exact wording the participant was given --
          // a stale literal defeats that entirely.
          information_sheet_version: PARTICIPANT_INFORMATION_SHEET_VERSION,
          method: "VERBAL_RA_RECORDED",
        }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  // Both of these are ordered progressions server-side and reject a
  // backwards or skipped step -- without onError the button just did
  // nothing and never said why.
  const setTranscript = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${params.id}/transcript-status/`, {
        method: "POST",
        body: JSON.stringify({ transcript_status: status }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not update the transcript status."),
  });

  const setCoding = useMutation({
    mutationFn: (status: string) =>
      adminFetch(`/kii/${params.id}/coding-status/`, {
        method: "POST",
        body: JSON.stringify({ coding_status: status }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not update the coding status."),
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
          <WriteOnly>
            <div className="flex flex-wrap gap-2">
              {(STATUS_OPTIONS[record.status] ?? []).map((next) => (
                <Button
                  key={next}
                  variant="outline"
                  disabled={setStatus.isPending}
                  onClick={() => setStatus.mutate(next)}
                >
                  {next}
                </Button>
              ))}
            </div>
            {/* COMPLETED and DECLINED are terminal -- say so rather than
                showing an empty row of buttons. */}
            {(STATUS_OPTIONS[record.status] ?? []).length === 0 && (
              <p className="text-text-muted text-sm">
                {record.status} is a final status — no further transitions.
              </p>
            )}
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
          </WriteOnly>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Consent</h3>
          <p className="text-xs text-text-muted">
            Participation and recording consent are always captured separately --
            recording consent is never inferred from participation consent.
          </p>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <WriteOnly note={null}>
                <Button
                  variant="outline"
                  disabled={setConsent.isPending}
                  onClick={() => setConsent.mutate("PARTICIPATION")}
                >
                  Record participation consent
                </Button>
              </WriteOnly>
              <span className="text-sm text-text-muted">
                Participation: {record.participation_consent_decision ?? "Not recorded"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <WriteOnly note={null}>
                <Button
                  variant="outline"
                  disabled={setConsent.isPending}
                  onClick={() => setConsent.mutate("KII_RECORDING")}
                >
                  Record recording consent
                </Button>
              </WriteOnly>
              <span className="text-sm text-text-muted">
                Recording: {record.recording_consent_decision ?? "Not recorded"}
              </span>
            </div>
          </div>
        </Card>

        <Card className="space-y-2 md:col-span-2">
          <h3 className="font-medium">Coding</h3>
          {!record.kii_form_configured ? (
            <p className="text-sm text-text-muted">
              The KII Guide link hasn&rsquo;t been set up yet (KOBO_KII_FORM_URL). Ask the
              administrator to configure it.
            </p>
          ) : record.coding_url ? (
            <>
              <p className="text-sm text-text-muted">
                Opens the KoboToolbox KII Guide with this record&rsquo;s KII-ID already filled
                in.
              </p>
              <WriteOnly>
                <a
                  href={record.coding_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors min-h-11 bg-header text-white hover:opacity-90"
                >
                  Continue this interview
                </a>
              </WriteOnly>
            </>
          ) : (
            <p className="text-sm text-text-muted">
              Record participation consent first — the interview link is withheld until then.
            </p>
          )}
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Transcript: {record.transcript_status}</h3>
          <WriteOnly>
            <div className="flex flex-wrap gap-2">
              {TRANSCRIPT_OPTIONS.map((s) => (
                <Button
                  key={s}
                  variant="outline"
                  disabled={s === record.transcript_status || setTranscript.isPending}
                  onClick={() => setTranscript.mutate(s)}
                >
                  {s}
                </Button>
              ))}
            </div>
          </WriteOnly>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">Coding: {record.coding_status}</h3>
          <WriteOnly>
            <div className="flex flex-wrap gap-2">
              {CODING_OPTIONS.map((s) => (
                <Button
                  key={s}
                  variant="outline"
                  disabled={s === record.coding_status || setCoding.isPending}
                  onClick={() => setCoding.mutate(s)}
                >
                  {s}
                </Button>
              ))}
            </div>
          </WriteOnly>
        </Card>
      </div>

      <div className="mt-4">
        {/* PROIT is the Field Coordinator's and PI's tool (api/permissions IsFieldCoordinatorOrAdmin,
            Supervisor read-only). Other roles on this page used to get a 403 from it. */}
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"]}>
          <PreProfilePanel kiiRecordId={record.id} />
        </IfRole>
      </div>
      <div className="mt-4">
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "KII_RA", "SUPERVISOR_READONLY"]}>
          <KoboFormPanel formKey="kii" record={record.kii_id} title="Completed KII form (KoboToolbox)" />
        </IfRole>
      </div>
    </AdminShell>
  );
}
