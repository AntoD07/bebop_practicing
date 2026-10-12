import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { SESSION_COOKIE, sessionCookieOptions, signSession } from "@/lib/auth";

export const runtime = "nodejs";

function same(a: string, b: string) {
  const ha = createHash("sha256").update(a).digest();
  const hb = createHash("sha256").update(b).digest();
  return timingSafeEqual(ha, hb);
}

export async function POST(req: Request) {
  const expected = process.env.APP_PASSWORD;
  if (!expected) return NextResponse.json({ error: "APP_PASSWORD is not configured" }, { status: 503 });
  let password = "";
  try {
    const body = await req.json();
    password = String(body?.password ?? "");
  } catch {
    /* fall through: empty password */
  }
  if (!password || !same(password, expected)) {
    await new Promise((r) => setTimeout(r, 1000));
    return NextResponse.json({ error: "wrong password" }, { status: 401 });
  }
  const token = await signSession();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  return res;
}
