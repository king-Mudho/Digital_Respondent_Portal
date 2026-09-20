"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { WriteOnly } from "@/components/admin/RoleGate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { adminFetch } from "@/lib/api/admin";

interface Choice {
  code: string;
  label: string;
}

interface SchemaField {
  name: string;
  path: string;
  label: string;
  type: "text" | "date" | "select_one" | "select_multiple";
  in_repeat: boolean;
  choices?: Choice[];
}

interface Schema {
  form_id: string;
  groups: string[];
  fields: SchemaField[];
}

interface SchemaResponse {
  schema: Schema;
  deterministic_fields: string[];
  ai_configured: boolean;
  kobo_submit_configured: boolean;
}

interface DocumentRecord {
  id: number;
  document_id: string;
  title: string;
  source_file_name: string;
  source_file_pages: number | null;
  ai_draft_status: "" | "running" | "failed";
  ai_draft_error: string;
  ai_draft_progress: string;
  ai_draft: Record<string, unknown> | null;
  ai_draft_generated_at: string | null;
  ai_draft_model: string;
  kobo_submission_uuid: string;
  kobo_submitted_at: string | null;
}

// Matches the section labels in the deployed XLSForm
// (docs/14_DOCUMENTARY_EVIDENCE_MODULE.md).
const GROUP_LABELS: Record<string, string> = {
  section_a: "A. Source Identification and Provenance",
  section_b: "B. Relevance and Evidence-Quality Screen",
  section_c: "C. Novel Financing Models (NFM)",
  section_d: "D. Agribusiness Bankability Index — ABI Core Dimensions",
  section_e: "E. Digital Readiness — Moderator",
  section_f: "F. Aggregation Capability — Moderator",
  section_g: "G. Institutional Environment — Moderator",
  section_h: "H. Food Systems Transformation",
  section_i: "I. Cross-Cutting Inclusion, Resilience and Sustainability",
  section_j: "J. Quantitative Evidence Extraction",
  section_k: "K. Hypothesis / Objective Mapping",
  section_l: "L. Triangulation and Analytical Memo",
};

const REPEAT_GROUP_PATH = "section_j/metric_repeat";
// The most pages the AI can read in one go (backend/apps/evidence/ai_coding.py MAX_PDF_PAGES).
const MAX_PDF_PAGES = 100;
// Reading a longer text in parts (MAX_WHOLE_DOCUMENT_PAGES, CHUNK_PAGES): the ceiling and the part size.
const MAX_WHOLE_DOCUMENT_PAGES = 1500;
const CHUNK_PAGES = 80;

/** Pages a range like "12-60" (or "12") covers; null when it isn't a range yet. */
function rangeLength(text: string): number | null {
  const m = /^\s*(\d+)\s*(?:-\s*(\d+))?\s*$/.exec(text);
  if (!m) return null;
  const start = Number(m[1]);
  const end = Number(m[2] ?? m[1]);
  return end >= start ? end - start + 1 : null;
}
// Long-form fields that read better as a textarea than a one-line input.
const LONG_FIELD_HINTS = ["summary", "note", "memo", "evidence", "mechanism", "interpretation", "assessment", "finding", "reason", "theme", "bias"];

function isLongField(field: SchemaField): boolean {
  const key = field.name.toLowerCase();
  return field.type === "text" && LONG_FIELD_HINTS.some((hint) => key.includes(hint));
}

function FieldControl({
  field,
  value,
  onChange,
  disabled,
}: {
  field: SchemaField;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  if (field.type === "select_one") {
    return (
      <select
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-md border border-border px-3 py-2 text-sm"
      >
        <option value="">—</option>
        {field.choices?.map((c) => (
          <option key={c.code} value={c.code}>
            {c.label}
          </option>
        ))}
      </select>
    );
  }
  if (field.type === "select_multiple") {
    const selected = new Set(Array.isArray(value) ? (value as string[]) : []);
    return (
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {field.choices?.map((c) => (
          <label key={c.code} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={selected.has(c.code)}
              disabled={disabled}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(c.code);
                else next.delete(c.code);
                onChange([...next]);
              }}
            />
            {c.label}
          </label>
        ))}
      </div>
    );
  }
  if (isLongField(field)) {
    return (
      <textarea
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={3}
        className="w-full rounded-md border border-border px-3 py-2 text-sm"
      />
    );
  }
  return (
    <input
      type={field.type === "date" ? "date" : "text"}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="w-full rounded-md border border-border px-3 py-2 text-sm"
    />
  );
}

