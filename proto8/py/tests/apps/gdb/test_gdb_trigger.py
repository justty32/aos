"""aos.gdb.trigger 與 gdb_trigger handler（不起 daemon）：連續 N 次與歸零、once、tools 篩法、sh 的 0／10／其他、py 函式與運算式的打包與拒收、tool_error、字條從 resume 之後算；handler 用假的 aos-agent 跑：pause 型發 pause、留字條；hold 型扣住等放行（放行退 0、什麼都不印；shell 的 ctl resume 也放行；被 TERM 留 hold_ended 且同一次再來時直接再扣住；放行過的同一次再來不再扣）；條件壞了只 warning 退 0；介面長相（a.bp、resume／step／stop 不收參數、沒有 skip 與 wait_stopped、說明字串）。"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "py"))
from aos.gdb import trigger  # noqa: E402

ENTRY = PROTO / "py" / "tools" / "agent" / "gdb_trigger" / "_entry"


def spec(**kw):
    s = {"kind": "always", "event": "before_tool", "tools": None, "times": 1, "once": False, "agent": "ann", "daemon": None}
    s.update(kw)
    s.setdefault("how", trigger.how(s["event"]))
    trigger.validate(s)
    return s


def run_steps(s, events):
    count, fired = {}, []
    for ev in events:
        count, hit, _ = trigger.step(s, count, ev)
        fired.append(hit)
    return count, fired


class Steps(unittest.TestCase):
    def test_times_in_a_row_and_reset(self):
        s = spec(kind="tool_error", event="after_tool", times=3)
        bad, ok = {"name": "math", "code": 1}, {"name": "math", "code": 0}
        count, fired = run_steps(s, [bad, bad, ok, bad, bad, bad, bad])
        self.assertEqual(fired, [False, False, False, False, False, True, False])
        self.assertEqual(count["streak"], 1)      # 停了就歸零，之後重新數
        self.assertEqual(count["fired"], 1)

    def test_other_tools_break_the_streak(self):
        s = spec(tools=["write"], times=2)
        count, fired = run_steps(s, [{"name": "write"}, {"name": "read"}, {"name": "write"}, {"name": "write"}])
        self.assertEqual(fired, [False, False, False, True])

    def test_once(self):
        s = spec(once=True)
        count, fired = run_steps(s, [{"name": "a"}, {"name": "a"}, {"name": "a"}])
        self.assertEqual(fired, [True, False, False])
        self.assertEqual(count["seen"], 1)

    def test_tool_error(self):
        s = spec(kind="tool_error", event="after_tool")
        self.assertTrue(trigger.check(s, {"code": 1}))
        self.assertTrue(trigger.check(s, {"code": None, "timed_out": True}))
        self.assertFalse(trigger.check(s, {"code": 0}))
        with self.assertRaises(trigger.Bad):
            spec(kind="tool_error", event="before_tool")

    def test_how_follows_the_event(self):
        self.assertEqual([trigger.how(e) for e in ("before_tool", "before_queue", "after_tool", "brain_failed")],
                         ["hold", "hold", "pause", "pause"])
        with self.assertRaises(trigger.Bad):
            spec(how="pause")                    # before_tool 不能選 pause：一個名字一種意思

    def test_sh(self):
        self.assertTrue(trigger.check(spec(kind="sh", sh="echo noise; grep -q write"), {"name": "write"}))
        self.assertFalse(trigger.check(spec(kind="sh", sh="exit 10"), {}))
        with self.assertRaises(trigger.Bad):
            trigger.check(spec(kind="sh", sh="exit 3"), {})
        count, hit, broken = trigger.step(spec(kind="sh", sh="exit 3"), {}, {})
        self.assertFalse(hit)
        self.assertIn("exited 3", broken)
        self.assertIn("exited 3", count["last_error"])


class Py(unittest.TestCase):
    def roundtrip(self, cond, event):
        return trigger.check(spec(kind="py", py=json.loads(json.dumps(trigger.pack_py(cond)))), event)

    def test_lambda_and_def(self):
        self.assertTrue(self.roundtrip(lambda ev: ev["name"] == "write", {"name": "write"}))

        def big(ev, limit=3):
            return len(json.dumps(ev.get("arguments", {}))) > limit and bool(re.search("x", ev["name"]))
        self.assertTrue(self.roundtrip(big, {"name": "xx", "arguments": {"a": 1}}))
        self.assertFalse(self.roundtrip(big, {"name": "yy", "arguments": {"a": 1}}))

    def test_expression(self):
        self.assertTrue(self.roundtrip("ev.get('code') == 2", {"code": 2}))
        with self.assertRaises(trigger.Bad):
            trigger.pack_py("ev.get(")
        with self.assertRaises(trigger.Bad):
            trigger.pack_py("ev['n'] == secret")

    def test_refused_when_it_cannot_travel(self):
        outer = 5
        with self.assertRaises(trigger.Bad) as c:
            trigger.pack_py(lambda ev: ev["n"] > outer)
        self.assertIn("outer", str(c.exception))
        with self.assertRaises(trigger.Bad):
            trigger.pack_py(lambda ev: ev["n"] > SOME_GLOBAL)  # noqa: F821
        with self.assertRaises(trigger.Bad):
            trigger.pack_py(lambda ev, s=object(): True)
        with self.assertRaises(trigger.Bad):
            trigger.pack_py(lambda a, b: True)
        self.assertTrue(self.roundtrip(lambda ev, outer=outer: ev["n"] > outer, {"n": 6}))

    def test_raising_function_is_a_broken_condition(self):
        s = spec(kind="py", py=trigger.pack_py(lambda ev: 1 / 0))
        count, hit, broken = trigger.step(s, {}, {})
        self.assertFalse(hit)
        self.assertIn("ZeroDivisionError", broken)


class Log(unittest.TestCase):
    def test_since_resume(self):
        entries = [{"kind": "stop", "trigger": "a"}, {"kind": "resume"}, {"kind": "stop", "trigger": "b"},
                   {"kind": "pause_failed", "trigger": "c"}, {"kind": "hold_ended", "trigger": "d"}, {"kind": "other"}]
        self.assertEqual([e["trigger"] for e in trigger.since_resume(entries)], ["b", "c", "d"])


class Handler(unittest.TestCase):
    """handler 本身：假的 aos-agent 記下參數、寫 ctl.json（像 pause 那樣）。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gdb-trigger-"))
        self.stack = self.tmp / "stack"
        self.cell = self.stack / "hooks" / "gdb_x"
        self.cell.mkdir(parents=True)
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        fake = bin_ / "aos-agent"
        fake.write_text('#!/bin/sh\necho "$@" >> "%s/calls.txt"\necho \'{"cmd": "pause", "seq": 7}\' > "%s/ctl.json"\necho "pause sent"\n'
                        % (self.tmp, self.stack))
        fake.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=str(bin_) + os.pathsep + self.env["PATH"], AOS_STACK=str(self.cell) + "/", PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fire(self, s, event):
        trigger.write_json(str(self.cell / trigger.SPEC), s)
        doc = dict({"hook": "gdb_x", "stack": str(self.stack)}, **event)
        return subprocess.run([str(ENTRY)], input=json.dumps(doc), capture_output=True, text=True, env=self.env, timeout=30)

    def calls(self):
        p = self.tmp / "calls.txt"
        return p.read_text().splitlines() if p.exists() else []

    def test_pause_note_and_count(self):
        s = spec(event="after_tool", times=2, daemon="/d", tools=["write"])
        r = self.fire(s, {"event": "after_tool", "name": "write", "code": 0})
        self.assertEqual((r.returncode, r.stdout, self.calls()), (0, "", []))
        r = self.fire(s, {"event": "after_tool", "name": "write", "code": 0, "content": "ok"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.calls(), ["--daemon /d ctl pause --no-wait ann"])
        notes = trigger.read_log(str(self.stack))
        self.assertEqual(len(notes), 1)
        self.assertEqual((notes[0]["kind"], notes[0]["trigger"], notes[0]["ctl_seq"], notes[0]["how"]), ("stop", "gdb_x", 7, "pause"))
        self.assertEqual(notes[0]["detail"]["content"], "ok")
        self.assertEqual(json.loads((self.cell / trigger.COUNT).read_text())["fired"], 1)

    # ---- hold（before_tool）----
    def start(self, s, event):
        trigger.write_json(str(self.cell / trigger.SPEC), s)
        doc = dict({"hook": "gdb_x", "stack": str(self.stack)}, **event)
        p = subprocess.Popen([str(ENTRY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        p.stdin.write(json.dumps(doc))
        p.stdin.close()
        self.addCleanup(lambda: p.poll() is None and (p.kill(), p.wait()))
        end = time.monotonic() + 10
        while time.monotonic() < end and trigger.read_hold(str(self.stack)) is None:
            self.assertIsNone(p.poll(), p.stderr.read() if p.poll() is not None else "")
            time.sleep(0.05)
        h = trigger.read_hold(str(self.stack))
        self.assertIsNotNone(h)
        return p, h

    def finish(self, p):
        p.wait(timeout=10)
        with p.stdout, p.stderr:
            return p.returncode, p.stdout.read(), p.stderr.read()

    def test_hold_then_run(self):
        p, h = self.start(spec(tools=["write"]), {"event": "before_tool", "name": "write", "id": "c1", "arguments": {"path": "a"}})
        self.assertEqual((h["event"], h["key"]), ("before_tool", "c1"))
        self.assertNotIn("skippable", h)
        self.assertEqual(self.calls(), [])                         # hold 不發 ctl pause
        time.sleep(0.5)
        self.assertIsNone(p.poll())                                # 還扣著
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[:2], (0, ""))
        self.assertIsNone(trigger.read_hold(str(self.stack)))
        self.assertIsNone(json.loads((self.cell / trigger.COUNT).read_text())["pending"])
        self.assertEqual(trigger.read_log(str(self.stack))[0]["how"], "hold")

    def test_release_needs_the_same_token(self):
        p, h = self.start(spec(), {"event": "before_tool", "name": "write", "id": "c2"})
        trigger.write_release(str(self.stack), "not-this-one")          # token 對不上＝不理
        time.sleep(0.5)
        self.assertIsNone(p.poll())
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[:2], (0, ""))

    def test_shell_ctl_resume_releases(self):
        (self.stack / "ctl.json").write_text('{"cmd": "pause", "seq": 3}\n')
        p, h = self.start(spec(), {"event": "before_tool", "name": "write", "id": "c3"})
        (self.stack / "ctl.json").write_text('{"cmd": "pause", "seq": 4}\n')    # 別人 pause：不放行
        time.sleep(0.5)
        self.assertIsNone(p.poll())
        (self.stack / "ctl.json").write_text('{"cmd": "resume", "seq": 5}\n')
        self.assertEqual(self.finish(p)[0], 0)
        log = trigger.read_log(str(self.stack))
        self.assertEqual((log[-1]["kind"], log[-1]["by"]), ("resume", "ctl"))

    def test_term_leaves_pending_and_the_same_call_is_held_again(self):
        s = spec(once=True)
        p, h = self.start(s, {"event": "before_tool", "name": "write", "id": "c4"})
        p.send_signal(signal.SIGTERM)
        self.assertEqual(self.finish(p)[0], 143)
        self.assertIsNone(trigger.read_hold(str(self.stack)))
        log = trigger.read_log(str(self.stack))
        self.assertEqual(log[-1]["kind"], "hold_ended")
        count = json.loads((self.cell / trigger.COUNT).read_text())
        self.assertEqual((count["pending"], count["fired"]), ("c4", 0))          # 沒放行＝這次不算（once 沒用掉）
        p, h = self.start(s, {"event": "before_tool", "name": "write", "id": "c4"})  # 同一次回來：直接再扣
        self.assertTrue(h["again"])
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[0], 0)
        count = json.loads((self.cell / trigger.COUNT).read_text())
        self.assertEqual((count["pending"], count["fired"], count["decided"]), (None, 1, {"key": "c4"}))
        r = self.fire(s, {"event": "before_tool", "name": "write", "id": "c5"})     # once 用掉了：別的呼叫不扣
        self.assertEqual(r.returncode, 0)

    def test_a_released_call_coming_back_is_not_held_again(self):
        s = spec()
        p, h = self.start(s, {"event": "before_tool", "name": "write", "id": "c6"})
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[:2], (0, ""))
        log = trigger.read_log(str(self.stack))
        self.assertEqual((log[-1]["kind"], log[-1]["by"], log[-1]["token"]), ("resume", "repl", h["token"]))   # handler 自己寫
        self.assertNotIn("go", log[-1])
        r = self.fire(s, {"event": "before_tool", "name": "write", "id": "c6"})     # 那一格被收掉後重跑同一個呼叫：照跑、不再扣
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIsNone(trigger.read_hold(str(self.stack)))

    def test_an_old_resume_in_ctl_does_not_release(self):
        (self.stack / "ctl.json").write_text('{"cmd": "resume", "seq": 9}\n')   # 扣住之前就在的 resume
        time.sleep(0.05)
        p, h = self.start(spec(), {"event": "before_tool", "name": "write", "id": "c7"})
        time.sleep(0.6)
        self.assertIsNone(p.poll())
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[0], 0)

    def test_letter_hold_then_release(self):
        p, h = self.start(spec(event="before_queue"), {"event": "before_queue", "letter": "L1", "content": "hi"})
        self.assertEqual((h["event"], h["key"]), ("before_queue", "L1"))
        trigger.write_release(str(self.stack), h["token"])
        self.assertEqual(self.finish(p)[:2], (0, ""))            # 照收那封信

    def test_broken_condition_warns_and_exits_0(self):
        r = self.fire(spec(kind="sh", sh="exit 4"), {"event": "before_tool", "name": "write"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("gdb_trigger: warning:", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_missing_spec_is_an_error_line(self):
        r = subprocess.run([str(ENTRY)], input="{}", capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("gdb_trigger: error: SpecMissing", r.stderr)

    def test_pause_failure_is_noted(self):
        (self.tmp / "bin" / "aos-agent").write_text("#!/bin/sh\necho 'aos-agent: error: PhaseBad ann is stopped' >&2\nexit 1\n")
        r = self.fire(spec(event="after_tool"), {"event": "after_tool", "name": "write", "code": 0})
        self.assertEqual(r.returncode, 0)
        notes = trigger.read_log(str(self.stack))
        self.assertEqual(notes[0]["kind"], "pause_failed")
        self.assertIn("PhaseBad", notes[0]["why"])



class Shape(unittest.TestCase):
    """介面的長相（線 aosgdb-api-1119，線 aos-pylib-cut-1119 改）：把手在 aos.py.agent（a.xxx＝aos-agent xxx、讀檔在 a.look）、斷點全在 a.bp；
    建斷點＝a.bp.add.<種類>(...)（使用者 11-19 裁定），字串式 a.bp.add("before_tool") 不留；resume 不收參數；aos-gdb 的說明字串跟著改。"""

    def bp(self):
        import aos.gdb as g
        return g.Breakpoints(g.Target("ann", "/d"))   # 不跑指令：Target 的 stack 用到才問

    def test_old_names_are_gone(self):
        import aos.gdb as g
        import aos.gdb.look as look
        for old in ("Agent", "attach", "echo", "sh", "watch", "watchers", "unwatch"):
            self.assertFalse(hasattr(g, old), old)
        self.assertFalse(hasattr(look.Look, "state"))                   # a.ctl.state() 還給指令
        for name in ("where", "history", "observed", "request", "queue", "stderr", "file", "path"):
            self.assertTrue(callable(getattr(look.Look, name)), name)

    def test_one_failed_for_the_live_side(self):
        import aos.gdb as g
        from aos.py import Failed, Timeout
        self.assertIs(g.Failed, Failed)
        self.assertTrue(issubclass(Timeout, TimeoutError))

    def test_bp_methods(self):
        import inspect
        import aos.gdb as g
        for name in ("rm", "set", "ls", "get", "resume", "step", "pause", "why", "held", "stopped", "notes", "clear"):
            self.assertTrue(callable(getattr(g.Breakpoints, name)), name)
        for name in ("resume", "step", "pause"):                         # 使用者 11-19「a.resume()就是a.resume()，他的args不應該有東西」
            self.assertEqual(list(inspect.signature(getattr(g.Breakpoints, name)).parameters), ["self"], name)
        for gone in ("skip", "wait_stopped", "stop"):                   # 11-19「不該有這個方法」；等停下併進 resume／step；stop 改名 pause
            self.assertFalse(hasattr(g.Breakpoints, gone), gone)
        self.assertFalse(hasattr(trigger, "SKIPPABLE"))
        b = g.Breakpoints(g.Target("cara", "/d"))
        self.assertEqual((b.idle_s, b.report_s, b.timeout_s), (1.0, 10, None))   # 等的設定是屬性，不是參數
        b.idle_s, b.timeout_s = 5, 30
        again = g.Breakpoints(g.Target("cara", "/d"))                   # a.bp 每次取都是新的：同一隻共用設定
        self.assertEqual((again.idle_s, again.timeout_s), (5, 30))
        self.assertEqual(g.Breakpoints(g.Target("dora", "/d")).idle_s, 1.0)
        for name, bad in (("idle_s", 0), ("report_s", -1), ("timeout_s", "x"), ("idle_s", True)):
            with self.assertRaises(g.Failed):
                setattr(b, name, bad)

    def test_result_reads_like_where_it_stopped(self):
        from aos.gdb.look import Why
        w = Why("ann", True, True, [{"kind": "stop", "by": "step", "trigger": None, "about": "a.bp.step(): one step"}])
        self.assertIsNone((w.outcome, w.head)[0])
        self.assertIn("ann is paused by a.bp.step()", repr(w))
        w.outcome, w.head = "stopped", "stopped after one step, before think"
        self.assertTrue(repr(w).startswith("stopped after one step, before think\nann is paused by a.bp.step()"))
        w.outcome, w.head = "idle", "ann did not stop: it is idle"
        self.assertEqual(repr(w), "ann did not stop: it is idle")
        h = Why("ann", True, True, [], held={"trigger": "gdb_before_tool_1", "event": "before_tool", "detail": {"name": "write"}})
        self.assertEqual(h.breakpoint, "before_tool_1")
        self.assertIn("a.bp.step() runs it", repr(h))
        self.assertNotIn("skip", repr(h))

    def test_add_kinds_one_shape(self):
        import inspect
        import aos.gdb as g
        from aos.agentlib import hooks
        add = self.bp().add
        self.assertEqual(set(dir(add)), set(e for e in hooks.EVENTS if e != hooks.CLOCK_EVENT) | {"tool_error", "watch"})
        for kind in dir(add):
            ps = inspect.signature(getattr(add, kind)).parameters
            with self.subTest(kind=kind):
                self.assertEqual([p for p in ps if ps[p].kind == ps[p].KEYWORD_ONLY][-2:], ["id", "replace"])
                self.assertIn("sh", ps)
                self.assertIn("py", ps)
        self.assertEqual(list(inspect.signature(add.before_tool).parameters)[0], "tool")
        self.assertEqual(list(inspect.signature(add.brain_failed).parameters)[0], "code")
        self.assertEqual(list(inspect.signature(add.before_queue).parameters)[0], "sh")   # 沒有主詞
        self.assertIn("every_ms", inspect.signature(add.watch).parameters)
        with self.assertRaises(AttributeError):
            add.befor_tool                                               # 打錯當場知道
        with self.assertRaises(g.Failed) as e:
            add("before_tool", tool="x")                                 # 字串式不留
        self.assertEqual(e.exception.code, "ArgumentsBad")
        with self.assertRaises(g.Failed):
            add.before_tool("x", bogus=1)
        with self.assertRaises(g.Failed):
            add.before_queue("x")                                        # 沒有主詞的種類不收位置參數
        self.assertIn("before_tool(tool=None, *", repr(add))

    def test_help_text_uses_the_new_names(self):
        from aos.apps import gdb as app
        self.assertIn("a.bp.add.before_tool(", app.HELP)
        self.assertIn("a.look.history", app.HELP)
        for verb in ("a.bp.resume()", "a.bp.step()", "a.bp.pause()"):
            self.assertIn(verb, app.HELP)
        for text in (app.HELP, app.BANNER):
            for old in ("stop_before_tool", "skip=True", "wait_paused", "a.watch(", "a.why(", "a.resume(", "a.triggers(", "skip(", "wait_stopped", "a.bp.stop(",
                        "a.bp.add(\"", "import aos.gdb", "g.attach", "a.where()", "a.history(", "import ag,", "import ag\n", "ag.tool"):
                self.assertNotIn(old, text)

    def test_bp_id(self):
        from aos.gdb.look import bp_id
        self.assertEqual((bp_id("gdb_before_tool_1"), bp_id("gdbw_watch_1"), bp_id(None)), ("before_tool_1", "watch_1", None))


if __name__ == "__main__":
    unittest.main()
