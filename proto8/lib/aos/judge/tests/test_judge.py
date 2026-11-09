# Verify broken reply recovery and restart deduplication with real aos-post mailboxes.
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ENTRY = Path(__file__).resolve().parents[1] / "_entry"
PROTO8 = ENTRY.parents[3]
POST = PROTO8 / "impls/aos-post/bin/aos-post"
DIRECTIVE = PROTO8 / "impls/aos-directive/bin"


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.fixture()

    def fixture(self, **policy):
        scratch = os.environ.get("JUDGE_TEST_TMP", "/tmp")
        self.root = Path(subprocess.check_output(
            ["mktemp", "-d", str(Path(scratch) / "judge-test.XXXXXX")], text=True).strip())
        self.stack = self.root / "stack"
        self.daemon = self.root / "daemon"
        self.stack.mkdir()
        self.daemon.mkdir()
        self.requests = self.stack / "requests"
        self.replies = self.stack / "judge_replies"
        self.ctl = self.daemon / "procs_ctl_mailbox"
        self.sender = self.root / "sender"
        self.policy = self.root / "judge.json"
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

    def judge(self):
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
            result = self.judge()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((self.ctl / "new" / name / "letter.json").is_file())
            self.assertFalse(broken.exists())
            if index == 0:
                self.assertIn("judge: warning: reply broken-reply is broken; dropped", result.stderr)
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
        result = self.judge()
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
            (self.stack / "judge_ordered.json").write_text(json.dumps({
                forwarded: {"letter": name, "reply_to": str(self.sender)}}))
        result = self.judge()
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


if __name__ == "__main__":
    unittest.main()
