# 用真的 aos-post 與 aos-exec 驗證 after_verdict hook 的「先留著」（hold）與表態檔 decisions/<信名>.json。
import json
import unittest

import test_kernel
import test_kernel_hooks

HOLD = "print(json.dumps({'verdict': 'hold'}))"


class KernelHoldTest(unittest.TestCase):
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
    expire = test_kernel_hooks.KernelHooksTest.expire

    def setUp(self):
        self.fresh()

    def send(self, name, **body):
        return self.post("send", "--reply-to", self.sender, self.requests, name, body=body or {"ping": True})

    def names(self, box, slot="new"):
        return sorted(path.name for path in (box / slot).iterdir() if not path.name.startswith("."))

    def held(self):
        return [row["letter"] for row in json.loads((self.stack / "hold.json").read_text())["held"]]

    def decide(self, name, verdict, **more):
        folder = self.stack / "decisions"
        folder.mkdir(exist_ok=True)
        (folder / (name + ".json")).write_text(json.dumps(dict(verdict=verdict, **more)))

    def answers(self):
        self.post("take-all", self.sender)
        found = {}
        for name in self.names(self.sender, "cur"):
            letter = json.loads(self.post("see", self.sender, name))
            found[letter["in_reply_to"]] = letter["body"]
        return found

    def test_01_hold_keeps_the_letter_and_asks_the_hook_once(self):
        self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
        self.send("request", procs_added={"a": {}}, desc="please")
        for _ in range(3):
            self.assert_round()
        self.assertEqual(self.names(self.requests, "cur"), ["request"])
        self.assertEqual(self.names(self.ctl) + self.names(self.sender), [])
        self.assertEqual(self.held(), ["request"])
        row = json.loads((self.stack / "hold.json").read_text())["held"][0]
        self.assertEqual(sorted(row), ["held_at", "letter"])
        events = self.events()
        self.assertEqual([(e["event"], e["verdict"], e["decision"]) for e in events], [("after_verdict", "pass", None)])
        self.assertEqual(events[0]["body"]["desc"], "please")

    def test_02_pass_decision_forwards_on_the_next_round(self):
        self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
        body = {"procs_added": {"a": {}}, "desc": "please", "anything": [1, {"x": None}]}
        self.send("request", **body)
        self.assert_round()
        self.decide("request", "pass")
        self.assert_round()
        forwarded, letter = self.read_new(self.ctl)
        self.assertEqual((forwarded, letter["body"]), ("request", body))
        self.assertEqual(self.names(self.requests, "cur"), [])
        self.assertEqual(self.held(), [])
        self.assertFalse((self.stack / "decisions" / "request.json").exists())
        self.assertEqual([(e["verdict"], e["decision"]) for e in self.events()], [("pass", None), ("pass", "pass")])

    def test_03_refuse_decision_answers_the_sender(self):
        self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
        self.send("with-reason")
        self.send("no-reason")
        self.assert_round()
        self.decide("with-reason", "refuse", error={"code": "NotNow", "msg": "say what it is for"})
        self.decide("no-reason", "refuse")
        result = self.assert_round()
        self.assertEqual(self.answers(), {
            "with-reason": {"applied": False, "error": {"code": "NotNow", "msg": "say what it is for"}},
            "no-reason": {"applied": False, "error": {"code": "HoldRefused",
                                                      "msg": "refused by the decision for this letter"}}})
        self.assertIn("kernel: warning: letter with-reason refused: NotNow say what it is for", result.stderr)
        self.assertEqual(self.names(self.requests, "cur") + self.names(self.ctl), [])
        self.assertEqual(len(self.events()), 2)  # 表態拒的信不再問 hook。

    def test_04_sender_deadline_ends_the_hold(self):
        for decided in (False, True):
            with self.subTest(decided=decided):
                self.fresh()
                self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
                self.send("request", procs_added={"a": {}}, queue_wait_ms=600000)
                self.assert_round()
                row = json.loads((self.stack / "hold.json").read_text())["held"][0]
                self.assertIn("expires_at", row)
                self.expire("request")
                if decided:
                    self.decide("request", "pass")  # 期限過了才說 pass：不放行。
                self.assert_round()
                error = self.answers()["request"]["error"]
                self.assertEqual(error["code"], "SlotMissing")
                self.assertRegex(error["msg"], r"^held \d+ ms, nobody decided in time \(queue_wait_ms 600000\)$")
                self.assertEqual(self.names(self.ctl) + self.names(self.requests, "cur"), [])
                self.assertEqual(self.held(), [])
                self.assertEqual(len(self.events()), 1)

    def test_05_many_letters_stay_held_and_are_decided_one_by_one(self):
        self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
        for index in range(5):
            self.send("letter-%d" % index, n=index)
        self.assert_round()
        self.assertEqual(self.held(), ["letter-%d" % index for index in range(5)])
        self.decide("letter-1", "pass")
        self.decide("letter-3", "refuse", error={"code": "No", "msg": "no"})
        self.assert_round()
        self.assertEqual(self.names(self.ctl), ["letter-1"])
        self.assertEqual(list(self.answers()), ["letter-3"])
        self.assertEqual(self.held(), ["letter-0", "letter-2", "letter-4"])
        self.send("letter-5")
        self.assert_round()
        self.assertEqual(self.held(), ["letter-0", "letter-2", "letter-4", "letter-5"])
        self.assertEqual(len(self.events()), 7)  # 六封各一次，加 letter-1 表態後重判一次。

    def test_06_changed_body_is_kept_while_held(self):
        changed = {"procs_added": {"b": {}}, "note": "rewritten"}
        hooks = self.hook("rewrite", "before_verdict", "print(json.dumps({'body': %r}))" % changed)
        hooks.update(self.hook("ask", "after_verdict", HOLD))
        self.configure(hooks=hooks)
        self.send("request", procs_added={"a": {}})
        self.assert_round()
        self.assertEqual(json.loads((self.stack / "bodies" / "request.json").read_text()), changed)
        self.assert_round()
        self.decide("request", "pass")
        self.assert_round()
        self.assertEqual(self.read_new(self.ctl)[1]["body"], changed)
        self.assertFalse((self.stack / "bodies" / "request.json").exists())
        self.assertEqual([e["event"] for e in self.events()], ["before_verdict", "after_verdict", "after_verdict"])

    def test_07_pass_decision_still_goes_through_the_rules(self):
        # 規則拒的信被 hook 留下、有人說 pass：重判時規則照樣拒。
        self.configure(allowed=["a"], hooks=self.hook("ask", "after_verdict", HOLD))
        self.send("request", procs_added={"zzz": {}})
        self.assert_round()
        self.assertEqual(self.events()[0]["verdict"], "refuse")
        self.assertEqual(self.held(), ["request"])
        self.decide("request", "pass")
        self.assert_round()
        self.assertEqual(self.answers()["request"]["error"]["code"], "NameUnknown")
        self.assertEqual(self.names(self.ctl), [])

    def test_08_decided_letter_can_wait_for_a_slot_without_being_held_again(self):
        self.configure(max_running=0, queue=True, hooks=self.hook("ask", "after_verdict", HOLD, condition="pass"))
        self.send("request", procs_added={"a": {}})
        self.assert_round()  # 沒格：排隊（hook 只看 pass，沒被問）。
        self.assertEqual(self.events(), [])
        self.configure(max_running=1, queue=True, hooks=self.hook("ask", "after_verdict", HOLD, condition="pass"))
        self.assert_round()  # 出隊：hook 留下。
        self.assertEqual(self.held(), ["request"])
        self.configure(max_running=0, queue=True, hooks=self.hook("ask", "after_verdict", HOLD))
        self.decide("request", "pass")
        self.assert_round()  # 表態了但沒格：排隊，表態檔留著。
        self.assertEqual(self.held(), [])
        self.assertEqual([row["letter"] for row in json.loads((self.stack / "queue.json").read_text())["queued"]],
                         ["request"])
        self.assertTrue((self.stack / "decisions" / "request.json").exists())
        self.configure(max_running=1, queue=True, hooks=self.hook("ask", "after_verdict", HOLD))
        self.assert_round()  # 有格了：hook 再回 hold 不算數，放行。
        self.assertEqual(self.names(self.ctl), ["request"])
        self.assertFalse((self.stack / "decisions" / "request.json").exists())
        self.assertEqual(self.events()[-1]["decision"], "pass")

    def test_09_route_hook_runs_again_after_the_decision(self):
        side = self.root / "side" / "requests"
        self.post("init", side)
        hooks = self.hook("ask", "after_verdict", HOLD)
        hooks.update(self.hook("route", "after_verdict", "print(json.dumps({'next': %r}))" % str(side)))
        self.configure(hooks=hooks)
        self.send("request")
        self.assert_round()
        self.assertEqual(self.names(side) + self.names(self.ctl), [])
        self.decide("request", "pass")
        self.assert_round()
        self.assertEqual((self.names(side), self.names(self.ctl)), (["request"], []))

    def test_10_broken_files_do_not_lose_letters(self):
        self.configure(hooks=self.hook("ask", "after_verdict", HOLD))
        self.send("request")
        self.assert_round()
        self.decide("request", "maybe")
        result = self.assert_round()
        self.assertIn("kernel: warning: decision for letter request is broken", result.stderr)
        self.assertFalse((self.stack / "decisions" / "request.json").exists())
        self.assertEqual(self.held(), ["request"])
        (self.stack / "hold.json").write_text("{")
        result = self.assert_round()
        self.assertIn("kernel: warning: cannot read hold.json", result.stderr)
        self.assertEqual(self.held(), ["request"])
        self.assertEqual(len(self.events()), 2)  # 窗壞了：當新信再問一次 hook。
        self.decide("gone", "pass")  # 站裡沒有的信：表態檔收掉。
        self.assert_round()
        self.assertFalse((self.stack / "decisions" / "gone.json").exists())

    def test_11_rules_first_then_hold_only_what_the_hook_picks(self):
        script = ("if 'desc' in (event.get('body') or {}):\n"
                  "    print(json.dumps({'verdict': 'hold'}))")
        self.configure(allowed=["a"], hooks=self.hook("ask", "after_verdict", script, condition="pass"))
        self.send("refused-by-rule", procs_added={"zzz": {}}, desc="x")
        self.send("sure", procs_added={"a": {}})
        self.send("unsure", procs_added={"a": {}}, desc="x")
        self.assert_round()
        self.assertEqual(self.names(self.ctl), ["sure"])
        self.assertEqual(self.answers()["refused-by-rule"]["error"]["code"], "NameUnknown")
        self.assertEqual(self.held(), ["unsure"])

    def test_12_other_hold_like_values_are_hook_failures(self):
        self.configure(hooks=self.hook("ask", "after_verdict", "print(json.dumps({'verdict': 'wait'}))"))
        self.send("request")
        result = self.kernel()
        self.assertEqual(result.returncode, 1)
        self.assertIn("verdict in stdout must be pass, refuse or hold", result.stderr)


if __name__ == "__main__":
    unittest.main()
