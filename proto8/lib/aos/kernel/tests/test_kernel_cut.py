# 驗證轉寄中途行程被砍（寄出前、寄出後還沒記對照）重起後不重寄、不漏寄、回信仍代得回去。
import json
import os
import sys
import unittest

import test_kernel
import test_kernel_hooks

HOLD = "print(json.dumps({'verdict': 'hold'}))"
# 假的 aos-post：其餘照轉給真的；寄到 KERNEL_TEST_CUT 那個信箱的 send，寄之前或寄成功之後砍掉叫它的站。
WRAPPER = """#!%s
# 測試用的 aos-post 外殼：在指定的 send 前後砍掉呼叫它的行程，模擬站被中斷。
import os, signal, subprocess, sys
cut = os.environ.get("KERNEL_TEST_CUT")
hit = bool(cut) and sys.argv[1:2] == ["send"] and cut in sys.argv
if hit and os.environ.get("KERNEL_TEST_CUT_WHEN") == "before":
    os.kill(os.getppid(), signal.SIGKILL)
    sys.exit(1)
result = subprocess.run([%r] + sys.argv[1:], input=sys.stdin.read(), text=True, stdout=subprocess.PIPE)
if hit and result.returncode == 0:
    os.kill(os.getppid(), signal.SIGKILL)
    sys.exit(1)
sys.stdout.write(result.stdout)
sys.exit(result.returncode)
"""


