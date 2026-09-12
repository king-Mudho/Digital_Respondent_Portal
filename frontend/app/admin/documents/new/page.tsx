"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

const DOCUMENT_TYPES = ["OFFICIAL", "SECONDARY", "PLATFORM"];

export default function NewDocumentPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    title: "",
    author_or_speaker: "",
    source_url_or_reference: "",
    document_type: "OFFICIAL",
    geographic_scope: "",
    evidence_extract: "",
  });
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const doc = await adminFetch<{ id: number }>("/documents/", {
        method: "POST",
        body: JSON.stringify(form),
      });
      router.push(`/admin/documents/${doc.id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell backHref="/admin/documents" backLabel="Documents">
      <h2 className="font-semibold text-xl mb-4">New Documentary Evidence Record</h2>
      <Card className="max-w-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              required
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Author / speaker</label>
            <input
              value={form.author_or_speaker}
              onChange={(e) => setForm((f) => ({ ...f, author_or_speaker: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Source URL / reference</label>
            <input
              value={form.source_url_or_reference}
              onChange={(e) => setForm((f) => ({ ...f, source_url_or_reference: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Document type</label>
            <select
              value={form.document_type}
              onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2 bg-surface"
            >
              {DOCUMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Geographic scope</label>
            <input
              value={form.geographic_scope}
              onChange={(e) => setForm((f) => ({ ...f, geographic_scope: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Evidence extract</label>
            <textarea
              value={form.evidence_extract}
              onChange={(e) => setForm((f) => ({ ...f, evidence_extract: e.target.value }))}
              className="w-full rounded-md border border-border px-3 py-2"
              rows={3}
            />
          </div>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create document record"}
          </Button>
        </form>
      </Card>
    </AdminShell>
  );
}
