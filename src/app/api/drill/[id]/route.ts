import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const d = await db();
  const rows = await d.select().from(schema.drillSessions).where(eq(schema.drillSessions.id, id));
  if (!rows[0]) return NextResponse.json({ exists: false, id });
  return NextResponse.json({ exists: true, id, state: rows[0].state, updatedAt: rows[0].updatedAt, deviceId: rows[0].deviceId });
}

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.json().catch(() => null);
  const state = body?.state as { config?: unknown; items?: unknown[]; currentIndex?: number; itemRemainingMs?: number; itemDeadlineAt?: number | null; updatedAt?: number; deviceId?: string } | undefined;
  if (!state || !Array.isArray(state.items)) return NextResponse.json({ error: "state required" }, { status: 400 });
  const remaining = state.itemDeadlineAt ? Math.max(0, Math.round((state.itemDeadlineAt - Date.now()) / 1000)) : Math.round((state.itemRemainingMs ?? 0) / 1000);
  const d = await db();
  const row = { id, config: state.config ?? null, items: state.items, currentIndex: state.currentIndex ?? 0, remainingSeconds: remaining, state, updatedAt: new Date().toISOString(), deviceId: state.deviceId ?? null };
  await d.insert(schema.drillSessions).values(row).onConflictDoUpdate({ target: schema.drillSessions.id, set: row });
  return NextResponse.json({ ok: true, updatedAt: row.updatedAt });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const d = await db();
  await d.delete(schema.drillSessions).where(eq(schema.drillSessions.id, id));
  return NextResponse.json({ ok: true });
}
