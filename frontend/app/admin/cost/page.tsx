"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface CostDashboard {
  total_cost: string;
  cost_by_category: Array<{ category: string; total: string }>;
  cost_per_qa_passed_quan: number | null;
  cost_per_completed_kii: number | null;
}

const CATEGORIES = ["RA_ALLOWANCE", "AIRTIME_DATA", "TRANSPORT", "ACCOMMODATION", "HOSTING", "MESSAGING", "OTHER"];

export default function CostDashboardPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-cost"],
    queryFn: () => adminFetch<CostDashboard>("/dashboards/cost/"),
  });
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    category: "TRANSPORT",
    amount: "",
    currency: "USD",
  });

  const addCost = useMutation({
    mutationFn: () =>
      adminFetch("/costs/", {
        method: "POST",
        body: JSON.stringify({ ...form, amount: Number(form.amount) }),
      }),
    onSuccess: () => {
      setError(null);
      setForm((f) => ({ ...f, amount: "" }));
      queryClient.invalidateQueries({ queryKey: ["dashboard-cost"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to log cost."),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
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

          <WriteOnly note={null}>
          <Card className="space-y-3 max-w-md">
            <h3 className="font-medium">Log a cost event</h3>
            {error && <p className="text-danger text-sm">{error}</p>}
            <input
              type="date"
              value={form.date}
              onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
            <select
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 text-sm bg-surface"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <input
              type="number"
              step="0.01"
              placeholder="Amount"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 text-sm"
            />
            <Button onClick={() => addCost.mutate()} disabled={!form.amount || addCost.isPending}>
              {addCost.isPending ? "Logging…" : "Log cost"}
            </Button>
          </Card>
          </WriteOnly>
        </div>
      )}
    </AdminShell>
  );
}
