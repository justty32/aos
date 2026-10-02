"""aos-tick 的 kind（使用者 2026-10-02 第二十四批）。真的開 bin/aos-tick 子程序。

使用者勾了「hooks 按 kind 掛」「停格按 kind 擋」「值改成隨便寫」：
- kind 是任意字串、核心不驗（KindValue）；
- hooks 新掛點 before_kind.<kind>、after_kind.<kind>（KindHooks）；
- tasks-blocked 內容是 `{"kinds": [字串…]}` 時只擋那幾類，其他形狀照舊全部擋（KindsBlocked）。
細節（順序、紀錄 skipped、跟 tasks-blocked 模組的互動）是 AI 隊定，見 notes/verdicts/11-tick-as-unit/25-1002-第二十四批.md。
"""
import json
import os
import unittest

from _tick_util import TickCase, check_record, sh, table, task
from _tick_hooks_util import HooksCase


ENVS = 'echo "$AOS_HOOK_POINT|$AOS_HOOK_INDEX|$AOS_HOOK_ID|${AOS_TASK_ID-none}|${AOS_TASK_INDEX-none}|${AOS_TASK_EXIT-none}" >> h.log'
BLOCK = ".aos/tick/tasks-blocked"


class KindValue(TickCase):
    """值改成隨便寫：核心照跑，不驗。"""

    def test_any_value_runs(self):
        self.tasks(sh("a", "touch a.ran", kind="system.x"), sh("b", "touch b.ran", kind="中文 類別"),
                   sh("c", "touch c.ran", kind=7), sh("d", "touch d.ran", kind=""))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(all(self.exists(n + ".ran") for n in "abcd"))
        self.assertEqual(self.rec()["ran"], 4)


