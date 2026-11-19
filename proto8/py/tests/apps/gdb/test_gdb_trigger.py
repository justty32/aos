"""aos.gdb.trigger 與 gdb_trigger handler（不起 daemon）：連續 N 次與歸零、once、tools 篩法、sh 的 0／10／其他、py 函式與運算式的打包與拒收、tool_error、字條從 resume 之後算；handler 用假的 aos-agent 跑：停的那次發 pause、留字條、block 退 10、條件壞了只 warning 退 0。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "py"))
from aos.gdb import trigger  # noqa: E402

ENTRY = PROTO / "py" / "tools" / "agent" / "gdb_trigger" / "_entry"


def spec(**kw):
    s = {"kind": "always", "event": "before_tool", "tools": None, "times": 1, "once": False, "block": False, "agent": "ann", "daemon": None}
    s.update(kw)
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
                   {"kind": "pause_failed", "trigger": "c"}, {"kind": "other"}]
        self.assertEqual([e["trigger"] for e in trigger.since_resume(entries)], ["b", "c"])


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
        s = spec(times=2, daemon="/d", tools=["write"])
        r = self.fire(s, {"event": "before_tool", "name": "write"})
        self.assertEqual((r.returncode, r.stdout, self.calls()), (0, "", []))
        r = self.fire(s, {"event": "before_tool", "name": "write", "arguments": {"path": "a"}})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.calls(), ["--daemon /d ctl pause --no-wait ann"])
        notes = trigger.read_log(str(self.stack))
        self.assertEqual(len(notes), 1)
        self.assertEqual((notes[0]["kind"], notes[0]["trigger"], notes[0]["ctl_seq"], notes[0]["blocked"]), ("stop", "gdb_x", 7, False))
        self.assertEqual(notes[0]["detail"]["arguments"], {"path": "a"})
        self.assertEqual(json.loads((self.cell / trigger.COUNT).read_text())["fired"], 1)

    def test_block_exits_10(self):
        r = self.fire(spec(block=True), {"event": "before_tool", "name": "write"})
        self.assertEqual(r.returncode, 10)
        self.assertTrue(trigger.read_log(str(self.stack))[0]["blocked"])

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
        r = self.fire(spec(), {"event": "before_tool", "name": "write"})
        self.assertEqual(r.returncode, 0)
        notes = trigger.read_log(str(self.stack))
        self.assertEqual(notes[0]["kind"], "pause_failed")
        self.assertIn("PhaseBad", notes[0]["why"])


if __name__ == "__main__":
    unittest.main()
