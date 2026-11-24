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
        executable = test_kernel.PROTO8 / "bin"
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

    def test_05_old_intercept_and_async_keys_are_not_read(self):
        # 11-21 起引擎沒有 intercept／async：寫了也不讀，退 10 照樣攔。
        for options in ({"intercept": False}, {"async": True}):
            with self.subTest(options=options):
                self.fresh()
                self.configure(hooks=self.hook("notice", "before_verdict", "print('no')\nsys.exit(10)", **options))
                self.send({"ping": "original"})
                self.assert_round()
                self.assertEqual(self.reply_error(), {"code": "HookRejected", "msg": "no"})
                self.assertEqual(list((self.ctl / "new").iterdir()), [])

    def test_06_hook_failures_stop_the_round(self):
        # 11-21 起沒有 on_error：hook 失敗一律停這一輪（HookFailed）；寫了 on_error: continue 也一樣。
        for failure in ("timeout", "exit"):
            for written in ({}, {"on_error": "continue"}):
                with self.subTest(failure=failure, written=written):
                    self.fresh()
                    script = "time.sleep(30)" if failure == "timeout" else "sys.exit(7)"
                    hooks = self.hook("broken", "before_verdict", script, timeout_ms=200, **written)
                    self.configure(hooks=hooks)
                    name = self.send({"ping": True})
                    result = self.kernel()
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("kernel: error: HookFailed", result.stderr)
                    self.assertIn("hook broken (event before_verdict) failed: %s"
                                  % ("did not finish in 200 ms" if failure == "timeout" else "exited 7"), result.stderr)
                    self.assertTrue((self.requests / "cur" / name).exists())
                    self.assertEqual(list((self.ctl / "new").iterdir()), [])
                    # 成功入隊以前的失敗不會消掉新信身分。
                    hooks["broken"] = dict(hooks["broken"], handler=self.handler("fixed", ""))
                    self.configure(hooks=hooks)
                    self.assert_round()
                    self.assertEqual(len(self.events()), 2)
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
        for hooks in ([], {"bad": {"event": "before_verdict"}}, {"bad": {"event": "after_verdict", "handler": "x", "condition": 3}},
                      {"bad": {"event": "before_verdict", "handler": "x", "timeout_ms": -1}}):
            with self.subTest(hooks=hooks):
                self.configure(hooks=hooks)
                result = self.kernel()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("kernel: error: CfgBad", result.stderr)

    def test_12_event_names_are_not_checked_and_hookeds_come_from_interfaces(self):
        # 事件名不驗：沒人發的點掛著也不錯、不跑；清單照 interfaces.json 的 hookeds 讀，kernel.json 的 hooks 不讀。
        self.configure(hooks=self.hook("later", "unknown", "sys.exit(7)"))
        self.send({"ping": True})
        self.assert_round()
        self.assertEqual(self.events(), [])
        self.policy.write_text(json.dumps({"hooks": self.hook("old", "before_verdict", "sys.exit(7)")}))
        (self.root / "kernel_hookeds.json").unlink()                 # named but not there: no hooks
        self.send({"ping": True}, name="second")
        self.assert_round()
        (self.root / "interfaces.json").unlink()                     # no interfaces.json: no hooks
        self.send({"ping": True}, name="third")
        self.assert_round()
        self.assertEqual(self.events(), [])
        self.assertEqual(len(list((self.ctl / "new").iterdir())), 3)

    def test_13_old_hooks_key_warns_once_per_change(self):
        # 11-24（使用者「1.不報錯。」）：kernel.json 還有舊 hooks 鍵＝照跑、warning 一行；同一份沒改不再印，改了再印，拿掉就收記號。
        self.configure()
        self.policy.write_text(json.dumps({"hooks": self.hook("old", "before_verdict", "sys.exit(7)")}))
        first = self.assert_round().stderr
        self.assertIn('has a top-level "hooks" key, which is ignored since 11-21', first)
        self.assertIn("kernel_hookeds.json", first)
        self.assertNotIn("hooks", self.assert_round().stderr)                  # same file, next round: quiet
        mark = self.stack / "hooks_key_warned.txt"
        self.assertTrue(mark.exists())
        self.policy.write_text(json.dumps({"hooks": {}, "reply_via_me": False}))
        os.utime(self.policy, ns=(1, 1))
        self.assertIn('"hooks" key', self.assert_round().stderr)               # changed: once more
        self.policy.write_text(json.dumps({}))
        self.assertNotIn("hooks", self.assert_round().stderr)
        self.assertFalse(mark.exists())
        self.assertEqual(self.events(), [])

if __name__ == "__main__":
    unittest.main()
