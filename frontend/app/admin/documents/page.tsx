"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
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

/** docs/14_DOCUMENTARY_EVIDENCE_MODULE.md. */
export default function DocumentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["document-records"],
    queryFn: () => adminFetch<{ results: DocumentRecord[] }>("/documents/"),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-xl">Documentary Evidence Corpus</h2>
        <Link href="/admin/documents/new">
          <Button>New document</Button>
        </Link>
      </div>
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
                <th className="py-2 pr-4">QA status</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id} className="border-t border-border">
                  <td className="py-2 pr-4 font-mono text-xs">{d.document_id}</td>
                  <td className="py-2 pr-4">{d.title}</td>
                  <td className="py-2 pr-4">{d.document_type}</td>
                  <td className="py-2 pr-4">{d.authenticity_assessment}</td>
                  <td className="py-2 pr-4">{d.qa_status}</td>
                  <td className="py-2">
                    <Link href={`/admin/documents/${d.id}`} className="text-header underline text-xs">
                      Manage
                    </Link>
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
