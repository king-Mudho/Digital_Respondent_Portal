import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE } from "@/lib/auth/cookies";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split(".");
    const json = Buffer.from(payload, "base64url").toString("utf-8");
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** Lets client components check session state without ever reading the
 * httpOnly cookie themselves. */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ authenticated: false });
  }
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === "number" ? payload.exp : 0;
  if (exp * 1000 < Date.now()) {
    return NextResponse.json({ authenticated: false });
  }
  return NextResponse.json({ authenticated: true, userId: payload?.user_id ?? null });
}
