"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, WriteOnly } from "@/components/admin/RoleGate";
import { KiiContactFinderPanel } from "@/components/admin/ContactFinderPanel";
import { InvitationSendPanel, type IssuedInvitation } from "@/components/admin/InvitationSendPanel";
import { KoboFormPanel } from "@/components/admin/KoboFormPanel";
import { InterviewSheet } from "@/components/admin/InterviewSheet";
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
  phone: string;
  whatsapp_number: string;
  email: string;
  preferred_mode: string;
  interview_date: string | null;
  duration_minutes: number | null;
  field_notes: string;
  status: string;
  transcript_status: string;
  coding_status: string;
  participation_consent_decision: string | null;
  recording_consent_decision: string | null;
  kii_form_configured: boolean;
  coding_url: string | null;
}

interface KIIInvitationTokenEntry {
  id: number;
  status: string;
  channel: string;
  issued_at: string;
  expires_at: string;
}

const OPEN_KII_TOKEN_STATUSES = ["GENERATED", "SENT", "OPENED", "CONSENTED", "STARTED"];
const KII_INVITATION_CHANNELS = ["WHATSAPP", "EMAIL", "SMS"];

const PREFERRED_MODES = [
  ["TEAMS", "Microsoft Teams"], ["ZOOM", "Zoom"], ["MEET", "Google Meet"],
  ["WHATSAPP_VOICE", "WhatsApp voice"], ["WHATSAPP_VIDEO", "WhatsApp video"],
  ["PHONE", "Phone"], ["FACE_TO_FACE", "Face to face"],
] as const;

