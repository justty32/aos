"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

本檔：停格檔 tasks-blocked（Step6TasksBlocked、TasksBlockedModule）。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import unittest

from _tick_util import TickCase, check_record, sh, table, task


class Step6TasksBlocked(TickCase):
    """使用者 2026-10-01 第十六批：停格檔改名 `<狀態資料夾>/tick/tasks-blocked`，每一項之前看、只看存不存在（內容不管）；
    在＝這一項與後面都不跑、stderr 不印；整格最後 tick 自己刪掉。"""

    BLOCK = ".aos/tick/tasks-blocked"

    def test_blocks_rest_quietly_and_deleted_at_end(self):
        self.tasks(sh("a", "true"), sh("b", "echo 停 > " + self.BLOCK), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["blocked_before"], rec["exit"], rec["ran"], rec["tasks"]), ("c", 0, 2, []))
        check_record(self, rec)
        self.assertFalse(self.exists(self.BLOCK))          # 整格最後刪掉
        self.tasks(sh("a", "true"), sh("b", "true"), sh("c", "touch c.ran"))
        self.assertEqual(self.tick().returncode, 0)        # 下一格照常
        self.assertTrue(self.exists("c.ran"))
        self.assertNotIn("blocked_before", self.rec())

    def test_placed_between_ticks_blocks_first(self):
        # 開格時不刪：格與格之間放的，第一項之前就擋下；內容不管、資料夾也算，最後都刪
        self.tasks(sh("a", "touch a.ran"))
        path = os.path.join(self.d, self.BLOCK)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for make in (lambda: self.write(self.BLOCK, "不是 JSON {"), lambda: os.makedirs(os.path.join(path, "x")),
                     lambda: os.symlink(os.path.join(self.d, "nowhere"), path)):
            make()
            r = self.tick()
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertFalse(self.exists("a.ran"))
            rec = self.rec()
            self.assertEqual((rec["blocked_before"], rec["ran"]), ("a", 0))
            check_record(self, rec)
            self.assertFalse(os.path.lexists(path))
        if os.geteuid() != 0:                              # 沒讀權也算在（tick 不讀）
            self.write(self.BLOCK, "x")
            os.chmod(path, 0)
            r = self.tick()
            self.assertEqual((r.returncode, r.stderr, self.rec()["blocked_before"]), (0, "", "a"))
            self.assertFalse(os.path.lexists(path))

    def test_after_error(self):
        self.tasks(sh("a", "exit 1"), sh("b", "echo > " + self.BLOCK), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["blocked_before"], rec["exit"]), ("c", 0))
        self.assertEqual((rec["ran"], rec["tasks"]), (2, [{"id": "a", "index": 0, "exit": 1}]))
        check_record(self, rec)

    def test_last_task_writes_it(self):
        # 最後一項才寫：沒有東西被擋（不記 blocked_before），最後一樣刪
        self.tasks(sh("a", "true"), sh("b", "echo > " + self.BLOCK))
        self.assertEqual(self.tick().returncode, 0)
        self.assertNotIn("blocked_before", self.rec())
        self.assertFalse(self.exists(self.BLOCK))


