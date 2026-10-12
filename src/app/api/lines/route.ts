import { NextResponse } from "next/server";
import { desc, eq } from "drizzle-orm";
import { db, schema } from "@/lib/db/client";
import { uid } from "@/lib/utils";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const lineType = new URL(req.url).searchParams.get("line_type");
  const d = await db();
  const q = d.select().from(schema.melodicLineLogs);
  const rows = lineType ? await q.where(eq(schema.melodicLineLogs.lineType, lineType)).orderBy(desc(schema.melodicLineLogs.createdAt)) : await q.orderBy(desc(schema.melodicLineLogs.createdAt));
  return NextResponse.json({ lines: rows });
}

export async function POST(req: Request) {
  const b = await req.json().catch(() => null);
  if (!b || !Array.isArray(b.cells) || !Array.isArray(b.note_seq) || typeof b.line_type !== "string") return NextResponse.json({ error: "line_type, cells[], note_seq[] required" }, { status: 400 });
  const row = {
    id: typeof b.id === "string" && b.id ? b.id : uid(),
    date: typeof b.date === "string" ? b.date : new Date().toISOString().slice(0, 10),
    lineType: b.line_type,
    cells: (b.cells as unknown[]).map(String),
    noteSeq: (b.note_seq as unknown[]).map((x) => (Array.isArray(x) ? x.map(String) : [String(x)])),
    grade: b.grade == null ? null : Number(b.grade),
    comment: b.comment == null ? null : String(b.comment),
    movement: b.movement == null || b.movement === "" ? null : String(b.movement),
    tabEncoding: b.tab_encoding == null ? null : String(b.tab_encoding),
    tabJson: b.tab_json ?? null,
    createdAt: new Date().toISOString(),
  };
  const d = await db();
  await d.insert(schema.melodicLineLogs).values(row).onConflictDoUpdate({ target: schema.melodicLineLogs.id, set: row });
  return NextResponse.json({ line: row });
}
