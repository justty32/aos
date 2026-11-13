# 用真的 aos-post 與 aos-exec 驗證 after_verdict hook 替單封信指定下一站（照規則分流）與各種邊緣。
import json
import os
import unittest

import test_kernel
import test_kernel_hooks


class KernelRouteTest(unittest.TestCase):
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
    reply_error = test_kernel_hooks.KernelHooksTest.reply_error

    def setUp(self):
        self.start()

    def start(self):
        self.fresh()
        self.side = self.root / "side" / "requests"
        self.post("init", self.side)

    def route_hook(self, event="after_verdict", table=None, **options):
        """照 body 的 lane 欄挑下一站；表裡沒有的 lane 不說話。"""
        table = {"side": str(self.side)} if table is None else table
        script = ("target = %r.get((event.get('body') or {}).get('lane'), 'unset')\n"
                  "if target != 'unset':\n"
                  "    print(json.dumps({'next': target}))" % table)
        return self.hook("route", event, script, **options)

    def send(self, name, lane=None, **body):
        if lane is not None:
            body["lane"] = lane
        return self.post("send", "--reply-to", self.sender, self.requests, name, body=body or {"ping": True})

    def names(self, box, slot="new"):
        return sorted(path.name for path in (box / slot).iterdir() if not path.name.startswith("."))

    def test_01_next_from_after_verdict_sends_each_letter_to_one_station(self):
        self.configure(hooks=self.route_hook())
        self.send("to-side", lane="side")
        self.send("to-default", lane="main")
        self.send("plain")
        self.assert_round()
        self.assertEqual(self.names(self.side), ["to-side"])
        self.assertEqual(self.names(self.ctl), ["plain", "to-default"])
        self.assertEqual(self.names(self.requests, "cur"), [])
        events = self.events()
        self.assertEqual([event["next"] for event in events], [None] * 3)
        self.assertEqual(self.names(self.sender), [])

    def test_02_other_events_cannot_choose_next(self):
        for event in ("before_verdict", "before_reply"):
            with self.subTest(event=event):
                self.start()
                self.configure(reply_via_me=True, hooks=self.route_hook(event))
                self.send("request", lane="side")
                self.assert_round()
                forwarded, _ = self.read_new(self.ctl)
                self.assertEqual(self.names(self.side), [])
                if event == "before_reply":
                    self.post("done", "--reply", self.ctl, forwarded, body={"lane": "side"})
                    self.assert_round()
                    self.assertEqual(self.read_new(self.sender)[1]["in_reply_to"], "request")
                    self.assertEqual(self.names(self.side), [])

    def test_03_replies_return_from_both_stations(self):
        self.configure(reply_via_me=True, hooks=self.route_hook())
        self.send("to-side", lane="side")
        self.send("to-default")
        self.assert_round()
        records = json.loads((self.stack / "forwarded.json").read_text())
        self.assertEqual({key: row["letter"] for key, row in records.items()},
                         {"to-side": "to-side", "to-default": "to-default"})
        for box, name in ((self.side, "to-side"), (self.ctl, "to-default")):
            forwarded, letter = self.read_new(box)
            self.assertEqual(forwarded, name)
            self.assertEqual(os.path.realpath(os.path.join(box, letter["reply_to"])), str(self.replies))
            self.post("done", "--reply", box, forwarded, body={"from": name})
        self.assert_round()
        self.post("take-all", self.sender)
        replies = [json.loads(self.post("see", self.sender, name)) for name in self.names(self.sender, "cur")]
        self.assertEqual(sorted((reply["in_reply_to"], reply["body"]["from"]) for reply in replies),
                         [("to-default", "to-default"), ("to-side", "to-side")])
        self.assertEqual(json.loads((self.stack / "forwarded.json").read_text()), {})

    def test_04_keep_ordered_with_next_is_a_configuration_error(self):
        self.configure(keep_ordered=True, hooks=self.route_hook())
        name = self.post("send", "--ordered", self.requests, "request", body={"lane": "side"})
        result = self.kernel()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("kernel: error: CfgBad a hook gave next but keep_ordered is on", result.stderr)
        self.assertEqual(self.names(self.requests, "cur"), [name])
        self.assertEqual(self.names(self.side) + self.names(self.ctl), [])
        # 沒開 keep_ordered：有序信照處理順序分到各站，轉出去是普通信。
        self.configure(hooks=self.route_hook())
        self.post("send", "--ordered", self.requests, "second", body={"ping": True})
        self.assert_round()
        self.assertEqual(self.names(self.side), ["request"])
        self.assertEqual(self.names(self.ctl), ["second"])

    def test_05_max_running_needs_count_daemon_and_counts_all_stations_together(self):
        self.configure(max_running=1, hooks=self.route_hook())
        name = self.send("first", lane="side", procs_added={"one": {}})
        result = self.kernel()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("kernel: error: CfgBad a hook gave next with max_running but count_daemon", result.stderr)
        self.assertEqual(self.names(self.requests, "cur"), [name])
        self.configure(max_running=1, count_daemon=str(self.daemon), hooks=self.route_hook())
        self.send("second", procs_added={"two": {}})
        self.assert_round()
        self.assertEqual(self.names(self.side), ["first"])
        self.assertEqual(self.names(self.ctl), [])
        self.assertEqual(self.reply_error()["code"], "SlotMissing")

    def test_06_unreachable_next_refuses_with_forward_failed(self):
        self.configure(hooks=self.route_hook(table={"gone": str(self.root / "gone" / "requests")}))
        self.send("request", lane="gone")
        self.assert_round()
        self.assertEqual(self.reply_error()["code"], "ForwardFailed")
        self.assertEqual(self.names(self.requests, "cur") + self.names(self.ctl), [])

    def test_07_bad_next_is_the_hooks_own_failure(self):
        for label, value in (("self", None), ("relative", "side/requests"), ("empty", ""), ("number", 7)):
            for mode in ("stop", "continue"):
                with self.subTest(value=label, mode=mode):
                    self.start()
                    if label == "self":
                        shortcut = self.root / "own_box"
                        shortcut.symlink_to(self.requests, target_is_directory=True)
                        value = str(shortcut)
                    self.configure(hooks=self.route_hook(table={"bad": value}, on_error=mode))
                    name = self.send("request", lane="bad")
                    result = self.kernel()
                    self.assertEqual(self.names(self.side), [])
                    if mode == "stop":
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn("kernel: error: HookFailed hook route (event after_verdict) failed: "
                                      "next in stdout must ", result.stderr)
                        self.assertEqual(self.names(self.requests, "cur"), [name])
                        self.assertEqual(self.names(self.ctl), [])
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("on_error: continue", result.stderr)
                        self.assertEqual(self.names(self.ctl), [name])

    def test_08_broken_route_hook_follows_on_error(self):
        for mode in ("stop", "continue"):
            with self.subTest(mode=mode):
                self.start()
                hooks = self.hook("route", "after_verdict", "time.sleep(30)", on_error=mode, timeout_ms=200)
                self.configure(hooks=hooks)
                name = self.send("request", lane="side")
                result = self.kernel()
                self.assertEqual(result.returncode, 1 if mode == "stop" else 0, result.stderr)
                self.assertEqual(self.names(self.side), [])
                self.assertEqual(self.names(self.ctl), [] if mode == "stop" else [name])
                self.assertEqual(self.names(self.requests, "cur"), [name] if mode == "stop" else [])

    def test_09_queued_letter_is_routed_when_it_leaves_the_queue(self):
        policy = dict(queue=True, count_daemon=str(self.daemon), hooks=self.route_hook())
        self.configure(max_running=0, **policy)
        name = self.send("request", lane="side", procs_added={"worker": {}})
        self.assert_round()
        self.assertEqual(self.names(self.requests, "cur"), [name])
        self.assertEqual(self.names(self.side) + self.names(self.ctl), [])
        self.configure(max_running=1, **policy)
        self.assert_round()
        self.assertEqual(self.names(self.side), [name])
        self.assertEqual(self.names(self.ctl), [])
        self.assertEqual([event["verdict"] for event in self.events()], ["queue", "pass"])

    def test_10_letter_already_in_the_chosen_station_is_not_sent_twice(self):
        self.configure(hooks=self.route_hook())
        name = self.send("request", lane="side")
        self.post("send", self.side, name, body={"lane": "side"})
        result = self.assert_round()
        self.assertNotIn("refused", result.stderr)
        self.assertEqual(self.names(self.side), [name])
        self.assertEqual(self.names(self.requests, "cur") + self.names(self.ctl) + self.names(self.sender), [])

    def test_11_null_next_and_refused_letters_keep_the_usual_path(self):
        self.configure(allowed=[], hooks=self.route_hook(table={"none": None, "side": str(self.side)}))
        self.send("default", lane="none")
        self.send("refused", lane="side", procs_added={"forbidden": {}})
        self.assert_round()
        self.assertEqual(self.names(self.ctl), ["default"])
        self.assertEqual(self.names(self.side), [])
        self.assertEqual(self.reply_error()["code"], "NameUnknown")

    def test_12_hook_can_pass_a_refused_letter_and_route_it(self):
        script = "print(json.dumps({'verdict': 'pass', 'next': %r}))" % str(self.side)
        self.configure(allowed=[], hooks=self.hook("route", "after_verdict", script, condition="refuse"))
        name = self.send("request", procs_added={"forbidden": {}})
        self.assert_round()
        self.assertEqual(self.names(self.side), [name])
        self.assertEqual(self.names(self.ctl) + self.names(self.sender), [])


if __name__ == "__main__":
    unittest.main()
