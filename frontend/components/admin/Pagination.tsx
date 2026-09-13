"use client";

import { Button } from "@/components/ui/button";

export const PAGE_SIZE = 20; // REST_FRAMEWORK["PAGE_SIZE"] in config/settings/base.py

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Page controls for the register screens. The registers hold 400 Main and
 * 400 Reserve cases, 90 KII records and 100 documents against a page size
 * of 20, and none of these screens had any way to reach page 2 -- every
 * row past the first twenty was simply unreachable in the UI.
 */
export function Pagination({
  page,
  count,
  onPageChange,
  label = "records",
}: {
  page: number;
  count: number;
  onPageChange: (page: number) => void;
  label?: string;
}) {
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  if (count === 0) return null;

  const first = (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, count);

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap pt-3 mt-3 border-t border-border">
      <p className="text-text-muted text-xs tabular-nums">
        Showing {first}–{last} of {count} {label}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <span className="text-xs text-text-muted tabular-nums">
          Page {page} of {totalPages}
        </span>
        <Button variant="outline" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
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
