// build gate (02c §6): JS after compression (gzip) at most 250 KB; no inline <script> in index.html (CSP script-src 'self').
// Only the assets index.html points at count: older hashed files stay in dist/ (nothing is deleted, 11-14 rule).
// The folder is dist/, or the first argument (scratch builds go to a new folder each time).
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
const dir = process.argv[2] || "dist";
const html = readFileSync(dir + "/index.html", "utf8");
let raw = 0, gz = 0;
for (const m of html.matchAll(/(?:src|href)="\/?(assets\/[^"]+\.js)"/g)) {
  const b = readFileSync(dir + "/" + m[1]);
  raw += b.length; gz += gzipSync(b).length;
}
const inline = /<script(?![^>]*\bsrc=)[^>]*>/.test(html);
console.log(`check-dist: js ${(raw / 1024).toFixed(1)} KB, gzip ${(gz / 1024).toFixed(1)} KB (limit 250), inline script: ${inline}`);
process.exit(gz > 250 * 1024 || inline ? 1 : 0);
