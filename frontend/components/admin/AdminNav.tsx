"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api/admin";
import { useAdminUser } from "@/lib/auth/session";
import { cn } from "@/lib/utils/cn";

/**
 * Renders exactly the screens the signed-in role may open, as served by
 * GET /api/v1/auth/me/ (backend api/navigation.py). Nothing is hardcoded
 * here: previously this file held a static list of all 14 links shown to
 * every role, so a Contact RA saw "Audit Log" and "Export" and got a 403
 * on click.
 */
export function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAdminUser();
  const screens = user?.screens ?? [];

  return (
    <nav className="bg-header text-white">
      <div className="px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="font-semibold">ABF-FST Research Operations Centre</p>
          {user && (
            <p className="text-xs text-white/70">
              {user.username} · {user.role_label}
              {user.read_only && " · read-only"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          <Link href="/admin/account" className="text-sm text-white/80 hover:text-white">
            Change password
          </Link>
          <button
            onClick={async () => {
              await logout();
              router.replace("/admin/login");
            }}
            className="text-sm text-white/80 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </div>
      {screens.length > 0 && (
        <div className="px-6 flex gap-4 overflow-x-auto border-t border-white/10 text-sm">
          {screens.map((screen) => (
            <Link
              key={screen.id}
              href={screen.path}
              className={cn(
                "py-2 whitespace-nowrap border-b-2 border-transparent",
                pathname === screen.path && "border-accent font-medium",
              )}
            >
              {screen.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