class KindHooks(HooksCase):
    """before_kind／after_kind：{kind: [inst…]}，掛在那一類每一個任務前後；順序（AI 隊定，由專到泛）：
    before_kind → 任務 → after_task.<id> → after_kind → after_every_task。"""

    def lines(self):
        return self.read("h.log").splitlines()

    def test_order_and_env(self):
        self.put({"tasks": [sh("a", "echo task-a >> h.log; exit 3", kind="build"),
                            sh("b", "echo task-b >> h.log", kind="build"),
                            sh("c", "echo task-c >> h.log"),                     # 沒 kind：不觸發 *_kind
                            sh("d", "echo task-d >> h.log", kind=5),             # 不是字串：當沒有類別
                            sh("e", "echo task-e >> h.log", kind="other")],
                  "kind": "build",                                               # 頂層 kind 不是預設
                  "hooks": {"before_kind": {"build": [sh("bk", ENVS)], "5": [sh("x5", "touch x5.ran")],
                                            "unused": [sh("xu", "touch xu.ran")]},
                            "after_task": {"a": [sh("ta", ENVS)]},
                            "after_kind": {"build": [sh("ak0", ENVS), sh("ak1", ENVS)], "other": [sh("ao", ENVS)]},
                            "after_every_task": [sh("ev", ENVS)]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.lines(), [
            "before_kind|0|bk|a|0|none",                     # 還沒跑：沒有 AOS_TASK_EXIT
            "task-a",
            "after_task|0|ta|a|0|3",
            "after_kind|0|ak0|a|0|3", "after_kind|1|ak1|a|0|3",
            "after_every_task|0|ev|a|0|3",
            "before_kind|0|bk|b|1|none", "task-b",
            "after_kind|0|ak0|b|1|0", "after_kind|1|ak1|b|1|0", "after_every_task|0|ev|b|1|0",
            "task-c", "after_every_task|0|ev|c|2|0",
            "task-d", "after_every_task|0|ev|d|3|0",
            "task-e", "after_kind|0|ao|e|4|0", "after_every_task|0|ev|e|4|0"])
        self.assertFalse(self.exists("x5.ran") or self.exists("xu.ran"))
        rec = self.rec()
        self.assertEqual(list(rec["hooks"]), ["before_kind", "after_task", "after_kind", "after_every_task"])
        check_record(self, rec)

    def test_kind_expanded_before_match(self):
        self.put({"tasks": [sh("a", "true", kind={"$env": "AOSTEST_KIND"})],
                  "hooks": {"after_kind": {"build": [sh("ak", "touch ak.ran")]}}})
        r = self.tick(env={"AOSTEST_KIND": "build"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("ak.ran"))

    def test_nonzero_recorded_with_task_index(self):
        self.put({"tasks": [sh("a", "true"), sh("b", "true", kind="k")],
                  "hooks": {"before_all": [sh("b0", "true")],
                            "before_kind": {"k": [sh("bk", "exit 2")]},
                            "after_kind": {"k": [sh("ok", "true"), sh("ak", "exit 4")]},
                            "after_all": [sh("aa", "true")]}})
        self.assertEqual(self.tick().returncode, 0)
        rec = self.rec()
        self.assertEqual(rec["hooks"], {"before_all": [],
                                        "before_kind": [{"id": "bk", "index": 0, "task_index": 1, "exit": 2}],
                                        "after_kind": [{"id": "ak", "index": 1, "task_index": 1, "exit": 4}],
                                        "after_all": []})
        check_record(self, rec)

    def test_before_kind_block_hits_next_task_only(self):
        # before_kind 在 tasks-blocked 檢查之後：它寫的不擋自己這一項，擋下一項
        self.put({"tasks": [sh("a", "touch a.ran", kind="k"), sh("b", "touch b.ran")],
                  "hooks": {"before_kind": {"k": [sh("blk", ": > " + BLOCK)]}}})
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("a.ran"))
        self.assertFalse(self.exists("b.ran"))
        self.assertEqual(self.rec()["blocked_before"], "b")

    def test_spawn_failure_label(self):
        self.put({"tasks": [sh("a", "true", kind="k")],
                  "hooks": {"before_kind": {"k": [task("h0", ["/nonexistent/prog"])]},
                            "after_kind": {"k": [task("h1", ["/nonexistent/prog"])]}}})
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("exec_failed: before_kind/k/h0:", r.stderr)
        self.assertIn("exec_failed: after_kind/k/h1:", r.stderr)

    def test_bad_shape(self):
        for hooks in ({"before_kind": [sh("x", "true")]}, {"after_kind": {"k": sh("x", "true")}},
                      {"after_kind": {"k": [{"id": "x"}]}}):
            self.put({"tasks": [sh("a", "touch a.ran", kind="k")], "hooks": hooks})
            r = self.tick()
            self.assertEqual(r.returncode, 1)
            self.assertIn("bad_table:", r.stderr)
            self.assertFalse(self.exists("a.ran"))


class KindsBlocked(TickCase):
    """tasks-blocked 內容是 `{"kinds": [字串…]}`：只擋 kind 在清單內的任務（跳過那一項、後面照跑），
    紀錄 `skipped`；其他形狀照舊全部擋。"""

    def put(self, *tasks, hooks=None, insts=None):
        doc = table(*tasks)
        if hooks is not None:
            doc["hooks"] = hooks
        if insts is not None:
            doc["modules"] = {"tasks-blocked": {"insts": insts}}
        self.write(".aos/tasks.json", json.dumps(doc, ensure_ascii=False))

    def block(self, content):
        os.makedirs(os.path.join(self.d, ".aos", "tick"), exist_ok=True)
        self.write(BLOCK, content)

    def test_only_listed_kinds_skipped(self):
        self.block(json.dumps({"kinds": ["slow"], "note": "給模組看的"}))
        ev = 'echo "$AOS_HOOK_POINT $AOS_TASK_ID" >> h.log'
        self.put(sh("a", "touch a.ran", kind="slow"), sh("b", "touch b.ran"), sh("c", "touch c.ran; exit 2", kind="fast"),
                 sh("d", "touch d.ran", kind="slow"),
                 hooks={"before_kind": {"slow": [sh("bk", ev)]}, "after_task": {"a": [sh("ta", ev)]},
                        "after_kind": {"slow": [sh("ak", ev)]}, "after_every_task": [sh("ev", ev)],
                        "before_all": [sh("b0", ev)], "after_all": [sh("aa", ev)]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual([n for n in "abcd" if self.exists(n + ".ran")], ["b", "c"])
        self.assertEqual(self.read("h.log").splitlines(),            # 被擋的 a、d：相關 hooks 都不跑
                         ["before_all ", "after_every_task b", "after_every_task c", "after_all "])
        rec = self.rec()
        self.assertEqual((rec["ran"], rec["tasks"], rec["skipped"]),
                         (2, [{"id": "c", "index": 2, "exit": 2}], [{"id": "a", "index": 0}, {"id": "d", "index": 3}]))
        self.assertNotIn("blocked_before", rec)
        check_record(self, rec)
        self.assertFalse(self.exists(BLOCK))                         # 整格最後照樣刪
        self.assertEqual(self.tick().returncode, 0)                  # 下一格沒擋
        self.assertNotIn("skipped", self.rec())

    def test_other_shapes_block_all(self):
        self.put(sh("a", "touch a.ran"), sh("b", "touch b.ran", kind="slow"))
        for content in ("", "{}", "[]", "不是 JSON", '{"kinds": "slow"}', '{"kinds": ["slow", 1]}', '{"kinds": null}'):
            self.block(content)
            r = self.tick()
            self.assertEqual((r.returncode, r.stderr), (0, ""), content)
            self.assertFalse(self.exists("a.ran"), content)
            rec = self.rec()
            self.assertEqual((rec["blocked_before"], rec["ran"]), ("a", 0))
            self.assertNotIn("skipped", rec)
            self.assertFalse(self.exists(BLOCK))

    def test_empty_kinds_and_non_string_kind_not_blocked(self):
        self.block('{"kinds": []}')
        self.put(sh("a", "touch a.ran", kind="slow"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("a.ran"))
        self.block('{"kinds": ["5"]}')
        self.put(sh("b", "touch b.ran", kind=5))
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("b.ran"))
        self.assertNotIn("skipped", self.rec())

    def test_reread_before_each_task(self):
        # a 寫 kinds 形狀：b（x 類）跳過；c 改成空檔：d 起全部擋
        self.put(sh("a", "echo '{\"kinds\":[\"x\"]}' > " + BLOCK), sh("b", "touch b.ran", kind="x"),
                 sh("c", ": > " + BLOCK), sh("d", "touch d.ran"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertFalse(self.exists("b.ran") or self.exists("d.ran"))
        rec = self.rec()
        self.assertEqual((rec["ran"], rec["skipped"], rec["blocked_before"]), (2, [{"id": "b", "index": 1}], "d"))
        check_record(self, rec)

    def test_module_runs_for_each_blocked_task(self):
        # 掛了 B-636 模組：每個要被擋的項之前各跑一次，不在清單的項不觸發
        self.block('{"kinds": ["x"]}')
        self.put(sh("a", "touch a.ran", kind="x"), sh("b", "touch b.ran"), sh("c", "touch c.ran", kind="x"),
                 insts=[sh("m", 'echo "$AOS_TASK_ID" >> m.log')])
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.read("m.log").split(), ["a", "c"])
        self.assertEqual(self.rec()["skipped"], [{"id": "a", "index": 0}, {"id": "c", "index": 2}])
        # 模組把清單改掉：放行這一項
        self.block('{"kinds": ["x"]}')
        self.put(sh("a", "touch a2.ran", kind="x"), insts=[sh("m", "echo '{\"kinds\":[]}' > " + BLOCK)])
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("a2.ran"))
        self.assertNotIn("skipped", self.rec())


if __name__ == "__main__":
    unittest.main()
