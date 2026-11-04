"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

本檔：跑任務、結束碼、紀錄檔（Step5Run、ExitCodes、RecordOnlyFailures、RecordFiles、Step9Whole）。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import unittest

from _tick_util import CAT_REC, TickCase, check_record, sh, task

from aos_tick_record import read_record


class Step5Run(TickCase):

    def test_env_record_signal_user_ignored(self):
        self.tasks(sh("a", "env > out.env"),
                   sh("b", CAT_REC + " > rec.json"),
                   sh("c", "kill -9 $$"),
                   task("d", ["true"], user="root" if os.geteuid() else "nobody"),
                   task("f", ["sh", "-c", "exit 3"]),
                   sh("g", "touch g.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)       # 任務失敗不影響 tick 的碼
        env = dict(l.split("=", 1) for l in self.read("out.env").splitlines() if "=" in l)
        self.assertEqual(env["AOS_TASK_INDEX"], "0")
        self.assertEqual(env["AOS_TASK_ID"], "a")
        self.assertEqual(env["AOS_TICK_CWD"], self.d)
        self.assertNotIn("AOS_TICK_RECORD", env)             # 使用者 2026-10-01 拿掉
        self.assertNotIn("AOS_NODE_DIR", env)                # 改名 AOS_TICK_CWD
        self.assertNotIn("AOS_TICK_LOCK_FD", env)
        seen = json.loads(self.read("rec.json"))                # b 跑的時候：a 跑完、0 沒記
        self.assertEqual((seen["ran"], seen["tasks"]), (1, []))
        self.assertNotIn("user_mismatch", r.stderr)          # user 不看，照 tick 自己的帳號跑
        self.assertEqual(self.rec()["tasks"], [{"id": "c", "index": 2, "signal": 9},
                                               {"id": "f", "index": 4, "exit": 3}])
        self.assertEqual(self.rec()["ran"], 6)
        check_record(self, self.rec())


class ExitCodes(TickCase):
    """aos 結束碼慣例下的 tick 結束碼（使用者 2026-10-01）：任務的碼只記、不影響 tick。"""

    def test_task_codes_only_recorded(self):
        self.tasks(sh("a", "exit 1"), sh("b", "exit 2"), sh("c", "exit 127"),
                   sh("d", "kill -2 $$"), sh("e", "touch e.ran"))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("e.ran"))             # 回 2、回錯都照常跑下一項
        rec = self.rec()
        self.assertEqual(rec["tasks"], [{"id": "a", "index": 0, "exit": 1}, {"id": "b", "index": 1, "exit": 2},
                                        {"id": "c", "index": 2, "exit": 127},
                                        {"id": "d", "index": 3, "signal": 2}])     # 照實記原碼；e 是 0 不記
        self.assertEqual(rec["ran"], 5)
        self.assertEqual(rec["exit"], 0)
        check_record(self, rec)

    def test_bad_current_record_is_error(self):
        self.tasks(sh("t", "touch ran"))
        self.write(".aos/tick/current/record.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)                  # 沒接住的例外：traceback 進 stderr
        self.assertFalse(self.exists("ran"))

    def test_bad_tasks_json_is_error(self):
        self.write(".aos/tasks.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_table:", r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1)   # 一行，不是 traceback


class RecordOnlyFailures(TickCase):
    """第八批（使用者 2026-10-01）：「tasks如果結果是0，那就不用紀錄了。」——`tasks` 只記不是 0 的，
    每筆 {"id","index","exit"}（訊號殺的是 "signal"）；`ran`＝本格到目前跑了幾項（含失敗的，被停格擋掉的不算）。"""

    def test_zero_not_recorded_nonzero_with_index_and_ran(self):
        self.tasks(sh("a", "true"), {"argv": ["sh", "-c", "exit 7"]},
                   sh("c", CAT_REC + " > c.json"), sh("d", "exit 1"), sh("e", CAT_REC + " > e.json"))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        c, e = json.loads(self.read("c.json")), json.loads(self.read("e.json"))
        self.assertEqual((c["ran"], c["tasks"]), (2, [{"id": "1", "index": 1, "exit": 7}]))   # 每跑完一項就更新
        self.assertEqual((e["ran"], e["tasks"]), (4, [{"id": "1", "index": 1, "exit": 7},
                                                      {"id": "d", "index": 3, "exit": 1}]))
        rec = self.rec()
        self.assertEqual((rec["ran"], rec["tasks"], rec["ended"]), (5, e["tasks"], True))
        check_record(self, rec)

    def test_all_zero_empty_and_open_ran_0(self):
        self.tasks(sh("a", CAT_REC + " > a.json"), sh("b", "true"))
        self.assertEqual(self.tick().returncode, 0)
        a = json.loads(self.read("a.json"))
        self.assertEqual((a["ran"], a["tasks"], a["ended"]), (0, [], False))      # 開格時 ran 是 0
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (2, []))

    def test_stop_ran_excludes_skipped_and_last(self):
        # b 建 tasks-blocked（b 自己失敗）：c 沒跑、不算進 ran；下一格的 last/ 原樣帶著
        self.tasks(sh("a", "exit 3"), sh("b", "echo > .aos/tick/tasks-blocked; exit 9"), sh("c", "exit 5"))
        self.assertEqual(self.tick().returncode, 0)
        first = self.rec()
        self.assertEqual((first["ran"], first["blocked_before"]), (2, "c"))
        self.assertEqual(first["tasks"], [{"id": "a", "index": 0, "exit": 3}, {"id": "b", "index": 1, "exit": 9}])
        check_record(self, first)
        self.tasks(sh("x", "true"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec("last"), first)
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (1, []))


class RecordFiles(TickCase):
    """第九批（使用者 2026-10-01）：「把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」。
    一格紀錄是資料夾 tick/current/：record.json（開格、收尾各寫一次）用 $ref 指向 ran.json、task-exits.json、
    hook-exits.json（有 hooks 才有）；換紀錄＝刪 last/、current/ 整個改名成 last/、建新的 current/。"""

    RAW = 'cat .aos/tick/current/record.json > raw.json; cat .aos/tick/current/ran.json > ran.txt'

    def raw(self, rel):
        return json.loads(self.read(rel))

    def test_layout_and_refs(self):
        self.tasks(sh("a", "exit 4"), sh("b", self.RAW), sh("c", "kill -9 $$"))
        self.assertEqual(self.tick().returncode, 0)
        during = self.raw("raw.json")                     # b 跑的時候：record.json 還是開格那份
        self.assertEqual({k: during[k] for k in ("ran", "tasks", "ended")},
                         {"ran": {"$ref": "ran.json"}, "tasks": {"$ref": "task-exits.json"}, "ended": False})
        self.assertEqual(self.read("ran.txt"), "1\n")
        cur = os.path.join(self.d, ".aos/tick/current")
        self.assertEqual(sorted(os.listdir(cur)), ["ran.json", "record.json", "task-exits.json"])   # 沒 hooks：沒有 hook-exits.json
        rec = self.raw(".aos/tick/current/record.json")
        self.assertEqual(set(rec), {"version", "seq", "started_at_ms", "ran", "tasks", "ended", "exit"})
        self.assertEqual((rec["ran"], rec["tasks"], rec["ended"], rec["exit"]),
                         ({"$ref": "ran.json"}, {"$ref": "task-exits.json"}, True, 0))
        check_record(self, rec, raw=True)
        self.assertEqual(self.raw(".aos/tick/current/ran.json"), 3)
        self.assertEqual(self.raw(".aos/tick/current/task-exits.json"),
                         [{"id": "a", "index": 0, "exit": 4}, {"id": "c", "index": 2, "signal": 9}])
        full = self.rec()
        self.assertEqual((full["ran"], full["tasks"]), (3, self.raw(".aos/tick/current/task-exits.json")))
        self.assertNotIn("hooks", full)
        check_record(self, full)
        before = self.snap(".aos/tick/current")
        self.tasks(sh("x", "true"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.snap(".aos/tick/last"), before)          # 整個資料夾改名，檔原樣
        self.assertEqual(self.rec("last"), full)                       # $ref 是相對路徑，改名後仍指得對
        self.assertEqual(self.raw(".aos/tick/current/task-exits.json"), [])
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, ".aos/tick"))), ["current", "last"])

    def test_no_current_drops_last(self):
        # 沒有 current/ 卻有 last/：上一格沒留下紀錄＝不知道，刪 last/；seq 從 last 接
        self.tasks(task("t", ["true"]))
        self.tick(), self.tick()
        import shutil
        shutil.rmtree(os.path.join(self.d, ".aos/tick/current"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec()["seq"], 2)
        self.assertFalse(self.exists(".aos/tick/last"))

    def test_read_record_missing(self):
        self.assertIsNone(read_record(os.path.join(self.d, "nope")))


class Step9Whole(TickCase):

    def test_b626_only_true_no_daemon(self):
        self.tasks(task("t", ["true"]))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertNotIn("standard:", r.stderr)
        check_record(self, self.rec())


if __name__ == "__main__":
    unittest.main()
