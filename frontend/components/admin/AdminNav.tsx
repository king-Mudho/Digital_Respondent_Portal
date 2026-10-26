"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api/admin";
import { type AdminScreen, type AdminUser, useAdminUser } from "@/lib/auth/session";
import { cn } from "@/lib/utils/cn";

/**
 * Renders exactly the screens the signed-in role may open, as served by
 * GET /api/v1/auth/me/ (backend api/navigation.py). Nothing is hardcoded
 * here: previously this file held a static list of all 14 links shown to
 * every role, so a Contact RA saw "Audit Log" and "Export" and got a 403
 * on click.
 *
 * A left sidebar grouped by the server's `group` (2026-10-26): the single
 * top row had grown to 22 links and scrolled sideways. On a phone it is a
 * drawer behind a "Menu" button. So the PI's 22 screens fit without
 * scrolling, only the group holding the current page is open until another
 * is opened; a role with a handful of screens sees them all. Which groups
 * were opened is a per-browser convenience only.
 */
const EXPANDED_KEY = "drp.nav.expanded";
const SHOW_ALL_UP_TO = 8;

function groupScreens(screens: AdminScreen[]) {
  const groups = new Map<string, { label: string; order: number; screens: AdminScreen[] }>();
  for (const s of screens) {
    const label = s.group ?? "Screens";
    if (!groups.has(label)) groups.set(label, { label, order: s.group_order ?? 99, screens: [] });
    groups.get(label)!.screens.push(s);
  }
  return [...groups.values()]
    .sort((a, b) => a.order - b.order)
    .map((g) => ({ ...g, screens: g.screens.sort((a, b) => (a.order_in_group ?? 0) - (b.order_in_group ?? 0)) }));
}

/** The screen a path belongs to: itself, the parent of a detail page, or the longest screen path it sits under. */
function activeScreenId(user: AdminUser, pathname: string): string | undefined {
  const exact = user.screens.find((s) => s.path === pathname);
  if (exact) return exact.id;
  for (const [prefix, parentId] of Object.entries(user.child_paths ?? {})) {
    if (pathname.startsWith(prefix)) return parentId;
  }
  return [...user.screens]
    .filter((s) => pathname.startsWith(s.path.replace(/\/$/, "") + "/"))
    .sort((a, b) => b.path.length - a.path.length)[0]?.id;
}

export function AdminNav() {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const user = useAdminUser();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([]);

  useEffect(() => {
    try {
      setExpanded(JSON.parse(localStorage.getItem(EXPANDED_KEY) ?? "[]"));
    } catch {
      /* storage unavailable: only the current page's group opens */
    }
  }, []);
  useEffect(() => setOpen(false), [pathname]);

  if (!user) return null;
  const groups = groupScreens(user.screens);
  const active = activeScreenId(user, pathname);
  const activeGroup = user.screens.find((s) => s.id === active)?.group;

  const showAll = user.screens.length <= SHOW_ALL_UP_TO;
  const toggle = (label: string) => {
    const next = expanded.includes(label) ? expanded.filter((g) => g !== label) : [...expanded, label];
    setExpanded(next);
    try {
      localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));
    } catch {
      /* not remembered; fine */
    }
  };

  const signOut = async () => {
    await logout();
    router.replace("/admin/login");
  };

  const identity = (
    <div>
      <p className="font-semibold leading-tight">ABF-FST Research Operations Centre</p>
      <p className="text-xs text-white/70 mt-0.5">
        {user.username} · {user.role_label}
        {user.read_only && " · read-only"}
      </p>
    </div>
  );

  return (
    <>
      {/* Phone / narrow screens: a slim bar with a menu button. */}
      <header className="lg:hidden sticky top-0 z-30 bg-header text-white px-4 py-3 flex items-center justify-between gap-3">
        {identity}
        <button
          onClick={() => setOpen(true)}
          aria-expanded={open}
          aria-controls="admin-sidebar"
          className="shrink-0 rounded border border-white/30 px-3 py-1.5 text-sm hover:bg-white/10"
        >
          Menu
        </button>
      </header>
      {open && <div className="lg:hidden fixed inset-0 z-40 bg-black/40" onClick={() => setOpen(false)} aria-hidden />}

      <aside
        id="admin-sidebar"
        className={cn(
          "bg-header text-white flex flex-col w-64 shrink-0",
          "fixed inset-y-0 left-0 z-50 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="px-4 pt-4 pb-3 border-b border-white/10 flex items-start justify-between gap-2">
          {identity}
          <button onClick={() => setOpen(false)} className="lg:hidden text-white/70 hover:text-white text-sm" aria-label="Close menu">
            Close
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-2 text-sm" aria-label="Screens">
          {groups.map((g) => {
            const pinned = showAll || g.label === activeGroup;
            const isCollapsed = !pinned && !expanded.includes(g.label);
            return (
              <div key={g.label}>
                {pinned ? (
                  <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-white/55">{g.label}</p>
                ) : (
                  <button
                    onClick={() => toggle(g.label)}
                    aria-expanded={!isCollapsed}
                    className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-white/55 hover:text-white/80"
                  >
                    <span>
                      {g.label}
                      {isCollapsed && <span className="ml-1.5 normal-case tracking-normal font-normal">({g.screens.length})</span>}
                    </span>
                    <span aria-hidden className={cn("transition-transform", isCollapsed && "-rotate-90")}>▾</span>
                  </button>
                )}
                {!isCollapsed && (
                  <ul className="mt-0.5 space-y-px">
                    {g.screens.map((screen) => (
                      <li key={screen.id}>
                        <Link
                          href={screen.path}
                          aria-current={screen.id === active ? "page" : undefined}
                          className={cn(
                            "block rounded px-2 py-1 border-l-2 border-transparent text-white/85 hover:bg-white/10 hover:text-white",
                            screen.id === active && "bg-white/15 border-accent text-white font-medium",
                          )}
                        >
                          {screen.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-4 py-3 flex items-center justify-between text-sm">
          <Link href="/admin/account" className="text-white/80 hover:text-white">
            Change password
          </Link>
          <button onClick={signOut} className="text-white/80 hover:text-white">
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
