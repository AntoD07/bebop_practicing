import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const d = await db();
  await d.delete(schema.fingeringFavorites).where(eq(schema.fingeringFavorites.id, id));
  return NextResponse.json({ ok: true });
}
