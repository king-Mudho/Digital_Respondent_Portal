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
  cost_by_category: Array<{ category: string; label?: string; total: string; count?: number }>;
  cost_per_qa_passed_quan: number | null;
  cost_per_completed_kii: number | null;
}

interface CostEntry {
  id: number;
  date: string;
  category: string;
  category_label: string;
  description: string;
  paid_to: string;
  amount: string;
  currency: string;
  recorded_by: string;
}

interface CostList {
  results: CostEntry[];
  count: number;
  total: string;
}

// Same labels as apps/costs/models.py CostCategory.
const CATEGORIES: Array<[string, string]> = [
  ["RA_ALLOWANCE", "RA allowance"],
  ["AIRTIME_DATA", "Airtime / data"],
  ["TRANSPORT", "Transport"],
  ["ACCOMMODATION", "Accommodation"],
  ["HOSTING", "Hosting"],
  ["MESSAGING", "Messaging"],
  ["SOFTWARE_AI", "Software / AI tools"],
  ["OTHER", "Other"],
];

const today = () => new Date().toISOString().slice(0, 10);
const EMPTY = { date: today(), category: "SOFTWARE_AI", description: "", paid_to: "", amount: "" };

function money(value: string | number) {
  return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function downloadCsv(rows: CostEntry[], total: string) {
  const esc = (v: string) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [
    ["Date", "Category", "What it was for", "Paid to", "Amount (USD)", "Recorded by"].map(esc).join(","),
    ...rows.map((r) => [r.date, r.category_label, r.description, r.paid_to, r.amount, r.recorded_by].map(esc).join(",")),
    ["", "", "", "Total", total, ""].map(esc).join(","),
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ABF-FST_costs_${today()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function CostDashboardPage() {
  const queryClient = useQueryClient();
  const [month, setMonth] = useState("");
  const [category, setCategory] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-cost"],
    queryFn: () => adminFetch<CostDashboard>("/dashboards/cost/"),
  });
  const params = new URLSearchParams();
  if (month) params.set("month", month);
  if (category) params.set("category", category);
  const list = useQuery({
    queryKey: ["costs", month, category],
    queryFn: () => adminFetch<CostList>(`/costs/${params.toString() ? `?${params}` : ""}`),
    retry: false,
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["dashboard-cost"] });
    queryClient.invalidateQueries({ queryKey: ["costs"] });
  };
  const failed = (err: unknown, fallback: string) => setError(err instanceof ApiError ? err.message : fallback);

  const save = useMutation({
    mutationFn: () =>
      adminFetch(editing ? `/costs/${editing}/` : "/costs/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify({ ...form, amount: Number(form.amount) }),
      }),
    onSuccess: () => {
      setError(null);
      setNotice(editing ? "Cost corrected." : "Cost recorded.");
      setEditing(null);
      setForm({ ...EMPTY, date: form.date, category: form.category });
      refresh();
    },
    onError: (err) => failed(err, "The cost could not be saved."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => adminFetch(`/costs/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setError(null);
      setNotice("Cost entry deleted.");
      refresh();
    },
    onError: (err) => failed(err, "The cost could not be deleted."),
  });

  const startEdit = (row: CostEntry) => {
    setEditing(row.id);
    setNotice(null);
    setError(null);
    setForm({ date: row.date, category: row.category, description: row.description, paid_to: row.paid_to, amount: row.amount });
  };
  const rows = list.data?.results ?? [];
  const forbidden = list.error instanceof ApiError && list.error.status === 403;
  const field = "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm";

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="mb-4 text-xl font-semibold">Cost Dashboard</h2>
      {isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Total spend" value={money(data.total_cost)} />
            <StatCard
              label="Cost per QA-passed QUAN"
              value={data.cost_per_qa_passed_quan ? money(data.cost_per_qa_passed_quan) : "—"}
            />
            <StatCard
              label="Cost per completed KII"
              value={data.cost_per_completed_kii ? money(data.cost_per_completed_kii) : "—"}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
            <Card>
              <h3 className="mb-2 font-medium">Spend by category</h3>
              {data.cost_by_category.length === 0 ? (
                <p className="text-sm text-text-muted">No costs recorded yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-text-muted">
                      <th className="py-1 pr-4 font-medium">Category</th>
                      <th className="py-1 pr-4 text-right font-medium">Entries</th>
                      <th className="py-1 text-right font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cost_by_category.map((c) => (
                      <tr key={c.category} className="border-t border-border">
                        <td className="py-1 pr-4">{c.label ?? c.category}</td>
                        <td className="py-1 pr-4 text-right tabular-nums">{c.count ?? ""}</td>
                        <td className="py-1 text-right tabular-nums">{money(c.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-border font-semibold">
                      <td className="py-1 pr-4">Total</td>
                      <td />
                      <td className="py-1 text-right tabular-nums">{money(data.total_cost)}</td>
                    </tr>
                  </tfoot>
                </table>
              )}
            </Card>

            <WriteOnly note={null}>
              <Card className="space-y-3">
                <h3 className="font-medium">{editing ? "Correct this cost" : "Record a cost"}</h3>
                {error && <p role="alert" className="text-sm text-danger">{error}</p>}
                {notice && !error && <p className="text-sm text-success">{notice}</p>}
                <label className="block space-y-1 text-sm">
                  <span className="text-text-muted">Date</span>
                  <input type="date" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} className={field} />
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-text-muted">Category</span>
                  <select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className={field}>
                    {CATEGORIES.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-text-muted">What it was for</span>
                  <input
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="e.g. Claude subscription, October"
                    maxLength={255}
                    className={field}
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-text-muted">Paid to (optional)</span>
                  <input
                    value={form.paid_to}
                    onChange={(e) => setForm((f) => ({ ...f, paid_to: e.target.value }))}
                    placeholder="e.g. Anthropic, or the RA's name"
                    maxLength={255}
                    className={field}
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-text-muted">Amount (USD)</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="0.00"
                    value={form.amount}
                    onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                    className={field}
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => save.mutate()} disabled={!form.amount || !form.description.trim() || save.isPending}>
                    {save.isPending ? "Saving…" : editing ? "Save changes" : "Record cost"}
                  </Button>
                  {editing && (
                    <Button variant="outline" onClick={() => { setEditing(null); setForm(EMPTY); }}>
                      Cancel
                    </Button>
                  )}
                </div>
              </Card>
            </WriteOnly>
          </div>

          <Card>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h3 className="font-medium">All costs</h3>
                <p className="text-xs text-text-muted">Each entry, newest first. Filter by month or category; the total is for what is shown.</p>
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <label className="space-y-1 text-xs">
                  <span className="block text-text-muted">Month</span>
                  <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm" />
                </label>
                <label className="space-y-1 text-xs">
                  <span className="block text-text-muted">Category</span>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm">
                    <option value="">All categories</option>
                    {CATEGORIES.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                {(month || category) && (
                  <Button variant="outline" className="min-h-9 py-1.5" onClick={() => { setMonth(""); setCategory(""); }}>
                    Clear
                  </Button>
                )}
                <Button variant="outline" className="min-h-9 py-1.5" disabled={!rows.length} onClick={() => downloadCsv(rows, list.data?.total ?? "0")}>
                  Download CSV
                </Button>
              </div>
            </div>
            {forbidden ? (
              <p className="text-sm text-text-muted">Individual cost entries are visible to the PI, Field Coordinator and Supervisor.</p>
            ) : list.isLoading ? (
              <p className="text-sm text-text-muted">Loading…</p>
            ) : rows.length === 0 ? (
              <p className="text-sm text-text-muted">No costs {month || category ? "match these filters" : "recorded yet"}.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[44rem] text-sm">
                  <thead>
                    <tr className="text-left text-text-muted">
                      <th className="py-1.5 pr-3 font-medium">Date</th>
                      <th className="py-1.5 pr-3 font-medium">Category</th>
                      <th className="py-1.5 pr-3 font-medium">What it was for</th>
                      <th className="py-1.5 pr-3 font-medium">Paid to</th>
                      <th className="py-1.5 pr-3 text-right font-medium">Amount</th>
                      <th className="py-1.5 pr-3 font-medium">Recorded by</th>
                      <WriteOnly note={null}><th className="py-1.5" aria-label="Actions" /></WriteOnly>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} className={`border-t border-border align-top ${editing === r.id ? "bg-bg" : ""}`}>
                        <td className="whitespace-nowrap py-1.5 pr-3 tabular-nums">{shortDate(r.date)}</td>
                        <td className="whitespace-nowrap py-1.5 pr-3">{r.category_label}</td>
                        <td className="py-1.5 pr-3">{r.description || <span className="text-text-muted">(not given)</span>}</td>
                        <td className="py-1.5 pr-3">{r.paid_to}</td>
                        <td className="whitespace-nowrap py-1.5 pr-3 text-right tabular-nums">{money(r.amount)}</td>
                        <td className="py-1.5 pr-3 text-text-muted">{r.recorded_by}</td>
                        <WriteOnly note={null}>
                          <td className="whitespace-nowrap py-1.5 text-right">
                            <button type="button" className="mr-3 text-xs text-header underline" onClick={() => startEdit(r)}>
                              Edit
                            </button>
                            <button
                              type="button"
                              className="text-xs text-danger underline"
                              disabled={remove.isPending}
                              onClick={() => {
                                if (window.confirm(`Delete "${r.description || r.category_label}" (${money(r.amount)}, ${shortDate(r.date)})?`)) remove.mutate(r.id);
                              }}
                            >
                              Delete
                            </button>
                          </td>
                        </WriteOnly>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-border font-semibold">
                      <td className="py-1.5 pr-3" colSpan={4}>
                        Total{month || category ? " (filtered)" : ""} · {list.data?.count} {list.data?.count === 1 ? "entry" : "entries"}
                      </td>
                      <td className="whitespace-nowrap py-1.5 pr-3 text-right tabular-nums">{money(list.data?.total ?? 0)}</td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
