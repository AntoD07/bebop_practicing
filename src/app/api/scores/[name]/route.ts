import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ name: string }> }) {
  const { name } = await ctx.params;
  const d = await db();
  const rows = await d.select().from(schema.scores).where(eq(schema.scores.name, decodeURIComponent(name)));
  if (!rows[0]) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ score: rows[0] });
}

export async function PUT(req: Request, ctx: { params: Promise<{ name: string }> }) {
  const { name } = await ctx.params;
  const b = await req.json().catch(() => ({}));
  const d = await db();
  const key = decodeURIComponent(name);
  const rows = await d.select({ name: schema.scores.name }).from(schema.scores).where(eq(schema.scores.name, key));
  if (!rows[0]) return NextResponse.json({ error: "save the MusicXML first" }, { status: 404 });
  await d.update(schema.scores).set({ bestFingering: b.best_fingering ?? null }).where(eq(schema.scores.name, key));
  return NextResponse.json({ ok: true });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ name: string }> }) {
  const { name } = await ctx.params;
  const d = await db();
  await d.delete(schema.scores).where(eq(schema.scores.name, decodeURIComponent(name)));
  return NextResponse.json({ ok: true });
}
