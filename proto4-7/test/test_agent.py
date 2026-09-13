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
REAL_EXEC = ROOT / "proto4-3" / "aos-exec"


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.A = self.base / "bob"
        self.K = self.base / "K"
        (self.K / "llm" / "requests").mkdir(parents=True)
        (self.K / "llm" / "results").mkdir(parents=True)
        self.kernel = self.base / "fake-kernel"
        self.kernel.write_text(
            "#!/bin/sh\nset -eu\n"
            "[ \"$1\" = llm ]\nmkdir -p \"$2/llm/requests\"\n"
            "cp \"$3\" \"$2/llm/requests/$5.json\"\n"
            "echo \"$2/llm/results/$5.json\"\n",
            encoding="utf-8",
        )
        self.kernel.chmod(0o755)
        self.env = os.environ | {"AOS_KERNEL": str(self.kernel), "AOS_EXEC": str(REAL_EXEC)}
        self.run_user("new", "--name", "bob", "--system", "help", "--K", str(self.K))

    def tearDown(self):
        self.tmp.cleanup()

    def run_agent(self, *args, env=None):
        return subprocess.run(
            [str(AGENT), str(self.A), *args], text=True, capture_output=True,
            env=env or self.env, check=False,
        )

    def run_user(self, *args, stdin=None):
        return subprocess.run(
            [str(USER), str(self.A), *args], input=stdin, text=True,
            capture_output=True, env=self.env, check=False,
        )

    def read(self, relative):
        return json.loads((self.A / relative).read_text(encoding="utf-8"))

    def write(self, relative, value):
        (self.A / relative).write_text(
            json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
        )

    def state(self, **changes):
        state = {
            "state": "idle", "question": 1, "step": 0, "request": None,
            "checks": 0, "errors": 0, "idle_since_error": 0,
            "stuck": False, "last_error": None, "outbox_n": 0,
        }
        state.update(changes)
        self.write("state.json", state)

    def result(self, name, text="hello", tool_calls=None, ok=True, error=None):
        message = {"role": "assistant", "content": text}
        if tool_calls is not None:
            message["tool_calls"] = tool_calls
        value = {
            "ok": ok, "text": text,
            "raw": {"choices": [{"message": message}]},
        }
        if error:
            value["error"] = error
        path = self.K / "llm" / "results" / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def send_and_ask(self, text="hi"):
        self.assertEqual(self.run_user("say", text).returncode, 0)
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "ask")
        self.assertEqual(self.run_agent().returncode, 0)
        return self.read("state.json")

    def test_four_state_transitions_and_waiting(self):
        self.assertEqual(self.run_agent().returncode, 101)
        state = self.send_and_ask()
        self.assertEqual(state["state"], "wait")
        self.assertEqual(state["step"], 1)
        self.assertEqual(self.run_agent().returncode, 101)
        self.assertEqual(self.read("state.json")["checks"], 1)
        self.result("bob-q1-s1", "answer")
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "act")
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "idle")
        self.assertEqual(self.read("outbox/0001.json")["content"], "answer")

    def test_request_has_system_messages_and_tools(self):
        self.send_and_ask("question")
        request = self.read("req.json")
        self.assertEqual(request["messages"][0], {"role": "system", "content": "help"})
        self.assertEqual(request["messages"][1]["content"], "[user] question")
        self.assertEqual([x["function"]["name"] for x in request["tools"]], ["echo", "sh"])
        copied = json.loads((self.K / "llm/requests/bob-q1-s1.json").read_text())
        self.assertEqual(copied, request)

    def test_request_omits_tools_key_when_tool_list_is_empty(self):
        for folder in (self.A / "tools").iterdir():
            for path in folder.iterdir():
                path.unlink()
            folder.rmdir()
        self.send_and_ask()
        self.assertNotIn("tools", self.read("req.json"))

    def test_mail_array_moves_whole_file_and_bad_mail_reports(self):
        inbox = self.A / "inbox/user"
        self.write("inbox/user/a.json", [
            {"from": "user", "time": "1", "content": "one"},
            {"from": "user", "time": "2", "content": "two"},
        ])
        (inbox / "bad.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual([x["content"] for x in self.read("messages.json")], ["[user] one", "[user] two"])
        self.assertTrue((inbox / "read/a.json").exists())
        self.assertTrue((inbox / "read/bad.json").exists())
        self.assertEqual(self.read("outbox/0001.json")["content"], "有一封信讀不懂")

    def test_bad_mail_alone_did_work_so_returns_zero(self):
        (self.A / "inbox/user/bad.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "idle")

    def test_outbox_counter_survives_reset(self):
        self.send_and_ask()
        self.result("bob-q1-s1", "first")
        self.run_agent(); self.run_agent()
        self.assertEqual(self.run_agent("--reset").returncode, 0)
        self.write("inbox/user/bad.json", "not a letter")
        self.run_agent()
        self.assertTrue((self.A / "outbox/0002.json").exists())

    def test_max_steps_stops_without_submitting(self):
        config = self.read("agent.json")
        config["max_steps_per_question"] = 1
        self.write("agent.json", config)
        self.state(state="ask", step=1)
        self.assertEqual(self.run_agent().returncode, 0)
        state = self.read("state.json")
        self.assertEqual((state["state"], state["step"], state["stuck"]), ("idle", 2, True))
        self.assertIn("走了 1 格", self.read("outbox/0001.json")["content"])

    def test_checks_limit_is_exactly_600(self):
        missing = self.K / "llm/results/missing.json"
        self.state(state="wait", request=str(missing), checks=598)
        self.assertEqual(self.run_agent().returncode, 101)
        self.assertEqual(self.read("state.json")["checks"], 599)
        self.assertEqual(self.run_agent().returncode, 0)
        state = self.read("state.json")
        self.assertEqual((state["state"], state["checks"], state["errors"]), ("idle", 0, 1))

    def test_fifth_model_error_becomes_stuck(self):
        path = self.result("bad", ok=False, text="", error={"kind": "http", "msg": "down"})
        self.state(state="wait", request=str(path), errors=4)
        self.assertEqual(self.run_agent().returncode, 0)
        state = self.read("state.json")
        self.assertTrue(state["stuck"])
        self.assertEqual(state["last_error"], "http: down")
        self.assertIn("等你新信", self.read("outbox/0001.json")["content"])

    def test_empty_and_missing_choices_are_errors(self):
        empty = self.result("empty", text="")
        self.state(state="wait", request=str(empty))
        self.run_agent()
        self.assertIn("空白", self.read("state.json")["last_error"])
        bad = self.K / "llm/results/nochoices.json"
        bad.write_text('{"ok":true,"text":"x","raw":{}}', encoding="utf-8")
        self.state(state="wait", request=str(bad))
        self.run_agent()
        self.assertIn("choices", self.read("state.json")["last_error"])

    def test_resend_at_twenty_and_dangling_tool_safety_net(self):
        self.write("messages.json", [{"role": "user", "content": "pending"}])
        self.state(idle_since_error=19)
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "ask")
        self.write("messages.json", [{"role": "tool", "content": "result"}])
        self.state(idle_since_error=0)
        for _ in range(19):
            self.assertEqual(self.run_agent().returncode, 101)
        self.assertEqual(self.run_agent().returncode, 0)
        self.assertEqual(self.read("state.json")["state"], "ask")

    def test_new_mail_clears_stuck_and_errors(self):
        self.state(errors=5, stuck=True, last_error="x", idle_since_error=9)
        self.run_user("say", "continue")
        self.run_agent()
        state = self.read("state.json")
        self.assertEqual((state["errors"], state["stuck"], state["step"]), (0, False, 0))
        self.assertIsNone(state["last_error"])

    def test_exit_codes_100_1_and_2(self):
        config = self.read("agent.json")
        config["stop"] = True
        self.write("agent.json", config)
        self.assertEqual(self.run_agent().returncode, 100)
        config["stop"] = False
        config["K"] = str(self.base / "gone")
        self.write("agent.json", config)
        self.assertEqual(self.run_agent().returncode, 1)
        result = subprocess.run([str(AGENT)], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)

    def test_submit_failure_counts_as_agent_error(self):
        broken = self.base / "broken-kernel"
        broken.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        broken.chmod(0o755)
        env = self.env | {"AOS_KERNEL": str(broken)}
        self.run_user("say", "hi")
        self.run_agent(env=env)
        result = self.run_agent(env=env)
        self.assertEqual(result.returncode, 0)
        state = self.read("state.json")
        self.assertEqual((state["state"], state["errors"]), ("idle", 1))


if __name__ == "__main__":
    unittest.main()
