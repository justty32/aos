# 驗證只有 hook 拒因與重置時間的 BudgetMissing 回信會讓 wait 格冷卻後再試。
import json
import time
import unittest

import test_cooldown


class HookRetryLaterTest(unittest.TestCase):
    setUp = test_cooldown.Cooldown.setUp
    command = test_cooldown.Cooldown.command
    wait = test_cooldown.Cooldown.wait
    record = test_cooldown.Cooldown.record
    iso_at = test_cooldown.Cooldown.iso_at
    sends = test_cooldown.Cooldown.sends

    def test_hook_budget_missing_cools_until_reset_plus_five_seconds(self):
        reset = int(time.time()) + 600
        error = {"code": "BudgetMissing", "msg": "dept quota used up",
                 "resets_at": self.iso_at(reset), "scope": "hook", "hook": "quota"}
        self.wait(10)
        result = self.wait(10, FAKE_RECV="1", FAKE_REPLY=json.dumps({"error": error}),
                           FAKE_ERROR="aos-llm: error: BudgetMissing dept quota used up")
        record = self.record()
        self.assertEqual(record["code"], "BudgetMissing")
        self.assertAlmostEqual(test_cooldown.cooldown.parse(record["until"]), reset + 5, delta=1)
        self.assertIn("agent-fsm: warning: BudgetMissing dept quota used up", result.stderr)
        self.assertNotIn("agent-fsm: error:", result.stderr)
        self.assertFalse((self.stack / "think/pending.txt").exists())
        self.wait(10)
        self.assertEqual(self.sends(), 1)


if __name__ == "__main__":
    unittest.main()
