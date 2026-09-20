"use client";

import Link from "next/link";
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Pagination, usePaging, SearchBox, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface KIIRecord {
  id: number;
  kii_id: string;
  stakeholder_category: string;
  participant_role: string;
  status: string;
  transcript_status: string;
  coding_status: string;
}

/**
 * A basic register view -- scheduling, consent and transcript workflow UI
 * land in Phase 7 alongside the rest of the KII module's build-out
 * (docs/27_AGENT_EXECUTION_PLAN.md Phase 7).
 */
export default function KIIRegisterPage() {
  const [search, setSearch] = useState("");
  const { page, setPage, pageSize, setPageSize } = usePaging();

  const { data, isLoading } = useQuery({
    queryKey: ["kii-records", search, page, pageSize],
    queryFn: () =>
      adminFetch<Paginated<KIIRecord>>(
        `/kii/?page=${page}&page_size=${pageSize}` + (search ? `&search=${encodeURIComponent(search)}` : ""),
      ),
    placeholderData: keepPreviousData,
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="font-semibold text-xl">KII Register</h2>
        <div className="flex items-center gap-3 flex-wrap">
          <SearchBox
            value={search}
            onChange={(v) => {
              setSearch(v);
              setPage(1);
            }}
            placeholder="Search KII ID, name or role"
          />
          <WriteOnly note={null}>
            <Link href="/admin/kii/new">
              <Button>New KII record</Button>
            </Link>
          </WriteOnly>
        </div>
      </div>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">
            {search ? `No KII records match "${search}".` : "No KII records yet."}
          </p>
        ) : (
          <>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-2 pr-4">KII ID</th>
                <th className="py-2 pr-4">Stakeholder category</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Transcript</th>
                <th className="py-2 pr-4">Coding</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((k) => (
                <tr key={k.id} className="border-t border-border">
                  <td className="py-2 pr-4 font-mono text-xs">{k.kii_id}</td>
                  <td className="py-2 pr-4">{k.stakeholder_category}</td>
                  <td className="py-2 pr-4">{k.status}</td>
                  <td className="py-2 pr-4">{k.transcript_status}</td>
                  <td className="py-2 pr-4">{k.coding_status}</td>
                  <td className="py-2">
                    <Link href={`/admin/kii/${k.id}`} className="text-header underline text-xs">
                      Manage
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <Pagination page={page} count={data.count} onPageChange={setPage} pageSize={pageSize} onPageSizeChange={setPageSize} label="KII records" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
