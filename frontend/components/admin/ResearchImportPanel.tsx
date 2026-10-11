"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminUpload } from "@/lib/api/admin";

interface ImportRecord {
  record: string;
  record_id: number | string | null;
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

const TARGETS = {
  kii: {
    endpoint: "/proit/kii-import/",
    pack: "KII research pack",
    idLabel: "KII ID",
    link: (id: number | string) => `/admin/kii/${id}`,
    review: "Find contact details) and findings (Pre-Interview Profile). Check each source link before accepting, then lock the profile and send the invitation.",
    extra: " Interview-prep notes are added to the PROIT gap engine, marked as imported.",
  },
  main: {
    endpoint: "/proit/main-import/",
    pack: "Main-400 research pack",
    idLabel: "Sample ID",
    link: (id: number | string) => `/admin/sample/${id}`,
    review: "Find contact details) and findings (Pre-Interview Profile). Check each source link before accepting; once the case has a verified respondent with a contact, it can be invited.",
    extra: "",
  },
} as const;

/**
 * Loads a ChatGPT background-research workbook (a research pack's Fill sheets) into the review flows that already
 * exist (backend apps/proit/research_import.py): contacts become suggestions on each record's or case's "Find contact
 * details" panel, facts become PROIT proposals to Accept / Edit / Reject, and, for KII, the interview-prep notes go into
 * the gap engine. First a check that keeps nothing, then the import. PI and Field Coordinator only.
 */
export function ResearchImportPanel({ target }: { target: keyof typeof TARGETS }) {
  const t = TARGETS[target];
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
      return adminUpload<ImportResult>(t.endpoint, form);
    },
    onSuccess: (result) => {
      setError(null);
      if (result.dry_run) {
        setPreview(result);
        setDone(null);
      } else {
        setDone(result);
        setPreview(null);
        queryClient.invalidateQueries({ queryKey: [target === "kii" ? "kii" : "sample-cases"] });
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "The file could not be read."),
  });

  const shown = done ?? preview;
  return (
    <Card className="mb-4 space-y-2" aria-label="Import ChatGPT research">
      <h3 className="font-medium text-sm">Import background research (ChatGPT workbook)</h3>
      <p className="text-xs text-text-muted">
        Upload the Excel file ChatGPT returned from the {t.pack}. Nothing goes onto a {target === "kii" ? "record" : "case"}{" "}
        directly: contacts become suggestions under <em>Find contact details</em> and facts become PROIT findings to
        accept, edit or reject on each {target === "kii" ? "record" : "case"}&apos;s page.{t.extra} Locked profiles are
        never changed.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={`${target}-import-file`}
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
              Next: open each {target === "kii" ? "record" : "case"} below and review its suggestions ({t.review}
            </p>
          )}
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-text-muted">
                  <th className="px-2 py-1">{t.idLabel}</th>
                  <th className="px-2 py-1">Organisation</th>
                  <th className="px-2 py-1">Contacts</th>
                  <th className="px-2 py-1">Findings</th>
                  {target === "kii" && <th className="px-2 py-1">Interview notes</th>}
                  <th className="px-2 py-1">Status and warnings</th>
                </tr>
              </thead>
              <tbody>
                {shown.records.map((r) => (
                  <tr key={r.record} className="border-t border-border align-top">
                    <td className="px-2 py-1 font-mono">
                      {r.record_id ? <Link href={t.link(r.record_id)} className="underline">{r.record}</Link> : r.record}
                    </td>
                    <td className="px-2 py-1">{r.organisation}</td>
                    <td className="px-2 py-1 tabular-nums">{r.contacts}</td>
                    <td className="px-2 py-1 tabular-nums">{r.facts}{r.not_found ? ` (+${r.not_found} not found)` : ""}</td>
                    {target === "kii" && <td className="px-2 py-1">{r.prep.length ? `${r.prep.length} added` : "—"}</td>}
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
