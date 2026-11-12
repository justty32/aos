"""Test agent_def new (copy, rebase, directive from, DefExists, outside the workspace) and check (wraps lib/aos/defs) in a temp folder."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
PROTO = Path(__file__).resolve().parents[4]
NAME = TOOL.parent.name


def good_def(d, tools='{"tools": {}}'):
    d.mkdir(parents=True)
    (d / "README.md").write_text("A test definition.\n")
    (d / "_metainfo.json").write_text('{"summary": "test"}')
    (d / "interfaces.json").write_text('{"aos-agent": {"tools": "tools.json", "llm": "llm.json"}}')
    (d / "tools.json").write_text(tools)
    (d / "llm.json").write_text('{"model": "fake"}')
    return d


class AgentDef(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-def-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(AOS_WS=str(self.ws), PYTHONDONTWRITEBYTECODE="1")

    def run_tool(self, args, **env):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), text=True,
                              capture_output=True, env=dict(self.env, **env), timeout=30)

    def new(self, src, path="born", **env):
        return self.run_tool({"op": "new", "from": src, "path": path}, **env)

    def tools(self, path="born"):
        return json.loads((self.ws / path / "tools.json").read_text())

    # ---- new（舊 test_copy_repo 的案例改成新介面）----
    def test_repo_template_is_copied_as_written(self):
        tpl = PROTO / "templates" / "agent-fsm"
        for env in ({"AOS_HOME": str(PROTO)}, {}):
            with self.subTest(env=env):
                r = self.new(str(tpl), **env)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                born = self.ws / "born"
                self.assertEqual(r.stdout, "wrote definition %s (copied from %s)\n" % (born, tpl))
                self.assertEqual((born / "tools.json").read_text(), (tpl / "tools.json").read_text())   # 全是指示詞：一字不改
                self.assertFalse(any(p.name == "__pycache__" for p in born.rglob("*")))
                self.assertNotIn("lineage", json.loads((born / "_metainfo.json").read_text()))
                self.assertEqual([p.name for p in self.ws.iterdir()], ["born"])          # 沒留暫存夾
                shutil.rmtree(born)

    def test_outside_template_through_symlink_uses_literal_path(self):
        real = self.ws / "far" / "deep" / "tpl"
        real.mkdir(parents=True)
        (self.ws / "far" / "deep" / "tool").mkdir()
        (real / "interfaces.json").write_text('{"aos-agent": {"tools": "tools.json"}}')
        (real / "tools.json").write_text('{"tools": {"t": {"path": "../tool"}}}')
        (self.ws / "alias").symlink_to(real, target_is_directory=True)
        r = self.new("alias")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        # 字面路徑 alias/../tool＝<ws>/tool（不是解開捷徑後的 far/deep/tool）
        self.assertEqual(self.tools()["tools"]["t"]["path"], "../tool")

    def test_env_file_and_override_rebased(self):
        tpl = self.ws / "tpls" / "tpl"
        tpl.mkdir(parents=True)
        (tpl / "interfaces.json").write_text('{"aos-agent": {"tools": "tools.json"}}')
        (tpl / "tools.json").write_text('{"$override": "../base.json", "tools": {"t": {"path": "../tool", "env_file": "../k.env"},'
                                        ' "abs": {"path": "/opt/x"}, "d": {"path": {"$env": "AOS_HOME", "$path": "/lib/x"}}}}')
        r = self.new("tpls/tpl")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        reg = self.tools()
        self.assertEqual(reg["tools"]["t"], {"path": "../tpls/tool", "env_file": "../tpls/k.env"})
        self.assertEqual(reg["tools"]["abs"], {"path": "/opt/x"})
        self.assertEqual(reg["tools"]["d"], {"path": {"$env": "AOS_HOME", "$path": "/lib/x"}})
        self.assertEqual(reg["$override"], "../tpls/base.json")

    def test_symlinks_copied_as_links(self):
        tpl = good_def(self.ws / "tpl")
        (tpl / "link").symlink_to("README.md")
        (tpl / "__pycache__").mkdir()
        self.assertEqual(self.new("tpl").returncode, 0)
        self.assertTrue((self.ws / "born" / "link").is_symlink())
        self.assertFalse((self.ws / "born" / "__pycache__").exists())

    def test_path_outside_workspace_ok(self):
        good_def(self.ws / "tpl", '{"tools": {"t": {"path": "../tool"}}}')
        out = self.root / "elsewhere" / "deep" / "helper"
        r = self.new("tpl", str(out))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((out / "interfaces.json").is_file())
        # 從新位置走回 <ws>/tool
        self.assertEqual(json.loads((out / "tools.json").read_text())["tools"]["t"]["path"], "../../../ws/tool")

    def test_directive_from(self):
        good_def(self.root / "home" / "templates" / "t1")
        r = self.new({"$env": "AOS_HOME", "$path": "/templates/t1"}, AOS_HOME=str(self.root / "home"))
        if shutil.which("aos-directive") is None:
            self.skipTest("aos-directive not on PATH")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("copied from %s" % (self.root / "home" / "templates" / "t1"), r.stdout)
        r = self.new({"$env": "AOS_HOME", "$path": "/templates/t1"}, "b2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("%s: error: DirectiveBad" % NAME, r.stdout)
        self.assertIn("AOS_HOME is not set", r.stdout)

    def test_def_exists(self):
        good_def(self.ws / "tpl")
        (self.ws / "born").mkdir()
        r = self.new("tpl")
        self.assertEqual(r.returncode, 1)
        self.assertIn("%s: error: DefExists" % NAME, r.stdout)
        (self.ws / "dangling").symlink_to("nowhere")
        self.assertIn("DefExists", self.new("tpl", "dangling").stdout)

    def test_from_missing(self):
        (self.ws / "file").write_text("x")
        for src in ("nope", "file"):
            r = self.new(src)
            self.assertEqual(r.returncode, 1)
            self.assertIn("%s: error: DefMissing" % NAME, r.stdout)
        self.assertFalse((self.ws / "born").exists())

    def test_failure_removes_temp_folder(self):
        tpl = self.ws / "tpl"
        tpl.mkdir()
        (tpl / "interfaces.json").write_text("not json")
        r = self.new("tpl")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DefBad", r.stdout)
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), ["tpl"])

    def test_plain_folder_just_copied(self):
        (self.ws / "plain").mkdir()
        (self.ws / "plain" / "a.txt").write_text("a")
        self.assertEqual(self.new("plain").returncode, 0)
        self.assertEqual((self.ws / "born" / "a.txt").read_text(), "a")

    # ---- 參數 ----
    def test_bad_arguments(self):
        for args, word in (({}, "ArgumentsBad missing op"),
                           ({"op": "nope"}, "OpUnknown"),
                           ({"op": "new", "from": "a", "path": "b", "files": {}}, "ArgumentsBad unknown key files"),
                           ({"op": "new", "from": "a", "path": "b", "name": "kid"}, "ArgumentsBad unknown key name"),
                           ({"op": "check", "path": "a", "from": "b"}, "does not take from"),
                           ({"op": "new", "path": "b"}, "needs template"),
                           ({"op": "new", "from": "a"}, "path needs"),
                           ({"op": "new", "from": 3, "path": "b"}, "ArgumentsBad"),
                           ({"op": "check"}, "path needs")):
            with self.subTest(args=args):
                r = self.run_tool(args)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(word, r.stdout)
                self.assertTrue(r.stdout.startswith("%s: error: " % NAME), r.stdout)

    # ---- check ----
    def test_check_good(self):
        good_def(self.ws / "d")
        r = self.run_tool({"op": "check", "path": "d"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout), {"problems": []})

    def test_check_bad(self):
        d = good_def(self.ws / "d")
        (d / "README.md").unlink()
        r = self.run_tool({"op": "check", "path": str(d)})
        self.assertEqual(r.returncode, 1)
        first, last = r.stdout.splitlines()[0], r.stdout.splitlines()[-1]
        self.assertEqual(json.loads(first)["problems"][0]["path"], ".")
        self.assertTrue(last.startswith("%s: error: DefBad" % NAME), r.stdout)
        self.assertIn("defs: error: DefBad", r.stderr)   # 下層 stderr 原樣透出

    def test_check_missing(self):
        r = self.run_tool({"op": "check", "path": "nope"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("%s: error: DefMissing" % NAME, r.stdout)

    def test_copy_real_template_then_check(self):
        """複製真的 templates/agent-fsm 後 check：照實記結果（11-10 晚：problems 空、退 0）。"""
        r = self.new(str(PROTO / "templates" / "agent-fsm"), "helper")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        r = self.run_tool({"op": "check", "path": "helper"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout), {"problems": []})


if __name__ == "__main__":
    unittest.main()
