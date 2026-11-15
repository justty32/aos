// build gate (02c §6): no dangerouslySetInnerHTML / innerHTML / eval in the sources; agent text goes through React text nodes.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
const bad = [/dangerouslySetInnerHTML/, /\.innerHTML\s*=/, /\beval\s*\(/, /new Function\s*\(/];
let fail = 0;
const walk = (d) => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p);
  else if (/\.(ts|tsx)$/.test(f)) { const s = readFileSync(p, "utf8"); for (const r of bad) if (r.test(s)) { console.error(`check-src: ${p}: ${r}`); fail = 1; } } } };
walk("src");
process.exit(fail);
