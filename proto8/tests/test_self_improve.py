"""test_self_improve - 跑 demo/self-improve（自我改進流程：run → judge → improve，外面 aos-loop 包著）。

改進者（demo/self-improve/improver，一隻 agent）的腦用 test_dan 的假 server 照劇本回；工具 read／write／edit 掛 proto8/lib/base 的、try_run 是自己的。
看：達成就收工（0）、預算用完退 2、改壞了從最好的那版重來、每一版都留著、原版不動、判準改進者看不到、target/ 以外寫的不採用、
改進者失敗停住再跑接著做、判準是檢查程式、函數是單檔 JSON。不連真模型。設計：proto8/thinking/2026-10-24-self-improve.md。"""
import json, os, re, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_dan import FakeBrain, call, answer  # noqa: E402

EXEC = tool("aos-exec")
SELF = str(ROOT / "demo" / "self-improve")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
CODES = ("BudgetSpent", "ImproverFailed", "WsMissing", "StackMissing", "StackBad", "TargetMissing",
         "JudgeMissing", "JudgeBad", "BudgetBad", "LaunchFailed")

BUGGY = "import sys\nn = int(sys.argv[1])\nprint(sys.stdin.read()[:n], end='')\n"                 # 沒轉大寫、沒預設：0/3
HALF = "import sys\nn = int(sys.argv[1])\nprint(sys.stdin.read().upper()[:n], end='')\n"          # 只轉大寫：2/3
GOOD = "import sys\nn = int(sys.argv[1]) if len(sys.argv) > 1 else 3\nprint(sys.stdin.read().upper()[:n], end='')\n"
BROKEN = "import sys\nn = int(sys.argv[1] if len(sys.argv) > 1 else 3\n"
CASES = [{"args": ["2"], "stdin": "abc", "stdout": "AB"},
         {"args": [], "stdin": "hello", "stdout": "HEL"},
         {"args": ["4"], "stdin": "secret", "stdout": "SECR", "hidden": True}]


def tool_reply(*calls, tokens=None):
    r = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}]}
    if tokens:
        r["usage"] = {"prompt_tokens": tokens, "completion_tokens": 0, "total_tokens": tokens}
    return r


def write(path, content, cid="w"):
    return tool_reply(call(cid, "write", {"path": path, "content": content}))


