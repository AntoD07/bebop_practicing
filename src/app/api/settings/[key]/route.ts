import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

const KEY_RE = /^[a-z0-9_.:-]{1,64}$/i;

export async function GET(_req: Request, ctx: { params: Promise<{ key: string }> }) {
  const { key } = await ctx.params;
  if (!KEY_RE.test(key)) return NextResponse.json({ error: "bad key" }, { status: 400 });
  const d = await db();
  const rows = await d.select().from(schema.settings).where(eq(schema.settings.key, key));
  if (!rows[0]) return NextResponse.json({ key, value: null, updatedAt: null });
  return NextResponse.json(rows[0]);
}

export async function PUT(req: Request, ctx: { params: Promise<{ key: string }> }) {
  const { key } = await ctx.params;
  if (!KEY_RE.test(key)) return NextResponse.json({ error: "bad key" }, { status: 400 });
  const body = await req.json().catch(() => null);
  if (!body || !("value" in body)) return NextResponse.json({ error: "value required" }, { status: 400 });
  const updatedAt = typeof body.updatedAt === "string" ? body.updatedAt : new Date().toISOString();
  const d = await db();
  await d
    .insert(schema.settings)
    .values({ key, value: body.value, updatedAt })
    .onConflictDoUpdate({ target: schema.settings.key, set: { value: body.value, updatedAt } });
  return NextResponse.json({ key, value: body.value, updatedAt });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ key: string }> }) {
  const { key } = await ctx.params;
  const d = await db();
  await d.delete(schema.settings).where(eq(schema.settings.key, key));
  return NextResponse.json({ ok: true });
}
