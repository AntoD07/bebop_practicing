import fs from "node:fs";
import path from "node:path";
import { createClient, type Client } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import * as schema from "./schema";

const g = globalThis as unknown as { __bebopDb?: ReturnType<typeof drizzle<typeof schema>>; __bebopClient?: Client; __bebopSchema?: Promise<void> };

function makeClient(): Client {
  const url = process.env.TURSO_DATABASE_URL || "file:./data/logs/bebop.db";
  if (url.startsWith("file:")) {
    // local dev: make sure the folder exists (data/logs is git-ignored)
    try {
      fs.mkdirSync(path.dirname(url.slice("file:".length)), { recursive: true });
    } catch {
      /* ignore */
    }
  }
  return createClient({ url, authToken: process.env.TURSO_AUTH_TOKEN || undefined });
}

// Idempotent schema creation: zero-config locally and a safety net on Turso
// (drizzle-kit push is the real migration tool).
const DDL = [
  `CREATE TABLE IF NOT EXISTS practice_days (date TEXT PRIMARY KEY, key TEXT NOT NULL, position INTEGER NOT NULL, updated_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS connection_picks (pick_key TEXT PRIMARY KEY, kept TEXT NOT NULL, deleted_fingerings TEXT NOT NULL, saved_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS melodic_line_logs (id TEXT PRIMARY KEY, date TEXT NOT NULL, line_type TEXT NOT NULL, cells TEXT NOT NULL, note_seq TEXT NOT NULL, grade INTEGER, comment TEXT, movement TEXT, tab_encoding TEXT, tab_json TEXT, created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS scores (name TEXT PRIMARY KEY, saved_at TEXT NOT NULL, filename TEXT NOT NULL, musicxml TEXT NOT NULL, best_fingering TEXT)`,
  `CREATE TABLE IF NOT EXISTS drill_sessions (id TEXT PRIMARY KEY, config TEXT NOT NULL, items TEXT NOT NULL, current_index INTEGER NOT NULL, remaining_seconds INTEGER NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL, device_id TEXT)`,
  `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS engine_cache (hash TEXT PRIMARY KEY, engine_version TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)`,
];

export function rawClient(): Client {
  if (!g.__bebopClient) g.__bebopClient = makeClient();
  return g.__bebopClient;
}

export async function ensureSchema(): Promise<void> {
  if (!g.__bebopSchema) {
    g.__bebopSchema = (async () => {
      const c = rawClient();
      for (const sql of DDL) await c.execute(sql);
    })().catch((e) => {
      g.__bebopSchema = undefined;
      throw e;
    });
  }
  return g.__bebopSchema;
}

export async function db() {
  await ensureSchema();
  if (!g.__bebopDb) g.__bebopDb = drizzle(rawClient(), { schema });
  return g.__bebopDb;
}

export { schema };
