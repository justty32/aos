#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "proto4-7"
AGENT = P / "aos-agent"
USER = P / "aos-user"


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.A = self.base / "bob"
        self.K = self.base / "K"
        (self.K / "llm/results").mkdir(parents=True)
        subprocess.run(
            [str(USER), str(self.A), "new", "--name", "bob", "--system", "s", "--K", str(self.K)],
            capture_output=True, check=True,
        )
        self.env = os.environ | {"AOS_EXEC": str(ROOT / "proto4-3/aos-exec")}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, value):
        (self.A / relative).write_text(json.dumps(value) + "\n", encoding="utf-8")

    def read(self, relative):
        return json.loads((self.A / relative).read_text(encoding="utf-8"))

    def call(self, name, arguments, call_id="c1"):
        return {"id": call_id, "type": "function",
                "function": {"name": name, "arguments": arguments}}

    def prepare_act(self, text="", calls=None):
        result = {"ok": True, "text": text, "raw": {"choices": [{"message": {
            "role": "assistant", "content": text,
        }}]}}
        if calls is not None:
            result["raw"]["choices"][0]["message"]["tool_calls"] = calls
        path = self.K / "llm/results/r.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        self.write("state.json", {
            "state": "act", "question": 1, "step": 3, "request": str(path),
            "checks": 0, "errors": 0, "idle_since_error": 0,
            "stuck": False, "last_error": None, "outbox_n": 0,
        })

    def run_agent(self):
        return subprocess.run([str(AGENT), str(self.A)], text=True, capture_output=True,
                              env=self.env, check=False)

    def test_tool_parameters_always_have_type_and_properties(self):
        import sys
        sys.path.insert(0, str(P))
        import agent_tools
        bare = self.A / "tools" / "bare"
        bare.mkdir()
        (bare / "tool.json").write_text(json.dumps({"description": "d", "parameters": {}}))
        (bare / "run").write_text("#!/bin/sh\ncat\n")
        (bare / "run").chmod(0o755)
        tools = agent_tools.load_tools(self.A)
        for name in ("echo", "sh", "bare"):
            params = tools[name]["function"]["parameters"]
            self.assertEqual(params["type"], "object", name)
            self.assertIsInstance(params["properties"], dict, name)
        self.assertIn("text", tools["echo"]["function"]["parameters"]["properties"])

    def test_formal_tool_call_runs_and_returns_to_ask(self):
        call = self.call("echo", '{"x":"yes"}', "formal")
        self.prepare_act(calls=[call])
        self.assertEqual(self.run_agent().returncode, 0)
        messages = self.read("messages.json")
        self.assertEqual(messages[0]["tool_calls"], [call])
        self.assertEqual(messages[1]["tool_call_id"], "formal")
        self.assertEqual(json.loads(messages[1]["content"]), {"x": "yes"})
        self.assertEqual(self.read("state.json")["state"], "ask")

    def test_text_tool_call_is_recovered(self):
        self.prepare_act('<tool_call> blah {"name":"echo","arguments":{"x":1}} tail')
        self.run_agent()
        messages = self.read("messages.json")
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "call_3_1")
        self.assertEqual(json.loads(messages[1]["content"]), {"x": 1})

    def test_whole_json_tool_call_is_recovered(self):
        self.prepare_act('{"name":"echo","arguments":{"whole":true}}')
        self.run_agent()
        self.assertEqual(self.read("state.json")["state"], "ask")

    def test_brace_prefixed_prose_is_a_normal_reply(self):
        self.prepare_act("{not a whole JSON tool call} and then prose")
        self.run_agent()
        self.assertEqual(self.read("state.json")["state"], "idle")
        self.assertTrue((self.A / "outbox/0001.json").exists())

    def test_unrecoverable_text_call_counts_error(self):
        self.prepare_act('[TOOL_CALLS] {"name":"invented","arguments":{}}')
        self.run_agent()
        state = self.read("state.json")
        self.assertEqual((state["state"], state["errors"]), ("idle", 1))
        self.assertEqual(self.read("messages.json"), [])

    def test_missing_tool_and_bad_arguments_are_tool_results(self):
        self.prepare_act(calls=[self.call("gone", "{}", "a"), self.call("echo", "no-json", "b")])
        self.run_agent()
        messages = self.read("messages.json")
        self.assertEqual(messages[1]["content"], "沒有這個工具")
        self.assertTrue(messages[2]["content"].startswith("參數不是 JSON："))

    def test_nonzero_tool_includes_exit_stderr_and_stdout(self):
        folder = self.A / "tools/fail"
        folder.mkdir()
        self.write("tools/fail/tool.json", {"description": "fail", "parameters": {}})
        run = folder / "run"
        run.write_text("#!/bin/sh\necho OUT\necho ERR >&2\nexit 7\n", encoding="utf-8")
        run.chmod(0o755)
        self.prepare_act(calls=[self.call("fail", "{}")])
        self.run_agent()
        content = self.read("messages.json")[1]["content"]
        self.assertTrue(content.startswith("[exit 7] ERR"))
        self.assertIn("OUT", content)

    def test_tool_output_is_truncated_after_limit(self):
        config = self.read("agent.json")
        config["tool_output_limit"] = 5
        self.write("agent.json", config)
        folder = self.A / "tools/long"
        folder.mkdir()
        self.write("tools/long/tool.json", {"description": "long", "parameters": {}})
        run = folder / "run"
        run.write_text("#!/bin/sh\nprintf 123456789\n", encoding="utf-8")
        run.chmod(0o755)
        self.prepare_act(calls=[self.call("long", "{}")])
        self.run_agent()
        self.assertEqual(self.read("messages.json")[1]["content"], "12345…（截斷）")


if __name__ == "__main__":
    unittest.main()
