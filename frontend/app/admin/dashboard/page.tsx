"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfScreen } from "@/components/admin/RoleGate";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { withPilot } from "@/lib/api/pilot";

// The sub-dashboards all link back here, so link forward to them too --
// each only for the roles that hold it.
const SUB_DASHBOARDS = [
  { path: "/admin/dashboard/sampling", label: "Sampling" },
  { path: "/admin/dashboard/contact", label: "Contact" },
  { path: "/admin/dashboard/qa", label: "QA" },
  { path: "/admin/dashboard/kii-documents", label: "KII / Documents" },
  { path: "/admin/cost", label: "Cost" },
];

interface ExecutiveDashboard {
  quan_completed: number;
  quan_target: number;
  kii_completed: number;
  kii_target: number;
  documents_coded: number;
  documents_target: number;
  /** The ZAS 2026 pilot strand, counted beside the main study (2026-11-08). */
  quan_pilot?: number;
  kii_pilot?: number;
  documents_pilot?: number;
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
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">Executive Dashboard</h2>
        <div className="flex items-center gap-3 flex-wrap text-sm">
          {SUB_DASHBOARDS.map(({ path, label }) => (
            <IfScreen key={path} path={path}>
              <Link href={path} className="text-header underline">
                {label}
              </Link>
            </IfScreen>
          ))}
        </div>
      </div>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {(
              [
                ["QUAN completed", withPilot(data.quan_completed, data.quan_pilot), data.quan_target],
                ["KII completed", withPilot(data.kii_completed, data.kii_pilot), data.kii_target],
                ["Documents coded", withPilot(data.documents_coded, data.documents_pilot), data.documents_target],
              ] as const
            ).map(([label, count, target]) => (
              <StatCard key={label} label={label} value={`${count.total} / ${target}`} sublabel={count.split || undefined} />
            ))}
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
