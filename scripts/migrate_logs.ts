// One-shot import of the legacy runtime logs into the app database.
//
//   npm run migrate:logs                       (reads ./data/logs + ./data/scores)
//   LEGACY_ROOT=/path/to/old/checkout npm run migrate:logs
//
// Idempotent upserts: connection_picks.json as-is (same keys), melodic_lines.csv
// (Python list reprs parsed by a tiny tokenizer; the Tab column -> tab_encoding;
// SVG files are not migrated), data/scores/index.csv + files/*, and today's
// practice_details.json seeds practice_days. Targets TURSO_DATABASE_URL when
// set, else the local file DB.
import "dotenv/config";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import * as schema from "../src/lib/db/schema";

const ROOT = process.env.LEGACY_ROOT ? path.resolve(process.env.LEGACY_ROOT) : path.resolve(__dirname, "..");
const LOGS = path.join(ROOT, "data", "logs");
const SCORES = path.join(ROOT, "data", "scores");

/** Parse a Python literal list of strings (possibly nested one level), e.g.
 * `['a', "b's", 'c']` or `["['5', '6']", "['1']"]`. */
export function pyLiteralList(src: string): unknown[] {
  let i = 0;
  const s = src.trim();
  function ws() {
    while (i < s.length && /\s/.test(s[i])) i++;
  }
  function str(): string {
    const q = s[i++];
    let out = "";
    while (i < s.length && s[i] !== q) {
      if (s[i] === "\\") {
        i++;
        out += s[i++];
      } else out += s[i++];
    }
    i++; // closing quote
    return out;
  }
  function value(): unknown {
    ws();
    if (s[i] === "[") return list();
    if (s[i] === "'" || s[i] === '"') return str();
    let tok = "";
    while (i < s.length && !/[,\]\s]/.test(s[i])) tok += s[i++];
    if (tok === "None") return null;
    if (tok === "True") return true;
    if (tok === "False") return false;
    const n = Number(tok);
    return Number.isFinite(n) ? n : tok;
  }
  function list(): unknown[] {
    const out: unknown[] = [];
    i++; // [
    ws();
    while (i < s.length && s[i] !== "]") {
      out.push(value());
      ws();
      if (s[i] === ",") i++;
      ws();
    }
    i++; // ]
    return out;
  }
  const v = value();
  return Array.isArray(v) ? v : [v];
}

/** Minimal RFC-4180 CSV reader (quoted fields with doubled quotes, newlines inside quotes). */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else inQ = false;
      } else field += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.some((x) => x !== "")) rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    if (row.some((x) => x !== "")) rows.push(row);
  }
  const [header, ...body] = rows;
  if (!header) return [];
  return body.map((r) => Object.fromEntries(header.map((h, k) => [h, r[k] ?? ""])));
}

