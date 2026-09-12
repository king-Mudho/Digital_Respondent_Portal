"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface SamplingDashboard {
  main_by_province: Array<{ stratum__province: string; count: number }>;
  main_by_stratum: Array<{ stratum__code: string; verified_count: number; total: number }>;
  reserve_activations_by_reason: Array<{ activation_reason: string | null; count: number }>;
}

/** docs/16_DASHBOARDS_AND_REPORTING.md "Sampling dashboard" -- aggregate
 * counts only, never an organisation name. */
export default function SamplingDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-sampling"],
    queryFn: () => adminFetch<SamplingDashboard>("/dashboards/sampling/"),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Executive Dashboard">
      <h2 className="font-semibold text-xl mb-4">Sampling Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <h3 className="font-medium mb-2">Main-400 by province</h3>
            <table className="w-full text-sm">
              <tbody>
                {data.main_by_province.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1 pr-4">{row.stratum__province}</td>
                    <td className="py-1 tabular-nums">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card>
            <h3 className="font-medium mb-2">Verified / total by stratum</h3>
            <table className="w-full text-sm">
              <tbody>
                {data.main_by_stratum.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1 pr-4 font-mono text-xs">{row.stratum__code}</td>
                    <td className="py-1 tabular-nums">
                      {row.verified_count} / {row.total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="md:col-span-2">
            <h3 className="font-medium mb-2">Reserve activations by reason</h3>
            {data.reserve_activations_by_reason.length === 0 ? (
              <p className="text-text-muted text-sm">No reserve activations yet.</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {data.reserve_activations_by_reason.map((row, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="py-1 pr-4">{row.activation_reason}</td>
                      <td className="py-1 tabular-nums">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
