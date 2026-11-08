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
}

export interface CreditTotals {
  quan_administered: number;
  quan_assisted: number;
  kii_administered: number;
  kii_assisted: number;
  quan_qa_passed: number;
  total: number;
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
  can_override: boolean;
}

export const CREDIT_TONE: Record<CreditRow["kind"], string> = {
  ADMINISTERED: "bg-success text-white",
  ASSISTED: "bg-header text-white",
  UNCREDITED: "bg-bg border border-border text-text-muted",
};

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
