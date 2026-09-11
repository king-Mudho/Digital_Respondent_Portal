"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

interface DocumentRecord {
  id: number;
  document_id: string;
  title: string;
  document_type: string;
  authenticity_assessment: string;
  qa_status: string;
}

/** Basic register view -- full provenance/tagging workflow UI lands in
 * Phase 7 (docs/27_AGENT_EXECUTION_PLAN.md). */
export default function DocumentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["document-records"],
    queryFn: () => adminFetch<{ results: DocumentRecord[] }>("/documents/"),
  });

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-4">Documentary Evidence Corpus</h2>
      <Card>
        {isLoading || !data ? (
          <p className="text-text-muted">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">No documents yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="py-2 pr-4">Document ID</th>
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Authenticity</th>
                <th className="py-2">QA status</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id} className="border-t border-border">
                  <td className="py-2 pr-4 font-mono text-xs">{d.document_id}</td>
                  <td className="py-2 pr-4">{d.title}</td>
                  <td className="py-2 pr-4">{d.document_type}</td>
                  <td className="py-2 pr-4">{d.authenticity_assessment}</td>
                  <td className="py-2">{d.qa_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </AdminShell>
  );
}
