# 用真的 aos-post 信箱驗證框架站的轉寄、代回與重起防重。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


ENTRY = Path(__file__).resolve().parents[1] / "_entry"
PROTO8 = ENTRY.parents[3]
POST = PROTO8 / "impls/aos-post/bin/aos-post"
DIRECTIVE = PROTO8 / "impls/aos-directive/bin"


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.fixture()

    def fixture(self, **policy):
        scratch = os.environ.get("KERNEL_TEST_TMP", "/tmp")
        self.root = Path(subprocess.check_output(
            ["mktemp", "-d", str(Path(scratch) / "kernel-test.XXXXXX")], text=True).strip())
        self.addCleanup(shutil.rmtree, self.root)
        self.stack = self.root / "stack"
        self.daemon = self.root / "daemon"
        self.stack.mkdir()
        self.daemon.mkdir()
        self.requests = self.stack / "requests"
        self.replies = self.stack / "replies"
        self.ctl = self.daemon / "procs_requests"
        self.sender = self.root / "sender"
        self.policy = self.root / "kernel.json"
        self.policy.write_text(json.dumps(policy))
        self.env = dict(os.environ, AOS_STACK=str(self.stack), AOS_DAEMON=str(self.daemon),
                        PYTHONDONTWRITEBYTECODE="1",
                        PATH=os.pathsep.join([str(POST.parent), str(DIRECTIVE), os.environ["PATH"]]))
        self.env.pop("AOS_CLOCK", None)
        for box in (self.requests, self.replies, self.ctl, self.sender):
            self.post("init", box)

    def post_result(self, *args, body=None):
        return subprocess.run([str(POST), *map(str, args)],
                              input="" if body is None else json.dumps(body),
                              text=True, capture_output=True, env=self.env)

    def post(self, *args, body=None):
        result = self.post_result(*args, body=body)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def kernel(self):
        return subprocess.run([sys.executable, str(ENTRY), str(self.policy)],
                              text=True, capture_output=True, env=self.env)

    def broken_reply(self, kind):
        broken = self.replies / "cur" / "broken-reply"
        if kind == "file":
            broken.write_text("not a letter")
        else:
            name = self.post("send", self.replies, "broken-reply", body={"applied": True})
            self.post("take-all", self.replies)
            envelope = broken / "letter.json"
            if kind == "json":
                envelope.write_text("{")
            else:
                letter = json.loads(envelope.read_text())
                del letter["body"]
                envelope.write_text(json.dumps(letter))
            self.assertEqual(name, "broken-reply")
        self.assertEqual(self.post_result("see", self.replies, "broken-reply").returncode, 1)
        for index in range(2):
            name = "normal-%d" % index
            self.post("send", self.requests, name, body={"ping": True})
            result = self.kernel()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((self.ctl / "new" / name / "letter.json").is_file())
            self.assertFalse(broken.exists())
            if index == 0:
                self.assertIn("kernel: warning: reply broken-reply is broken; dropped", result.stderr)
            else:
                self.assertNotIn("broken-reply", result.stderr)

    def test_nonletter_reply_is_dropped_and_next_round_runs(self):
        self.broken_reply("file")

    def test_invalid_json_reply_is_dropped_and_next_round_runs(self):
        self.broken_reply("json")

    def test_reply_without_body_is_dropped_and_next_round_runs(self):
        self.broken_reply("body")

    def test_empty_round_does_not_read_daemon_state(self):
        (self.daemon / "procs_state.json").write_text("{broken")
        result = self.kernel()
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def duplicate(self, slot, mode, reason):
        self.fixture(max_running=0, keep_ordered=(mode == "preserved"))
        body = {"procs_added": {"worker": {}},
                "queue_wait_ms": {"expired": 1, "full": 0, "invalid": -1}[reason]}
        args = ["send", "--reply-to", self.sender]
        if mode != "ordinary":
            args.append("--ordered")
        name = self.post(*args, self.requests, "request", body=body)
        self.post("take-all", self.requests)
        request = self.requests / "cur" / name / "letter.json"
        letter = json.loads(request.read_text())
        letter["sent_at"] = "2000-01-01T00:00:00.000Z"
        request.write_text(json.dumps(letter))
        args = ["send"]
        if mode == "preserved":
            args.append("--ordered")
        forwarded = self.post(*args, self.ctl, "request", body=body)
        if slot == "cur":
            self.post("take-all", self.ctl)
        if mode == "preserved":
            (self.stack / "forwarded.json").write_text(json.dumps({
                forwarded: {"letter": name, "reply_to": str(self.sender), "sender": letter["sender"]}}))
        result = self.kernel()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(request.exists(), result.stderr)
        self.assertEqual(list((self.sender / "new").iterdir()), [], result.stderr)
        self.assertNotIn("refused", result.stderr)
        self.assertEqual([p.name for p in (self.ctl / slot).iterdir()], [forwarded])
        self.assertEqual(list((self.ctl / ("cur" if slot == "new" else "new")).iterdir()), [])

    def test_same_tail_already_forwarded_is_finished_before_refusal(self):
        for slot in ("new", "cur"):
            for mode in ("ordinary", "collapsed"):
                for reason in ("expired", "full", "invalid"):
                    with self.subTest(slot=slot, mode=mode, reason=reason):
                        self.duplicate(slot, mode, reason)

    def test_ordered_record_is_finished_before_refusal(self):
        for slot in ("new", "cur"):
            for reason in ("expired", "full", "invalid"):
                with self.subTest(slot=slot, reason=reason):
                    self.duplicate(slot, "preserved", reason)


    def configure(self, **policy):
        self.policy.write_text(json.dumps(policy))

    def assert_round(self):
        result = self.kernel()
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def read_new(self, box):
        self.post("take-all", box)
        names = sorted(path.name for path in (box / "cur").iterdir() if not path.name.startswith("."))
        self.assertEqual(len(names), 1, names)
        return names[0], json.loads(self.post("see", box, names[0]))

    def test_next_mailbox_does_not_need_daemon(self):
        target = self.root / "other"
        self.post("init", target)
        self.configure(next="other")
        self.env.pop("AOS_DAEMON")
        body = ["plain", 7]
        name = self.post("send", self.requests, "request", body=body)
        self.assert_round()
        forwarded, letter = self.read_new(target)
        self.assertEqual(forwarded, name)
        self.assertEqual(letter["body"], body)
        self.assertEqual(list((self.ctl / "new").iterdir()), [])

    def test_count_daemon_uses_the_other_daemon_table(self):
        counter = self.root / "counter"
        counter.mkdir()
        state = counter / "procs_state.json"
        state.write_text(json.dumps({"procs": {"busy": {"phase": "stuck"}}}))
        self.configure(next=str(self.ctl), count_daemon="counter", max_running=1)
        self.post("send", "--reply-to", self.sender, self.requests, "full",
                  body={"procs_added": {"worker": {}}})
        self.assert_round()
        _, reply = self.read_new(self.sender)
        self.assertEqual(reply["body"]["error"]["code"], "SlotMissing")
        self.assertEqual(list((self.ctl / "new").iterdir()), [])
        state.write_text(json.dumps({"procs": {}}))
        name = self.post("send", self.requests, "room", body={"procs_added": {"worker": {}}})
        self.assert_round()
        self.assertTrue((self.ctl / "new" / name).is_dir())

    def test_next_with_max_running_requires_count_daemon(self):
        self.configure(next=str(self.ctl), max_running=1)
        result = self.kernel()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("kernel: error: CfgBad", result.stderr)

    def test_forward_target_cannot_be_own_requests(self):
        for explicit in (True, False):
            with self.subTest(explicit=explicit):
                self.fixture()
                if explicit:
                    shortcut = self.root / "own_box"
                    shortcut.symlink_to(self.requests, target_is_directory=True)
                    self.configure(next=str(shortcut))
                else:
                    (self.daemon / "procs_state.json").write_text(json.dumps({
                        "procs_requests": str(self.requests), "procs": {}}))
                self.post("send", self.requests, "request", body={"ping": True})
                result = self.kernel()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("kernel: error: CfgBad", result.stderr)

    def test_zero_queue_wait_passes_when_slot_is_available(self):
        self.configure(max_running=1, queue=True)
        name = self.post("send", self.requests, "request",
                         body={"procs_added": {"worker": {}}, "queue_wait_ms": 0})
        self.post("take-all", self.requests)
        path = self.requests / "cur" / name / "letter.json"
        letter = json.loads(path.read_text())
        letter["sent_at"] = "2000-01-01T00:00:00.000Z"
        path.write_text(json.dumps(letter))
        self.assert_round()
        self.assertTrue((self.ctl / "new" / name).is_dir())
        self.assertEqual(json.loads((self.stack / "queue.json").read_text()), {"queued": []})

    def test_unordered_reply_via_me_uses_original_in_reply_to(self):
        self.configure(reply_via_me=True)
        name = self.post("send", "--reply-to", self.sender, self.requests, "request", body={"ping": True})
        self.assert_round()
        forwarded, letter = self.read_new(self.ctl)
        self.assertEqual((self.ctl / letter["reply_to"]).resolve(), self.replies)
        records = json.loads((self.stack / "forwarded.json").read_text())
        self.assertEqual(records[forwarded]["letter"], name)
        self.assertEqual(records[forwarded]["reply_to"], str(self.sender))
        self.assertIn("sender", records[forwarded])
        self.post("done", "--reply", self.ctl, forwarded, body={"applied": True})
        self.assert_round()
        _, reply = self.read_new(self.sender)
        self.assertEqual(reply["in_reply_to"], name)
        self.assertEqual(reply["body"], {"applied": True})
        self.assertEqual(json.loads((self.stack / "forwarded.json").read_text()), {})

    def test_two_stations_relay_reply_back_to_original_sender(self):
        second = self.root / "second"
        second.mkdir()
        second_requests = second / "requests"
        self.post("init", second_requests)
        second_policy = self.root / "second_kernel.json"
        second_policy.write_text(json.dumps({"next": str(self.ctl), "reply_via_me": True,
                                             "keep_ordered": True}))
        second_env = dict(self.env, AOS_STACK=str(second))
        second_env.pop("AOS_DAEMON")
        self.configure(next=str(second_requests), reply_via_me=True, keep_ordered=True)
        name = self.post("send", "--ordered", "--reply-to", self.sender,
                         self.requests, "request", body={"ping": True})
        self.assert_round()
        first_rows = json.loads((self.stack / "forwarded.json").read_text())
        first_forwarded = next(iter(first_rows))
        result = subprocess.run([sys.executable, str(ENTRY), str(second_policy)],
                                text=True, capture_output=True, env=second_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        forwarded, letter = self.read_new(self.ctl)
        self.assertEqual((self.ctl / letter["reply_to"]).resolve(), second / "replies")
        self.post("done", "--reply", self.ctl, forwarded, body={"applied": True})
        result = subprocess.run([sys.executable, str(ENTRY), str(second_policy)],
                                text=True, capture_output=True, env=second_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        reply_names = list((self.replies / "new").iterdir())
        self.assertEqual(len(reply_names), 1)
        reply = json.loads((reply_names[0] / "letter.json").read_text())
        self.assertEqual(reply["in_reply_to"], first_forwarded)
        self.assertEqual(list((self.sender / "new").iterdir()), [])
        self.assert_round()
        _, reply = self.read_new(self.sender)
        self.assertEqual(reply["in_reply_to"], name)
        self.assertEqual(reply["body"], {"applied": True})
        self.assertEqual(json.loads((second / "forwarded.json").read_text()), {})

    def test_missing_original_reply_mailbox_is_dropped_without_retry(self):
        self.configure(reply_via_me=True)
        self.post("send", "--reply-to", self.sender, self.requests, "request", body={"ping": True})
        self.assert_round()
        forwarded, _ = self.read_new(self.ctl)
        shutil.rmtree(self.sender)
        self.post("done", "--reply", self.ctl, forwarded, body={"applied": True})
        result = self.assert_round()
        self.assertIn("kernel: warning:", result.stderr)
        self.assertIn("could not be relayed", result.stderr)
        self.assertEqual(json.loads((self.stack / "forwarded.json").read_text()), {})
        self.assertEqual(list((self.replies / "cur").iterdir()), [])
        self.assertEqual(list((self.replies / "new").iterdir()), [])
        self.post("init", self.sender)
        result = self.assert_round()
        self.assertNotIn("could not be relayed", result.stderr)
        self.assertEqual(list((self.sender / "new").iterdir()), [])

    def test_restart_finishes_original_before_relaying_early_reply(self):
        self.configure(reply_via_me=True, keep_ordered=True)
        name = self.post("send", "--ordered", "--reply-to", self.sender,
                         self.requests, "request", body={"ping": True})
        self.post("take-all", self.requests)
        saved = self.root / "saved_request"
        shutil.copytree(self.requests / "cur" / name, saved)
        self.assert_round()
        forwarded, _ = self.read_new(self.ctl)
        shutil.copytree(saved, self.requests / "cur" / name)
        self.post("done", "--reply", self.ctl, forwarded, body={"applied": True})
        self.assert_round()
        self.assertFalse((self.requests / "cur" / name).exists())
        self.assertEqual(list((self.ctl / "new").iterdir()), [])
        self.assertEqual(list((self.ctl / "cur").iterdir()), [])
        _, reply = self.read_new(self.sender)
        self.assertEqual(reply["in_reply_to"], name)
        self.assertEqual(json.loads((self.stack / "forwarded.json").read_text()), {})

    def test_ordered_request_without_reply_to_is_not_resent_after_restart(self):
        self.configure(keep_ordered=True)
        name = self.post("send", "--ordered", self.requests, "request", body={"ping": True})
        self.post("take-all", self.requests)
        original = json.loads(self.post("see", self.requests, name))
        forwarded = self.post("send", "--ordered", self.ctl, "request", body=original["body"])
        (self.stack / "forwarded.json").write_text(json.dumps({
            forwarded: {"letter": name, "reply_to": None, "sender": original["sender"]}}))
        self.assert_round()
        self.assertFalse((self.requests / "cur" / name).exists())
        self.assertEqual([path.name for path in (self.ctl / "new").iterdir()], [forwarded])
        self.assertEqual(json.loads((self.stack / "forwarded.json").read_text()), {})
        self.assert_round()
        self.assertEqual([path.name for path in (self.ctl / "new").iterdir()], [forwarded])


if __name__ == "__main__":
    unittest.main()
