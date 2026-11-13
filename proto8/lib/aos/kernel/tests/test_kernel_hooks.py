# 用真的 aos-post 與 aos-exec 驗證 kernel 三個 hook 時機和排隊時的保存。
import json
import os
from pathlib import Path
import sys
import time
import unittest

import test_kernel


class KernelHooksTest(unittest.TestCase):
    fixture = test_kernel.KernelTest.fixture
    post_result = test_kernel.KernelTest.post_result
    post = test_kernel.KernelTest.post
    kernel = test_kernel.KernelTest.kernel
    configure = test_kernel.KernelTest.configure
    assert_round = test_kernel.KernelTest.assert_round
    read_new = test_kernel.KernelTest.read_new

    def setUp(self):
        self.fresh()

    def fresh(self):
        self.fixture()
        executable = test_kernel.PROTO8 / "impls/aos-exec/bin"
        self.env["PATH"] = str(executable) + os.pathsep + self.env["PATH"]

    def handler(self, name, script):
        path = self.root / (name + ".py")
        path.write_text("#!" + sys.executable + "\n"
                        "# 暫存的測試 handler：記錄真正收到的事件，再執行指定動作。\n"
                        "import json, pathlib, sys, time\n"
                        "event = json.load(sys.stdin)\n"
                        "assert {'event', 'hook', 'stack', 'letter', 'sender', 'reply_to', 'body'} <= event.keys()\n"
                        "assert 'names' not in event\n"
                        "assert pathlib.Path(event['stack']).is_absolute()\n"
                        "with open(%r, 'a') as stream:\n"
                        "    stream.write(json.dumps(event) + '\\n')\n" % str(self.root / "events.jsonl")
                        + script + "\n")
        path.chmod(0o755)
        return path.name

    def hook(self, name, event, script="", **options):
        return {name: dict(event=event, handler=self.handler(name, script), **options)}

    def events(self):
        path = self.root / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def send(self, body, name="request"):
        return self.post("send", "--reply-to", self.sender, self.requests, name, body=body)

    def reply_error(self):
        return self.read_new(self.sender)[1]["body"]["error"]

    def expire(self, name):
        path = self.requests / "cur" / name / "letter.json"
        letter = json.loads(path.read_text())
        letter["sent_at"] = "2000-01-01T00:00:00.000Z"
        path.write_text(json.dumps(letter))

    def test_01_before_verdict_changes_forwarded_body(self):
        changed = {"procs_added": {"allowed": {}}, "private": "changed"}
        hooks = self.hook("rewrite", "before_verdict", "print(json.dumps({'body': %r}))" % changed)
        self.configure(allowed=["allowed"], hooks=hooks)
        name = self.send({"procs_added": {"forbidden": {}}})
        self.assert_round()
        forwarded, letter = self.read_new(self.ctl)
        self.assertEqual((forwarded, letter["body"]), (name, changed))
        event = self.events()[0]
        self.assertEqual((event["event"], event["hook"], event["letter"]),
                         ("before_verdict", "rewrite", name))
        self.assertIn("sent_at", event)
        self.assertEqual(event["body"], {"procs_added": {"forbidden": {}}})

    def test_02_before_verdict_blocks_rules_and_after_verdict(self):
        for stdout, expected in (("  denied by policy  ", "denied by policy"), ("", "blocked by hook block")):
            with self.subTest(stdout=stdout):
                self.fresh()
                trace = self.root / "after.called"
                hooks = self.hook("block", "before_verdict", "print(%r)\nsys.exit(10)" % stdout)
                hooks.update(self.hook("after", "after_verdict", "pathlib.Path(%r).touch()" % str(trace)))
                self.configure(allowed=[], hooks=hooks)
                self.send({"procs_added": "invalid"})
                result = self.assert_round()
                self.assertEqual(self.reply_error(), {"code": "HookRejected", "msg": expected})
                self.assertNotIn("BodyBad", result.stderr)
                self.assertFalse(trace.exists())
                self.assertEqual([e["event"] for e in self.events()], ["before_verdict"])

    def test_03_after_verdict_can_refuse_or_override_refusal(self):
        for original in ("pass", "refuse"):
            with self.subTest(original=original):
                self.fresh()
                replacement = "refuse" if original == "pass" else "pass"
                hooks = self.hook("flip", "after_verdict", "print(json.dumps({'verdict': %r}))" % replacement,
                                  condition=original)
                policy = {"hooks": hooks}
                if original != "pass":
                    policy.update(max_running=0, queue=(original == "queue"))
                self.configure(**policy)
                name = self.send({"procs_added": {"worker": {}}})
                self.assert_round()
                if replacement == "refuse":
                    self.assertEqual(self.reply_error(), {"code": "HookRejected", "msg": "refused by hook flip"})
                    self.assertEqual(list((self.ctl / "new").iterdir()), [])
                else:
                    self.assertEqual(self.read_new(self.ctl)[0], name)
                event = self.events()[0]
                self.assertEqual(event["verdict"], original)
                self.assertEqual(event["error"] is None, original != "refuse")
    def test_04_before_reply_changes_or_blocks_relay(self):
        for block in (False, True):
            with self.subTest(block=block):
                self.fresh()
                script = "print('  sensitive  ')\nsys.exit(10)" if block else "print('{\"body\": {\"redacted\": true}}')"
                self.configure(reply_via_me=True, hooks=self.hook("reply", "before_reply", script))
                name = self.send({"ping": True})
                self.post("take-all", self.requests)
                original = json.loads(self.post("see", self.requests, name))
                self.assert_round()
                forwarded, _ = self.read_new(self.ctl)
                reply_name = self.post("done", "--reply", self.ctl, forwarded, body={"secret": "original"})
                # done 的 stdout 不保證是信名，從信箱讀真正的回信信封。
                self.post("take-all", self.replies)
                pending = list((self.replies / "cur").iterdir())
                self.assertEqual(len(pending), 1, reply_name)
                downstream = json.loads(self.post("see", self.replies, pending[0].name))
                self.assert_round()
                _, reply = self.read_new(self.sender)
                self.assertEqual(reply["in_reply_to"], name)
                expected = {"applied": False, "error": {"code": "HookRejected",
                            "msg": "reply blocked by hook reply: sensitive"}} if block else {"redacted": True}
                self.assertEqual(reply["body"], expected)
                event = self.events()[0]
                self.assertEqual(event["sender"], original["sender"])
                self.assertEqual(event["reply_sender"], downstream["sender"])
                self.assertEqual(event["reply_to"], str(self.sender))
                self.assertEqual(event["letter"], name)
                self.assertEqual(event["body"], {"secret": "original"})

    def test_05_notification_hooks_do_not_change_or_block(self):
        for options in ({"intercept": False}, {"async": True}):
            with self.subTest(options=options):
                self.fresh()
                finished = self.root / "finished"
                script = "print('{\"body\": {\"wrong\": true}}')\npathlib.Path(%r).touch()\nsys.exit(10)" % str(finished)
                self.configure(hooks=self.hook("notice", "before_verdict", script, **options))
                body = {"ping": "original"}
                self.send(body)
                self.assert_round()
                deadline = time.monotonic() + 3
                while not finished.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(finished.exists())
                self.assertEqual(self.read_new(self.ctl)[1]["body"], body)

    def test_06_hook_failures_stop_or_continue(self):
        for failure in ("timeout", "exit"):
            for mode in ("stop", "continue"):
                with self.subTest(failure=failure, mode=mode):
                    self.fresh()
                    script = "time.sleep(30)" if failure == "timeout" else "sys.exit(7)"
                    hooks = self.hook("broken", "before_verdict", script, on_error=mode, timeout_ms=200)
                    self.configure(hooks=hooks)
                    name = self.send({"ping": True})
                    result = self.kernel()
                    if mode == "stop":
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn("kernel: error: HookFailed", result.stderr)
                        self.assertTrue((self.requests / "cur" / name).exists())
                        self.assertEqual(list((self.ctl / "new").iterdir()), [])
                        # 成功入隊以前的失敗不會消掉新信身分。
                        hooks["broken"] = dict(hooks["broken"], handler=self.handler("fixed", ""))
                        self.configure(hooks=hooks)
                        self.assert_round()
                        self.assertEqual(len(self.events()), 2)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("kernel: warning: hook broken", result.stderr)
                        self.assertIn("on_error: continue", result.stderr)
                    self.assertTrue((self.ctl / "new" / name).exists())

    def test_07_waiting_letter_does_not_repeat_hooks(self):
        hooks = self.hook("before", "before_verdict")
        hooks.update(self.hook("after", "after_verdict"))
        self.configure(queue=True, max_running=0, hooks=hooks)
        name = self.send({"procs_added": {"worker": {}}})
        self.assert_round()
        first = self.events()
        self.assertEqual([event["event"] for event in first], ["before_verdict", "after_verdict"])
        self.assertEqual(first[1]["verdict"], "queue")
        self.assert_round()
        self.assertEqual(self.events(), first)
        self.assertTrue((self.requests / "cur" / name).exists())

    def test_08_leaving_queue_runs_after_verdict_once(self):
        for expired in (False, True):
            with self.subTest(expired=expired):
                self.fresh()
                hooks = self.hook("before", "before_verdict")
                hooks.update(self.hook("after", "after_verdict"))
                self.configure(queue=True, max_running=0, hooks=hooks)
                name = self.send({"procs_added": {"worker": {}}, "queue_wait_ms": 60000})
                self.assert_round()
                if expired:
                    self.expire(name)
                else:
                    self.configure(queue=True, max_running=1, hooks=hooks)
                self.assert_round()
                events = self.events()
                self.assertEqual([event["event"] for event in events],
                                 ["before_verdict", "after_verdict", "after_verdict"])
                self.assertEqual([event["verdict"] for event in events[1:]],
                                 ["queue", "refuse" if expired else "pass"])
                if expired:
                    self.assertEqual(self.reply_error()["code"], "SlotMissing")
                else:
                    self.assertEqual(self.read_new(self.ctl)[0], name)
                self.assert_round()
                self.assertEqual(self.events(), events)

    def test_09_changed_queued_body_is_private_and_removed_after_dispatch(self):
        changed = {"procs_added": {"worker": {}}, "secret": "private payload"}
        hooks = self.hook("rewrite", "before_verdict", "print(json.dumps({'body': %r}))" % changed)
        self.configure(queue=True, max_running=0, hooks=hooks)
        name = self.send({"ping": True})
        self.assert_round()
        saved = self.stack / "bodies" / (name + ".json")
        self.assertEqual(json.loads(saved.read_text()), changed)
        window = json.loads((self.stack / "queue.json").read_text())
        self.assertEqual(window["queued"][0]["names"], ["worker"])
        self.assertNotIn("body", window["queued"][0])
        self.assertNotIn("private payload", json.dumps(window))
        self.assert_round()
        self.assertEqual(len(self.events()), 1)
        self.configure(queue=True, max_running=1, hooks=hooks)
        self.assert_round()
        self.assertFalse(saved.exists())
        self.assertEqual(self.read_new(self.ctl)[1]["body"], changed)

    def test_10_before_reply_requires_reply_via_me(self):
        self.configure(hooks=self.hook("reply", "before_reply"))
        result = self.kernel()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("kernel: error: CfgBad", result.stderr)

    def test_11_invalid_hooks_configuration_is_rejected(self):
        for hooks in ([], {"bad": {"event": "unknown", "handler": "unused"}}):
            with self.subTest(hooks=hooks):
                self.configure(hooks=hooks)
                result = self.kernel()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("kernel: error: CfgBad", result.stderr)


if __name__ == "__main__":
    unittest.main()
