import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";
import { PRACTICE_KEYS, POSITIONS } from "@/lib/music/constants";

export const runtime = "nodejs";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function pick<T>(xs: readonly T[]): T {
  return xs[Math.floor(Math.random() * xs.length)];
}

async function getOrDraw(date: string) {
  const d = await db();
  const rows = await d.select().from(schema.practiceDays).where(eq(schema.practiceDays.date, date));
  if (rows[0]) return rows[0];
  const row = { date, key: pick(PRACTICE_KEYS), position: 1 + Math.floor(Math.random() * POSITIONS.length), updatedAt: new Date().toISOString() };
  await d.insert(schema.practiceDays).values(row).onConflictDoNothing();
  const again = await d.select().from(schema.practiceDays).where(eq(schema.practiceDays.date, date));
  return again[0] ?? row;
}

export async function GET(req: Request) {
  const date = new URL(req.url).searchParams.get("date") ?? "";
  if (!DATE_RE.test(date)) return NextResponse.json({ error: "date=YYYY-MM-DD required" }, { status: 400 });
  return NextResponse.json(await getOrDraw(date));
}

export async function PUT(req: Request) {
  const body = await req.json().catch(() => ({}));
  const date = String(body.date ?? "");
  if (!DATE_RE.test(date)) return NextResponse.json({ error: "date=YYYY-MM-DD required" }, { status: 400 });
  const current = await getOrDraw(date);
  const key = body.key === undefined ? current.key : String(body.key);
  const position = body.position === undefined ? current.position : Number(body.position);
  if (!PRACTICE_KEYS.includes(key as (typeof PRACTICE_KEYS)[number])) return NextResponse.json({ error: "bad key" }, { status: 422 });
  if (!Number.isInteger(position) || position < 1 || position > POSITIONS.length) return NextResponse.json({ error: "bad position" }, { status: 422 });
  const d = await db();
  const row = { date, key, position, updatedAt: new Date().toISOString() };
  await d.insert(schema.practiceDays).values(row).onConflictDoUpdate({ target: schema.practiceDays.date, set: { key, position, updatedAt: row.updatedAt } });
  return NextResponse.json(row);
}
