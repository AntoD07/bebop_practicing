import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

// One row per calendar day: the server draws the random key/position on the
// first request of the day so phone and laptop can never disagree.
export const practiceDays = sqliteTable("practice_days", {
  date: text("date").primaryKey(),
  key: text("key").notNull(),
  position: integer("position").notNull(),
  updatedAt: text("updated_at").notNull(),
});

// Curation of the Cell Connections page, keyed exactly like the legacy
// connection_picks.json (chord1|chord2|[ii:]pivot|position[|anchor:…]).
export const connectionPicks = sqliteTable("connection_picks", {
  pickKey: text("pick_key").primaryKey(),
  kept: text("kept", { mode: "json" }).$type<string[][]>().notNull(),
  deletedFingerings: text("deleted_fingerings", { mode: "json" }).$type<Record<string, string[]>>().notNull(),
  savedAt: text("saved_at").notNull(),
});

export const melodicLineLogs = sqliteTable("melodic_line_logs", {
  id: text("id").primaryKey(),
  date: text("date").notNull(),
  lineType: text("line_type").notNull(),
  cells: text("cells", { mode: "json" }).$type<string[]>().notNull(),
  noteSeq: text("note_seq", { mode: "json" }).$type<string[][]>().notNull(),
  grade: integer("grade"),
  comment: text("comment"),
  movement: text("movement"),
  tabEncoding: text("tab_encoding"),
  tabJson: text("tab_json", { mode: "json" }).$type<unknown>(),
  createdAt: text("created_at").notNull(),
});

export const scores = sqliteTable("scores", {
  name: text("name").primaryKey(),
  savedAt: text("saved_at").notNull(),
  filename: text("filename").notNull(),
  musicxml: text("musicxml").notNull(),
  bestFingering: text("best_fingering", { mode: "json" }).$type<unknown>(),
});

export const drillSessions = sqliteTable("drill_sessions", {
  id: text("id").primaryKey(),
  config: text("config", { mode: "json" }).$type<unknown>().notNull(),
  items: text("items", { mode: "json" }).$type<unknown[]>().notNull(),
  currentIndex: integer("current_index").notNull(),
  remainingSeconds: integer("remaining_seconds").notNull(),
  state: text("state", { mode: "json" }).$type<unknown>().notNull(),
  updatedAt: text("updated_at").notNull(),
  deviceId: text("device_id"),
});

export const settings = sqliteTable("settings", {
  key: text("key").primaryKey(),
  value: text("value", { mode: "json" }).$type<unknown>().notNull(),
  updatedAt: text("updated_at").notNull(),
});

// Shared compute cache in front of the Python function (any device).
export const engineCache = sqliteTable("engine_cache", {
  hash: text("hash").primaryKey(),
  engineVersion: text("engine_version").notNull(),
  body: text("body").notNull(),
  createdAt: text("created_at").notNull(),
});
