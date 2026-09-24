"""daemon.md §2 的非同步 exec 入口、控制 pipe 與同 session 的 process group。"""
import json
import os
import signal
import sys
import time
from unittest import mock

import aos_exec
from _util import Base


class SpawnTargetTests(Base):
    def spawn(self, target, **kw):
        child = aos_exec.spawn_target(target, **kw)
        self.addCleanup(self.reap, child.process)
        return child

    @staticmethod
    def reap(proc):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)
        for pipe in (proc.stdin, proc.stdout):
            pipe.close()

    def wait(self, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            value = predicate()
            if value:
                return value
            time.sleep(.005)
        self.fail("等待子程式狀態逾時")

    def job(self, body, **fields):
        return self.inst(dict(argv=[sys.executable, "-c", body], **fields), "inst.json")

    def bad(self, target, code):
        with self.assertRaises(aos_exec.SpawnError) as cm:
            aos_exec.spawn_target(target)
        self.assertEqual(cm.exception.code, code)
        self.assertTrue(cm.exception.msg)

    def test_pipe_waits_for_caller_go(self):
        marker = os.path.join(self.d, "marker")
        target = self.job("import sys,pathlib; line=sys.stdin.readline(); "
                          "pathlib.Path(%r).write_text(line) if line else None" % marker)
        child = self.spawn(target)
        self.assertFalse(os.path.exists(marker))
        self.assertIsNone(child.process.poll())
        os.write(child.process.stdin.fileno(), b'{"jsonrpc":"2.0","method":"go"}\n')
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (0, "child"))
        self.assertEqual(json.loads(self.read("marker"))["method"], "go")

    def test_eof_before_go(self):
        marker = os.path.join(self.d, "marker")
        target = self.job("import sys,pathlib; "
                          "pathlib.Path(%r).touch() if sys.stdin.readline() else None" % marker)
        child = self.spawn(target)
        child.process.stdin.close()
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (0, "child"))
        self.assertFalse(os.path.exists(marker))

    def test_same_session_distinct_group_and_cloexec(self):
        child = self.spawn(self.job("import sys; sys.stdin.readline()"))
        self.assertEqual(os.getsid(child.process.pid), os.getsid(0))
        self.assertEqual(os.getpgid(child.process.pid), child.process.pid)
        for pipe in (child.process.stdin, child.process.stdout):
            self.assertFalse(os.get_inheritable(pipe.fileno()))
            self.assertFalse(os.get_blocking(pipe.fileno()))

    def test_plain_target_and_pipe_output(self):
        target = self.write("child", "#!/bin/sh\nread value\nprintf '%s' \"$value\"\n", executable=True)
        child = self.spawn(target)
        os.write(child.process.stdin.fileno(), b"hello\n")
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(os.read(child.process.stdout.fileno(), 100), b"hello")
        self.assertEqual(child.finish(), (0, "child"))

    def test_directory_base_and_envs(self):
        self.inst({"argv": [sys.executable, "-c", "import os,sys; "
                             "assert os.getcwd()==%r; assert os.environ['TEST_SPAWN']=='ok'" % self.d],
                   "envs": {"TEST_SPAWN": "ok"}, "exit": "status"})
        child = self.spawn(self.d)
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (0, "child"))
        self.assertEqual(self.read("status"), "0\n")

    def test_stderr_and_exit_append(self):
        self.write("err", "before\n")
        self.write("status", "100\n")
        target = self.job("import sys; sys.stderr.write('after\\n'); sys.exit(7)",
                           stderr={"$opt": "append", "$val": "err"},
                           exit={"$opt": "append", "$val": "status"})
        child = self.spawn(target)
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (7, "child"))
        self.assertEqual(self.read("err"), "before\nafter\n")
        self.assertEqual(self.read("status"), "100\n7\n")

    def test_finish_signal(self):
        child = self.spawn(self.job("import sys; sys.stdin.readline()", exit="status"))
        child.process.send_signal(signal.SIGTERM)
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (143, "child"))
        self.assertEqual(self.read("status"), "143\n")

    def test_explicit_stdin_stdout_rejected_even_empty(self):
        for key in ("stdin", "stdout"):
            for value in ("", "some-file", {"$opt": "inherit"}):
                with self.subTest(key=key, value=value):
                    self.bad(self.job("pass", **{key: value}), "Usage")

    def test_top_reference_explicit_stream_rejected(self):
        self.inst({"job": {"argv": [sys.executable, "-c", "pass"], "stdin": ""}}, "source.json")
        target = self.inst({"$ref": "source.json#/job"}, "inst.json")
        self.bad(target, "Usage")

    def test_top_reference_keeps_document_and_relative_position(self):
        self.inst({"job": {"argv": [{"$ref": "", "$at": "/python"}, "-c",
                                    {"$ref": "", "$at": "../../body"}],
                           "body": "raise SystemExit(8)"}, "python": sys.executable}, "source.json")
        target = self.inst({"$ref": "source.json#/job"}, "inst.json")
        child = self.spawn(target)
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (8, "child"))

    def test_root_reference_keeps_current_document(self):
        self.inst({"argv": [{"$ref": "", "$at": "/python"}, "-c", "pass"],
                   "python": sys.executable}, "source.json")
        child = self.spawn(self.inst({"$ref": "source.json"}, "inst.json"))
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (0, "child"))

    def test_cwd_and_exit_mkdir_stderr_merge(self):
        target = self.job("import sys; sys.stderr.write('merged')",
                           cwd={"$opt": "mkdir", "$val": "work"},
                           stderr={"$opt": "merge"},
                           exit={"$opt": "mkdir", "$val": "out/status"})
        child = self.spawn(target)
        self.wait(lambda: child.process.poll() is not None)
        self.assertEqual(child.finish(), (0, "child"))
        self.assertEqual(os.read(child.process.stdout.fileno(), 100), b"merged")
        self.assertEqual(self.read("work/out/status"), "0\n")

    def test_invalid_nul_path_is_spawn_failed(self):
        self.bad(self.job("pass", cwd={"$opt": "mkdir", "$val": "bad\0dir"}), "SpawnFailed")

    def test_missing_json_and_bad_json(self):
        self.bad(os.path.join(self.d, "missing.json"), "SpawnFailed")
        self.bad(self.write("bad.json", "{"), "SpawnFailed")

    def test_missing_target_is_spawn_failed(self):
        self.bad(os.path.join(self.d, "missing"), "SpawnFailed")
        self.bad(self.d, "SpawnFailed")

    def test_missing_program_no_exit_written(self):
        target = self.inst({"argv": ["/no-such-daemon-child"], "exit": "status"}, "inst.json")
        self.bad(target, "SpawnFailed")
        self.assertFalse(self.exists("status"))

    def test_nonexecutable_no_child(self):
        self.bad(self.write("not-executable", "#!/bin/sh\nexit 0\n"), "SpawnFailed")

    def test_preflight_missing_cwd(self):
        self.bad(self.job("pass", cwd="missing-dir"), "SpawnFailed")

    def test_child_does_not_inherit_other_control_write_end(self):
        first = self.spawn(self.job("import sys; sys.stdin.readline()"))
        second = self.spawn(self.job("import sys; sys.stdin.readline()"))
        first.process.stdin.close()
        self.wait(lambda: first.process.poll() is not None)
        self.assertIsNone(second.process.poll())
        self.assertEqual(first.finish(), (0, "child"))

    def test_unreadable_inst_is_spawn_failed(self):
        target = self.job("pass")
        with mock.patch("builtins.open", side_effect=PermissionError("unreadable target")):
            self.bad(target, "SpawnFailed")
