"""Test agent_def new (a plain copy like cp -r: byte for byte, _metainfo.json included, no path rewritten; directive from, DefExists, outside the workspace) and check (wraps py/tools/aos/defs) in a temp folder."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
PROTO = Path(__file__).resolve().parents[5]
NAME = TOOL.parent.name


def tree(root):
    """{相對路徑: (種類, 內容)}：檔＝(file, bytes, 權限位)、捷徑＝(link, 目標字串)、夾＝(dir, 權限位)；不跟捷徑走。"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for n in dirnames + filenames:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, root)
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                out[rel] = ("link", os.readlink(p))
            elif stat.S_ISDIR(st.st_mode):
                out[rel] = ("dir", stat.S_IMODE(st.st_mode))
            else:
                with open(p, "rb") as f:
                    out[rel] = ("file", f.read(), stat.S_IMODE(st.st_mode))
    return out


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

    def assert_same_copy(self, src, born):
        """born＝src 逐 byte 照抄（跟 cp -r 一樣）；唯一的不同是 __pycache__ 不抄（_metainfo.json 也照抄，使用者 11-21「不寫」）。"""
        want = {k: v for k, v in tree(src).items() if "__pycache__" not in Path(k).parts}
        self.assertEqual(tree(born), want)

    # ---- new 純粹 cp（使用者 11-20 第 10 題：「純粹的cp過去，各種相對路徑就這樣」）----
    def test_copy_is_byte_for_byte_and_rewrites_no_path(self):
        tpl = self.ws / "tpls" / "tpl"
        (tpl / "fn").mkdir(parents=True)
        (tpl / "sub" / "empty").mkdir(parents=True)
        (tpl / "__pycache__").mkdir()
        (tpl / "__pycache__" / "x.pyc").write_bytes(b"\0")
        (tpl / "interfaces.json").write_text('{"aos-agent": {"tools": "tools.json"}, "hooks": "hooks.json", "hookeds": "hookeds.json"}')
        tools = ('{"$override": "../base.json",\n "tools": {"add": {"path": "fn/add.py"},  "t": {"path": "../tool", "env_file": "../k.env"},'
                 ' "abs": {"path": "/opt/x"}, "d": {"path": {"$env": "AOS_HOME", "$path": "/lib/x"}}}}')
        (tpl / "tools.json").write_text(tools)                                    # 排版怪、有夾內夾外的相對路徑
        (tpl / "hookeds.json").write_text('{"h": {"event": "before_tool", "handler": "fn/no_secrets.py"}}')
        (tpl / "fn" / "add.py").write_text("#!/usr/bin/env python3\nprint(1)\n")
        (tpl / "fn" / "add.py").chmod(0o750)
        (tpl / "fsm.json").write_text('{"states": {"a": {"exec": {"argv": ["python3", "../../shared/x.py"]}}}}')
        (tpl / "_metainfo.json").write_text('{"summary": "t", "note": {"from": "old"}}')
        (tpl / "in_link").symlink_to("fn/add.py")
        (tpl / "out_link").symlink_to("../../outside")                          # 指夾外（斷的也照搬）
        (tpl / "abs_link").symlink_to("/etc/hostname")
        for dest in ("born", "a/b/c/born", str(self.root / "elsewhere" / "born")):
            with self.subTest(dest=dest):
                r = self.new("tpls/tpl", dest)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                born = Path(dest) if os.path.isabs(dest) else self.ws / dest
                self.assert_same_copy(tpl, born)
                self.assertEqual((born / "tools.json").read_text(), tools)        # 一字不改（含指夾外的 ../tool）

    def test_symlinked_tools_file_stays_a_link(self):
        tpl = good_def(self.ws / "tpl")
        (self.ws / "shared_tools.json").write_text('{"tools": {"t": {"path": "../tool"}}}')
        (tpl / "tools.json").unlink()
        (tpl / "tools.json").symlink_to("../shared_tools.json")
        self.assertEqual(self.new("tpl", "a/born").returncode, 0)
        link = self.ws / "a" / "born" / "tools.json"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../shared_tools.json")             # 照抄；從新位置指到哪裡就是哪裡
        self.assertFalse(link.exists())

    def test_every_stock_template_is_copied_byte_for_byte(self):
        """repo 的每份範本（有 interfaces.json 的）抄到深一層的地方：跟範本逐 byte 相同。"""
        root = PROTO / "templates"
        names = sorted(d.name for d in root.iterdir() if (d / "interfaces.json").is_file())
        self.assertIn("agent-fsm", names)
        for name in names:
            with self.subTest(template=name):
                r = self.run_tool({"op": "new", "template": name, "path": "deep/er/" + name}, AOS_HOME=str(PROTO))
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                self.assert_same_copy(root / name, self.ws / "deep" / "er" / name)

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
                self.assertEqual((born / "_metainfo.json").read_bytes(), (tpl / "_metainfo.json").read_bytes())   # 照抄
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
        self.assertIn("(copied from %s)" % (self.ws / "alias"), r.stdout)         # 字面路徑，不解開捷徑
        self.assert_same_copy(real, self.ws / "born")
        self.assertEqual(self.tools()["tools"]["t"]["path"], "../tool")         # 照抄

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
        # 純粹 cp：照抄，從新位置算就指到 elsewhere/deep/tool（使用者選「也不管，跟 #include 一樣」）
        self.assertEqual((out / "tools.json").read_text(), '{"tools": {"t": {"path": "../tool"}}}')

    def test_directive_from(self):
        good_def(self.root / "home" / "templates" / "t1")
        r = self.new({"$env": "AOS_HOME", "$path": "/templates/t1"}, AOS_HOME=str(self.root / "home"))
        if shutil.which("aos-directive") is None:
            self.skipTest("aos-directive not on PATH")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("copied from %s" % (self.root / "home" / "templates" / "t1"), r.stdout)
        self.assertEqual(json.loads((self.ws / "born" / "_metainfo.json").read_text()), {"summary": "test"})   # 照抄
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

    def test_broken_interfaces_is_just_copied(self):
        """new 不讀 interfaces.json（沒有要改寫的路徑）：壞的也照抄，留給 check 報。失敗清暫存夾見 test_copy_failure_leaves_nothing。"""
        tpl = self.ws / "tpl"
        tpl.mkdir()
        (tpl / "interfaces.json").write_text("not json")
        r = self.new("tpl")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual((self.ws / "born" / "interfaces.json").read_text(), "not json")
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), ["born", "tpl"])

    def test_plain_folder_just_copied(self):
        (self.ws / "plain").mkdir()
        (self.ws / "plain" / "a.txt").write_text("a")
        self.assertEqual(self.new("plain").returncode, 0)
        self.assertEqual((self.ws / "born" / "a.txt").read_text(), "a")
        # 沒有 _metainfo.json＝新的也沒有；兩邊都不多檔
        self.assertEqual(sorted(p.name for p in (self.ws / "born").iterdir()), ["a.txt"])
        self.assertEqual(sorted(p.name for p in (self.ws / "plain").iterdir()), ["a.txt"])

    # ---- _metainfo.json 照抄（11-21 使用者「不寫」）----
    def test_metainfo_copied_as_it_is(self):
        """每個鍵、排版、捷徑都照抄；new 不讀它，所以不是物件的也照抄。"""
        tpl = good_def(self.ws / "tpl")
        text = '{"summary": "test", "note": {"from": "grandpa"},   "cost": {"time_ms": 1}}'
        (tpl / "_metainfo.json").write_text(text)
        self.assertEqual(self.new("tpl").returncode, 0)
        self.assertEqual((self.ws / "born" / "_metainfo.json").read_text(), text)
        (tpl / "_metainfo.json").write_text("[1]")
        self.assertEqual(self.new("tpl", "born2").returncode, 0)
        self.assertEqual((self.ws / "born2" / "_metainfo.json").read_text(), "[1]")
        (tpl / "real_meta.json").write_text('{"summary": "linked"}')
        (tpl / "_metainfo.json").unlink()
        (tpl / "_metainfo.json").symlink_to("real_meta.json")
        self.assertEqual(self.new("tpl", "born3").returncode, 0)
        self.assertEqual(os.readlink(self.ws / "born3" / "_metainfo.json"), "real_meta.json")   # 捷徑照搬

    def test_copy_failure_leaves_nothing(self):
        """抄到一半失敗（讀不了的檔）＝WriteFailed、暫存夾清掉、目的地不在。"""
        tpl = good_def(self.ws / "tpl")
        secret = tpl / "secret.txt"
        secret.write_text("x")
        secret.chmod(0)
        self.addCleanup(secret.chmod, 0o644)
        if os.access(secret, os.R_OK):
            self.skipTest("running as a user who can read a mode-000 file")
        r = self.new("tpl")
        self.assertEqual(r.returncode, 1)
        self.assertIn("%s: error: WriteFailed" % NAME, r.stdout)
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), ["tpl"])

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

    def test_check_finds_what_the_copy_calls_but_is_not_there(self):
        """11-19 aos-check-refs（G1，使用者選「只放進檢查指令」）：寫錯的工具路徑、不在的格程式、型別錯的腦設定，check 報 DefBad。"""
        r = self.new(str(PROTO / "templates" / "agent-fsm"), "helper")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        d = self.ws / "helper"
        tools = json.loads((d / "tools.json").read_text())
        tools.setdefault("tools", {})["ghost"] ={"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/nope"}}
        (d / "tools.json").write_text(json.dumps(tools))
        (d / "wait.py").unlink()
        (d / "llm.json").write_text('{"temperature": "hot"}')
        r = self.run_tool({"op": "check", "path": "helper"})
        self.assertEqual(r.returncode, 1, r.stderr + r.stdout)
        reasons = [p["reason"] for p in json.loads(r.stdout.splitlines()[0])["problems"]]
        self.assertEqual(len(reasons), 3, reasons)
        self.assertIn("tool ghost cannot be used (PathMissing", reasons[0])
        self.assertIn('fsm.json#/states/wait/exec/argv/1: script "wait.py" does not exist', reasons[1])
        self.assertEqual(reasons[2], 'temperature in llm.json must be a number, not "hot"')
        self.assertTrue(r.stdout.splitlines()[-1].startswith("%s: error: DefBad 3 definition problems found" % NAME), r.stdout)


if __name__ == "__main__":
    unittest.main()
