import { NextResponse } from "next/server";
import { desc, eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";
import { uid } from "@/lib/utils";

export const runtime = "nodejs";

const sig = (layout: number[][]) => layout.map(([s, f]) => `${s}/${f}`).join(" ");

export async function GET(req: Request) {
  const page = new URL(req.url).searchParams.get("page");
  const d = await db();
  const q = d.select().from(schema.fingeringFavorites);
  const rows = page ? await q.where(eq(schema.fingeringFavorites.page, page)).orderBy(desc(schema.fingeringFavorites.createdAt)) : await q.orderBy(desc(schema.fingeringFavorites.createdAt));
  return NextResponse.json({ favorites: rows });
}

// Adds the favourite unless the same layout is already saved for the same
// page, key, pair and exercise -> { favorite, added }.
export async function POST(req: Request) {
  const b = await req.json().catch(() => null);
  const okPair = b && b.pair && Array.isArray(b.pair.roots) && Array.isArray(b.pair.qualities);
  if (!okPair || typeof b.key !== "string" || !Array.isArray(b.layout) || !Array.isArray(b.line) || b.layout.length !== b.line.length || !b.layout.length) return NextResponse.json({ error: "key, pair, layout[] and line[] (same length) required" }, { status: 400 });
  const row = {
    id: uid(),
    page: typeof b.page === "string" && b.page ? b.page : "triad_pairs",
    title: String(b.title ?? ""),
    exercise: String(b.exercise ?? ""),
    params: (b.params && typeof b.params === "object" ? b.params : {}) as Record<string, unknown>,
    key: b.key as string,
    position: b.position == null || b.position === "" ? null : String(b.position),
    pair: { roots: (b.pair.roots as unknown[]).map(String), qualities: (b.pair.qualities as unknown[]).map(String) },
    start: String(b.start ?? ""),
    layout: (b.layout as unknown[][]).map((x) => [Number(x[0]), Number(x[1])]),
    line: b.line as schema.FavoriteNote[],
    cost: b.cost == null ? null : Number(b.cost),
    createdAt: new Date().toISOString(),
  };
  const d = await db();
  const existing = await d.select().from(schema.fingeringFavorites).where(eq(schema.fingeringFavorites.page, row.page));
  const dup = existing.find((f) => f.key === row.key && f.exercise === row.exercise && JSON.stringify(f.pair) === JSON.stringify(row.pair) && sig(f.layout) === sig(row.layout));
  if (dup) return NextResponse.json({ favorite: dup, added: false });
  await d.insert(schema.fingeringFavorites).values(row);
  return NextResponse.json({ favorite: row, added: true });
}
