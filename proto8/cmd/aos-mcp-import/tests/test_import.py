"""Test aos-mcp-import (external-mcp 07 step 5) against the fake stdio MCP server: all, --only, --except, name clash, PackExists, bytes unchanged on errors, load still passes, the 20-tool warning, aos-tools ls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-mcp-import" / "bin" / "aos-mcp-import"
TOOLS_BIN = PROTO / "cmd" / "aos-tools" / "bin" / "aos-tools"
FAKE = PROTO / "lib" / "tests" / "fake_mcp_stdio.py"
sys.path.insert(0, str(PROTO / "lib"))
import mcp_server_file  # noqa: E402

FAKE_NAMES = ["echo", "fail", "image", "sleep", "big", "refschema", "show_env"]
# 換工具表的小殼：FAKE_TOOLS（JSON）蓋掉假 server 的 TOOLS，其餘行為照舊（撞名、超過 20 支用）。
WRAPPER = """import json, os, sys
sys.path.insert(0, %r)
import fake_mcp_stdio as f
f.TOOLS = json.loads(os.environ["FAKE_TOOLS"])
f.main()
""" % str(FAKE.parent)


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and k != "FAKE_MODE"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


def tool(name):
    return {"name": name, "description": "Tool %s." % name, "inputSchema": {"type": "object", "properties": {}}}


class Import(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-mcp-import-"))
        self.mcp = self.tmp / "mcp"
        self.mcp.mkdir()
        (self.tmp / "wrapper.py").write_text(WRAPPER)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def server_file(self, name="fake", tools=None, mode=None, **extra):
        s = {"name": name, "transport": "stdio", "command": sys.executable, "args": [str(FAKE)]}
        env = {}
        if tools is not None:
            s["args"] = [str(self.tmp / "wrapper.py")]
            env["FAKE_TOOLS"] = json.dumps(tools)
        if mode:
            env["FAKE_MODE"] = mode
        if env:
            s["env"] = env
        s.update(extra)
        p = self.mcp / ("%s.json" % name)
        p.write_text(json.dumps({"description": "A fake server for tests.", "mcp_server": s}, indent=1))
        return p

    def run_import(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=self.tmp,
                              env=clean_env(**env), capture_output=True, text=True, timeout=60)

    def fails(self, code, path, *args):
        before = path.read_bytes()
        r = self.run_import(*args)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("aos-mcp-import: error: %s " % code, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse([n for n in os.listdir(path.parent) if n.endswith(".tmp")])
        return r

    def imported(self, path, *args):
        before = json.loads(path.read_text())
        r = self.run_import(*args, path)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(path.read_text())
        self.assertEqual(doc["description"], before["description"])
        mcp_server_file.load(str(path))          # eca 那條照樣能讀同一份檔
        self.assertFalse([p for p in os.listdir(path.parent) if p.endswith(".tmp")])
        return r, doc

    # 全收
    def test_all(self):
        p = self.server_file()
        r, doc = self.imported(p)
        self.assertEqual(r.stdout.splitlines(), ["imported 7 of 7 tools from fake -> %s" % p,
                                                 'add it to tools.json "$override": "%s"' % p])
        self.assertEqual(r.stderr, "")
        self.assertEqual(list(doc), ["description", "mcp_server", "mcp_import", "mcp_tools", "tools"])
        self.assertNotIn("only", doc["mcp_server"])
        self.assertNotIn("except", doc["mcp_server"])
        self.assertEqual(list(doc["mcp_tools"]), FAKE_NAMES)
        self.assertEqual(doc["tools"]["fake_show_env"], {"path": "fake.json#/mcp_tools/show_env"})
        self.assertEqual(sorted(doc["tools"]), sorted("fake_" + n for n in FAKE_NAMES))
        imp = doc["mcp_import"]
        self.assertEqual(imp["protocol_version"], "2025-06-18")
        self.assertEqual(imp["server_tools"], 7)
        self.assertRegex(imp["imported_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
        echo = doc["mcp_tools"]["echo"]
        self.assertEqual(echo["_entry"], ["python3", {"$env": "AOS_HOME", "$path": "/lib/base/mcp_tool/_entry"},
                                          "--pack", "fake.json", "--tool", "echo"])
        self.assertEqual(echo["_tooldef"]["description"], "[MCP server fake] Return the supplied text.")
        self.assertNotIn("$defs", json.dumps(doc["mcp_tools"]["refschema"]["_tooldef"]))

    def test_only(self):
        p = self.server_file()
        r, doc = self.imported(p, "--only", "echo,fail")
        self.assertEqual(r.stdout.splitlines()[0], "imported 2 of 7 tools from fake -> %s" % p)
        self.assertEqual(doc["mcp_server"]["only"], ["echo", "fail"])
        self.assertEqual(list(doc["mcp_tools"]), ["echo", "fail"])
        self.assertEqual(sorted(doc["tools"]), ["fake_echo", "fake_fail"])

    def test_except(self):
        p = self.server_file()
        r, doc = self.imported(p, "--except=big,sleep")
        self.assertEqual(doc["mcp_server"]["except"], ["big", "sleep"])
        self.assertEqual(list(doc["mcp_tools"]), ["echo", "fail", "image", "refschema", "show_env"])

    def test_only_from_file_and_same_flag(self):
        p = self.server_file(only=["image", "echo"])
        r, doc = self.imported(p, "--only", "echo,image")       # 同一組（順序不同）＝照檔裡的
        self.assertEqual(doc["mcp_server"]["only"], ["image", "echo"])
        self.assertEqual(list(doc["mcp_tools"]), ["echo", "image"])

    def test_except_unknown_name_warns(self):
        p = self.server_file()
        r, doc = self.imported(p, "--except", "nope")
        self.assertIn("aos-mcp-import: warning: except names tools the server fake does not have: nope", r.stderr)
        self.assertEqual(len(doc["mcp_tools"]), 7)

    def test_flag_conflicts_with_file(self):
        p = self.server_file(only=["echo"])
        self.fails("ArgumentsBad", p, "--only", "fail", p)
        self.fails("ArgumentsBad", p, "--except", "fail", p)

    def test_only_unknown(self):
        p = self.server_file()
        r = self.fails("ToolUnknown", p, "--only", "echo,nope", p)
        self.assertIn("nope", r.stderr)

    # 撞名、原名有 / ~ . 大寫（邊緣 4）
    def test_name_clash_and_escaping(self):
        p = self.server_file(tools=[tool("Get.Time"), tool("get_time"), tool("a/b~c")])
        r = self.fails("NameBad", p, p)
        self.assertIn("fake_get_time", r.stderr)
        r, doc = self.imported(p, "--except", "Get.Time")
        self.assertEqual(doc["tools"], {"fake_get_time": {"path": "fake.json#/mcp_tools/get_time"},
                                        "fake_a_b_c": {"path": "fake.json#/mcp_tools/a~1b~0c"}})
        self.assertEqual(doc["mcp_tools"]["a/b~c"]["_entry"][-1], "a/b~c")

    def test_pack_exists(self):
        p = self.server_file()
        self.imported(p)
        r = self.fails("PackExists", p, p)
        self.assertIn("sync", r.stderr)

    def test_errors_leave_file(self):
        self.fails("ServerFailed", self.server_file(mode="init_fail"), self.mcp / "fake.json")
        p = self.server_file(command="/nonexistent/mcp-server")
        self.fails("CommandMissing", p, p)
        p = self.server_file(env_file="missing.env")
        self.fails("PathMissing", p, p)
        r = self.run_import(self.mcp / "nope.json")
        self.assertIn("aos-mcp-import: error: PackMissing ", r.stderr)
        p.write_text('{"description": "x", "mcp_server": {"name": "Bad", "transport": "stdio", "command": "x"}}')
        self.fails("PackBad", p, p)

    def test_write_failed(self):
        if os.geteuid() == 0:
            self.skipTest("root can write a read-only folder")
        p = self.server_file()
        os.chmod(self.mcp, 0o555)
        try:
            self.fails("WriteFailed", p, p)
        finally:
            os.chmod(self.mcp, 0o755)

    def test_timeout(self):
        p = self.server_file(args=["-c", "import time; time.sleep(30)"])
        t0 = time.monotonic()
        r = self.fails("ServerFailed", p, "--timeout-s", "0.5", p)
        self.assertLess(time.monotonic() - t0, 10)
        self.assertIn("timed out", r.stderr)
        self.fails("ArgumentsBad", p, "--timeout-s", "0", p)

    def test_many_tools_warn(self):
        p = self.server_file(tools=[tool("t%02d" % i) for i in range(21)])
        r, doc = self.imported(p)
        self.assertIn("aos-mcp-import: warning: imported all 21 tools of fake", r.stderr)
        self.assertEqual(len(doc["tools"]), 21)
        q = self.server_file(name="few", tools=[tool("t%02d" % i) for i in range(20)])
        r, _ = self.imported(q)
        self.assertNotIn("warning", r.stderr)

    def test_three_doors(self):
        r = self.run_import()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-mcp-import: error: ArgumentsBad ", r.stderr)
        self.assertIn("(usage: aos-mcp-import", r.stderr)
        r = self.run_import("--help")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("--only A,B", r.stdout)
        r = self.run_import("--bogus", "x.json")
        self.assertIn("aos-mcp-import: error: FlagUnknown ", r.stderr)
        r = self.run_import("sync", "x.json")
        self.assertIn("aos-mcp-import: error: CommandUnknown ", r.stderr)
        r = self.run_import("--only", "a", "--except", "b", "x.json")
        self.assertIn("aos-mcp-import: error: ArgumentsBad ", r.stderr)
        r = self.run_import("a.json", "b.json")
        self.assertIn("aos-mcp-import: error: ArgumentsBad ", r.stderr)

    # 疊進 tools.json，aos-tools 看得到（包檔資料夾相對路徑、整夾帶走仍通）
    def test_aos_tools_ls(self):
        p = self.server_file()
        self.imported(p, "--only", "echo,fail")
        moved = self.tmp / "moved"
        shutil.copytree(self.mcp, moved / "mcp")
        (moved / "tools.json").write_text(json.dumps({"$override": ["mcp/fake.json"], "tools": {}}))
        r = subprocess.run([sys.executable, str(TOOLS_BIN), "--file", str(moved / "tools.json"), "ls", "--json"],
                           cwd=moved, env=clean_env(AOS_HOME=str(PROTO)), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = {t["name"]: t for t in json.loads(r.stdout)}
        self.assertEqual(sorted(got), ["fake_echo", "fake_fail"])
        self.assertEqual(got["fake_echo"]["path"], "%s#/mcp_tools/echo" % (moved / "mcp" / "fake.json"))


if __name__ == "__main__":
    unittest.main()
