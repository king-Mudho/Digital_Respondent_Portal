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

/**
 * Same relay as adminFetch, for a multipart file upload (e.g. a
 * documentary-evidence source file). No Content-Type header is set here --
 * the browser adds `multipart/form-data; boundary=...` itself, and the
 * proxy route now forwards whatever Content-Type it's given rather than
 * hardcoding application/json.
 */
export async function adminUpload<T>(
  path: string,
  formData: FormData,
  onProgress?: (fraction: number) => void,
): Promise<T> {
  // fetch() can't report how much of a request body has been sent; a big scan
  // over a slow connection looks frozen. XMLHttpRequest can, so use it when
  // the caller wants progress.
  const response = onProgress
    ? await new Promise<{ ok: boolean; status: number; statusText: string; text: string }>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/proxy${path}`);
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) onProgress(event.loaded / event.total);
        };
        xhr.onload = () =>
          resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, statusText: xhr.statusText, text: xhr.responseText });
        xhr.onerror = () => reject(new ApiError(0, "network_error", "The upload was interrupted. Check your connection and try again.", {}));
        xhr.ontimeout = () => reject(new ApiError(0, "timeout", "The upload timed out. Try again on a faster connection.", {}));
        xhr.send(formData);
      })
    : await fetch(`/api/proxy${path}`, { method: "POST", body: formData }).then(async (r) => ({
        ok: r.ok,
        status: r.status,
        statusText: r.statusText,
        text: await r.text(),
      }));

  let parsed: { error?: { code?: string; message?: string; field_errors?: Record<string, string[]> } } | null = null;
  try {
    parsed = JSON.parse(response.text);
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    const error = parsed?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "unknown_error",
      // nginx answers an over-size upload with a bare HTML 413 page, not JSON.
      response.status === 413
        ? "That file is too large to upload."
        : (error?.message ?? response.statusText),
      error?.field_errors ?? {},
    );
  }
  return parsed as T;
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
