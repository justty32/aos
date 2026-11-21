"""aos.gdb.trigger 與 gdb_trigger handler（不起 daemon）：連續 N 次與歸零、once、tools 篩法、sh 的 0／10／其他、py 函式與運算式的打包與拒收、tool_error、字條從 resume 之後算；handler 用假的 aos-agent 跑：pause 型發 pause、留字條；hold 型扣住等放行（放行退 0、什麼都不印；shell 的 ctl resume 也放行；被 TERM 留 hold_ended 且同一次再來時直接再扣住；放行過的同一次再來不再扣）；條件壞了只 warning 退 0；介面長相（a.bp、resume／step／pause 只收 wait=、沒有 skip 與 wait_stopped、說明字串、wait=False 回的 Pending）；
斷點 id 純數字、刪了不重用、add 回的物件屬性每次重查、rm／set／get 收物件與 id、自己取名、下斷點失敗號碼還回去（假的 aos-agent）。"""
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
        self.cell = self.stack / "hookeds" / "gdb_x"
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

    def test_broken_trigger_warns_and_exits_0(self):
        # 11-21 起 hook 沒有 on_error：這支自己壞了（沒有／壞的 trigger.json）一行 warning、退 0，不擋 agent
        r = subprocess.run([str(ENTRY)], input="{}", capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("gdb_trigger: warning: SpecMissing", r.stderr)
        self.assertNotIn("error:", r.stderr)
        self.cell.mkdir(parents=True, exist_ok=True)
        (self.cell / trigger.SPEC).write_text("{")
        r = subprocess.run([str(ENTRY)], input="{}", capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("gdb_trigger: warning: SpecBad", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_pause_failure_is_noted(self):
        (self.tmp / "bin" / "aos-agent").write_text("#!/bin/sh\necho 'aos-agent: error: PhaseBad ann is stopped' >&2\nexit 1\n")
        r = self.fire(spec(event="after_tool"), {"event": "after_tool", "name": "write", "code": 0})
        self.assertEqual(r.returncode, 0)
        notes = trigger.read_log(str(self.stack))
        self.assertEqual(notes[0]["kind"], "pause_failed")
        self.assertIn("PhaseBad", notes[0]["why"])



class Shape(unittest.TestCase):
    """介面的長相（線 aosgdb-api-1119，線 aos-pylib-cut-1119 改）：遙控器在 aos.py.agent（a.xxx＝aos-agent xxx、讀檔在 a.look）、斷點全在 a.bp；
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
        for name in ("resume", "step", "pause"):                         # 使用者 11-20「三個都加」wait=，只開這一個參數
            ps = inspect.signature(getattr(g.Breakpoints, name)).parameters
            self.assertEqual(list(ps), ["self", "wait"], name)
            self.assertIs(ps["wait"].default, True)
            with self.assertRaises(g.Failed):
                getattr(self.bp(), name)(wait=1)                         # 只收 True／False，先擋、什麼都不送
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
        h = Why("ann", True, True, [], held={"trigger": "gdb_1", "event": "before_tool", "detail": {"name": "write"}})
        self.assertEqual(h.breakpoint, 1)
        self.assertIn("held at breakpoint 1:", repr(h))
        self.assertIn("a.bp.step() runs it", repr(h))
        self.assertNotIn("skip", repr(h))

    def test_add_kinds_one_shape(self):
        import inspect
        import aos.gdb as g
        from aos.agentlib import hooks
        add = self.bp().add
        self.assertEqual(set(dir(add)), set(e for e in hooks.POINTS if e != hooks.CLOCK_EVENT)
                         | {"before_compact", "after_compact", "after_start", "after_stop", "before_run", "after_run"}
                         | {"tool_error", "watch"})
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
        self.assertEqual((bp_id("gdb_3"), bp_id("gdbw_12"), bp_id("gdb_mine"), bp_id("gdbw_mine"), bp_id(None)), (3, 12, "mine", "mine", None))

    def test_pending(self):
        """wait=False 回的物件：is_done() 由 False 變 True；wait() 回背景的結果、背景的錯在 wait() 丟（使用者 11-20「用is_done()」）。"""
        import threading
        from aos.gdb.handles import Pending
        from aos.gdb.look import Why, Failed
        go = threading.Event()
        w = Why("ann", True, True, [])
        w.outcome, w.head = "stopped", "stopped after one step, before think"
        p = Pending("a.bp.step(wait=False)", "ann", run=lambda cancel: (go.wait(5), w)[1])
        self.assertFalse(p.is_done())
        self.assertIn("still waiting", repr(p))
        go.set()
        self.assertIs(p.wait(), w)
        self.assertTrue(p.is_done())
        self.assertIn("done: stopped after one step", repr(p))

        def boom(cancel):
            raise Failed("a.bp.resume", "it broke")
        q = Pending("a.bp.resume(wait=False)", "ann", run=boom)
        with self.assertRaises(Failed):
            q.wait()
        self.assertTrue(q.is_done())
        self.assertTrue(Pending("a.bp.pause(wait=False)", "ann", value=w).is_done())   # 已經停著：一拿到就是好的


FAKE_AGENT = r'''#!/usr/bin/env python3
"""a fake aos-agent for AddFails: ctl state who, hook ls/add/rm; MODE file "missing" = HooksMissing, "fail" = hook add fails"""
import json, os, sys
T = os.environ["FAKE_DIR"]
args = sys.argv[sys.argv.index("--target") + 2:]
mode = open(os.path.join(T, "MODE")).read().strip()
table = os.path.join(T, "hooks.json")
have = json.load(open(table)) if os.path.exists(table) else []
if args[:2] == ["ctl", "state"]:
    print(json.dumps({"who": {"stack": os.path.join(T, "stack")}}))
    sys.exit(0)
if args[0] == "hook" and mode == "missing":
    sys.stderr.write("aos-agent: error: HooksMissing ann names no hookeds file it can keep a copy of (write \"hookeds\": \"hookeds.json\" "
                     "at the top of the definition's interfaces.json)\n")
    sys.exit(1)
if args[:2] == ["hook", "ls"]:
    print(json.dumps([{"name": n} for n in have]))
elif args[:2] == ["hook", "add"]:
    if mode == "fail":
        sys.stderr.write("aos-agent: error: HooksBad the list is broken\n")
        sys.exit(1)
    n = args[args.index("--name") + 1]
    json.dump(args, open(os.path.join(T, "add_args.json"), "w"))
    json.dump(sorted(set(have) | {n}), open(table, "w"))
    print("added " + n)
elif args[:2] == ["hook", "rm"]:
    if mode == "fail":
        sys.stderr.write("aos-agent: error: HooksBad the list is broken\n")
        sys.exit(1)
    json.dump([x for x in have if x != args[2]], open(table, "w"))
    print("removed " + args[2])
'''
FAKE_DAEMON_CTL = r'''#!/usr/bin/env python3
"""a fake aos-daemon-ctl for AddFails: ls -j shows ann only; add is rejected"""
import json, sys
if "ls" in sys.argv:
    print(json.dumps({"procs": {"ann": {"phase": "running"}}}))
    sys.exit(0)
sys.stderr.write("aos-daemon-ctl: error: AddRejected the daemon said no\n")
sys.exit(1)
'''


class AddFails(unittest.TestCase):
    """下斷點失敗＝什麼都不留（使用者 11-19 下午「派線修」，線 aos-bpfix-1119）：裝不上 hook（HooksMissing 等）時小格不留、a.bp 列不出、id 不跳號；
    重下（replace）失敗＝原本的設定與計數放回去；a.bp.set 裝不上＝設定不變；觀察者掛不上表＝新建的 stack 夾不留。HooksMissing 補一句怎麼修。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gdb-addfail-"))
        (self.tmp / "stack").mkdir()
        (self.tmp / "daemon" / "procs").mkdir(parents=True)
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for name, text in (("aos-agent", FAKE_AGENT), ("aos-daemon-ctl", FAKE_DAEMON_CTL)):
            (bin_ / name).write_text(text)
            (bin_ / name).chmod(0o755)
        self.mode("missing")
        self.old = {k: os.environ.get(k) for k in ("PATH", "FAKE_DIR")}
        os.environ["PATH"] = str(bin_) + os.pathsep + os.environ["PATH"]
        os.environ["FAKE_DIR"] = str(self.tmp)
        import aos.gdb as g
        self.g = g
        self.bp = g.Breakpoints(g.Target("ann", str(self.tmp / "daemon")))

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mode(self, m):
        (self.tmp / "MODE").write_text(m)

    def test_hooks_missing_leaves_nothing_and_says_how_to_fix(self):
        for _ in range(2):
            with self.assertRaises(self.g.Failed) as e:
                self.bp.add.before_tool("write")
            self.assertEqual(e.exception.code, "HooksMissing")
            self.assertIn("give hooks={} to defs.Agent(...) in agent.py", str(e.exception))
            self.assertIn("recompile", str(e.exception))
            self.assertTrue(str(e.exception).startswith("aos-agent: error: HooksMissing ann names no hookeds file"))   # 原本那行原樣在前
            self.assertFalse((self.tmp / "stack" / "hookeds").exists())             # 小格（連 hookeds/ 夾）都沒留
            self.assertEqual(self.bp._trigger_ids(), set())
        with self.assertRaises(self.g.Failed) as e:
            self.bp.ls()                                                          # 列也是同一句
        self.assertIn("give hooks={} to defs.Agent(...) in agent.py", str(e.exception))
        self.mode("ok")
        self.assertEqual(self.bp.add.before_tool("write").id, 1)                 # id 不跳號
        self.assertEqual([(r["id"], r["enabled"]) for r in self.bp.ls()], [(1, True)])

    def test_failing_add_next_to_others_and_replace_puts_back(self):
        self.mode("ok")
        self.assertEqual(self.bp.add.after_tool("write", times=2).id, 1)
        cell = self.tmp / "stack" / "hookeds" / "gdb_0001"
        trigger.write_json(str(cell / trigger.COUNT), {"seen": 5, "streak": 1, "fired": 2})
        before = {n: (cell / n).read_bytes() for n in (trigger.SPEC, trigger.COUNT)}
        self.mode("fail")
        with self.assertRaises(self.g.Failed):
            self.bp.add.after_tool("read")                                       # 旁邊已有一個：新的不留、舊的不動
        with self.assertRaises(self.g.Failed):
            self.bp.add.after_tool("read", id=1, replace=True)                   # 重下失敗：原本的設定與計數放回去
        self.assertEqual({n: (cell / n).read_bytes() for n in before}, before)
        self.assertEqual(sorted(p.name for p in (self.tmp / "stack" / "hookeds").iterdir()), ["gdb_0001"])
        with self.assertRaises(self.g.Failed):
            self.bp.set(1, times=5)                                              # 改也一樣：裝不上＝設定不變
        self.assertEqual((cell / trigger.SPEC).read_bytes(), before[trigger.SPEC])
        self.mode("ok")
        self.assertEqual(self.bp.add.after_tool("read").id, 2)
        self.assertEqual([r["id"] for r in self.bp.ls()], [1, 2])

    def test_watcher_that_cannot_go_on_the_table_leaves_no_stack(self):
        self.mode("ok")
        with self.assertRaises(self.g.Failed) as e:
            self.bp.add.watch(py="False")
        self.assertEqual(e.exception.code, "AddRejected")
        self.assertEqual(list((self.tmp / "daemon" / "procs").iterdir()), [])
        nxt = self.tmp / "stack" / "gdb" / trigger.NEXT
        self.assertEqual(json.loads(nxt.read_text()), {"next": 1})               # 掛不上表＝號碼還回去了
        kept = self.tmp / "daemon" / "procs" / "gdbw_0005"                         # 先前 rm 過、留著給人看的夾：不動，號碼也不再用
        kept.mkdir()
        (kept / "old.txt").write_text("kept")
        with self.assertRaises(self.g.Failed):
            self.bp.add.watch(py="False")
        self.assertEqual((kept / "old.txt").read_text(), "kept")
        self.assertEqual(json.loads(nxt.read_text()), {"next": 6})               # 這次拿的是 6（躲開 5），沒掛上也還回去
        self.assertEqual(self.bp.add.before_tool().id, 6)


class Ids(unittest.TestCase):
    """斷點 id 與 add 回的物件（使用者 11-20：id 純數字、種類放屬性；號碼「不重用」；add「回物件、帶屬性」；屬性「每次讀都重新查」）。
    用 AddFails 那支假的 aos-agent（hook ls／add／rm、ctl state），不起 daemon。"""

    setUp, tearDown, mode = AddFails.setUp, AddFails.tearDown, AddFails.mode

    def test_numbers_are_never_used_again(self):
        self.mode("ok")
        b1 = self.bp.add.before_tool("write")
        self.assertEqual((b1.id, type(b1.id)), (1, int))
        self.bp.rm(b1)
        b2 = self.bp.add.before_tool("write")
        self.assertEqual(b2.id, 2)                                               # 刪 1 再加得到 2
        again = self.g.Breakpoints(self.g.Target("ann", str(self.tmp / "daemon")))   # 重新取 a.bp（像重開 REPL）：計數器在 stack 裡
        self.assertEqual(again.add.after_tool().id, 3)
        self.bp.rm(2)
        self.bp.rm("3")                                                          # 數字字串也收
        self.assertEqual(self.bp.ls(), [])
        self.assertEqual(self.bp.add.tool_error().id, 4)
        self.assertEqual(json.loads((self.tmp / "stack" / "gdb" / trigger.NEXT).read_text()), {"next": 5})
        self.assertEqual(sorted(json.loads((self.tmp / "hooks.json").read_text())), ["gdb_0004"])   # hook 名＝gdb_<補零的號碼>

    def test_add_returns_a_live_object(self):
        self.mode("ok")
        b = self.bp.add.after_tool("write", times=2)
        self.assertEqual((b.id, b.kind, b.how, b.times, b.enabled, b.fired), (1, "after_tool", "pause", 2, True, 0))
        self.assertEqual(self.bp.add.tool_error().kind, "tool_error")
        self.assertEqual(self.bp.add.before_queue().kind, "before_queue")
        added = json.loads((self.tmp / "add_args.json").read_text())             # 11-21：不再帶 --on-error／--no-intercept
        self.assertEqual(added[added.index("--timeout-ms") + 1], "0")                # before_queue 扣住：不限時
        self.assertFalse({"--on-error", "--no-intercept", "--async"} & set(added))
        trigger.write_json(str(self.tmp / "stack" / "hookeds" / "gdb_0001" / trigger.COUNT), {"seen": 4, "fired": 2})
        self.assertEqual((b.fired, b.seen), (2, 4))                              # 每次讀都重新查
        self.assertEqual(self.bp.set(b, times=3).times, 3)                       # set 收物件（也回物件）
        self.assertEqual(b.times, 3)
        self.assertEqual(self.bp.get(b)["id"], 1)                                # get 收物件也收號碼
        self.assertEqual(self.bp.get(1), self.bp.get("1"))
        self.assertTrue(b == 1 and b == self.bp.get(1)["id"])
        self.assertIn("breakpoint 1 of ann: after_tool", repr(b))
        with self.assertRaises(AttributeError):
            b.kind = "x"                                                         # 唯讀：改用 a.bp.set
        with self.assertRaises(AttributeError):
            b.no_such_field
        self.bp.rm(b)                                                            # rm 收物件
        with self.assertRaises(self.g.Failed) as e:
            b.fired                                                              # 刪掉之後讀屬性＝報錯
        self.assertEqual(e.exception.code, "BreakpointGone")
        self.assertIn("gone", str(e.exception))
        self.assertEqual(b.id, 1)                                                # id 本身照拿得到
        self.assertIn("gone", repr(b))
        with self.assertRaises(self.g.Failed):
            self.bp.get(b)

    def test_names_and_ids_you_give(self):
        """自己取名照留（替使用者做的選擇：最不破壞）；號碼不能自己挑，只能 replace 已有的。"""
        self.mode("ok")
        m = self.bp.add.after_tool(id="mine")
        self.assertEqual((m.id, m.kind), ("mine", "after_tool"))
        self.assertEqual(sorted(json.loads((self.tmp / "hooks.json").read_text())), ["gdb_mine"])
        n = self.bp.add.before_tool()
        self.assertEqual(n.id, 1)                                                # 取名不吃號碼
        self.assertEqual([r["id"] for r in self.bp.ls()], [1, "mine"])           # 號碼在前、名字在後
        r = self.bp.add.before_queue(id=n, replace=True)                         # replace 收物件：同一個號碼換掉
        self.assertEqual((r.id, r.kind, n.kind), (1, "before_queue", "before_queue"))
        for bad in (7, "7"):
            with self.assertRaises(self.g.Failed) as e:
                self.bp.add.before_tool(id=bad, replace=True)                    # 沒有的號碼不能自己挑
            self.assertIn("never used again", str(e.exception))
        with self.assertRaises(self.g.Failed):
            self.bp.add.after_tool(id="mine")                                    # 同名不換（沒給 replace）
        for bad in (0, -1, True, "", "a/b", None, 1.5):
            with self.assertRaises(self.g.Failed):
                self.bp.get(bad)
        self.assertEqual(self.bp.add.after_tool().id, 2)


if __name__ == "__main__":
    unittest.main()
