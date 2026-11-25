/** Research assistants, their work and the completions credited to them (backend apps/ra, 2026-11-08). */

export interface CreditRow {
  id: number;
  study: "QUAN" | "KII";
  study_label: string;
  ref: string;
  organisation: string;
  submitted_at: string;
  kind: "ADMINISTERED" | "ASSISTED" | "UNCREDITED";
  kind_label: string;
  ra: string;
  ra_name: string;
  evidence: string;
  qa_status: string;
  overridden: boolean;
  override_reason: string;
  overridden_by: string;
  /** The commission this completion earns its RA (0 with no RA). */
  amount_usd: number;
}

export interface CreditTotals {
  quan_administered: number;
  quan_assisted: number;
  kii_administered: number;
  kii_assisted: number;
  quan_qa_passed: number;
  total: number;
  /** Commission earned in the period, US$ (questionnaires only once QA-passed). */
  earned_usd: number;
  /** Credited questionnaires still pending or queried in QA: they earn once they pass. */
  awaiting_qa: number;
}

export interface Workload {
  main_assigned: number;
  kii_assigned: number;
  main_by_status: Record<string, number>;
  kii_by_status: Record<string, number>;
  calls_7d: number;
  contacts_7d: number;
}

export interface MyWork {
  name: string;
  workload: Workload;
  totals: (CreditTotals & { name: string }) | null;
  credits: CreditRow[];
  assist_days: number;
  /** Commission per credited completion, US$ (settings.RA_COMMISSION_USD). */
  commission_usd: number;
  /** The PI only: paused research assistants, to reactivate (25 Nov 2026). Never sent to an RA. */
  paused?: PausedRA[];
}

export interface TeamMember {
  id: number;
  username: string;
  name: string;
  role: string;
  role_label: string;
  workload: Workload;
  credits: CreditTotals;
}

export interface Team {
  team: TeamMember[];
  others: (CreditTotals & { name: string; username: string })[];
  uncredited: number;
  credits: CreditRow[];
  unassigned: { main: number; kii: number };
  /** Accounts holding open Main-400 work (cases and activated Reserves), to move it from. */
  main_holders?: { id: number; username: string; count: number }[];
  assist_days: number;
  commission_usd: number;
  /** Commission earned by everyone in the period, US$. */
  earned_usd: number;
  can_override: boolean;
  /** Deactivated RA accounts (25 Nov 2026): shown in red, for the PI to reactivate. */
  paused?: PausedRA[];
  /** Only the PI pauses or reactivates an RA. */
  can_change_status?: boolean;
}

export interface PausedRA {
  id: number;
  username: string;
  name: string;
  role: string;
  role_label: string;
  paused_at: string | null;
  paused_reason: string;
  last_login: string | null;
  workload: Workload;
  /** Open work still on the account that they did not find themselves. */
  open: { main: number; kii: number };
  total: number;
  earned_usd: number;
}

export const CREDIT_TONE: Record<CreditRow["kind"], string> = {
  ADMINISTERED: "bg-success text-white",
  ASSISTED: "bg-header text-white",
  UNCREDITED: "bg-bg border border-border text-text-muted",
};

/** US$2.50 */
export function usd(amount: number | undefined): string {
  return `US$${(amount ?? 0).toFixed(2)}`;
}

/** ?since=&until= for a pay period; "" for all time. */
export function periodQuery(since: string, until: string): string {
  const q = new URLSearchParams();
  if (since) q.set("since", since);
  if (until) q.set("until", until);
  return q.toString();
}

export function firstOfMonth(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
