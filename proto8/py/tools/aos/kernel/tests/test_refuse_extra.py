# 驗證 kernel 框架：refuse 可帶額外錯誤鍵；after_verdict 保留包的額外鍵與 hook 自己加的鍵。
import copy
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


KERNEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KERNEL.parents[2]))
sys.path.insert(0, str(KERNEL))
import hooks  # noqa: E402
import letters  # noqa: E402
import procs_rules  # noqa: E402


class RefuseExtraTest(unittest.TestCase):
    def refuse(self, function, *args):
        sent = []
        warns = []
        ctx = types.SimpleNamespace(warn=warns.append, requests="/r")

        def post(argv, text=""):
            sent.append(json.loads(text) if text else None)
            return 0, ""
        with mock.patch.object(letters, "post", post):
            function(ctx, "L1", {}, *args)
        return sent[0]

    def test_letters_refuse_without_extra_is_unchanged(self):
        self.assertEqual(self.refuse(letters.refuse, "Quota", "too many"),
                         {"applied": False, "error": {"code": "Quota", "msg": "too many"}})

    def test_letters_refuse_with_extra_adds_keys_but_never_overwrites_code_msg(self):
        reply = self.refuse(letters.refuse, "Quota", "too many", {"limit": 3, "code": "X", "msg": "Y"})
        self.assertEqual(reply["error"], {"limit": 3, "code": "Quota", "msg": "too many"})
        self.assertIs(reply["applied"], False)

    def test_procs_rules_refuse_passes_extra_on(self):
        self.assertEqual(self.refuse(procs_rules.refuse, "Quota", "m")["error"], {"code": "Quota", "msg": "m"})
        self.assertEqual(self.refuse(procs_rules.refuse, "Quota", "m", {"n": 1})["error"],
                         {"n": 1, "code": "Quota", "msg": "m"})


class AfterVerdictExtraTest(unittest.TestCase):
    def run_hooks(self, detail, change=None, verdict="refuse"):
        """change(error) 改 hook 看到的 error；回 (after_verdict 的結果, hook 看到的 error)。"""
        ctx = types.SimpleNamespace(can_hold=False, check_next=None, route={}, warn=lambda line: None,
                                    cfg={"hooks": {"h": {"event": "after_verdict"}}})
        seen = []

        def fire(_ctx, event, data, entries=None):
            data = copy.deepcopy(data)
            seen.append(copy.deepcopy(data["error"]))
            changed = []
            if change is not None:
                change(data["error"])
                changed = ["error"]
            return {"data": data, "changed": changed, "blocked": False, "hook": "h", "text": ""}
        with mock.patch.object(hooks, "fire", fire):
            result = hooks.after_verdict(ctx, "L1", {"body": {}}, verdict, detail)
        return result, seen[0]

    def test_pack_extra_reaches_the_hook_and_the_reply(self):
        result, seen = self.run_hooks(("BudgetMissing", "used up", {"scope": "total", "code": "bad", "max": 5}))
        self.assertEqual(seen, {"scope": "total", "max": 5, "code": "BudgetMissing", "msg": "used up"})
        self.assertEqual(result, ("refuse", ("BudgetMissing", "used up", {"scope": "total", "max": 5})))

    def test_two_item_detail_returns_two_items(self):
        result, seen = self.run_hooks(("Quota", "no"))
        self.assertEqual(seen, {"code": "Quota", "msg": "no"})
        self.assertEqual(result, ("refuse", ("Quota", "no")))

    def test_hook_added_key_is_kept_and_a_changed_msg_too(self):
        def change(error):
            error["hint"] = "later"
            error["msg"] = "changed"
        result, _ = self.run_hooks(("BudgetMissing", "used up", {"scope": "total"}), change)
        self.assertEqual(result, ("refuse", ("BudgetMissing", "changed", {"scope": "total", "hint": "later"})))

    def test_hook_added_key_on_a_two_item_detail(self):
        result, _ = self.run_hooks(("Quota", "no"), lambda error: error.update(hint=1))
        self.assertEqual(result, ("refuse", ("Quota", "no", {"hint": 1})))

    def test_code_changed_drops_the_pack_extras_but_keeps_hook_keys(self):
        def change(error):
            error["code"] = "Quota"
            error["mine"] = True
        result, _ = self.run_hooks(("BudgetMissing", "used up", {"scope": "total", "max": 5}), change)
        self.assertEqual(result, ("refuse", ("Quota", "used up", {"mine": True})))

    def test_code_changed_alone_gives_two_items(self):
        result, _ = self.run_hooks(("BudgetMissing", "used up", {"scope": "total"}),
                                   lambda error: error.update(code="Quota"))
        self.assertEqual(result, ("refuse", ("Quota", "used up")))

    def test_code_changed_keeps_a_pack_key_the_hook_gave_a_new_value(self):
        def change(error):
            error["code"] = "Quota"
            error["scope"] = "mine"
        result, _ = self.run_hooks(("BudgetMissing", "m", {"scope": "total", "max": 5}), change)
        self.assertEqual(result, ("refuse", ("Quota", "m", {"scope": "mine"})))

    def test_hook_overruling_to_its_own_error_without_extras(self):
        def change(error):
            error.clear()
            error.update(code="Own", msg="mine")
        result, _ = self.run_hooks(("BudgetMissing", "m", {"scope": "total"}), change)
        self.assertEqual(result, ("refuse", ("Own", "mine")))

    def test_no_hook_change_pass_through_keeps_detail(self):
        result, _ = self.run_hooks(("BudgetMissing", "m", {"scope": "total"}), None)
        self.assertEqual(result, ("refuse", ("BudgetMissing", "m", {"scope": "total"})))


if __name__ == "__main__":
    unittest.main()