/** Review screen for an AI-drafted coding of the Document Analysis Tool.
 * Nothing here reaches KoboToolbox until "Submit to KoboToolbox" is
 * clicked -- see backend/apps/evidence/ai_coding.py's docstring for why
 * that human step isn't optional for this particular form. */
export default function DocumentAIDraftPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pages, setPages] = useState("");
  const [wholeDoc, setWholeDoc] = useState(false);

  const { data: schemaData } = useQuery({
    queryKey: ["document-ai-schema"],
    queryFn: () => adminFetch<SchemaResponse>("/documents/ai-draft-schema/"),
    staleTime: Infinity, // the deployed form doesn't change within a session
  });

  const { data: doc, isLoading } = useQuery({
    queryKey: ["document", params.id],
    queryFn: () => adminFetch<DocumentRecord>(`/documents/${params.id}/`),
    // The AI reads in the background (minutes): keep checking until it stops.
    refetchInterval: (query) => (query.state.data?.ai_draft_status === "running" ? 3000 : false),
  });

  // Loads the server's draft into local editable state exactly once per
  // generation -- doc.ai_draft_generated_at changing means a fresh
  // generate/regenerate happened and should overwrite in-progress edits;
  // otherwise a background refetch must never clobber what the RA is typing.
  useEffect(() => {
    if (doc?.ai_draft) setAnswers(doc.ai_draft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc?.ai_draft_generated_at]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["document", params.id] });

  const generate = useMutation({
    mutationFn: () =>
      adminFetch<DocumentRecord>(`/documents/${params.id}/ai-draft/`, {
        method: "POST",
        body: JSON.stringify({ pages: pages.trim(), whole_document: wholeDoc }),
      }),
    onSuccess: () => {
      setError(null);
      setDirty(false);
      setNotice(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not generate a draft."),
  });

  const save = useMutation({
    mutationFn: () =>
      adminFetch<DocumentRecord>(`/documents/${params.id}/ai-draft/`, {
        method: "PUT",
        body: JSON.stringify({ answers }),
      }),
    onSuccess: () => {
      setError(null);
      setDirty(false);
      setNotice(dirty ? "Changes saved." : "Saved. Nothing had changed since the last save.");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save your changes."),
  });

  const submit = useMutation({
    mutationFn: async () => {
      // Always save first, so Submit never files a stale copy of the draft
      // if the RA edited a field and clicked Submit without saving.
      await adminFetch(`/documents/${params.id}/ai-draft/`, { method: "PUT", body: JSON.stringify({ answers }) });
      return adminFetch<DocumentRecord>(`/documents/${params.id}/ai-draft/submit/`, { method: "POST" });
    },
    onSuccess: () => {
      setError(null);
      setDirty(false);
      setNotice("Submitted to KoboToolbox, and a copy is now held in the portal.");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not submit to KoboToolbox."),
  });

  if (isLoading || !doc || !schemaData) {
    return (
      <AdminShell backHref={`/admin/documents/${params.id}`} backLabel="Document">
        <p className="text-text-muted">Loading…</p>
      </AdminShell>
    );
  }

  const { schema, deterministic_fields: deterministicFields, ai_configured: aiConfigured } = schemaData;
  const alreadySubmitted = Boolean(doc.kobo_submitted_at);
  const running = doc.ai_draft_status === "running";
  const isPdf = doc.source_file_name.toLowerCase().endsWith(".pdf");
  const tooLong = isPdf && (doc.source_file_pages ?? 0) > MAX_PDF_PAGES;
  // How many pages this draft would read, and so in how many parts.
  const span = pages.trim() ? rangeLength(pages) : (doc.source_file_pages ?? null);
  const inParts = wholeDoc && span !== null && span > MAX_PDF_PAGES;
  const partCount = span ? Math.ceil(span / CHUNK_PAGES) : 0;
  const overCeiling = isPdf && (doc.source_file_pages ?? 0) > MAX_WHOLE_DOCUMENT_PAGES && !pages.trim();
  const setField = (path: string, value: unknown) => {
    setAnswers((prev) => ({ ...prev, [path]: value }));
    setDirty(true);
    setNotice(null);
  };

  const repeatRows = (Array.isArray(answers[REPEAT_GROUP_PATH]) ? answers[REPEAT_GROUP_PATH] : []) as Record<string, unknown>[];
  const repeatFields = schema.fields.filter((f) => f.path.startsWith(`${REPEAT_GROUP_PATH}/`));

  return (
    <AdminShell backHref={`/admin/documents/${params.id}`} backLabel="Document">
      <h2 className="font-semibold text-xl mb-1">Auto-fill: {doc.title}</h2>
      <p className="text-text-muted text-sm mb-4 font-mono">{doc.document_id}</p>

      {!aiConfigured && (
        <Card className="mb-4">
          <p className="text-sm">AI drafting hasn&rsquo;t been set up yet (ANTHROPIC_API_KEY). Ask the administrator.</p>
        </Card>
      )}
      {error && <p className="text-danger text-sm mb-4">{error}</p>}
      {notice && <p className="text-sm mb-4">{notice}</p>}
      {doc.ai_draft_status === "failed" && doc.ai_draft_error && (
        <p className="text-danger text-sm mb-4">The last attempt failed: {doc.ai_draft_error}</p>
      )}
      {running && (
        <Card className="mb-4 space-y-1">
          <p className="text-sm font-medium">
            The AI is reading the document…{doc.ai_draft_progress ? ` ${doc.ai_draft_progress}` : ""}
          </p>
          <p className="text-xs text-text-muted">
            {/^(Starting|Reading part|Read part|Combining)/.test(doc.ai_draft_progress)
              ? "A long document is read in parts and takes longer, often ten to thirty minutes. "
              : "This usually takes one to five minutes. "}
            You can leave this page and come back; the draft will be here
            when it&rsquo;s ready.
          </p>
        </Card>
      )}

      {alreadySubmitted && (
        <Card className="mb-4 space-y-1">
          <p className="text-sm font-medium">Already submitted to KoboToolbox</p>
          <p className="text-xs text-text-muted">
            {new Date(doc.kobo_submitted_at!).toLocaleString()} · instance {doc.kobo_submission_uuid}
          </p>
          <p className="text-xs text-text-muted">
            The answers below are locked, because changing them here would not change the record in KoboToolbox, and
            submitting again would create a duplicate. To redo the coding, delete that record in KoboToolbox, then
            press Sync on the Completed forms page: this document unlocks.
          </p>
        </Card>
      )}

      <WriteOnly>
        <Card className="mb-4 space-y-3">
          {isPdf && (
            <div className="space-y-1">
              <label className="text-sm text-text-muted" htmlFor="page-range">
                Pages to read{tooLong && !wholeDoc ? " (required)" : " (optional)"}
              </label>
              <input
                id="page-range"
                type="text"
                value={pages}
                onChange={(e) => setPages(e.target.value)}
                placeholder={tooLong ? "e.g. 1-100" : "all pages"}
                disabled={running || generate.isPending}
                className="w-40 rounded-md border border-border px-3 py-2 text-sm block"
              />
              {tooLong && (
                <p className="text-xs text-text-muted">
                  This PDF has {doc.source_file_pages} pages and the AI can read up to {MAX_PDF_PAGES} at a time. Enter
                  the pages that make up this evidence unit, such as a chapter, or read the whole document in parts.
                  Locators will use the original page numbers.
                </p>
              )}
              {tooLong && (
                <label className="flex items-start gap-2 text-sm max-w-xl">
                  <input
                    type="checkbox"
                    checked={wholeDoc}
                    onChange={(e) => setWholeDoc(e.target.checked)}
                    disabled={running || generate.isPending}
                    className="mt-1"
                  />
                  <span>
                    Read the whole document in parts
                    <span className="block text-xs text-text-muted">
                      The AI codes each part of about {CHUNK_PAGES} pages, then combines them into one draft. Leave
                      the page box empty for all {doc.source_file_pages} pages, or enter a longer range.
                      {overCeiling && ` This PDF is over the ${MAX_WHOLE_DOCUMENT_PAGES}-page limit, so enter a range.`}
                    </span>
                  </span>
                </label>
              )}
              {inParts && (
                <p className="text-xs text-text-muted max-w-xl" role="note">
                  About {span} pages in {partCount} parts: roughly {Math.ceil(partCount / 3) * 3 + 3}{" "}
                  minutes, and it uses about {partCount + 1} times the AI of an ordinary draft. Because the ratings are
                  judged across parts, check them especially carefully.
                </p>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              disabled={!aiConfigured || generate.isPending || running}
              onClick={() => {
                if (doc.ai_draft && !window.confirm("This replaces the current draft and any unsaved edits. Continue?")) return;
                if (
                  inParts &&
                  !window.confirm(`Read about ${span} pages in ${partCount} parts? This takes several minutes and costs about ${partCount + 1} times an ordinary draft.`)
                ) {
                  return;
                }
                generate.mutate();
              }}
            >
              {generate.isPending || running ? "Reading the document…" : doc.ai_draft ? "Regenerate draft" : "Generate AI draft"}
            </Button>
            {doc.ai_draft && !alreadySubmitted && (
              <Button variant="outline" disabled={save.isPending || running} onClick={() => save.mutate()}>
                {save.isPending ? "Saving…" : "Save changes"}
              </Button>
            )}
            {doc.ai_draft && !alreadySubmitted && (
              <Button
                disabled={submit.isPending}
                onClick={() => {
                  if (window.confirm("Submit this reviewed draft to KoboToolbox as a completed record?")) submit.mutate();
                }}
              >
                {submit.isPending ? "Submitting…" : "Submit to KoboToolbox"}
              </Button>
            )}
          </div>
          {doc.ai_draft_generated_at && (
            <p className="text-xs text-text-muted">
              Drafted {new Date(doc.ai_draft_generated_at).toLocaleString()} by {doc.ai_draft_model}. Read every
              field before saving or submitting -- this is a starting point, not a finished coding.
            </p>
          )}
        </Card>
      </WriteOnly>

      {!doc.ai_draft ? (
        <Card>
          <p className="text-sm text-text-muted">
            No draft yet. {doc.source_file_name ? "Click “Generate AI draft” above." : "Upload a source file on the document page first."}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {schema.groups
            .filter((g) => g !== "section_j")
            .map((group) => {
              const fields = schema.fields.filter((f) => f.path.startsWith(`${group}/`) && !f.in_repeat);
              if (fields.length === 0) return null;
              return (
                <Card key={group} className="space-y-4">
                  <h3 className="font-medium">{GROUP_LABELS[group] ?? group}</h3>
                  {group === "section_a" && (
                    <p className="text-xs text-text-muted">
                      The grey fields come from the record (the AI read them from the document&rsquo;s first pages when
                      the record was made). To correct one,{" "}
                      <Link href={`/admin/documents/${params.id}`} className="underline">edit the record details</Link>{" "}
                     ; the change appears here and is used when you submit.
                    </p>
                  )}
                  {fields.map((field) => {
                    const isDeterministic = deterministicFields.includes(field.path);
                    return (
                      <div key={field.path} className="space-y-1">
                        <label className="text-sm text-text-muted">{field.label}</label>
                        {isDeterministic ? (
                          <p className="text-sm rounded-md bg-surface px-3 py-2">
                            {String(answers[field.path] ?? "") || "—"}
                          </p>
                        ) : (
                          <FieldControl
                            field={field}
                            value={answers[field.path]}
                            onChange={(v) => setField(field.path, v)}
                            disabled={alreadySubmitted}
                          />
                        )}
                      </div>
                    );
                  })}
                </Card>
              );
            })}

          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{GROUP_LABELS.section_j}</h3>
              {!alreadySubmitted && (
                <Button
                  variant="outline"
                  onClick={() => setField(REPEAT_GROUP_PATH, [...repeatRows, {}])}
                >
                  Add metric
                </Button>
              )}
            </div>
            {repeatRows.length === 0 && <p className="text-sm text-text-muted">No quantitative metrics recorded.</p>}
            {repeatRows.map((row, i) => (
              <div key={i} className="border border-border rounded-md p-3 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {repeatFields.map((field) => (
                    <div key={field.path} className="space-y-1">
                      <label className="text-sm text-text-muted">{field.label}</label>
                      <FieldControl
                        field={field}
                        value={row[field.name]}
                        disabled={alreadySubmitted}
                        onChange={(v) => {
                          const next = [...repeatRows];
                          next[i] = { ...next[i], [field.name]: v };
                          setField(REPEAT_GROUP_PATH, next);
                        }}
                      />
                    </div>
                  ))}
                </div>
                {!alreadySubmitted && (
                  <Button
                    variant="outline"
                    onClick={() => setField(REPEAT_GROUP_PATH, repeatRows.filter((_, j) => j !== i))}
                  >
                    Remove this metric
                  </Button>
                )}
              </div>
            ))}
          </Card>
        </div>
      )}
    </AdminShell>
  );
}
