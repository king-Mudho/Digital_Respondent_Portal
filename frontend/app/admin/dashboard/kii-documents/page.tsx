"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface KIIDocumentDashboard {
  kii_completed: number;
  kii_target: number;
  kii_by_status: Record<string, number>;
  documents_by_type: Record<string, number>;
  documents_by_qa_status: Record<string, number>;
  documents_target_low: number;
  documents_target_high: number;
}

/** docs/16_DASHBOARDS_AND_REPORTING.md "KII/document dashboard" -- counts
 * only, distinct from the KII/Document registers (which show individual
 * records to authorised internal roles). */
export default function KIIDocumentDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-kii-documents"],
    queryFn: () => adminFetch<KIIDocumentDashboard>("/dashboards/kii-documents/"),
  });

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">KII / Document Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <StatCard label="KII completed" value={`${data.kii_completed} / ${data.kii_target}`} />
            <StatCard
              label="Documents (target range)"
              value={`${data.documents_target_low}-${data.documents_target_high}`}
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <h3 className="font-medium mb-2">KII by status</h3>
              {Object.entries(data.kii_by_status).map(([k, v]) => (
                <p key={k} className="text-sm">
                  {k}: <span className="tabular-nums">{v}</span>
                </p>
              ))}
            </Card>
            <Card>
              <h3 className="font-medium mb-2">Documents by type</h3>
              {Object.entries(data.documents_by_type).map(([k, v]) => (
                <p key={k} className="text-sm">
                  {k}: <span className="tabular-nums">{v}</span>
                </p>
              ))}
            </Card>
            <Card>
              <h3 className="font-medium mb-2">Documents by QA status</h3>
              {Object.entries(data.documents_by_qa_status).map(([k, v]) => (
                <p key={k} className="text-sm">
                  {k}: <span className="tabular-nums">{v}</span>
                </p>
              ))}
            </Card>
          </div>
        </div>
      )}
    </AdminShell>
  );
}
