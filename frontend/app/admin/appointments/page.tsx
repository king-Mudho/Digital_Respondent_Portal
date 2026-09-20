"use client";

import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface Appointment {
  id: number;
  sample_case: number | null;
  sample_id: string | null;
  organisation_name: string | null;
  kii_record: number | null;
  kii_id: string | null;
  scheduled_for: string;
  mode: string;
  status: string;
}

const STATUS_OPTIONS: Record<string, string[]> = {
  REQUESTED: ["CONFIRMED", "CANCELLED"],
  CONFIRMED: ["COMPLETED", "MISSED", "CANCELLED"],
};

const STATUS_FILTERS = ["", "REQUESTED", "CONFIRMED", "COMPLETED", "MISSED", "CANCELLED"];

export default function AppointmentsPage() {
  const queryClient = useQueryClient();
  const [status, setStatusFilter] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["appointments", status, page, pageSize],
    queryFn: () =>
      adminFetch<Paginated<Appointment>>(
        `/appointments/?page=${page}&page_size=${pageSize}` + (status ? `&status=${status}` : ""),
      ),
    placeholderData: keepPreviousData,
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status: next }: { id: number; status: string }) =>
      adminFetch(`/appointments/${id}/status/`, { method: "POST", body: JSON.stringify({ status: next }) }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "Could not update the appointment."),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">Appointment Queue</h2>
        <label className="text-sm text-text-muted">
          <span className="sr-only">Filter by status</span>
          <select
            value={status}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-border px-3 py-2 bg-surface text-sm"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>
                {s === "" ? "All statuses" : s}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">
            {status ? `No ${status.toLowerCase()} appointments.` : "No appointments scheduled."}
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="py-2 pr-4">Case / informant</th>
                    <th className="py-2 pr-4">Scheduled for</th>
                    <th className="py-2 pr-4">Mode</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((a) => (
                    <tr key={a.id} className="border-t border-border">
                      {/* Previously this table showed only the numeric FK,
                          so an RA could not tell whose appointment it was. */}
                      <td className="py-2 pr-4">
                        {a.sample_id ? (
                          <>
                            <span className="font-mono text-xs">{a.sample_id}</span>
                            {a.organisation_name && (
                              <span className="block text-xs text-text-muted">{a.organisation_name}</span>
                            )}
                          </>
                        ) : a.kii_id ? (
                          <span className="font-mono text-xs">{a.kii_id}</span>
                        ) : (
                          <span className="text-text-muted text-xs">—</span>
                        )}
                      </td>
                      <td className="py-2 pr-4">{new Date(a.scheduled_for).toLocaleString()}</td>
                      <td className="py-2 pr-4">{a.mode}</td>
                      <td className="py-2 pr-4">{a.status}</td>
                      <td className="py-2">
                        <WriteOnly note={null}>
                          <div className="flex gap-2">
                            {(STATUS_OPTIONS[a.status] ?? []).map((next) => (
                              <Button
                                key={next}
                                variant="outline"
                                disabled={setStatus.isPending}
                                onClick={() => setStatus.mutate({ id: a.id, status: next })}
                              >
                                {next}
                              </Button>
                            ))}
                            {/* COMPLETED / MISSED / CANCELLED are terminal --
                                say so rather than leaving an empty cell. */}
                            {(STATUS_OPTIONS[a.status] ?? []).length === 0 && (
                              <span className="text-text-muted text-xs">No further action</span>
                            )}
                          </div>
                        </WriteOnly>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="appointments" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