async function main() {
  const url = process.env.TURSO_DATABASE_URL || "file:./data/logs/bebop.db";
  if (url.startsWith("file:")) fs.mkdirSync(path.dirname(url.slice(5)), { recursive: true });
  const client = createClient({ url, authToken: process.env.TURSO_AUTH_TOKEN || undefined });
  const db = drizzle(client, { schema });
  // the app creates the tables lazily; make sure they exist here too
  const { ensureSchema } = await import("../src/lib/db/client");
  process.env.TURSO_DATABASE_URL = url;
  await ensureSchema();

  let n = 0;
  // 1) connection picks
  const picksPath = path.join(LOGS, "connection_picks.json");
  if (fs.existsSync(picksPath)) {
    const picks = JSON.parse(fs.readFileSync(picksPath, "utf8")) as Record<string, { kept: string[][]; deleted_fingerings?: Record<string, string[]>; saved?: string }>;
    for (const [pickKey, v] of Object.entries(picks)) {
      const row = { pickKey, kept: v.kept ?? [], deletedFingerings: v.deleted_fingerings ?? {}, savedAt: v.saved ? `${v.saved}T00:00:00.000Z` : new Date().toISOString() };
      await db.insert(schema.connectionPicks).values(row).onConflictDoUpdate({ target: schema.connectionPicks.pickKey, set: row });
      n++;
    }
    console.log(`connection_picks: ${Object.keys(picks).length} row(s)`);
  }
  // 2) melodic lines
  const linesPath = path.join(LOGS, "melodic_lines.csv");
  if (fs.existsSync(linesPath)) {
    const rows = parseCsv(fs.readFileSync(linesPath, "utf8"));
    let k = 0;
    for (const r of rows) {
      const cells = pyLiteralList(r["Line"] ?? "[]").map(String);
      const noteSeq = pyLiteralList(r["Note sequence"] ?? "[]").map((x) => (typeof x === "string" ? pyLiteralList(x).map(String) : Array.isArray(x) ? x.map(String) : [String(x)]));
      // a stable id per CSV row (identical rows exist in the legacy log: keep them all)
      const id = "legacy:" + createHash("sha1").update(`${r["Date"]}|${r["Line type"]}|${cells.join("|")}|${k}`).digest("hex").slice(0, 24);
      const row = {
        id,
        date: r["Date"] || "1970-01-01",
        lineType: r["Line type"] || "",
        cells,
        noteSeq,
        grade: r["Grade"] ? Number(r["Grade"]) : null,
        comment: r["Comment"] || null,
        movement: r["Movement"] && r["Movement"] !== "nan" ? r["Movement"] : null,
        tabEncoding: r["Tab"] && r["Tab"] !== "nan" ? r["Tab"] : null,
        tabJson: null,
        createdAt: `${r["Date"] || "1970-01-01"}T00:00:${String(k % 60).padStart(2, "0")}.000Z`,
      };
      await db.insert(schema.melodicLineLogs).values(row).onConflictDoUpdate({ target: schema.melodicLineLogs.id, set: row });
      k++;
    }
    n += rows.length;
    console.log(`melodic_line_logs: ${rows.length} row(s)`);
  }
  // 3) scores
  const indexPath = path.join(SCORES, "index.csv");
  if (fs.existsSync(indexPath)) {
    const rows = parseCsv(fs.readFileSync(indexPath, "utf8"));
    let k = 0;
    for (const r of rows) {
      const file = r["File"] ? path.join(ROOT, r["File"]) : null;
      if (!file || !fs.existsSync(file)) {
        console.warn(`score ${r["Name"]}: file missing (${r["File"]})`);
        continue;
      }
      const best = r["Best fingering"] ? { label: r["Best fingering"], cost: r["Best cost"] ? Number(r["Best cost"]) : null, where: r["Best played at"] || null, encoding: r["Tab"] || null } : null;
      const row = { name: r["Name"], savedAt: r["Saved"] ? `${r["Saved"]}T00:00:00.000Z` : new Date().toISOString(), filename: path.basename(file), musicxml: fs.readFileSync(file, "utf8"), bestFingering: best };
      await db.insert(schema.scores).values(row).onConflictDoUpdate({ target: schema.scores.name, set: row });
      k++;
    }
    n += k;
    console.log(`scores: ${k} row(s)`);
  }
  // 4) today's draw
  const detailsPath = path.join(LOGS, "practice_details.json");
  if (fs.existsSync(detailsPath)) {
    const d = JSON.parse(fs.readFileSync(detailsPath, "utf8")) as { date: string; key: string; position: number };
    if (d.date && d.key && d.position) {
      const row = { date: d.date, key: d.key, position: Number(d.position), updatedAt: new Date().toISOString() };
      await db.insert(schema.practiceDays).values(row).onConflictDoNothing();
      n++;
      console.log(`practice_days: seeded ${d.date} (${d.key} / ${d.position})`);
    }
  }
  console.log(`done — ${n} row(s) upserted into ${url}`);
}

if (require.main === module) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
