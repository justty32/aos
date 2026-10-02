"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

本檔：AOS_DIRNAME 三態（DirName、EmptyDirName）。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import unittest

from _tick_util import CAT_REC, TickCase, sh, table, task


class DirName(TickCase):
    """使用者 2026-10-01（待統一更新 spec）：環境變數 `AOS_DIRNAME` 決定狀態資料夾的名字（只換名字、位置不變）。
    沒設＝`.aos`；空字串＝工作資料夾本身（見 EmptyDirName）；含 `/`、是 `.`、`..` 算用法錯回 1。"""

    ENV = {"AOS_DIRNAME": ".aos2"}

    def test_all_under_custom_dir(self):
        self.tasks(sh("wrong", "touch wrong.ran"))                     # .aos/tasks.json 不該被用
        before = sorted(os.listdir(os.path.join(self.d, ".aos")))
        self.write(".aos2/tasks.json", json.dumps(table(
            sh("a", 'echo "$AOS_DIRNAME" > a.txt; ' + CAT_REC + " > a.json"),
            sh("b", "echo > .aos2/tick/tasks-blocked"), sh("c", "touch c.ran"))))
        r = self.tick(env=self.ENV)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("c.ran"))
        self.assertEqual(self.read("a.txt"), ".aos2\n")
        self.assertEqual(json.loads(self.read("a.json"))["seq"], 1)        # 從 $AOS_TICK_CWD/.aos2/tick/ 找得到
        rec = self.rec(dirname=".aos2")
        self.assertEqual((rec["seq"], rec["blocked_before"]), (1, "c"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, ".aos2"))), ["tasks.json", "tick", "tick.lock"])
        self.write(".aos2/tick-blocked", "擋\n")
        r = self.tick(env=self.ENV)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("c.ran"))
        os.unlink(os.path.join(self.d, ".aos2/tick-blocked"))
        self.assertFalse(self.exists(".aos2/tick/tasks-blocked"))     # 整格最後刪掉（在 .aos2/tick/）
        self.write(".aos2/tasks.json", json.dumps(table(sh("c", "touch c.ran"))))
        self.assertEqual(self.tick(env=self.ENV).returncode, 0)
        self.assertTrue(self.exists("c.ran"))
        self.assertEqual(self.rec("last", dirname=".aos2")["seq"], 1)
        self.assertFalse(self.exists("wrong.ran"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, ".aos"))), before)   # .aos/ 沒被碰

    def test_dir_needs_custom_tasks_json(self):
        self.tasks(task("t", ["true"]))                               # 只有 .aos/tasks.json
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_tasks:", r.stderr)
        self.assertFalse(self.exists(".aos2"))
        self.assertEqual(self.tick().returncode, 0)                   # 沒設＝.aos
        self.assertEqual(self.rec()["seq"], 1)

    def test_bad_values_are_usage_errors(self):
        self.tasks(sh("t", "touch ran"))
        for bad in ("a/b", "/tmp", ".", "..", "x/"):
            r = self.tick(env={"AOS_DIRNAME": bad})
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("usage:", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertFalse(self.exists("ran"))
        self.assertEqual(sorted(os.listdir(self.d)), [".aos"])
        self.assertEqual(os.listdir(os.path.join(self.d, ".aos")), ["tasks.json"])


class EmptyDirName(TickCase):
    """使用者 2026-10-01 再改（待統一更新 spec）：`AOS_DIRNAME` 設了但是空字串＝不用子資料夾，
    tasks.json、tick.lock、tick-blocked、tick/tasks-blocked、tick/current/、tick/last/ 都直接在工作資料夾下。
    跟「沒設」（＝.aos）分得開。"""

    ENV = {"AOS_DIRNAME": ""}

    def test_all_directly_under_cwd(self):
        self.tasks(sh("wrong", "touch wrong.ran"))                     # .aos/tasks.json 不該被用
        self.write("tasks.json", json.dumps(table(
            sh("a", 'echo "[$AOS_DIRNAME]" > a.txt; ' + CAT_REC + " > a.json"),
            sh("b", "echo > tick/tasks-blocked"), sh("c", "touch c.ran"))))
        r = self.tick(env=self.ENV)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("c.ran"))
        self.assertEqual(self.read("a.txt"), "[]\n")
        self.assertEqual(json.loads(self.read("a.json"))["seq"], 1)        # 從 $AOS_TICK_CWD/tick/ 找得到
        self.assertEqual(self.rec(dirname="")["seq"], 1)
        self.assertTrue(self.exists("tick.lock"))
        self.assertEqual(os.listdir(os.path.join(self.d, ".aos")), ["tasks.json"])   # .aos/ 沒被碰
        self.write("tick-blocked", "擋\n")
        r = self.tick(env=self.ENV)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("c.ran"))
        os.unlink(os.path.join(self.d, "tick-blocked"))
        self.assertFalse(self.exists("tick/tasks-blocked"))           # 整格最後刪掉
        self.write("tasks.json", json.dumps(table(sh("c", "touch c.ran"))))
        self.assertEqual(self.tick(env=self.ENV).returncode, 0)
        self.assertTrue(self.exists("c.ran"))
        self.assertEqual(self.rec("last", dirname="")["seq"], 1)
        self.assertFalse(self.exists("wrong.ran"))
        self.assertFalse(self.exists(".aos/tick"))

    def test_unset_vs_empty(self):
        self.tasks(sh("t", "touch aos.ran"))                           # 只有 .aos/tasks.json
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 1)                              # 空字串：工作資料夾下沒有 tasks.json
        self.assertIn("no_tasks:", r.stderr)
        self.assertFalse(self.exists("tick.lock"))
        self.assertEqual(self.tick().returncode, 0)                   # 沒設：.aos/tasks.json
        self.assertTrue(self.exists("aos.ran"))
        self.assertTrue(self.exists(".aos/tick/current/record.json"))
        self.assertFalse(self.exists("tick"))


if __name__ == "__main__":
    unittest.main()
