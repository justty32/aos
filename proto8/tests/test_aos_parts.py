"""test_aos_parts - proto8/bin/aos-parts：一個 agent 資料夾一份格的註冊檔（parts.json），add／rm／ls／get／which／run。

註冊的優先、沒註冊走固定名字（捷徑與真資料夾）、都沒有 which 退 10、註冊了但壞＝PartBad（不退固定名字）、
run 帶 env 跑那一格、run 找不到＝PartMissing、撞名 PartExists／--override、$env 指示詞只解要用的那一格、rm、ls、$ref 拆檔。
設計：proto8/thinking/2026-10-28-agent-round.md「§ 1 格怎麼找」與文末「實作時代定」。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

PARTS = str(ROOT / "bin" / "aos-parts")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "PART_K", "PART_KEY", "PART_UNSET")
SHOW = """#!/bin/sh
echo "$PART_K|$AOS_STACK|$*"
exit "${CODE:-0}"
"""


class AosParts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = Path(self.tmp.name)
        self.agent = t / "agent"
        self.agent.mkdir()
        lib = self.lib = t / "lib"
        for n in ("round", "queue", "history"):
            (lib / n).mkdir(parents=True)
            (lib / n / "_entry").write_text("#!/bin/sh\necho lib-%s \"$@\"\n" % n)
            (lib / n / "_entry").chmod(0o755)
        (lib / "show").write_text(SHOW)
        (lib / "show").chmod(0o755)
        (lib / "cat.json").write_text('{"_entry": {"argv": ["cat"]}}')
        self.env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        self.env["PATH"] = path_with(self.env.get("PATH", ""))

    def tearDown(self):
        self.tmp.cleanup()

    def run_parts(self, *args, stdin="", cwd=None, env=None):
        return subprocess.run([PARTS] + list(args), input=stdin, capture_output=True, text=True,
                              cwd=cwd or self.agent, env=env or self.env, timeout=60)

    def ok(self, *args, **kw):
        r = self.run_parts(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def bad(self, code, *args, **kw):
        r = self.run_parts(*args, **kw)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(r.stderr.splitlines()[-1].startswith("aos-parts: " + code + " "), r.stderr)   # aos-json 的那行可能在前面
        return r.stderr

    def which(self, slot, **kw):
        return json.loads(self.ok("which", "--json", slot, **kw))

    def reg(self):
        return json.loads((self.agent / "parts.json").read_text())["parts"]

    def write_reg(self, parts):
        (self.agent / "parts.json").write_text(json.dumps({"parts": parts}))

    def test_registered_wins_over_fixed(self):
        (self.agent / "queue").mkdir()                                       # 固定名字也有
        self.ok("add", "queue", "../lib/queue")
        got = self.which("queue")
        self.assertEqual((got["path"], got["from"], got["env"]), (str(self.lib / "queue"), "parts", {}))
        self.assertEqual(self.ok("which", "queue"), str(self.lib / "queue") + "\n")
        self.assertEqual(self.ok("run", "queue", "x"), "lib-queue x\n")

    def test_fixed_name_symlink_and_real_dir(self):
        (self.agent / "round").symlink_to(self.lib / "round")               # 捷徑
        (self.agent / "hook").mkdir()
        (self.agent / "hook" / "pre_tool").mkdir()                           # 真資料夾，兩層槽名
        (self.agent / "hook" / "pre_tool" / "_entry").write_text("#!/bin/sh\necho mine\n")
        (self.agent / "hook" / "pre_tool" / "_entry").chmod(0o755)
        got = self.which("round")
        self.assertEqual((got["path"], got["from"]), (str(self.agent / "round"), "fixed"))   # 捷徑不解開
        self.assertEqual(self.which("hook/pre_tool")["path"], str(self.agent / "hook" / "pre_tool"))
        self.assertEqual(self.ok("run", "round", "a"), "lib-round a\n")
        self.assertEqual(self.ok("run", "hook/pre_tool"), "mine\n")
        self.assertFalse((self.agent / "parts.json").exists())              # 只是查，不寫

    def test_nothing_which_10_run_part_missing(self):
        for args in (("which", "hook/on_error"), ("which", "--json", "act")):
            r = self.run_parts(*args)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))
        self.ok("add", "queue", "../lib/queue")                              # 註冊檔裡有別的槽也一樣
        self.assertEqual(self.run_parts("which", "act").returncode, 10)
        self.bad("PartMissing", "run", "act")

    def test_registered_but_broken_is_part_bad(self):
        (self.agent / "queue").symlink_to(self.lib / "queue")               # 固定名字好好的
        self.write_reg({"queue": {"path": "../lib/nope"}})
        self.bad("PartBad", "which", "queue")                               # 不退去找固定名字
        self.bad("PartBad", "run", "queue")
        self.bad("PartBad", "ls")
        self.bad("PartBad", "get", "queue")
        (self.agent / "parts.json").unlink()
        self.ok("add", "history", "../lib/history")
        (self.lib / "history" / "_entry").unlink()
        (self.lib / "history").rmdir()
        self.bad("PartBad", "which", "history")
        (self.agent / "act").symlink_to(self.lib / "gone")                  # 固定名字是壞捷徑：也報錯、不當沒有
        self.bad("PartBad", "which", "act")
        (self.agent / "plain").write_text("not json")                       # 沒 +x 也不是 JSON
        self.bad("PartBad", "which", "plain")

    def test_run_env_args_code(self):
        self.ok("add", "--env", "PART_K=v1", "--env=CODE=3", "act", "../lib/show")
        stack = str(self.t / "st")
        env = dict(self.env, PART_K="outer", AOS_STACK=stack)
        r = self.run_parts("run", "act", "a", "b c", env=env)
        self.assertEqual((r.returncode, r.stdout), (3, "v1|%s/|a b c\n" % stack))  # env 以註冊檔為準、AOS_STACK 傳下去（aos-exec 補 /）、結束碼是那格的
        self.assertEqual(self.which("act")["env"], {"PART_K": "v1", "CODE": "3"})
        self.ok("add", "--override", "cat", "../lib/cat.json")              # JSON 檔也能登記、stdin 原樣進
        self.assertEqual(self.ok("run", "cat", stdin="hi\n"), "hi\n")

    def test_add_exists_override_and_store(self):
        (self.agent / "round").symlink_to(self.lib / "round")
        self.ok("add", "round", "round")                                     # 收捷徑：存 abspath、不解開
        self.assertEqual(self.reg()["round"], {"path": str(self.agent / "round")})
        self.bad("PartExists", "add", "round", "../lib/queue")
        self.ok("add", "--override", "--env", "A=1", "round", "../lib/queue")
        self.assertEqual(self.reg()["round"], {"path": str(self.lib / "queue"), "env": {"A": "1"}})
        self.ok("add", "endpoint/fake", "../lib/show")
        self.assertIn("endpoint/fake", self.reg())
        before = (self.agent / "parts.json").read_text()
        (self.lib / "plain.txt").write_text("hello")
        self.bad("PathMissing", "add", "act", "../lib/nope")
        self.bad("PathBad", "add", "act", "../lib/plain.txt")
        self.bad("SlotBad", "add", "Act", "../lib/queue")
        self.bad("SlotBad", "add", "a/b/c", "../lib/queue")
        self.bad("ArgumentsBad", "add", "../lib/queue")                     # 槽名必給
        self.bad("ArgumentsBad", "add", "--env", "noeq", "act", "../lib/queue")
        self.assertEqual((self.agent / "parts.json").read_text(), before)   # 錯了什麼都不寫

    def test_env_directive_only_this_slot(self):
        self.write_reg({"endpoint/fake": {"path": "../lib/show", "env": {"PART_K": {"$env": "PART_KEY"}}},
                        "endpoint/openai": {"path": "../lib/show", "env": {"PART_K": {"$env": "PART_UNSET"}}}})
        env = dict(self.env, PART_KEY="secret")
        self.assertEqual(self.which("endpoint/fake", env=env)["env"], {"PART_K": "secret"})   # 別格的 $env 沒設不擋
        self.assertEqual(self.ok("run", "endpoint/fake", env=env).split("|")[0], "secret")
        self.bad("DirectiveBad", "which", "endpoint/openai", env=env)
        self.bad("DirectiveBad", "run", "endpoint/openai", env=env)

    def test_rm_ls_get(self):
        self.assertEqual(self.ok("ls"), "")
        self.assertEqual(json.loads(self.ok("ls", "--json")), [])
        self.ok("add", "queue", "../lib/queue")
        self.ok("add", "--env", "X=1", "act", "../lib/show")
        rows = [l.split("\t") for l in self.ok("ls").splitlines()]
        self.assertEqual(rows, [["act", str(self.lib / "show")], ["queue", str(self.lib / "queue")]])
        self.assertEqual(json.loads(self.ok("ls", "--json"))[0], {"slot": "act", "path": str(self.lib / "show"), "env": {"X": "1"}})
        self.assertEqual(json.loads(self.ok("get", "queue")), {"slot": "queue", "path": str(self.lib / "queue"), "env": {}})
        self.bad("PartMissing", "get", "round")
        self.assertEqual(json.loads(self.ok("rm", "act")), {"removed": "act"})
        self.assertEqual(sorted(self.reg()), ["queue"])
        self.bad("PartMissing", "rm", "act")
        self.write_reg([])
        self.bad("RegistryBad", "ls")
        self.write_reg({"Bad": {"path": "x"}})
        self.bad("RegistryBad", "which", "queue")

    def test_relative_from_registry_dir_and_ref_split(self):
        """手寫的相對路徑從 parts.json 的資料夾算；$ref 陣列拆成兩份，add 寫進最後一份、rm 從它所在那份拿掉。"""
        (self.agent / "parts.json").write_text('{"parts": {"$ref": ["base.json", "mine.json"]}}')
        (self.agent / "base.json").write_text('{"queue": {"path": "../lib/queue"}}')
        (self.agent / "mine.json").write_text("{}")
        other = self.t / "elsewhere"
        other.mkdir()
        (other / "queue").mkdir()                                            # cwd 的固定名字不算：看註冊檔的資料夾
        f = str(self.agent / "parts.json")
        self.assertEqual(self.ok("--file", f, "which", "queue", cwd=other), str(self.lib / "queue") + "\n")
        self.assertEqual(self.run_parts("--file", f, "which", "history", cwd=other).returncode, 10)
        self.ok("add", "history", "../lib/history")
        self.assertIn("history", json.loads((self.agent / "mine.json").read_text()))
        self.ok("rm", "queue")
        self.assertEqual(json.loads((self.agent / "base.json").read_text()), {})
        self.assertEqual([l.split("\t")[0] for l in self.ok("ls").splitlines()], ["history"])
        (self.agent / "parts.json").write_text('{"parts": {"$ref": "nope.json"}}')
        self.bad("DirectiveBad", "which", "queue")

    def test_usage_errors(self):
        self.bad("ArgumentsBad")
        self.bad("CommandUnknown", "list")
        self.bad("FlagUnknown", "--nope", "ls")
        self.bad("FlagUnknown", "ls", "--nope")
        self.bad("FlagUnknown", "add", "--nope", "act", "../lib/show")
        self.bad("ArgumentsBad", "which")
        self.bad("ArgumentsBad", "run")
        self.bad("SlotBad", "which", "../x")


if __name__ == "__main__":
    unittest.main()
