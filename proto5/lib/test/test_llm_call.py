"""aos-llm call 的離線整合驗證：每例建立本機端點並完整收尾。"""
import contextlib
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import aos_llm_call as llm
from aos_agent_home import AgentError

CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-llm"


class LlmCallTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.requests = []
        self.response = {"choices": [{"message": {"role": "assistant", "content": "你好\n世界"}}]}
        self.status, self.delay = 200, 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append((self.path, dict(self.headers), json.loads(raw)))
                time.sleep(owner.delay)
                raw = owner.response if isinstance(owner.response, bytes) else json.dumps(owner.response).encode()
                try:
                    self.send_response(owner.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # 逾時測試的呼叫端已關閉連線

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.close_server)
        self.config = {"_metainfo": {"_type": "llm_config", "_version": 1}, "models": {"small": {
            "endpoint": "http://127.0.0.1:%d/v1///" % self.server.server_port, "model": "real-model"}}}
        self.info = {"_metainfo": {"_type": "llm_agent", "_version": 1}, "llm": {"model": "small"}}
        self.write("info.json", self.info)
        self.path = self.write("llm.json", self.config)
        self.env = {"AOS_LLM_CONFIG": str(self.path), "NO_PROXY": "*", "no_proxy": "*"}
        # 所有 HTTP 都只連本機，測試不繼承外部代理設定。
        proxy = patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"})
        proxy.start()
        self.addCleanup(proxy.stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def write(self, name, value):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def save(self):
        self.write("llm.json", self.config)
        self.write("info.json", self.info)

    def call(self):
        self.save()
        return llm.call(self.base, env=self.env)

    def error(self, code, fn, *args):
        with self.assertRaises(AgentError) as cm:
            fn(*args)
        self.assertEqual(cm.exception.code, code)
        if code in ('EngineFailed', 'Timeout'):
            entry = self.config['models']['small']
            self.assertIn('（endpoint %s，模型 small→%s）' % (entry['endpoint'], entry['model']), cm.exception.msg)
        return cm.exception

    def config_error(self, code="ConfigInvalid"):
        self.save()
        self.error(code, llm.load_config, self.path, self.env)

    def cli(self, *args, env=None, sub=("call",)):
        return subprocess.run([sys.executable, str(CLI), *sub, *args], cwd=self.base,
                              env=dict(os.environ, **(self.env if env is None else env)),
                              capture_output=True, text=True, timeout=5)

    def test_success_full_request(self):
        self.write("prompts/system.json", {"content": "人格"})
        history = [{"role": "user", "content": "hello", "extra": {"$env": "missing"}}]
        self.write("prompts/history.json", history)
        t = {"type": "function", "function": {"name": "echo"}, "_meta": {"argv": ["echo"]},
             "_timeout_ms": 0, "_private": True, "custom": {"_nested": 1}}
        self.write("tools.json", [t])
        self.info["tools"] = ["tools.json"]
        self.info["llm"]["params"] = {"temperature": 0.2, "cpu": "keep", "model": "bad",
                                       "messages": [], "tools": [], "stream": True}
        self.assertEqual(self.call(), self.response["choices"][0]["message"])
        path, headers, body = self.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(body, {"model": "real-model", "temperature": 0.2, "cpu": "keep",
                               "messages": [{"role": "system", "content": "人格"}] + history,
                               "tools": [{k: v for k, v in t.items() if not k.startswith("_")}]})

    def test_empty_system_tools_omitted(self):
        self.call()
        self.assertEqual(self.requests[0][2], {"model": "real-model", "messages": []})

    def test_authorization(self):
        self.config["models"]["small"]["api_key"] = "secret"
        self.call()
        self.assertEqual(self.requests[0][1]["Authorization"], "Bearer secret")

    def test_empty_key_no_authorization(self):
        self.config["models"]["small"]["api_key"] = ""
        self.call()
        self.assertNotIn("Authorization", self.requests[0][1])

    def test_null_key_no_authorization(self):
        self.config["models"]["small"]["api_key"] = None
        self.call()
        self.assertNotIn("Authorization", self.requests[0][1])

    def test_missing_key_no_authorization(self):
        self.call()
        self.assertNotIn("Authorization", self.requests[0][1])

    def test_tool_calls_response(self):
        msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "a", "type": "function",
               "function": {"name": "echo", "arguments": "{}"}}], "extra": 12}
        self.response["choices"][0]["message"] = msg
        self.assertEqual(self.call(), msg)

    def test_normalize_order_preserves_extras(self):
        msg = {"role": "assistant", "content": None, "tool_calls": [], "extra": {"x": 1}}
        self.response["choices"][0]["message"] = msg
        self.assertEqual(self.call(), {"role": "assistant", "content": "", "extra": {"x": 1}})
        self.assertIn("tool_calls", msg)

    def test_normalize_null_without_calls(self):
        self.assertEqual(llm.normalize({"role": "assistant", "content": None}), {"role": "assistant", "content": ""})
        self.assertEqual(llm.normalize({"role": "assistant"}), {"role": "assistant"})

    def test_wrong_response_role(self):
        self.response["choices"][0]["message"] = {"role": "user", "content": "x"}
        self.error("EngineFailed", self.call)

    def test_response_call_missing_id(self):
        self.response["choices"][0]["message"] = {"role": "assistant", "content": None,
            "tool_calls": [{"type": "function", "function": {"name": "x", "arguments": "{}"}}]}
        self.error("EngineFailed", self.call)

    def test_response_null_with_invalid_calls(self):
        for calls in (None, {}, "", [None]):
            self.response["choices"][0]["message"] = {"role": "assistant", "content": None, "tool_calls": calls}
            self.error("EngineFailed", self.call)

    def test_response_content_wrong_or_missing(self):
        for msg in ({"role": "assistant"}, {"role": "assistant", "content": 3}):
            self.response["choices"][0]["message"] = msg
            self.error("EngineFailed", self.call)

    def test_http_500_cli(self):
        self.status, self.response = 500, b"first line\nsecond line"
        e = self.error("EngineFailed", self.call)
        self.assertIn("500", e.msg)
        self.assertIn("first line second line", e.msg)
        result = self.cli(str(self.base))
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("aos-llm: EngineFailed: HTTP 500", result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_non_json(self):
        self.response = b"not json"
        self.error("EngineFailed", self.call)

    def test_json_non_object(self):
        self.response = []
        self.error("EngineFailed", self.call)

    def test_missing_choices(self):
        for response in ({}, {"choices": []}, {"choices": {}}, {"choices": [None]}):
            self.response = response
            self.error("EngineFailed", self.call)

    def test_missing_message(self):
        for choice in ({}, {"message": None}, {"message": []}):
            self.response = {"choices": [choice]}
            self.error("EngineFailed", self.call)

    def test_timeout(self):
        self.delay = 0.4
        self.config["models"]["small"]["timeout_ms"] = 200
        self.error("Timeout", self.call)

    def test_connection_refused(self):
        # 綁住但不 listen，避免釋放埠之後被別的行程搶走。
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.config["models"]["small"]["endpoint"] = "http://127.0.0.1:%d" % s.getsockname()[1]
            self.error("EngineFailed", self.call)

    def test_bad_endpoint(self):
        self.config["models"]["small"]["endpoint"] = "not a url"
        self.error("EngineFailed", self.call)

    def test_config_meta_missing(self):
        del self.config["_metainfo"]
        self.config_error()

    def test_config_meta_shape_fields_type(self):
        for meta in (None, [], {}, {"_type": "llm_config"}, {"_version": 1},
                     {"_type": "wrong", "_version": 1}):
            self.config["_metainfo"] = meta
            self.config_error()

    def test_config_version(self):
        for version in (True, False, 1.0, "1", 2, None):
            self.config["_metainfo"]["_version"] = version
            self.config_error("UnsupportedVersion")

    def test_config_models(self):
        for models in (None, [], "x"):
            self.config["models"] = models
            self.config_error()
        del self.config["models"]
        self.config_error()

    def test_config_entry_object(self):
        self.config["models"]["small"] = []
        self.config_error()

    def test_config_endpoint_model(self):
        original = copy.deepcopy(self.config)
        for key in ("endpoint", "model"):
            for value in (None, "", 1):
                self.config = copy.deepcopy(original)
                self.config["models"]["small"][key] = value
                self.config_error()
            self.config = copy.deepcopy(original)
            del self.config["models"]["small"][key]
            self.config_error()

    def test_config_api_key_type(self):
        self.config["models"]["small"]["api_key"] = 123
        self.config_error()

    def test_config_timeout_type(self):
        for value in (0, -1, True, False, 2.0, "2", None):
            self.config["models"]["small"]["timeout_ms"] = value
            self.config_error()

    def test_config_default_timeout(self):
        self.assertEqual(llm.load_config(self.path)["models"]["small"]["timeout_ms"], 120000)

    def test_config_unused_model_invalid(self):
        self.config["models"]["unused"] = {"endpoint": "x", "model": ""}
        self.error("ConfigInvalid", self.call)
        self.assertEqual(self.requests, [])

    def test_unknown_model(self):
        self.info["llm"]["model"] = "missing"
        self.error("UnknownModel", self.call)
        self.assertEqual(self.requests, [])

    def test_config_io(self):
        self.error("ReadFailed", llm.load_config, self.base / "missing")
        self.path.write_text("{", encoding="utf-8")
        self.error("JsonSyntax", llm.load_config, self.path)

    def test_config_non_object(self):
        self.write("llm.json", [])
        self.error("NotAnObject", llm.load_config, self.path)

    def test_config_top_directive(self):
        self.write("llm.json", {"$env": "MISSING"})
        self.error("FieldTypeMismatch", llm.load_config, self.path)

    def test_config_all_directives_resolved(self):
        self.config["extra"] = {"$env": "MISSING"}
        self.config_error("EnvironmentVariableMissing")

    def test_config_reference_base_and_env(self):
        self.write("cfg/entry.json", {"endpoint": self.config["models"]["small"]["endpoint"],
                                       "model": "real", "api_key": {"$env": "KEY"}})
        self.config["models"]["small"] = {"$ref": "entry.json"}
        path = self.write("cfg/llm.json", self.config)
        self.assertEqual(llm.load_config(path, {"KEY": "secret"})["models"]["small"]["api_key"], "secret")

    def test_config_env_missing_empty_relative(self):
        for env in ({}, {"AOS_LLM_CONFIG": ""}, {"AOS_LLM_CONFIG": "llm.json"}):
            self.error("ConfigInvalid", llm.config_path, env)
            self.error("ConfigInvalid", llm.call, self.base, env)

    def test_read_history_at_execution(self):
        self.write("prompts/history.json", [{"role": "user", "content": "old"}])
        config = llm.load_config(self.path)
        new = [{"role": "user", "content": "new"}]
        self.write("prompts/history.json", new)
        self.assertEqual(llm.build_request(self.base, config)[0]["messages"], new)
        self.call()
        self.assertEqual(self.requests[0][2]["messages"], new)

    def test_cli_success_default_dir(self):
        result = self.cli()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(json.loads(result.stdout), self.response["choices"][0]["message"])
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("你好", result.stdout)
        self.assertTrue(result.stdout.endswith("\n"))

    def test_cli_agent_dir_argument(self):
        result = self.cli(str(self.base))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_failure_stdout_empty(self):
        result = self.cli(env={"AOS_LLM_CONFIG": "relative"})
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertTrue(result.stderr.startswith("aos-llm: ConfigInvalid:"))
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_cli_agent_error(self):
        result = self.cli(str(self.base / "missing"))
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("NotAnAgent", result.stderr)

    def test_cli_usage_exit_2(self):
        result = self.cli("one", "two")
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("usage:", result.stderr)

    def test_bare_aos_llm_and_old_form_are_usage_errors(self):
        for sub in ((), ("nope",)):
            with self.subTest(sub=sub):
                result = self.cli(sub=sub)
                self.assertEqual((result.returncode, result.stdout), (2, ""))
                self.assertIn("usage: aos-llm", result.stderr)
        self.assertFalse((CLI.parent / "aos-llm-call").exists())

    def test_help_lists_call(self):
        result = self.cli("-h", sub=())
        self.assertEqual(result.returncode, 0)
        self.assertIn("call", result.stdout)
        result = self.cli("-h")
        self.assertIn("AGENT_DIR", result.stdout)

    def test_main_error_one_line(self):
        self.info["llm"]["model"] = "missing\nmodel"
        self.save()
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(llm.main(["call", str(self.base)]), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(len(err.getvalue().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
