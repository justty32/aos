"""Test do_task start / end / status on a real history file: a fake aos-agent answers ctl who, its history half is the real aos_agent.history."""
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
PROTO = TOOL.parents[3]

# 假 aos-agent：ctl who＝bob；history＝真的 aos_agent.history，只把「哪隻、哪個檔」換成 FAKE_HISTORY（不要 daemon）
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
from types import SimpleNamespace
P = os.environ["FAKE_PROTO"]
sys.path[:0] = [P + "/cmd/aos-agent", P + "/py", P + "/lib"]
import aos_flags
from aos_agent import history
from aos_agent.common import Fail
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if sys.argv[1:3] == ["ctl", "who"]:
    print("bob")
    sys.exit(0)
if os.environ.get("FAKE_FAIL") and sys.argv[4:5] == [os.environ["FAKE_FAIL"]]:   # FAKE_FAIL_NTH＝log 裡第幾次這個子指令起才失敗（預設第 1 次）
    with open(os.environ["FAKE_LOG"]) as f:
        seen = sum(1 for l in f if json.loads(l)[3:4] == [os.environ["FAKE_FAIL"]])
    if seen >= int(os.environ.get("FAKE_FAIL_NTH", "1")):
        aos_flags.die("aos-agent", "WriteFailed", "cannot write the history (test)")
history.target = lambda opts: SimpleNamespace(name="bob", stack=os.path.dirname(os.environ["FAKE_HISTORY"]))
history.history_file = lambda a: os.environ["FAKE_HISTORY"]
try:
    history.cmd(sys.argv[2:])
except Fail as e:
    aos_flags.die("aos-agent", e.code, e)
