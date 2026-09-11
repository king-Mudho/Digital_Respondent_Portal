import { NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(ACCESS_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
  return response;
}
