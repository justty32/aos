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

    def start(self, pipe=True, go=True, ready=True, bootstrap=None):
        log = open(os.path.join(self.d, "cpu.log"), "ab")
        self.addCleanup(log.close)
        command = [PY, CPU, self.d]
        if bootstrap is not None:
            setup = "import sys, os, time\nfrom pathlib import Path\n" + \
                    "sys.path.insert(0, %r)\nimport aos_exec, aos_exec_cpu, aos_home\n" % LIB
            command = [PY, "-c", setup + bootstrap + "\nsys.exit(aos_exec_cpu.main([%r]))" % self.d]
        p = subprocess.Popen(command, stdin=subprocess.PIPE if pipe else subprocess.DEVNULL,
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
        # Freeze only exec's monotonic clock until the handler is installed.
        bootstrap = """
from types import SimpleNamespace
clock = Path(%r)
aos_exec.time = SimpleNamespace(monotonic=lambda: float(clock.read_text()), sleep=time.sleep)
""" % os.path.join(self.d, "clock")
        self.write("clock", "10")
        self.start(bootstrap=bootstrap)
        source = "import signal,time,sys; signal.signal(signal.SIGTERM,lambda *a:(open('term-sent','w').close(),sys.exit(0))); open('ready','w').close(); time.sleep(30)"
        self.post(params={"target": self.job(source), "timeout_ms": 150})
        self.wait(lambda: self.exists("ready"))
        aos_home.write_json(os.path.join(self.d, "clock"), 10.151)
        self.wait(lambda: self.exists("term-sent"))
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
        self.start(bootstrap=self.signal_observer())
        source = """
import os, signal, time
if os.fork() == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    open('descendant.pid', 'w').write(str(os.getpid()))
    while True: time.sleep(.01)
open('worker.pid', 'w').write(str(os.getpid()))
while True: time.sleep(.01)
"""
        self.post(params={"target": self.job(source)})
        self.wait(lambda: self.exists("worker.pid") and self.read("worker.pid"))
        self.workers.append(int(self.read("worker.pid")))
        self.wait(lambda: self.exists("descendant.pid") and self.read("descendant.pid"))
        descendant = int(self.read("descendant.pid"))
        self.p.send_signal(signal.SIGTERM)
        self.wait(lambda: self.exists("first-signal"))
        self.p.send_signal(signal.SIGINT)
        result = self.response()["result"]
        self.assertTrue(result["stopped"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["code"], 143)
        self.assertEqual(self.p.wait(timeout=6), 0)
        def dead():
            try:
                os.kill(descendant, 0)
                with open("/proc/%d/stat" % descendant) as stream:
                    return stream.read().rsplit(")", 1)[1].split()[0] == "Z"
            except (ProcessLookupError, FileNotFoundError):
                return True
        self.wait(dead)  # Before cleanup_workers can mask a missing group KILL.

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
        # 09-24 fix-r4：DIR 省略＝目前資料夾，讀到的是同一個壞 info。
        result = subprocess.run([PY, CPU], cwd=self.d, stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith(b"aos-cpu: NotAHome:"))

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

    def test_bad_go_id_does_not_touch_home(self):
        os.unlink(os.path.join(self.d, "info.json"))
        self.start(go=False, ready=False)
        self.p.stdin.write(b'{"jsonrpc":"2.0","method":"go","id":{}}\n')
        self.p.stdin.close()
        self.assertEqual(self.p.wait(timeout=6), 0)
        self.assertFalse(self.exists("requests"))
        self.assertFalse(self.exists("state.json"))
        self.assertIn("aos-cpu: BadControl:", self.read("cpu.log"))

    def bad_stop(self, ident):
        self.start()
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "stop", "id": ident}) + "\n").encode())
        self.p.stdin.flush()
        self.wait(lambda: "BadControl" in self.read("cpu.log"))
        self.post(params={"target": self.job()})
        self.assertEqual(self.response()["result"]["code"], 0)
        self.stop()

    def test_stop_with_valid_id_is_ignored(self):
        self.bad_stop("request-id")

    def test_stop_with_object_id_is_ignored(self):
        self.bad_stop({})

    def test_control_envelope_validation(self):
        for value in ([], {}, {"jsonrpc": "1.0", "method": "go"},
                      {"jsonrpc": "2.0", "method": 1},
                      {"jsonrpc": "2.0", "method": "go", "id": True}):
            with self.subTest(value=value):
                self.assertIsNotNone(aos_exec_cpu._control_error(value))
        for ident in ("id", 1, 1.5, None):
            self.assertIsNone(aos_exec_cpu._control_error({"jsonrpc": "2.0", "method": "go", "id": ident}))
        self.assertIsNotNone(aos_exec_cpu._control_error({"jsonrpc": "2.0", "method": "stop", "id": None}))

    def signal_observer(self):
        return """
original_poll = aos_exec_cpu.Control.poll
marker = Path(%r)
def observed_poll(control, process=None):
    result = original_poll(control, process)
    if control.stopping and not control.force:
        marker.touch()
    if control.force:
        marker.with_name("second-signal").touch()
    return result
aos_exec_cpu.Control.poll = observed_poll
""" % os.path.join(self.d, "first-signal")

    def test_exit_before_second_signal_keeps_result(self):
        bootstrap = self.signal_observer() + """
observed = aos_exec_cpu.Control.poll
home = Path(%r)
def gated_poll(control, process=None):
    result = observed(control, process)
    if control.stopping and not control.force and process is not None:
        process.wait(timeout=6)
        (home / 'job-exited').touch()
        until = time.monotonic() + 6
        while not (home / 'release-result').exists():
            if time.monotonic() >= until: raise RuntimeError('result gate timed out')
            time.sleep(.005)
        return observed(control, process)
    return result
aos_exec_cpu.Control.poll = gated_poll
""" % self.d
        self.start(bootstrap=bootstrap)
        source = "import os,time; open('ready','w').close()\nwhile not os.path.exists('release-job'): time.sleep(.005)\nraise SystemExit(7)"
        self.post(params={"target": self.job(source)})
        self.wait(lambda: self.exists("ready"))
        self.p.send_signal(signal.SIGTERM)
        self.wait(lambda: self.exists("first-signal"))
        self.write("release-job", "")
        self.wait(lambda: self.exists("job-exited"))
        self.assertFalse(self.exists("responses/one.json"))
        self.p.send_signal(signal.SIGINT)
        self.write("release-result", "")
        result = self.response()["result"]
        self.assertTrue(self.exists("second-signal"))
        self.assertEqual(result["code"], 7)
        self.assertFalse(result["stopped"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(self.p.wait(timeout=6), 0)

    def test_completion_and_reconciliation_crash_windows_do_not_rerun(self):
        # Real crashes in both normal completion and the subsequent reconciliation.
        for after_unlink in (False, True):
            with self.subTest(after_unlink=after_unlink):
                name = "after" if after_unlink else "before"
                aos_home.ensure_queue(self.d)
                effect = name + ".effect"
                self.post(name, params={"target": self.job("open(%r,'a').write('once\\n')" % effect)})
                inject = """
request = Path(%r)
original_unlink = os.unlink
def crash_unlink(path, *args, **kwargs):
    if Path(path) == request:
        if %r: original_unlink(path, *args, **kwargs)
        os._exit(73)
    return original_unlink(path, *args, **kwargs)
os.unlink = crash_unlink
""" % (os.path.join(self.d, "requests", name + ".json"), after_unlink)
                self.start(ready=False, bootstrap=inject)
                self.assertEqual(self.p.wait(timeout=6), 73)
                saved = self.read("responses/" + name + ".json")
                self.assertEqual(self.state()["current"]["name"], name + ".json")
                self.assertEqual(self.exists("requests/" + name + ".json"), not after_unlink)
                # Crash recovery itself: before request deletion, or before clearing current.
                if after_unlink:
                    inject = """
def crash_state(home, state):
    os._exit(74)
aos_home.write_state = crash_state
"""
                self.start(ready=False, bootstrap=inject)
                self.assertEqual(self.p.wait(timeout=6), 74 if after_unlink else 73)
                self.start()
                self.assertEqual(self.response(name), json.loads(saved))
                self.assertIsNone(self.state()["current"])
                self.assertEqual(self.read(effect), "once\n")
                self.stop()

    def test_legal_go_ids_and_bad_lines(self):
        for ident in ("id", 1, 1.5, None):
            with self.subTest(ident=ident):
                self.start(go=False, ready=False)
                bad = [b'[]', b'{', b'{"jsonrpc":"2.0","method":1}',
                       b'{"jsonrpc":"2.0","method":"go","id":true}',
                       b'{"jsonrpc":"2.0","method":"go","id":NaN}']
                before = self.read("cpu.log").count("BadControl")
                self.p.stdin.write(b"\n".join(bad) + b"\n" +
                                   (json.dumps({"jsonrpc": "2.0", "method": "go", "id": ident}) + "\n").encode())
                self.p.stdin.flush()
                self.wait(lambda: self.exists("state.json") and self.state()["pid"] == self.p.pid)
                self.stop()
                self.assertEqual(self.read("cpu.log").count("BadControl") - before, len(bad))
