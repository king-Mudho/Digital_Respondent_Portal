"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface CostDashboard {
  total_cost: string;
  cost_by_category: Array<{ category: string; total: string }>;
  cost_per_qa_passed_quan: number | null;
  cost_per_completed_kii: number | null;
}

export default function CostDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-cost"],
    queryFn: () => adminFetch<CostDashboard>("/dashboards/cost/"),
  });

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">Cost Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Total spend" value={`$${data.total_cost}`} />
            <StatCard
              label="Cost per QA-passed QUAN"
              value={data.cost_per_qa_passed_quan ? `$${data.cost_per_qa_passed_quan.toFixed(2)}` : "—"}
            />
            <StatCard
              label="Cost per completed KII"
              value={data.cost_per_completed_kii ? `$${data.cost_per_completed_kii.toFixed(2)}` : "—"}
            />
          </div>
          <Card>
            <h3 className="font-medium mb-2">Spend by category</h3>
            {data.cost_by_category.length === 0 ? (
              <p className="text-text-muted text-sm">No cost events recorded yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-1 pr-4">Category</th>
                    <th className="py-1">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cost_by_category.map((c, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="py-1 pr-4">{c.category}</td>
                      <td className="py-1">${c.total}</td>
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
