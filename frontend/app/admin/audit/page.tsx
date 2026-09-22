"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Pagination, usePaging, type Paginated } from "@/components/admin/Pagination";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface AuditEvent {
  id: number;
  user_display: string | null;
  action: string;
  label: string;
  detail: string;
  object_type: string;
  object_id: string;
  created_at: string;
}

export default function AuditLogPage() {
  const { page, setPage, pageSize, setPageSize } = usePaging();

  const { data, isLoading } = useQuery({
    queryKey: ["audit-log", page, pageSize],
    queryFn: () => adminFetch<Paginated<AuditEvent>>(`/audit/?page=${page}&page_size=${pageSize}`),
    placeholderData: keepPreviousData,
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-4">Audit Log</h2>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">No audit events recorded yet.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
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
                      <td className="py-2 pr-4 text-xs whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                      <td className="py-2 pr-4 text-xs">
                        <span title={e.action}>{e.label}</span>
                        {e.detail && <span className="block text-text-muted">{e.detail}</span>}
                      </td>
                      <td className="py-2 pr-4 text-xs">
                        {e.object_type}:{e.object_id}
                      </td>
                      <td className="py-2 text-xs">{e.user_display ?? "system"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="events" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
