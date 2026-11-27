// Runs inside pi's proc: reads the aos/llm declaration under --llm, relays 127.0.0.1:PORT (pi's own loopback) to that unix socket, then runs pi and exits with its code.
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { spawn } from "node:child_process";

function die(msg) {
  process.stderr.write("launch: error: " + msg + "\n");
  process.exit(70);
}

const argv = process.argv.slice(2);
const sep = argv.indexOf("--");
if (sep < 0) die("usage: launch.mjs --llm DIR --port N -- PI_CLI_JS ARGS...");
const opts = {};
for (let i = 0; i < sep; i += 2) opts[argv[i].replace(/^--/, "")] = argv[i + 1];
const piArgv = argv.slice(sep + 1);
const llm = opts.llm || "/llm";
const port = Number(opts.port || 8787);

// aoslua: the dir has the interface iff this path is reachable; its parameters are the files under it
const decl = path.join(llm, "__meta/__interfaces/aos/llm");
const read = (k) => {
  try {
    return fs.readFileSync(path.join(decl, k), "utf8").trim();
  } catch (e) {
    die(`${llm} does not declare aos/llm (${path.join(decl, k)}: ${e.code})`);
  }
};
const kind = read("kind");
const protocol = read("protocol");
const api = read("api");
if (kind !== "socket") die(`aos/llm kind is ${kind}, this relay only speaks to a socket`);
if (protocol !== "http/1.1") die(`aos/llm protocol is ${protocol}, this relay expects http/1.1`);
if (api !== "openai-completions") die(`aos/llm api is ${api}, pi is configured for openai-completions`);
const sock = path.join(llm, read("path"));
process.stderr.write(`launch: aos/llm at ${llm}: ${kind} ${sock}, ${protocol} ${api} base ${read("base")}; relay 127.0.0.1:${port}\n`);

let conns = 0;
const srv = net.createServer((c) => {
  conns++;
  const u = net.connect(sock);
  c.pipe(u);
  u.pipe(c);
  c.on("error", () => u.destroy());
  u.on("error", (e) => {
    process.stderr.write(`launch: relay: ${sock}: ${e.code || e.message}\n`);
    c.destroy();
  });
});
srv.on("error", (e) => die(`listen 127.0.0.1:${port}: ${e.code || e.message}`));
srv.listen(port, "127.0.0.1", () => {
  const child = spawn(process.execPath, piArgv, { stdio: "inherit" });
  const fwd = (s) => () => child.kill(s);
  for (const s of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(s, fwd(s));
  child.on("exit", (code, sig) => {
    process.stderr.write(`launch: pi exited ${sig ? "on " + sig : "with " + code}; relay carried ${conns} connection(s)\n`);
    process.exit(sig ? 128 + 15 : code);
  });
  child.on("error", (e) => die(`spawn pi: ${e.message}`));
});
