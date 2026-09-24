"""kernel.md §1～§4：純判定、syscall 帳本與派工；不開外部行程。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aos_home as home
import aos_kernel as kernel

CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-kernel"


class KernelCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aos-kernel-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.k, self.d = self.root / "K", self.root / "D"
        self.k.mkdir()
        self.d.mkdir()
        home.ensure_queue(self.k)
        home.ensure_queue(self.d)
        self.raw = {"_metainfo": {"_type": "kernel", "_version": 1},
                    "daemon": str(self.d), "cpus": {"k": {"pool": "kernel"},
                    "0": {}, "1": {}, "llm": {"pool": "llm"}},
                    "tick_ms": 0, "interval_ms": 100, "timeout_ms": 0,
                    "done_exit": 100, "bad_after": 3}
        home.write_json(self.k / "info.json", self.raw)
        self.info = kernel.load_info(self.k)
        self.state = kernel.new_state(self.info, "test-chain", "k", str(CLI))
        self.engine = kernel.Kernel(self.k, self.info, self.state, 7)
        for name in self.raw["cpus"]:
            (self.k / "cpus" / name).mkdir(parents=True)
            home.ensure_queue(self.k / "cpus" / name)
        self.engine.save()

    def proc(self, name="p", **values):
        proc = {"request": "add-%s.json" % name, "target": str(self.root / "missing.json"),
                "dir_target": ".aos/inst.json", "once": False, "pool": "default",
                "interval_ms": 100, "timeout_ms": 0, "status": "queued", "runs": 0,
                "fails": 0, "not_before": 0, "pending": None}
        proc.update(values)
        self.state["procs"][name] = proc
        if proc["status"] == "queued":
            self.state["queue"].append(name)
        return proc

    def syscall(self, method, params=None, name="syscall.json", id="request-id", notify=False):
        value = {"jsonrpc": "2.0", "method": method}
        if not notify:
            value["id"] = id
        if params is not None:
            value["params"] = params
        home.post_request(self.k, name, value)
        return home.read_request(self.k / "requests" / name)

    def reply(self, request="syscall.json"):
        return next(item["body"] for item in self.state["replies"] if item["name"] == request)

    def assign(self, name="p", cpu="0", req="k-old-chain-1-0.json", **values):
        proc = self.proc(name, status="running", **values)
        self.state["cpus"][cpu] = {"req": req, "proc": name, "discard": False}
        return proc, self.k / "cpus" / cpu, req

    def result(self, code=0, kind="child", **flags):
        return home.result_response("cpu-id", dict(code=code, kind=kind, timed_out=False,
                                                    stopped=False, ms=1, **flags))


class ClassifyTests(KernelCase):
    def test_decision_table_and_precedence(self):
        original = self.proc(runs=4, fails=1, not_before=17)
        stopped = home.result_response(1, {"code": 100, "kind": "aos", "stopped": True})
        interrupted = home.error_response(1, -32000, "中斷", {"code": "Interrupted"})
        cases = [(stopped, "queued", 4, 1, 17),
                 (interrupted, "queued", 4, 2, 123.1),
                 (self.result(100, "aos"), "queued", 5, 2, 123.1),
                 (self.result(100), "done", 5, 0, 17),
                 (self.result(0), "queued", 5, 0, 123.1),
                 (self.result(101), "queued", 5, 0, 123.1),
                 (self.result(2), "queued", 5, 2, 123.1)]
        before = copy.deepcopy(original)
        for response, status, runs, fails, not_before in cases:
            with self.subTest(response=response):
                actual = kernel.classify(original, response, self.info, now=123)
                self.assertEqual((actual["status"], actual["runs"], actual["fails"]),
                                 (status, runs, fails))
                self.assertAlmostEqual(actual["not_before"], not_before)
                self.assertEqual(original, before)

    def test_bad_after_threshold_and_disabled(self):
        original = self.proc(runs=1, fails=2)
        for response in (self.result(7), self.result(1, "aos"),
                         home.error_response(1, -32000, "failed")):
            with self.subTest(response=response):
                actual = kernel.classify(original, response, self.info, now=123)
                self.assertEqual((actual["status"], actual["fails"]), ("bad", 3))
                disabled = dict(self.info, bad_after=0)
                actual = kernel.classify(original, response, disabled, now=123)
                self.assertEqual((actual["status"], actual["fails"]), ("queued", 3))

    def test_done_exit_zero_disables_completion(self):
        actual = kernel.classify(self.proc(), self.result(0), dict(self.info, done_exit=0), now=1)
        self.assertEqual((actual["status"], actual["runs"]), ("queued", 1))

    def test_success_resets_failures(self):
        actual = kernel.classify(self.proc(fails=2), self.result(), self.info, now=1)
        self.assertEqual(actual["fails"], 0)


class SyscallTests(KernelCase):
    def test_add_commits_proc_reply_delete_together_once(self):
        env = self.syscall("add", {"target": str(self.root / "not-created.json"), "name": "bob"})
        snapshots = []
        save = self.engine.save
        def recorded_save():
            snapshots.append(copy.deepcopy(self.state))
            return save()
        with patch.object(self.engine, "save", side_effect=recorded_save):
            self.engine.apply_syscall(env)
        self.assertEqual(len(snapshots), 1)
        saved = snapshots[0]
        self.assertIn("bob", saved["procs"])
        self.assertEqual(saved["queue"], ["bob"])
        self.assertIn(env.name, saved["deletes"])
        self.assertEqual(saved["replies"][0]["body"], {"result": {"name": "bob"}})
        self.assertTrue((self.k / "requests" / env.name).exists())
        self.assertFalse((self.k / "responses" / env.name).exists())

    def test_once_add_delays_reply_and_preserves_args(self):
        env = self.syscall("add", {"target": str(self.root / "program"), "name": "one",
                                   "once": True, "args": []})
        self.engine.apply_syscall(env)
        proc = self.state["procs"]["one"]
        self.assertEqual(proc["pending"], {"name": env.name, "id": env.id})
        self.assertEqual(proc["args"], [])
        self.assertEqual(self.state["replies"], [])
        self.assertEqual(self.state["deletes"], [env.name])

    def test_add_without_args_does_not_invent_field(self):
        self.engine.apply_syscall(self.syscall("add", {"target": "/future.json", "name": "p"}))
        self.assertNotIn("args", self.state["procs"]["p"])

    def test_numeric_name_is_max_plus_one(self):
        for name in ("2", "10", "named"):
            self.proc(name)
        self.engine.apply_syscall(self.syscall("add", {"target": "/future.json"}))
        self.assertEqual(self.reply(), {"result": {"name": "11"}})

    def test_deletes_prevents_rescan_even_after_proc_removed(self):
        env = self.syscall("add", {"target": "/future.json", "name": "p"})
        self.engine.apply_syscall(env)
        self.state["procs"].clear()
        self.state["queue"].clear()
        self.engine.apply_syscall(env)
        self.assertEqual(self.state["procs"], {})
        self.assertEqual(self.state["deletes"], [env.name])
        self.assertEqual(len(self.state["replies"]), 1)

    def test_same_name_add_rejected_for_every_status(self):
        for index, status in enumerate(("queued", "running", "done", "bad")):
            with self.subTest(status=status):
                self.proc("duplicate", status=status)
                env = self.syscall("add", {"target": "/future.json", "name": "duplicate"},
                                   name="add-%d.json" % index)
                self.engine.apply_syscall(env)
                self.assertEqual(self.reply(env.name)["error"]["data"]["code"], "AlreadyExists")

    def test_invalid_params_and_pool(self):
        cases = [{"target": "relative.json"}, {"target": "/x", "pool": "kernel"},
                 {"target": "/x", "pool": "absent"}, {"target": "/x", "args": None},
                 {"target": "/x", "interval_ms": True}, {"target": "/x", "name": ".."}]
        for index, params in enumerate(cases):
            with self.subTest(params=params):
                env = self.syscall("add", params, name="bad-%d.json" % index)
                self.engine.apply_syscall(env)
                self.assertEqual(self.reply(env.name)["error"]["code"], -32602)
        self.assertEqual(self.state["procs"], {})

    def test_rm_nonrunning_states(self):
        for index, status in enumerate(("queued", "done", "bad")):
            name = "p%d" % index
            self.proc(name, status=status)
            self.engine.apply_syscall(self.syscall("rm", {"name": name}, name="rm-%d.json" % index))
            self.assertNotIn(name, self.state["procs"])
            self.assertNotIn(name, self.state["queue"])

    def test_rm_missing_returns_not_found(self):
        self.engine.apply_syscall(self.syscall("rm", {"name": "absent"}))
        self.assertEqual(self.reply()["error"]["data"]["code"], "NotFound")

    def test_rm_running_request_present_marks_discard(self):
        proc, cpu, req = self.assign()
        home.post_request(cpu, req, {"jsonrpc": "2.0", "id": 1, "method": "aos-exec"})
        self.engine.remove("p")
        self.assertIs(self.state["procs"]["p"], proc)
        self.assertTrue(self.state["cpus"]["0"]["discard"])
        env = self.syscall("add", {"target": "/other.json", "name": "p"})
        self.engine.apply_syscall(env)
        self.assertEqual(self.reply()["error"]["data"]["code"], "AlreadyExists")

    def test_rm_running_response_present_marks_discard(self):
        proc, cpu, req = self.assign()
        home.write_json(cpu / "responses" / req, self.result())
        self.engine.remove("p")
        self.assertIs(self.state["procs"]["p"], proc)
        self.assertTrue(self.state["cpus"]["0"]["discard"])

    def test_rm_recorded_but_unsent_cancels_assignment(self):
        self.assign()
        self.engine.remove("p")
        self.assertNotIn("p", self.state["procs"])
        self.assertEqual(self.state["cpus"]["0"], {"req": None, "proc": None, "discard": False})

    def test_rm_once_immediately_removed_for_all_three_cases(self):
        for index, mode in enumerate(("queued", "inflight", "responded", "unsent")):
            name = "one%d" % index
            pending = {"name": "pending-%d.json" % index, "id": index}
            if mode == "queued":
                self.proc(name, once=True, pending=pending)
            else:
                proc, cpu, req = self.assign(name, cpu=("0", "1", "llm")[index - 1],
                                             once=True, pending=pending,
                                             req="work-%d.json" % index)
                if mode == "inflight":
                    home.post_request(cpu, req, {"jsonrpc": "2.0", "method": "aos-exec", "id": 1})
                elif mode == "responded":
                    home.write_json(cpu / "responses" / req, self.result())
            self.engine.remove(name)
            self.assertEqual(self.reply(pending["name"])["error"]["data"]["code"], "Removed")
            if name in self.state["procs"]:
                self.assertIsNone(self.state["procs"][name]["pending"])


class CollectDispatchTests(KernelCase):
    def test_collect_waits_for_request_disappearance(self):
        proc, cpu, req = self.assign()
        home.post_request(cpu, req, {"jsonrpc": "2.0", "id": 1, "method": "aos-exec"})
        home.write_json(cpu / "responses" / req, self.result())
        self.engine.collect()
        self.assertEqual(proc["runs"], 0)
        self.assertEqual(self.state["cpus"]["0"]["req"], req)
        self.assertEqual(self.state["acks"], [])

    def test_collect_checks_request_before_response(self):
        proc, cpu, req = self.assign()
        home.write_json(cpu / "responses" / req, self.result())
        accesses = []
        original = Path.exists
        def exists(path):
            if path.name == req:
                accesses.append(path.parent.name)
            return original(path)
        with patch.object(Path, "exists", exists):
            self.engine.collect()
        self.assertEqual(accesses[:2], ["requests", "responses"])
        self.assertEqual(self.state["procs"]["p"]["runs"], 1)

    def test_once_response_is_copied_with_original_pending_identity(self):
        for index, body in enumerate(({"result": {"code": 137, "kind": "child", "stopped": True}},
                                      {"error": {"code": -32000, "message": "中斷",
                                                 "data": {"code": "Interrupted"}}})):
            name = "one%d" % index
            pending = {"name": "once-%d.json" % index, "id": "original-%d" % index}
            proc, cpu, req = self.assign(name, req="result-%d.json" % index,
                                         once=True, pending=pending)
            home.write_json(cpu / "responses" / req, dict(jsonrpc="2.0", id="cpu-id", **body))
            self.engine.collect()
            self.assertNotIn(name, self.state["procs"])
            item = next(x for x in self.state["replies"] if x["name"] == pending["name"])
            self.assertEqual(item, dict(pending, body=body))
            self.assertIn({"home": str(cpu), "name": req}, self.state["acks"])

    def test_discard_collect_drops_without_counting(self):
        proc, cpu, req = self.assign(runs=5, fails=2)
        self.state["cpus"]["0"]["discard"] = True
        home.write_json(cpu / "responses" / req, self.result())
        self.engine.collect()
        self.assertNotIn("p", self.state["procs"])
        self.assertEqual((proc["runs"], proc["fails"]), (5, 2))
        self.assertEqual(self.state["replies"], [])

    def test_two_free_cpus_do_not_dispatch_same_proc(self):
        self.proc()
        self.engine.dispatch()
        busy = [c for c in self.state["cpus"].values() if c["req"] is not None]
        self.assertEqual(len(busy), 1)
        self.assertEqual(busy[0]["proc"], "p")
        self.assertEqual(self.state["queue"], [])

    def test_pool_and_not_before(self):
        self.proc("future", not_before=10**12)
        self.proc("model", pool="llm", args=["hello"])
        self.engine.dispatch()
        self.assertIsNone(self.state["cpus"]["0"]["req"])
        self.assertIsNone(self.state["cpus"]["1"]["req"])
        self.assertEqual(self.state["cpus"]["llm"]["proc"], "model")
        req = self.state["cpus"]["llm"]["req"]
        request = home.read_json(self.k / "cpus" / "llm" / "requests" / req)
        self.assertEqual(request["params"]["args"], ["hello"])
        self.assertEqual(self.state["queue"], ["future"])

    def test_stopping_cancels_queued_once_and_keeps_repeat(self):
        self.proc("one", once=True, pending={"name": "once.json", "id": "once-id"})
        self.proc("repeat")
        self.state["phase"] = "stopping"
        self.engine.stopping()
        self.assertNotIn("one", self.state["procs"])
        self.assertIn("repeat", self.state["procs"])
        self.assertEqual(self.reply("once.json")["error"]["data"]["code"], "Stopping")


class InfoTests(KernelCase):
    def test_initial_state_shape(self):
        self.assertEqual(self.state["chain"], "test-chain")
        self.assertEqual(self.state["kcpu"], "k")
        self.assertEqual(self.state["cli"], str(CLI))
        self.assertEqual(self.state["phase"], "running")
        self.assertEqual(set(self.state["cpus"]), {"0", "1", "llm"})
        for name in ("procs", "queue", "acks", "replies", "stops", "deletes"):
            self.assertFalse(self.state[name])
        self.assertTrue(all(c == {"req": None, "proc": None, "discard": False}
                            for c in self.state["cpus"].values()))

    def test_envs_copied_without_expansion_or_validation(self):
        envs = {"$opt": "clear", "$val": {"PATH": {"$env": "AOS_UNSET_KERNEL_TEST"}}}
        self.raw["cpus"]["llm"]["envs"] = envs
        home.write_json(self.k / "info.json", self.raw)
        self.assertEqual(kernel.load_info(self.k)["cpus"]["llm"]["envs"], envs)

    def test_info_rejects_nonliteral_top_and_wrong_kernel_count(self):
        bad_values = [{"$ref": "other.json"}, dict(self.raw, cpus={"0": {}}),
                      dict(self.raw, cpus={"k": {"pool": "kernel"}, "j": {"pool": "kernel"}})]
        for value in bad_values:
            with self.subTest(value=value):
                home.write_json(self.k / "info.json", value)
                with self.assertRaises(kernel.KernelError) as cm:
                    kernel.load_info(self.k)
                self.assertEqual(cm.exception.code, "FieldTypeMismatch")

    def test_info_integer_boundaries(self):
        for key, value in (("tick_ms", -1), ("interval_ms", True), ("timeout_ms", -1),
                           ("done_exit", 256), ("bad_after", False)):
            with self.subTest(key=key):
                home.write_json(self.k / "info.json", dict(self.raw, **{key: value}))
                with self.assertRaises(kernel.KernelError) as cm:
                    kernel.load_info(self.k)
                self.assertEqual(cm.exception.code, "FieldTypeMismatch")

    def test_init_refuses_existing_home(self):
        with self.assertRaises(kernel.KernelError):
            kernel.init(self.k)
