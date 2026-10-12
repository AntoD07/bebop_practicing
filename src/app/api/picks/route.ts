import { NextResponse } from "next/server";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function GET() {
  const d = await db();
  const rows = await d.select({ pickKey: schema.connectionPicks.pickKey, savedAt: schema.connectionPicks.savedAt, kept: schema.connectionPicks.kept }).from(schema.connectionPicks);
  return NextResponse.json({ picks: rows.map((r) => ({ pickKey: r.pickKey, saved: r.savedAt, n_kept: r.kept.length })) });
}
