"use client";

import { useCallback, useEffect, useState } from "react";

export const PAGE_SIZE = 20; // the default: backend api/pagination.py StandardPagination
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100, 200];
const STORAGE_KEY = "drp.pageSize";

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Page and page size for a register screen. The chosen size is remembered in
 * the browser (a per-person convenience; the screen works without it) so
 * every register opens at the size the person last picked. Changing the size
 * goes back to page 1, since page 3 of 10 is not page 3 of 50.
 */
export function usePaging() {
  const [page, setPage] = useState(1);
  const [pageSize, setSize] = useState(PAGE_SIZE);

  useEffect(() => {
    try {
      const saved = Number(window.localStorage.getItem(STORAGE_KEY));
      if (PAGE_SIZE_OPTIONS.includes(saved)) setSize(saved);
    } catch {
      /* storage blocked: keep the default */
    }
  }, []);

  const setPageSize = useCallback((size: number) => {
    setSize(size);
    setPage(1);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(size));
    } catch {
      /* not remembered, still applied */
    }
  }, []);

  return { page, setPage, pageSize, setPageSize };
}

/** Page numbers to show: the first, the last and a window around the current one, with gaps as null. */
function pageNumbers(page: number, totalPages: number): (number | null)[] {
  const wanted = new Set<number>([1, totalPages]);
  const windowStart = Math.max(1, Math.min(page - 2, totalPages - 4));
  for (let p = windowStart; p <= Math.min(totalPages, windowStart + 4); p++) wanted.add(p);
  const sorted = [...wanted].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(null);
    out.push(p);
  });
  return out;
}

const controlClass =
  "inline-flex items-center justify-center min-w-9 h-9 px-2 rounded-md text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-surface";

/**
 * Page controls for the register screens: "Showing 1 to 20 of 348 results",
 * a Show-per-page choice, first/previous/numbered/next/last. Without
 * onPageSizeChange the size choice is left out.
 */
export function Pagination({
  page,
  count,
  onPageChange,
  pageSize = PAGE_SIZE,
  onPageSizeChange,
  label = "results",
}: {
  page: number;
  count: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  label?: string;
}) {
  if (count === 0) return null;
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const current = Math.min(page, totalPages);
  const first = (current - 1) * pageSize + 1;
  const last = Math.min(current * pageSize, count);
  const go = (p: number) => onPageChange(Math.min(Math.max(1, p), totalPages));

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-4 flex-wrap pt-3 mt-3 border-t border-border"
    >
      <p className="text-text-muted text-sm tabular-nums" role="status">
        Showing {first} to {last} of {count} {label}
      </p>
      <div className="flex items-center gap-4 flex-wrap">
        {onPageSizeChange && (
          <label className="flex items-center gap-2 text-sm text-text-muted">
            Show:
            <select
              aria-label="Rows per page"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text min-h-9"
            >
              {(PAGE_SIZE_OPTIONS.includes(pageSize) ? PAGE_SIZE_OPTIONS : [...PAGE_SIZE_OPTIONS, pageSize].sort((a, b) => a - b)).map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            per page
          </label>
        )}
        <div className="flex items-center gap-1 flex-wrap">
          <button type="button" className={controlClass} aria-label="First page" disabled={current <= 1} onClick={() => go(1)}>
            «
          </button>
          <button type="button" className={controlClass} aria-label="Previous page" disabled={current <= 1} onClick={() => go(current - 1)}>
            ‹
          </button>
          <button type="button" className={`${controlClass} px-3 hidden sm:inline-flex`} disabled={current <= 1} onClick={() => go(current - 1)}>
            Previous
          </button>
          {pageNumbers(current, totalPages).map((p, i) =>
            p === null ? (
              <span key={`gap-${i}`} className="px-1 text-text-muted" aria-hidden="true">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                aria-label={`Page ${p}`}
                aria-current={p === current ? "page" : undefined}
                className={`${controlClass} tabular-nums ${p === current ? "bg-header text-white font-medium" : ""}`}
                onClick={() => go(p)}
              >
                {p}
              </button>
            ),
          )}
          <button type="button" className={`${controlClass} px-3 hidden sm:inline-flex`} disabled={current >= totalPages} onClick={() => go(current + 1)}>
            Next
          </button>
          <button type="button" className={controlClass} aria-label="Next page" disabled={current >= totalPages} onClick={() => go(current + 1)}>
            ›
          </button>
          <button type="button" className={controlClass} aria-label="Last page" disabled={current >= totalPages} onClick={() => go(totalPages)}>
            »
          </button>
        </div>
      </div>
    </nav>
  );
}

/** Search box for the register screens, wired to DRF's SearchFilter (?search=). */
export function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="relative">
      <span className="sr-only">Search</span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded-md border border-border px-3 py-2 text-sm w-56 max-w-full"
      />
    </label>
  );
}
