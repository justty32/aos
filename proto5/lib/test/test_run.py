"""aos-run 真進程：狀態順序、ctl、完成後計時與可選子孫清理。"""
import json
import signal
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

import aos_exec
import aos_run

import aos_inst
from _util import Base, LIB, PY

CLI = os.path.join(os.path.dirname(LIB), "cli", "aos-run")
TOOL_CPU = os.path.join(os.path.dirname(LIB), "cli", "aos-tool-cpu")


class RunTests(Base):
    def wait_for(self, predicate, timeout=5):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("等待條件逾時")

    def status(self):
        try:
            return json.loads(Path(self.d, "R/run.json").read_text())
        except FileNotFoundError:
            return {}

    def start(self, target, *args):
        p = subprocess.Popen([PY, CLI, str(target), *map(str, args), "--home", str(Path(self.d, "R"))],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
        self.addCleanup(self.cleanup, p)
        return p

    def cleanup(self, p):
        if p.poll() is None:
            p.terminate()
            try:
                p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
        else:
            p.communicate()

    def finish(self, p, code=0):
        out, err = p.communicate(timeout=8)
        self.assertEqual(p.returncode, code, err)
        return out, err, self.status()

    def target(self, script="pass", **kwargs):
        return self.inst(dict(argv=[PY, "-c", script], **kwargs), "job.json")

    def test_max_runs_and_status(self):
        target = self.target("raise SystemExit(7)")
        p = self.start(target, "--max-runs", 2, "--interval-ms", 0)
        out, err, status = self.finish(p)
        self.assertEqual((out, err), ("", ""))
        self.assertEqual(status, dict(pid=p.pid, busy=False, target=target, runs=2,
                                     last_target=target, last_exit=7, last_kind="child", last_ms=status["last_ms"], held=False))
        self.assertGreaterEqual(status["last_ms"], 0)

    def test_repeatable_stop_exit(self):
        p = self.start(self.target("raise SystemExit(101)"), "--stop-exit", 100, "--stop-exit", 101)
        state = self.finish(p)[2]
        self.assertEqual((state["runs"], state["last_exit"]), (1, 101))

    def test_aos_failures_repeat_and_kind_is_preserved(self):
        p = self.start(os.path.join(self.d, "missing.json"), "--max-runs", 2, "--interval-ms", 0)
        state = self.finish(p)[2]
        self.assertEqual((state["runs"], state["last_exit"], state["last_kind"]), (2, 125, "aos"))

    def test_stop_exit_125_matches_aos_failure(self):
        p = self.start(os.path.join(self.d, "missing.json"), "--stop-exit", 125)
        self.assertEqual(self.finish(p)[2]["runs"], 1)

    def test_bad_utf8_is_reported_as_aos_failure(self):
        target = os.path.join(self.d, "bad.json")
        Path(target).write_bytes(b"\xff")
        p = self.start(target, "--max-runs", 1)
        _, err, state = self.finish(p)
        self.assertIn("JsonSyntax", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual((state["last_exit"], state["last_kind"]), (125, "aos"))

    def test_nul_argv_is_reported_as_aos_failure(self):
        target = self.inst({"argv": ["bad\0command"]}, "job.json")
        p = self.start(target, "--max-runs", 1)
        _, err, state = self.finish(p)
        self.assertIn("FieldTypeMismatch", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual((state["last_exit"], state["last_kind"]), (125, "aos"))

    def test_missing_plain_target_stops_usage(self):
        p = self.start(os.path.join(self.d, "missing"))
        state = self.finish(p, 2)[2]
        self.assertEqual((state["last_exit"], state["last_kind"]), (2, "usage"))

    def test_interval_starts_after_completion(self):
        script = "import time; f=open('times','a'); f.write(str(time.monotonic())+'\\n'); f.close(); time.sleep(.16)"
        p = self.start(self.target(script), "--max-runs", 2, "--interval-ms", 180)
        self.finish(p)
        times = list(map(float, self.read("times").splitlines()))
        self.assertGreaterEqual(times[1] - times[0], 0.32)

    def test_zero_timeout_does_not_cut_off(self):
        p = self.start(self.target("import time; time.sleep(.12)"), "--timeout-ms", 0, "--max-runs", 1)
        self.assertEqual(self.finish(p)[2]["last_exit"], 0)

    def test_no_unrequested_flags(self):
        for flag in ("--from-start", "--time-limit-ms", "--stop-on-error", "--dir-target", "--stderr", "--status-fd"):
            with self.subTest(flag=flag):
                r = subprocess.run([PY, CLI, flag], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2)

    def test_invalid_numbers_and_fd(self):
        for args in (("--interval-ms", "-1"), ("--timeout-ms", "-1"), ("--max-runs", "-1"),
                     ("--stop-exit", "256"), ("--status-fd", "-1"), ("--status-fd", "99999")):
            with self.subTest(args=args):
                r = subprocess.run([PY, CLI, *args], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)

    def test_term_during_interval_is_prompt(self):
        p = self.start(self.target(), "--interval-ms", 10000)
        self.wait_for(lambda: self.status().get("runs", 0) >= 1)
        start = time.monotonic()
        p.terminate()
        self.assertEqual(self.finish(p)[2]["runs"], 1)
        self.assertLess(time.monotonic() - start, 1)

    def test_default_target_directory(self):
        self.inst({"argv": [PY, "-c", "pass"]})
        r = subprocess.run([PY, CLI, "--max-runs", "1"], cwd=self.d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_plain_executable(self):
        target = self.write("job", "#!/bin/sh\necho plain\n", executable=True)
        p = self.start(target, "--max-runs", 1)
        self.assertEqual(self.finish(p)[0], "plain\n")

    def test_no_home_writes_no_state(self):
        target = self.target()
        result = subprocess.run([PY, CLI, target, "--max-runs", "1"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(Path(self.d, "run.json").exists())
        self.assertFalse(Path(self.d, "R").exists())

    def tree(self, nested=False, ignore_parent=True):
        # 父與孫皆就緒才測 TERM；不把啟動競態當成殺進程成功。
        child = ("import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                 "open('grand.pid','w').write(str(os.getpid())); time.sleep(30)")
        script = ("import os,signal,subprocess,time; "
                  + ("signal.signal(signal.SIGTERM,signal.SIG_IGN); " if ignore_parent else "")
                  + "open('child.pid','w').write(str(os.getpid())); "
                  + "subprocess.Popen(%r); time.sleep(30)" % [PY, "-c", child])
        if not nested:
            return self.target(script)
        self.inst({"_metainfo": {"_type": "tool_cpu", "_version": 1}}, "T/info.json")
        inst = aos_inst.load_obj({"argv": [PY, "-c", script]}, self.d)
        self.inst({"inst": inst, "stdin": "", "timeout_ms": 30000,
                   "result": os.path.join(self.d, "result.json")}, "T/requests/work.json")
        return self.target("import runpy,sys; sys.argv=%r; runpy.run_path(%r,run_name='__main__')"
                           % ([TOOL_CPU, os.path.join(self.d, "T")], TOOL_CPU))

    def assert_tree_dead(self):
        for name in ("child.pid", "grand.pid"):
            pid = int(self.read(name))
            def dead():
                try:
                    return Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[0] == "Z"
                except FileNotFoundError:
                    return True
            self.wait_for(dead)

    def test_first_term_kills_child_and_grandchild(self):
        p = self.start(self.tree(), "--kill-tree")
        self.wait_for(lambda: self.exists("grand.pid"))
        start = time.monotonic()
        p.terminate()
        events = self.finish(p)[2]
        self.assertGreaterEqual(time.monotonic() - start, 1.8)
        self.assertEqual((events["runs"], events["last_exit"]), (1, 137))
        self.assert_tree_dead()

    def test_parent_exits_on_term_but_grandchild_still_killed(self):
        p = self.start(self.tree(ignore_parent=False), "--kill-tree")
        self.wait_for(lambda: self.exists("grand.pid"))
        p.terminate()
        self.assertEqual(self.finish(p)[2]["last_exit"], 143)
        self.assert_tree_dead()

    def test_timeout_kills_child_and_grandchild(self):
        p = self.start(self.tree(), "--timeout-ms", 400, "--max-runs", 1)
        self.assertEqual(self.finish(p)[2]["last_exit"], 137)
        self.assert_tree_dead()

    def test_term_crosses_tool_cpu_run_inst_session(self):
        p = self.start(self.tree(nested=True), "--kill-tree")
        self.wait_for(lambda: self.exists("grand.pid"))
        p.terminate()
        self.finish(p)
        self.assert_tree_dead()
        self.assertFalse(self.exists("result.json"))

    def test_timeout_crosses_tool_cpu_run_inst_session(self):
        p = self.start(self.tree(nested=True), "--timeout-ms", 600, "--max-runs", 1)
        self.finish(p)
        self.assert_tree_dead()

    def test_first_term_finishes_current_run(self):
        p = self.start(self.target("import time; open('begun','w').close(); time.sleep(.3); open('finished','w').close()"),
                       "--interval-ms", 0)
        self.wait_for(lambda: self.exists("begun"))
        p.terminate()
        state = self.finish(p)[2]
        self.assertTrue(self.exists("finished"))
        self.assertEqual((state["runs"], state["last_exit"]), (1, 0))

    def test_without_kill_tree_second_term_leaves_other_session_alive(self):
        p = self.start(self.tree(nested=True))
        self.wait_for(lambda: self.exists("grand.pid"))
        p.terminate()
        time.sleep(.1)
        self.assertIsNone(p.poll())
        p.terminate()
        state = self.finish(p)[2]
        self.assertEqual(state["last_exit"], 143)
        pids = [int(self.read(name)) for name in ("child.pid", "grand.pid")]
        try:
            for pid in pids:
                self.assertNotEqual(Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[0], "Z")
        finally:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_ctl_hold_and_resume(self):
        self.write("R/ctl.json", '{"op":"hold"}')
        p = self.start(self.target("open('ran','w').close()"), "--interval-ms", 10, "--max-runs", 1)
        self.wait_for(lambda: self.status().get("held"))
        self.assertFalse(self.exists("ran"))
        self.assertEqual(self.status()["runs"], 0)
        Path(self.d, "R/ctl.json").unlink()
        self.assertFalse(self.finish(p)[2]["held"])
        self.assertTrue(self.exists("ran"))

    def test_zero_interval_hold_does_not_rewrite_state(self):
        self.write("R/ctl.json", '{"op":"hold"}')
        p = self.start(self.target(), "--interval-ms", 0)
        self.wait_for(lambda: self.status().get("held"))
        path = Path(self.d, "R/run.json")
        mtimes = [path.stat().st_mtime_ns]
        until = time.monotonic() + .5
        while time.monotonic() < until:
            time.sleep(.01)
            mtimes.append(path.stat().st_mtime_ns)
        self.assertLessEqual(sum(a != b for a, b in zip(mtimes, mtimes[1:])), 1)
        self.assertEqual(self.status()["runs"], 0)
        p.terminate()
        self.finish(p)

    def test_busy_target_preserves_last_completed_target(self):
        first = self.target()
        second = self.inst({"argv": [PY, "-c", "import time; time.sleep(.4)"]}, "second.json")
        slot = Path(self.d, "slot.json")
        slot.symlink_to(first)
        p = self.start(slot, "--interval-ms", 150, "--max-runs", 2)
        self.wait_for(lambda: self.status().get("runs") == 1)
        slot.unlink()
        slot.symlink_to(second)
        self.wait_for(lambda: self.status().get("busy") and self.status().get("target") == second)
        self.assertEqual(self.status()["last_target"], first)
        self.assertEqual(self.finish(p)[2]["last_target"], second)

    def test_ctl_stop_retains_control_and_does_not_start(self):
        self.write("R/ctl.json", '{"op":"stop"}')
        p = self.start(self.target("open('ran','w').close()"))
        self.assertEqual(self.finish(p)[2]["runs"], 0)
        self.assertFalse(self.exists("ran"))
        self.assertTrue(self.exists("R/ctl.json"))

    def test_ctl_during_run_takes_effect_after_interval(self):
        p = self.start(self.target("import time; open('begun','w').close(); time.sleep(.2); open('finished','w').close()"),
                       "--interval-ms", 100)
        self.wait_for(lambda: self.exists("begun"))
        self.write("R/ctl.json", '{"op":"stop"}')
        self.assertEqual(self.finish(p)[2]["runs"], 1)
        self.assertTrue(self.exists("finished"))

    def test_invalid_ctl_and_unknown_op_are_ignored(self):
        for value in ('{', '{"op":"unknown"}', '[]'):
            self.write("R/ctl.json", value)
            p = self.start(self.target(), "--max-runs", 1)
            self.assertEqual(self.finish(p)[2]["runs"], 1)

    def test_busy_null_before_resolve_and_target_before_load(self):
        target = self.target()
        home = Path(self.d, "R")
        original_realpath, original_load = os.path.realpath, aos_inst.load
        seen = []
        def resolve(path, *args, **kwargs):
            if os.fspath(path) == target:
                seen.append(self.status().copy())
            return original_realpath(path, *args, **kwargs)
        def load(path, base):
            seen.append(self.status().copy())
            return original_load(path, base)
        with patch.object(aos_exec.os.path, "realpath", resolve), patch.object(aos_inst, "load", load):
            self.assertEqual(aos_run.main([target, "--home", str(home), "--max-runs", "1"]), 0)
        self.assertTrue(seen[0]["busy"])
        self.assertIsNone(seen[0]["target"])
        self.assertTrue(seen[1]["busy"])
        self.assertEqual(seen[1]["target"], target)

    def test_symlink_change_after_resolution_loads_reported_target(self):
        first = self.target("open('first','w').close()")
        second = self.inst({"argv": [PY, "-c", "open('second','w').close()"]}, "second.json")
        slot = Path(self.d, "slot.json")
        slot.symlink_to(first)
        def selected(path):
            self.assertEqual(path, first)
            slot.unlink()
            slot.symlink_to(second)
        self.assertEqual(aos_exec.run_target(str(slot), on_target=selected), (0, "child"))
        self.assertTrue(self.exists("first"))
        self.assertFalse(self.exists("second"))


if __name__ == "__main__":
    unittest.main()
