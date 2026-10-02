"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

本檔：目標資料夾、互斥鎖、擋板、seq（Step1Target、Step1Lock、Step2Blocked、Step3Seq）。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import subprocess
import time
import unittest

from _util import PY
from _tick_util import CLEAN_ENV, TICK, TickCase, check_record, sh, table, task


class Step1Target(TickCase):
    """使用者 2026-10-01（待統一更新 spec）：目標（位置參數）省略用 ./、相對轉絕對；資料夾要有 .aos/tasks.json
    （不看 inst.json）；不存在回 1。同日撤回「是檔就拿它當表」：目標只能是資料夾，給檔＝用法錯回 1。"""

    def test_cwd_default_and_not_git(self):
        self.tasks(sh("t", 'echo "$AOS_TICK_CWD" > cwd.txt'))
        r = subprocess.run([PY, TICK], cwd=self.d, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("cwd.txt"), self.d + "\n")
        self.assertEqual(self.rec()["seq"], 1)
        self.assertFalse(self.exists(".git"))

    def test_relative_path_made_absolute(self):
        self.tasks(sh("t", 'echo "$AOS_TICK_CWD" > cwd.txt'))
        parent, name = os.path.split(self.d)
        for i, target in enumerate((name, os.path.join(".", name, "")), 1):
            r = subprocess.run([PY, TICK, target], cwd=parent, env=CLEAN_ENV,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.read("cwd.txt"), self.d + "\n")
            self.assertEqual(self.rec()["seq"], i)

    def test_dir_without_tasks_json_is_error(self):
        r = self.tick()                                   # 有 .aos/、沒有 tasks.json
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_tasks:", r.stderr)
        self.assertFalse(self.exists(".aos/tick"))
        os.rmdir(os.path.join(self.d, ".aos"))            # 連 .aos/ 都沒有
        self.assertEqual(self.tick().returncode, 1)
        self.assertEqual(os.listdir(self.d), [])

    def test_inst_json_only_is_error(self):
        # tick 跟 inst.json 分開：只有 .aos/inst.json（和頂層 inst.json）不算工作資料夾
        self.inst({"argv": ["sh", "-c", "touch ran"]})
        self.inst({"argv": ["sh", "-c", "touch ran"]}, rel="inst.json")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_tasks:", r.stderr)
        self.assertFalse(self.exists("ran"))
        self.assertFalse(self.exists(".aos/tick"))

    def test_tasks_json_present_inst_json_not_needed(self):
        self.tasks(task("t", ["true"]))
        self.assertFalse(self.exists(".aos/inst.json"))
        self.assertEqual(self.tick().returncode, 0)

    def test_file_target_is_usage_error(self):
        # 使用者 2026-10-01 撤回「目標是檔就拿它當表」：給檔（不管是不是 .aos/tasks.json 本身）＝stderr usage、回 1，什麼都不建
        self.tasks(sh("t", "touch ran"))
        other = self.write("sub/my.json", json.dumps(table(sh("a", "touch a.ran"))))
        for target in (other, os.path.join(self.d, ".aos", "tasks.json")):
            r = self.tick(target)
            self.assertEqual(r.returncode, 1, target)
            self.assertIn("usage:", r.stderr)
            self.assertIn("資料夾", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertFalse(self.exists("ran"))
        self.assertFalse(self.exists("sub/a.ran"))
        self.assertEqual(sorted(os.listdir(self.d)), [".aos", "sub"])
        self.assertEqual(os.listdir(os.path.join(self.d, ".aos")), ["tasks.json"])
        self.assertEqual(os.listdir(os.path.join(self.d, "sub")), ["my.json"])

    def test_base_is_tick_dir_not_launch_dir(self):
        # 表裡的相對路徑與指示詞以工作資料夾為中心，不是以啟動時的目錄
        self.write("n/.aos/tasks.json", json.dumps(table({"$ref": "item.json"})))
        self.write("n/item.json", json.dumps(sh("r", "touch from-ref")))
        self.write("item.json", json.dumps(sh("wrong", "touch wrong.ran")))
        r = subprocess.run([PY, TICK, "n"], cwd=self.d, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.exists("n/from-ref"))
        self.assertFalse(self.exists("wrong.ran"))
        self.assertEqual((self.rec(cwd="n")["ran"], self.rec(cwd="n")["tasks"]), (1, []))

    def test_metainfo_optional(self):
        # 裁定 2026-10-01：頂層 _metainfo 不是必填；每項 _metainfo 照 inst 規則可省（沒寫＝posix 第 1 版）
        self.write(".aos/tasks.json", json.dumps({"tasks": [
            {"id": "a", "argv": ["sh", "-c", "echo a >> ran"]},
            sh("b", "echo b >> ran")]}))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("ran"), "a\nb\n")
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (2, []))

    def test_bad_item_metainfo_only_when_run(self):
        # 裁定 2026-10-01：每項 _metainfo 跑到那一項才照 inst 規則驗；驗不過＝既有「跑到某項展開失敗」行為
        # （自然丟錯回 1）。前一項已跑、前面先停格就輪不到它
        bad = {"_metainfo": {"_type": "posix", "_version": 2}, "id": "x", "argv": ["touch", "x.ran"]}
        self.tasks(sh("a", "touch a.ran"), bad)
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)
        self.assertTrue(self.exists("a.ran"))
        self.assertFalse(self.exists("x.ran"))
        self.tasks(sh("a", "echo > .aos/tick/tasks-blocked"), bad)
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (1, []))

    def test_bad_item_metainfo_value_is_error(self):
        # 每項沒寫 `_metainfo` 照跑（aos_inst 當 posix 第 1 版）；寫了但值不對，極簡檢查不看，
        # 跑到這一項展開成 inst 時 aos_inst 自然丟錯（traceback），回 1
        self.tasks({"_metainfo": {"_type": "nope", "_version": 1}, "id": "x", "argv": ["true"]})
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)

    def test_missing_path_and_usage_errors(self):
        r = self.tick(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_target:", r.stderr)
        r = subprocess.run([PY, TICK, "nope"], cwd=self.d, env=CLEAN_ENV,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.exists("nope"))
        self.assertEqual(self.tick("--bogus").returncode, 1)      # aos 結束碼慣例：argv 用法錯算 1
        # 使用者 2026-10-01：目標改位置參數，`--target` 旗標拿掉不留——給了算用法錯；目標多於一個也是
        self.assertEqual(self.tick(self.d).returncode, 1)
        self.assertEqual(self.tick(self.d, self.d).returncode, 1)


class Step1Lock(TickCase):
    """使用者 2026-10-01 加回最簡互斥：外層定期跑，上一格沒跑完下一格就來是正常使用。
    拿不到 `.aos/tick.lock` 就 stderr `busy:`、回 0（使用者 2026-10-01 再改：預料之中），不寫紀錄、不加 seq。"""

    def wait_for(self, rel):
        for _ in range(500):
            if self.exists(rel):
                return
            time.sleep(0.02)
        self.fail("等不到 %s" % rel)

    def test_second_tick_while_first_running(self):
        self.tasks(task("t", ["true"]))
        self.assertEqual(self.tick().returncode, 0)                  # seq 1
        self.tasks(sh("hold", "touch started; while [ ! -e go ]; do sleep 0.05; done"), sh("z", "touch z.ran"))
        first = subprocess.Popen([PY, TICK, self.d], env=CLEAN_ENV,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.wait_for("started")
            cur, last = self.snap(".aos/tick/current"), self.snap(".aos/tick/last")
            self.write(".aos/tick-blocked", "壞了\n")                 # 鎖先：上一格沒跑完時回 busy 不是 blocked
            r = self.tick()
            self.assertEqual(r.returncode, 0)
            self.assertIn("busy:", r.stderr)
            self.assertNotIn("blocked:", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
            self.assertEqual(self.snap(".aos/tick/current"), cur)   # 紀錄與 seq 都不動
            self.assertEqual(self.snap(".aos/tick/last"), last)
            self.assertEqual((self.rec()["seq"], self.rec("last")["seq"]), (2, 1))
            os.unlink(os.path.join(self.d, ".aos/tick-blocked"))
        finally:
            self.write("go", "")
            out, err = first.communicate(timeout=30)
        self.assertEqual(first.returncode, 0, err)
        self.assertTrue(self.exists("z.ran"))
        self.assertEqual(self.tick().returncode, 0)                  # 放掉之後下一格照常
        self.assertEqual(self.rec()["seq"], 3)

    def test_lock_fd_not_passed_to_tasks(self):
        lock = os.path.join(self.d, ".aos", "tick.lock")
        probe = ("import os\n"
                 "fds = [os.readlink('/proc/self/fd/' + n) for n in os.listdir('/proc/self/fd')\n"
                 "       if os.path.exists('/proc/self/fd/' + n)]\n"
                 "open('held', 'w').write(str(%r in fds))\n" % lock)
        self.tasks(sh("a", "env > out.env"), task("b", [PY, "-c", probe]))
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("held"), "False")
        self.assertNotIn("AOS_TICK_LOCK_FD", self.read("out.env"))


class Step2Blocked(TickCase):

    def test_blocked(self):
        self.tasks(sh("t", "echo ran >> ran.txt"))
        self.assertEqual(self.tick().returncode, 0)
        cur, last_exists = self.snap(".aos/tick/current"), self.exists(".aos/tick/last")
        self.write(".aos/tick-blocked", "壞了\n")
        r = self.tick()
        self.assertEqual(r.returncode, 0)                 # 正常機制結束：回 0、stderr 不印（第十六批）
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.read("ran.txt"), "ran\n")
        self.assertEqual(self.snap(".aos/tick/current"), cur)
        self.assertEqual(self.exists(".aos/tick/last"), last_exists)
        os.unlink(os.path.join(self.d, ".aos/tick-blocked"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec()["seq"], 2)

    def blocked_quietly(self):
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("ran.txt"))
        self.assertFalse(self.exists(".aos/tick"))

    def test_blocked_only_existence(self):
        # 只看存不存在：空檔、資料夾、沒讀權、壞 symlink 都一樣靜靜回 0（第十六批）
        self.tasks(sh("t", "echo ran >> ran.txt"))
        path = os.path.join(self.d, ".aos/tick-blocked")
        self.write(".aos/tick-blocked", "")
        self.blocked_quietly()
        os.unlink(path)
        os.mkdir(path)
        self.blocked_quietly()
        os.rmdir(path)
        os.symlink(os.path.join(self.d, "nowhere"), path)
        self.blocked_quietly()
        os.unlink(path)
        if os.geteuid() != 0:                             # root 讀得到 000 的檔，測不出來
            self.write(".aos/tick-blocked", "x")
            os.chmod(path, 0)
            self.blocked_quietly()
            os.chmod(path, 0o644)


class Step3Seq(TickCase):

    def test_ten_ticks_and_shell(self):
        self.tasks(task("t", ["true"]))
        for i in range(1, 11):
            if i == 5:
                r = subprocess.run(["sh", "-c", 'cd "$1" && "$2" "$3"', "x", self.d, PY, TICK],
                                   env=CLEAN_ENV, capture_output=True, text=True)
            else:
                r = self.tick()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.rec()["seq"], i)
            if i > 1:
                self.assertEqual(self.rec("last")["seq"], i - 1)
            check_record(self, self.rec())

    def test_first_run_no_last(self):
        self.tasks()
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec(), dict(self.rec(), seq=1, tasks=[], ended=True, exit=0))
        self.assertFalse(self.exists(".aos/tick/last"))


if __name__ == "__main__":
    unittest.main()
