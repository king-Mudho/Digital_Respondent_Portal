"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch, adminUpload } from "@/lib/api/admin";

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
  const [error, setError] = useState<string | null>(null);

  // Quick add: upload a file and let the AI fill in the record and draft the form.
  const fileRef = useRef<HTMLInputElement>(null);
  const [quick, setQuick] = useState({ title: "", pages: "", wholeDocument: false });
  const [quickBusy, setQuickBusy] = useState(false);
  const [quickProgress, setQuickProgress] = useState<number | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);

  async function handleQuickAdd(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setQuickError("Choose the document to upload first.");
      return;
    }
    setQuickBusy(true);
    setQuickError(null);
    setQuickProgress(0);
    try {
      const body = new FormData();
      body.append("file", file);
      if (quick.title.trim()) body.append("title", quick.title.trim());
      if (quick.pages.trim()) body.append("pages", quick.pages.trim());
      if (quick.wholeDocument) body.append("whole_document", "true");
      const doc = await adminUpload<{ id: number }>("/documents/quick-create/", body, setQuickProgress);
      router.push(`/admin/documents/${doc.id}/ai-draft`);
    } catch (err) {
      setQuickError(err instanceof ApiError ? err.message : "Could not start Auto-fill for that file.");
      if (fileRef.current) fileRef.current.value = "";
      setQuickBusy(false);
      setQuickProgress(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const doc = await adminFetch<{ id: number }>("/documents/", {
        method: "POST",
        body: JSON.stringify(form),
      });
      router.push(`/admin/documents/${doc.id}`);
    } catch (err) {
      // Without this a rejected POST left the form looking untouched,
      // with no indication anything had gone wrong.
      setError(err instanceof ApiError ? err.message : "Could not create the document record.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell backHref="/admin/documents" backLabel="Documents">
      <h2 className="font-semibold text-xl mb-4">New Documentary Evidence Record</h2>
      <Card className="max-w-lg mb-4">
        <form onSubmit={handleQuickAdd} className="space-y-3" aria-label="Quick add from a file">
          <div>
            <h3 className="font-medium">Fastest: upload the document</h3>
            <p className="text-sm text-text-muted">
              The AI reads the file, fills in the title, author, date and other details, and drafts the whole
              coding form. You then review it, edit anything, and submit to KoboToolbox yourself.
            </p>
          </div>
          {quickError && <p className="text-danger text-sm">{quickError}</p>}
          <input
            ref={fileRef}
            type="file"
            aria-label="Document file"
            accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx,.txt,.csv"
            disabled={quickBusy}
            className="text-sm"
          />
          <details className="text-sm">
            <summary className="cursor-pointer text-text-muted">Optional: title, pages to read</summary>
            <div className="space-y-3 mt-2">
              <div>
                <label className="block text-sm font-medium mb-1" htmlFor="quick-title">Title (leave empty to let the AI read it)</label>
                <input
                  id="quick-title"
                  value={quick.title}
                  onChange={(e) => setQuick((q) => ({ ...q, title: e.target.value }))}
                  className="w-full rounded-md border border-border px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" htmlFor="quick-pages">Pages to read (a chapter, e.g. 290-340)</label>
                <input
                  id="quick-pages"
                  value={quick.pages}
                  onChange={(e) => setQuick((q) => ({ ...q, pages: e.target.value }))}
                  placeholder="all pages"
                  className="w-40 rounded-md border border-border px-3 py-2"
                />
              </div>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={quick.wholeDocument}
                  onChange={(e) => setQuick((q) => ({ ...q, wholeDocument: e.target.checked }))}
                  className="mt-1"
                />
                <span>
                  Read the whole document in parts
                  <span className="block text-xs text-text-muted">
                    For a PDF over 100 pages: about 80 pages at a time, then combined. Slower; check the ratings carefully.
                  </span>
                </span>
              </label>
            </div>
          </details>
          <Button type="submit" disabled={quickBusy}>
            {quickBusy
              ? quickProgress !== null && quickProgress < 1
                ? `Uploading… ${Math.round(quickProgress * 100)}%`
                : "Starting Auto-fill…"
              : "Upload and auto-fill"}
          </Button>
        </form>
      </Card>
      <p className="text-sm text-text-muted mb-2 max-w-lg">Or enter the details yourself:</p>
      <Card className="max-w-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p className="text-danger text-sm">{error}</p>}
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
