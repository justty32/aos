import json
import os
from pathlib import Path
import subprocess
import unittest

import aos_llm
from _util import CpuCase, PY, ROOT


CLI = ROOT / "aos-llm"


class AosLlmTest(CpuCase):
    def endpoint(self, name="local", **extra):
        endpoint = {
            "name": name, "kind": "openai",
            "base_url": "http://127.0.0.1:%d/v1" % self.port,
            "model": "fake-model", "timeout_ms": 2000,
        }
        endpoint.update(extra)
        return endpoint

    def write(self, name, value):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def llm(self, *args, input_data=None, env=None):
        return subprocess.run([PY, str(CLI), *map(str, args)],
                              input=input_data, text=True, capture_output=True,
                              env=env)

    def request(self, name="req.json", content="echo:hello", **extra):
        return self.write(name, {
            "messages": [{"role": "user", "content": content}], **extra})

    def test_single_endpoint_file_success_and_full_shape(self):
        endpoint = self.write("one.json", self.endpoint())
        output = Path(self.temp.name) / "out.json"
        result = self.llm("call", endpoint, self.request(), output)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(output.read_text())
        self.assertEqual(body["text"], "hello")
        self.assertEqual(set(body), {
            "ok", "id", "endpoint", "model", "model_requested", "text",
            "finish_reason", "usage", "ms", "raw", "error"})
        self.assertEqual(set(body["usage"]), {
            "prompt", "completion", "total", "cached", "reasoning"})

    def test_endpoint_file_hash_name(self):
        endpoints = self.write("many.json", {
            "default": "other", "endpoints": [self.endpoint("other"),
                                                 self.endpoint("chosen")]})
        output = Path(self.temp.name) / "hash.json"
        result = self.llm("call", str(endpoints) + "#chosen",
                          self.request(), output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())["endpoint"], "chosen")

    def test_endpoints_file_without_hash_uses_default(self):
        endpoints = self.write("default.json", {
            "default": "chosen", "endpoints": [self.endpoint("chosen")]})
        output = Path(self.temp.name) / "default-out.json"
        result = self.llm("call", endpoints, self.request(), output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())["endpoint"], "chosen")

    def test_http_500_writes_result_and_stderr(self):
        endpoint = self.write("http.json", self.endpoint())
        output = Path(self.temp.name) / "http-out.json"
        result = self.llm("call", endpoint,
                          self.request(content="fail:500"), output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text())["error"]["kind"], "http")
        self.assertIn("aos-llm: http:", result.stderr)

    def test_request_model_is_bad_request_exit_one(self):
        endpoint = self.write("model-ep.json", self.endpoint())
        output = Path(self.temp.name) / "model-out.json"
        result = self.llm("call", endpoint,
                          self.request(model="not-allowed"), output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text())["error"]["kind"],
                         "bad_request")

    def test_stdin_request_and_stdout_result(self):
        endpoint = self.write("stdio.json", self.endpoint())
        request = json.dumps({"id": "stdio", "messages": [
            {"role": "user", "content": "echo:pipe"}]})
        result = self.llm("call", endpoint, "-", "-", input_data=request)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual((body["id"], body["text"]), ("stdio", "pipe"))

    def test_missing_endpoint_file_is_usage_error(self):
        result = self.llm("call", Path(self.temp.name) / "missing.json",
                          self.request(), Path(self.temp.name) / "unused.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertIn("aos-llm: ENDPOINT 解不開", result.stderr)

    def test_models_prints_one_id_per_line(self):
        endpoint = self.write("models.json", self.endpoint())
        result = self.llm("models", endpoint)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "fake-model\n")

    def test_missing_api_key_is_result_error(self):
        endpoint = self.write("key.json", self.endpoint(
            api_key_env="AOS_LLM_TEST_MISSING_KEY"))
        output = Path(self.temp.name) / "key-out.json"
        env = dict(os.environ)
        env.pop("AOS_LLM_TEST_MISSING_KEY", None)
        result = self.llm("call", endpoint, self.request(), output, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text())["error"]["kind"],
                         "no_api_key")

    def test_timeout_flag_overrides_request(self):
        endpoint = self.write("timeout.json", self.endpoint(timeout_ms=2000))
        output = Path(self.temp.name) / "timeout-out.json"
        result = self.llm("call", endpoint,
                          self.request(content="slow:0.2", timeout_ms=1000),
                          output, "--timeout-ms", "20")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_text())["error"]["kind"],
                         "timeout")

    def test_library_bad_endpoint_returns_result_and_null_id(self):
        result = aos_llm.call({}, {"messages": [{"role": "user",
                                                  "content": "x"}]})
        self.assertFalse(result["ok"])
        self.assertIsNone(result["id"])
        self.assertEqual(result["error"]["kind"], "bad_request")


if __name__ == "__main__":
    unittest.main()
