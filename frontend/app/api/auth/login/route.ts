import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL } from "@/config/env";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";

export async function POST(request: NextRequest) {
  const { username, password } = await request.json();

  const upstream = await fetch(`${API_BASE_URL}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!upstream.ok) {
    // Every upstream failure used to be reported as bad credentials, so a
    // throttled or unavailable backend sent people hunting for a password
    // problem that didn't exist.
    if (upstream.status === 429) {
      return NextResponse.json(
        {
          error: {
            code: "too_many_attempts",
            message: "Too many sign-in attempts from this network. Wait a minute and try again.",
          },
        },
        { status: 429 },
      );
    }
    if (upstream.status >= 500) {
      return NextResponse.json(
        { error: { code: "backend_unavailable", message: "The server isn't responding. Try again shortly." } },
        { status: 502 },
      );
    }
    return NextResponse.json({ error: { code: "invalid_credentials", message: "Invalid username or password." } }, { status: 401 });
  }

  const { access, refresh } = await upstream.json();
  const response = NextResponse.json({ ok: true });
  const isProd = process.env.NEXT_PUBLIC_APP_ENV === "production";

  response.cookies.set(ACCESS_COOKIE, access, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 30, // matches JWT_ACCESS_TOKEN_LIFETIME_MINUTES default
  });
  response.cookies.set(REFRESH_COOKIE, refresh, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // matches JWT_REFRESH_TOKEN_LIFETIME_DAYS default
  });
  return response;
}
