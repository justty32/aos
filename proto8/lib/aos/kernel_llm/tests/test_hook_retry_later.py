# 驗證問腦站將判決 hook 的晚點重試拒因送回 agent 的 think/reply 信箱。
import json
import unittest

import test_hooks


class HookRetryLaterTest(unittest.TestCase):
    setUp = test_hooks.HookTests.setUp
    configure = test_hooks.HookTests.configure
    run_kernel = test_hooks.HookTests.run_kernel
    send = test_hooks.HookTests.send
    replies = test_hooks.HookTests.replies

    def think_reply_box(self):
        self.box = self.stack / "think" / "reply"
        for part in ("new", "tmp", "cur"):
            (self.box / part).mkdir(parents=True)

    def test_before_verdict_budget_missing_reaches_think_reply(self):
        error = {"code": "BudgetMissing", "msg": "dept quota used up",
                 "resets_at": "2026-11-14T16:00:00+08:00"}
        self.configure("before_verdict", "print(json.dumps(%r))\nsys.exit(10)" % {"error": error})
        self.think_reply_box()
        self.send("blocked", "hello")
        self.run_kernel()
        self.assertEqual(self.replies(), {"blocked": {"error": dict(error, scope="hook", hook="probe")}})
        self.assertFalse((self.stack / "requests/new/blocked").exists())
        self.assertFalse((self.stack / "requests/cur/blocked/proc.json").exists())

    def test_after_verdict_exit_zero_keeps_hook_error_in_think_reply(self):
        error = {"code": "BudgetMissing", "msg": "m", "resets_at": "2026-11-14T16:00:00+08:00",
                 "scope": "hook", "hook": "x", "window": "hour", "limit": "max_calls"}
        self.configure("after_verdict", "print(json.dumps(%r))" % {"verdict": "refuse", "error": error})
        self.think_reply_box()
        self.send("overruled", "hello")
        self.run_kernel()
        self.assertEqual(self.replies(), {"overruled": {"error": error}})
        self.assertFalse((self.stack / "requests/cur/overruled/proc.json").exists())


if __name__ == "__main__":
    unittest.main()
