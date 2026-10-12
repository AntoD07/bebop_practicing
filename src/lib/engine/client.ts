// Browser-side client of the engine proxy (/api/engine/*) with an IndexedDB
// response cache keyed by sha256(engineVersion + canonical request).
import { get as idbGet, set as idbSet } from "idb-keyval";
import { canonicalJson, sha256 } from "./hash";

export class EngineError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

let engineVersion: string | null = null;
let versionPromise: Promise<string | null> | null = null;

export async function getEngineVersion(): Promise<string | null> {
  if (engineVersion) return engineVersion;
  if (!versionPromise) {
    versionPromise = fetch("/api/engine/health", { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) return null;
        const j = (await r.json()) as { engine_version?: string };
        engineVersion = j.engine_version ?? null;
        return engineVersion;
      })
      .catch(() => null)
      .finally(() => {
        versionPromise = null;
      });
  }
  return versionPromise;
}

const NO_CACHE = new Set(["health", "score/read-vision", "constants"]);

function errorMessage(status: number, body: unknown): string {
  if (body && typeof body === "object") {
    const b = body as { detail?: unknown; error?: unknown };
    if (typeof b.detail === "string") return b.detail;
    if (Array.isArray(b.detail)) return b.detail.map((d) => (d as { msg?: string }).msg ?? JSON.stringify(d)).join("; ");
    if (typeof b.error === "string") return b.error;
  }
  return `engine request failed (${status})`;
}

export type EngineOptions = { signal?: AbortSignal; cache?: boolean };

export async function engineGet<T>(path: string, params?: Record<string, string | number | boolean | null | undefined>, opts: EngineOptions = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== null) qs.set(k, String(v));
  const search = qs.toString() ? `?${qs}` : "";
  return engineRequest<T>("GET", path + search, null, opts);
}

export async function enginePost<T>(path: string, body: unknown, opts: EngineOptions = {}): Promise<T> {
  return engineRequest<T>("POST", path, body, opts);
}

async function engineRequest<T>(method: "GET" | "POST", pathWithSearch: string, body: unknown, opts: EngineOptions): Promise<T> {
  const base = pathWithSearch.split("?")[0];
  const cacheable = opts.cache !== false && !NO_CACHE.has(base) && !(base === "lines/sample" && (body as { seed?: unknown } | null)?.seed == null);
  let key: string | null = null;
  if (cacheable && typeof indexedDB !== "undefined") {
    const v = await getEngineVersion();
    if (v) {
      key = "engine:" + (await sha256(`${v}|${method}|${pathWithSearch}|${canonicalJson(body)}`));
      try {
        const hit = await idbGet<T>(key);
        if (hit) return hit;
      } catch {
        /* IDB unavailable (private mode) */
      }
    }
  }
  const r = await fetch(`/api/engine/${pathWithSearch}`, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });
  if (r.status === 401) {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- full reload clears client state after the session expired
    if (typeof window !== "undefined") window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    throw new EngineError(401, "signed out", null);
  }
  let json: unknown = null;
  try {
    json = await r.json();
  } catch {
    json = null;
  }
  if (!r.ok) throw new EngineError(r.status, errorMessage(r.status, json), json);
  if (key) {
    try {
      await idbSet(key, json);
    } catch {
      /* ignore */
    }
  }
  return json as T;
}
