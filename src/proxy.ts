// Next 16 "proxy" (the file formerly named middleware.ts): the one auth gate.
// Everything but /login, the login API, Next's assets, the manifest/icons and
// the Python function (/api/py, protected by its own API key) needs the session
// cookie. Pages redirect to /login?next=…, API routes get a 401.
import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySession } from "@/lib/auth";

export const config = {
  matcher: [
    "/((?!login|api/auth/login|api/py|_next/static|_next/image|favicon.ico|manifest.webmanifest|icons/|sw.js).*)",
  ],
};

export async function proxy(req: NextRequest) {
  const ok = await verifySession(req.cookies.get(SESSION_COOKIE)?.value);
  if (ok) return NextResponse.next();
  const { pathname, search } = req.nextUrl;
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  url.searchParams.set("next", pathname + search);
  return NextResponse.redirect(url);
}