class TasksBlockedModule(TickCase):
    """B-636 `modules["tasks-blocked"].insts`（使用者 2026-10-01 第十六批）：某一項之前發現 tasks-blocked 時先跑那一串，
    跑完再看一次：檔被刪了就放行這一項與後面的，還在就照預設擋下；結束碼不記、非 0 沒影響；沒掛＝預設行為。"""

    BLOCK = ".aos/tick/tasks-blocked"

    def put(self, tasks, insts):
        doc = table(*tasks)
        doc["modules"] = {"tasks-blocked": {"insts": insts}}
        self.write(".aos/tasks.json", json.dumps(doc, ensure_ascii=False))

    def test_insts_remove_file_releases(self):
        self.put([sh("a", ": > " + self.BLOCK), sh("b", "touch b.ran"), sh("c", "touch c.ran")],
                 [sh("seen", 'echo "$AOS_TASK_ID $AOS_TASK_INDEX ${AOS_HOOK_POINT-none} $AOS_TICK_CWD" >> on.txt'),
                  sh("rm", "rm " + self.BLOCK + "; exit 7")])
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("b.ran") and self.exists("c.ran"))
        self.assertEqual(self.read("on.txt").split(), ["b", "1", "none", self.d])   # 被擋下那一項的變數
        rec = self.rec()
        self.assertEqual((rec["ran"], rec["tasks"]), (3, []))                      # 非 0（7）不記
        self.assertNotIn("blocked_before", rec)
        check_record(self, rec)

    def test_insts_keep_file_blocks(self):
        self.put([sh("a", ": > " + self.BLOCK), sh("b", "touch b.ran")],
                 [sh("n", "echo n >> on.txt; exit 3")])
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("b.ran"))
        self.assertEqual(self.read("on.txt"), "n\n")                              # 同一項之前只跑一次
        rec = self.rec()
        self.assertEqual((rec["blocked_before"], rec["ran"], rec["tasks"]), ("b", 1, []))
        self.assertFalse(self.exists(self.BLOCK))                                   # 整格最後照樣刪

    def test_runs_again_when_blocked_again(self):
        # 放行之後，後面的任務又寫了：c 之前再跑一次；這次不刪就擋下 c
        self.put([sh("a", ": > " + self.BLOCK), sh("b", ": > " + self.BLOCK), sh("c", "touch c.ran")],
                 [sh("once", 'echo "$AOS_TASK_ID" >> on.txt; [ -e released ] || { touch released; rm ' + self.BLOCK + '; }')])
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.read("on.txt").split(), ["b", "c"])
        self.assertFalse(self.exists("c.ran"))
        self.assertEqual(self.rec()["blocked_before"], "c")

    def test_placed_before_first_and_empty_insts(self):
        self.write(self.BLOCK, "")
        self.put([sh("a", "touch a.ran")], [])                                    # 掛了但一串是空的：檔還在就擋
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("a.ran"))
        self.assertEqual((self.rec()["blocked_before"], self.rec()["ran"]), ("a", 0))

    def test_not_run_without_file_and_spawn_failure(self):
        self.put([sh("a", "true")], [task("x", ["/nonexistent/prog"])])
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))                        # 沒有 tasks-blocked 就不跑
        self.put([sh("a", ": > " + self.BLOCK), sh("b", "touch b.ran")], [task("x", ["/nonexistent/prog"])])
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("exec_failed: tasks-blocked/x:", r.stderr)                    # 開不起來照任務印一行
        self.assertFalse(self.exists("b.ran"))
        self.assertEqual(self.rec()["tasks"], [])

    def test_bad_module(self):
        for mod in ([], {"insts": {}}, {}, {"insts": [{"id": "x"}]}, {"insts": ["no"]}):
            doc = table(sh("a", "touch a.ran"))
            doc["modules"] = {"tasks-blocked": mod}
            self.write(".aos/tasks.json", json.dumps(doc))
            r = self.tick()
            self.assertEqual(r.returncode, 1, mod)
            self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("a.ran"))

    def test_insts_expanded_at_open(self):
        # 第二十批：tasks-blocked 的 insts 跟任務一樣開格就展開（不再是例外），內部壞了＝bad_table；
        # modules 其他鍵照舊整個展開
        doc = table(sh("a", "touch a.ran"))
        for mods in ({"tasks-blocked": {"insts": [{"argv": ["true"], "envs": {"X": {"$env": "AOSTEST_SURELY_NOT_SET"}}}]}},
                     {"tasks-blocked": {"insts": []}, "other": {"$ref": "nope.json"}}):
            doc["modules"] = mods
            self.write(".aos/tasks.json", json.dumps(doc))
            r = self.tick()
            self.assertEqual(r.returncode, 1, mods)
            self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("a.ran"))
        # 舊鍵名 tasks_blocked 只是陌生的模組鍵：不掛、檔在就照預設擋
        doc["modules"] = {"tasks_blocked": {"insts": [{"argv": ["sh", "-c", "rm .aos/tick/tasks-blocked"]}]}}
        self.write(".aos/tasks.json", json.dumps(doc))
        self.write(".aos/tick/tasks-blocked", "")
        self.assertEqual(self.tick().returncode, 0)
        self.assertFalse(self.exists("a.ran"))


if __name__ == "__main__":
    unittest.main()
