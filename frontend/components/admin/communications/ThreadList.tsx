"use client";

import { PAGE_SIZE_OPTIONS } from "@/components/admin/Pagination";
import { shortTime, threadKey, type Channel, type Kind, type ThreadPage } from "@/lib/api/communications";
import { ChannelBadge, StatusTicks } from "./Marks";

export type Show = "all" | "waiting" | "failed";

export interface ListFilters {
  show: Show;
  register: "" | Kind;
  channel: "" | Channel;
  q: string;
  page: number;
  pageSize: number;
}

/** Page numbers to show around the current one: 1 … 4 5 6 … 12. */
function pageWindow(current: number, total: number): (number | null)[] {
  const wanted = new Set([1, total, current - 1, current, current + 1].filter((p) => p >= 1 && p <= total));
  const sorted = [...wanted].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(null);
    out.push(p);
  });
  return out;
}

const SHOW_LABEL: Record<Show, string> = { waiting: "Waiting", failed: "Not delivered", all: "All" };

export function ThreadList({
  data,
  loading,
  filters,
  onFilters,
  selected,
  onSelect,
  showUnknown,
  unknownSelected,
  onSelectUnknown,
}: {
  data: ThreadPage | undefined;
  loading: boolean;
  filters: ListFilters;
  onFilters: (next: Partial<ListFilters>) => void;
  selected: string | null;
  onSelect: (key: string) => void;
  showUnknown: boolean;
  unknownSelected: boolean;
  onSelectUnknown: () => void;
}) {
  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-border p-3">
        <div className="flex gap-1" role="tablist" aria-label="Show">
          {(["waiting", "failed", "all"] as Show[]).map((key) => (
            <button
              key={key}
              role="tab"
              aria-selected={filters.show === key}
              onClick={() => onFilters({ show: key, page: 1 })}
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium ${filters.show === key ? "bg-header text-white" : "text-text-muted hover:bg-bg"}`}
            >
              {SHOW_LABEL[key]}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={filters.q}
          onChange={(e) => onFilters({ q: e.target.value, page: 1 })}
          placeholder="Search organisation, person or ID"
          aria-label="Search conversations"
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
        />
        <div className="flex gap-2">
          <select
            aria-label="Register"
            value={filters.register}
            onChange={(e) => onFilters({ register: e.target.value as ListFilters["register"], page: 1 })}
            className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">Main-400 and KII</option>
            <option value="main">Main-400 only</option>
            <option value="kii">KII only</option>
          </select>
          <select
            aria-label="Channel"
            value={filters.channel}
            onChange={(e) => onFilters({ channel: e.target.value as ListFilters["channel"], page: 1 })}
            className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">Every channel</option>
            <option value="WHATSAPP">WhatsApp</option>
            <option value="SMS">SMS</option>
            <option value="EMAIL">Email</option>
          </select>
        </div>
      </div>

      <ul className="min-h-0 flex-1 overflow-y-auto" aria-label="Conversations">
        {showUnknown && (
          <li>
            <button
              type="button"
              onClick={onSelectUnknown}
              className={`w-full border-b border-border px-3 py-3 text-left hover:bg-bg ${unknownSelected ? "bg-bg" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">Numbers not on any record</span>
                {(data?.unknown_waiting ?? 0) > 0 && (
                  <span className="rounded-full bg-danger px-2 py-px text-[11px] font-semibold text-white">{data?.unknown_waiting}</span>
                )}
              </div>
              <p className="text-xs text-text-muted">WhatsApp messages from people the study has no record of</p>
            </button>
          </li>
        )}
        {loading && !data && <li className="p-4 text-sm text-text-muted">Loading conversations…</li>}
        {data && data.results.length === 0 && (
          <li className="p-4 text-sm text-text-muted">
            {filters.show === "waiting"
              ? "Nobody is waiting for an answer."
              : filters.show === "failed"
                ? "No conversation's last message failed to arrive."
                : "No conversations match."}
          </li>
        )}
        {data?.results.map((row) => {
          const key = threadKey(row.kind, row.id);
          const active = key === selected;
          return (
            <li key={key}>
              <button
                type="button"
                onClick={() => onSelect(key)}
                aria-current={active ? "true" : undefined}
                className={`relative w-full border-b border-border px-3 py-3 text-left hover:bg-bg ${active ? "bg-bg" : ""}`}
              >
                {active && <span className="absolute inset-y-0 left-0 w-0.5 bg-header" aria-hidden />}
                <div className="flex items-baseline justify-between gap-2">
                  <span className={`truncate text-sm ${row.waiting ? "font-semibold" : "font-medium"}`}>{row.organisation}</span>
                  <span className={`shrink-0 text-[11px] tabular-nums ${row.waiting ? "font-semibold text-header" : "text-text-muted"}`}>
                    {shortTime(row.last_activity)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
                  <span className="font-mono">{row.ref}</span>
                  {row.person && <span className="truncate">· {row.person}</span>}
                </div>
                <div className="mt-1 flex items-center gap-1.5">
                  {row.last_message.direction === "out" && <StatusTicks status={row.last_sent_status} className="shrink-0" />}
                  <p className="min-w-0 flex-1 truncate text-xs text-text-muted">
                    {row.last_message.direction === "in" && <span className="text-text">They wrote: </span>}
                    {row.last_message.text || "Invitation activity only"}
                  </p>
                  {row.waiting && <span className="h-2 w-2 shrink-0 rounded-full bg-header" aria-label="Waiting for an answer" />}
                </div>
                {row.channels.length > 0 && (
                  <div className="mt-1.5 flex gap-1">
                    {row.channels.map((c) => <ChannelBadge key={c} channel={c} />)}
                  </div>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      {data && data.count > 0 && (
        <nav aria-label="Pages" className="space-y-1.5 border-t border-border px-3 py-2 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-text-muted tabular-nums" role="status">
              {(filters.page - 1) * data.page_size + 1}–{Math.min(filters.page * data.page_size, data.count)} of {data.count}
            </span>
            <label className="flex items-center gap-1.5 text-text-muted">
              Show
              <select
                aria-label="Conversations per page"
                value={data.page_size}
                onChange={(e) => onFilters({ pageSize: Number(e.target.value), page: 1 })}
                className="rounded-md border border-border bg-surface px-1.5 py-1 text-xs text-text"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
              per page
            </label>
          </div>
          {pages > 1 && (
            <div className="flex flex-wrap items-center justify-center gap-0.5">
              <button type="button" aria-label="Newer page" disabled={filters.page <= 1} onClick={() => onFilters({ page: filters.page - 1 })} className="min-h-8 rounded px-2 hover:bg-bg disabled:opacity-40">
                ← Newer
              </button>
              {pageWindow(filters.page, pages).map((p, i) =>
                p === null ? (
                  <span key={`gap-${i}`} className="px-1 text-text-muted" aria-hidden="true">…</span>
                ) : (
                  <button
                    key={p}
                    type="button"
                    aria-label={`Page ${p}`}
                    aria-current={p === filters.page ? "page" : undefined}
                    onClick={() => onFilters({ page: p })}
                    className={`min-h-8 min-w-8 rounded px-1.5 tabular-nums ${p === filters.page ? "bg-header font-medium text-white" : "hover:bg-bg"}`}
                  >
                    {p}
                  </button>
                ),
              )}
              <button type="button" aria-label="Older page" disabled={filters.page >= pages} onClick={() => onFilters({ page: filters.page + 1 })} className="min-h-8 rounded px-2 hover:bg-bg disabled:opacity-40">
                Older →
              </button>
            </div>
          )}
        </nav>
      )}
    </div>
  );
}
