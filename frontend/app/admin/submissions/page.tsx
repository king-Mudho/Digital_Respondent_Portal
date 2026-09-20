"use client";

import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import { IfRole } from "@/components/admin/RoleGate";
import { Pagination, type Paginated } from "@/components/admin/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

interface FormInfo {
  key: string;
  title: string;
  configured: boolean;
  can_email: boolean;
  can_email_respondent: boolean;
}

interface SubmissionRow {
  id: number;
  record: string;
  submitted_at: string | null;
  submitted_by: string;
  portal_copy: boolean;
}

interface SyncRun {
  finished_at: string | null;
  error_message: string;
}

interface SyncStatus {
  key: string;
  configured: boolean;
  kobo_count: number | null;
  portal_count: number;
  removed_count: number;
  in_sync: boolean;
  kobo_error: string;
  last_sync: SyncRun | null;
  last_success: SyncRun | null;
}

type Status = { id: number; tone: "ok" | "error"; text: string } | null;

async function downloadPdf(formKey: string, id: number) {
  const response = await fetch(`/api/proxy/kobo/forms/${formKey}/submissions/${id}/pdf/`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.code ?? "unknown_error", body?.error?.message ?? "Download failed.", {});
  }
  const filename =
    /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? `submission-${id}.pdf`;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Completed KoboToolbox submissions as PDFs. Each role sees only its own form:
 * QA the questionnaire, the KII RA the KII Guide, the Documentary RA the
 * Document Analysis Tool. Copies are emailed only to the signed-in user's own
 * address or, for the questionnaire, to the respondent's address on file.
 */
