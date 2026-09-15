"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/admin/AdminShell";
import {
  ChartCard,
  Columns,
  formatValue,
  HorizontalBars,
  Meter,
  SERIES_1,
  SERIES_2,
  STATUS,
} from "@/components/reports/charts";
import { Card } from "@/components/ui/card";
import { adminFetch } from "@/lib/api/admin";

type Range = "7" | "30" | "90" | "all";

interface Breakdown extends Record<string, unknown> {
  key: string;
  label: string;
  cases: number;
  invited: number;
  submitted: number;
  qa_passed: number;
  response_rate: number | null;
  invited_share: number;
  submitted_share: number;
}

interface Report {
  generated_at: string;
  range: { key: Range; days: number | null; since: string | null };
  kpis: {
    sample_target: number;
    active_sample: number;
    cases_invited: number;
    cases_submitted: number;
    cases_qa_passed: number;
    response_rate: number | null;
    completion_rate: number | null;
    median_completion_minutes: number | null;
    submissions_in_range: number;
    follow_ups_sent_in_range: number;
    withdrawals: number;
    reserves_activated: number;
    kii_completed: number;
    kii_target: number;
    documents_included: number;
    documents_target_low: number;
    documents_target_high: number;
    cost_total: string;
    cost_per_qa_passed: string | null;
  };
  funnel: Array<{ stage: string; label: string; cases: number }>;
  workflow: Array<{ status: string; label: string; cases: number }>;
  submissions_by_day: Array<{ date: string; submissions: number }>;
  breakdowns: Record<"province" | "actor_family" | "size_class", Breakdown[]>;
  administration_modes: Array<{ code: string; label: string; submissions: number }>;
  mode_imbalance: { threshold: number | null; dominant_mode: string | null; share: number | null; alert: boolean };
  duration_histogram: Array<{ bucket: string; min_minutes: number; max_minutes: number | null; submissions: number }>;
  duration_thresholds_minutes: { min: number | null; max: number | null };
  qa: { outcomes: Array<{ status: string; label: string; count: number }>; flags: Array<{ rule: string; count: number }> };
  contact: { outcomes: Array<{ outcome: string; label: string; count: number }>; appointments: Array<{ status: string; count: number }> };
  kii: Array<{ status: string; label: string; count: number }>;
  documents: Array<{ status: string; label: string; count: number }>;
}

const RANGES: Array<{ key: Range; label: string; phrase: string }> = [
  { key: "7", label: "Last 7 days", phrase: "the last 7 days" },
  { key: "30", label: "Last 30 days", phrase: "the last 30 days" },
  { key: "90", label: "Last 90 days", phrase: "the last 90 days" },
  { key: "all", label: "All time", phrase: "all time" },
];

const plural = (n: number, one: string, many: string) => `${formatValue(n)} ${n === 1 ? one : many}`;

const BREAKDOWNS = [
  { key: "province", label: "Province" },
  { key: "actor_family", label: "Organisation type" },
  { key: "size_class", label: "Size" },
] as const;

const QA_COLOURS: Record<string, string> = {
  QA_PASSED: STATUS.good,
  QUERY: STATUS.warning,
  REJECTED: STATUS.critical,
  PENDING: STATUS.neutral,
};

const RULE_LABELS: Record<string, string> = {
  min_plausible_duration_seconds: "Completed implausibly fast",
  max_plausible_duration_seconds: "Took implausibly long",
  hard_stop_missing_required_fields: "Required answers missing",
  max_missing_optional_fields_percent: "Too many optional answers missing",
  duplicate_master_id_window_hours: "Possible duplicate for the organisation",
};

const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

function Kpi({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
      {detail && <p className="text-xs text-text-muted mt-1">{detail}</p>}
    </div>
  );
}

/**
 * Reports: how fieldwork is going, across the whole study. Counts and rates
 * only -- no organisation or person is named anywhere here, and nothing a
 * respondent answered is scored (AGENTS.md ground rule 3).
 */
