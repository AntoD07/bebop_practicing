import { NextResponse } from "next/server";
import { db, schema } from "@/lib/db/client";

export const runtime = "nodejs";

export async function GET() {
  const d = await db();
  const rows = await d.select({ name: schema.scores.name, savedAt: schema.scores.savedAt, filename: schema.scores.filename, bestFingering: schema.scores.bestFingering }).from(schema.scores);
  return NextResponse.json({ scores: rows });
}

export async function POST(req: Request) {
  const b = await req.json().catch(() => null);
  const name = String(b?.name ?? "").trim();
  if (!name || typeof b.musicxml !== "string" || !b.musicxml) return NextResponse.json({ error: "name and musicxml required" }, { status: 400 });
  const filename = String(b.filename ?? "score.musicxml");
  const d = await db();
  const savedAt = new Date().toISOString();
  // re-saving keeps any best fingering already chosen
  await d
    .insert(schema.scores)
    .values({ name, savedAt, filename, musicxml: b.musicxml, bestFingering: null })
    .onConflictDoUpdate({ target: schema.scores.name, set: { savedAt, filename, musicxml: b.musicxml } });
  return NextResponse.json({ ok: true, name, savedAt });
}
