"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface Appointment {
  id: number;
  sample_case: number | null;
  kii_record: number | null;
  scheduled_for: string;
  mode: string;
  status: string;
}

const STATUS_OPTIONS: Record<string, string[]> = {
  REQUESTED: ["CONFIRMED", "CANCELLED"],
  CONFIRMED: ["COMPLETED", "MISSED", "CANCELLED"],
};

export default function AppointmentsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["appointments"],
    queryFn: () => adminFetch<{ results: Appointment[] }>("/appointments/"),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      adminFetch(`/appointments/${id}/status/`, { method: "POST", body: JSON.stringify({ status }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["appointments"] }),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Appointment Queue</h2>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">No appointments scheduled.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-2 pr-4">Scheduled for</th>
                <th className="py-2 pr-4">Mode</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((a) => (
                <tr key={a.id} className="border-t border-border">
                  <td className="py-2 pr-4">{new Date(a.scheduled_for).toLocaleString()}</td>
                  <td className="py-2 pr-4">{a.mode}</td>
                  <td className="py-2 pr-4">{a.status}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      {(STATUS_OPTIONS[a.status] ?? []).map((next) => (
                        <Button
                          key={next}
                          variant="outline"
                          onClick={() => setStatus.mutate({ id: a.id, status: next })}
                        >
                          {next}
                        </Button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </AdminShell>
  );
}
