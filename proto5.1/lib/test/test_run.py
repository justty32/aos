"""aos-run 真進程：事件、完成後計時、TERM／timeout、nested tool CPU 與換槽鎖。"""
import fcntl
import os
from pathlib import Path
import subprocess
import time
import unittest

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

    def start(self, target, *args):
        log = open(os.path.join(self.d, "events"), "wb")
        self.addCleanup(log.close)
        p = subprocess.Popen([PY, CLI, str(target), *map(str, args), "--status-fd", str(log.fileno())],
                             pass_fds=(log.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
        return out, err, self.read("events").splitlines()

    def target(self, script="pass", **kwargs):
        return self.inst(dict(argv=[PY, "-c", script], **kwargs), "job.json")

    def test_max_runs_and_events(self):
        p = self.start(self.target("raise SystemExit(7)"), "--max-runs", 2, "--interval-ms", 0)
        out, err, events = self.finish(p)
        self.assertEqual((out, err), ("", ""))
        self.assertEqual(events, ["ready", "start #1", "done #1 exit=7 kind=child",
                                  "start #2", "done #2 exit=7 kind=child", "stop max-runs"])

    def test_repeatable_stop_exit(self):
        p = self.start(self.target("raise SystemExit(101)"), "--stop-exit", 100, "--stop-exit", 101)
        self.assertEqual(self.finish(p)[2][-2:], ["done #1 exit=101 kind=child", "stop stop-exit"])

    def test_aos_failures_repeat_and_kind_is_preserved(self):
        p = self.start(os.path.join(self.d, "missing.json"), "--max-runs", 2, "--interval-ms", 0)
        self.assertEqual(self.finish(p)[2][2:5], ["done #1 exit=125 kind=aos", "start #2",
                                               "done #2 exit=125 kind=aos"])

    def test_stop_exit_125_matches_aos_failure(self):
        p = self.start(os.path.join(self.d, "missing.json"), "--stop-exit", 125)
        self.assertEqual(self.finish(p)[2][-2:], ["done #1 exit=125 kind=aos", "stop stop-exit"])

    def test_bad_utf8_is_reported_as_aos_failure(self):
        target = os.path.join(self.d, "bad.json")
        Path(target).write_bytes(b"\xff")
        p = self.start(target, "--max-runs", 1)
        _, err, events = self.finish(p)
        self.assertIn("JsonSyntax", err)
        self.assertNotIn("Traceback", err)
        self.assertIn("done #1 exit=125 kind=aos", events)

    def test_nul_argv_is_reported_as_aos_failure(self):
        target = self.inst({"argv": ["bad\0command"]}, "job.json")
        p = self.start(target, "--max-runs", 1)
        _, err, events = self.finish(p)
        self.assertIn("FieldTypeMismatch", err)
        self.assertNotIn("Traceback", err)
        self.assertIn("done #1 exit=125 kind=aos", events)

    def test_missing_plain_target_stops_usage(self):
        p = self.start(os.path.join(self.d, "missing"))
        self.assertEqual(self.finish(p, 2)[2][-2:], ["done #1 exit=2 kind=usage", "stop usage"])

    def test_interval_starts_after_completion(self):
        script = "import time; f=open('times','a'); f.write(str(time.monotonic())+'\\n'); f.close(); time.sleep(.16)"
        p = self.start(self.target(script), "--max-runs", 2, "--interval-ms", 180)
        self.finish(p)
        times = list(map(float, self.read("times").splitlines()))
        self.assertGreaterEqual(times[1] - times[0], 0.32)

    def test_zero_timeout_does_not_cut_off(self):
        p = self.start(self.target("import time; time.sleep(.12)"), "--timeout-ms", 0, "--max-runs", 1)
        self.assertIn("done #1 exit=0 kind=child", self.finish(p)[2])

    def test_no_unrequested_flags(self):
        for flag in ("--from-start", "--time-limit-ms", "--stop-on-error", "--dir-target", "--stderr"):
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
        self.wait_for(lambda: "done #1" in self.read("events"))
        start = time.monotonic()
        p.terminate()
        self.assertEqual(self.finish(p)[2][-1], "stop signal")
        self.assertLess(time.monotonic() - start, 1)

    def test_default_target_directory(self):
        self.inst({"argv": [PY, "-c", "pass"]})
        r = subprocess.run([PY, CLI, "--max-runs", "1"], cwd=self.d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_plain_executable(self):
        target = self.write("job", "#!/bin/sh\necho plain\n", executable=True)
        p = self.start(target, "--max-runs", 1)
        self.assertEqual(self.finish(p)[0], "plain\n")

    def test_broken_status_pipe_does_not_abort_job(self):
        read, write = os.pipe()
        os.close(read)
        try:
            r = subprocess.run([PY, CLI, self.target(), "--max-runs", "1", "--status-fd", str(write)],
                               pass_fds=(write,), capture_output=True, text=True)
        finally:
            os.close(write)
        self.assertEqual(r.returncode, 0, r.stderr)

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
        p = self.start(self.tree())
        self.wait_for(lambda: self.exists("grand.pid"))
        start = time.monotonic()
        p.terminate()
        events = self.finish(p)[2]
        self.assertGreaterEqual(time.monotonic() - start, 1.8)
        self.assertEqual(events[-2:], ["done #1 exit=137 kind=child", "stop signal"])
        self.assert_tree_dead()

    def test_parent_exits_on_term_but_grandchild_still_killed(self):
        p = self.start(self.tree(ignore_parent=False))
        self.wait_for(lambda: self.exists("grand.pid"))
        p.terminate()
        self.assertIn("done #1 exit=143 kind=child", self.finish(p)[2])
        self.assert_tree_dead()

    def test_timeout_kills_child_and_grandchild(self):
        p = self.start(self.tree(), "--timeout-ms", 400, "--max-runs", 1)
        self.assertIn("done #1 exit=137 kind=child", self.finish(p)[2])
        self.assert_tree_dead()

    def test_term_crosses_tool_cpu_run_inst_session(self):
        p = self.start(self.tree(nested=True))
        self.wait_for(lambda: self.exists("grand.pid"))
        p.terminate()
        self.finish(p)
        self.assert_tree_dead()
        self.assertFalse(self.exists("result.json"))

    def test_timeout_crosses_tool_cpu_run_inst_session(self):
        p = self.start(self.tree(nested=True), "--timeout-ms", 600, "--max-runs", 1)
        self.finish(p)
        self.assert_tree_dead()

    def test_target_lock_prevents_old_file_load(self):
        target = self.target("open('old','w').close()")
        with open(target + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            p = self.start(target, "--max-runs", 1)
            self.wait_for(lambda: "ready" in self.read("events"))
            time.sleep(.1)
            self.assertEqual(self.read("events").splitlines(), ["ready"])
            self.target("open('new','w').close()")
            fcntl.flock(lock, fcntl.LOCK_UN)
            self.finish(p)
        self.assertFalse(self.exists("old"))
        self.assertTrue(self.exists("new"))

    def test_term_while_waiting_target_lock(self):
        target = self.target()
        with open(target + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            p = self.start(target)
            self.wait_for(lambda: "ready" in self.read("events"))
            p.terminate()
            self.assertEqual(self.finish(p)[2], ["ready", "stop signal"])

    def test_yield_finishes_active_run_then_waits_until_marker_cleared(self):
        target = self.target("import time; open('begun','a').write('x'); time.sleep(.35); "
                             "open('completed','a').write('x')")
        with open(target + ".lock", "w+b", buffering=0) as lock:
            p = self.start(target, "--interval-ms", 0, "--max-runs", 2)
            self.wait_for(lambda: self.exists("begun"))
            # kernel 寫 Y 不需等 active invocation 解鎖；它不會終止正在做的工作。
            lock.write(b"Y")
            self.wait_for(lambda: "done #1" in self.read("events"))
            time.sleep(.15)
            self.assertEqual(self.read("completed"), "x")
            self.assertEqual(self.read("begun"), "x")
            self.assertNotIn("start #2", self.read("events"))
            fcntl.flock(lock, fcntl.LOCK_EX)
            lock.truncate(0)
            fcntl.flock(lock, fcntl.LOCK_UN)
            events = self.finish(p)[2]
        self.assertEqual(self.read("completed"), "xx")
        self.assertEqual(events, ["ready", "start #1", "done #1 exit=0 kind=child",
                                  "start #2", "done #2 exit=0 kind=child", "stop max-runs"])

    def test_term_while_waiting_yield_marker(self):
        target = self.target()
        self.write("job.json.lock", "Y")
        p = self.start(target)
        self.wait_for(lambda: "ready" in self.read("events"))
        time.sleep(.1)
        start = time.monotonic()
        p.terminate()
        self.assertEqual(self.finish(p)[2], ["ready", "stop signal"])
        self.assertLess(time.monotonic() - start, 1)


if __name__ == "__main__":
    unittest.main()
