"""Test that before_queue runs exactly once per letter on aos-eca-turn: plain and slash letters, alone or arriving while a turn waits for the answer (11-20 user: "修：只過一次"). CLI = fake_claude_stream with live_mail."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[3]
TURN = PROTO / "bin" / "aos-eca-turn"


class SlashHookOnce(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="eca-slash-once-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.bin, self.defn, self.ws, self.stack, self.home = (self.t / n for n in ("bin", "def", "ws", "stack", "home"))
        for d in (self.bin, self.defn, self.ws, self.stack, self.home):
            d.mkdir()
        (self.bin / "claude").symlink_to(HERE / "fake_claude_stream")
        (self.defn / "cli.json").write_text(json.dumps({"kind": "claude", "timeout_ms": 30000, "live_mail": True}))
        (self.defn / "interfaces.json").write_text(json.dumps({"hookeds": "hookeds.json"}))
        self.calls, self.cli_log = self.t / "calls.jsonl", self.t / "cli.jsonl"
        hook = self.defn / "count"
        hook.write_text("#!/bin/sh\n# count - before_queue hook: one line per call, no change\ncat >> '%s'\necho >> '%s'\n" % (self.calls, self.calls))
        hook.chmod(0o755)
        (self.defn / "hookeds.json").write_text(json.dumps({"count": {"event": "before_queue", "handler": "count"}}))
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def env(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("AOS_", "FAKE_")) and k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env.update(PATH="%s:%s" % (self.bin, env.get("PATH", "")), HOME=str(self.home), AOS_STACK=str(self.stack),
                   AOS_WS=str(self.ws), FAKE_CLI_LOG=str(self.cli_log), PYTHONDONTWRITEBYTECODE="1")
        return env

    def say(self, text):
        subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], input=json.dumps({"role": "user", "content": text}),
                       env=self.env(), check=True, capture_output=True, text=True)

    def turn(self):
        r = subprocess.run([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def received(self):
        return [json.loads(l)["line"] for l in self.cli_log.read_text().splitlines()] if self.cli_log.exists() else []

    def mid_turn(self, late):
        """A slow first letter, then `late` once the CLI has it; then one more turn for whatever stayed in the queue."""
        self.say("SLOW:3 first")
        p = subprocess.Popen([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        end = time.time() + 10
        while time.time() < end and self.received()[:1] != ["SLOW:3 first"]:
            time.sleep(0.1)
        self.say(late)
        _, err = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, err)
        self.turn()

    def counts(self):
        calls = [json.loads(l) for l in self.calls.read_text().splitlines() if l.strip()] if self.calls.exists() else []
        out = {}
        for c in calls:
            out[c["content"]] = out.get(c["content"], 0) + 1
        return out

    def queue(self):
        return [n for s in ("new", "cur") for n in os.listdir(self.stack / "queue" / s) if not n.startswith(".")]

    def test_plain_letter_alone(self):
        self.say("hello")
        self.turn()
        self.assertEqual(self.counts(), {"hello": 1})

    def test_slash_letter_alone(self):
        self.say("/compact")
        self.turn()
        self.assertEqual(self.counts(), {"/compact": 1})

    def test_plain_letter_mid_turn(self):
        self.mid_turn("second")
        self.assertEqual(self.counts(), {"SLOW:3 first": 1, "second": 1})
        self.assertEqual(self.received(), ["SLOW:3 first", "second"])
        self.assertEqual(self.queue(), [])

    def test_slash_letter_mid_turn(self):
        self.mid_turn("/compact")
        self.assertEqual(self.counts(), {"SLOW:3 first": 1, "/compact": 1})   # not seen while waiting; once in the next turn
        self.assertEqual(self.queue(), [])


if __name__ == "__main__":
    unittest.main()
