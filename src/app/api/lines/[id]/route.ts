import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const b = await req.json().catch(() => ({}));
  const set: Partial<typeof schema.melodicLineLogs.$inferInsert> = {};
  if ("grade" in b) set.grade = b.grade == null ? null : Number(b.grade);
  if ("comment" in b) set.comment = b.comment == null ? null : String(b.comment);
  const d = await db();
  await d.update(schema.melodicLineLogs).set(set).where(eq(schema.melodicLineLogs.id, id));
  return NextResponse.json({ ok: true });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const d = await db();
  await d.delete(schema.melodicLineLogs).where(eq(schema.melodicLineLogs.id, id));
  return NextResponse.json({ ok: true });
}
