"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface ExecutiveDashboard {
  quan_completed: number;
  quan_target: number;
  kii_completed: number;
  kii_target: number;
  documents_coded: number;
  documents_target_low: number;
  documents_target_high: number;
  days_remaining_to_data_lock: number;
  fieldwork_expenditure_to_date: string;
  highest_risk_coverage_gaps: Array<Record<string, unknown>>;
}

export default function ExecutiveDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-executive"],
    queryFn: () => adminFetch<ExecutiveDashboard>("/dashboards/executive/"),
  });

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">Executive Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="QUAN completed"
              value={`${data.quan_completed} / ${data.quan_target}`}
            />
            <StatCard
              label="KII completed"
              value={`${data.kii_completed} / ${data.kii_target}`}
            />
            <StatCard
              label="Documents coded"
              value={`${data.documents_coded} / ${data.documents_target_low}-${data.documents_target_high}`}
            />
            <StatCard
              label="Days to data lock"
              value={data.days_remaining_to_data_lock}
              sublabel="30 November 2026"
            />
          </div>
          <StatCard
            label="Fieldwork expenditure to date"
            value={`$${data.fieldwork_expenditure_to_date}`}
          />
          <Card>
            <h3 className="font-medium mb-2">Highest-risk coverage gaps (lowest-filled strata)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-1 pr-4">Province</th>
                    <th className="py-1 pr-4">Actor family</th>
                    <th className="py-1 pr-4">Size class</th>
                    <th className="py-1">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {data.highest_risk_coverage_gaps.map((gap, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="py-1 pr-4">{String(gap.stratum__province ?? "-")}</td>
                      <td className="py-1 pr-4">{String(gap.stratum__actor_family ?? "-")}</td>
                      <td className="py-1 pr-4">{String(gap.stratum__size_class ?? "-")}</td>
                      <td className="py-1">{String(gap.count ?? "-")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
