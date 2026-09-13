"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch } from "@/lib/api/admin";

export interface AdminScreen {
  id: string;
  path: string;
  label: string;
}

export interface AdminUser {
  username: string;
  role: string | null;
  role_label: string;
  screens: AdminScreen[];
  landing_path: string;
  read_only: boolean;
  universal_paths: string[];
  child_paths: Record<string, string>;
}

/**
 * Who is signed in and which screens they may open, from
 * GET /api/v1/auth/me/ (backend api/navigation.py is the single source of
 * truth). The nav renders exactly `screens`; AdminShell refuses to render
 * a screen that isn't in it. Both are UX only -- every endpoint still
 * enforces its own permission class server-side.
 */
const AdminUserContext = createContext<AdminUser | null>(null);

export function useAdminUser(): AdminUser | null {
  return useContext(AdminUserContext);
}

export const AdminUserProvider = AdminUserContext.Provider;

export function useAdminSession() {
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    adminFetch<AdminUser>("/auth/me/")
      .then((data) => {
        if (cancelled) return;
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoading(false);
        router.replace("/admin/login");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { user, loading };
}

/**
 * Whether this user may open an admin path. Mirrors
 * api.navigation.can_open_path, but entirely from data the server sent --
 * no screen list or path rule is hardcoded here.
 */
export function canOpenPath(user: AdminUser | null, path: string): boolean {
  if (!user) return false;

  const universal = user.universal_paths ?? [];
  if (universal.some((p) => path === p || path.startsWith(p.replace(/\/$/, "") + "/"))) {
    return true;
  }

  const allowedIds = new Set(user.screens.map((s) => s.id));
  for (const [prefix, parentId] of Object.entries(user.child_paths ?? {})) {
    if (path.startsWith(prefix)) return allowedIds.has(parentId);
  }

  return user.screens.some((s) => s.path === path);
}
