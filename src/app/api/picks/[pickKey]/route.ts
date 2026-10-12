import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ pickKey: string }> }) {
  const { pickKey } = await ctx.params;
  const key = decodeURIComponent(pickKey);
  const d = await db();
  const rows = await d.select().from(schema.connectionPicks).where(eq(schema.connectionPicks.pickKey, key));
  if (!rows[0]) return NextResponse.json({ exists: false, pickKey: key });
  const r = rows[0];
  return NextResponse.json({ exists: true, pickKey: key, kept: r.kept, deleted_fingerings: r.deletedFingerings, saved: r.savedAt });
}

export async function PUT(req: Request, ctx: { params: Promise<{ pickKey: string }> }) {
  const { pickKey } = await ctx.params;
  const key = decodeURIComponent(pickKey);
  const body = await req.json().catch(() => null);
  if (!body || !Array.isArray(body.kept)) return NextResponse.json({ error: "kept[] required" }, { status: 400 });
  const kept = (body.kept as unknown[]).filter((p) => Array.isArray(p) && p.length === 2).map((p) => (p as unknown[]).map(String));
  const deleted: Record<string, string[]> = {};
  for (const [k, v] of Object.entries((body.deleted_fingerings ?? {}) as Record<string, unknown>)) if (Array.isArray(v) && v.length) deleted[k] = v.map(String);
  const savedAt = typeof body.saved === "string" ? body.saved : new Date().toISOString();
  const d = await db();
  await d
    .insert(schema.connectionPicks)
    .values({ pickKey: key, kept, deletedFingerings: deleted, savedAt })
    .onConflictDoUpdate({ target: schema.connectionPicks.pickKey, set: { kept, deletedFingerings: deleted, savedAt } });
  return NextResponse.json({ exists: true, pickKey: key, kept, deleted_fingerings: deleted, saved: savedAt });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ pickKey: string }> }) {
  const { pickKey } = await ctx.params;
  const key = decodeURIComponent(pickKey);
  const d = await db();
  await d.delete(schema.connectionPicks).where(eq(schema.connectionPicks.pickKey, key));
  return NextResponse.json({ ok: true });
}
