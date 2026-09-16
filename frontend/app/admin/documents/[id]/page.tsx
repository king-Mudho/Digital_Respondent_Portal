"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole, ReadOnly, WriteOnly } from "@/components/admin/RoleGate";
import { KoboFormPanel } from "@/components/admin/KoboFormPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch, adminUpload } from "@/lib/api/admin";
import { useRef, useState } from "react";

interface DocumentRecord {
  id: number;
  document_id: string;
  title: string;
  document_type: string;
  authenticity_assessment: string;
  qa_status: string;
  evidence_extract: string;
  interpretive_memo: string;
  coding_url: string | null;
  source_file_name: string;
  source_file_size: number | null;
  source_file_uploaded_at: string | null;
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
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const uploadFile = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return adminUpload(`/documents/${params.id}/file/`, body);
    },
    onSuccess: () => {
      setUploadError(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      invalidate();
    },
    onError: (err) =>
      setUploadError(err instanceof ApiError ? err.message : "Could not upload the file."),
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
            </p>
          ) : (
            <p className="text-sm text-text-muted">No file uploaded yet.</p>
          )}
          <WriteOnly>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.mp3,.m4a,.wav,.mp4"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadFile.mutate(file);
                }}
                disabled={uploadFile.isPending}
                className="text-sm"
              />
              {uploadFile.isPending && <span className="text-sm text-text-muted">Uploading…</span>}
            </div>
            <p className="text-xs text-text-muted">
              A scan, photo, screenshot or recording of the source (PDF, image, Office file or audio/video,
              up to 20 MB). Uploading replaces any earlier file for this record.
            </p>
            {uploadError && <p className="text-danger text-sm">{uploadError}</p>}
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
                <a
                  href={doc.coding_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors min-h-11 bg-header text-white hover:opacity-90"
                >
                  Code this document
                </a>
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
