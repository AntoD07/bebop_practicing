import "dotenv/config";
import { defineConfig } from "drizzle-kit";

const url = process.env.TURSO_DATABASE_URL ?? "file:./data/logs/bebop.db";
const remote = /^(libsql|https?|wss?):/.test(url);

export default defineConfig({
  schema: "./src/lib/db/schema.ts",
  out: "./drizzle",
  dialect: remote ? "turso" : "sqlite",
  dbCredentials: remote ? { url, authToken: process.env.TURSO_AUTH_TOKEN } : { url },
});
