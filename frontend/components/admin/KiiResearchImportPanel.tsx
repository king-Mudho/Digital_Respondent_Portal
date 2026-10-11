"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminUpload } from "@/lib/api/admin";

interface ImportRecord {
  kii_id: string;
  record_id: number | null;
  organisation: string;
  status: "ready" | "imported" | "skipped" | "nothing new";
  contacts: number;
  facts: number;
  not_found: number;
  prep: string[];
  warnings: string[];
}

interface ImportResult {
  dry_run: boolean;
  file: string;
  records: ImportRecord[];
  totals: { contacts: number; facts: number; not_found: number; records: number };
  examples_skipped: number;
  missing_sheets: string[];
}

/**
 * Loads a ChatGPT background-research workbook (the KII research pack's Fill A/B/C sheets) into the review flows that
 * already exist (backend apps/proit/kii_import.py): contacts become suggestions on each record's "Find contact
 * details" panel, facts become PROIT proposals to Accept / Edit / Reject, and the interview-prep notes go into the
 * gap engine. First a check that keeps nothing, then the import. PI and Field Coordinator only.
 */
export function KiiResearchImportPanel() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: (dryRun: boolean) => {
      const form = new FormData();
      form.append("file", file as File);
      form.append("dry_run", dryRun ? "true" : "false");
      return adminUpload<ImportResult>("/proit/kii-import/", form);
    },
    onSuccess: (result) => {
      setError(null);
      if (result.dry_run) {
        setPreview(result);
        setDone(null);
      } else {
        setDone(result);
        setPreview(null);
        queryClient.invalidateQueries({ queryKey: ["kii"] });
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The file could not be read."),
  });

  const shown = done ?? preview;
  return (
    <Card className="mb-4 space-y-2" aria-label="Import ChatGPT research">
      <h3 className="font-medium text-sm">Import background research (ChatGPT workbook)</h3>
      <p className="text-xs text-text-muted">
        Upload the Excel file ChatGPT returned from the KII research pack. Nothing goes onto a record directly: contacts
        become suggestions under <em>Find contact details</em> and facts become PROIT findings to accept, edit or reject
        on each record&apos;s page. Interview-prep notes are added to the PROIT gap engine, marked as imported. Locked
        profiles are never changed.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id="kii-import-file"
          type="file"
          accept=".xlsx"
          aria-label="ChatGPT research workbook"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setPreview(null);
            setDone(null);
            setError(null);
          }}
          className="text-sm max-w-full"
        />
        <Button variant="outline" disabled={!file || run.isPending} onClick={() => run.mutate(true)}>
          {run.isPending && !preview ? "Checking…" : "Check file"}
        </Button>
        {preview && preview.totals.records > 0 && (
          <Button disabled={run.isPending} onClick={() => run.mutate(false)}>
            {run.isPending ? "Importing…" : `Import ${preview.totals.records} record${preview.totals.records === 1 ? "" : "s"}`}
          </Button>
        )}
      </div>
      {error && <p className="text-danger text-sm">{error}</p>}

      {shown && (
        <div className="space-y-2 text-sm">
          <p>
            {shown.dry_run ? "This file would add" : "Added"}: {shown.totals.contacts} contact suggestions, {shown.totals.facts} PROIT
            findings{shown.totals.not_found ? ` (and ${shown.totals.not_found} marked not found)` : ""}, for {shown.totals.records} record
            {shown.totals.records === 1 ? "" : "s"}.
            {shown.examples_skipped > 0 && ` ${shown.examples_skipped} example rows left out.`}
            {shown.missing_sheets.length > 0 && ` Sheets not in the file: ${shown.missing_sheets.join(", ")}.`}
          </p>
          {done && (
            <p className="text-xs">
              Next: open each record below and review its suggestions (Find contact details) and findings (Pre-Interview
              Profile). Check each source link before accepting, then lock the profile and send the invitation.
            </p>
          )}
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-text-muted">
                  <th className="px-2 py-1">KII ID</th>
                  <th className="px-2 py-1">Organisation</th>
                  <th className="px-2 py-1">Contacts</th>
                  <th className="px-2 py-1">Findings</th>
                  <th className="px-2 py-1">Interview notes</th>
                  <th className="px-2 py-1">Status and warnings</th>
                </tr>
              </thead>
              <tbody>
                {shown.records.map((r) => (
                  <tr key={r.kii_id} className="border-t border-border align-top">
                    <td className="px-2 py-1 font-mono">
                      {r.record_id ? <Link href={`/admin/kii/${r.record_id}`} className="underline">{r.kii_id}</Link> : r.kii_id}
                    </td>
                    <td className="px-2 py-1">{r.organisation}</td>
                    <td className="px-2 py-1 tabular-nums">{r.contacts}</td>
                    <td className="px-2 py-1 tabular-nums">{r.facts}{r.not_found ? ` (+${r.not_found} not found)` : ""}</td>
                    <td className="px-2 py-1">{r.prep.length ? `${r.prep.length} added` : "—"}</td>
                    <td className="px-2 py-1">
                      <span className="rounded-full border border-border px-2 py-0.5">{r.status}</span>
                      {r.warnings.map((w, i) => <span key={i} className="block text-text-muted mt-1">{w}</span>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}
