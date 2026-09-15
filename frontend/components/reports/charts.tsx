"use client";

import { useEffect, useId, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";

/*
 * Chart tokens. Categorical slots 1-2 validated with the dataviz palette
 * validator against the portal's white surface (CVD ΔE 24.7, normal-vision
 * ΔE 33.6, both >= 3:1). Status colours are only ever used for a state and
 * always sit beside a text label.
 */
export const SERIES_1 = "#2a78d6";
export const SERIES_2 = "#eb6834";
export const STATUS = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b", neutral: "#898781" };
const GRID = "#e1e0d9";
const AXIS = "#898781";
const INK_MUTED = "#5b6b7a";

const number = new Intl.NumberFormat("en-GB");

export function formatValue(value: number | null | undefined, kind: "count" | "percent" | "minutes" = "count") {
  if (value === null || value === undefined) return "—";
  if (kind === "percent") return `${Math.round(value * 100)}%`;
  if (kind === "minutes") return `${number.format(value)} min`;
  return number.format(value);
}

export interface Column<T> {
  key: keyof T & string;
  label: string;
  kind?: "count" | "percent" | "minutes" | "text";
}

/** A chart with its own table view, so no value is only reachable by hovering. */
export function ChartCard<T extends Record<string, unknown>>({
  title,
  subtitle,
  rows,
  columns,
  children,
  empty,
}: {
  title: string;
  subtitle?: string;
  rows: T[];
  columns: Column<T>[];
  children: ReactNode;
  empty?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  const headingId = useId();
  const hasData = rows.some((row) => columns.some((c) => c.kind !== "text" && Number(row[c.key]) > 0));

  return (
    <section aria-labelledby={headingId}>
      <Card className="space-y-3 h-full">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 id={headingId} className="font-medium">
              {title}
            </h3>
            {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
          </div>
          {hasData && (
            <button
              type="button"
              onClick={() => setShowTable((v) => !v)}
              className="text-xs text-header underline"
              aria-pressed={showTable}
            >
              {showTable ? "Show chart" : "Show table"}
            </button>
          )}
        </div>
        {!hasData ? (
          <p className="text-sm text-text-muted py-6">{empty ?? "Nothing recorded yet."}</p>
        ) : showTable ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted">
                  {columns.map((c) => (
                    <th key={c.key} className={`py-1 pr-3 font-normal ${c.kind && c.kind !== "text" ? "text-right" : ""}`}>
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={`py-1 pr-3 ${c.kind && c.kind !== "text" ? "text-right tabular-nums" : ""}`}
                      >
                        {c.kind && c.kind !== "text"
                          ? formatValue(row[c.key] as number | null, c.kind)
                          : String(row[c.key] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </Card>
    </section>
  );
}

function TooltipBox({
  active,
  payload,
  label,
  kind,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; color?: string; payload?: Record<string, unknown> }>;
  label?: string | number;
  kind?: "count" | "percent" | "minutes";
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="text-text-muted mb-1">{label}</p>
      {payload.map((item, i) => (
        <p key={i} className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-0.5 w-3" style={{ background: item.color }} />
          <span className="font-semibold tabular-nums">{formatValue(item.value ?? 0, kind)}</span>
          {payload.length > 1 && <span className="text-text-muted">{item.name}</span>}
        </p>
      ))}
    </div>
  );
}

const axisProps = { stroke: GRID, tick: { fill: AXIS, fontSize: 11 }, tickLine: false } as const;

type Row = Record<string, unknown>;

/** True on phone-width screens, where category labels must give the bars room. */
function useNarrow() {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 640px)");
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return narrow;
}

/** Horizontal bars for labelled categories, one series or two. */

export function HorizontalBars<T extends Row>({
  rows,
  labelKey,
  series,
  valueKind = "count",
  colorFor,
}: {
  rows: T[];
  labelKey: string;
  series: Array<{ key: string; name: string; color: string }>;
  valueKind?: "count" | "percent" | "minutes";
  /** Per-bar colour for a single series that encodes a state (status colours). */
  colorFor?: (row: T) => string;
}) {
  const barSize = series.length > 1 ? 12 : 18;
  const rowHeight = series.length > 1 ? 40 : 32;
  const height = Math.max(120, rows.length * rowHeight + (series.length > 1 ? 56 : 24));
  const longest = Math.max(...rows.map((r) => String(r[labelKey]).length), 4);
  const narrow = useNarrow();

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows as Row[]} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 4 }} barGap={2}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis
            type="number"
            allowDecimals={valueKind === "percent"}
            domain={valueKind === "percent" ? [0, 1] : [0, "auto"]}
            tickFormatter={(v: number) => formatValue(v, valueKind)}
            {...axisProps}
          />
          <YAxis
            type="category"
            dataKey={labelKey}
            width={Math.min(narrow ? 104 : 170, 12 + longest * 6.2)}
            {...axisProps}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            interval={0}
          />
          <Tooltip cursor={{ fill: "rgba(28,58,94,0.06)" }} content={<TooltipBox kind={valueKind} />} />
          {series.length > 1 && <Legend iconType="rect" wrapperStyle={{ fontSize: 12, color: INK_MUTED }} />}
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} barSize={barSize} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {colorFor && rows.map((row, i) => <Cell key={i} fill={colorFor(row)} />)}
              {series.length === 1 && (
                <LabelList dataKey={s.key} position="right" formatter={(v: unknown) => formatValue(Number(v), valueKind)} style={{ fill: INK_MUTED, fontSize: 11 }} />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Columns over an ordered axis (days, duration buckets). */
export function Columns<T extends Row>({
  rows,
  xKey,
  yKey,
  name,
  height = 220,
  xTickFormatter,
  references = [],
}: {
  rows: T[];
  xKey: string;
  yKey: string;
  name: string;
  height?: number;
  xTickFormatter?: (value: string) => string;
  references?: Array<{ x: string; label: string }>;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows as Row[]} margin={{ top: 16, right: 8, bottom: 4, left: -16 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey={xKey} {...axisProps} tickFormatter={xTickFormatter} minTickGap={16} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} />
          <Tooltip
            cursor={{ fill: "rgba(28,58,94,0.06)" }}
            content={<TooltipBox />}
            labelFormatter={(v) => (xTickFormatter ? xTickFormatter(String(v)) : String(v))}
          />
          {references.map((r) => (
            <ReferenceLine key={r.label} x={r.x} stroke={AXIS} label={{ value: r.label, position: "top", fill: INK_MUTED, fontSize: 10 }} />
          ))}
          <Bar dataKey={yKey} name={name} fill={SERIES_1} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** A labelled progress meter against a target. */
export function Meter({ label, value, target, note }: { label: string; value: number; target: number; note?: string }) {
  const share = target ? Math.min(value / target, 1) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>{label}</span>
        <span className="tabular-nums">
          <span className="font-semibold">{formatValue(value)}</span>
          <span className="text-text-muted"> / {formatValue(target)}</span>
        </span>
      </div>
      <div
        className="h-2 rounded-full bg-[#cde2fb]"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={target}
        aria-valuenow={value}
      >
        <div className="h-2 rounded-full" style={{ width: `${share * 100}%`, background: SERIES_1 }} />
      </div>
      {note && <p className="text-xs text-text-muted">{note}</p>}
    </div>
  );
}
