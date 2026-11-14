# 驗證判決 hook 退 10 的晚點重試回信、舊拒信，以及退 0 改判的原樣欄位。
import json
import unittest

import test_kernel_hooks


class HookRetryLaterTest(unittest.TestCase):
    fixture = test_kernel_hooks.KernelHooksTest.fixture
    post_result = test_kernel_hooks.KernelHooksTest.post_result
    post = test_kernel_hooks.KernelHooksTest.post
    kernel = test_kernel_hooks.KernelHooksTest.kernel
    configure = test_kernel_hooks.KernelHooksTest.configure
    assert_round = test_kernel_hooks.KernelHooksTest.assert_round
    read_new = test_kernel_hooks.KernelHooksTest.read_new
    fresh = test_kernel_hooks.KernelHooksTest.fresh
    handler = test_kernel_hooks.KernelHooksTest.handler
    hook = test_kernel_hooks.KernelHooksTest.hook
    send = test_kernel_hooks.KernelHooksTest.send
    reply_error = test_kernel_hooks.KernelHooksTest.reply_error

    RESET = "2026-11-14T16:00:00+08:00"
    MSG = "dept quota used up"

    def rejected_reply(self, event, stdout):
        self.fresh()
        self.configure(hooks=self.hook("quota", event, "print(%r)\nsys.exit(10)" % stdout))
        self.send({"procs_added": {"worker": {}}})
        self.assert_round()
        self.assertEqual(list((self.ctl / "new").iterdir()), [])
        return self.reply_error()

    def test_budget_missing_reset_absent_null_and_untrusted_fields(self):
        for event in ("before_verdict", "after_verdict"):
            for fields in ({"resets_at": self.RESET}, {}, {"resets_at": None},
                           {"resets_at": self.RESET, "scope": "total", "hook": "forged",
                            "window": "all", "limit": "max_calls", "max": 1, "unknown": True}):
                with self.subTest(event=event, fields=fields):
                    error = dict(fields, code="BudgetMissing", msg=self.MSG)
                    expected = {"code": "BudgetMissing", "msg": self.MSG, "scope": "hook", "hook": "quota"}
                    if "resets_at" in fields:
                        expected["resets_at"] = fields["resets_at"]
                    self.assertEqual(self.rejected_reply(event, json.dumps({"error": error})), expected)

    def test_other_stdout_keeps_exact_legacy_error(self):
        cases = ["  denied by policy  ", "", " \n\t ", "{bad json", "[]", "null", "42",
                 '{"error":{"code":"Other","msg":"x"}}',
                 json.dumps({"error": {"code": "Other", "msg": "x", "limit": 1}}),
                 json.dumps({"error": {"code": "BudgetMissing"}}),
                 json.dumps({"error": {"code": "BudgetMissing", "msg": ""}}),
                 json.dumps({"error": {"code": "BudgetMissing", "msg": 3}}),
                 json.dumps({"error": {"code": "BudgetMissing", "msg": "m", "resets_at": 123}}),
                 json.dumps({"error": {"code": "BudgetMissing", "msg": "m", "resets_at": False}}),
                 json.dumps({"error": []})]
        for event in ("before_verdict", "after_verdict"):
            for stdout in cases:
                with self.subTest(event=event, stdout=stdout):
                    self.assertEqual(self.rejected_reply(event, stdout),
                                     {"code": "HookRejected", "msg": stdout.strip() or "blocked by hook quota"})

    def test_after_verdict_exit_zero_keeps_hook_error_fields(self):
        self.fresh()
        error = {"code": "BudgetMissing", "msg": "m", "resets_at": self.RESET,
                 "scope": "hook", "hook": "x", "window": "all", "limit": "max_calls"}
        change = {"verdict": "refuse", "error": error}
        self.configure(hooks=self.hook("quota", "after_verdict", "print(json.dumps(%r))" % change))
        self.send({"procs_added": {"worker": {}}})
        self.assert_round()
        self.assertEqual(self.reply_error(), error)


if __name__ == "__main__":
    unittest.main()
