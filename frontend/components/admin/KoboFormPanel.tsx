"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

interface Found {
  id: number;
  submitted_at: string | null;
  submitted_by: string;
}

/**
 * The completed KoboToolbox form(s) for one portal record -- a case's
 * questionnaire, a KII's interview record, a document's coding sheet --
 * matched on the form's own identifier field. Mount it only for roles that
 * hold the form (kobo.submission_copies.FORMS).
 */
export function KoboFormPanel({ formKey, record, title }: { formKey: string; record: string; title: string }) {
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading, error: lookupError } = useQuery({
    queryKey: ["kobo-lookup", formKey, record],
    queryFn: () => adminFetch<{ results: Found[] }>(`/kobo/forms/${formKey}/lookup/?record=${encodeURIComponent(record)}`),
  });

  const download = async (id: number) => {
    setError(null);
    const response = await fetch(`/api/proxy/kobo/forms/${formKey}/submissions/${id}/pdf/`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setError(body?.error?.message ?? "Download failed.");
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `${record}-${id}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const notConnected = lookupError instanceof ApiError && lookupError.code === "kobo_not_configured";

  return (
    <Card className="space-y-2">
      <h3 className="font-medium">{title}</h3>
      {isLoading ? (
        <p className="text-text-muted text-sm">Checking KoboToolbox…</p>
      ) : notConnected ? (
        <p className="text-text-muted text-sm">This form isn&apos;t connected to KoboToolbox yet.</p>
      ) : lookupError ? (
        <p className="text-danger text-sm">{(lookupError as Error).message}</p>
      ) : !data?.results.length ? (
        <p className="text-text-muted text-sm">No completed form in KoboToolbox for {record} yet.</p>
      ) : (
        <ul className="space-y-2">
          {data.results.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-text-muted">
                {row.submitted_at ? `Submitted ${new Date(`${row.submitted_at}Z`).toLocaleString()}` : "Submitted"}
                {row.submitted_by ? ` by ${row.submitted_by}` : " (web form)"}
              </span>
              <Button variant="outline" onClick={() => download(row.id)}>
                Download PDF
              </Button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-danger text-sm">{error}</p>}
    </Card>
  );
}
