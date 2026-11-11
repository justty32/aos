"""Test the 11-11 hook events: clock_due (hooks.clock_tick in the cells), after_start / after_stop (lib/agent/hook_fire)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hooks import CELLS, PROTO, Hooks, hooks  # noqa: E402

FIRE = PROTO / "lib" / "agent" / "hook_fire" / "_entry"


class ClockHook(Hooks):
    def setUp(self):
        super().setUp()
        self.clock = self.root / "d" / "clock"
        self.clock.parent.mkdir()
        self.set_cycle(100)
        self.env["AOS_CLOCK"] = str(self.clock)
        self.warned = []

    def set_cycle(self, n):
        self.clock.write_text("%d\n" % n)

    def tick(self, **env):
        old = {k: os.environ.get(k) for k in env}
        os.environ.update({k: v for k, v in env.items() if v is not None})
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
        try:
            return hooks.clock_tick(str(self.defn), str(self.stack), warn=self.warned.append)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def due(self, name="t", **keys):
        entry = {"event": "clock_due", "handler": self.hook(name), "on_error": "continue"}
        if "every_ms" not in keys and "every_cycles" not in keys:
            entry["every_cycles"] = 10
        entry.update(keys)
        return entry

    # ---- 驗格
    def test_validate(self):
        for bad, why in (({"event": "clock_due", "handler": "x"}, "exactly one"),
                         ({"event": "clock_due", "handler": "x", "every_cycles": 1, "every_ms": 1}, "exactly one"),
                         ({"event": "clock_due", "handler": "x", "every_ms": 0}, "positive"),
                         ({"event": "clock_due", "handler": "x", "every_ms": 5, "clock": ""}, "clock"),
                         ({"event": "after_stop", "handler": "x", "every_ms": 5}, "only for event clock_due"),
                         ({"event": "after_start", "handler": "x", "condition": "a"}, "takes no condition")):
            with self.subTest(bad=bad):
                with self.assertRaises(hooks.HooksBad) as cm:
                    hooks.validate_entry(bad)
                self.assertIn(why, str(cm.exception))
        hooks.validate_entry({"event": "clock_due", "handler": "x", "every_ms": 300000, "clock": "_clock"})

    # ---- clock_tick
    def test_no_clock_hook_costs_nothing(self):
        self.declare({"q": {"event": "after_queue", "handler": self.hook("q")}})
        self.assertEqual(self.tick(AOS_CLOCK=str(self.clock)), [])
        self.assertFalse((self.stack / "hooks").exists())

    def test_baseline_then_due_then_missed(self):
        self.declare({"t": self.due()})
        env = {"AOS_CLOCK": str(self.clock)}
        self.assertEqual(self.tick(**env), [])                    # 第一次＝只記基準
        self.assertEqual(json.loads((self.stack / "hooks" / "t" / "clock_due.json").read_text())["cycle"], 100)
        self.set_cycle(109)
        self.assertEqual(self.tick(**env), [])                    # 沒到：不起行程
        self.assertEqual(self.events(), [])
        self.set_cycle(110)
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.tick(**env), [])                    # 同一格不重跑
        self.set_cycle(165)                                       # 忙了很久：回來只跑一次
        self.assertEqual(self.tick(**env), ["t"])
        a, b = self.events()
        self.assertEqual((a["event"], a["cycle"], a["last_cycle"], a["missed"], a["interval_ms"], a["clock"]),
                         ("clock_due", 110, 100, 0, 1000, str(self.clock)))
        self.assertEqual((b["cycle"], b["last_cycle"], b["missed"]), (165, 110, 4))
        self.assertEqual(b["stack"], str(self.stack))

    def test_every_ms_counts_cycles(self):
        self.declare({"t": self.due(every_ms=3000)})
        env = {"AOS_CLOCK": str(self.clock), "AOS_CLOCK_INTERVAL": "500"}   # 3000 ms＝6 格
        self.tick(**env)
        self.set_cycle(105)
        self.assertEqual(self.tick(**env), [])
        self.set_cycle(106)
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.events()[0]["interval_ms"], 500)

    def test_backwards_resets(self):
        self.declare({"t": self.due()})
        env = {"AOS_CLOCK": str(self.clock)}
        self.tick(**env)
        self.set_cycle(3)                                        # 根重起、換台
        self.assertEqual(self.tick(**env), [])
        self.set_cycle(12)
        self.assertEqual(self.tick(**env), [])
        self.set_cycle(13)
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.events()[0]["last_cycle"], 3)

    def test_no_clock_warns_once(self):
        self.declare({"t": self.due()})
        for _ in range(3):
            self.assertEqual(self.tick(AOS_CLOCK=None), [])
        self.assertEqual(len(self.warned), 1)
        self.assertIn("AOS_CLOCK is not set", self.warned[0])
        self.tick(AOS_CLOCK=str(self.root / "nope"))
        self.assertEqual(len(self.warned), 2)                    # 原因變了才再說一次
        self.assertIn("no clock file", self.warned[1])
        self.tick(AOS_CLOCK=str(self.clock))                     # 時鐘回來：記基準
        self.set_cycle(110)
        self.assertEqual(self.tick(AOS_CLOCK=str(self.clock)), ["t"])

    def test_clock_as_folder_and_proc_name(self):
        self.declare({"by_dir": self.due("d", every_cycles=1, clock=str(self.clock.parent)),
                      "by_proc": self.due("p", every_cycles=1, clock="_sub")})
        daemon = self.root / "daemon"
        (daemon / "procs" / "_sub").mkdir(parents=True)
        (daemon / "procs" / "_sub" / "clock").write_text("7\n")
        (daemon / "procs_state.json").write_text(json.dumps({"procs": {"_sub": {"stack": "procs/_sub"}}}))
        env = {"AOS_DAEMON": str(daemon)}
        self.tick(**env)
        self.set_cycle(101)
        (daemon / "procs" / "_sub" / "clock").write_text("8\n")
        self.assertEqual(sorted(self.tick(**env)), ["by_dir", "by_proc"])   # 兩個 hook 各記各的
        clocks = sorted(e["clock"] for e in self.events())
        self.assertEqual(clocks, sorted([str(self.clock), str(daemon / "procs" / "_sub" / "clock")]))
        self.declare({"x": self.due(clock="_nobody")})
        self.tick(**env)
        self.assertIn("not on the daemon table", self.warned[-1])

    def test_cells_check_and_history_stays(self):
        self.declare({"t": self.due(every_cycles=1)})
        self.history([{"role": "user", "content": "hi"}])
        self.run_cell("idle", code=10)                           # 第一次：基準
        self.set_cycle(101)
        r = self.run_cell("idle", code=10)
        self.assertEqual([e["event"] for e in self.events()], ["clock_due"], r.stderr)
        self.set_cycle(102)
        self.run_cell("wait", code=11)                           # 沒 pending、沒 request＝回 think；開頭照樣看時鐘
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(self.history(), [{"role": "user", "content": "hi"}])

    def test_failing_handler_stop_stops_cell(self):
        entry = self.due(every_cycles=1)
        entry.update(on_error="stop", handler=self.hook("bad", "sys.exit(3)"))
        self.declare({"t": entry})
        self.run_cell("idle", code=10)
        self.set_cycle(101)
        r = self.run_cell("idle", code=1)
        self.assertIn("HookFailed", r.stderr)
        self.set_cycle(101)
        self.run_cell("idle", code=10)                           # 記過了：不每拍重跑

    # ---- after_start／after_stop（hook_fire）
    def test_hook_fire(self):
        self.declare({"s": {"event": "after_start", "handler": self.hook("s")},
                      "e": {"event": "after_stop", "handler": self.hook("e")}})
        run = lambda *a, **env: subprocess.run([str(FIRE), *a], env=dict(self.env, **env), capture_output=True,
                                               text=True, timeout=20)
        self.assertEqual(run("after_start", str(self.defn)).returncode, 0)
        self.assertEqual(run("after_stop", str(self.defn), AOS_LOOP_CODE="143", AOS_LOOP_SIGNAL="15").returncode, 0)
        self.assertEqual(run("after_stop", str(self.defn), AOS_LOOP_CODE="0", AOS_LOOP_SIGNAL="").returncode, 0)
        a, b, c = self.events()
        self.assertEqual(a["event"], "after_start")
        self.assertNotIn("code", a)
        self.assertEqual((b["event"], b["code"], b["signal"]), ("after_stop", 143, 15))
        self.assertEqual((c["code"], c["signal"]), (0, None))
        r = run("before_queue", str(self.defn))
        self.assertEqual(r.returncode, 1)
        self.assertIn("hook_fire: error: ArgumentsBad", r.stderr)
        self.declare({"e": {"event": "after_stop", "handler": self.hook("bad", "sys.exit(2)")}})
        r = run("after_stop", str(self.defn))
        self.assertEqual(r.returncode, 1)
        self.assertIn("hook_fire: error: HookFailed", r.stderr)


def load_tests(loader, tests, pattern):
    """只跑這裡的測試（ClockHook 繼承 test_hooks.Hooks 的夾具，不重跑它的測試）。"""
    return unittest.TestSuite(ClockHook(n) for n in sorted(vars(ClockHook)) if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
