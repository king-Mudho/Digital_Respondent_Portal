"use client";

import { canOpenPath, useAdminUser } from "@/lib/auth/session";

/**
 * The three in-page role gates. All of them must be rendered *inside*
 * AdminShell -- the signed-in user is provided as context around
 * AdminShell's children, so a page component's own body cannot see it.
 *
 * These are UX only. The DRF permission classes in api/permissions.py are
 * what actually stop a write; these just stop us showing a role controls
 * that would 403 the moment it touched them.
 */

/**
 * Hides write controls from the two observer roles (Supervisor and
 * Analyst, which the backend reports as `read_only` on /auth/me/). Those
 * roles are granted read access to screens that mix reading and writing
 * -- the cost dashboard also logs cost events, the KII register also
 * creates records -- so without this they saw buttons that always failed.
 */
export function WriteOnly({
  children,
  note = "Your role has read-only access to this screen.",
}: {
  children: React.ReactNode;
  /** Shown in place of the controls. Pass null to render nothing at all. */
  note?: string | null;
}) {
  const user = useAdminUser();

  if (user?.read_only) {
    return note ? <p className="text-text-muted text-sm">{note}</p> : null;
  }
  return <>{children}</>;
}

/**
 * The inverse of WriteOnly: content shown *instead of* an editor to the
 * observer roles, e.g. a memo rendered as plain text where everyone else
 * gets a textarea.
 */
export function ReadOnly({ children }: { children: React.ReactNode }) {
  const user = useAdminUser();
  return user?.read_only ? <>{children}</> : null;
}

/**
 * Renders children only if this role may open `path` -- for cross-links
 * between screens. The Main-400 register linking to Organisations is
 * right for the PI and Field Coordinator but not for a Contact RA, who
 * has the register and not the organisation form.
 */
export function IfScreen({ path, children }: { path: string; children: React.ReactNode }) {
  const user = useAdminUser();
  return canOpenPath(user, path) ? <>{children}</> : null;
}

/** Renders children only for the listed roles (Role values from accounts.models). */
export function IfRole({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const user = useAdminUser();
  return user && user.role && roles.includes(user.role) ? <>{children}</> : null;
}
