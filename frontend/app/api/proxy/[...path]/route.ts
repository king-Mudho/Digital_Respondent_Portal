import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL } from "@/config/env";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";

/**
 * Authenticated proxy for internal Research Operations Centre calls.
 * Reads the httpOnly JWT cookie server-side and attaches it as a Bearer
 * token -- client code never sees or handles the token itself
 * (docs/07_FRONTEND_ARCHITECTURE.md "app/api/ ... auth cookie relay only").
 * On a 401, attempts one refresh via the refresh cookie before giving up.
 */
async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
  });
  if (!response.ok) return null;
  const { access } = await response.json();
  return access;
}

async function proxy(request: NextRequest, path: string[]) {
  const targetUrl = `${API_BASE_URL}/${path.join("/")}/${request.nextUrl.search}`;
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();

  const doFetch = (token?: string) =>
    fetch(targetUrl, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body,
    });

  let upstream = await doFetch(accessToken);
  let refreshedAccessToken: string | null = null;

  if (upstream.status === 401 && refreshToken) {
    refreshedAccessToken = await refreshAccessToken(refreshToken);
    if (refreshedAccessToken) {
      upstream = await doFetch(refreshedAccessToken);
    }
  }

  // Streamed through untouched: binary-safe (.text() re-encoded bodies as
  // UTF-8 and corrupted every PDF), and a long export -- a ZIP of hundreds of
  // PDFs -- starts arriving at once instead of waiting past nginx's timeout.
  const responseBody = upstream.body;
  const headers: Record<string, string> = {
    "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
  };
  // CSV export downloads rely on this to name/save the file correctly.
  const disposition = upstream.headers.get("Content-Disposition");
  if (disposition) headers["Content-Disposition"] = disposition;
  const cacheControl = upstream.headers.get("Cache-Control");
  if (cacheControl) headers["Cache-Control"] = cacheControl;

  const response = new NextResponse(responseBody, { status: upstream.status, headers });

  if (refreshedAccessToken) {
    const isProd = process.env.NEXT_PUBLIC_APP_ENV === "production";
    response.cookies.set(ACCESS_COOKIE, refreshedAccessToken, {
      httpOnly: true,
      secure: isProd,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 30,
    });
  }

  return response;
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
