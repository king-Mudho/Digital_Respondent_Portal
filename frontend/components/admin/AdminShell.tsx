"use client";

import Link from "next/link";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AdminNav } from "./AdminNav";

/**
 * backHref/backLabel render a consistent "<- Back to X" link above every
 * page's content, pointing at that page's logical parent (a detail page
 * back to its list, a sub-dashboard back to the Executive Dashboard, any
 * top-level screen back to the Dashboard) -- centralised here rather than
 * duplicated per page so every admin screen gets one without repeating the
 * markup. Omit both on the Executive Dashboard itself (there's no parent
 * to go back to) and on /admin/login (pre-auth).
 */
export function AdminShell({
  children,
  backHref,
  backLabel,
}: {
  children: React.ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  const authChecked = useRequireAuth();

  if (!authChecked) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-text-muted">Checking session…</p>
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AdminNav />
      <main className="flex-1 px-6 py-6">
        {backHref && (
          <Link
            href={backHref}
            className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4"
          >
            ← Back to {backLabel ?? "Dashboard"}
          </Link>
        )}
        {children}
      </main>
    </div>
  );
}
