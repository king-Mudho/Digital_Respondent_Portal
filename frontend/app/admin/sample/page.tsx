"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface SampleCase {
  id: number;
  sample_id: string;
  organisation_name: string;
  organisation_master_id: string;
  sample_type: string;
  status: string;
  workflow_status: string | null;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

export default function SampleRegisterPage() {
  const [sampleType, setSampleType] = useState("MAIN");

  const { data, isLoading } = useQuery({
    queryKey: ["sample-cases", sampleType],
    queryFn: () => adminFetch<Paginated<SampleCase>>(`/sample-cases/?sample_type=${sampleType}`),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-xl">Main-400 Register</h2>
        <select
          value={sampleType}
          onChange={(e) => setSampleType(e.target.value)}
          className="rounded-md border border-border px-3 py-2 bg-surface text-sm"
        >
          <option value="MAIN">Main</option>
          <option value="RESERVE">Reserve</option>
        </select>
      </div>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted">
                  <th className="py-2 pr-4">Sample ID</th>
                  <th className="py-2 pr-4">Master ID</th>
                  <th className="py-2 pr-4">Organisation</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((sc) => (
                  <tr key={sc.id} className="border-t border-border">
                    <td className="py-2 pr-4 font-mono text-xs">{sc.sample_id}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{sc.organisation_master_id}</td>
                    <td className="py-2 pr-4">{sc.organisation_name}</td>
                    <td className="py-2 pr-4">
                      <span className="rounded-full bg-bg border border-border px-2 py-0.5 text-xs">
                        {sc.workflow_status ?? sc.status}
                      </span>
                    </td>
                    <td className="py-2">
                      <Link href={`/admin/sample/${sc.sample_id}`} className="text-header underline text-xs">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.results.length === 0 && (
              <p className="text-text-muted text-sm py-4">No cases found.</p>
            )}
          </div>
        )}
      </Card>
    </AdminShell>
  );
}
