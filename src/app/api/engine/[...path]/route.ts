// The only path from the browser to the Python function: adds the API key,
// checks the shared engine_cache (Turso) before calling Python, stores the
// response, and forwards everything else transparently. Up to 300 s.
import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";
import { canonicalJson, sha256 } from "@/lib/engine/hash";

export const runtime = "nodejs";
export const maxDuration = 300;
export const dynamic = "force-dynamic";

const NO_CACHE = new Set(["health", "score/read-vision", "constants"]);
const ENGINE_VERSION_TTL_MS = 10 * 60 * 1000;

function engineUrl(): string {
  const u = process.env.ENGINE_URL?.replace(/\/+$/, "");
  if (u) return u;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://127.0.0.1:8000";
}

function apiHeaders(): Record<string, string> {
  const h: Record<string, string> = { accept: "application/json" };
  const k = process.env.ENGINE_API_KEY;
  if (k) h["X-API-Key"] = k;
  return h;
}

const g = globalThis as unknown as { __engineVersion?: { v: string; at: number } };

async function engineVersion(): Promise<string | null> {
  const now = Date.now();
  if (g.__engineVersion && now - g.__engineVersion.at < ENGINE_VERSION_TTL_MS) return g.__engineVersion.v;
  try {
    const r = await fetch(`${engineUrl()}/api/py/health`, { headers: apiHeaders(), cache: "no-store" });
    if (!r.ok) return null;
    const j = (await r.json()) as { engine_version?: string };
    if (!j.engine_version) return null;
    g.__engineVersion = { v: j.engine_version, at: now };
    return j.engine_version;
  } catch {
    return null;
  }
}

function cacheable(path: string, body: unknown): boolean {
  if (NO_CACHE.has(path)) return false;
  if (path === "lines/sample") {
    const b = body as { seed?: unknown } | null;
    return !!b && b.seed !== undefined && b.seed !== null;
  }
  return true;
}

async function forward(method: "GET" | "POST", path: string, search: string, body: string | null) {
  const url = `${engineUrl()}/api/py/${path}${search}`;
  const r = await fetch(url, {
    method,
    headers: { ...apiHeaders(), ...(body ? { "content-type": "application/json" } : {}) },
    body: body ?? undefined,
    cache: "no-store",
    signal: AbortSignal.timeout(295_000),
  });
  const text = await r.text();
  return { status: r.status, text, etag: r.headers.get("etag") };
}

async function handle(req: Request, ctx: { params: Promise<{ path: string[] }> }, method: "GET" | "POST") {
  const { path: parts } = await ctx.params;
  const path = parts.join("/");
  const search = new URL(req.url).search;
  const bodyText = method === "POST" ? await req.text() : null;
  let bodyJson: unknown = null;
  if (bodyText) {
    try {
      bodyJson = JSON.parse(bodyText);
    } catch {
      return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
    }
  }
  const useCache = cacheable(path, bodyJson) && process.env.ENGINE_CACHE !== "off";
  let hash: string | null = null;
  let version: string | null = null;
  if (useCache) {
    version = await engineVersion();
    if (version) {
      hash = await sha256(`${version}|${method}|${path}${search}|${canonicalJson(bodyJson)}`);
      try {
        const d = await db();
        const rows = await d.select().from(schema.engineCache).where(eq(schema.engineCache.hash, hash));
        if (rows[0] && rows[0].engineVersion === version) {
          return new NextResponse(rows[0].body, {
            status: 200,
            headers: { "content-type": "application/json", "x-engine-cache": "hit", etag: `"${version.slice(0, 12)}-${hash.slice(0, 20)}"` },
          });
        }
      } catch (e) {
        console.warn("engine_cache lookup failed", e);
      }
    }
  }
  let res: { status: number; text: string; etag: string | null };
  try {
    res = await forward(method, path, search, bodyText);
  } catch (e) {
    return NextResponse.json({ error: `engine unreachable: ${(e as Error).message}` }, { status: 502 });
  }
  if (res.status === 200 && hash && version) {
    try {
      const d = await db();
      await d
        .insert(schema.engineCache)
        .values({ hash, engineVersion: version, body: res.text, createdAt: new Date().toISOString() })
        .onConflictDoUpdate({ target: schema.engineCache.hash, set: { engineVersion: version, body: res.text, createdAt: new Date().toISOString() } });
    } catch (e) {
      console.warn("engine_cache store failed", e);
    }
  }
  return new NextResponse(res.text, {
    status: res.status,
    headers: { "content-type": "application/json", "x-engine-cache": hash ? "miss" : "bypass", ...(res.etag ? { etag: res.etag } : {}) },
  });
}

export async function GET(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, ctx, "GET");
}

export async function POST(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, ctx, "POST");
}
