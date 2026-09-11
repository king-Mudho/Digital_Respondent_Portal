"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";
import { useState } from "react";

interface DocumentRecord {
  id: number;
  document_id: string;
  title: string;
  document_type: string;
  authenticity_assessment: string;
  qa_status: string;
  evidence_extract: string;
  interpretive_memo: string;
}

/** A08-adjacent document detail/provenance workflow page --
 * docs/14_DOCUMENTARY_EVIDENCE_MODULE.md. */
export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [memo, setMemo] = useState("");

  const { data: doc, isLoading } = useQuery({
    queryKey: ["document", params.id],
    queryFn: () => adminFetch<DocumentRecord>(`/documents/${params.id}/`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["document", params.id] });

  const setAuthenticity = useMutation({
    mutationFn: (assessment: string) =>
      adminFetch(`/documents/${params.id}/authenticity/`, {
        method: "POST",
        body: JSON.stringify({ assessment }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const setQaStatus = useMutation({
    mutationFn: (qa_status: string) =>
      adminFetch(`/documents/${params.id}/qa-status/`, {
        method: "POST",
        body: JSON.stringify({ qa_status }),
      }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const saveMemo = useMutation({
    mutationFn: () =>
      adminFetch(`/documents/${params.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ interpretive_memo: memo }),
      }),
    onSuccess: invalidate,
  });

  if (isLoading || !doc) {
    return (
      <AdminShell>
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  return (
    <AdminShell>
      <h2 className="font-semibold text-xl mb-1">{doc.title}</h2>
      <p className="text-text-muted text-sm mb-4 font-mono">{doc.document_id}</p>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <h3 className="font-medium">Authenticity: {doc.authenticity_assessment}</h3>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setAuthenticity.mutate("VERIFIED")}>
              Mark verified
            </Button>
            <Button variant="outline" onClick={() => setAuthenticity.mutate("DISPUTED")}>
              Mark disputed
            </Button>
          </div>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">QA status: {doc.qa_status}</h3>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setQaStatus.mutate("INCLUDED")}>
              Include
            </Button>
            <Button variant="outline" onClick={() => setQaStatus.mutate("EXCLUDED")}>
              Exclude
            </Button>
          </div>
          {doc.authenticity_assessment === "UNVERIFIED" && (
            <p className="text-xs text-text-muted">
              Cannot be included until authenticity is assessed.
            </p>
          )}
        </Card>

        <Card className="space-y-3 md:col-span-2">
          <h3 className="font-medium">Interpretive memo (dispute reasons, notes)</h3>
          <textarea
            value={memo || doc.interpretive_memo}
            onChange={(e) => setMemo(e.target.value)}
            className="w-full rounded-md border border-border px-3 py-2"
            rows={3}
          />
          <Button variant="outline" onClick={() => saveMemo.mutate()}>
            Save memo
          </Button>
        </Card>
      </div>
    </AdminShell>
  );
}
