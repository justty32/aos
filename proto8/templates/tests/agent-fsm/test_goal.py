"""agent-fsm 的 goal（11-11 goal/02）：idle 格單跑（停下被丟、done 後不丟、上限停、pause／resume、信優先、外面設／清、有叫工具歸零、
history 空時當開場題目、do_task 摺過也算進展、提醒找不到時以 summary 為界）＋真 aos-fsm 一步一步走、真 llm kernel＋假腦劇本實跑兩條。"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[2] / "agent-fsm"   # 範本本身
PROTO = CELLS.parents[1]
GOAL_TOOL = PROTO / "py" / "tools" / "agent" / "goal"
NOTE = "[aos] goal: "
_spec = importlib.util.spec_from_file_location("goal_state", PROTO / "py" / "aos" / "agentlib" / "goal_state.py")
goal_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(goal_state)


def answer(text):
    return {"role": "assistant", "content": text}


def called(name, args=None, cid="c1"):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args or {})}}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="aos-goal-fsm-")))
        if not os.environ.get("KEEP"):
            self.addCleanup(shutil.rmtree, self.root, True)
        self.defn, self.d, self.ws, self.kernel = (self.root / n for n in ("def", "d", "ws", "kernel"))
        shutil.copytree(CELLS, self.defn, ignore=shutil.ignore_patterns("__pycache__"))
        (self.defn / "hookeds.json").write_text('{}')         # 不要範本的 on_clock 鉤子攪局
        (self.defn / "llm.json").write_text('{"model": "fake"}')
        (self.defn / "tools.json").write_text(json.dumps({"tools": {
            "peek_now_time": {"path": str(PROTO / "py/tools/base/peek_now_time")}, "goal": {"path": str(GOAL_TOOL)}}}))
        for x in (self.ws, self.kernel):
            x.mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps(
            {"procs": {"bob": {"phase": "running", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(PROTO / "bin")]
        self.env = dict(env, PATH=os.pathsep.join(bins + [env["PATH"]]), AOS_HOME=str(PROTO),
                        PYTHONPATH=os.pathsep.join([str(PROTO / "py")]), PYTHONDONTWRITEBYTECODE="1",
                        AOS_STACK=str(self.stack), AOS_CD=str(self.defn), AOS_WS=str(self.ws), AOS_DAEMON=str(self.d),
                        AOS_LLM_KERNEL=str(self.kernel))
        self.hist = self.stack / "history.jsonl"

    # ---- 小工具
    def write_history(self, *rows):
        self.hist.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def add(self, *rows):
        with self.hist.open("a") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))

    def history(self):
        return [json.loads(l) for l in self.hist.read_text().splitlines() if l.strip()] if self.hist.exists() else []

    def notes(self):
        return [m["content"] for m in self.history() if m.get("role") == "user" and str(m.get("content")).startswith(NOTE)]

    def idle(self, code, *args):
        r = subprocess.run([sys.executable, str(self.defn / "idle.py"), *args], env=self.env, capture_output=True, text=True,
                           timeout=30)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def goal(self, *args):
        """外面（人、父 agent）：aos-agent goal。"""
        r = subprocess.run(["aos-agent", "-d", str(self.d), "goal", "-t", "bob", *args], env=dict(self.env, AOS_STACK=""),
                           capture_output=True, text=True, timeout=60, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def tool(self, args):
        """bob 自己的 goal 工具（同腦叫：aos-exec 起、$AOS_STACK＝它的工具小格）。"""
        cell = self.stack / "tools" / "goal"
        r = subprocess.run(["aos-exec", "--stack", str(cell) + "/", str(GOAL_TOOL)], input=json.dumps(args), env=self.env,
                           capture_output=True, text=True, timeout=60, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def rec(self):
        return json.loads((self.stack / "goal.json").read_text())

    def say(self, text):
        box = self.stack / "queue"
        if not box.exists():
            subprocess.run(["aos-post", "init", str(box)], env=self.env, check=True, capture_output=True)
        return subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], input=json.dumps({"role": "user", "content": text}),
                              env=self.env, check=True, capture_output=True, text=True).stdout.strip()   # 信名（回答配對的 aos.letter）


class IdleCell(Base):
    def test_stop_remind_then_done(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.idle(10)                                                  # no goal: nothing
        self.tool({"op": "set", "text": "Write the report."})
        self.assertEqual(self.rec()["set_by"], "agent")
        self.idle(0)
        self.assertEqual(self.notes(), ["[aos] goal: Write the report. (reminder 1 of 10. Keep working on it; when it is finished "
                                        "call the goal tool with op done; if you are waiting for someone, op pause.)"])
        self.idle(10)                                                  # last message is the reminder (a user), not a stop
        self.add(answer("I will."))
        self.idle(0)
        self.assertIn("(reminder 2 of 10.", self.notes()[-1])
        self.add(answer("Finished."))
        self.tool({"op": "done", "reason": "the report is written"})
        self.idle(10)
        self.assertEqual(len(self.notes()), 2)
        self.assertEqual((self.rec()["status"], self.rec()["reason"]), ("done", "the report is written"))

    def test_limit_pauses(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.goal("set", "--limit", "2", "Keep going.")
        for _ in range(3):
            self.idle(0)
            self.add(answer("ok"))
        self.idle(10)
        n = self.notes()
        self.assertEqual(len(n), 3)
        self.assertIn("(reminder 2 of 2.", n[1])
        self.assertEqual(n[2], "[aos] goal: reminder limit 2 reached; goal paused (op resume to go on). Goal: Keep going.")
        r = self.rec()
        self.assertEqual((r["status"], r["updated_by"], r["reminded"]), ("paused", "aos", 2))
        self.assertIn("limit 2 reached", r["reason"])
        self.goal("resume")                                            # resume starts the count again
        self.idle(0)
        self.assertIn("(reminder 1 of 2.", self.notes()[-1])

    def test_pause_letter_does_not_resume_then_resume(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.goal("set", "Fix the bug.")
        self.tool({"op": "pause", "reason": "waiting for amy"})
        self.idle(10)
        self.say("amy: here is the log")                              # a letter comes: taken as usual, the goal stays paused
        self.idle(0)
        self.assertEqual(self.history()[-1]["content"], "amy: here is the log")
        self.add(answer("Thanks."))
        self.idle(10)
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.rec()["status"], "paused")
        self.tool({"op": "resume"})
        self.idle(0)
        self.assertIn("(reminder 1 of 10.", self.notes()[-1])

    def pause_with_history(self):
        self.goal("set", "Fix the bug.")
        self.tool({"op": "pause", "reason": "waiting for amy"})
        self.set_reminded(2)
        self.write_history({"role": "user", "content": "Fix the bug."},
                           called("goal", {"op": "pause", "reason": "waiting for amy"}),
                           {"role": "tool", "tool_call_id": "c1", "content": "status\tpaused"},
                           answer("I am waiting for amy."))

    def test_agent_pause_letter_gets_one_note_without_changing_goal(self):
        self.pause_with_history()
        before = (self.stack / "goal.json").read_bytes()
        self.say("amy: here is the log")
        self.idle(0)
        self.assertEqual(self.history()[-1]["content"], "amy: here is the log")
        self.assertEqual(self.notes(), [])
        self.add(answer("Thanks."))
        self.idle(0)
        note = goal_state.paused_note(self.rec())
        self.assertEqual(self.history()[-1], {"role": "user", "content": note})   # 不經 queue 的提示不帶 aos 鍵（整列相等也斷言了這點）
        self.assertEqual(self.notes(), [note])
        self.assertEqual((self.rec()["status"], self.rec()["reminded"]), ("paused", 2))
        self.assertEqual((self.stack / "goal.json").read_bytes(), before)
        self.add(answer("I am still waiting."))
        self.idle(10)
        self.say("amy: one more log")
        self.idle(0)
        self.add(answer("Thanks again."))
        self.idle(10)
        self.assertEqual(self.notes(), [note])
        self.assertEqual((self.stack / "goal.json").read_bytes(), before)

    def test_pause_by_outside_or_aos_gets_no_note(self):
        for by in ("outside", "aos"):
            with self.subTest(updated_by=by):
                self.pause_with_history()
                r = dict(self.rec(), updated_by=by)
                (self.stack / "goal.json").write_text(json.dumps(r))
                before = (self.stack / "goal.json").read_bytes()
                self.say("amy: here is the log")
                self.idle(0)
                self.add(answer("Thanks."))
                self.idle(10)
                self.assertEqual(self.notes(), [])
                self.assertEqual((self.stack / "goal.json").read_bytes(), before)

    def test_agent_pause_without_later_message_gets_no_note(self):
        self.pause_with_history()
        self.idle(10)
        self.assertEqual(self.notes(), [])

    def test_resume_after_paused_note_gets_normal_reminder(self):
        self.pause_with_history()
        self.say("amy: here is the log")
        self.idle(0)
        self.add(answer("Thanks."))
        self.idle(0)
        self.assertIn("paused (waiting for amy).", self.notes()[-1])
        self.add(called("goal", {"op": "resume"}, "c2"))
        self.tool({"op": "resume"})
        self.add({"role": "tool", "tool_call_id": "c2", "content": "status\tactive"}, answer("I can go on."))
        self.idle(0)
        self.assertEqual(len(self.notes()), 2)
        self.assertIn("(reminder 1 of 10.", self.notes()[-1])
        self.assertEqual(self.rec()["status"], "active")

    def test_paused_tail_discards_partial_line_and_ignores_older_bad_json(self):
        self.pause_with_history()
        self.add({"role": "user", "content": "amy: here is the log"}, answer("Thanks."))
        tail = self.hist.read_bytes()
        self.hist.write_bytes(b"not JSON\n" + b"x" * 262144 + b"\n" + tail)
        self.idle(0)
        last = json.loads(self.hist.read_bytes().splitlines()[-1])
        self.assertEqual(last, {"role": "user", "content": goal_state.paused_note(self.rec())})

    def test_paused_tail_bad_json_gets_no_note(self):
        self.pause_with_history()
        self.add({"role": "user", "content": "amy: here is the log"})
        with self.hist.open("a") as f:
            f.write("not JSON\n")
        self.add(answer("Thanks."))
        before = self.hist.read_bytes()
        self.idle(10)
        self.assertEqual(self.hist.read_bytes(), before)

    def test_paused_tail_without_goal_call_gets_no_note(self):
        self.pause_with_history()
        self.add({"role": "user", "content": "x" * 262144}, answer("Thanks."))
        before = self.hist.read_bytes()
        self.idle(10)
        self.assertEqual(self.hist.read_bytes(), before)

    def test_letters_come_first(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.goal("set", "Fix the bug.")
        name = self.say("a new letter")
        self.idle(0)
        self.assertEqual(self.history()[-1], {"role": "user", "content": "a new letter", "aos": {"letter": name}})
        self.assertEqual((self.notes(), self.rec()["reminded"]), ([], 0))

    def test_outside_set_and_clear(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.assertIn("set the goal of bob: Ship it.", self.goal("set", "Ship", "it."))
        self.assertEqual(self.rec()["set_by"], "outside")
        self.assertIn("status\tactive", self.tool({"op": "get"}))
        self.idle(0)
        self.add(answer("ok"))
        self.goal("clear", "-y")
        self.idle(10)
        self.assertEqual(len(self.notes()), 1)
        self.assertIn("no goal", self.tool({"op": "get"}))

    def test_tool_call_resets_the_count(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        self.goal("set", "--limit", "3", "Do work.")
        self.idle(0)
        self.add(answer("thinking"))
        self.idle(0)
        self.assertIn("(reminder 2 of 3.", self.notes()[-1])
        self.add(called("peek_now_time"), {"role": "tool", "tool_call_id": "c1", "content": "12:00"}, answer("did a step"))
        self.idle(0)
        self.assertIn("(reminder 1 of 3.", self.notes()[-1])          # progress: back to 1
        self.add(called("goal", {"op": "get"}, "c2"), {"role": "tool", "tool_call_id": "c2", "content": "status\tactive"},
                 answer("still here"))
        self.idle(0)
        self.assertIn("(reminder 2 of 3.", self.notes()[-1])          # calling goal itself is no progress

    def test_empty_history_gets_the_goal_as_opening(self):
        # 11-11 稍後使用者「也丟，當開場題目」：還沒答過任何一輪、外面先 set 了 goal＝它就是第一則
        self.goal("set", "Write the report.")
        self.assertFalse(self.hist.exists())
        self.idle(0)
        self.assertEqual(len(self.history()), 1)
        self.assertTrue(self.history()[0]["content"].startswith("[aos] goal: Write the report. (reminder 1 of 10."))
        self.assertEqual(self.rec()["reminded"], 1)
        self.idle(10)                                                  # the reminder waits for the brain: not again

    def test_opening_prompt_comes_before_the_goal(self):
        (self.defn / "prompt.txt").write_text("Start here.\n")
        self.goal("set", "Write the report.")
        self.idle(0, "--prompt", "prompt.txt")
        opening = json.loads((self.stack / "letters.json").read_text())["pending"]   # 開場白也走 queue：一樣帶 aos.letter、記進 pending
        self.assertEqual(len(opening), 1)
        self.assertRegex(opening[0], r"^[0-9]{12}\.")                          # 有序信的名字（aos-post send --ordered）
        self.assertEqual(self.history(), [{"role": "user", "content": "Start here.", "aos": {"letter": opening[0]}}])
        self.assertEqual(self.rec()["reminded"], 0)

    def set_reminded(self, n):
        r = self.rec()
        r["reminded"] = n
        (self.stack / "goal.json").write_text(json.dumps(r))

    def test_do_task_fold_counts_as_progress(self):
        # 11-11 稍後使用者「算。兩者不要耦合太深，就goal那邊稍微檢查一下history就好。」：do_task end 把提醒一起摺掉，
        # 留下的 [aos] summary: 與 end 那則照樣算到（goal 不認識 do_task：end 只是 goal 以外的一支工具）
        self.goal("set", "--limit", "3", "Do work.")
        self.set_reminded(2)
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."),
                           called("do_task", {"op": "start", "task": "the work"}, "c1"), {"role": "tool", "tool_call_id": "c1", "content": "started"},
                           {"role": "user", "content": "[aos] summary: lines 5-9, 5 messages. Task \"the work\" ended: done"},
                           called("do_task", {"op": "end", "summary": "done"}, "c9"), {"role": "tool", "tool_call_id": "c9", "content": "ended"},
                           answer("The work is done."))
        self.idle(0)
        self.assertIn("(reminder 1 of 3.", self.notes()[-1])

    def test_lost_reminder_without_progress(self):
        # 提醒找不到：以最近一則 [aos] summary: 為界，界線後沒叫工具＝不歸零；連 summary 都沒有＝不歸零（代定）
        self.goal("set", "--limit", "5", "Do work.")
        self.set_reminded(2)
        self.write_history({"role": "user", "content": "hi"}, called("peek_now_time"), {"role": "tool", "tool_call_id": "c1", "content": "12:00"},
                           {"role": "user", "content": "[aos] summary: lines 4-7, 4 messages. talked"}, answer("ok"))
        self.idle(0)
        self.assertIn("(reminder 3 of 5.", self.notes()[-1])
        self.set_reminded(2)
        self.write_history({"role": "user", "content": "hi"}, called("peek_now_time"), {"role": "tool", "tool_call_id": "c1", "content": "12:00"},
                           answer("ok"))
        self.idle(0)
        self.assertIn("(reminder 3 of 5.", self.notes()[-1])

    def test_bad_goal_file_is_quiet(self):
        self.write_history({"role": "user", "content": "hi"}, answer("Hello."))
        (self.stack / "goal.json").write_text("{nope")
        r = self.idle(10)
        self.assertEqual(r.stderr, "")


class PausedDue(unittest.TestCase):
    def setUp(self):
        self.rec = dict(goal_state.new("Fix the bug.", 10, "agent"), status="paused", reason="waiting for amy")
        self.pause = called("goal", {"op": "pause", "reason": "waiting for amy"})
        self.message = {"role": "user", "content": "amy: here is the log"}

    def test_summary_before_any_goal_call_is_a_boundary(self):
        history = [self.pause, {"role": "user", "content": "[aos] summary: earlier work"},
                   self.message, answer("Thanks.")]
        self.assertFalse(goal_state.paused_due(self.rec, history))
        self.assertFalse(goal_state.paused_due(self.rec, history[1:]))

    def test_new_mail_notice_counts_as_a_message(self):
        history = [self.pause, {"role": "user", "content": "[aos] new_mail: 1 new letter from amy."}, answer("Thanks.")]
        self.assertTrue(goal_state.paused_due(self.rec, history))

    def test_reminder_stops_another_paused_note(self):
        for content in (goal_state.paused_note(self.rec), NOTE + "an earlier reminder"):
            with self.subTest(content=content):
                history = [self.pause, {"role": "user", "content": content}, self.message, answer("Thanks.")]
                self.assertFalse(goal_state.paused_due(self.rec, history))

    def test_only_messages_after_the_nearest_goal_call_count(self):
        self.assertFalse(goal_state.paused_due(self.rec, [self.message, self.pause, answer("Waiting.")]))
        self.assertFalse(goal_state.paused_due(self.rec, [self.pause, self.message, called("goal"), answer("Waiting.")]))
        self.assertFalse(goal_state.paused_due(self.rec, [self.message, answer("Thanks.")]))

    def test_requires_agent_pause_and_stopped_history(self):
        history = [self.pause, self.message, answer("Thanks.")]
        for rec in (None, dict(self.rec, status="active"), dict(self.rec, updated_by="outside"),
                    dict(self.rec, updated_by="aos"), {"status": "paused"}):
            with self.subTest(rec=rec):
                self.assertFalse(goal_state.paused_due(rec, history))
        for history in ([], [self.pause, self.message], [self.pause, self.message, called("peek_now_time")]):
            with self.subTest(history=history):
                self.assertFalse(goal_state.paused_due(self.rec, history))

    def test_goal_tool_names_and_unrelated_calls(self):
        for name in ("goal", "mcp__aos__goal", "aos.goal"):
            with self.subTest(name=name):
                history = [called(name), called("peek_now_time"), self.message, answer("Thanks.")]
                self.assertTrue(goal_state.paused_due(self.rec, history))
        self.assertFalse(goal_state.paused_due(self.rec, [called("not_goal"), self.message, answer("Thanks.")]))

    def test_paused_note_reason_fallback_and_prefix(self):
        for reason in (None, ""):
            rec = dict(self.rec)
            if reason is None:
                rec.pop("reason")
            else:
                rec["reason"] = reason
            note = goal_state.paused_note(rec)
            self.assertEqual(note, NOTE + "paused (no reason given). A message came after you paused. If you can go on, "
                             "call the goal tool with op resume; if the goal is finished, op done; "
                             "if you are still waiting, just say so. Goal: Fix the bug.")
            self.assertTrue(goal_state.is_reminder({"role": "user", "content": note}))


class FakeBrainRun(Base):
    """真 aos-fsm 一步一步走四格，腦＝真 llm kernel＋llm_fake 劇本。"""

    def kernel_up(self, endpoint):
        (self.root / "kernel.json").write_text(json.dumps({"exec": str(PROTO / "py/tools/base/llm_fake"), "endpoint": "fake",
                                                           "endpoints": {"fake": endpoint}}))
        (self.root / "kernel_daemon.json").write_text(json.dumps({"interval_ms": 10, "exec": {"argv": [
            str(PROTO / "py/tools/aos/kernel_llm/_entry"), str(self.root / "kernel.json")]}}))
        log = open(self.root / "kernel.log", "w")
        self.addCleanup(log.close)
        p = subprocess.Popen(["aos-daemon", str(self.root / "kernel_daemon.json")], cwd=self.root,
                             env=dict(self.env, AOS_STACK=str(self.kernel)), stdout=log, stderr=log, start_new_session=True)

        def down():
            (self.kernel / "ctl.json").write_text('{"cmd":"stop","seq":1}')
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        self.addCleanup(down)

    def run_until_idle(self, max_steps=200):
        """走到 idle 連三拍沒事（idle 退 10、history 不長）為止。"""
        quiet, before = 0, None
        for _ in range(max_steps):
            stage = (self.stack / "stage.txt").read_text().strip() if (self.stack / "stage.txt").exists() else "idle"
            r = subprocess.run(["aos-fsm", str(self.defn / "fsm.json")], env=self.env, capture_output=True, text=True, timeout=120,
                               cwd=self.defn)
            self.assertEqual(r.returncode, 0, r.stderr)
            now = self.hist.read_text() if self.hist.exists() else ""
            quiet = quiet + 1 if stage == "idle" and now == before else 0
            before = now
            if quiet >= 3:
                return
            if stage == "wait":
                time.sleep(0.02)
        self.fail("did not settle; history: %s" % self.history())

    def test_stop_remind_progress_done(self):
        self.kernel_up({"script": [
            {"content": "Hello."},                                                        # stops: reminder 1
            {"tool_calls": [{"name": "peek_now_time"}]},                                  # progress
            {"content": "Did one step."},                                                 # stops: reminder 1 again
            {"tool_calls": [{"name": "goal", "arguments": {"op": "done", "reason": "all steps done"}}]},
            {"content": "Done."}]})
        self.say("hi")
        self.goal("set", "--limit", "3", "Finish the job.")
        self.run_until_idle()
        notes = self.notes()
        self.assertEqual(len(notes), 2, self.history())
        self.assertTrue(all("(reminder 1 of 3." in n for n in notes), notes)
        r = self.rec()
        self.assertEqual((r["status"], r["reason"], r["set_by"], r["updated_by"]), ("done", "all steps done", "outside", "agent"))
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "Done."})

    def test_limit_with_a_brain_that_only_talks(self):
        (self.defn / "tools.json").write_text('{"tools": {}}')                              # no tools: the fake brain only answers
        self.kernel_up({})
        self.say("hi")
        self.goal("set", "--limit", "2", "Keep going.")
        self.run_until_idle()
        notes = self.notes()
        self.assertEqual(len(notes), 3, self.history())
        self.assertTrue(notes[2].startswith("[aos] goal: reminder limit 2 reached; goal paused"), notes)
        self.assertEqual(self.rec()["status"], "paused")
        self.assertEqual(self.history()[-1]["role"], "assistant")                         # the brain saw the limit note too


if __name__ == "__main__":
    unittest.main()
