"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AdminUserProvider, canOpenPath, useAdminSession } from "@/lib/auth/session";
import { AdminNav } from "./AdminNav";

/**
 * backHref/backLabel render a consistent "<- Back to X" link above every
 * page's content, pointing at that page's logical parent (a detail page
 * back to its list, a sub-dashboard back to the Executive Dashboard, any
 * top-level screen back to the Dashboard) -- centralised here rather than
 * duplicated per page so every admin screen gets one without repeating the
 * markup. Omit both on the Executive Dashboard itself (there's no parent
 * to go back to) and on /admin/login (pre-auth).
 *
 * Also the role gate for the whole Research Operations Centre: the nav
 * shows only the screens this role may open, and a screen it may not open
 * renders an explicit "no access" card instead of a page whose every fetch
 * 403s. Server-side permission classes remain the real boundary.
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
  const { user, loading } = useAdminSession();
  const pathname = usePathname();

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-text-muted">Checking session…</p>
      </main>
    );
  }

  // useAdminSession has already redirected to /admin/login.
  if (!user) return null;

  const allowed = canOpenPath(user, pathname ?? "");

  // A page's declared parent isn't always one this role may open -- the
  // KII/Document dashboard points back to the Executive Dashboard, which
  // KII and Documentary RAs are refused. Fall back to this role's own start
  // screen rather than offering a link into a "no access" card, and drop
  // the link entirely when that start screen is the page we're already on
  // (a Contact RA's start screen *is* the Main-400 Register).
  let effectiveBackHref = backHref;
  let effectiveBackLabel = backLabel ?? "Dashboard";
  if (backHref && !canOpenPath(user, backHref)) {
    const landing = user.screens.find((s) => s.path === user.landing_path);
    effectiveBackHref = landing ? landing.path : undefined;
    effectiveBackLabel = landing ? landing.label : effectiveBackLabel;
  }
  if (effectiveBackHref === pathname) effectiveBackHref = undefined;

  return (
    <AdminUserProvider value={user}>
      <div className="min-h-screen flex flex-col">
        <AdminNav />
        <main className="flex-1 px-6 py-6">
          {allowed ? (
            <>
              {effectiveBackHref && (
                <Link
                  href={effectiveBackHref}
                  className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4"
                >
                  ← Back to {effectiveBackLabel}
                </Link>
              )}
              {children}
            </>
          ) : (
            <NoAccess landingPath={user.landing_path} roleLabel={user.role_label} />
          )}
        </main>
      </div>
    </AdminUserProvider>
  );
}

function NoAccess({ landingPath, roleLabel }: { landingPath: string; roleLabel: string }) {
  return (
    <div className="max-w-md rounded-md border border-border bg-surface p-5 space-y-3">
      <h2 className="font-semibold">This screen isn&apos;t part of your role</h2>
      <p className="text-text-muted text-sm">
        Your account is set up as <b>{roleLabel || "an internal user"}</b>, which doesn&apos;t include this screen.
        The links in the bar above are the screens you can use. If you think you should have access to this one,
        ask the PI to change your role.
      </p>
      <Link href={landingPath} className="inline-block text-header underline text-sm">
        Go to my start screen
      </Link>
    </div>
  );
}
