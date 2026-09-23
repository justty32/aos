"""新 exec cpu 的真行程測試：控制握手、信封、停止與崩潰對帳（cpu.md）。"""
import json
import os
import signal
import subprocess
import sys
import time
from unittest import mock

from _util import Base, LIB, PY
import aos_exec_cpu
import aos_home

CPU = os.path.join(os.path.dirname(LIB), "cli", "aos-cpu")


class CpuCase(Base):
    def setUp(self):
        super().setUp()
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 5}, "info.json")
        self.p = None
        self.workers = []
        self.addCleanup(self.cleanup_workers)

    def wait(self, condition, timeout=6):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = condition()
            if value:
                return value
            time.sleep(0.005)
        self.fail("等不到條件；cpu=%r" % (None if self.p is None else self.p.poll()))

    def cleanup_workers(self):
        for pid in self.workers:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def start(self, pipe=True, go=True, ready=True):
        log = open(os.path.join(self.d, "cpu.log"), "ab")
        self.addCleanup(log.close)
        p = subprocess.Popen([PY, CPU, self.d], stdin=subprocess.PIPE if pipe else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=log, start_new_session=True)
        self.p = p
        def cleanup():
            if p.poll() is None:
                p.kill()
            p.wait(timeout=5)
            for stream in (p.stdin, p.stdout):
                if stream is not None:
                    stream.close()
        self.addCleanup(cleanup)
        if pipe and go:
            self.control("go")
        if ready:
            self.wait(lambda: self.exists("state.json") and self.state().get("pid") == p.pid)
        return p

    def state(self):
        return json.loads(self.read("state.json"))

    def control(self, method):
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode())
        self.p.stdin.flush()

    def post(self, name="one", method="aos-exec", params=None, notify=False, raw=None):
        obj = {"jsonrpc": "2.0", "method": method}
        if not notify:
            obj["id"] = name
        if params is not None:
            obj["params"] = params
        if raw is None:
            aos_home.post_request(self.d, name + ".json", obj)
        else:
            pending = self.write("requests/%s.tmp" % name, raw)
            os.link(pending, os.path.join(self.d, "requests", name + ".json"))
            os.unlink(pending)
        return name

    def response(self, name="one"):
        self.wait(lambda: not self.exists("requests/%s.json" % name) and
                  self.exists("responses/%s.json" % name))
        return json.loads(self.read("responses/%s.json" % name))

    def job(self, source="pass", name="job.json", **extra):
        return self.inst(dict(argv=[PY, "-c", source], **extra), name)

    def sleeping(self):
        pidfile = os.path.join(self.d, "worker.pid")
        target = self.job("import os,time; open(%r,'w').write(str(os.getpid())); time.sleep(30)" % pidfile)
        self.post(params={"target": target})
        self.wait(lambda: self.exists("worker.pid") and self.read("worker.pid"))
        self.workers.append(int(self.read("worker.pid")))
        return target

    def stop(self):
        self.control("stop")
        self.assertEqual(self.p.wait(timeout=6), 0, self.read("cpu.log"))


