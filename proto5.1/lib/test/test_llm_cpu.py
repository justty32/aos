"""llm cpu：FakeLLM、讀驗、收屍、原子認領，以及真兩進程同搶一份。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import aos_llm_cpu
from aos_agent_info import AgentError
from test_llm_ask import FakeLLM, OK_MESSAGE

CLI = str(Path(__file__).resolve().parents[2] / "cli" / "aos-llm-cpu")


class CPUCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "cpu"
        self.dir.mkdir()
        self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1}, "models": {}})
        for part in ("requests", "running", "done"):
            (self.dir / part).mkdir()

    def write(self, path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def request(self, name="a", part="requests", **kw):
        engine = kw.pop("engine", {"endpoint": "http://unused.invalid/v1", "model": "real-fake",
                                    "timeout_ms": 1000})
        self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                                            "models": {"fake": engine}})
        req = {"model": "fake", "body": {"messages": [{"role": "user", "content": "$env is literal"}]},
               "result": str(self.dir.parent / (name + "-result.json"))}
        req.update(kw)
        self.write(self.dir / part / (name + ".json"), req)
        return req

    def llm(self):
        fake = FakeLLM()
        self.addCleanup(fake.close)
        return fake

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, CLI, *map(str, args)], capture_output=True, text=True,
                              cwd=cwd, timeout=10)


class TestLoad(CPUCase):
    def test_minimal(self):
        self.assertEqual(aos_llm_cpu.load(self.dir)["metainfo"], {"_type": "llm_cpu", "_version": 1})

    def test_metainfo_directives(self):
        self.write(self.dir / "info.json", {"_metainfo": {"$ref": "meta.json"}, "models": {}})
        self.write(self.dir / "meta.json", {"_type": {"$env": "KIND"}, "_version": 1})
        self.assertEqual(aos_llm_cpu.load(self.dir, env={"KIND": "llm_cpu"})["metainfo"]["_type"], "llm_cpu")

    def test_top_ref(self):
        self.write(self.dir / "real.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1}, "models": {}})
        self.write(self.dir / "info.json", {"$ref": "real.json"})
        aos_llm_cpu.load(self.dir)

    def test_invalid_info(self):
        cases = [([], "NotAnObject"), ({}, "NotAnAgent"), ({"_metainfo": []}, "MetainfoInvalid"),
                 ({"_metainfo": {"_type": "llm_agent", "_version": 1}}, "NotAnAgent"),
                 ({"_metainfo": {"_type": "llm_cpu"}}, "MetainfoInvalid"),
                 ({"_metainfo": {"_type": "llm_cpu", "_version": True}}, "UnsupportedVersion"),
                 ({"_metainfo": {"$opt": "foo", "$val": 1}}, "UnknownOption")]
        for obj, code in cases:
            with self.subTest(code=code, obj=obj):
                self.write(self.dir / "info.json", obj)
                with self.assertRaises(AgentError) as cm:
                    aos_llm_cpu.load(self.dir)
                self.assertEqual(cm.exception.code, code)

    def test_models_resolve_all_directives_in_referenced_file(self):
        self.write(self.dir / "models.json", {"table": {"small": {"endpoint": {"$env": "URL"},
                   "model": {"$ref": "#/real"}, "api_key": {"$env": "KEY"},
                   "timeout_ms": {"$ref": "#/ms"}}}, "real": "real-name", "ms": 99})
        self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                                            "models": {"$ref": "models.json#/table"}})
        self.assertEqual(aos_llm_cpu.load(self.dir, env={"URL": "http://fake/v1", "KEY": "secret"})["models"],
                         {"small": {"endpoint": "http://fake/v1", "model": "real-name", "api_key": "secret", "timeout_ms": 99}})
        with self.assertRaisesRegex(AgentError, "EnvironmentVariableMissing"):
            aos_llm_cpu.load(self.dir, env={})

    def test_models_defaults_and_null_key(self):
        self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                                            "models": {"small": {"endpoint": "http://x", "model": "m", "api_key": None}}})
        self.assertEqual(aos_llm_cpu.load(self.dir)["models"]["small"],
                         {"endpoint": "http://x", "model": "m", "api_key": None, "timeout_ms": 120000})

    def test_models_invalid(self):
        base = {"endpoint": "http://x", "model": "m"}
        cases = [None, [], {"": base}, {"m": []}, {"m": {}}, {"m": dict(base, endpoint="")},
                 {"m": dict(base, model="")}, {"m": dict(base, api_key=2)}]
        cases += [{"m": dict(base, timeout_ms=value)} for value in (0, -1, True, 1.2, "5", None)]
        for models in cases:
            with self.subTest(models=models):
                self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1}, "models": models})
                with self.assertRaisesRegex(AgentError, "EngineInvalid"):
                    aos_llm_cpu.load(self.dir)

    def test_models_required(self):
        self.write(self.dir / "info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1}})
        with self.assertRaisesRegex(AgentError, "EngineInvalid"):
            aos_llm_cpu.load(self.dir)

    def test_missing_info(self):
        (self.dir / "info.json").unlink()
        with self.assertRaisesRegex(AgentError, "NotAnAgent"):
            aos_llm_cpu.load(self.dir)

    def test_bad_json(self):
        (self.dir / "info.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(AgentError, "JsonSyntax"):
            aos_llm_cpu.load(self.dir)


class TestTick(CPUCase):
    def test_empty(self):
        self.assertEqual(aos_llm_cpu.tick(self.dir), 101)

    def test_missing_queue_dirs_created(self):
        for part in ("requests", "running", "done"):
            (self.dir / part).rmdir()
        self.assertEqual(aos_llm_cpu.tick(self.dir), 101)
        self.assertTrue((self.dir / "running").is_dir())

    def test_success(self):
        fake = self.llm()
        req = self.request(engine={"endpoint": fake.endpoint, "model": "fake", "api_key": "secret", "timeout_ms": 1000})
        self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(json.loads(Path(req["result"]).read_text()), {"ok": True, "message": OK_MESSAGE})
        self.assertEqual(fake.last["body"], dict(req["body"], model="fake"))
        self.assertEqual(fake.last["headers"]["Authorization"], "Bearer secret")
        self.assertTrue((self.dir / "done" / "a.json").exists())
        self.assertFalse((self.dir / "running" / "a.json").exists())
        self.assertFalse(list(self.dir.parent.glob("*.tmp")))

    def test_unknown_alias_returns_exact_error_without_http(self):
        req = self.request(model="missing")
        with patch("aos_llm_cpu.aos_llm_ask.call", side_effect=AssertionError("不應 HTTP")):
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(json.loads(Path(req["result"]).read_text()),
                         {"ok": False, "error": "不認識的模型代號"})
        self.assertTrue((self.dir / "done" / "a.json").exists())

    def test_cpu_fills_real_model_and_does_not_mutate_payload(self):
        req = self.request(body={"model": "wrong", "messages": [], "temperature": 0.2})
        with patch("aos_llm_cpu.aos_llm_ask.call", return_value=OK_MESSAGE) as call:
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(call.call_args.args[1], {"model": "real-fake", "messages": [], "temperature": 0.2})
        self.assertEqual(json.loads((self.dir / "done" / "a.json").read_text()), req)

    def test_engine_failure_is_result_and_zero(self):
        fake = self.llm()
        fake.mode = "500"
        req = self.request(engine={"endpoint": fake.endpoint, "model": "fake"})
        self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        result = json.loads(Path(req["result"]).read_text())
        self.assertFalse(result["ok"])
        self.assertIn("HTTP 500", result["error"])
        self.assertTrue((self.dir / "done" / "a.json").exists())

    def test_sorted_one_only_and_tmp_ignored(self):
        for name in ("b", "a"):
            self.request(name)
        (self.dir / "requests" / "0.json.tmp").write_text("unfinished")
        with patch("aos_llm_cpu.aos_llm_ask.call", return_value=OK_MESSAGE) as call:
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        call.assert_called_once()
        self.assertTrue((self.dir / "done" / "a.json").exists())
        self.assertTrue((self.dir / "requests" / "b.json").exists())

    def test_same_name_running_never_overwritten(self):
        old = self.request(part="running")
        new = self.request(body={"new": True})
        self.assertEqual(aos_llm_cpu.tick(self.dir), 101)
        self.assertEqual(json.loads((self.dir / "running" / "a.json").read_text()), old)
        self.assertEqual(json.loads((self.dir / "requests" / "a.json").read_text()), new)

    def test_same_name_done_skipped_next_claimed(self):
        old = self.request(part="done")
        self.request()
        self.request("b")
        with patch("aos_llm_cpu.aos_llm_ask.call", return_value=OK_MESSAGE):
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(json.loads((self.dir / "done" / "a.json").read_text()), old)
        self.assertTrue((self.dir / "requests" / "a.json").exists())
        self.assertTrue((self.dir / "done" / "b.json").exists())

    def test_reap_stale(self):
        req = self.request(part="running")
        path = self.dir / "running" / "a.json"
        os.utime(path, (time.time() - 40, time.time() - 40))
        self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertFalse(json.loads(Path(req["result"]).read_text())["ok"])
        self.assertTrue((self.dir / "done" / "a.json").exists())
        self.assertEqual(aos_llm_cpu.tick(self.dir), 101)

    def test_reap_keeps_already_published_result(self):
        req = self.request(part="running")
        result = {"ok": True, "message": OK_MESSAGE}
        self.write(Path(req["result"]), result)
        os.utime(self.dir / "running" / "a.json", (1, 1))
        self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(json.loads(Path(req["result"]).read_text()), result)

    def test_reap_all_then_claim_one(self):
        for name in ("a", "b"):
            self.request(name, part="running")
            os.utime(self.dir / "running" / (name + ".json"), (1, 1))
        self.request("c")
        with patch("aos_llm_cpu.aos_llm_ask.call", return_value=OK_MESSAGE):
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertEqual(sorted(p.name for p in (self.dir / "done").iterdir()), ["a.json", "b.json", "c.json"])

    def test_old_queue_mtime_refreshed_at_claim(self):
        self.request()
        os.utime(self.dir / "requests" / "a.json", (1, 1))
        def ask(engine, body):
            self.assertLess(time.time() - (self.dir / "running" / "a.json").stat().st_mtime, 5)
            self.assertEqual(aos_llm_cpu.tick(self.dir), 101)
            return OK_MESSAGE
        with patch("aos_llm_cpu.aos_llm_ask.call", side_effect=ask):
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)

    def test_late_worker_cannot_overwrite_reaper(self):
        req = self.request()
        def ask(engine, body):
            os.utime(self.dir / "running" / "a.json", (1, 1))
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
            return OK_MESSAGE
        with patch("aos_llm_cpu.aos_llm_ask.call", side_effect=ask):
            self.assertEqual(aos_llm_cpu.tick(self.dir), 0)
        self.assertFalse(json.loads(Path(req["result"]).read_text())["ok"])

    def test_bad_request_stays_queued(self):
        for changes, code in [({"model": ""}, "EngineInvalid"), ({"body": []}, "FieldTypeMismatch"),
                              ({"result": "relative.json"}, "FieldTypeMismatch"),
                              ({"model": None}, "EngineInvalid")]:
            with self.subTest(changes=changes):
                self.request(**changes)
                with self.assertRaisesRegex(AgentError, code):
                    aos_llm_cpu.tick(self.dir)
                self.assertTrue((self.dir / "requests" / "a.json").exists())

    def test_write_failure_keeps_running(self):
        self.request(result=str(self.dir / "missing" / "result.json"))
        with patch("aos_llm_cpu.aos_llm_ask.call", return_value=OK_MESSAGE):
            with self.assertRaisesRegex(AgentError, "ReadFailed"):
                aos_llm_cpu.tick(self.dir)
        self.assertTrue((self.dir / "running" / "a.json").exists())

    def test_real_two_processes_claim_once(self):
        fake = self.llm()
        fake.sleep = 0.3
        self.request(engine={"endpoint": fake.endpoint, "model": "fake", "timeout_ms": 2000})
        procs = [subprocess.Popen([sys.executable, CLI, str(self.dir)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outputs = [p.communicate(timeout=10) for p in procs]
        self.assertEqual(sorted(p.returncode for p in procs), [0, 101])
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(outputs, [("", ""), ("", "")])

    def test_two_cpus_http_overlap(self):
        fake = self.llm()
        # 兩個 HTTP handler 都進來才放行，明確驗 HTTP 期間沒有持 queue 鎖。
        barrier = threading.Barrier(2)
        original = fake.server.RequestHandlerClass.do_POST
        def together(handler):
            barrier.wait(timeout=3)
            original(handler)
        fake.server.RequestHandlerClass.do_POST = together
        requests = [self.request(name, engine={"endpoint": fake.endpoint, "model": "fake", "timeout_ms": 5000})
                    for name in ("a", "b")]
        procs = [subprocess.Popen([sys.executable, CLI, str(self.dir)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for p in procs:
            p.communicate(timeout=10)
        self.assertEqual([p.returncode for p in procs], [0, 0])
        self.assertEqual(len(fake.requests), 2)
        for req in requests:
            self.assertTrue(json.loads(Path(req["result"]).read_text())["ok"])


class TestCLI(CPUCase):
    def test_empty_101(self):
        result = self.cli(self.dir)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (101, "", ""))

    def test_default_cwd(self):
        self.assertEqual(self.cli(cwd=self.dir).returncode, 101)

    def test_success_zero(self):
        fake = self.llm()
        self.request(engine={"endpoint": fake.endpoint, "model": "fake"})
        result = self.cli(self.dir)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_engine_failure_zero(self):
        fake = self.llm()
        fake.mode = "500"
        self.request(engine={"endpoint": fake.endpoint, "model": "fake"})
        self.assertEqual(self.cli(self.dir).returncode, 0)

    def test_read_error_one(self):
        self.write(self.dir / "info.json", {})
        result = self.cli(self.dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-llm-cpu: NotAnAgent:", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_bad_request_one(self):
        (self.dir / "requests" / "a.json").write_text("{", encoding="utf-8")
        result = self.cli(self.dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("JsonSyntax:", result.stderr)

    def test_usage_two(self):
        self.assertEqual(self.cli("--unknown").returncode, 2)
        self.assertEqual(self.cli(self.dir / "missing").returncode, 2)


if __name__ == "__main__":
    unittest.main()
