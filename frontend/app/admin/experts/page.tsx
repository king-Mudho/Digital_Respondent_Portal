"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { ExpertForm, type ExpertFields } from "@/components/admin/ExpertForm";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { EXPERT_STATUS_TONE, type ExpertPanel, type ExpertRow } from "@/lib/api/experts";

/**
 * The ABI expert content-validation panel (backend apps/experts, 2026-11-08): twelve experts across the protocol's
 * five panel areas rate the 16 candidate ABI indicators on the KoboToolbox questionnaire. Register each expert here,
 * then send their personal link from their page; their questionnaire completes them automatically.
 */
export default function ExpertsPage() {
  return (
    <AdminShell>
      <Experts />
    </AdminShell>
  );
}

function Experts() {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["experts"], queryFn: () => adminFetch<ExpertPanel>("/experts/") });
  const register = useMutation({
    mutationFn: (fields: ExpertFields) => adminFetch<ExpertRow>("/experts/", { method: "POST", body: JSON.stringify(fields) }),
    onSuccess: () => {
      setAdding(false);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["experts"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The expert was not registered."),
  });

  if (isLoading || !data) return <p className="text-text-muted">Loading…</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <h2 className="text-xl font-semibold">Expert panel (ABI content validation)</h2>
          <p className="text-sm text-text-muted">
            Twelve experts rate the 16 candidate ABI indicators for relevance, clarity and observability. Each gets a
            personal link: they read the information, consent, and the questionnaire opens with their Expert ID filled in.
            The questionnaire carries only that ID; names and contacts stay here.
          </p>
        </div>
        <WriteOnly note={null}>
          {!adding && <Button onClick={() => setAdding(true)}>Register an expert</Button>}
        </WriteOnly>
      </div>

      {data.invitations_closed && (
        <p className="rounded-md border border-warning bg-surface px-4 py-3 text-sm">
          <span className="font-medium">Invitations are closed. </span>
          {data.invitations_closed} You can still register experts.
        </p>
      )}
      {!data.form_configured && (
        <p className="rounded-md border border-border bg-surface px-4 py-3 text-sm text-text-muted">
          The questionnaire isn&apos;t connected yet: deploy the XLSForm in KoboToolbox, then set KOBO_EXPERT_ASSET_UID and
          KOBO_EXPERT_FORM_URL on the server.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Card className="space-y-1 lg:col-span-1">
          <p className="text-xs uppercase tracking-wide text-text-muted">Completed</p>
          <p className="text-2xl font-semibold tabular-nums">{data.completed} / {data.target}</p>
        </Card>
        {data.panel.map((p) => (
          <Card key={p.area} className="space-y-1">
            <p className="text-xs leading-snug text-text-muted">{p.label}</p>
            <p className="text-lg font-semibold tabular-nums">{p.completed} / {p.target}</p>
            <p className="text-[11px] text-text-muted">{p.registered} registered · {p.invited} invited</p>
          </Card>
        ))}
      </div>

      {adding && (
        <Card className="space-y-3">
          <h3 className="font-medium">Register an expert</h3>
          <ExpertForm
            panelAreas={data.panel_areas}
            institutionCategories={data.institution_categories}
            submitLabel="Register"
            busy={register.isPending}
            error={error}
            onSubmit={(f) => register.mutate(f)}
            onCancel={() => setAdding(false)}
          />
        </Card>
      )}

      {data.results.length === 0 ? (
        <p className="text-sm text-text-muted">No experts registered yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-muted">
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Expert</th>
                <th className="px-3 py-2">Panel area</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Personal link</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.expert_id} className="border-b border-border align-top last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link href={`/admin/experts/${e.expert_id}`} className="text-header underline">{e.expert_id}</Link>
                  </td>
                  <td className="px-3 py-2">
                    <Link href={`/admin/experts/${e.expert_id}`} className="font-medium hover:underline">{e.full_name}</Link>
                    <span className="block text-xs text-text-muted">{[e.title, e.institution].filter(Boolean).join(", ")}</span>
                  </td>
                  <td className="px-3 py-2 text-xs">{e.panel_area_label}</td>
                  <td className={`px-3 py-2 text-xs font-medium ${EXPERT_STATUS_TONE[e.status]}`}>{e.status_label}</td>
                  <td className="px-3 py-2 text-xs text-text-muted">
                    {e.link ? `${e.link.status} · expires ${new Date(e.link.expires_at).toLocaleDateString()}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
