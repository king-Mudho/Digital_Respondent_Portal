"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, WriteOnly } from "@/components/admin/RoleGate";
import { PreProfilePanel } from "@/components/admin/PreProfilePanel";
import { KoboFormPanel } from "@/components/admin/KoboFormPanel";
import { RespondentsPanel } from "@/components/admin/RespondentsPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";
import { useAdminUser } from "@/lib/auth/session";

interface SampleCaseDetail {
  id: number;
  sample_id: string;
  organisation: number;
  organisation_name: string;
  organisation_master_id: string;
  stratum_code: string;
  sample_type: string;
  status: string;
  workflow_status: string | null;
  assigned_ra: number | null;
  assigned_ra_username: string | null;
  matched_case: number | null;
  matched_case_sample_id: string | null;
  matched_case_organisation_name: string | null;
}

interface ContactRA {
  id: number;
  username: string;
}

interface AvailableReserve {
  id: number;
  sample_id: string;
  organisation_name: string;
  stratum_code: string;
  same_stratum: boolean;
}

interface ContactEvent {
  id: number;
  channel: string;
  occurred_at: string;
  outcome: string;
  notes: string;
}

interface InvitationTokenEntry {
  id: number;
  status: string;
  channel: string;
  invitation_wave: number;
  issued_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoked_reason: string;
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
const INVITATION_CHANNELS = ["WHATSAPP", "EMAIL", "SMS", "PRINTED_CODE", "QR"];
// A token in any of these states is still "open" -- issuing a new one
// supersedes it, and it's still eligible for a manual revoke
// (docs/10_INVITATION_AND_CONSENT.md).
const OPEN_TOKEN_STATUSES = ["GENERATED", "SENT", "OPENED", "ELIGIBILITY_PASSED", "CONSENTED", "SURVEY_STARTED"];

/** Invitation wording sent with the link. Pending PI approval alongside the
 * reminder texts (docs/31) -- change it here, in one place. */
function invitationMessage({ link, manualCode, expiresAt }: { link: string; manualCode: string; expiresAt: string }) {
  return (
    "Hello. You are invited to take part in the ABF-FST research study at Chinhoyi University of " +
    "Technology on agribusiness financing in Zimbabwe. Taking part is voluntary.\n\n" +
    `Your personal link: ${link}\n(valid until ${new Date(expiresAt).toLocaleDateString("en-GB")})\n\n` +
    `Prefer to answer by phone? Reply to this message and quote code ${manualCode}.

` +
    // Added 2026-09-16 (PI): the portal's screens send respondents to "the
    // details in your invitation message", which had none.
    "Questions: Happyson Saina, 0773943709, abffst.research.cut@gmail.com"
  );
}

/**
 * A participant withdrew by phone, WhatsApp or in person. The server records
 * the withdrawal, revokes their invitation (which also stops reminders),
 * marks the case Refused if it hasn't submitted, and erases their contact
 * details (docs/10, docs/18). Until 2026-09-14 there was no way to do this.
 */
function WithdrawalPanel({ sampleId }: { sampleId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [method, setMethod] = useState("VERBAL_RA_RECORDED");
  const [message, setMessage] = useState<string | null>(null);
  const withdraw = useMutation({
    mutationFn: () =>
      adminFetch<{ invitations_revoked: number; moved_to_refused: boolean; respondents_contact_erased: number }>(
        `/sample-cases/${sampleId}/withdraw/`,
        { method: "POST", body: JSON.stringify({ reason: reason.trim(), method }) },
      ),
    onSuccess: (data) => {
      setReason("");
      setMessage(
        `Withdrawal recorded. ${data.invitations_revoked} invitation(s) revoked` +
          (data.moved_to_refused ? ", case marked Refused" : "") +
          `, contact details erased for ${data.respondents_contact_erased} respondent(s).`,
      );
      queryClient.invalidateQueries();
    },
    onError: (err) => setMessage(err instanceof ApiError ? err.message : "Could not record the withdrawal."),
  });

  return (
    <Card className="space-y-2">
      <h3 className="font-medium">Record a withdrawal</h3>
      <p className="text-text-muted text-xs">
        Use when the participant asks to withdraw. Their link stops working, reminders stop, and their
        phone, WhatsApp, email and gatekeeper contact are erased. This can&apos;t be undone.
      </p>
      <label className="block text-sm">
        How they told us
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="mt-1 block rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
        >
          <option value="VERBAL_RA_RECORDED">By phone or in person</option>
          <option value="WRITTEN">In writing (WhatsApp, email, letter)</option>
        </select>
      </label>
      <label className="block text-sm">
        Reason or their words
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
        />
      </label>
      <Button
        variant="outline"
        disabled={!reason.trim() || withdraw.isPending}
        onClick={() => {
          if (window.confirm("Record this participant as withdrawn? This can't be undone.")) withdraw.mutate();
        }}
      >
        {withdraw.isPending ? "Recording…" : "Record withdrawal"}
      </Button>
      {message && <p className="text-sm">{message}</p>}
    </Card>
  );
}

function InvitationsPanel({
  sampleId,
  isInvitable,
  notYetVerified,
}: {
  sampleId: string;
  isInvitable: boolean;
  notYetVerified: boolean;
}) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState("WHATSAPP");
  const [wave, setWave] = useState(1);
  const [justIssued, setJustIssued] = useState<{
    link: string;
    manualCode: string;
    expiresAt: string;
    whatsappTo: string;
    whatsappToName: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: history } = useQuery({
    queryKey: ["invitations", sampleId],
    queryFn: () => adminFetch<{ results: InvitationTokenEntry[] }>(`/invitations/?sample_id=${sampleId}`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["invitations", sampleId] });

  const issue = useMutation({
    mutationFn: () =>
      adminFetch<{
        raw_token: string;
        raw_manual_code: string;
        expires_at: string;
        whatsapp_to: string;
        whatsapp_to_name: string;
      }>("/invitations/", {
        method: "POST",
        body: JSON.stringify({ sample_id: sampleId, channel, invitation_wave: wave }),
      }),
    onSuccess: (data) => {
      setError(null);
      // The only moment this raw token/code is ever visible again -- only
      // its salted hash is persisted server-side from here on
      // (docs/10_INVITATION_AND_CONSENT.md).
      setJustIssued({
        link: `${window.location.origin}/i/${data.raw_token}`,
        manualCode: data.raw_manual_code,
        expiresAt: data.expires_at,
        whatsappTo: data.whatsapp_to,
        whatsappToName: data.whatsapp_to_name,
      });
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to issue invitation."),
  });

  const revoke = useMutation({
    mutationFn: (tokenId: number) =>
      adminFetch(`/invitations/${tokenId}/revoke/`, {
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
  const hasOpenToken = entries.some((e) => OPEN_TOKEN_STATUSES.includes(e.status));

  return (
    <Card className="space-y-3">
      <h3 className="font-medium">Invitations</h3>
      {!isInvitable && (
        <p className="text-text-muted text-xs">
          This case can&apos;t be invited right now (a locked Reserve case must be activated first).
        </p>
      )}
      {isInvitable && notYetVerified && (
        <p className="rounded-md border border-border bg-bg p-2 text-xs">
          This case hasn&apos;t reached S03 (eligible respondent identified). You can still invite it,
          but its status won&apos;t follow the respondent and no reminders will be offered until it is
          moved through verification below.
        </p>
      )}
      {error && <p className="text-danger text-sm">{error}</p>}

      {justIssued && (
        <div className="rounded-md border border-border bg-bg p-3 space-y-2 text-sm">
          <p className="font-medium">Invitation link (shown once -- copy it now)</p>
          <input
            readOnly
            value={justIssued.link}
            onFocus={(e) => e.target.select()}
            className="w-full rounded-md border border-border px-2 py-1.5 font-mono text-xs bg-surface"
          />
          <p className="text-text-muted text-xs">
            Manual code (for phone-assisted administration):{" "}
            <span className="font-mono">{justIssued.manualCode}</span> · expires{" "}
            {new Date(justIssued.expiresAt).toLocaleDateString()}
          </p>
          {/* Sending by hand until the WhatsApp Business Platform is
              connected: wa.me opens WhatsApp with the message ready, and the
              RA picks the respondent's chat. */}
          <div className="flex flex-wrap gap-2 pt-1">
            <a
              href={`https://wa.me/${justIssued.whatsappTo}?text=${encodeURIComponent(invitationMessage(justIssued))}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center rounded-md border border-border px-3 py-1.5 text-sm"
            >
              Send via WhatsApp
            </a>
            <Button
              variant="outline"
              onClick={() => navigator.clipboard?.writeText(invitationMessage(justIssued))}
            >
              Copy message
            </Button>
          </div>
          <p className="text-text-muted text-xs">
            {justIssued.whatsappTo
              ? `Opens the chat with ${justIssued.whatsappToName} (+${justIssued.whatsappTo}). Send it from the study WhatsApp number.`
              : "No WhatsApp number on file, so WhatsApp will ask you to choose the chat. Add the number under Respondents and contact details."}
          </p>
        </div>
      )}

      {isInvitable && (
        <WriteOnly>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-xs text-text-muted mb-1">Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
            >
              {INVITATION_CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Wave</label>
            <input
              type="number"
              min={1}
              value={wave}
              onChange={(e) => setWave(Number(e.target.value))}
              className="w-20 rounded-md border border-border px-2 py-1.5 text-sm"
            />
          </div>
          <Button onClick={() => issue.mutate()} disabled={issue.isPending}>
            {issue.isPending
              ? "Issuing…"
              : hasOpenToken
                ? "Send new invitation (replaces current)"
                : "Send invitation"}
          </Button>
        </div>
        </WriteOnly>
      )}

      {entries.length > 0 && (
        <div className="border-t border-border pt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-1 pr-4">Wave</th>
                <th className="py-1 pr-4">Channel</th>
                <th className="py-1 pr-4">Status</th>
                <th className="py-1 pr-4">Issued</th>
                <th className="py-1">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="py-1 pr-4">{e.invitation_wave}</td>
                  <td className="py-1 pr-4">{e.channel}</td>
                  <td className="py-1 pr-4">
                    {e.status}
                    {e.status === "REVOKED" && e.revoked_reason && (
                      <p className="text-text-muted text-xs">{e.revoked_reason}</p>
                    )}
                  </td>
                  <td className="py-1 pr-4">{new Date(e.issued_at).toLocaleDateString()}</td>
                  <td className="py-1">
                    {OPEN_TOKEN_STATUSES.includes(e.status) && (
                      <WriteOnly note={null}>
                        <Button
                          variant="outline"
                          disabled={revoke.isPending}
                          onClick={() => revoke.mutate(e.id)}
                        >
                          Revoke
                        </Button>
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

function AssignedRaPanel({ sampleCase }: { sampleCase: SampleCaseDetail }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const { data: contactRAs } = useQuery({
    queryKey: ["contact-ras"],
    queryFn: () => adminFetch<{ results: ContactRA[] }>("/auth/contact-ras/"),
  });

  const assign = useMutation({
    mutationFn: (assignedRa: number | null) =>
      adminFetch(`/sample-cases/${sampleCase.sample_id}/`, {
        method: "PATCH",
        body: JSON.stringify({ assigned_ra: assignedRa }),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["sample-case", sampleCase.sample_id] });
    },
    // A Contact RA or Supervisor opening this page sees the panel too --
    // only Field Coordinator/Admin can actually PATCH assigned_ra
    // (api.permissions.CanViewSampleCases); anyone else gets a 403 here.
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to change assignment."),
  });

  return (
    <Card className="space-y-2">
      <h3 className="font-medium">Assigned Contact RA</h3>
      {error && <p className="text-danger text-sm">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {/* Contact RA and Supervisor can see the assignment but only the
            Field Coordinator and PI may change it -- showing them a live
            dropdown just produced a 403 on the first change. */}
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR"]}>
          <select
            value={sampleCase.assigned_ra ?? ""}
            onChange={(e) => assign.mutate(e.target.value ? Number(e.target.value) : null)}
            disabled={assign.isPending}
            className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface"
          >
            <option value="">Unassigned</option>
            {(contactRAs?.results ?? []).map((ra) => (
              <option key={ra.id} value={ra.id}>
                {ra.username}
              </option>
            ))}
          </select>
        </IfRole>
        <span className="text-text-muted text-sm">
          {sampleCase.assigned_ra_username
            ? `Currently: ${sampleCase.assigned_ra_username}`
            : "Unassigned"}
        </span>
      </div>
    </Card>
  );
}

/**
 * Which Reserve case replaces this Main case if it drops out. The 400
 * pairs came from the September import; this covers an organisation added
 * afterwards, which previously meant going into Django admin.
 *
 * Only shown for MAIN cases, and only to the roles that may set it — the
 * server validates the pairing again regardless (services.set_matched_case).
 */
function MatchedCasePanel({ sampleCase }: { sampleCase: SampleCaseDetail }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  // Only the roles that can change the pairing need the candidate list; the
  // endpoint refuses everyone else, which showed up as a 403 on every case
  // page a Contact RA opened.
  const canEdit = ["PI_ADMIN", "FIELD_COORDINATOR"].includes(useAdminUser()?.role ?? "");

  const { data: candidates, isLoading } = useQuery({
    queryKey: ["available-reserves", sampleCase.sample_id],
    queryFn: () =>
      adminFetch<{ results: AvailableReserve[] }>(
        `/sample-cases/${sampleCase.sample_id}/available-reserves/`,
      ),
    enabled: canEdit,
  });

  const setMatch = useMutation({
    mutationFn: (matchedCase: number | null) =>
      adminFetch(`/sample-cases/${sampleCase.sample_id}/`, {
        method: "PATCH",
        body: JSON.stringify({ matched_case: matchedCase }),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["sample-case", sampleCase.sample_id] });
      queryClient.invalidateQueries({ queryKey: ["available-reserves", sampleCase.sample_id] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not change the matched Reserve."),
  });

  const options = candidates?.results ?? [];
  const selected = options.find((o) => o.id === sampleCase.matched_case);
  const crossStratum = selected ? !selected.same_stratum : false;

  return (
    <Card className="space-y-2">
      <h3 className="font-medium">Matched Reserve case</h3>
      <p className="text-text-muted text-xs">
        The Reserve that replaces this case if it drops out. Activating that Reserve later
        still requires an authorised reason and an evidence note.
      </p>
      {error && <p className="text-danger text-sm">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR"]}>
          <select
            value={sampleCase.matched_case ?? ""}
            disabled={setMatch.isPending || isLoading}
            onChange={(e) => setMatch.mutate(e.target.value ? Number(e.target.value) : null)}
            className="rounded-md border border-border px-2 py-1.5 text-sm bg-surface max-w-full"
          >
            <option value="">No matched Reserve</option>
            {options.map((r) => (
              <option key={r.id} value={r.id}>
                {r.sample_id} — {r.organisation_name}
                {r.same_stratum ? "" : ` (different stratum: ${r.stratum_code})`}
              </option>
            ))}
          </select>
        </IfRole>
        <span className="text-text-muted text-sm">
          {sampleCase.matched_case_sample_id
            ? `Currently: ${sampleCase.matched_case_sample_id} — ${sampleCase.matched_case_organisation_name}`
            : "No matched Reserve"}
        </span>
      </div>
      {canEdit && !isLoading && options.length === 0 && !sampleCase.matched_case && (
        <p className="text-text-muted text-xs">
          No unclaimed, still-locked Reserve cases are available to pair with.
        </p>
      )}
      {crossStratum && (
        <p className="text-warning text-xs">
          This Reserve is in a different stratum from the Main case, which weakens the
          stratified design. Intentional pairings are fine — it is recorded in the audit log.
        </p>
      )}
    </Card>
  );
}

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
      <AdminShell backHref="/admin/sample" backLabel="Main-400 Register">
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  const currentStatus = sampleCase.workflow_status ?? sampleCase.status;
  const nextOptions = WORKFLOW_TRANSITIONS[currentStatus] ?? [];

  return (
    <AdminShell backHref="/admin/sample" backLabel="Main-400 Register">
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

        <AssignedRaPanel sampleCase={sampleCase} />

        {/* Reserve cases don't have a matched Reserve of their own. */}
        {sampleCase.sample_type === "MAIN" && <MatchedCasePanel sampleCase={sampleCase} />}

        {/* PROIT is the Field Coordinator's and PI's tool (api/permissions IsFieldCoordinatorOrAdmin,
            Supervisor read-only). Other roles on this page used to get a 403 from it. */}
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"]}>
          <PreProfilePanel sampleCaseId={sampleCase.id} />
        </IfRole>

        <RespondentsPanel sampleId={sampleCase.sample_id} />

        <InvitationsPanel
          sampleId={sampleCase.sample_id}
          isInvitable={sampleCase.sample_type === "MAIN" || sampleCase.status === "ACTIVATED"}
          notYetVerified={
            sampleCase.sample_type === "MAIN" && ["S00", "S01", "S02"].includes(sampleCase.workflow_status ?? "")
          }
        />

        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "SUPERVISOR_READONLY"]}>
          <KoboFormPanel formKey="questionnaire" record={sampleCase.sample_id} title="Completed questionnaire" />
        </IfRole>

        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR"]}>
          <WithdrawalPanel sampleId={sampleCase.sample_id} />
        </IfRole>

        {sampleCase.sample_type === "MAIN" && (
          <Card className="space-y-3">
            <h3 className="font-medium">Advance workflow status</h3>
            {nextOptions.length === 0 ? (
              <p className="text-text-muted text-sm">No further transitions from {currentStatus}.</p>
            ) : (
              <WriteOnly>
                <div className="flex flex-wrap gap-2">
                  {nextOptions.map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      disabled={transition.isPending}
                      onClick={() => transition.mutate(s)}
                    >
                      → {s}
                    </Button>
                  ))}
                </div>
              </WriteOnly>
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

          <WriteOnly note={null}>
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
              {addContactEvent.isPending ? "Logging…" : "Log contact attempt"}
            </Button>
          </div>
          </WriteOnly>
        </Card>
      </div>
    </AdminShell>
  );
}
