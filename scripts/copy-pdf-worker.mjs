// pdf.js needs its worker served as a plain file; copy it next to the app's
// static assets on install (public/ is git-ignored for this file).
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(import.meta.url);
try {
  const src = path.join(path.dirname(require.resolve("pdfjs-dist/package.json")), "build", "pdf.worker.min.mjs");
  mkdirSync("public", { recursive: true });
  copyFileSync(src, path.join("public", "pdf.worker.min.mjs"));
  console.log("copied pdf.worker.min.mjs to public/");
} catch (e) {
  if (!existsSync("public/pdf.worker.min.mjs")) console.warn("pdf worker not copied:", e.message);
}
