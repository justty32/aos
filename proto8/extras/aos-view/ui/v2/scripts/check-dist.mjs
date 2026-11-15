// build gate (02c §6): JS after compression (gzip) at most 250 KB; no inline <script> in index.html (CSP script-src 'self').
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
let raw = 0, gz = 0;
for (const f of readdirSync("dist/assets")) if (f.endsWith(".js")) {
  const b = readFileSync("dist/assets/" + f);
  raw += b.length; gz += gzipSync(b).length;
}
const html = readFileSync("dist/index.html", "utf8");
const inline = /<script(?![^>]*\bsrc=)[^>]*>/.test(html);
console.log(`check-dist: js ${(raw / 1024).toFixed(1)} KB, gzip ${(gz / 1024).toFixed(1)} KB (limit 250), inline script: ${inline}`);
process.exit(gz > 250 * 1024 || inline ? 1 : 0);
