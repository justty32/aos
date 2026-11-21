"""Test the 11-11 hook events: on_clock (hook_clock.clock_tick, through H.clock_tick() in the cells), after_start / after_stop (aos-hook fire --def, as the templates' loop.json on_start / on_stop).
11-21 top-1121-hooknew: on_clock's "first check after a start" compares STACK/state.json's boot_id / pid / started_at_ticks (aos-hook fire after_start clears nothing);
the after_stop event has only event / hook / stack, the handler reads AOS_LOOP_CODE / AOS_LOOP_SIGNAL / AOS_LOOP_CAUSE itself."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hooks import CELLS, PROTO, Hooks, hooks  # noqa: E402
from aos.agentlib import hook_clock  # noqa: E402  （on_clock 的看時鐘 11-20 從 hooks.py 搬到這裡）

HOOK = PROTO / "bin" / "aos-hook"   # 裝好的指令（install.py 之後才有）
LOOP_ENV = ("AOS_LOOP_CODE", "AOS_LOOP_SIGNAL", "AOS_LOOP_CAUSE")   # what aos-loop sets for on_stop (11-14 B7 the cause; declared in py/aos/apps/hook/loop_hooks.json)


def fire(event, defn, env):
    """範本 loop.json 的 on_start／on_stop 那一行：aos-hook fire -q --stop-on-nonzero --def DEF EVENT（stdin 接 /dev/null，同 daemon 底下）。"""
    return subprocess.run([str(HOOK), "fire", "-q", "--stop-on-nonzero", "--def", str(defn), event], env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)


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
            return hook_clock.clock_tick(str(self.defn), str(self.stack), warn=self.warned.append)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def due(self, name="t", **keys):
        entry = {"event": "on_clock", "handler": self.hook(name)}
        if "every_ms" not in keys and "every_cycles" not in keys:
            entry["every_cycles"] = 10
        entry.update(keys)
        return entry

    # ---- 驗格
    def test_validate(self):
        for bad, why in (({"event": "on_clock", "handler": "x"}, "exactly one"),
                         ({"event": "on_clock", "handler": "x", "every_cycles": 1, "every_ms": 1}, "exactly one"),
                         ({"event": "on_clock", "handler": "x", "every_ms": 0}, "positive"),
                         ({"event": "on_clock", "handler": "x", "every_ms": 5, "clock": ""}, "clock"),
                         ({"event": "after_stop", "handler": "x", "every_ms": 5}, "only for event on_clock")):
            with self.subTest(bad=bad):
                with self.assertRaises(hooks.HooksBad) as cm:
                    hooks.check_entry(bad)
                self.assertIn(why, str(cm.exception))
        hooks.check_entry({"event": "on_clock", "handler": "x", "every_ms": 300000, "clock": "_clock"})
        hooks.check_entry({"event": "after_start", "handler": "x", "condition": "a"})   # 11-21: kept, never compared there

    # ---- clock_tick
    def test_no_clock_hook_costs_nothing(self):
        self.declare({"q": {"event": "after_queue", "handler": self.hook("q")}})
        self.assertEqual(self.tick(AOS_CLOCK=str(self.clock)), [])
        self.assertFalse((self.stack / "hookeds").exists())

    def test_baseline_then_due_then_missed(self):
        self.declare({"t": self.due()})
        env = {"AOS_CLOCK": str(self.clock)}
        self.assertEqual(self.tick(**env), ["t"])                 # 第一次＝立刻跑一次並記基準（11-11 使用者「起來就先觸發一次」）
        self.assertEqual(json.loads((self.stack / "hookeds" / "t" / "on_clock.json").read_text())["cycle"], 100)
        self.set_cycle(109)
        self.assertEqual(self.tick(**env), [])                    # 沒到：不起行程
        self.assertEqual(len(self.events()), 1)
        self.set_cycle(110)
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.tick(**env), [])                    # 同一格不重跑
        self.set_cycle(165)                                       # 忙了很久：回來只跑一次
        self.assertEqual(self.tick(**env), ["t"])
        f, a, b = self.events()
        self.assertEqual((f["first"], f["cycle"], f["last_cycle"], f["missed"]), (True, 100, None, 0))
        self.assertEqual((a["event"], a["first"], a["cycle"], a["last_cycle"], a["missed"], a["interval_ms"], a["clock"]),
                         ("on_clock", False, 110, 100, 0, 1000, str(self.clock)))
        self.assertEqual((b["cycle"], b["last_cycle"], b["missed"]), (165, 110, 4))
        self.assertEqual(b["stack"], str(self.stack))

    def loop_run(self, pid, ticks=1000, boot="boot-a"):
        """STACK/state.json as aos-loop writes it (only the keys hook_clock reads, plus one more)."""
        (self.stack / "state.json").write_text(json.dumps({"pid": pid, "started_at_ticks": ticks, "boot_id": boot, "runs": 3}))

    def test_restart_fires_again(self):   # 每次睡醒、重起：state.json 換了一次 loop（pid／started_at_ticks／boot_id）＝下一次檢查又是第一次
        self.declare({"t": self.due()})
        env = {"AOS_CLOCK": str(self.clock)}
        self.loop_run(4000)
        self.tick(**env)
        self.set_cycle(103)
        self.assertEqual(self.tick(**env), [])
        r = fire("after_start", self.defn, self.env)                      # 11-21: after_start clears nothing
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.stack / "hookeds" / "t" / "on_clock.json").exists())
        self.assertEqual(self.tick(**env), [])
        self.loop_run(4000, boot="boot-a")                                  # same run written again (other keys may change)
        self.assertEqual(self.tick(**env), [])
        self.loop_run(4001)                                                 # restarted: another pid
        self.assertEqual(self.tick(**env), ["t"])
        self.set_cycle(104)
        self.assertEqual(self.tick(**env), [])
        self.loop_run(4001, ticks=2000)                                     # pid reused, another start
        self.assertEqual(self.tick(**env), ["t"])
        self.loop_run(4001, ticks=2000, boot="boot-b")                      # machine rebooted
        self.assertEqual(self.tick(**env), ["t"])
        (self.stack / "state.json").unlink()                                # no loop window at all: another "run" too
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.tick(**env), [])
        self.assertEqual([(e["first"], e["cycle"]) for e in self.events()],
                         [(True, 100), (True, 103), (True, 104), (True, 104), (True, 104)])

    def test_every_ms_counts_cycles(self):
        self.declare({"t": self.due(every_ms=3000)})
        env = {"AOS_CLOCK": str(self.clock), "AOS_CLOCK_INTERVAL": "500"}   # 3000 ms＝6 格
        self.tick(**env)
        self.set_cycle(105)
        self.assertEqual(self.tick(**env), [])
        self.set_cycle(106)
        self.assertEqual(self.tick(**env), ["t"])
        self.assertEqual(self.events()[1]["interval_ms"], 500)

    def test_two_intervals_on_one_agent(self):
        """同一隻掛多個 on_clock、各自的間隔（daemon 時鐘＝基礎間隔，每個 hook 各自除頻；11-11 使用者「多個間隔」），狀態檔不互踩。"""
        self.declare({"fast": self.due("fast", every_cycles=2), "slow": self.due("slow", every_cycles=5),
                      "ms": self.due("ms", every_ms=3000)})                       # 3000 ms ÷ 1000 ms＝3 格
        env = {"AOS_CLOCK": str(self.clock)}
        runs = {"fast": [], "slow": [], "ms": []}
        for c in range(100, 121):
            self.set_cycle(c)
            for name in self.tick(**env):
                runs[name].append(c)
        self.assertEqual(runs["fast"], list(range(100, 121, 2)))
        self.assertEqual(runs["slow"], [100, 105, 110, 115, 120])
        self.assertEqual(runs["ms"], [100, 103, 106, 109, 112, 115, 118])
        for name, last in (("fast", 120), ("slow", 120), ("ms", 118)):
            self.assertEqual(json.loads((self.stack / "hookeds" / name / "on_clock.json").read_text())["cycle"], last)

    def test_backwards_counts_as_first(self):
        self.declare({"t": self.due()})
        env = {"AOS_CLOCK": str(self.clock)}
        self.tick(**env)
        self.set_cycle(3)                                        # 根重起、換台：等同第一次，跑一次並重記基準
        self.assertEqual(self.tick(**env), ["t"])
        self.set_cycle(12)
        self.assertEqual(self.tick(**env), [])
        self.set_cycle(13)
        self.assertEqual(self.tick(**env), ["t"])
        ev = self.events()
        self.assertEqual([(e["first"], e["cycle"], e["last_cycle"]) for e in ev], [(True, 100, None), (True, 3, None), (False, 13, 3)])

    def test_no_clock_warns_once(self):
        self.declare({"t": self.due()})
        for _ in range(3):
            self.assertEqual(self.tick(AOS_CLOCK=None), [])
        self.assertEqual(len(self.warned), 1)
        self.assertIn("AOS_CLOCK is not set", self.warned[0])
        self.tick(AOS_CLOCK=str(self.root / "nope"))
        self.assertEqual(len(self.warned), 2)                    # 原因變了才再說一次
        self.assertIn("no clock file", self.warned[1])
        self.assertEqual(self.tick(AOS_CLOCK=str(self.clock)), ["t"])   # 時鐘回來：第一次，跑一次
        self.assertTrue(self.events()[0]["first"])
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
        self.assertEqual(sorted(self.tick(**env)), ["by_dir", "by_proc"])   # 第一次各跑一次
        self.set_cycle(101)
        (daemon / "procs" / "_sub" / "clock").write_text("8\n")
        self.assertEqual(sorted(self.tick(**env)), ["by_dir", "by_proc"])   # 兩個 hook 各記各的
        clocks = sorted(e["clock"] for e in self.events()[2:])
        self.assertEqual(clocks, sorted([str(self.clock), str(daemon / "procs" / "_sub" / "clock")]))
        self.declare({"x": self.due(clock="_nobody")})
        self.tick(**env)
        self.assertIn("not on the daemon table", self.warned[-1])

    def test_cells_check_and_history_stays(self):
        self.declare({"t": self.due(every_cycles=1)})
        self.history([{"role": "user", "content": "hi"}])
        r = self.run_cell("idle", code=10)                       # 第一次：跑一次
        self.assertEqual([e["event"] for e in self.events()], ["on_clock"], r.stderr)
        self.run_cell("idle", code=10)                           # 沒走：不跑
        self.set_cycle(101)
        self.run_cell("idle", code=10)
        self.set_cycle(102)
        self.run_cell("wait", code=11)                           # 沒 pending、沒 request＝回 think；開頭照樣看時鐘
        self.assertEqual(len(self.events()), 3)
        self.assertEqual(self.history(), [{"role": "user", "content": "hi"}])

    def test_failing_handler_is_a_warning(self):   # 11-21: on_clock cannot be blocked: a failure is one warning, the cell goes on
        entry = self.due(every_cycles=1)
        entry.update(handler=self.hook("bad", "sys.exit(3)"))
        self.declare({"t": entry})
        r = self.run_cell("idle", code=10)                       # 第一次就跑、失敗＝一行 warning
        self.assertIn("agent-fsm: warning: hook t (event on_clock) failed: exited 3", r.stderr)
        self.assertNotIn("HookFailed", r.stderr)
        r = self.run_cell("idle", code=10)                       # 記過了：不每拍重跑
        self.assertNotIn("warning", r.stderr)
        self.assertEqual(len(self.events()), 1)

    # ---- after_start／after_stop（aos-hook fire --def）
    def test_fire_start_stop(self):
        self.declare({"s": {"event": "after_start", "handler": self.hook("s")},
                      "e": {"event": "after_stop", "handler": self.hook("e")}})
        run = lambda event, **env: fire(event, self.defn, dict(self.env, **env))
        self.assertEqual(run("after_start").returncode, 0)
        r = run("after_stop", AOS_LOOP_CODE="143", AOS_LOOP_SIGNAL="15")
        self.assertEqual((r.returncode, r.stdout), (0, ""))                  # -q：stdout 什麼都沒有
        a, b = self.events()
        self.assertEqual((a["event"], a["hook"], a["stack"]), ("after_start", "s", str(self.stack)))
        self.assertEqual(set(b), {"event", "hook", "stack"})                 # 11-21: no code / signal / cause in the event
        self.assertEqual(b["event"], "after_stop")
        r = run("no_such_point")                                             # 11-21: no event names checked; nobody listens = 0
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        r = run("after_start", AOS_STACK="")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-hook: error: StackMissing", r.stderr)
        self.declare({"e": {"event": "after_stop", "handler": self.hook("bad", "sys.exit(2)")}})
        r = run("after_stop")
        self.assertEqual(r.returncode, 2)                                    # --stop-on-nonzero: the handler's own code
        self.assertIn("aos-hook: error: HookFailed hook e (event after_stop) exited 2", r.stderr)
        self.declare({"e": {"event": "after_stop", "handler": self.hook("no", "sys.exit(10)")}})
        r = run("after_stop")
        self.assertEqual((r.returncode, r.stderr), (10, ""))                 # 10 = "no": no error line

    def test_fire_cause(self):   # 11-14 B7 the cause; 11-21: the handler reads AOS_LOOP_CODE / AOS_LOOP_SIGNAL / AOS_LOOP_CAUSE as aos-loop set them
        seen = self.root / "env.jsonl"
        body = "open(%r, 'a').write(json.dumps({k: os.environ.get(k) for k in %r}) + '\\n')\n" % (str(seen), LOOP_ENV)
        self.declare({"e": {"event": "after_stop", "handler": self.hook("e", body)}})
        env = {k: v for k, v in self.env.items() if k not in LOOP_ENV}
        cases = ["sleep", " sleep\n", "future_x", "", None]
        for value in cases:
            e = dict(env, AOS_LOOP_CODE="143", AOS_LOOP_SIGNAL="15")
            if value is not None:
                e["AOS_LOOP_CAUSE"] = value
            r = fire("after_stop", self.defn, e)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
        got = [json.loads(line) for line in seen.read_text().splitlines()]
        self.assertEqual([g["AOS_LOOP_CAUSE"] for g in got], cases)           # as it is: no trimming, no null for empty
        self.assertEqual({(g["AOS_LOOP_CODE"], g["AOS_LOOP_SIGNAL"]) for g in got}, {("143", "15")})
        self.assertTrue(all("cause" not in ev for ev in self.events()))
        r = fire("after_start", self.defn, dict(env, AOS_LOOP_CAUSE="sleep"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.events()), len(cases))   # after_start 沒有 hook：不多事件


def load_tests(loader, tests, pattern):
    """只跑這裡的測試（ClockHook 繼承 test_hooks.Hooks 的夾具，不重跑它的測試）。"""
    return unittest.TestSuite(ClockHook(n) for n in sorted(vars(ClockHook)) if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
