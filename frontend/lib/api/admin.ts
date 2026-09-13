import { ApiError } from "./client";

/**
 * Typed fetch client for internal Research Operations Centre endpoints.
 * Always calls the same-origin /api/proxy relay (never the Django API
 * directly) so the httpOnly JWT cookie is attached server-side -- see
 * app/api/proxy/[...path]/route.ts.
 */
export async function adminFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "unknown_error",
      error?.message ?? response.statusText,
      error?.field_errors ?? {},
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    // The route distinguishes bad credentials from a throttled or
    // unavailable backend -- pass its message through rather than
    // relabelling everything as a password problem.
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? "invalid_credentials",
      body?.error?.message ?? "Invalid username or password.",
    );
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

// Session identity now comes from the Django endpoint GET /auth/me/ via
// lib/auth/session.tsx -- it returns the role, the screens that role may
// open and its landing path, all of which a cookie-presence check cannot.
