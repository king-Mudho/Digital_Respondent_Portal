"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch, adminUpload } from "@/lib/api/admin";

/**
 * The study's own authorisation letters (ethics clearance, institutional approval) -- managed here, shown
 * to a respondent (who a document's is_public switch lets see it) on the invitation-flow information step
 * so they can check who approved the study before answering anything (apps/clearance).
 */

const DOCUMENT_TYPES = [
  ["ETHICS_CLEARANCE", "Research ethics clearance"],
  ["INSTITUTIONAL_APPROVAL", "Institutional / government approval"],
  ["SUPERVISION_CONFIRMATION", "Confirmation of supervision"],
  ["INTRODUCTION_LETTER", "Introduction / support letter"],
  ["OTHER", "Other"],
] as const;

interface ClearanceDocument {
  id: number;
  title: string;
  issuing_body: string;
  document_type: string;
  document_type_display: string;
  reference_number: string;
  issue_date: string | null;
  description: string;
  is_public: boolean;
  active: boolean;
  has_file: boolean;
  file_name: string;
}

const emptyForm = { title: "", issuing_body: "", document_type: "ETHICS_CLEARANCE", reference_number: "", issue_date: "", description: "" };

export default function ClearanceDocumentsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const fileInputs = useRef<Record<number, HTMLInputElement | null>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["clearance-documents"],
    queryFn: () => adminFetch<{ results: ClearanceDocument[] }>("/clearance-documents/"),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["clearance-documents"] });

  const create = useMutation({
    mutationFn: () =>
      adminFetch<ClearanceDocument>("/clearance-documents/", {
        method: "POST",
        body: JSON.stringify({ ...form, issue_date: form.issue_date || null }),
      }),
    onSuccess: () => {
      setError(null);
      setForm(emptyForm);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not add the document."),
  });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<ClearanceDocument, "is_public" | "active">> }) =>
      adminFetch<ClearanceDocument>(`/clearance-documents/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: invalidate,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save that change."),
  });

  const upload = useMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => {
      const body = new FormData();
      body.append("file", file);
      await adminUpload(`/clearance-documents/${id}/file/`, body);
    },
    onSuccess: (_r, { id }) => {
      setError(null);
      if (fileInputs.current[id]) fileInputs.current[id]!.value = "";
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not upload the file."),
  });

  const remove = useMutation({
    mutationFn: (id: number) => adminFetch(`/clearance-documents/${id}/`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not delete that document."),
  });

  const docs = data?.results ?? [];

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <h2 className="font-semibold text-xl mb-1">Research Clearance</h2>
      <p className="text-sm text-text-muted mb-4 max-w-2xl">
        The letters that show this study is genuine and authorised. A document is shown to respondents only
        once you switch on <strong>Shown to respondents</strong> below and it has a file attached -- it stays
        hidden by default. Respondents see it on the information step of their invitation link.
      </p>

      {error && <p className="text-danger text-sm mb-3">{error}</p>}

      <Card className="space-y-3 mb-4">
        <h3 className="font-medium text-sm">Add a document</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="text-xs text-text-muted space-y-1 block">
            Title
            <input className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="e.g. Research Ethics Clearance Letter" />
          </label>
          <label className="text-xs text-text-muted space-y-1 block">
            Issuing body
            <input className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.issuing_body}
              onChange={(e) => setForm((f) => ({ ...f, issuing_body: e.target.value }))} placeholder="e.g. Chinhoyi University of Technology" />
          </label>
          <label className="text-xs text-text-muted space-y-1 block">
            Type
            <select className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.document_type}
              onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}>
              {DOCUMENT_TYPES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-text-muted space-y-1 block">
            Reference number (as printed on the letter, if any)
            <input className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.reference_number}
              onChange={(e) => setForm((f) => ({ ...f, reference_number: e.target.value }))} placeholder="e.g. Annex 19, Form GRSD 17 SEBS/06/2025" />
          </label>
          <label className="text-xs text-text-muted space-y-1 block">
            Date on the letter
            <input type="date" className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.issue_date}
              onChange={(e) => setForm((f) => ({ ...f, issue_date: e.target.value }))} />
          </label>
          <label className="text-xs text-text-muted space-y-1 block md:col-span-2">
            Description shown to respondents (plain language, optional)
            <textarea rows={2} className="w-full rounded-md border border-border px-2 py-1.5 text-sm" value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </label>
        </div>
        <Button onClick={() => create.mutate()} disabled={create.isPending || !form.title.trim() || !form.issuing_body.trim()}>
          Add document
        </Button>
      </Card>

      <Card>
        {isLoading ? (
          <p className="text-text-muted">Loading…</p>
        ) : docs.length === 0 ? (
          <p className="text-text-muted text-sm">No clearance documents yet.</p>
        ) : (
          <div className="divide-y divide-border">
            {docs.map((doc) => (
              <div key={doc.id} className="py-3 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium">{doc.title}</p>
                    <p className="text-xs text-text-muted">
                      {doc.issuing_body} · {doc.document_type_display}
                      {doc.reference_number && <> · {doc.reference_number}</>}
                      {doc.issue_date && <> · {doc.issue_date}</>}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <label className="flex items-center gap-1.5 text-xs">
                      <input type="checkbox" checked={doc.is_public}
                        onChange={(e) => patch.mutate({ id: doc.id, body: { is_public: e.target.checked } })} />
                      Shown to respondents
                    </label>
                    <label className="flex items-center gap-1.5 text-xs">
                      <input type="checkbox" checked={doc.active}
                        onChange={(e) => patch.mutate({ id: doc.id, body: { active: e.target.checked } })} />
                      Active
                    </label>
                  </div>
                </div>
                {doc.is_public && !doc.has_file && (
                  <p className="text-xs text-danger">Shown to respondents is on, but no file is attached yet -- nobody sees it until one is.</p>
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-text-muted">{doc.has_file ? `File: ${doc.file_name}` : "No file uploaded yet"}</span>
                  <input
                    ref={(el) => { fileInputs.current[doc.id] = el; }}
                    type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" id={`file-${doc.id}`}
                    onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate({ id: doc.id, file }); }}
                  />
                  <label htmlFor={`file-${doc.id}`}>
                    <Button variant="outline" type="button" onClick={() => fileInputs.current[doc.id]?.click()}>
                      {doc.has_file ? "Replace file" : "Upload file"}
                    </Button>
                  </label>
                  {doc.has_file && (
                    // eslint-disable-next-line @next/next/no-html-link-for-pages -- file download, not page navigation.
                    <a href={`/api/proxy/clearance-documents/${doc.id}/file/`} className="text-xs underline text-header">View</a>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => { if (confirm(`Delete "${doc.title}"?`)) remove.mutate(doc.id); }}
                    disabled={doc.is_public}
                    title={doc.is_public ? "Switch off \"Shown to respondents\" first, or set it inactive instead" : undefined}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AdminShell>
  );
}