def errors(stderr):
    """stderr 裡 self-improve 的每一行都要是「self-improve: 代號 原因」，代號在表上；回代號清單。"""
    found = []
    for line in stderr.splitlines():
        if line.startswith("self-improve:"):
            m = re.match(r"self-improve: ([A-Z][A-Za-z]+) \S", line)
            assert m and m.group(1) in CODES, "self-improve 的錯誤行格式不對：%r" % line
            found.append(m.group(1))
    return found


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        self.stack = self.ws / ".stack"
        self.put("goal.txt", "印出 stdin 的前 N 個字元、轉大寫；N 是第一個參數，沒給就是 3。")
        self.put("target/_entry", json.dumps({"argv": ["python3", "f.py"]}))
        self.put("target/f.py", BUGGY)
        self.put("judge/cases.json", json.dumps(CASES))

    def put(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def brain(self, *script):
        b = FakeBrain(script)
        self.addCleanup(b.close)
        return b

    def improve(self, brain=None, timeout=120):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with(e.get("PATH", ""))
        if brain:
            e["AOS_BRAIN_URL"] = brain.url
        r = subprocess.run([EXEC, "--ws", str(self.ws), SELF], capture_output=True, text=True, env=e, timeout=timeout)
        r.codes = errors(r.stderr)
        return r

    def version(self, v):
        return json.loads((self.stack / "versions" / v / "version.json").read_text())

    def verdict(self, v):
        return json.loads((self.stack / "versions" / v / "verdict.json").read_text())

    def states(self):
        return [(json.loads(l)["state"], json.loads(l)["code"]) for l in (self.stack / "trace.jsonl").read_text().splitlines()]

    def result(self):
        return json.loads((self.ws / "out" / "result.json").read_text())

    def test_improves_until_passed(self):
        b = self.brain(tool_reply(call("r", "read", {"path": "target/f.py"})),
                       write("target/f.py", GOOD),
                       tool_reply(call("t", "try_run", {"args": [], "stdin": "hello"})),
                       answer("補上 N 的預設值 3。"))
        r = self.improve(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.states(), [("run", 0), ("judge", 0), ("improve", 0), ("run", 0), ("judge", 10)])
        self.assertEqual((self.verdict("v000")["score"], self.verdict("v001")["score"]), (0, 3))
        self.assertTrue(self.verdict("v001")["passed"])
        self.assertEqual(self.version("v001")["from"], "v000")
        self.assertEqual((self.ws / "target" / "f.py").read_text(), BUGGY)                 # 原版不動
        self.assertEqual((self.stack / "versions" / "v000" / "target" / "f.py").read_text(), BUGGY)   # 每一版都留著
        self.assertEqual((self.ws / "out" / "best" / "target" / "f.py").read_text(), GOOD)
        self.assertEqual(self.result()["best"], "v001")
        self.assertIn("+n = int(sys.argv[1]) if len(sys.argv) > 1 else 3",
                      (self.stack / "versions" / "v001" / "diff.txt").read_text())
        self.assertIn("補上 N 的預設值", (self.ws / "out" / "report.txt").read_text())
        tried = [m for m in b.requests[-1]["messages"] if m["role"] == "tool"][-1]["content"]
        self.assertIn("結束碼 0\n--- stdout ---\nHEL", tried)                             # try_run 跑的是改過的那份

    def test_task_hides_hidden_cases_and_judge(self):
        b = self.brain(tool_reply(call("r", "read", {"path": "../../../../../judge/cases.json"})),
                       answer("看不到。"))
        self.put("budget.json", json.dumps({"rounds": 1}))
        r = self.improve(b)
        self.assertEqual(r.returncode, 2, r.stderr)
        task = b.requests[0]["messages"][1]["content"]
        self.assertIn("另有 1 組看不到的例子沒過", task)
        self.assertIn("|abc", task)                         # 看得到的例子照給
        self.assertNotIn("secret", task.lower())            # 藏起來的不給
        self.assertNotIn("judge", task)
        said = [m for m in b.requests[1]["messages"] if m["role"] == "tool"][0]["content"]
        self.assertIn("read: PathBad", said)                # 判準在改進者的工作資料夾外面，讀不到

    def test_starts_from_best_after_regression(self):
        b = self.brain(write("target/f.py", HALF), answer("半套。"),
                       write("target/f.py", BROKEN), answer("改壞了。"),
                       write("target/f.py", GOOD), answer("好了。"))
        r = self.improve(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        scores = [self.verdict(v)["score"] for v in ("v000", "v001", "v002", "v003")]
        self.assertEqual(scores, [0, 2, 0, 3])
        self.assertEqual([self.version(v)["from"] for v in ("v001", "v002", "v003")], ["v000", "v001", "v001"])
        task3 = b.requests[4]["messages"][1]["content"]
        self.assertIn("- v002：0/3", task3)
        self.assertIn("就是 v001 那一版", task3)                # v002 改壞了：從最好的 v001 重來

    def test_same_score_restarts_from_earliest_and_notes_repeats(self):
        b = self.brain(answer("沒改。"), answer("還是沒改。"))
        self.put("budget.json", json.dumps({"rounds": 2}))
        r = self.improve(b)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.codes, ["BudgetSpent"])
        self.assertEqual(self.version("v002")["from"], "v000")       # 同分取最早的
        self.assertEqual(self.version("v002")["same_as"], "v000")    # 繞回去了
        self.assertFalse(self.result()["passed"])
        self.assertIn("跟 v000 一模一樣", (self.ws / "out" / "report.txt").read_text())

    def test_budget_spent_then_more_budget_goes_on(self):
        self.put("budget.json", json.dumps({"rounds": 1}))
        b = self.brain(write("target/f.py", BROKEN), answer("壞的。"), write("target/f.py", GOOD), answer("好了。"))
        r = self.improve(b)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.codes, ["BudgetSpent"])
        self.assertIn("最好的一版 v000（0/3）", r.stderr)
        self.assertEqual((self.ws / "out" / "best" / "target" / "f.py").read_text(), BUGGY)   # 回到最好的那版
        r = self.improve(b)                                    # 沒加預算：還是停在 judge、一樣的話
        self.assertEqual((r.returncode, r.codes), (2, ["BudgetSpent"]))
        self.put("budget.json", json.dumps({"rounds": 3}))
        r = self.improve(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.version("v002")["from"], "v000")
        self.assertTrue(self.result()["passed"])

    def test_token_budget(self):
        self.put("budget.json", json.dumps({"tokens": 1000}))
        b = self.brain(tool_reply(call("r", "read", {"path": "target/f.py"}), tokens=600),
                       {"choices": [{"message": {"role": "assistant", "content": "不改。"}}],
                        "usage": {"total_tokens": 500}})
        r = self.improve(b)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("tokens 用完了", r.stderr)
        self.assertEqual(self.result()["used"]["tokens"], 1100)

    def test_only_target_is_taken(self):
        b = self.brain(tool_reply(call("a", "write", {"path": "notes.txt", "content": "x"}),
                                  call("b", "write", {"path": "target/extra.py", "content": "# extra\n"})),
                       answer("寫了兩個檔。"))
        self.put("budget.json", json.dumps({"rounds": 1}))
        self.improve(b)
        v1 = self.stack / "versions" / "v001"
        self.assertEqual(self.version("v001")["ignored"], ["notes.txt"])
        self.assertTrue((v1 / "target" / "extra.py").exists())
        self.assertFalse((v1 / "notes.txt").exists())
        self.assertEqual(sorted(p.name for p in (self.ws / "judge").iterdir()), ["cases.json"])
        self.assertIn("target/ 以外寫的東西沒採用：notes.txt", (self.ws / "out" / "report.txt").read_text())

    def test_improver_failed_stops_then_resumes(self):
        r = self.improve(self.brain((500, "壞了")))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(r.codes, ["ImproverFailed"])
        self.assertEqual((self.stack / "state.txt").read_text().strip(), "improve")
        r = self.improve(self.brain(write("target/f.py", GOOD), answer("好了。")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.stack / "failed" / "v001.1").is_dir())    # 半成品搬走、留著看
        self.assertEqual(self.result()["used"]["rounds"], 2)             # 失敗的那次也算一輪

    def test_check_program(self):
        (self.ws / "judge" / "cases.json").unlink()
        self.put("judge/check/_entry", json.dumps({"argv": ["python3", "check.py"]}))
        self.put("judge/check/check.py", (
            "import os, subprocess, sys\n"
            "out = subprocess.run(['aos-exec', os.environ['IMPROVE_TARGET']], input='hello', capture_output=True,"
            " text=True).stdout\n"
            "print('沒給 N 時拿到 %r' % out)\n"
            "sys.exit(0 if out == 'HEL' else 1)\n"))
        b = self.brain(write("target/f.py", GOOD), answer("好了。"))
        r = self.improve(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.verdict("v000")["score"], self.verdict("v001")["score"]), (0, 1))
        task = b.requests[0]["messages"][1]["content"]
        self.assertIn("一支檢查程式", task)
        self.assertIn("沒給 N 時拿到 ''", task)            # 檢查程式的 stdout 就是給改進者的回饋

    def test_single_file_target(self):
        (self.ws / "target" / "f.py").unlink()
        (self.ws / "target" / "_entry").unlink()
        (self.ws / "target").rmdir()
        self.put("target.json", json.dumps({"argv": ["printf", "ab"]}))
        self.put("judge/cases.json", json.dumps([{"stdout": "AB"}]))
        b = self.brain(write("target.json", json.dumps({"argv": ["printf", "AB"]})), answer("改成大寫。"))
        r = self.improve(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ws / "out" / "best" / "target.json").exists())
        self.assertIn("target.json", b.requests[0]["messages"][1]["content"])

    def test_own_errors(self):
        (self.ws / "judge" / "cases.json").unlink()
        r = self.improve()
        self.assertEqual((r.returncode, r.codes), (1, ["JudgeMissing"]))
        self.put("judge/cases.json", json.dumps([{"args": "x", "stdout": ""}]))
        r = self.improve()
        self.assertEqual((r.returncode, r.codes), (1, ["JudgeBad"]))


if __name__ == "__main__":
    unittest.main()
