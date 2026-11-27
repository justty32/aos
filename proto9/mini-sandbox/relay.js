#!/usr/bin/env node
// The relay mini's llm kernel puts out next to its socket (copied from pi-sandbox/relay.js; the declaration dir defaults to $AOS_ENV, or / when it is not set, and the declared socket path may be absolute): listens on 127.0.0.1:PORT (the client's own loopback), joins each connection to the declared unix socket, runs CMD and exits with its code.
// CommonJS on purpose: the kernel puts it out without an extension, and node runs an extensionless file as CommonJS.
"use strict";
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { spawn } = require("node:child_process");

const USAGE = "relay [--llm DIR] [--port N] [-- CMD ARGS...]  (DIR: default $AOS_ENV, or / when it is not set; N: default 8787)";

function die(code, msg) {
  process.stderr.write(`relay: error: ${code} ${msg}\n`);
  process.exit(code === "ArgumentsBad" ? 2 : 1);
}

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h")) {
  process.stdout.write(`usage: ${USAGE}\nListens on 127.0.0.1:N and joins each connection to the unix socket that DIR (default $AOS_ENV) declares in .aos/interfaces/aos/llm/ (DIR: default $AOS_ENV, or / when it is not set); with CMD, runs it (a .js/.mjs/.cjs CMD runs under this node) and exits with its code.\n`);
  process.exit(0);
}
if (argv.length === 0) die("ArgumentsBad", `no arguments (usage: ${USAGE})`);
const sep = argv.indexOf("--");
const own = sep < 0 ? argv : argv.slice(0, sep);
const cmd = sep < 0 ? [] : argv.slice(sep + 1);
const opts = {};
for (let i = 0; i < own.length; i += 2) {
  if (!["--llm", "--port"].includes(own[i]) || own[i + 1] === undefined) die("ArgumentsBad", `bad argument ${own[i]} (usage: ${USAGE})`);
  opts[own[i].slice(2)] = own[i + 1];
}
const llm = opts.llm || process.env.AOS_ENV || "/"; // the rule: $AOS_ENV first, / when it is not set
const port = Number(opts.port || 8787);

// reachable = has the interface; its parameters are the one-line files under it
const decl = path.join(llm, ".aos/interfaces/aos/llm");
const read = (k) => {
  try {
    return fs.readFileSync(path.join(decl, k), "utf8").trim();
  } catch (e) {
    die("NotDeclared", `${llm} does not declare aos/llm (${path.join(decl, k)}: ${e.code})`);
  }
};
const want = { kind: "socket", protocol: "http/1.1", api: "openai-completions" };
for (const [k, v] of Object.entries(want)) {
  const got = read(k);
  if (got !== v) die("DeclarationBad", `aos/llm ${k} is ${got}, this relay needs ${v}`);
}
const sock = path.resolve(llm, read("path")); // absolute in mini: the declaration is copied into inner layers

const srv = net.createServer((c) => {
  const u = net.connect(sock);
  c.pipe(u);
  u.pipe(c);
  c.on("error", () => u.destroy());
  u.on("error", (e) => {
    process.stderr.write(`relay: warning: ${sock}: ${e.code || e.message}\n`);
    c.destroy();
  });
});
srv.on("error", (e) => die("ListenFailed", `127.0.0.1:${port}: ${e.code || e.message}`));
srv.listen(port, "127.0.0.1", () => {
  if (cmd.length === 0) return; // relay only, until killed
  const js = /\.(c|m)?js$/.test(cmd[0]);
  const child = spawn(js ? process.execPath : cmd[0], js ? cmd : cmd.slice(1), { stdio: "inherit" });
  for (const s of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(s, () => child.kill(s));
  child.on("exit", (code, sig) => {
    process.exit(sig ? 128 + (require("node:os").constants.signals[sig] || 15) : code);
  });
  child.on("error", (e) => die("SpawnFailed", `${cmd[0]}: ${e.message}`));
});