class KernelCutTest(unittest.TestCase):
    fixture = test_kernel.KernelTest.fixture
    post_result = test_kernel.KernelTest.post_result
    post = test_kernel.KernelTest.post
    kernel = test_kernel.KernelTest.kernel
    configure = test_kernel.KernelTest.configure
    assert_round = test_kernel.KernelTest.assert_round
    read_new = test_kernel.KernelTest.read_new
    fresh = test_kernel_hooks.KernelHooksTest.fresh
    handler = test_kernel_hooks.KernelHooksTest.handler
    hook = test_kernel_hooks.KernelHooksTest.hook
    events = test_kernel_hooks.KernelHooksTest.events

    def setUp(self):
        self.start()

    def start(self):
        self.fresh()
        folder = self.root / "cutbin"
        folder.mkdir()
        wrapper = folder / "aos-post"
        wrapper.write_text(WRAPPER % (sys.executable, str(test_kernel.POST)))
        wrapper.chmod(0o755)
        self.env["PATH"] = str(folder) + os.pathsep + self.env["PATH"]
        self.side = self.root / "side" / "requests"
        self.post("init", self.side)

    def names(self, box, slot="new"):
        return sorted(path.name for path in (box / slot).iterdir() if not path.name.startswith("."))

    def everywhere(self, box):
        return self.names(box) + self.names(box, "cur")

    def records(self):
        path = self.stack / "forwarded.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def send(self, name="request", ordered=False, reply=True, **body):
        args = ["send"]
        if reply:
            args += ["--reply-to", self.sender]
        if ordered:
            args.append("--ordered")
        return self.post(*args, self.requests, name, body=body or {"ping": True})

    def cut_round(self, box, when="after"):
        """跑一輪，在寄到 box 的那一次 send 前（before）或寄成功後（after）砍掉站。"""
        self.env.update(KERNEL_TEST_CUT=str(box), KERNEL_TEST_CUT_WHEN=when)
        result = self.kernel()
        del self.env["KERNEL_TEST_CUT"], self.env["KERNEL_TEST_CUT_WHEN"]
        self.assertEqual(result.returncode, -9, result.stderr)
        return result

    def answer(self, box, original):
        """下游收信、回信；站再跑一輪後原寄件人收到以原信名回的那一封。"""
        forwarded, _ = self.read_new(box)
        self.post("done", "--reply", box, forwarded, body={"from": forwarded})
        result = self.assert_round()
        self.assertNotIn("no forwarding record", result.stderr)
        name, reply = self.read_new(self.sender)
        self.assertEqual((reply["in_reply_to"], reply["body"]), (original, {"from": forwarded}))
        self.post("done", self.sender, name)
        self.assertEqual(self.records(), {})

    def test_01_plain_letter_cut_after_send_is_not_resent_and_reply_returns(self):
        self.configure(reply_via_me=True)
        name = self.send()
        self.cut_round(self.ctl)
        self.assertEqual((self.names(self.ctl), self.names(self.requests, "cur")), ([name], [name]))
        self.assert_round()
        self.assertEqual((self.everywhere(self.ctl), self.names(self.requests, "cur")), ([name], []))
        self.assertEqual(list(self.records()), [name])
        self.answer(self.ctl, name)
        self.assertEqual(self.everywhere(self.ctl), [])

    def test_02_reply_that_arrived_before_the_restart_still_returns(self):
        self.configure(reply_via_me=True)
        name = self.send()
        self.cut_round(self.ctl)
        forwarded, _ = self.read_new(self.ctl)
        self.post("done", "--reply", self.ctl, forwarded, body={"done": True})
        result = self.assert_round()
        self.assertNotIn("no forwarding record", result.stderr)
        self.assertEqual(self.everywhere(self.ctl) + self.names(self.requests, "cur"), [])
        _, reply = self.read_new(self.sender)
        self.assertEqual((reply["in_reply_to"], reply["body"]), (name, {"done": True}))
        self.assertEqual(self.records(), {})

    def test_03_ordered_letter_cut_after_send_is_not_resent(self):
        for relay in (True, False):
            with self.subTest(reply_via_me=relay):
                self.start()
                self.configure(keep_ordered=True, reply_via_me=relay)
                name = self.send(ordered=True)
                self.cut_round(self.ctl)
                sent = self.names(self.ctl)
                self.assertEqual(len(sent), 1, sent)
                self.assertRegex(sent[0], r"^[0-9]{12}\.request$")
                self.assert_round()
                self.assert_round()
                self.assertEqual((self.everywhere(self.ctl), self.names(self.requests, "cur")), (sent, []))
                if relay:
                    self.assertEqual(self.records()[sent[0]]["letter"], name)
                    self.answer(self.ctl, name)
                else:
                    self.assertEqual(self.records(), {})

    def test_04_ordered_reply_that_arrived_before_the_restart_still_returns(self):
        self.configure(keep_ordered=True, reply_via_me=True)
        name = self.send(ordered=True)
        self.cut_round(self.ctl)
        forwarded, _ = self.read_new(self.ctl)
        self.post("done", "--reply", self.ctl, forwarded, body={"done": True})
        result = self.assert_round()
        self.assertNotIn("no forwarding record", result.stderr)
        self.assertEqual(self.everywhere(self.ctl) + self.names(self.requests, "cur"), [])
        _, reply = self.read_new(self.sender)
        self.assertEqual((reply["in_reply_to"], reply["body"]), (name, {"done": True}))
        self.assertEqual(self.records(), {})

    def test_05_cut_before_send_sends_once_after_restart(self):
        for ordered in (False, True):
            with self.subTest(ordered=ordered):
                self.start()
                self.configure(keep_ordered=True, reply_via_me=True)
                name = self.send(ordered=ordered)
                self.cut_round(self.ctl, when="before")
                self.assertEqual((self.everywhere(self.ctl), self.names(self.requests, "cur")), ([], [name]))
                self.assert_round()
                self.assertEqual(len(self.everywhere(self.ctl)), 1)
                self.assertEqual(self.names(self.requests, "cur"), [])
                self.assert_round()
                self.assertEqual(len(self.everywhere(self.ctl)), 1)
                self.answer(self.ctl, name)

    def test_06_earlier_ordered_letter_with_the_same_tail_is_not_mistaken(self):
        self.configure(keep_ordered=True)
        self.send(ordered=True, reply=False)
        self.assert_round()
        first = self.names(self.ctl)
        self.assertEqual(len(first), 1)
        second = self.send(ordered=True, reply=False)
        self.cut_round(self.ctl, when="before")
        self.assertEqual((self.names(self.ctl), self.names(self.requests, "cur")), (first, [second]))
        self.assert_round()
        self.assertEqual(len(self.names(self.ctl)), 2)
        self.assertEqual(self.names(self.requests, "cur"), [])
        self.assert_round()
        self.assertEqual(len(self.names(self.ctl)), 2)
        self.assertEqual(self.records(), {})

    def test_07_failed_send_leaves_no_record(self):
        for ordered in (False, True):
            with self.subTest(ordered=ordered):
                self.start()
                self.configure(next=str(self.root / "gone" / "requests"), keep_ordered=True, reply_via_me=True)
                self.send(ordered=ordered)
                self.assert_round()
                _, reply = self.read_new(self.sender)
                self.assertEqual(reply["body"]["error"]["code"], "ForwardFailed")
                self.assertEqual(self.names(self.requests, "cur"), [])
                self.assertEqual(self.records(), {})

    def test_08_letter_routed_by_a_hook_cut_after_send(self):
        script = "print(json.dumps({'next': %r}))" % str(self.side)
        self.configure(reply_via_me=True, hooks=self.hook("route", "after_verdict", script))
        name = self.send()
        self.cut_round(self.side)
        self.assertEqual((self.names(self.side), self.names(self.requests, "cur")), ([name], [name]))
        self.assert_round()
        self.assertEqual((self.everywhere(self.side), self.names(self.requests, "cur")), ([name], []))
        self.assertEqual(self.everywhere(self.ctl), [])
        self.assertEqual(len(self.events()), 1)  # 重起那一輪靠待定列認出已寄出，沒再問 hook。
        self.answer(self.side, name)

    def test_09_routed_reply_that_arrived_before_the_restart_still_returns(self):
        script = "print(json.dumps({'next': %r}))" % str(self.side)
        self.configure(reply_via_me=True, hooks=self.hook("route", "after_verdict", script))
        name = self.send()
        self.cut_round(self.side)
        forwarded, _ = self.read_new(self.side)
        self.post("done", "--reply", self.side, forwarded, body={"done": True})
        result = self.assert_round()
        self.assertNotIn("no forwarding record", result.stderr)
        self.assertEqual(self.everywhere(self.side) + self.everywhere(self.ctl) + self.names(self.requests, "cur"), [])
        _, reply = self.read_new(self.sender)
        self.assertEqual((reply["in_reply_to"], reply["body"]), (name, {"done": True}))

    def test_10_held_letter_passed_then_cut_after_send(self):
        self.configure(reply_via_me=True, hooks=self.hook("ask", "after_verdict", HOLD))
        name = self.send()
        self.assert_round()
        self.assertEqual(self.everywhere(self.ctl), [])
        folder = self.stack / "decisions"
        folder.mkdir()
        (folder / (name + ".json")).write_text(json.dumps({"verdict": "pass"}))
        self.cut_round(self.ctl)
        self.assertEqual((self.names(self.ctl), self.names(self.requests, "cur")), ([name], [name]))
        self.assert_round()
        self.assertEqual((self.everywhere(self.ctl), self.names(self.requests, "cur")), ([name], []))
        self.assertEqual(json.loads((self.stack / "hold.json").read_text()), {"held": []})
        self.assertFalse((folder / (name + ".json")).exists())
        self.answer(self.ctl, name)

    def test_11_window_that_cannot_be_told_apart_sends_again(self):
        # 下游已做完移走、回信還沒到（或不經本站）就重起：分不出「沒寄出」，照沒寄出重寄（README 寫明的窗）。
        for ordered in (False, True):
            with self.subTest(ordered=ordered):
                self.start()
                self.configure(keep_ordered=ordered, reply_via_me=not ordered)
                name = self.send(ordered=ordered)
                self.cut_round(self.ctl)
                forwarded, _ = self.read_new(self.ctl)
                self.post("done", self.ctl, forwarded)
                self.assert_round()
                self.assertEqual(len(self.names(self.ctl)), 1)
                self.assertEqual(self.names(self.requests, "cur"), [])
                if ordered:
                    self.assertEqual(self.records(), {})
                else:
                    self.answer(self.ctl, name)

    def test_12_broken_pending_record_is_state_bad(self):
        (self.stack / "forwarded.json").write_text(json.dumps({
            "pending/request": {"letter": "request", "reply_to": None, "sender": None, "pending": "yes"}}))
        result = self.kernel()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("kernel: error: StateBad cannot read forwarded.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
