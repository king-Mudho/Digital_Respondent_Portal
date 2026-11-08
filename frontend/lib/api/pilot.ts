/**
 * The ZAS 2026 pilot strand (backend apps/kobo/pilot.py, PI decision 8 Nov 2026): pilot records are counted beside
 * the main study, never inside it, so every figure that adds them says how it splits.
 */
export function withPilot(main: number, pilot: number | undefined): { total: number; split: string } {
  const p = pilot ?? 0;
  return { total: main + p, split: p ? `${main} main + ${p} ZAS 2026 pilot` : "" };
}

export type PilotStrand = "QUAN" | "KII" | "DOCUMENT";

export interface PilotRecordRow {
  id: number;
  strand: PilotStrand;
  form: string;
  form_title: string;
  kobo_id: number;
  reference: string;
  collected_on: string | null;
  consented: boolean | null;
  summary: Record<string, string>;
  flags: string[];
  included: boolean;
  exclusion_reason: string;
  decided_by: string;
  decided_at: string | null;
}

export interface PilotListing {
  counts: { quan: number; kii: number; documents: number };
  totals: { form: string; title: string; strand: PilotStrand; included: number; excluded: number }[];
  results: PilotRecordRow[];
  last_synced_at: string | null;
}