'''


def call(cid, name, args):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def asks(cid, args, name="do_task"):
    return {"role": "assistant", "content": None, "tool_calls": [call(cid, name, args)]}


def said(cid, text):
    return {"role": "tool", "tool_call_id": cid, "content": text}


class DoTask(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="do-task-"))
        (self.tmp / "ws").mkdir()
        (self.tmp / "st").mkdir()
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        self.hist = self.tmp / "st" / "history.jsonl"
        self.cell = self.tmp / "st" / "tools" / "do_task"
        self.log = self.tmp / "log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]), AOS_WS=str(self.tmp / "ws"),
                        AOS_STACK=str(self.cell), FAKE_LOG=str(self.log), FAKE_HISTORY=str(self.hist),
                        FAKE_PROTO=str(PROTO), PYTHONDONTWRITEBYTECODE="1")
        self.write([{"role": "user", "content": "Go."}])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, msgs):
        self.hist.write_text("".join(json.dumps(m) + "\n" for m in msgs))

    def read(self):
        return [json.loads(l) for l in self.hist.read_text().splitlines() if l.strip()]

    def removed(self):
        p = self.tmp / "st" / "history_removed.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def step(self, cid, args, name="do_task"):
        """像 act 那樣：assistant 叫工具這則接進 history、跑工具、結果接進 history。回 (退出碼, stdout)。"""
        self.write(self.read() + [asks(cid, args, name)])
        return self.finish(cid, args)

    def finish(self, cid, args):
        r = self.run_tool(args)
        self.write(self.read() + [said(cid, r.stdout)])
        return r.returncode, r.stdout

    def run_tool(self, args, **env):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                              env=dict(self.env, **env), timeout=60)

    def other(self, cid, text="2026-11-11T10:00:00Z"):
        self.write(self.read() + [asks(cid, {}, "peek_now_time"), said(cid, text)])

    def test_start_work_end_folds_to_mark_and_summary(self):
        code, out = self.step("c1", {"op": "start", "task": "Find the time"})
        self.assertEqual(code, 0, out)
        self.assertIn("Task started (depth 1) \"Find the time\"", out)
        state = json.loads((self.cell / "tasks.json").read_text())
        self.assertEqual([t["call"] for t in state["tasks"]], ["c1"])
        self.other("c2")
        self.write(self.read() + [{"role": "assistant", "content": "Thinking out loud."}])   # 中間自己答了一句也摺
        self.other("c3")
        before = self.read()
        code, out = self.step("c4", {"op": "end", "summary": "It is 10:00."})
        self.assertEqual(code, 0, out)
        h = self.read()
        self.assertEqual(h[:3], before[:3])                        # Go.、紀錄點、start 的結果
        self.assertEqual(h[3], {"role": "user", "content": "[aos] summary: lines 4-8, 5 messages. Task \"Find the time\" ended: It is 10:00."})
        self.assertEqual(h[4]["tool_calls"][0]["id"], "c4")
        self.assertEqual(h[5]["tool_call_id"], "c4")
        self.assertEqual(len(h), 6)
        self.assertIn("5 messages (lines 4-8) are now one summary at line 4; the originals are in history_removed.jsonl in the stack of bob.", out)
        self.assertNotIn(str(self.tmp), json.dumps(self.read()))   # 11-12：結果行進 history（進 git），不帶絕對路徑
        self.assertEqual([r["message"] for r in self.removed()], before[3:8])   # 原文照舊留檔
        self.assertEqual(json.loads((self.cell / "tasks.json").read_text())["tasks"], [])

    def test_status(self):
        code, out = self.step("c1", {"op": "status"})
        self.assertEqual(code, 0, out)
        self.assertIn("Not in a task", out)
        self.assertFalse(self.cell.exists())                        # 只讀不建小格
        self.step("c2", {"op": "start", "task": "outer"})
        self.other("c3")
        code, out = self.step("c4", {"op": "status"})
        self.assertIn("In 1 task", out)
        self.assertIn("1. \"outer\" started ", out)
        self.assertIn("its start is line 4, 3 messages after it", out)

    def test_end_without_start(self):
        code, out = self.step("c1", {"op": "end", "summary": "x"})
        self.assertEqual(code, 1)
        self.assertIn("do_task: error: TaskMissing", out)

    def test_summary_required(self):
        self.step("c1", {"op": "start"})
        for args in ({"op": "end"}, {"op": "end", "summary": "  "}):
            code, out = self.step("c%d" % len(self.read()), args)
            self.assertEqual(code, 1)
            self.assertIn("do_task: error: ArgumentsBad summary is required", out)
        code, out = self.step("c9", {"op": "start", "summary": "x"})
        self.assertIn("ArgumentsBad op start does not take summary", out)
        code, out = self.step("c10", {"op": "fold"})
        self.assertIn("do_task: error: ", out)
        code, out = self.step("c11", {"op": "end", "summary": "s", "keep_others": "yes"})
        self.assertIn("do_task: error: ArgumentsBad keep_others must be boolean", out)
        code, out = self.step("c12", {"op": "start", "keep_others": True})
        self.assertIn("ArgumentsBad op start does not take keep_others", out)

    def test_same_call_again_is_not_a_second_start(self):
        self.write(self.read() + [asks("c1", {"op": "start", "task": "t"})])
        first = self.run_tool({"op": "start", "task": "t"})        # act 跑完、還沒接結果就斷了：重跑同一個 call
        second = self.run_tool({"op": "start", "task": "t"})
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(len(json.loads((self.cell / "tasks.json").read_text())["tasks"]), 1)

    def test_same_end_again_prints_the_same(self):
        self.step("c1", {"op": "start"})
        self.other("c2")
        self.write(self.read() + [asks("c3", {"op": "end", "summary": "s"})])
        first = self.run_tool({"op": "end", "summary": "s"})
        once = self.read()
        second = self.run_tool({"op": "end", "summary": "s"})
        self.assertEqual((first.returncode, second.returncode), (0, 0), second.stdout)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(self.read(), once)                        # 不再摺一次

    def test_folded_but_not_recorded_is_not_folded_again(self):
        self.step("c1", {"op": "start"})
        self.other("c2")
        self.write(self.read() + [asks("c3", {"op": "end", "summary": "s"})])
        self.assertEqual(self.run_tool({"op": "end", "summary": "s"}).returncode, 0)
        once = self.read()
        state = json.loads((self.cell / "tasks.json").read_text())   # 摺完、記上之前斷了：任務還開著、ended 沒寫
        state["tasks"] = [{"call": "c1", "started_at": "x"}]
        state.pop("ended")
        (self.cell / "tasks.json").write_text(json.dumps(state))
        r = self.run_tool({"op": "end", "summary": "s"})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Already folded", r.stdout)
        self.assertEqual(self.read(), once)

    def test_nested(self):
        self.step("c1", {"op": "start", "task": "outer"})
        self.other("c2")
        code, out = self.step("c3", {"op": "start", "task": "inner"})
        self.assertIn("Task started (depth 2) \"inner\" inside \"outer\"", out)
        self.other("c4")
        code, out = self.step("c5", {"op": "end", "summary": "inner done"})
        self.assertEqual(code, 0, out)
        self.assertIn("Task ended (depth 2) \"inner\"", out)
        self.assertIn("You are still in task (depth 1) \"outer\"", out)
        h = self.read()
        self.assertEqual(h[7]["content"], "[aos] summary: lines 8-9, 2 messages. Task \"inner\" ended: inner done")
        code, out = self.step("c6", {"op": "end", "summary": "outer done"})
        self.assertEqual(code, 0, out)
        h = self.read()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "user", "assistant", "tool"])
        self.assertTrue(h[3]["content"].endswith("Task \"outer\" ended: outer done"))
        self.assertIn("lines 4-10, 7 messages", h[3]["content"])    # 裡面那段的總結也一起摺
        code, out = self.step("c7", {"op": "end", "summary": "x"})
        self.assertIn("TaskMissing", out)

    def test_depth_limit(self):
        for i in range(5):
            self.assertEqual(self.step("s%d" % i, {"op": "start"})[0], 0)
        code, out = self.step("s5", {"op": "start"})
        self.assertEqual(code, 1)
        self.assertIn("do_task: error: DepthExceeded", out)

    LETTER = {"role": "user", "content": "From bob: the answer is 42."}
    GOAL = {"role": "user", "content": "[aos] goal: Write the report. (reminder 1 of 10. ...)"}

    def task_with_letters(self, **end):
        self.step("c1", {"op": "start", "task": "t"})
        self.other("c2")
        self.write(self.read() + [{"role": "assistant", "content": "Waiting for bob."}, self.LETTER])
        self.other("c3")
        self.write(self.read() + [{"role": "assistant", "content": "Hm."}, self.GOAL,
                                  {"role": "user", "content": "[aos] summary: lines 9-9, 1 message. old"}])   # 自己摺過的照摺
        self.other("c4")
        before = self.read()
        code, out = self.step("c5", dict({"op": "end", "summary": "bob said 42"}, **end))
        self.assertEqual(code, 0, out)
        return before, out

    def test_letters_during_the_task_are_folded_by_default(self):
        before, out = self.task_with_letters()                      # 使用者 11-11「可選。預設清掉。」
        h = self.read()
        self.assertEqual(h[3]["content"], "[aos] summary: lines 4-14, 11 messages. Task \"t\" ended: bob said 42")
        self.assertEqual([m["role"] for m in h[4:]], ["assistant", "tool"])
        self.assertNotIn(self.LETTER, h)
        self.assertIn("11 messages (lines 4-14) are now one summary at line 4", out)
        self.assertIn("2 of them came from others during the task (letters, reminders) and were folded too", out)
        self.assertEqual([r["message"] for r in self.removed()], before[3:14])   # 信的原文也留檔
        self.assertEqual({r["op"] for r in self.removed()}, {"summarize"})      # 沒有挪（set）

    def test_letters_during_the_task_stay_with_keep_others(self):
        letter, goal = self.LETTER, self.GOAL
        before, out = self.task_with_letters(keep_others=True)
        h = self.read()
        self.assertEqual(h[3]["content"], "[aos] summary: lines 4-12, 9 messages. Task \"t\" ended: bob said 42")
        self.assertEqual(h[4:6], [letter, goal])                    # 別人說的照原順序、接在總結後面
        self.assertEqual([m["role"] for m in h[6:]], ["assistant", "tool"])
        self.assertIn("2 messages from others during the task are kept after the summary", out)
        folded = [r["message"] for r in self.removed() if r["op"] == "summarize"]
        self.assertEqual(len(folded), 9)

    def letters_end_cut(self, **fail):
        """task_with_letters 那段，但叫 end 那次被砍在 fail 那一步（假 aos-agent 讓它失敗＝程序死在那裡）；act 再跑同一個 call。"""
        self.step("c1", {"op": "start", "task": "t"})
        self.other("c2")
        self.write(self.read() + [{"role": "assistant", "content": "Waiting for bob."}, self.LETTER])
        self.other("c3")
        self.write(self.read() + [{"role": "assistant", "content": "Hm."}, self.GOAL,
                                  {"role": "user", "content": "[aos] summary: lines 9-9, 1 message. old"}])
        self.other("c4")
        before = self.read()
        args = {"op": "end", "summary": "bob said 42", "keep_others": True}
        self.write(before + [asks("c5", args)])
        self.log.unlink()
        cut = self.run_tool(args, **fail)
        self.assertEqual(cut.returncode, 1, cut.stdout)
        state = (self.cell / "tasks.json").read_text()
        again = self.run_tool(args)
        self.assertEqual(again.returncode, 0, again.stdout)
        return before, state, again.stdout

    def assert_kept_once(self, before, out):
        h = self.read()
        self.assertEqual([m for m in h if m in (self.LETTER, self.GOAL)], [self.LETTER, self.GOAL])   # 各一次、不重複
        self.assertEqual(h[3]["content"], "[aos] summary: lines 4-12, 9 messages. Task \"t\" ended: bob said 42")
        self.assertEqual(h[4:6], [self.LETTER, self.GOAL])          # 照原順序接在總結後面
        self.assertEqual(len(h), 7)                                  # 總結、兩則、叫 end 那則
        self.assertIn("9 messages (lines 4-14) are now one summary at line 4", out)
        self.assertIn("2 messages from others during the task are kept after the summary", out)
        self.assertEqual([r["message"] for r in self.removed() if r["op"] == "set"], before[12:14])   # 被蓋掉的兩則各留一次
        self.assertEqual(len([r for r in self.removed() if r["op"] == "summarize"]), 9)
        self.assertEqual(json.loads((self.cell / "tasks.json").read_text())["tasks"], [])

    def test_keep_others_cut_before_summarize(self):
        before, _, out = self.letters_end_cut(FAKE_FAIL="summarize")   # 兩則都挪完、summarize 前死掉
        self.assert_kept_once(before, out)

    def test_keep_others_cut_between_moves(self):
        before, _, out = self.letters_end_cut(FAKE_FAIL="set", FAKE_FAIL_NTH="2")   # 第一則挪完、第二則前死掉
        self.assert_kept_once(before, out)

    def test_keep_others_cut_after_summarize(self):
        before, state, _ = self.letters_end_cut(FAKE_FAIL="summarize")
        once = self.read()
        (self.cell / "tasks.json").write_text(state)              # 摺完、記上之前死掉：小格還是 summarize 前那份
        r = self.run_tool({"op": "end", "summary": "bob said 42", "keep_others": True})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Already folded", r.stdout)
        self.assertEqual(self.read(), once)

    def test_restart_keeps_the_mark(self):
        self.step("c1", {"op": "start", "task": "long job"})
        self.other("c2")
        # agent 被停、再起來：工具是另一個行程，紀錄點只在小格的 tasks.json 與 history 裡
        code, out = self.step("c3", {"op": "status"})
        self.assertIn("1. \"long job\" started", out)
        code, out = self.step("c4", {"op": "end", "summary": "done"})
        self.assertEqual(code, 0, out)

    def test_mark_gone(self):
        self.step("c1", {"op": "start", "task": "t"})
        self.other("c2")
        self.write([m for m in self.read() if not (m.get("tool_calls") and m["tool_calls"][0]["id"] == "c1")])
        code, out = self.step("c3", {"op": "end", "summary": "s"})
        self.assertEqual(code, 1)
        self.assertIn("MarkerMissing", out)
        self.assertEqual(json.loads((self.cell / "tasks.json").read_text())["tasks"], [])

    def test_nothing_to_fold(self):
        self.write(self.read() + [{"role": "assistant", "content": None, "tool_calls": [
            call("c1", "do_task", {"op": "start"}), call("c2", "do_task", {"op": "end", "summary": "s"})]}])
        self.assertEqual(self.finish("c1", {"op": "start"})[0], 0)
        code, out = self.finish("c2", {"op": "end", "summary": "s"})
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing to fold", out)

    def test_eca_shaped_history(self):
        self.write([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}, {"role": "user", "content": "c"}])
        r = self.run_tool({"op": "start"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("do_task: error: BodyUnsupported do_task works only in an agent-fsm body", r.stdout)
        self.assertFalse(self.cell.exists())

    def test_lower_error_passes_through(self):
        self.step("c1", {"op": "start"})
        self.other("c2")
        self.write(self.read() + [asks("c3", {"op": "end", "summary": "s"})])
        r = self.run_tool({"op": "end", "summary": "s"}, FAKE_FAIL="summarize")
        self.assertEqual(r.returncode, 1)
        self.assertIn("do_task: error: WriteFailed cannot write the history (test)", r.stdout)
        self.assertEqual(len(json.loads((self.cell / "tasks.json").read_text())["tasks"]), 1)   # 沒摺成＝任務照開

    def test_state_errors_name_the_cell_not_the_machine(self):
        """11-12 線 errpath：錯誤行會接進 history（進 git），狀態檔寫相對 $AOS_STACK、不帶 OSError 的絕對檔名。"""
        self.cell.mkdir(parents=True)
        (self.cell / "tasks.json").write_text("{broken")
        self.write(self.read() + [asks("c0", {"op": "status"})])
        r = self.run_tool({"op": "status"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("do_task: error: StateBad cannot read $AOS_STACK/tasks.json: "), r.stdout)
        self.assertNotIn(str(self.tmp), r.stdout + r.stderr)
        if os.geteuid() == 0:
            return
        (self.cell / "tasks.json").unlink()
        self.cell.chmod(0o500)
        try:
            self.write(self.read() + [asks("c1", {"op": "start"})])
            r = self.run_tool({"op": "start"})
        finally:
            self.cell.chmod(0o700)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "do_task: error: WriteFailed cannot write $AOS_STACK/tasks.json: Permission denied")
        self.assertNotIn(str(self.tmp), r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