class TestExecCpu(CpuCase):
    def test_go_handshake_and_eof_before_go_touches_nothing(self):
        os.unlink(os.path.join(self.d, "info.json"))
        self.start(go=False, ready=False)
        self.p.stdin.close()
        self.assertEqual(self.p.wait(timeout=4), 0)
        self.assertFalse(self.exists("state.json"))
        self.assertFalse(self.exists("requests"))

    def test_go_and_stop_in_one_chunk(self):
        self.start(go=False, ready=False)
        self.p.stdin.write(b'{"jsonrpc":"2.0","method":"go"}\n{"jsonrpc":"2.0","method":"stop"}\n')
        self.p.stdin.flush()
        self.assertEqual(self.p.wait(timeout=4), 0)
        self.assertIsNone(self.state()["current"])

    def test_no_pipe_does_not_wait_for_go(self):
        self.start(pipe=False)
        self.post("stop-test", "stop", notify=True)
        self.assertEqual(self.p.wait(timeout=4), 0)
        self.assertFalse(self.exists("requests/stop-test.json"))

    def test_pipe_eof_stops(self):
        self.start()
        self.p.stdin.close()
        self.assertEqual(self.p.wait(timeout=4), 0)

    def test_pipe_partial_lines_and_unknown_method(self):
        self.start()
        self.control("unknown")
        self.p.stdin.write(b'{"jsonrpc":"2.0","method":"sto')
        self.p.stdin.flush()
        self.post(params={"target": self.job()})
        self.assertEqual(self.response()["result"]["code"], 0)
        self.p.stdin.write(b'p"}\n')
        self.p.stdin.flush()
        self.assertEqual(self.p.wait(timeout=4), 0)

    def test_three_envelopes_and_errors_do_not_count_runs(self):
        self.start()
        cases = [("bad-json", "{", -32700),
                 ("bad-envelope", '{"id":"kept","method":3}', -32600),
                 ("unknown", '{"jsonrpc":"2.0","id":4,"method":"x"}', -32601),
                 ("params", '{"jsonrpc":"2.0","id":null,"method":"aos-exec","params":[]}', -32602)]
        for name, raw, code in cases:
            self.post(name, raw=raw)
            response = self.response(name)
            self.assertEqual(response["error"]["code"], code)
        self.assertEqual(self.response("bad-envelope")["id"], "kept")
        for i, (method, params) in enumerate((("x", None), ("aos-exec", []),
                                             ("aos-exec", {"target": self.job()}))):
            name = "notify-%d" % i
            self.post(name, method, params, notify=True)
            self.wait(lambda: not self.exists("requests/%s.json" % name))
            self.assertFalse(self.exists("responses/%s.json" % name))
        self.wait(lambda: self.state()["runs"] == 1)
        self.stop()

    def test_usage_and_params_validation(self):
        self.start()
        target = self.job()
        invalid = [{"target": target, "args": []}, {"target": "/not-here"},
                   {"target": self.d, "dir_target": "missing"}, {"target": target, "args": None},
                   {"target": target, "timeout_ms": True}, {"target": target, "stderr": 3},
                   {"target": target, "dir_target": 3}, {"args": []}]
        for i, params in enumerate(invalid):
            name = "bad-%d" % i
            self.post(name, params=params)
            error = self.response(name)["error"]
            self.assertEqual(error["code"], -32602)
            self.assertEqual(error["data"]["code"], "Usage" if i < 3 else "FieldTypeMismatch")
        self.assertEqual(self.state()["runs"], 0)
        self.stop()

    def test_missing_json_is_aos_result_and_counts(self):
        self.start()
        self.post(params={"target": "missing.json"})
        result = self.response()["result"]
        self.assertEqual((result["code"], result["kind"]), (1, "aos"))
        self.assertFalse(result["timed_out"])
        self.wait(lambda: self.state()["runs"] == 1)
        self.stop()

    def test_plain_target_args_stderr_and_inherited_streams(self):
        target = self.write("script", "#!/bin/sh\nread line || echo stdin-eof\nprintf '<%s>\\n' \"$@\"\necho stderr-ok >&2\n", executable=True)
        self.start()
        self.post(params={"target": target, "args": ["a b", ""], "stderr": "-"})
        self.assertEqual(self.response()["result"]["code"], 0)
        self.stop()
        log = self.read("cpu.log")
        self.assertIn("stdin-eof", log)
        self.assertIn("<a b>\n<>\n", log)
        self.assertIn("stderr-ok", log)
        self.assertEqual(self.p.stdout.read(), b"")

    def test_inst_stderr_override(self):
        self.start()
        self.post(params={"target": self.job("import sys; print('inst-error',file=sys.stderr)"), "stderr": "-"})
        self.response()
        self.stop()
        self.assertIn("inst-error", self.read("cpu.log"))

    def test_timeout_true_even_child_exits_zero_on_term(self):
        self.start()
        source = "import signal,time,sys; signal.signal(signal.SIGTERM,lambda *a:sys.exit(0)); time.sleep(30)"
        self.post(params={"target": self.job(source), "timeout_ms": 150})
        result = self.response()["result"]
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["stopped"])
        self.assertEqual(result["code"], 0)
        self.stop()

    def test_first_sigterm_finishes_work_and_leaves_next_request(self):
        gate = os.path.join(self.d, "release")
        marker = os.path.join(self.d, "started")
        source = "import os,time; open(%r,'w').close()\nwhile not os.path.exists(%r): time.sleep(.005)" % (marker, gate)
        self.start()
        target = self.job(source)
        self.post(params={"target": target, "timeout_ms": 3000})
        self.wait(lambda: self.exists("started"))
        self.p.send_signal(signal.SIGTERM)
        self.post("z-next", params={"target": self.job(name="next.json")})
        self.write("release", "")
        result = self.response()["result"]
        self.assertEqual(result["code"], 0)
        self.assertFalse(result["stopped"])
        self.assertEqual(self.p.wait(timeout=4), 0)
        self.assertTrue(self.exists("requests/z-next.json"))

    def test_two_signals_force_stop(self):
        self.start()
        self.sleeping()
        def switches():
            with open("/proc/%d/status" % self.p.pid) as source:
                return int(next(line.split(":")[1] for line in source if line.startswith("voluntary_ctxt_switches:")))
        before = switches()
        self.p.send_signal(signal.SIGTERM)
        # 真正經過幾轮等待／poll，讓第一次訊號被主人處理，再送第二次。
        self.wait(lambda: switches() >= before + 3)
        self.p.send_signal(signal.SIGINT)
        result = self.response()["result"]
        self.assertTrue(result["stopped"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["code"], 143)
        self.assertEqual(self.p.wait(timeout=4), 0)

    def test_killed_cpu_restart_publishes_interrupted(self):
        first = self.start()
        self.sleeping()
        first.kill()
        first.wait(timeout=4)
        self.start()
        error = self.response()["error"]
        self.assertEqual(error["code"], -32000)
        self.assertEqual(error["data"]["code"], "Interrupted")
        self.assertIsNone(self.state()["current"])
        self.stop()

    def test_control_fds_are_high_cloexec_and_not_in_work(self):
        self.start()
        source = "import os,json; print(json.dumps([n for n in os.listdir('/proc/self/fd') if int(n)>=64]))"
        self.post(params={"target": self.job(source, stdout="fds.json")})
        self.response()
        self.assertEqual(json.loads(self.read("fds.json")), [])
        with open("/proc/%d/fdinfo/64" % self.p.pid) as info:
            flags = int(next(line.split()[1] for line in info if line.startswith("flags:")), 8)
        self.assertTrue(flags & os.O_CLOEXEC)
        self.stop()

    def test_bad_home_and_usage_exit_codes(self):
        self.inst({"_metainfo": {"_type": "wrong", "_version": 1}}, "info.json")
        result = subprocess.run([PY, CPU, self.d], stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith(b"aos-cpu: NotAHome:"))
        result = subprocess.run([PY, CPU, self.d, "extra"], capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_response_write_failure_preserves_current_and_request(self):
        home = self.d
        os.makedirs(os.path.join(home, "requests"))
        os.makedirs(os.path.join(home, "responses", "one.json"))
        self.post(params={"target": self.job()})
        self.start(ready=False)
        self.assertEqual(self.p.wait(timeout=4), 1)
        self.assertEqual(self.state()["current"]["name"], "one.json")
        self.assertTrue(self.exists("requests/one.json"))
        self.assertEqual(self.state()["runs"], 0)

    def test_stop_files_take_priority_and_all_are_removed(self):
        aos_home.ensure_queue(self.d)
        self.post("a-job", params={"target": self.job()})
        self.post("stop-a", "stop", notify=True)
        self.post("stop-b", "stop", notify=True)
        self.start(ready=False)
        self.assertEqual(self.p.wait(timeout=4), 0)
        self.assertTrue(self.exists("requests/a-job.json"))
        self.assertFalse(self.exists("requests/stop-a.json"))
        self.assertFalse(self.exists("requests/stop-b.json"))
        self.assertEqual(self.state()["runs"], 0)

    def test_ack_removes_response_and_ack_file(self):
        self.start()
        self.post(params={"target": self.job()})
        self.response()
        self.post("ack-taken", "ack", {"name": "one.json"}, notify=True)
        self.wait(lambda: not self.exists("requests/ack-taken.json"))
        self.assertFalse(self.exists("responses/one.json"))
        self.post("ack-missing", "ack", {"name": "never-existed.json"}, notify=True)
        self.wait(lambda: not self.exists("requests/ack-missing.json"))
        self.assertFalse(self.exists("responses/ack-missing.json"))
        self.stop()

    def test_invalid_reserved_prefix_replies_without_execution(self):
        self.start()
        self.post("stop-wrong", params={"target": self.job()})
        self.assertEqual(self.response("stop-wrong")["error"]["code"], -32600)
        self.post("ack-wrong", params={}, notify=True)
        self.wait(lambda: not self.exists("requests/ack-wrong.json"))
        self.assertFalse(self.exists("responses/ack-wrong.json"))
        self.assertEqual(self.state()["runs"], 0)
        self.stop()

    def test_default_timeout_from_info(self):
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1},
                   "poll_ms": 5, "timeout_ms": 80}, "info.json")
        self.start()
        self.post(params={"target": self.job("import time; time.sleep(30)")})
        self.assertTrue(self.response()["result"]["timed_out"])
        self.stop()

    def test_sigpipe_is_ignored(self):
        self.start()
        self.p.send_signal(signal.SIGPIPE)
        self.post(params={"target": self.job()})
        self.assertEqual(self.response()["result"]["code"], 0)
        self.stop()

    def test_recovery_keeps_preexisting_response_without_rerun(self):
        aos_home.ensure_queue(self.d)
        self.post(params={"target": self.job("raise SystemExit(9)")})
        saved = {"jsonrpc": "2.0", "id": "one", "result": {"code": 4}}
        aos_home.write_json(os.path.join(self.d, "responses", "one.json"), saved)
        aos_home.write_state(self.d, {"current": {"name": "one.json", "id": "one", "notify": False}, "runs": 7})
        self.start()
        self.assertEqual(self.response(), saved)
        self.assertEqual(self.state()["runs"], 7)
        self.stop()

    def test_signal_handler_only_sets_flags(self):
        with mock.patch("os.fstat", return_value=mock.Mock(st_mode=0)):
            control = aos_exec_cpu.Control()
        control._signal(signal.SIGTERM, None)
        self.assertFalse(control.stopping)
        self.assertFalse(control.poll())
        self.assertTrue(control.stopping)
        control._signal(signal.SIGTERM, None)
        self.assertTrue(control.poll())
