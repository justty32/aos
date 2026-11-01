"""test_round_parts - lib/agent/parts.py：器官（roundlib、queue、compact、act、ask_round）共用的找格（11-01 A 題，取代 bin/aos-parts 與 test_aos_parts）。

parts.json＝aos-exec 格式的槽表（槽值＝字串路徑或 {".env", "_entry"}，endpoint／hook 巢狀、頂層不包 parts）。
查找順序：註冊檔有寫的優先（固定名字也在照樣用註冊檔）、沒寫走固定名字 <agent>/<槽>（捷徑、真資料夾）、都沒有＝None；
  登記了但壞＝不退去找固定名字（aos-exec 跑的時候自己報）；parts.json 壞／路上不是物件＝Bad。
叫起來：aos-exec <find 回的> 跑得動、相對路徑從 parts.json 的資料夾算；`.env` key 預設不蓋環境（N-58）、--dotenv-override 才蓋；
  必要的格沒掛＝round 格報 PartMissing、parts.json 壞＝PartsBad；endpoints 是註冊檔與 endpoint/ 底下的聯集。
設計：proto8/thinking/2026-10-31-parts-round.md（決定 11-01）、05 § 實作計畫 A 題。"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, path_with, tool  # noqa: E402

sys.path.insert(0, str(ROOT / "lib" / "agent"))
import parts  # noqa: E402

EXEC = tool("aos-exec")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "PART_K")
SHOW = '#!/bin/sh\necho "$PART_K|$*"\nexit "${CODE:-0}"\n'


class Parts(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.t = Path(t.name)
        self.agent = self.t / "agent"
        self.agent.mkdir()
        self.lib = self.t / "lib"
        for n in ("queue", "history", "act"):
            (self.lib / n).mkdir(parents=True)
            (self.lib / n / "_entry").write_text('#!/bin/sh\necho lib-%s "$@"\n' % n)
            (self.lib / n / "_entry").chmod(0o755)
        (self.lib / "show").write_text(SHOW)
        (self.lib / "show").chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        self.env["PATH"] = path_with(self.env.get("PATH", ""))

    def reg(self, table):
        (self.agent / "parts.json").write_text(json.dumps(table))

    def run_slot(self, slot, *args, env=None, flags=()):
        got = parts.find(str(self.agent), slot)
        self.assertIsNotNone(got, slot)
        return subprocess.run([EXEC] + list(flags) + [got] + list(args), capture_output=True, text=True,
                              env=dict(self.env, **(env or {})), cwd=self.t, timeout=60)

    def test_registered_wins_over_fixed(self):
        (self.agent / "queue").symlink_to(self.lib / "history")              # 固定名字也有（指到別的）
        self.reg({"queue": "../lib/queue"})                                   # 相對路徑從 parts.json 的資料夾算
        self.assertEqual(parts.find(str(self.agent), "queue"), "%s/parts.json#/queue" % self.agent)
        r = self.run_slot("queue", "x")
        self.assertEqual((r.returncode, r.stdout), (0, "lib-queue x\n"), r.stderr)

    def test_fixed_name_symlink_and_real_dir(self):
        self.reg({"history": "../lib/history"})                              # 註冊檔裡有別的槽也一樣
        (self.agent / "queue").symlink_to(self.lib / "queue")                # 捷徑
        hook = self.agent / "hook" / "pre_tool"
        hook.mkdir(parents=True)                                              # 真資料夾，兩層槽名
        (hook / "_entry").write_text("#!/bin/sh\necho mine\n")
        (hook / "_entry").chmod(0o755)
        self.assertEqual(parts.find(str(self.agent), "queue"), str(self.agent / "queue"))   # 捷徑不解開
        self.assertEqual(parts.find(str(self.agent), "hook/pre_tool"), str(hook))
        self.assertEqual(self.run_slot("queue", "a").stdout, "lib-queue a\n")
        self.assertEqual(self.run_slot("hook/pre_tool").stdout, "mine\n")
        (self.agent / "parts.json").unlink()                                  # 沒有 parts.json＝只看固定名字
        self.assertEqual(parts.find(str(self.agent), "queue"), str(self.agent / "queue"))

    def test_nothing_is_none(self):
        self.assertIsNone(parts.find(str(self.agent), "act"))
        self.reg({"queue": "../lib/queue", "hook": {"pre_think": "../lib/show"}})
        self.assertIsNone(parts.find(str(self.agent), "act"))
        self.assertIsNone(parts.find(str(self.agent), "hook/on_error"))     # 同一組裡沒寫的那個點
        self.assertIsNone(parts.find(str(self.agent), "endpoint/default"))

    def test_registered_but_broken_not_fallback(self):
        (self.agent / "queue").symlink_to(self.lib / "queue")                # 固定名字好好的
        self.reg({"queue": "../lib/nope"})
        self.assertEqual(parts.find(str(self.agent), "queue"), "%s/parts.json#/queue" % self.agent)   # 不退去找固定名字
        r = self.run_slot("queue")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-exec: "), r.stderr)        # 壞了 aos-exec 自己說

    def test_bad_registry(self):
        for text in ("not json", "[]"):
            (self.agent / "parts.json").write_text(text)
            with self.assertRaises(parts.Bad):
                parts.find(str(self.agent), "queue")
        self.reg({"hook": "../lib/show"})                                     # 路上不是物件
        with self.assertRaises(parts.Bad):
            parts.find(str(self.agent), "hook/pre_think")

    def test_nested_env_not_override_and_dotenv_override(self):
        self.reg({"endpoint": {"main": {".env": {"PART_K": "v1", "CODE": "3"}, "_entry": "../lib/show"}}})
        r = self.run_slot("endpoint/main", "a", "b c")
        self.assertEqual((r.returncode, r.stdout), (3, "v1|a b c\n"))       # .env key 帶上、結束碼是那格的
        r = self.run_slot("endpoint/main", env={"PART_K": "outer"})
        self.assertEqual(r.stdout, "outer|\n")                               # 環境裡已有的不蓋（N-58）
        r = self.run_slot("endpoint/main", env={"PART_K": "outer"}, flags=("--dotenv-override",))
        self.assertEqual(r.stdout, "v1|\n")                                  # 要蓋：那一跳加 --dotenv-override

    def test_env_directive(self):
        self.reg({"act": {".env": {"PART_K": {"$env": "PART_SRC"}}, "_entry": "../lib/show"}})
        r = self.run_slot("act", env={"PART_SRC": "secret"})
        self.assertEqual((r.returncode, r.stdout), (0, "secret|\n"), r.stderr)

    def test_endpoints_union(self):
        self.reg({"endpoint": {"default": "../lib/show", "litellm": "../lib/show"}})
        (self.agent / "endpoint" / "local").mkdir(parents=True)
        (self.agent / "endpoint" / ".hidden").mkdir()
        self.assertEqual(parts.endpoints(str(self.agent)), ["default", "litellm", "local"])
        (self.agent / "parts.json").unlink()
        self.assertEqual(parts.endpoints(str(self.agent)), ["local"])

    def test_cell_reports_parts_bad_and_part_missing(self):
        """真的格（lib/agent/queue 的 claim 要 history 格）：parts.json 壞＝queue: PartsBad；沒掛＝PartMissing、信留在 new/。"""
        queue = str(ROOT / "lib" / "agent" / "queue")
        env = dict(self.env, AOS_STACK=str(self.t / "stack") + "/")

        def q(*args, stdin=""):
            return subprocess.run([EXEC, queue, str(self.agent)] + list(args), input=stdin, capture_output=True,
                                  text=True, env=env, cwd=self.t, timeout=60)
        self.assertEqual(q("push", stdin='{"role": "user", "content": "hi"}').returncode, 0)
        for text, code in (("not json", "PartsBad"), ("{}", "PartMissing")):
            (self.agent / "parts.json").write_text(text)
            r = q("claim")
            self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["queue:", code]), r.stderr)
        self.assertEqual(len(os.listdir(self.t / "stack" / "queue" / "new")), 1)


if __name__ == "__main__":
    unittest.main()
