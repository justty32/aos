import json
import socket
import unittest

from _util import CpuCase


class WorkerTest(CpuCase):
    def ask(self, request_id, content, **extra):
        self.request(request_id, content, **extra)
        self.tick()
        return self.result(request_id)

    def test_echo_success_shape_and_usage_line(self):
        result = self.ask("echo", "echo:hello")
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "hello")
        self.assertEqual(result["finish_reason"], "stop")
        self.assertEqual(result["usage"], {
            "prompt": 11, "completion": 7, "total": 18,
            "cached": 3, "reasoning": 2})
        for key in ("id", "endpoint", "model", "ms", "raw", "error"):
            self.assertIn(key, result)
        lines = (self.home / "usage.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        usage = json.loads(lines[0])
        for key in ("prompt", "completion", "total", "cached", "reasoning"):
            self.assertIn(key, usage)

    def test_http_500(self):
        error = self.ask("http", "fail:500")["error"]
        self.assertEqual((error["kind"], error["status"], error["retryable"]),
                         ("http", 500, True))

    def test_bad_json(self):
        self.assertEqual(self.ask("badjson", "badjson")["error"]["kind"],
                         "bad_json")

    def test_model_mismatch(self):
        self.assertEqual(self.ask("mismatch", "model:other")["error"]["kind"],
                         "model_mismatch")

    def test_missing_api_key(self):
        self.set_local(extra={"api_key_env": "AOS_TEST_KEY_THAT_DOES_NOT_EXIST"})
        error = self.ask("nokey", "echo:x")["error"]
        self.assertEqual(error["kind"], "no_api_key")
        self.assertIn("AOS_TEST_KEY_THAT_DOES_NOT_EXIST", error["msg"])

    def test_connection_refused(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        self.set_local(timeout_ms=300,
                       extra={"base_url": "http://127.0.0.1:%d/v1" % port})
        error = self.ask("connect", "echo:x")["error"]
        self.assertEqual(error["kind"], "connect")
        self.assertTrue(error["retryable"])

    def test_params_cannot_override_fixed_model(self):
        result = self.ask("params", "echo:x",
                          params={"model": "wrong", "stream": True,
                                  "temperature": 0.2})
        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "fake-model")


if __name__ == "__main__":
    unittest.main()
