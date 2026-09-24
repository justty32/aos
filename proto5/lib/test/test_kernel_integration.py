"""kernel.md 的真 daemon＋exec cpu 整合：鏈、派工、回收、CLI 與交接。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import aos_client
import aos_home
from _kernel_util import KernelCase, CLI, PY, read_json, wait_for, isolated_test


class KernelIntegration(KernelCase):
    def test_init_boot_recurring_once_rm_and_clean_stop(self):
        self.setup_running()
        target = self.job()
        self.add(target, "repeat")
        wait_for(lambda: self.state().get("procs", {}).get("repeat", {}).get("runs", 0) >= 3)
        once = self.call("add", {"name": "once", "target": target, "once": True})
        self.assertEqual(once["result"]["code"], 0)
        self.assertEqual(once["result"]["kind"], "child")
        self.assertNotIn("once", self.state()["procs"])
        self.assertEqual(self.call("rm", {"name": "repeat"})["result"], {"name": "repeat"})
        wait_for(lambda: "repeat" not in self.state()["procs"])
        self.kernel_stop()
        self.daemon_stop()
        self.assertEqual(self.state()["phase"], "stopped")
        self.assertEqual(self.dstate()["children"], {})

    def test_repeat_boot_replaces_kernel_cpu_and_old_chain_tick_self_destructs(self):
        self.setup_running()
        old = self.state()
        old_pid = self.dstate()["children"]["k"]["pid"]
        inst = (self.home / "cpus" / "0" / "inst.json").read_bytes()
        info = (self.home / "cpus" / "0" / "info.json").read_bytes()
        self.boot()
        new = self.state()
        self.assertNotEqual(new["chain"], old["chain"])
        self.assertNotEqual(self.dstate()["children"]["k"]["pid"], old_pid)
        self.assertEqual((self.home / "cpus" / "0" / "inst.json").read_bytes(), inst)
        self.assertEqual((self.home / "cpus" / "0" / "info.json").read_bytes(), info)
        self.good_cli("tick", self.home, "--chain", old["chain"], "--seq", "999")
        self.assertNotEqual(self.state()["last_seq"], 999)
        self.assertFalse((self.home / "cpus" / "k" / "requests" / ("k-%s-1000.json" % old["chain"])).exists())
        self.kernel_stop()

    def test_llm_pool_and_envs_copy_to_new_home(self):
        envs = {"POOL_TEST": "llm-only", "PATH": {"$env": "PATH"}}
        self.setup_running(cpus={"k": {"pool": "kernel"}, "0": {}, "llm": {"pool": "llm", "envs": envs}})
        inst = read_json(self.home / "cpus" / "llm" / "inst.json")
        self.assertEqual(inst["envs"], envs)
        output = self.root / "pool-output.json"
        target = self.job("import json,os; print(json.dumps({'parent':os.getppid(),'env':os.getenv('POOL_TEST')}))",
                          stdout=str(output))
        response = self.call("add", {"target": target, "name": "llm-once", "pool": "llm", "once": True})
        self.assertEqual(response["result"]["code"], 0)
        answer = read_json(output)
        self.assertEqual(answer["env"], "llm-only")
        self.assertEqual(answer["parent"], self.dstate()["children"]["llm"]["pid"])
        self.kernel_stop()

    def test_killed_busy_cpu_recovers_interrupted_once(self):
        if not os.environ.get("AOS_TEST_SUBREAPER"):
            result = isolated_test(__name__, type(self).__name__, self._testMethodName)
            self.assertEqual(result.returncode, 0, result.stderr)
            return
        self.setup_running()
        marker = self.root / "worker.pid"
        target = self.job("import os,time; open(%r,'w').write(str(os.getpid())); time.sleep(30)" % str(marker))
        request = aos_client.submit(self.home, "add", {"target": target, "name": "interrupted", "once": True})
        wait_for(lambda: marker.exists() and marker.read_text())
        worker = int(marker.read_text())
        self.groups.add(worker)
        cpu_pid = self.dstate()["children"]["0"]["pid"]
        os.kill(cpu_pid, signal.SIGKILL)
        response = aos_client.wait_response(self.home, request, timeout_ms=6000, poll_ms=5)
        self.assertEqual(response["error"]["data"]["code"], "Interrupted")
        aos_client.ack(self.home, request)
        self.assertNotIn("interrupted", self.state()["procs"])
        self.assertNotEqual(self.dstate()["children"]["0"]["pid"], cpu_pid)
        os.killpg(worker, signal.SIGKILL)
        os.waitpid(worker, 0)
        self.groups.remove(worker)
        self.kernel_stop()

    def test_bad_after_done_exit_and_logs(self):
        self.setup_running(bad_after=2, done_exit=7)
        self.add(self.root / "missing.json", "bad")
        self.add(self.job("raise SystemExit(7)"), "done")
        wait_for(lambda: self.state().get("procs", {}).get("bad", {}).get("status") == "bad")
        wait_for(lambda: self.state().get("procs", {}).get("done", {}).get("status") == "done")
        state = self.state()
        self.assertEqual((state["procs"]["bad"]["runs"], state["procs"]["bad"]["fails"]), (2, 2))
        self.assertEqual((state["procs"]["done"]["runs"], state["procs"]["done"]["fails"]), (1, 0))
        def logged_events():
            path = self.home / "kernel.log"
            if not path.exists():
                return []
            # append 可能還沒完成；只解析完整行，下次輪詢再讀尾端。
            return [event for line in path.read_text().splitlines(keepends=True)
                    if line.endswith("\n") for event in json.loads(line)["events"]]
        def completed_log():
            events = logged_events()
            responses = [e for e in events if e["event"] == "response" and e["proc"] in ("bad", "done")]
            return events if len(responses) == 3 and any(e["event"] == "bad" for e in events) else None
        events = wait_for(completed_log)
        self.assertEqual([e for e in events if e["event"] == "bad"],
                         [{"event": "bad", "proc": "bad", "fails": 2, "bad_after": 2}])
        for name, code, kind, count in (("bad", 1, "aos", 2), ("done", 7, "child", 1)):
            responses = [e["response"] for e in events if e["event"] == "response" and e["proc"] == name]
            self.assertEqual(len(responses), count)
            for response in responses:
                ms = response["result"]["ms"]
                self.assertIs(type(ms), int)
                self.assertGreaterEqual(ms, 0)
                self.assertEqual(response, {"result": {"code": code, "kind": kind,
                                 "timed_out": False, "stopped": False, "ms": ms}})
        self.kernel_stop()

    def test_info_reload_tick_timing_and_add_defaults_are_immutable(self):
        self.setup_running(interval_ms=500)
        target = self.job()
        self.add(target, "old")
        self.info.update(tick_ms=120, interval_ms=0)
        self.write(self.home / "info.json", self.info)
        self.add(target, "new")
        self.assertEqual(self.state()["procs"]["old"]["interval_ms"], 500)
        self.assertEqual(self.state()["procs"]["new"]["interval_ms"], 0)
        # 睡眠設定由 RecoveryTests 的受控 sleep 驗證；此處只驗新設定仍可接鏈。
        seq = self.state()["last_seq"]
        wait_for(lambda: self.state()["last_seq"] >= seq + 3)
        self.kernel_stop()

    def test_cli_once_wait_ack_and_work_failure_is_successful_cli(self):
        self.setup_running()
        target = self.job("raise SystemExit(9)")
        result = self.good_cli("add", self.home, target, "--once", "--wait-ms", "4000")
        response = json.loads(result.stdout)
        payload = response.get("result", response)
        self.assertEqual(payload["code"], 9)
        wait_for(lambda: not list((self.home / "responses").glob("*.json")))
        self.kernel_stop()

    def test_cli_remote_usage_error_is_one_but_local_usage_is_two(self):
        self.setup_running()
        result = self.cli("add", self.home, self.job(), "--once", "--wait-ms", "5000", "--")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage", result.stderr)
        self.assertEqual(self.cli("add", self.home, self.job(), "--invalid-flag").returncode, 2)
        self.kernel_stop()

    def test_cli_once_without_wait_prints_response_path(self):
        self.setup_running()
        result = self.good_cli("add", self.home, self.job(), "--once")
        self.assertIn(str(self.home / "responses"), result.stdout)
        response = wait_for(lambda: list((self.home / "responses").glob("*.json")))
        name = response[0].name
        self.assertIn(name, result.stdout)
        self.assertEqual(read_json(response[0])["result"]["code"], 0)
        ack = self.good_cli("ack", self.home, self.home / "responses" / name)
        self.assertEqual(ack.stdout, "")
        wait_for(lambda: not response[0].exists())
        self.kernel_stop()

    def test_ls_is_read_only_and_cli_errors(self):
        self.setup_running()
        self.add(self.job(), "visible")
        wait_for(lambda: not list((self.home / "requests").glob("*.json")))
        before = []
        result = self.good_cli("ls", self.home)
        for text in ("chain", "phase", "visible", "runs", "fails", "alive", "current"):
            self.assertIn(text, result.stdout)
        self.assertEqual(list((self.home / "requests").glob("*.json")), before)
        error = self.cli("rm", self.home, "does-not-exist")
        self.assertEqual(error.returncode, 1)
        self.assertIn("NotFound", error.stderr)
        self.assertEqual(self.cli("add", self.home).returncode, 2)
        self.kernel_stop()

    def test_boot_rejects_absent_daemon_using_lock_not_stale_pid(self):
        self.initialize()
        self.write(self.daemon / "state.json", {"pid": os.getpid(), "children": {}})
        result = self.cli("boot", self.home, "--daemon-target", self.daemon)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.home / "state.json").exists())
        self.assertNotIn("daemon", read_json(self.home / "info.json"))

    def test_boot_name_taken_leaves_existing_chain_and_info_intact(self):
        self.initialize()
        self.start_daemon()
        target = self.job("import sys; sys.stdin.readline(); sys.stdin.read()")
        response = aos_client.call(self.daemon, "spawn", {"name": "k", "target": target}, timeout_ms=3000, poll_ms=5)
        self.assertIn("result", response)
        before = (self.home / "info.json").read_bytes()
        result = self.cli("boot", self.home, "--daemon-target", self.daemon)
        self.assertEqual(result.returncode, 1)
        self.assertIn("NameTaken", result.stderr)
        self.assertEqual((self.home / "info.json").read_bytes(), before)
        self.assertFalse((self.home / "state.json").exists())

    def test_boot_preserves_inflight_once_pending_and_worker_cpu(self):
        self.setup_running()
        gate = self.root / "release"
        marker = self.root / "started"
        source = "import os,time; open(%r,'w').close()\nwhile not os.path.exists(%r): time.sleep(.005)" % (str(marker), str(gate))
        target = self.job(source)
        request = aos_client.submit(self.home, "add", {"name": "inflight", "target": target,
                                                       "once": True, "timeout_ms": 5000})
        wait_for(lambda: marker.exists())
        state = self.state()
        old_req = state["cpus"]["0"]["req"]
        pending = state["procs"]["inflight"]["pending"]
        old_pid = self.dstate()["children"]["0"]["pid"]
        self.boot()
        state = self.state()
        self.assertEqual(state["cpus"]["0"]["req"], old_req)
        self.assertEqual(state["procs"]["inflight"]["pending"], pending)
        self.assertEqual(self.dstate()["children"]["0"]["pid"], old_pid)
        gate.touch()
        response = aos_client.wait_response(self.home, request, timeout_ms=5000, poll_ms=5)
        self.assertEqual(response["result"]["code"], 0)
        aos_client.ack(self.home, request)
        wait_for(lambda: not (self.home / "cpus" / "0" / "responses" / old_req).exists())
        self.kernel_stop()

    def test_stop_replies_to_queued_once_and_finishes_running_once_before_cpu_stop(self):
        self.setup_running()
        gate, marker = self.root / "release", self.root / "started"
        source = "import os,time; open(%r,'w').close()\nwhile not os.path.exists(%r): time.sleep(.005)" % (str(marker), str(gate))
        running = aos_client.submit(self.home, "add", {"target": self.job(source), "name": "running",
                                                        "once": True, "timeout_ms": 5000})
        wait_for(lambda: marker.exists())
        queued = aos_client.submit(self.home, "add", {"target": self.job(name="queued"), "name": "queued", "once": True})
        wait_for(lambda: self.state().get("procs", {}).get("queued", {}).get("status") == "queued")
        self.good_cli("halt", self.home, "--no-wait")
        rejected = aos_client.wait_response(self.home, queued, timeout_ms=5000, poll_ms=5)
        self.assertEqual(rejected["error"]["data"]["code"], "Stopping")
        self.assertEqual(self.state()["phase"], "stopping")
        self.assertFalse((self.home / "responses" / running).exists())
        aos_client.ack(self.home, queued)
        gate.touch()
        response = aos_client.wait_response(self.home, running, timeout_ms=5000, poll_ms=5)
        self.assertEqual(response["result"]["code"], 0)
        aos_client.ack(self.home, running)
        wait_for(lambda: self.state().get("phase") == "stopped")
        wait_for(lambda: not self.dstate().get("children"))
        for box in ("acks", "replies", "stops", "deletes"):
            self.assertEqual(self.state()[box], [])

    def test_boot_switches_kernel_cpu_and_collects_its_inflight_work(self):
        config = read_json(self.daemon / "info.json")
        config.update(stop_wait_ms=1000, kill_wait_ms=1000)
        self.write(self.daemon / "info.json", config)
        self.setup_running()
        marker, gate = self.root / "started", self.root / "release"
        source = "import os,time; open(%r,'w').close()\nwhile not os.path.exists(%r): time.sleep(.005)" % (str(marker), str(gate))
        request = aos_client.submit(self.home, "add", {"name": "promoted-once", "target": self.job(source),
                                                       "once": True, "timeout_ms": 5000})
        wait_for(lambda: marker.exists())
        old_state = self.state()
        old_req = old_state["cpus"]["0"]["req"]
        old_children = self.dstate()["children"]
        old_k, old_zero = old_children["k"]["pid"], old_children["0"]["pid"]
        self.info["cpus"]["k"]["pool"] = "default"
        self.info["cpus"]["0"]["pool"] = "kernel"
        self.write(self.home / "info.json", self.info)
        boot = subprocess.Popen([PY, str(CLI / "aos-kernel"), "boot", "--target", str(self.home),
                                 "--daemon-target", str(self.daemon)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True)
        def cleanup_boot():
            if boot.poll() is None:
                boot.kill()
            boot.wait(timeout=4)
            boot.stdout.close()
            boot.stderr.close()
        self.addCleanup(cleanup_boot)
        wait_for(lambda: self.dstate().get("children", {}).get("0", {}).get("state") == "killing")
        # 舊 kernel 已交接完才會停原工作 cpu；此刻放行，回音留在即將升格的家。
        with self.assertRaises(ProcessLookupError):
            os.kill(old_k, 0)
        gate.touch()
        stdout, stderr = boot.communicate(timeout=8)
        self.assertEqual(boot.returncode, 0, stderr)
        response = aos_client.wait_response(self.home, request, timeout_ms=5000, poll_ms=5)
        self.assertEqual(response["result"]["code"], 0)
        aos_client.ack(self.home, request)
        wait_for(lambda: self.state()["last_seq"] >= 2 and "0" not in self.state()["cpus"])
        state = self.state()
        self.assertEqual(state["kcpu"], "0")
        self.assertNotEqual(state["chain"], old_state["chain"])
        with self.assertRaises(ProcessLookupError):
            os.kill(old_zero, 0)
        self.assertNotIn("promoted-once", state["procs"])
        wait_for(lambda: not (self.home / "cpus" / "0" / "responses" / old_req).exists())
        result = self.call("add", {"name": "after-switch", "target": self.job(name="after"), "once": True})
        self.assertEqual(result["result"]["code"], 0)
        self.kernel_stop()
