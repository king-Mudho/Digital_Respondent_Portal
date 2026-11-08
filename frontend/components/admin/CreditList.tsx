"use client";

import { CREDIT_TONE, type CreditRow } from "@/lib/api/ra";

/** Completed submissions with who earned each one: the record RAs are paid from. `action` adds a control per row. */
export function CreditList({
  credits,
  showRA,
  action,
  empty,
}: {
  credits: CreditRow[];
  showRA: boolean;
  action?: (c: CreditRow) => React.ReactNode;
  empty: string;
}) {
  if (credits.length === 0) return <p className="text-sm text-text-muted">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-text-muted">
            <th className="px-3 py-2">Submitted</th>
            <th className="px-3 py-2">Study</th>
            <th className="px-3 py-2">Case / KII</th>
            {showRA && <th className="px-3 py-2">Research assistant</th>}
            <th className="px-3 py-2">Credit</th>
            <th className="px-3 py-2">Evidence</th>
            {action && <th className="px-3 py-2" />}
          </tr>
        </thead>
        <tbody>
          {credits.map((c) => (
            <tr key={c.id} className="border-b border-border align-top last:border-0">
              <td className="whitespace-nowrap px-3 py-2 tabular-nums">{new Date(c.submitted_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</td>
              <td className="px-3 py-2 text-xs">
                {c.study === "QUAN" ? "Questionnaire" : "KII"}
                {c.qa_status && <span className="block text-text-muted">QA: {c.qa_status}</span>}
              </td>
              <td className="px-3 py-2">
                <span className="font-mono text-xs">{c.ref}</span>
                <span className="block text-xs text-text-muted">{c.organisation}</span>
              </td>
              {showRA && <td className="px-3 py-2 font-medium">{c.ra_name || <span className="font-normal text-text-muted">—</span>}</td>}
              <td className="px-3 py-2">
                <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${CREDIT_TONE[c.kind]}`}>
                  {c.kind === "ADMINISTERED" ? "Administered" : c.kind === "ASSISTED" ? "Assisted" : "No RA"}
                </span>
                {c.overridden && <span className="block text-[11px] text-text-muted">set by {c.overridden_by}</span>}
              </td>
              <td className="px-3 py-2 text-xs text-text-muted">
                {c.evidence}
                {c.override_reason && <span className="block text-text">“{c.override_reason}”</span>}
              </td>
              {action && <td className="px-3 py-2 text-right">{action(c)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