export default function ReportsPage() {
  const [range, setRange] = useState<Range>("30");
  const [breakdown, setBreakdown] = useState<(typeof BREAKDOWNS)[number]["key"]>("province");

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["reports", range],
    queryFn: () => adminFetch<Report>(`/reports/overview/?range=${range}`),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });

  const rangeLabel = RANGES.find((r) => r.key === range)?.phrase ?? "";

  return (
    <AdminShell backHref="/admin/dashboard" backLabel="Dashboard">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h2 className="font-semibold text-xl">Reports</h2>
          <p className="text-sm text-text-muted">
            Fieldwork progress, reach and data quality. Counts and rates only.
          </p>
        </div>
        <div role="group" aria-label="Date range" className="flex flex-wrap gap-1 rounded-md border border-border bg-surface p-1">
          {RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              aria-pressed={range === r.key}
              onClick={() => setRange(r.key)}
              className={`rounded px-3 py-1.5 text-sm ${range === r.key ? "bg-header text-white" : "text-text hover:bg-bg"}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <Card>
          <p className="text-danger text-sm">{(error as Error).message}</p>
        </Card>
      ) : isLoading || !data ? (
        <p className="text-text-muted">Loading…</p>
      ) : (
        <div className={`space-y-4 transition-opacity ${isFetching ? "opacity-60" : ""}`}>
          <p className="text-xs text-text-muted">
            Case progress is cumulative. Time-based figures cover {rangeLabel}
            {data.range.since ? ` (since ${shortDate(data.range.since)})` : ""}. Updated{" "}
            {new Date(data.generated_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}.
          </p>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Kpi
              label="Questionnaires submitted"
              value={formatValue(data.kpis.cases_submitted)}
              detail={`of ${formatValue(data.kpis.sample_target)} Main cases`}
            />
            <Kpi
              label="Passed QA"
              value={formatValue(data.kpis.cases_qa_passed)}
              detail={`${formatValue(data.kpis.completion_rate, "percent")} of the target`}
            />
            <Kpi
              label="Response rate"
              value={formatValue(data.kpis.response_rate, "percent")}
              detail={`${formatValue(data.kpis.cases_submitted)} of ${formatValue(data.kpis.cases_invited)} invited cases`}
            />
            <Kpi
              label="Median completion time"
              value={formatValue(data.kpis.median_completion_minutes, "minutes")}
              detail={`${plural(data.kpis.submissions_in_range, "submission", "submissions")}, ${rangeLabel}`}
            />
            <Kpi label="Follow-ups sent" value={formatValue(data.kpis.follow_ups_sent_in_range)} detail={rangeLabel} />
            <Kpi label="Withdrawals" value={formatValue(data.kpis.withdrawals)} detail="all time" />
            <Kpi label="Reserves activated" value={formatValue(data.kpis.reserves_activated)} detail="all time" />
            <Kpi
              label="Fieldwork cost"
              value={`$${formatValue(Number(data.kpis.cost_total))}`}
              detail={data.kpis.cost_per_qa_passed ? `$${data.kpis.cost_per_qa_passed} per QA-passed case` : "per case once QA passes begin"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Case funnel"
              subtitle="Each case counted once, at every stage it has reached"
              rows={data.funnel}
              columns={[
                { key: "label", label: "Stage", kind: "text" },
                { key: "cases", label: "Cases", kind: "count" },
              ]}
            >
              <HorizontalBars rows={data.funnel} labelKey="label" series={[{ key: "cases", name: "Cases", color: SERIES_1 }]} />
            </ChartCard>

            <ChartCard
              title="Submissions per day"
              subtitle={`Questionnaires received, ${rangeLabel}`}
              rows={data.submissions_by_day}
              columns={[
                { key: "date", label: "Date", kind: "text" },
                { key: "submissions", label: "Submissions", kind: "count" },
              ]}
              empty={`No questionnaires received in ${rangeLabel}.`}
            >
              <Columns rows={data.submissions_by_day} xKey="date" yKey="submissions" name="Submissions" xTickFormatter={shortDate} />
            </ChartCard>
          </div>

          <ChartCard
            title="Coverage"
            subtitle="Share of each group's cases invited and submitted — low bars show where to focus contact effort"
            rows={data.breakdowns[breakdown]}
            columns={[
              { key: "label", label: BREAKDOWNS.find((b) => b.key === breakdown)!.label, kind: "text" },
              { key: "cases", label: "Cases", kind: "count" },
              { key: "invited", label: "Invited", kind: "count" },
              { key: "submitted", label: "Submitted", kind: "count" },
              { key: "qa_passed", label: "Passed QA", kind: "count" },
              { key: "invited_share", label: "Share invited", kind: "percent" },
              { key: "response_rate", label: "Response rate", kind: "percent" },
            ]}
          >
            <div className="space-y-2">
              <div role="group" aria-label="Break down by" className="flex flex-wrap gap-2 text-sm">
                {BREAKDOWNS.map((b) => (
                  <button
                    key={b.key}
                    type="button"
                    aria-pressed={breakdown === b.key}
                    onClick={() => setBreakdown(b.key)}
                    className={`rounded-full border px-3 py-1 ${breakdown === b.key ? "border-header bg-header text-white" : "border-border"}`}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
              <HorizontalBars
                rows={data.breakdowns[breakdown]}
                labelKey="label"
                valueKind="percent"
                series={[
                  { key: "invited_share", name: "Invited", color: SERIES_1 },
                  { key: "submitted_share", name: "Submitted", color: SERIES_2 },
                ]}
              />
            </div>
          </ChartCard>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Time to complete the questionnaire"
              subtitle={
                data.duration_thresholds_minutes.min || data.duration_thresholds_minutes.max
                  ? `QA flags under ${data.duration_thresholds_minutes.min ?? "—"} and over ${data.duration_thresholds_minutes.max ?? "—"} minutes`
                  : "Minutes from opening the form to finishing it"
              }
              rows={data.duration_histogram}
              columns={[
                { key: "bucket", label: "Minutes", kind: "text" },
                { key: "submissions", label: "Submissions", kind: "count" },
              ]}
              empty={`No completed questionnaires with a recorded time in ${rangeLabel}.`}
            >
              <Columns rows={data.duration_histogram} xKey="bucket" yKey="submissions" name="Submissions" />
            </ChartCard>

            <ChartCard
              title="QA outcomes"
              subtitle={`Submissions received in ${rangeLabel}, by current QA state`}
              rows={data.qa.outcomes}
              columns={[
                { key: "label", label: "State", kind: "text" },
                { key: "count", label: "Submissions", kind: "count" },
              ]}
            >
              <HorizontalBars
                rows={data.qa.outcomes}
                labelKey="label"
                series={[{ key: "count", name: "Submissions", color: SERIES_1 }]}
                colorFor={(row) => QA_COLOURS[row.status] ?? STATUS.neutral}
              />
            </ChartCard>

            <ChartCard
              title="Why QA flagged submissions"
              subtitle={`Automated flags raised, ${rangeLabel}`}
              rows={data.qa.flags.map((f) => ({ ...f, label: RULE_LABELS[f.rule] ?? f.rule }))}
              columns={[
                { key: "label", label: "Reason", kind: "text" },
                { key: "count", label: "Flags", kind: "count" },
              ]}
              empty="No automated QA flags."
            >
              <HorizontalBars
                rows={data.qa.flags.map((f) => ({ ...f, label: RULE_LABELS[f.rule] ?? f.rule }))}
                labelKey="label"
                series={[{ key: "count", name: "Flags", color: SERIES_1 }]}
              />
            </ChartCard>

            <ChartCard
              title="How questionnaires were completed"
              subtitle={
                data.mode_imbalance.alert
                  ? `⚠ ${data.mode_imbalance.dominant_mode} is ${formatValue(data.mode_imbalance.share, "percent")} of submissions — above the ${formatValue(data.mode_imbalance.threshold, "percent")} QA alert level`
                  : `Administration mode, ${rangeLabel}`
              }
              rows={data.administration_modes}
              columns={[
                { key: "label", label: "Mode", kind: "text" },
                { key: "submissions", label: "Submissions", kind: "count" },
              ]}
            >
              <HorizontalBars rows={data.administration_modes} labelKey="label" series={[{ key: "submissions", name: "Submissions", color: SERIES_1 }]} />
            </ChartCard>

            <ChartCard
              title="Contact attempts"
              subtitle={`Outcome of logged calls and messages, ${rangeLabel}`}
              rows={data.contact.outcomes}
              columns={[
                { key: "label", label: "Outcome", kind: "text" },
                { key: "count", label: "Attempts", kind: "count" },
              ]}
              empty={`No contact attempts logged in ${rangeLabel}.`}
            >
              <HorizontalBars rows={data.contact.outcomes} labelKey="label" series={[{ key: "count", name: "Attempts", color: SERIES_1 }]} />
            </ChartCard>

            <ChartCard
              title="Where Main cases are in the workflow"
              subtitle="Current status of each of the Main cases"
              rows={data.workflow.filter((w) => w.cases > 0)}
              columns={[
                { key: "label", label: "Status", kind: "text" },
                { key: "cases", label: "Cases", kind: "count" },
              ]}
            >
              <HorizontalBars
                rows={data.workflow.filter((w) => w.cases > 0).map((w) => ({ ...w, label: `${w.status} ${w.label}` }))}
                labelKey="label"
                series={[{ key: "cases", name: "Cases", color: SERIES_1 }]}
              />
            </ChartCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="space-y-4">
              <h3 className="font-medium">Qualitative and documentary strands</h3>
              <Meter label="KII interviews completed" value={data.kpis.kii_completed} target={data.kpis.kii_target} />
              <Meter
                label="Documents included in the evidence base"
                value={data.kpis.documents_included}
                target={data.kpis.documents_target_high}
                note={`Target ${data.kpis.documents_target_low}–${data.kpis.documents_target_high}`}
              />
            </Card>
            <ChartCard
              title="KII interviews by status"
              rows={data.kii}
              columns={[
                { key: "label", label: "Status", kind: "text" },
                { key: "count", label: "Interviews", kind: "count" },
              ]}
            >
              <HorizontalBars rows={data.kii} labelKey="label" series={[{ key: "count", name: "Interviews", color: SERIES_1 }]} />
            </ChartCard>
          </div>
        </div>
      )}
    </AdminShell>
  );
}
