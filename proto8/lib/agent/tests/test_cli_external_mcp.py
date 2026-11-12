"""驗 cli.json 的 mcp_servers（11-12 external-mcp 步 1）：server 檔讀取與形狀、codex 的 -c、bearer 只進 CLI 行程的環境、壞的那台 warning 跳過、畫面啟動器。"""
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
from agent import cli_mcp, cli_print  # noqa: E402
import mcp_server_file as msf  # noqa: E402
from tool_io import Error  # noqa: E402


class FakeCell:
    def __init__(self, d):
        self.d = d

    def file(self, name):
        return str(self.d / name)

    def write(self, name, text):
        Path(self.file(name)).write_text(text)


class ExternalMcp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-ext-mcp-"))
        self.token = "FAKE-" + secrets.token_hex(8)
        (self.tmp / "keys").mkdir(mode=0o700)
        (self.tmp / "keys" / "site.env").write_text("# fake\nexport SITE_TOKEN='%s'\n" % self.token)
        (self.tmp / "keys" / "ca.pem").write_text("not a real cert\n")
        (self.tmp / "mcp").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def server(self, fname, **kw):
        s = {"name": "site", "transport": "http", "url": "https://127.0.0.1:18443/mcp",
             "bearer_token_env": "SITE_TOKEN", "env_file": "../keys/site.env", "ca_file": "../keys/ca.pem"}
        s.update(kw)
        s = {k: v for k, v in s.items() if v is not None}
        (self.tmp / "mcp" / fname).write_text(json.dumps({"description": "fake", "mcp_server": s}))
        return str(self.tmp / "mcp" / fname)

    def cfg(self, entries, kind="codex"):
        c = {"kind": kind, "mcp_servers": entries}
        err = io.StringIO()
        with redirect_stderr(err):
            c["external"] = cli_mcp.external_servers(c, str(self.tmp), str(self.tmp / "cli.json"))
        return c, err.getvalue()

    def test_load_http(self):
        s = msf.load(self.server("a.json", only=["echo"]))
        self.assertEqual(s["env_file"], str(self.tmp / "keys" / "site.env"))
        self.assertEqual(s["ca_file"], str(self.tmp / "keys" / "ca.pem"))
        self.assertEqual(s["only"], ["echo"])

    def test_load_bad(self):
        for kw, code in (({"name": "aos"}, "PackBad"), ({"name": "Bad-Name"}, "PackBad"), ({"transport": "sse"}, "PackBad"),
                         ({"command": "x"}, "PackBad"), ({"only": ["a"], "except": ["b"]}, "PackBad"),
                         ({"url": "ftp://x"}, "PackBad"), ({"env_file": "../keys/nope.env"}, "PathMissing"),
                         ({"ca_file": "../keys/nope.pem"}, "PathMissing")):
            with self.assertRaises(Error) as cm:
                msf.load(self.server("b.json", **kw))
            self.assertEqual(cm.exception.code, code, kw)
        with self.assertRaises(Error) as cm:
            msf.load(str(self.tmp / "mcp" / "none.json"))
        self.assertEqual(cm.exception.code, "PackMissing")

    def test_stdio_shape_only(self):
        s = msf.load(self.server("s.json", transport="stdio", url=None, bearer_token_env=None, ca_file=None,
                                 command="aos-mcp", args=["x"]))
        self.assertEqual(s["command"], "aos-mcp")

    def test_codex_flags_and_env(self):
        self.server("a.json", only=["echo"])
        c, err = self.cfg(["mcp/a.json"])
        self.assertEqual(err, "")
        argv, env, spec = cli_mcp.external_codex(c)
        self.assertEqual(argv[::2], ["-c"] * (len(argv) // 2))
        conf = tomllib.loads("\n".join(argv[1::2]))
        site = conf["mcp_servers"]["site"]
        self.assertEqual(site, {"url": "https://127.0.0.1:18443/mcp", "bearer_token_env_var": "SITE_TOKEN",
                                "default_tools_approval_mode": "approve", "enabled_tools": ["echo"]})
        self.assertEqual(conf["shell_environment_policy"]["exclude"], ["SITE_TOKEN"])
        self.assertEqual(env["SITE_TOKEN"], self.token)
        self.assertEqual(env["SSL_CERT_FILE"], str(self.tmp / "keys" / "ca.pem"))
        self.assertEqual(env["CODEX_CA_CERTIFICATE"], env["SSL_CERT_FILE"])
        self.assertNotIn(self.token, json.dumps(argv) + json.dumps(spec))
        self.assertEqual(spec["from"], [["SITE_TOKEN", str(self.tmp / "keys" / "site.env")]])

    def test_broken_skipped_others_kept(self):
        self.server("good.json")
        self.server("dup.json")
        self.server("bad.json", name="aos")
        self.server("other.json", name="other", bearer_token_env="OTHER_TOKEN")   # env file has no OTHER_TOKEN
        c, err = self.cfg(["mcp/good.json", "mcp/missing.json", "mcp/bad.json", "mcp/dup.json", "mcp/other.json"])
        self.assertEqual([s["name"] for s in c["external"]], ["site", "other"])
        self.assertIn("PackMissing", err)
        self.assertIn("name aos is taken", err)
        self.assertIn("already used", err)
        err2 = io.StringIO()
        with redirect_stderr(err2):
            argv, env, _ = cli_mcp.external_codex(c)
        self.assertIn("other skipped", err2.getvalue())
        self.assertNotIn(self.token, err + err2.getvalue())
        self.assertNotIn("mcp_servers.other.", " ".join(argv))
        self.assertIn("mcp_servers.site.url", " ".join(argv))

    def test_ca_conflict_second_skipped(self):
        (self.tmp / "keys" / "ca2.pem").write_text("x\n")
        self.server("a.json")
        self.server("b.json", name="two", ca_file="../keys/ca2.pem")
        c, _ = self.cfg(["mcp/a.json", "mcp/b.json"])
        err = io.StringIO()
        with redirect_stderr(err):
            argv, _, _ = cli_mcp.external_codex(c)
        self.assertIn("two skipped", err.getvalue())
        self.assertNotIn("mcp_servers.two.", " ".join(argv))

    def stdio(self, fname="s.json", **kw):
        (self.tmp / "keys" / "demo.env").write_text("DEMO_KEY=%s\n" % self.token)
        base = dict(name="demo", transport="stdio", url=None, bearer_token_env=None, ca_file=None,
                    env_file="../keys/demo.env", command="sh", args=["-c", 'test "$DEMO_KEY" = "$1" && echo "ok $TZ"', "sh", self.token],
                    env={"TZ": "UTC"})
        base.update(kw)
        return self.server(fname, **base)

    def test_stdio_both_bodies(self):
        f = self.stdio(only=["peek_now_time"])
        launcher = str(LIB.parent / "cmd" / "aos-mcp-launch" / "bin" / "aos-mcp-launch")
        with patch.object(cli_mcp.shutil, "which", lambda n: launcher if n == "aos-mcp-launch" else None), \
                patch.dict(os.environ, {"AOS_HOME": "/p8"}):
            c, err = self.cfg(["mcp/s.json"], kind="claude")
            self.assertEqual(err, "")
            ext, env, spec = cli_mcp.external_claude(c)
            cell = FakeCell(self.tmp)
            argv = cli_mcp.mcp_argv(c, cell, "/w", "/st", ext)
            self.assertEqual(json.loads(Path(cell.file("mcp.json")).read_text())["mcpServers"],
                             {"demo": {"command": launcher, "args": [f]}})
            self.assertEqual(argv[2:], ["--allowedTools", "mcp__demo__peek_now_time"])
            self.assertEqual((env, spec), ({}, None))
            c, _ = self.cfg(["mcp/s.json"])
            argv, env, spec = cli_mcp.external_codex(c)
        demo = tomllib.loads("\n".join(argv[1::2]))["mcp_servers"]["demo"]
        self.assertEqual(demo, {"command": launcher, "args": [f], "env": {"AOS_HOME": "/p8"},
                                "default_tools_approval_mode": "approve", "enabled_tools": ["peek_now_time"]})
        self.assertNotIn(self.token, json.dumps(argv))
        self.assertEqual((env, spec), ({}, None))

    def test_launcher_runs_server_with_key(self):
        f = self.stdio()
        launcher = str(LIB.parent / "cmd" / "aos-mcp-launch" / "bin" / "aos-mcp-launch")
        r = subprocess.run([launcher, f], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "ok UTC", r.stderr)
        self.server("h.json")
        r = subprocess.run([launcher, str(self.tmp / "mcp" / "h.json")], capture_output=True, text=True)
        self.assertIn("aos-mcp-launch: error: PackBad", r.stderr)
        r = subprocess.run([launcher], capture_output=True, text=True)
        self.assertIn("ArgumentsBad", r.stderr)

    def test_launcher_relative_paths_from_server_folder(self):
        """aos-mcp-launch 先 cd 到 server 檔的資料夾：command（含 /）與 args 的相對路徑都從那裡算，跟呼叫者的 cwd 無關（Q2 代定 G13）。"""
        (self.tmp / "mcp" / "bin").mkdir()
        (self.tmp / "mcp" / "bin" / "hello.txt").write_text("from the server folder\n")
        run = self.tmp / "mcp" / "bin" / "run"
        run.write_text("#!/bin/sh\nexec cat \"$@\"\n")
        run.chmod(0o755)
        (self.tmp / "mcp" / "r.json").write_text(json.dumps({"description": "fake", "mcp_server": {
            "name": "rel", "transport": "stdio", "command": "bin/run", "args": ["bin/hello.txt"]}}))
        (self.tmp / "elsewhere").mkdir()
        launcher = str(LIB.parent / "cmd" / "aos-mcp-launch" / "bin" / "aos-mcp-launch")
        r = subprocess.run([launcher, "../mcp/r.json"], capture_output=True, text=True, cwd=self.tmp / "elsewhere")
        self.assertEqual((r.returncode, r.stdout), (0, "from the server folder\n"), r.stderr)

    def test_stdio_launcher_missing(self):
        self.stdio()
        c, _ = self.cfg(["mcp/s.json"])
        with patch.object(cli_mcp.shutil, "which", lambda n: None), redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            cli_mcp.external_codex(c)

    def test_claude_side(self):
        self.server("a.json", except_=None)
        self.server("b.json", name="two", bearer_token_env=None, env_file=None, ca_file=None, only=["echo"])
        self.server("c.json", name="three", ca_file=None, **{"except": ["echo"]})
        c, err = self.cfg(["mcp/a.json", "mcp/b.json", "mcp/c.json"], kind="claude")
        self.assertEqual(err, "")
        cell = FakeCell(self.tmp)
        ext, env, spec = cli_mcp.external_claude(c)
        argv = cli_mcp.mcp_argv(c, cell, "/w", "/st", ext)
        self.assertEqual(env, {"NODE_EXTRA_CA_CERTS": str(self.tmp / "keys" / "ca.pem")})
        self.assertEqual(spec, {"set": env, "from": []})
        self.assertEqual(argv[:2], ["--mcp-config", cell.file("mcp.json")])
        self.assertEqual(argv[2:4], ["--allowedTools", "mcp__site,mcp__two__echo,mcp__three"])
        self.assertEqual(argv[4:], ["--disallowedTools", "mcp__three__echo"])
        written = Path(cell.file("mcp.json")).read_text()
        self.assertNotIn(self.token, written + json.dumps(argv))
        conf = json.loads(written)["mcpServers"]
        self.assertEqual(sorted(conf), ["site", "three", "two"])
        self.assertEqual(conf["two"], {"type": "http", "url": "https://127.0.0.1:18443/mcp"})
        r = subprocess.run(conf["site"]["headersHelper"], shell=True, capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout), {"Authorization": "Bearer " + self.token})

    def test_bad_array_is_cfgbad(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.cfg("mcp/a.json")

    def test_no_key_no_change(self):
        c = {"kind": "codex"}
        self.assertEqual(cli_mcp.external_servers(c, str(self.tmp), "cli.json"), [])
        self.assertEqual(cli_mcp.external_codex({"kind": "codex", "external": []}), ([], {}, None))

    def test_run_cli_env_only_child(self):
        r = cli_print.run_cli(["sh", "-c", 'cat >/dev/null; test "$SITE_TOKEN" = "$1" && echo same', "sh", self.token],
                                "", str(self.tmp), 10000, env={"SITE_TOKEN": self.token})
        self.assertEqual(r.stdout.strip(), "same")
        self.assertNotIn("SITE_TOKEN", os.environ)

    def test_exec_launcher(self):
        self.server("a.json")
        c, _ = self.cfg(["mcp/a.json"])
        _, _, spec = cli_mcp.external_codex(c)
        argv = cli_mcp.exec_wrap(["sh", "-c", 'test -n "$SITE_TOKEN" && echo "$SSL_CERT_FILE"'], spec)
        self.assertNotIn(self.token, " ".join(argv))
        r = subprocess.run(argv, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "SITE_TOKEN"})
        self.assertEqual(r.stdout.strip(), str(self.tmp / "keys" / "ca.pem"))
        self.assertNotIn(self.token, r.stdout + r.stderr)
        self.assertEqual(cli_mcp.exec_wrap(["x"], None), ["x"])


if __name__ == "__main__":
    unittest.main()
