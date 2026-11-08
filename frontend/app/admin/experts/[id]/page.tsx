"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { ExpertForm, type ExpertFields } from "@/components/admin/ExpertForm";
import { InvitationSendPanel, type IssuedInvitation } from "@/components/admin/InvitationSendPanel";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { EXPERT_STATUS_TONE, type ExpertDetail, type ExpertPanel } from "@/lib/api/experts";

/** One expert: their details, their personal link (send it on WhatsApp or email), and its history. */
export default function ExpertPage() {
  return (
    <AdminShell backHref="/admin/experts" backLabel="Expert panel">
      <Expert />
    </AdminShell>
  );
}

function Expert() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<IssuedInvitation | null>(null);
  const [channel, setChannel] = useState("WHATSAPP");
  const expert = useQuery({ queryKey: ["expert", id], queryFn: () => adminFetch<ExpertDetail>(`/experts/${id}/`) });
  const panel = useQuery({ queryKey: ["experts"], queryFn: () => adminFetch<ExpertPanel>("/experts/") });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["expert", id] });
    queryClient.invalidateQueries({ queryKey: ["experts"] });
  };
  const fail = (fallback: string) => (err: unknown) => setError(err instanceof Error ? err.message : fallback);

  const save = useMutation({
    mutationFn: (body: Partial<ExpertFields> & { status?: string }) =>
      adminFetch(`/experts/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      refresh();
    },
    onError: fail("The change was not saved."),
  });
  const invite = useMutation({
    mutationFn: () =>
      adminFetch<IssuedInvitation>("/expert-invitations/", {
        method: "POST",
        body: JSON.stringify({ expert_id: id, channel, link_base: window.location.origin }),
      }),
    onSuccess: (data) => {
      setIssued(data);
      setError(null);
      refresh();
    },
    onError: fail("The link was not issued."),
  });
  const revoke = useMutation({
    mutationFn: (tokenId: number) =>
      adminFetch(`/expert-invitations/${tokenId}/revoke/`, { method: "POST", body: JSON.stringify({ reason: "Withdrawn by staff" }) }),
    onSuccess: refresh,
    onError: fail("The link was not withdrawn."),
  });

  if (expert.isLoading || !expert.data || !panel.data) return <p className="text-text-muted">Loading…</p>;
  const e = expert.data;
  const closed = panel.data.invitations_closed;
  const openToken = e.invitations.find((t) => ["SENT", "OPENED", "CONSENTED", "STARTED", "GENERATED"].includes(t.status));

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <p className="font-mono text-xs text-text-muted">{e.expert_id}</p>
        <h2 className="text-xl font-semibold">{e.full_name}</h2>
        <p className="text-sm text-text-muted">{[e.title, e.institution].filter(Boolean).join(", ")}</p>
        <p className={`text-sm font-medium ${EXPERT_STATUS_TONE[e.status]}`}>
          {e.status_label}
          {e.consent && <span className="font-normal text-text-muted"> · consent {e.consent.decision.toLowerCase()} {new Date(e.consent.at).toLocaleDateString()}</span>}
          {e.completed_at && <span className="font-normal text-text-muted"> · questionnaire received {new Date(e.completed_at).toLocaleDateString()}</span>}
        </p>
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-medium">Details</h3>
          <WriteOnly note={null}>
            {!editing && <Button variant="outline" className="min-h-9 py-1.5" onClick={() => setEditing(true)}>Edit</Button>}
          </WriteOnly>
        </div>
        {editing ? (
          <ExpertForm
            initial={e}
            panelAreas={panel.data.panel_areas}
            institutionCategories={panel.data.institution_categories}
            submitLabel="Save"
            busy={save.isPending}
            error={null}
            onSubmit={(f) => save.mutate(f)}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {[
              ["Panel area", e.panel_area_label],
              ["Experience", e.years_experience ? `${e.years_experience} years` : ""],
              ["WhatsApp", e.whatsapp_number],
              ["Phone", e.phone],
              ["Email", e.email],
              ["Conflict of interest", e.conflicts_note],
              ["Notes", e.notes],
            ].map(([label, value]) =>
              value ? (
                <div key={label} className="flex gap-2">
                  <dt className="w-36 shrink-0 text-text-muted">{label}</dt>
                  <dd className="break-words">{value}</dd>
                </div>
              ) : null,
            )}
          </dl>
        )}
      </Card>

      <WriteOnly>
        <Card className="space-y-3">
          <h3 className="font-medium">Personal link</h3>
          {e.status === "COMPLETED" ? (
            <p className="text-sm text-text-muted">Their questionnaire has arrived; no link is needed.</p>
          ) : e.status === "DECLINED" ? (
            <p className="text-sm text-text-muted">They declined. No link is sent.</p>
          ) : closed ? (
            <p className="text-sm text-text-muted">{closed}</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <select aria-label="Send by" value={channel} onChange={(ev) => setChannel(ev.target.value)} className="rounded-md border border-border bg-surface px-2 py-2 text-sm">
                <option value="WHATSAPP">WhatsApp</option>
                <option value="EMAIL">Email</option>
              </select>
              <Button onClick={() => invite.mutate()} disabled={invite.isPending}>
                {invite.isPending ? "Issuing…" : openToken ? "Send a new link (replaces the current one)" : "Send the link"}
              </Button>
            </div>
          )}
          {issued && (
            <InvitationSendPanel
              invitation={issued}
              preferred={channel}
              sendPathBase={`/expert-invitations/${issued.token_id}`}
            />
          )}
          {e.status !== "COMPLETED" && e.status !== "DECLINED" && (
            <button type="button" className="text-xs text-text-muted underline" onClick={() => save.mutate({ status: "DECLINED" })}>
              Record that they declined (e.g. by phone)
            </button>
          )}
        </Card>
      </WriteOnly>

      {e.invitations.length > 0 && (
        <Card className="space-y-2">
          <h3 className="font-medium">Link history</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-muted">
                  <th className="py-1 pr-4">Issued</th>
                  <th className="py-1 pr-4">Channel</th>
                  <th className="py-1 pr-4">Status</th>
                  <th className="py-1 pr-4">First opened</th>
                  <th className="py-1" />
                </tr>
              </thead>
              <tbody>
                {e.invitations.map((t) => (
                  <tr key={t.id} className="border-t border-border">
                    <td className="py-1 pr-4">{new Date(t.issued_at).toLocaleDateString()}</td>
                    <td className="py-1 pr-4">{t.channel}</td>
                    <td className="py-1 pr-4">{t.status_label}{t.revoked_reason && ` (${t.revoked_reason})`}</td>
                    <td className="py-1 pr-4">{t.first_opened_at ? new Date(t.first_opened_at).toLocaleString() : "—"}</td>
                    <td className="py-1 text-right">
                      {["SENT", "OPENED", "CONSENTED", "STARTED", "GENERATED"].includes(t.status) && (
                        <WriteOnly note={null}>
                          <button type="button" className="text-xs underline" onClick={() => revoke.mutate(t.id)}>Withdraw</button>
                        </WriteOnly>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
