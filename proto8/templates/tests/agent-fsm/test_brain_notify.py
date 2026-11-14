"""Test brain_notify with a fake aos-mailbox: refusal notices, deduplication, and nonfatal errors."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENTRY = PROTO / "lib" / "agent" / "brain_notify" / "_entry"
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-mailbox: error: MailboxMissing no mailbox here\n")
    sys.exit(1)
print("letter-1")
'''


class BrainNotify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="brain-notify-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = self.root / "procs" / "worker"
        self.cell = self.agent / "hooks" / "brain_notify"
        self.cell.mkdir(parents=True)
        self.history = self.agent / "history.jsonl"
        self.seen = self.cell / "notified.json"
        self.box = self.root / "parent" / "mailbox"
        for part in ("tmp", "new", "cur"):
            (self.box / part).mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "aos-mailbox"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.log = self.root / "mailbox.log"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=os.pathsep.join((str(self.bin), os.environ["PATH"])),
                        AOS_STACK=str(self.cell), AOS_NOTIFY_BOX=str(self.box),
                        FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        self.event = {"event": "brain_failed", "hook": "brain_notify", "stack": str(self.agent),
                      "name": "BudgetMissing", "reason": "max_calls 150 reached in this window (day); not run"}

    def run_hook(self, event=None, text=None, env=None, argv=()):
        r = subprocess.run([sys.executable, str(ENTRY), *argv],
                           input=json.dumps(self.event if event is None else event) if text is None else text,
                           capture_output=True, text=True, env=self.env if env is None else env, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def warning(self, result, code):
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("brain_notify: warning: " + code), result.stderr)
        self.assertNotIn("brain_notify: error:", result.stderr)

    def test_first_send_deduplicates_then_history_growth_sends_again(self):
        self.history.write_text('{"role":"user","content":"work"}\n')
        r = self.run_hook(env=dict(self.env, AOS_NOTIFY_BOX="  " + str(self.box) + " \n"))
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(self.calls(), [["--stack", str(self.agent), "send", "--from", "worker", "--box", str(self.box),
                                        "--status", "BLOCKED", "--title", "worker: brain refused (BudgetMissing), waiting",
                                        "--", self.event["reason"] + ". It sends the same request again by itself after a "
                                        "cooldown (30 s doubling to 30 min). Raise the budget, or stop it."]])
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 1})
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)
        with self.history.open("a") as f:
            f.write('{"role":"assistant","content":"done"}\n')
        self.run_hook()
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 2})
        self.assertEqual(list(self.cell.glob("*.tmp")), [])

    def test_missing_history_counts_zero_and_different_code_sends(self):
        self.run_hook()
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 0})
        self.run_hook()
        self.assertEqual(len(self.calls()), 1)
        self.run_hook(event=dict(self.event, name="BrainFailed", reason="endpoint unavailable"))
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BrainFailed", "history_lines": 0})
        self.assertEqual(self.calls()[-1][-3], "worker: brain refused (BrainFailed), waiting")

    def test_corrupt_record_sends_once_and_rewrites(self):
        self.seen.write_text('{"code":')
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 0})
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)

    def test_unset_or_blank_box_warns_without_sending(self):
        for box in (None, " \t\n"):
            with self.subTest(box=box):
                env = dict(self.env)
                env.pop("AOS_NOTIFY_BOX")
                if box is not None:
                    env["AOS_NOTIFY_BOX"] = box
                r = self.run_hook(env=env)
                self.assertEqual(r.stderr, "brain_notify: warning: AOS_NOTIFY_BOX is not set; nobody is told that "
                                          "worker got BudgetMissing\n")
                self.assertEqual(r.stdout, "")
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.seen.exists())

    def test_send_failure_warns_without_recording_and_can_retry(self):
        r = self.run_hook(env=dict(self.env, FAKE_FAIL="1"))
        self.warning(r, "CommandFailed")
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(self.seen.exists())
        self.run_hook()
        self.assertEqual(len(self.calls()), 2)
        self.assertTrue(self.seen.exists())

    def test_missing_mailbox_command_warns_without_recording(self):
        r = self.run_hook(env=dict(self.env, PATH=str(self.root / "no-commands")))
        self.warning(r, "LaunchFailed")
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.seen.exists())

    def test_bad_stdin_warns_without_sending(self):
        for text in ("not json", "[]", "null", "{}", json.dumps(dict(self.event, stack="relative")),
                     json.dumps(dict(self.event, name=None)), json.dumps(dict(self.event, reason=None))):
            with self.subTest(text=text):
                self.warning(self.run_hook(text=text), "ArgumentsBad")
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.seen.exists())

    def test_missing_hook_cell_warns_without_sending(self):
        env = dict(self.env)
        env.pop("AOS_STACK")
        self.warning(self.run_hook(env=env), "StackMissing")
        self.assertEqual(self.calls(), [])

    def test_write_failure_warns_after_send_without_recording(self):
        missing_cell = self.root / "missing-cell"
        self.warning(self.run_hook(env=dict(self.env, AOS_STACK=str(missing_cell))), "WriteFailed")
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((missing_cell / "notified.json").exists())

    def test_help_and_unknown_argument(self):
        r = self.run_hook(text="not json", argv=("--help",))
        self.assertIn("usage: brain_notify", r.stdout)
        self.assertEqual(r.stderr, "")
        self.warning(self.run_hook(argv=("--unknown",)), "ArgumentsBad")
        self.assertEqual(self.calls(), [])

    def test_template_mount(self):
        hooks = json.loads((PROTO / "templates" / "agent-fsm" / "hooks.json").read_text())
        self.assertEqual(hooks["hooks"]["brain_notify"],
                         {"event": "brain_failed", "condition": ["BudgetMissing"],
                          "handler": {"$env": "AOS_HOME", "$path": "/lib/agent/brain_notify"},
                          "on_error": "continue", "timeout_ms": 10000})
        self.assertIn("AOS_NOTIFY_BOX", hooks["description"])


if __name__ == "__main__":
    unittest.main()