export default function SubmissionsPage() {
  const [formKey, setFormKey] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<Status>(null);
  const queryClient = useQueryClient();

  const { data: forms, error: formsError } = useQuery({
    queryKey: ["kobo-forms"],
    queryFn: () => adminFetch<{ forms: FormInfo[]; email_configured: boolean }>("/kobo/forms/"),
  });
  useEffect(() => {
    if (!formKey && forms?.forms.length) setFormKey(forms.forms[0].key);
  }, [forms, formKey]);
  const form = forms?.forms.find((f) => f.key === formKey);

  const { data, isLoading, error } = useQuery({
    queryKey: ["kobo-submissions", formKey, page],
    queryFn: () => adminFetch<Paginated<SubmissionRow>>(`/kobo/forms/${formKey}/submissions/?page=${page}`),
    enabled: Boolean(form?.configured),
    placeholderData: keepPreviousData,
    // A 4xx/5xx here is a definite answer (not connected, not your form), not a blip.
    retry: false,
  });

  const { data: syncData } = useQuery({
    queryKey: ["kobo-sync-status"],
    queryFn: () => adminFetch<{ forms: SyncStatus[] }>("/kobo/sync/status/"),
    retry: false,
  });
  const sync = syncData?.forms.find((f) => f.key === formKey);
  const canSync = Boolean(form?.can_email); // the same roles that can write can sync; Supervisor is read-only

  const runSync = useMutation({
    mutationFn: () =>
      adminFetch<{ forms: SyncStatus[] }>("/kobo/sync/", { method: "POST", body: JSON.stringify({ form: formKey }) }),
    onSuccess: (result) => {
      queryClient.setQueryData(["kobo-sync-status"], (old: { forms: SyncStatus[] } | undefined) => ({
        forms: (old?.forms ?? []).map((f) => result.forms.find((n) => n.key === f.key) ?? f),
      }));
      queryClient.invalidateQueries({ queryKey: ["kobo-submissions"] });
    },
  });

  const download = useMutation({
    mutationFn: (id: number) => downloadPdf(formKey!, id),
    onError: (err, id) => setStatus({ id, tone: "error", text: err instanceof Error ? err.message : "Download failed." }),
  });

  const email = useMutation({
    mutationFn: ({ id, recipient }: { id: number; recipient: "me" | "respondent" }) =>
      adminFetch<{ sent_to: string }>(`/kobo/forms/${formKey}/submissions/${id}/email/`, {
        method: "POST",
        body: JSON.stringify({ recipient }),
      }),
    onSuccess: (result, { id }) => setStatus({ id, tone: "ok", text: `Sent to ${result.sent_to}.` }),
    onError: (err, { id }) =>
      setStatus({ id, tone: "error", text: err instanceof ApiError ? err.message : "Could not send the email." }),
  });

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-semibold text-xl">Completed forms</h2>
        {forms && forms.forms.length > 1 && (
          <label className="text-sm w-full sm:w-auto min-w-0">
            <span className="sr-only">Form</span>
            <select
              value={formKey ?? ""}
              onChange={(e) => {
                setFormKey(e.target.value);
                setPage(1);
                setStatus(null);
              }}
              className="w-full sm:w-auto max-w-full rounded-md border border-border px-3 py-2 bg-surface text-sm"
            >
              {forms.forms.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.title}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {forms && !forms.email_configured && (
        <p className="mb-3 rounded-md border border-border bg-bg p-2 text-sm">
          Email isn&apos;t set up on the server yet, so copies can be downloaded but not emailed.
        </p>
      )}
      {formsError && <p className="text-danger text-sm">{(formsError as Error).message}</p>}

      {form?.configured && (
        <Card className="mb-4 space-y-2" >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium" role="status">
                {!sync
                  ? "Checking the sync…"
                  : sync.kobo_error
                    ? "Couldn’t reach KoboToolbox to compare."
                    : sync.in_sync
                      ? "✓ In sync with KoboToolbox"
                      : "Not in sync with KoboToolbox yet"}
              </p>
              {sync && (
                <p className="text-xs text-text-muted">
                  KoboToolbox holds {sync.kobo_count ?? "?"} · the portal holds {sync.portal_count}
                  {sync.removed_count > 0 && ` · ${sync.removed_count} deleted in KoboToolbox since`}
                  {sync.last_success?.finished_at && ` · last synced ${new Date(sync.last_success.finished_at).toLocaleString()}`}
                  {sync.last_sync?.error_message && ` · last attempt failed: ${sync.last_sync.error_message}`}
                </p>
              )}
              {runSync.error && (
                <p className="text-xs text-danger">
                  {runSync.error instanceof ApiError ? runSync.error.message : "The sync failed."}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {canSync && (
                <Button variant="outline" disabled={runSync.isPending} onClick={() => runSync.mutate()}>
                  {runSync.isPending ? "Syncing…" : "Sync now"}
                </Button>
              )}
              <IfRole roles={["PI_ADMIN"]}>
                {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- file download, not page navigation. */}
                <a href={`/api/proxy/kobo/forms/${formKey}/export/xlsx/`} className="inline-block rounded-md border border-border px-3 py-2 text-sm">
                  Excel workbook
                </a>
                {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- file download, not page navigation. */}
                <a href={`/api/proxy/kobo/forms/${formKey}/export/pdfs/`} className="inline-block rounded-md border border-border px-3 py-2 text-sm">
                  All as PDFs (ZIP)
                </a>
              </IfRole>
            </div>
          </div>
        </Card>
      )}

      <Card>
        {!form ? (
          <p className="text-text-muted text-sm">Loading…</p>
        ) : !form.configured ? (
          <p className="text-text-muted text-sm">{form.title} isn&apos;t connected to KoboToolbox yet.</p>
        ) : error ? (
          <p className="text-danger text-sm">{(error as Error).message}</p>
        ) : isLoading || !data ? (
          <p className="text-text-muted text-sm">Loading…</p>
        ) : data.results.length === 0 ? (
          <p className="text-text-muted text-sm">No submissions yet.</p>
        ) : (
          <>
            <ul className="divide-y divide-border">
              {data.results.map((row) => (
                <li key={row.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-mono text-sm">
                      {row.record}
                      {row.portal_copy && <span className="ml-2 font-sans text-xs text-text-muted">✓ saved in portal</span>}
                    </p>
                    <p className="text-xs text-text-muted">
                      {row.submitted_at ? `Submitted ${new Date(`${row.submitted_at}Z`).toLocaleString()}` : ""}
                      {row.submitted_by ? ` · by ${row.submitted_by}` : " · web form"}
                    </p>
                    {status?.id === row.id && (
                      <p className={`text-xs ${status.tone === "error" ? "text-danger" : "text-text-muted"}`} role="status">
                        {status.text}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      disabled={download.isPending}
                      onClick={() => {
                        setStatus(null);
                        download.mutate(row.id);
                      }}
                    >
                      Download PDF
                    </Button>
                    {form.can_email && forms?.email_configured && (
                      <Button
                        variant="outline"
                        disabled={email.isPending}
                        onClick={() => email.mutate({ id: row.id, recipient: "me" })}
                      >
                        Email to me
                      </Button>
                    )}
                    {form.can_email && form.can_email_respondent && forms?.email_configured && (
                      <Button
                        variant="outline"
                        disabled={email.isPending}
                        onClick={() => {
                          if (window.confirm(`Email ${row.record}'s answers to the respondent's address on file?`)) {
                            email.mutate({ id: row.id, recipient: "respondent" });
                          }
                        }}
                      >
                        Email to respondent
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <Pagination page={page} count={data.count} onPageChange={setPage} label="submissions" />
          </>
        )}
      </Card>
    </AdminShell>
  );
}