const STATUS_OPTIONS: Record<string, string[]> = {
  PROSPECT: ["INVITED", "DECLINED"],
  // COMPLETED direct from INVITED (2026-10-01): a self-administered interview
  // (see the Invite panel below) has no call to schedule.
  INVITED: ["SCHEDULED", "DECLINED", "COMPLETED"],
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
  // null = not edited yet (show what the server has), so a detail can be cleared --
  // same reasoning as the Document record's own details form.
  const [details, setDetails] = useState<Record<string, string> | null>(null);
  const [detailsSaved, setDetailsSaved] = useState(false);

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

  const saveDetails = useMutation({
    mutationFn: () => adminFetch(`/kii/${params.id}/`, { method: "PATCH", body: JSON.stringify(details ?? {}) }),
    onSuccess: () => {
      setError(null);
      setDetails(null);
      setDetailsSaved(true);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save the details."),
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

      <Card className="space-y-3 mb-4">
        <h3 className="font-medium">Record details</h3>
        <p className="text-xs text-text-muted">Correct a mistyped name, role, category or contact detail here. Status, transcript and coding progress have their own controls below and are never changed from this form.</p>
        <WriteOnly note={null}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(
              [
                ["participant_name", "Participant name"],
                ["participant_role", "Participant role"],
                ["stakeholder_category", "Stakeholder category"],
              ] as const
            ).map(([field, label]) => (
              <div key={field}>
                <label className="block text-sm text-text-muted mb-1" htmlFor={`detail-${field}`}>{label}</label>
                <input
                  id={`detail-${field}`}
                  value={details?.[field] ?? record[field] ?? ""}
                  onChange={(e) => {
                    setDetailsSaved(false);
                    setDetails((d) => ({ ...(d ?? {}), [field]: e.target.value }));
                  }}
                  className="w-full rounded-md border border-border px-3 py-2 text-sm"
                />
              </div>
            ))}
            {(
              [
                ["phone", "Phone"],
                ["whatsapp_number", "WhatsApp number"],
              ] as const
            ).map(([field, label]) => (
              <div key={field}>
                <label className="block text-sm text-text-muted mb-1" htmlFor={`detail-${field}`}>{label}</label>
                <input
                  id={`detail-${field}`}
                  value={details?.[field] ?? record[field] ?? ""}
                  onChange={(e) => {
                    setDetailsSaved(false);
                    setDetails((d) => ({ ...(d ?? {}), [field]: e.target.value }));
                  }}
                  className="w-full rounded-md border border-border px-3 py-2 text-sm"
                />
              </div>
            ))}
            <div>
              <label className="block text-sm text-text-muted mb-1" htmlFor="detail-email">Email</label>
              <input
                id="detail-email"
                type="email"
                value={details?.email ?? record.email ?? ""}
                onChange={(e) => {
                  setDetailsSaved(false);
                  setDetails((d) => ({ ...(d ?? {}), email: e.target.value }));
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1" htmlFor="detail-preferred_mode">Preferred mode</label>
              <select
                id="detail-preferred_mode"
                value={details?.preferred_mode ?? record.preferred_mode}
                onChange={(e) => {
                  setDetailsSaved(false);
                  setDetails((d) => ({ ...(d ?? {}), preferred_mode: e.target.value }));
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm bg-surface"
              >
                {PREFERRED_MODES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1" htmlFor="detail-interview_date">Interview date</label>
              <input
                id="detail-interview_date"
                type="date"
                value={details?.interview_date ?? record.interview_date ?? ""}
                onChange={(e) => {
                  setDetailsSaved(false);
                  setDetails((d) => ({ ...(d ?? {}), interview_date: e.target.value }));
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1" htmlFor="detail-duration_minutes">Duration (minutes)</label>
              <input
                id="detail-duration_minutes"
                type="number"
                min={0}
                value={details?.duration_minutes ?? record.duration_minutes ?? ""}
                onChange={(e) => {
                  setDetailsSaved(false);
                  setDetails((d) => ({ ...(d ?? {}), duration_minutes: e.target.value }));
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-text-muted mb-1" htmlFor="detail-field_notes">Field notes</label>
              <textarea
                id="detail-field_notes"
                rows={3}
                value={details?.field_notes ?? record.field_notes ?? ""}
                onChange={(e) => {
                  setDetailsSaved(false);
                  setDetails((d) => ({ ...(d ?? {}), field_notes: e.target.value }));
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" disabled={!details || saveDetails.isPending} onClick={() => saveDetails.mutate()}>
              {saveDetails.isPending ? "Saving…" : "Save details"}
            </Button>
            {detailsSaved && <span className="text-sm text-text-muted" role="status">Details saved.</span>}
          </div>
        </WriteOnly>
      </Card>

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

      {/* CanManageKII: the PI, Field Coordinator and KII RA search and decide; the Supervisor reads. */}
      <div className="my-4">
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "KII_RA", "SUPERVISOR_READONLY"]}>
          <KiiContactFinderPanel kiiId={record.id} onChange={invalidate} />
        </IfRole>
      </div>

      <KIIInvitePanel kiiId={record.kii_id} />

      <div className="mt-4">
        {/* PROIT is the Field Coordinator's and PI's tool (api/permissions IsFieldCoordinatorOrAdmin,
            Supervisor read-only). Other roles on this page used to get a 403 from it. */}
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"]}>
          <PreProfilePanel kiiRecordId={record.id} />
        </IfRole>
        {/* The KII RA verifies the locked profile with the participant; the profile itself is the coordinator's. */}
        <IfRole roles={["KII_RA"]}>
          <InterviewSheet kiiRecordId={record.id} />
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

/**
 * The informant's own self-service link (2026-10-01): a personal link they
 * can open unsupervised, the same way a Main-400 respondent already can --
 * mirrors the sample case page's own Invitations panel, pointed at
 * kii-invitations/ instead of invitations/ (apps/kii/urls.py).
 */
function KIIInvitePanel({ kiiId }: { kiiId: string }) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState("WHATSAPP");
  const [justIssued, setJustIssued] = useState<(IssuedInvitation & { channel: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: history } = useQuery({
    queryKey: ["kii-invitations", kiiId],
    queryFn: () => adminFetch<{ results: KIIInvitationTokenEntry[] }>(`/kii-invitations/?kii_id=${kiiId}`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["kii-invitations", kiiId] });

  const issue = useMutation({
    mutationFn: () =>
      adminFetch<IssuedInvitation>("/kii-invitations/", {
        method: "POST",
        body: JSON.stringify({ kii_id: kiiId, channel, link_base: window.location.origin }),
      }),
    onSuccess: (data) => {
      setError(null);
      setJustIssued({ ...data, channel });
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to issue invitation."),
  });

  const revoke = useMutation({
    mutationFn: (tokenId: number) =>
      adminFetch(`/kii-invitations/${tokenId}/revoke/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Revoked from admin UI" }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to revoke invitation."),
  });

  const entries = history?.results ?? [];
  const hasOpenToken = entries.some((e) => OPEN_KII_TOKEN_STATUSES.includes(e.status));

  return (
    <Card className="space-y-3 mt-4">
      <h3 className="font-medium">Invite (self-service link)</h3>
      <p className="text-xs text-text-muted">
        A personal link the informant can open on their own, in their own time -- for someone who would rather
        complete the interview alone than do a live call. Needs a phone, WhatsApp number or email on file above.
      </p>
      {error && <p className="text-danger text-sm">{error}</p>}

      {justIssued && (
        <InvitationSendPanel
          key={justIssued.token_id}
          invitation={justIssued}
          preferred={justIssued.channel}
          sendEmailPath={`/kii-invitations/${justIssued.token_id}/send-email/`}
        />
      )}

      <WriteOnly>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-xs text-text-muted mb-1">Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
            >
              {KII_INVITATION_CHANNELS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <Button onClick={() => issue.mutate()} disabled={issue.isPending}>
            {issue.isPending ? "Issuing…" : hasOpenToken ? "Send new link (replaces current)" : "Send link"}
          </Button>
        </div>
      </WriteOnly>

      {entries.length > 0 && (
        <div className="border-t border-border pt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-1 pr-4">Channel</th>
                <th className="py-1 pr-4">Status</th>
                <th className="py-1 pr-4">Issued</th>
                <th className="py-1">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="py-1 pr-4">{e.channel}</td>
                  <td className="py-1 pr-4">{e.status}</td>
                  <td className="py-1 pr-4">{new Date(e.issued_at).toLocaleDateString()}</td>
                  <td className="py-1">
                    {OPEN_KII_TOKEN_STATUSES.includes(e.status) && (
                      <WriteOnly note={null}>
                        <button
                          onClick={() => revoke.mutate(e.id)}
                          disabled={revoke.isPending}
                          className="text-danger underline text-xs"
                        >
                          Revoke
                        </button>
                      </WriteOnly>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
