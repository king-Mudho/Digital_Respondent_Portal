"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
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

export default function AppointmentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["appointments"],
    queryFn: () => adminFetch<{ results: Appointment[] }>("/appointments/"),
  });

  return (
    <AdminShell>
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
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((a) => (
                <tr key={a.id} className="border-t border-border">
                  <td className="py-2 pr-4">{new Date(a.scheduled_for).toLocaleString()}</td>
                  <td className="py-2 pr-4">{a.mode}</td>
                  <td className="py-2">{a.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </AdminShell>
  );
}
