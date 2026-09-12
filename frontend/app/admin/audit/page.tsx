"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface AuditEvent {
  id: number;
  user_display: string | null;
  action: string;
  object_type: string;
  object_id: string;
  created_at: string;
}

export default function AuditLogPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => adminFetch<{ results: AuditEvent[] }>("/audit/"),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Audit Log</h2>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-2 pr-4">When</th>
                <th className="py-2 pr-4">Action</th>
                <th className="py-2 pr-4">Object</th>
                <th className="py-2">User</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="py-2 pr-4 text-xs">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4 font-mono text-xs">{e.action}</td>
                  <td className="py-2 pr-4 text-xs">
                    {e.object_type}:{e.object_id}
                  </td>
                  <td className="py-2 text-xs">{e.user_display ?? "system"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </AdminShell>
  );
}
