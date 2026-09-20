"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, ReadOnly, WriteOnly } from "@/components/admin/RoleGate";
import { KoboFormPanel } from "@/components/admin/KoboFormPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch, adminUpload } from "@/lib/api/admin";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

interface DocumentRecord {
  id: number;
  document_id: string;
  title: string;
  author_or_speaker: string;
  publication_or_event_date: string | null;
  source_url_or_reference: string;
  geographic_scope: string;
  value_chain: string;
  document_type: string;
  authenticity_assessment: string;
  qa_status: string;
  evidence_extract: string;
  interpretive_memo: string;
  coding_url: string | null;
  source_file_name: string;
  source_file_size: number | null;
  source_file_uploaded_at: string | null;
  ai_coding_configured: boolean;
  ai_draft_generated_at: string | null;
  kobo_submitted_at: string | null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** A08-adjacent document detail/provenance workflow page --
 * docs/14_DOCUMENTARY_EVIDENCE_MODULE.md. */
export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  // null means "not edited yet, show what the server has". Defaulting the
  // textarea to `memo || doc.interpretive_memo` made an empty string fall
  // back to the saved text, so a memo could never be cleared.
  const [memo, setMemo] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const [autoFillAfter, setAutoFillAfter] = useState(true);
  // null = not edited yet (show what the server has), so a detail can be cleared.
  const [details, setDetails] = useState<Record<string, string> | null>(null);
  const [detailsSaved, setDetailsSaved] = useState(false);
  const [chapter, setChapter] = useState({ title: "", pages: "" });

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
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not record the assessment."),
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
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not set the QA status."),
  });

  const saveMemo = useMutation({
    mutationFn: () =>
      adminFetch(`/documents/${params.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ interpretive_memo: memo ?? "" }),
      }),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      setMemo(null); // fall back to the server's copy again
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save the memo."),
  });

  const saveDetails = useMutation({
    mutationFn: () => adminFetch(`/documents/${params.id}/`, { method: "PATCH", body: JSON.stringify(details ?? {}) }),
    onSuccess: () => {
      setError(null);
      setDetails(null);
      setDetailsSaved(true);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save the details."),
  });

  const copyForChapter = useMutation({
    mutationFn: () =>
      adminFetch<{ id: number; ai_draft_status: string }>(`/documents/${params.id}/copy/`, {
        method: "POST",
        body: JSON.stringify({ title: chapter.title.trim(), pages: chapter.pages.trim() }),
      }),
    onSuccess: (copy) => {
      setError(null);
      setChapter({ title: "", pages: "" });
      // With AI on, the copy is already being drafted: go to its review screen.
      router.push(copy.ai_draft_status === "running" ? `/admin/documents/${copy.id}/ai-draft` : `/admin/documents/${copy.id}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not copy the record."),
  });

  const uploadFile = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      setUploadProgress(0);
      await adminUpload(`/documents/${params.id}/file/`, body, setUploadProgress);
      // Straight into Auto-fill when asked: the AI starts reading at once. If it can't start
      // (a long PDF needs pages), the review screen opens anyway and says what to enter.
      if (autoFillAfter && doc?.ai_coding_configured) {
        await adminFetch(`/documents/${params.id}/ai-draft/`, { method: "POST", body: JSON.stringify({ pages: "" }) }).catch(() => null);
        return true;
      }
      return false;
    },
    onSettled: () => setUploadProgress(null),
    onSuccess: (startedAutoFill) => {
      setUploadError(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      invalidate();
      if (startedAutoFill) router.push(`/admin/documents/${params.id}/ai-draft`);
    },
    onError: (err) => {
      setUploadError(err instanceof ApiError ? err.message : "Could not upload the file.");
      // Cleared on error too, not just success: a browser only fires the file
      // input's change event when the selection changes, so leaving a
      // rejected file "selected" would silently swallow a retry of the same
      // path (e.g. after shrinking it below the size limit).
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const removeFile = useMutation({
    mutationFn: () => adminFetch(`/documents/${params.id}/file/`, { method: "DELETE" }),
    onSuccess: () => {
      setUploadError(null);
      invalidate();
    },
    onError: (err) => setUploadError(err instanceof ApiError ? err.message : "Could not remove the file."),
  });

  if (isLoading || !doc) {
    return (
      <AdminShell backHref="/admin/documents" backLabel="Documents">
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  const memoValue = memo ?? doc.interpretive_memo;

  return (
    <AdminShell backHref="/admin/documents" backLabel="Documents">
      <h2 className="font-semibold text-xl mb-1">{doc.title}</h2>
      <p className="text-text-muted text-sm mb-4 font-mono">
        {doc.document_id} · {doc.document_type}
      </p>
      {error && <p className="text-danger text-sm mb-4">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <h3 className="font-medium">Authenticity: {doc.authenticity_assessment}</h3>
          <WriteOnly>
            <div className="flex gap-2">
              <Button
                variant="outline"
                disabled={setAuthenticity.isPending || doc.authenticity_assessment === "VERIFIED"}
                onClick={() => setAuthenticity.mutate("VERIFIED")}
              >
                Mark verified
              </Button>
              <Button
                variant="outline"
                disabled={setAuthenticity.isPending || doc.authenticity_assessment === "DISPUTED"}
                onClick={() => setAuthenticity.mutate("DISPUTED")}
              >
                Mark disputed
              </Button>
            </div>
          </WriteOnly>
        </Card>

        <Card className="space-y-3">
          <h3 className="font-medium">QA status: {doc.qa_status}</h3>
          <WriteOnly>
            <div className="flex gap-2">
              <Button
                variant="outline"
                // set_qa_status refuses INCLUDED while authenticity is
                // UNVERIFIED -- don't offer a button that must fail.
                disabled={
                  setQaStatus.isPending ||
                  doc.authenticity_assessment === "UNVERIFIED" ||
                  doc.qa_status === "INCLUDED"
                }
                onClick={() => setQaStatus.mutate("INCLUDED")}
              >
                Include
              </Button>
              <Button
                variant="outline"
                disabled={setQaStatus.isPending || doc.qa_status === "EXCLUDED"}
                onClick={() => setQaStatus.mutate("EXCLUDED")}
              >
                Exclude
              </Button>
            </div>
          </WriteOnly>
          {doc.authenticity_assessment === "UNVERIFIED" && (
            <p className="text-xs text-text-muted">
              Cannot be included until authenticity is assessed.
            </p>
          )}
        </Card>

        <Card className="space-y-3 md:col-span-2">
          <h3 className="font-medium">Source file</h3>
          {doc.source_file_name ? (
            <p className="text-sm">
              <a
                href={`/api/proxy/documents/${params.id}/file/`}
                className="underline"
                target="_blank"
                rel="noreferrer"
              >
                {doc.source_file_name}
              </a>
              {doc.source_file_size != null && ` · ${formatFileSize(doc.source_file_size)}`}
              {doc.source_file_uploaded_at &&
                ` · uploaded ${new Date(doc.source_file_uploaded_at).toLocaleDateString()}`}
              <WriteOnly note={null}>
                <button
                  type="button"
                  disabled={removeFile.isPending}
                  className="ml-3 text-danger underline disabled:opacity-50"
                  onClick={() => {
                    // Named plainly: what goes, and what goes with it.
                    const draftNote =
                      doc.ai_draft_generated_at && !doc.kobo_submitted_at
                        ? " The AI draft made from it will be discarded too."
                        : "";
                    if (window.confirm(`Remove ${doc.source_file_name} from this document?${draftNote}`)) {
                      removeFile.mutate();
                    }
                  }}
                >
                  {removeFile.isPending ? "Removing…" : "Remove file"}
                </button>
              </WriteOnly>
            </p>
          ) : (
            <p className="text-sm text-text-muted">No file uploaded yet.</p>
          )}
          <WriteOnly>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.txt,.csv,.mp3,.m4a,.wav,.mp4"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadFile.mutate(file);
                }}
                disabled={uploadFile.isPending}
                className="text-sm"
              />
              {uploadFile.isPending && (
                <span className="flex items-center gap-2 text-sm text-text-muted">
                  <span className="inline-block h-2 w-40 rounded bg-border overflow-hidden" role="progressbar" aria-label="Upload progress">
                    <span className="block h-2 bg-header" style={{ width: `${Math.round((uploadProgress ?? 0) * 100)}%` }} />
                  </span>
                  {uploadProgress !== null && uploadProgress >= 1
                    ? "Saving…"
                    : `Uploading… ${Math.round((uploadProgress ?? 0) * 100)}%`}
                </span>
              )}
            </div>
            <p className="text-xs text-text-muted">
              A scan, photo, screenshot or recording of the source (PDF, image, Office file or audio/video,
              up to 20 MB). Uploaded the wrong one? Remove it above, or choose another file to replace it.
            </p>
            {doc.ai_coding_configured && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={autoFillAfter} onChange={(e) => setAutoFillAfter(e.target.checked)} />
                Start Auto-fill as soon as the file is uploaded
              </label>
            )}
            {uploadError && <p className="text-danger text-sm">{uploadError}</p>}
          </WriteOnly>
        </Card>

        {doc.source_file_name && (
          <WriteOnly note={null}>
            <Card className="space-y-3 md:col-span-2">
              <h3 className="font-medium">Copy for another chapter</h3>
              <p className="text-xs text-text-muted">
                Code another part of this same document as its own record: same author, date and source, with its own
                copy of the file. {doc.ai_coding_configured
                  ? "The AI starts drafting that chapter straight away."
                  : "Then code it as usual."}{" "}
                Authenticity and inclusion are decided separately for each chapter.
              </p>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-sm text-text-muted mb-1" htmlFor="copy-title">Chapter title (optional)</label>
                  <input
                    id="copy-title"
                    value={chapter.title}
                    onChange={(e) => setChapter((c) => ({ ...c, title: e.target.value }))}
                    placeholder="e.g. Warehouse receipts chapter"
                    className="w-72 max-w-full rounded-md border border-border px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-text-muted mb-1" htmlFor="copy-pages">Pages to read</label>
                  <input
                    id="copy-pages"
                    value={chapter.pages}
                    onChange={(e) => setChapter((c) => ({ ...c, pages: e.target.value }))}
                    placeholder="e.g. 290-340"
                    className="w-36 rounded-md border border-border px-3 py-2 text-sm"
                  />
                </div>
                <Button
                  variant="outline"
                  disabled={copyForChapter.isPending || (!chapter.title.trim() && !chapter.pages.trim())}
                  onClick={() => copyForChapter.mutate()}
                >
                  {copyForChapter.isPending ? "Copying…" : doc.ai_coding_configured ? "Copy and auto-fill" : "Copy record"}
                </Button>
              </div>
              <p className="text-xs text-text-muted">Leave the title empty and the AI names the chapter from its pages.</p>
            </Card>
          </WriteOnly>
        )}

        <Card className="space-y-3 md:col-span-2">
          <h3 className="font-medium">Record details</h3>
          <p className="text-xs text-text-muted">
            These go into the coding form as they are. If Auto-fill filled them in from the document, check them here.
          </p>
          <WriteOnly note={null}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(
                [
                  ["title", "Title"],
                  ["author_or_speaker", "Author / speaker"],
                  ["publication_or_event_date", "Publication or event date"],
                  ["source_url_or_reference", "Source URL / reference"],
                  ["geographic_scope", "Geographic scope"],
                  ["value_chain", "Value chain"],
                ] as const
              ).map(([field, label]) => (
                <div key={field}>
                  <label className="block text-sm text-text-muted mb-1" htmlFor={`detail-${field}`}>{label}</label>
                  <input
                    id={`detail-${field}`}
                    type={field === "publication_or_event_date" ? "date" : "text"}
                    value={details?.[field] ?? (doc[field] as string | null) ?? ""}
                    onChange={(e) => {
                      setDetailsSaved(false);
                      setDetails((d) => ({ ...(d ?? {}), [field]: e.target.value }));
                    }}
                    className="w-full rounded-md border border-border px-3 py-2 text-sm"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm text-text-muted mb-1" htmlFor="detail-document_type">Document type</label>
                <select
                  id="detail-document_type"
                  value={details?.document_type ?? doc.document_type}
                  onChange={(e) => {
                    setDetailsSaved(false);
                    setDetails((d) => ({ ...(d ?? {}), document_type: e.target.value }));
                  }}
                  className="w-full rounded-md border border-border px-3 py-2 text-sm bg-surface"
                >
                  {["OFFICIAL", "SECONDARY", "PLATFORM"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" disabled={!details || saveDetails.isPending} onClick={() => saveDetails.mutate()}>
                {saveDetails.isPending ? "Saving…" : "Save details"}
              </Button>
              {detailsSaved && <span className="text-sm text-text-muted" role="status">Details saved.</span>}
            </div>
          </WriteOnly>
        </Card>

        <Card className="space-y-2 md:col-span-2">
          <h3 className="font-medium">Coding</h3>
          {doc.coding_url ? (
            <>
              <p className="text-sm text-text-muted">
                Opens the KoboToolbox Document Analysis Tool with this record&rsquo;s DOC-ID and details
                already filled in.
              </p>
              <WriteOnly>
                <div className="flex flex-wrap items-center gap-3">
                  <a
                    href={doc.coding_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors min-h-11 bg-header text-white hover:opacity-90"
                  >
                    Code this document
                  </a>
                  {doc.ai_coding_configured && (
                    <Link
                      href={`/admin/documents/${params.id}/ai-draft`}
                      className="inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors min-h-11 border border-border text-text hover:bg-surface"
                    >
                      Auto-fill
                    </Link>
                  )}
                </div>
                {doc.ai_coding_configured && (
                  <p className="text-xs text-text-muted">
                    Auto-fill has AI read the uploaded source file and draft the whole form for you to
                    review, edit and submit yourself &mdash; nothing reaches KoboToolbox until you do.
                    {doc.kobo_submitted_at &&
                      ` Already submitted this way on ${new Date(doc.kobo_submitted_at).toLocaleDateString()}.`}
                  </p>
                )}
              </WriteOnly>
            </>
          ) : (
            <p className="text-sm text-text-muted">
              The Document Analysis Tool link hasn&rsquo;t been set up yet (KOBO_DOCUMENTS_FORM_URL). Ask
              the administrator to configure it.
            </p>
          )}
        </Card>

        {doc.evidence_extract && (
          <Card className="space-y-2 md:col-span-2">
            <h3 className="font-medium">Evidence extract</h3>
            <p className="text-sm whitespace-pre-wrap">{doc.evidence_extract}</p>
          </Card>
        )}

        <Card className="space-y-3 md:col-span-2">
          <h3 className="font-medium">Interpretive memo (dispute reasons, notes)</h3>
          <WriteOnly>
            <textarea
              value={memoValue}
              onChange={(e) => {
                setMemo(e.target.value);
                setSaved(false);
              }}
              className="w-full rounded-md border border-border px-3 py-2"
              rows={3}
            />
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                disabled={saveMemo.isPending || memo === null}
                onClick={() => saveMemo.mutate()}
              >
                {saveMemo.isPending ? "Saving…" : "Save memo"}
              </Button>
              {saved && <span className="text-sm text-text-muted">Saved.</span>}
            </div>
          </WriteOnly>
          {/* Read-only roles still need to see the memo itself. */}
          <ReadOnly>
            <p className="text-sm whitespace-pre-wrap">
              {doc.interpretive_memo || "No memo recorded."}
            </p>
          </ReadOnly>
        </Card>
      </div>
      <div className="mt-4">
        <IfRole roles={["PI_ADMIN", "FIELD_COORDINATOR", "DOCUMENTARY_RA", "SUPERVISOR_READONLY"]}>
          <KoboFormPanel formKey="documents" record={doc.document_id} title="Completed coding form (KoboToolbox)" />
        </IfRole>
      </div>
    </AdminShell>
  );
}
