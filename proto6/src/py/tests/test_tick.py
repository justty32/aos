"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import shlex
import subprocess
import time
import unittest

from _util import Base, LIB, PY
from aos_tick_record import read_record

HERE = os.path.dirname(os.path.abspath(__file__))
TICK = os.path.join(os.path.dirname(HERE), "bin", "aos-tick")

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}


def table(*tasks):
    return {"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)}


POSIX = {"_type": "posix", "_version": 1}


def task(tid, argv, **extra):
    """一項任務，`_metainfo`、`id`、`argv` 都填好（使用者 2026-10-01：`kind` 不必填；裁定 2026-10-01：`_metainfo` 可省）。"""
    return dict({"_metainfo": POSIX, "id": tid, "argv": argv}, **extra)


def sh(tid, script, **extra):
    return task(tid, ["sh", "-c", script], **extra)


# 使用者 2026-10-01：沒有 AOS_TICK_RECORD，任務從 $AOS_TICK_CWD/<dirname>/tick/current/ 找紀錄；
# dirname 照 AOS_DIRNAME 三態（沒設＝.aos、空字串＝直接在工作資料夾下、其他＝那個名字）。
# 第九批（2026-10-01）拆檔：record.json 用 $ref 指向 ran.json 等，任務用 aos_tick_record.read_record() 印展開後的完整紀錄
CAT_REC = ('d=${AOS_DIRNAME-.aos}; %s -c "import sys, json; sys.path.insert(0, sys.argv[1]); '
           'import aos_tick_record as r; print(json.dumps(r.read_record(sys.argv[2])))" %s '
           '"$AOS_TICK_CWD/${d:+$d/}tick/current"' % (shlex.quote(PY), shlex.quote(LIB)))


class TickCase(Base):

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.d, ".aos"))

    def tasks(self, *items):
        self.write(".aos/tasks.json", json.dumps(table(*items), ensure_ascii=False))

    def tick(self, *args, env=None):
        e = dict(CLEAN_ENV, **(env or {}))
        args = args or (self.d,)
        return subprocess.run([PY, TICK] + list(args), capture_output=True, text=True, env=e, timeout=30)

    def rec(self, name="current", cwd="", dirname=".aos"):
        """展開後的完整紀錄（第九批：`<cwd>/<dirname>/tick/<name>/record.json` 加上它 $ref 的檔）。"""
        return read_record(os.path.join(self.d, cwd, dirname, "tick", name))

    def snap(self, rel):
        """一格紀錄資料夾裡每個檔的原文（{檔名: 內容}）；資料夾不在回 None。"""
        p = os.path.join(self.d, rel)
        if not os.path.isdir(p):
            return None
        return {n: self.read(os.path.join(rel, n)) for n in sorted(os.listdir(p))}


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


class Step4Table(TickCase):

    def test_unknown_keys_and_whole_ref_run(self):
        self.write("task.json", json.dumps(sh("from-ref", "echo $AOS_TASK_ID > id.txt")))
        self.tasks(task("a", ["true"], group="g", needs=["x"], kind="system.x", methods="亂寫"),
                   {"$ref": "task.json"})
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.read("id.txt"), "from-ref\n")


class Step4Check(TickCase):
    """使用者 2026-10-01（待統一更新 spec）：「該填的沒填，然後不符合{"tasks":[]}這樣的格式，其他就不檢查。」
    「最外層不用檢查_metainfo，每一項也只需要檢查argv」。不過就 stderr 一行 `bad_table:`、回 1。"""

    def bad(self, doc):
        self.write(".aos/tasks.json", json.dumps(doc))
        r = self.tick()
        self.assertEqual(r.returncode, 1, doc)
        self.assertIn("bad_table:", r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertFalse(self.exists("ran"))
        self.assertFalse(self.exists(".aos/tick"))                         # 表壞不算開過一格

    def test_missing_or_wrong_shape(self):
        ok = sh("a", "touch ran")
        self.bad({"_metainfo": table()["_metainfo"]})                      # 缺 tasks
        self.bad(dict(table(), tasks={"a": ok}))                           # tasks 不是陣列
        self.bad([ok])                                                     # 頂層不是物件
        self.bad(table(ok, "x"))                                           # 項不是物件
        self.bad(table(ok, {"_metainfo": POSIX, "id": "b"}))               # 缺 argv

    def test_no_argv_anywhere(self):
        # 使用者 2026-10-01 頂層預設：合併後要有 argv（項自己有，或頂層有）；都沒有＝bad_table、不開格
        self.bad({"envs": {"A": "1"}, "tasks": [sh("a", "touch ran"), {"id": "b"}]})
        self.bad({"tasks": {"$ref": "nope.json"}})                         # 讀表那層解不開
        self.bad({"envs": {"$ref": "nope.json"}, "tasks": [sh("a", "touch ran")]})
        self.bad({"modules": {"$ref": "nope.json"}, "tasks": [sh("a", "touch ran")]})

    def test_modules_interior_broken(self):
        # 裁定 2026-10-01：modules 讀表時整個展開，內部展開失敗也是 bad_table、回 1、不開格
        self.bad({"modules": {"m": {"deep": [{"$ref": "nope.json"}]}}, "tasks": [sh("a", "touch ran")]})
        self.bad({"modules": {"m": {"$env": "AOSTEST_SURELY_NOT_SET"}}, "tasks": [sh("a", "touch ran")]})
        self.bad({"modules": {"m": {"$ref": "#/nope"}}, "tasks": [sh("a", "touch ran")]})

    def test_ref_item_checked_after_expand(self):
        self.write("item.json", json.dumps({"id": "b"}))                   # 展開後缺 argv
        self.bad(table(sh("a", "touch ran"), {"$ref": "item.json"}))
        self.bad(table(sh("a", "touch ran"), {"$ref": "nope.json"}))       # 展開不了

    def test_bad_table_keeps_record_and_seq(self):
        # 使用者 2026-10-01：讀表在換紀錄之前，表壞回 1、current／last 與 seq 都不動
        self.tasks(task("t", ["true"]))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.tick().returncode, 0)
        cur, last = self.snap(".aos/tick/current"), self.snap(".aos/tick/last")
        self.write(".aos/tasks.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_table:", r.stderr)
        self.assertEqual(self.snap(".aos/tick/current"), cur)
        self.assertEqual(self.snap(".aos/tick/last"), last)
        self.tasks(task("t", ["true"]))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual((self.rec()["seq"], self.rec("last")["seq"]), (3, 2))

    def test_not_checked(self):
        # 外層 _metainfo、每項 _metainfo、kind 不填或亂寫、id 重複、陌生鍵都不查，照跑
        self.write(".aos/tasks.json", json.dumps({"tasks": [
            {"id": "a", "argv": ["sh", "-c", "echo a >> ran"]},
            sh("a", "echo a2 >> ran", kind=123),
            sh("b", "echo b >> ran", kind="亂寫", methods=[{"x": 1}, {"x": 1}], zzz=1)]}))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("ran"), "a\na2\nb\n")
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (3, []))

    def test_no_id(self):
        # 使用者 2026-10-01：沒寫 id 就用它在 tasks 陣列的位置（從 0 起）轉字串；撞了不管
        self.tasks(sh("1", "true"),
                   {"argv": ["sh", "-c", 'echo "$AOS_TASK_ID" > id.txt; exit 4']},
                   {"argv": ["sh", "-c", "echo > .aos/tick/tasks-blocked"]}, sh("d", "touch d.ran"))
        r = self.tick(env={"AOS_TASK_ID": "外層的"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("id.txt"), "1\n")
        self.assertFalse(self.exists("d.ran"))
        rec = self.rec()
        self.assertEqual(rec["tasks"], [{"id": "1", "index": 1, "exit": 4}])   # 0 不記（第八批）
        self.assertEqual(rec["ran"], 3)
        self.assertEqual(rec["blocked_before"], "d")


class Step4Defaults(TickCase):
    """使用者 2026-10-01（待統一更新 spec）：tasks.json 頂層可放 inst 的七個欄位當每一項的預設；淺層合併、項蓋過；
    頂層 cwd 不改 tick 自己的 cwd、相對以工作資料夾為起點；讀表時只解到 tasks 這層，每項內部跑到時才解；
    合併後的 `$ref:""`／`#…` 指合併後的這一項。頂層 `_metainfo`、`id`、`kind`、`modules` 不當預設。"""

    def put(self, doc):
        self.write(".aos/tasks.json", json.dumps(doc, ensure_ascii=False))

    def test_defaults_applied_and_tick_cwd_unchanged(self):
        # brief 的新例子（cwd、stdout 加了 mkdir 讓測試自己建資料夾）；從上一層用相對目標啟動
        self.write("tasks.d/clean.json", json.dumps(
            {"id": "clean", "argv": ["sh", "-c", 'echo "clean $LANG $(pwd)"']}))
        self.put({
            "cwd": {"$opt": "mkdir", "$val": "work"},
            "envs": {"LANG": "C.UTF-8"},
            "stdout": {"$opt": ["append", "mkdir"], "$val": "logs/tasks.log"},
            "tasks": [
                {"id": "build", "argv": ["sh", "-c", 'echo "build $LANG $(pwd) $AOS_TICK_CWD"']},
                {"id": "report", "argv": ["sh", "-c", 'echo "report $(pwd)"'],
                 "cwd": {"$opt": "mkdir", "$val": "reports"}},
                {"$ref": "tasks.d/clean.json"}]})
        parent, name = os.path.split(self.d)
        r = subprocess.run([PY, TICK, name], cwd=parent, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        work, reports = os.path.join(self.d, "work"), os.path.join(self.d, "reports")
        self.assertEqual(self.read("work/logs/tasks.log"),
                         "build C.UTF-8 %s %s\nclean C.UTF-8 %s\n" % (work, self.d, work))
        self.assertEqual(self.read("reports/logs/tasks.log"), "report %s\n" % reports)
        # tick 自己的 cwd 不動：鎖、紀錄仍在工作資料夾的 .aos/，work/ 底下沒有
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (3, []))
        self.assertTrue(self.exists(".aos/tick.lock"))
        self.assertFalse(self.exists("work/.aos"))
        check_record(self, self.rec())

    def test_item_keys_override_and_envs_replaced_whole(self):
        self.put({"envs": {"A": "1", "B": "2"}, "stdout": "top.out", "tasks": [
            sh("x", 'echo "${A-unset} ${B-unset}"'),
            sh("y", 'echo "${A-unset} ${B-unset}"', envs={"B": "3"}, stdout="y.out")]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("top.out"), "1 2\n")
        self.assertEqual(self.read("y.out"), "unset 3\n")         # envs 整包換掉，不逐變數合併

    def test_tasks_and_defaults_from_ref(self):
        # 讀表那層：`tasks` 本身可以是 $ref（相對工作資料夾）；頂層預設的 `#…` 指整份 tasks.json
        self.write("tasks.d/list.json", json.dumps([{"id": "a"}, {"id": "b"}]))
        self.put({"shared": {"argv": ["sh", "-c", 'echo "$AOS_TASK_ID $V" >> out']},
                  "argv": {"$ref": "#/shared/argv"}, "envs": {"$ref": "#/shared2"},
                  "shared2": {"V": "v"},
                  "tasks": {"$ref": "tasks.d/list.json"}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("out"), "a v\nb v\n")

    def test_top_argv_default_items_only_id(self):
        self.put({"argv": ["sh", "-c", 'echo "$AOS_TASK_ID" >> ids'], "tasks": [{"id": "a"}, {}, {"id": "c"}]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("ids"), "a\n1\nc\n")

    def test_merged_ref_points_to_merged_item(self):
        # 合併後 `#/id` 指合併後的這一項：同一個頂層預設，每項解出自己的 id
        self.put({"envs": {"WHO": {"$ref": "#/id"}}, "tasks": [
            sh("a", 'echo "$WHO" >> who'), sh("b", 'echo "$WHO" >> who')]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("who"), "a\nb\n")

    def test_item_interior_resolved_only_when_run(self):
        # 第二項內部有壞 $env／$ref：讀表時不解，第一項建了停格檔、第二項沒跑到，整格回 0
        broken = {"id": "x", "argv": ["true"], "envs": {"X": {"$env": "AOSTEST_SURELY_NOT_SET"}},
                  "stdout": {"$ref": "nope.json"}}
        self.put({"stderr": {"$ref": "nope.json"}, "tasks": [sh("a", "echo > .aos/tick/tasks-blocked")]})
        self.assertEqual(self.tick().returncode, 1)              # 對照：頂層預設的值本身讀表時解一層
        self.put({"tasks": [sh("a", "echo > .aos/tick/tasks-blocked"), broken]})
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.rec()["ran"], self.rec()["tasks"]), (1, []))
        self.put({"tasks": [broken]})                             # 對照：跑到時才解，解不開自然丟錯回 1
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)

    def test_top_metainfo_id_kind_modules_not_defaults(self):
        self.put({"_metainfo": {"_type": "nope", "_version": 9}, "id": "TOP", "kind": "x",
                  "modules": {"m": {"deep": {"x": 1}}},
                  "tasks": [{"argv": [PY, "-c", "import os; open('id', 'w').write(os.environ['AOS_TASK_ID'])"]}]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))       # 頂層 _metainfo 若被合併，aos_inst 會丟錯
        self.assertEqual(self.read("id"), "0")

    def test_modules_not_merged(self):
        # 使用者 2026-10-01：「tasks.json頂層也應該有modules。」核心照收不理、不當預設合併；
        # 裁定 2026-10-01：讀表時整個展開（跟 daemon 設定檔一致），`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點
        import aos_tick_table
        self.write("mod.json", json.dumps({"deep": [{"$ref": "#/k"}], "k": 7}))
        tbl = aos_tick_table.check_table(
            {"modules": {"$ref": "#/m"},
             "m": {"x": {"$ref": "mod.json"}, "y": {"$ref": "#/v"}, "o": {"$opt": "mkdir", "$val": "d"}},
             "v": "top", "argv": ["true"], "tasks": [{"id": "a"}]}, self.d)
        self.assertEqual(tbl.modules, {"x": {"deep": [7], "k": 7}, "y": "top",
                                       "o": {"$opt": "mkdir", "$val": "d"}})
        self.assertEqual(aos_tick_table.merge(tbl.defaults, tbl.items[0]), {"argv": ["true"], "id": "a"})

    def test_modules_interior_expanded_when_run(self):
        # modules 內部的 $ref 讀表時就展開；照跑、不影響任務
        self.write("mod.json", json.dumps({"on": True}))
        self.put({"modules": {"m": {"cfg": {"$ref": "mod.json"}}}, "tasks": [sh("a", "touch ran")]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("ran"))


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
    """B-636 `modules.tasks_blocked.insts`（使用者 2026-10-01 第十六批）：某一項之前發現 tasks-blocked 時先跑那一串，
    跑完再看一次：檔被刪了就放行這一項與後面的，還在就照預設擋下；結束碼不記、非 0 沒影響；沒掛＝預設行為。"""

    BLOCK = ".aos/tick/tasks-blocked"

    def put(self, tasks, insts):
        doc = table(*tasks)
        doc["modules"] = {"tasks_blocked": {"insts": insts}}
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
        self.assertIn("exec_failed: tasks_blocked/x:", r.stderr)                    # 開不起來照任務印一行
        self.assertFalse(self.exists("b.ran"))
        self.assertEqual(self.rec()["tasks"], [])

    def test_bad_module(self):
        for mod in ([], {"insts": {}}, {}, {"insts": [{"id": "x"}]}, {"insts": ["no"]}):
            doc = table(sh("a", "touch a.ran"))
            doc["modules"] = {"tasks_blocked": mod}
            self.write(".aos/tasks.json", json.dumps(doc))
            r = self.tick()
            self.assertEqual(r.returncode, 1, mod)
            self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("a.ran"))

    def test_other_modules_still_expanded(self):
        # tasks_blocked 每項跑到時才展開；modules 其他鍵照舊整個展開（壞了＝bad_table）
        doc = table(sh("a", "true"))
        doc["modules"] = {"tasks_blocked": {"insts": [{"argv": ["true"], "envs": {"X": {"$env": "AOSTEST_SURELY_NOT_SET"}}}]},
                          "other": {"$ref": "nope.json"}}
        self.write(".aos/tasks.json", json.dumps(doc))
        self.assertEqual(self.tick().returncode, 1)
        del doc["modules"]["other"]
        self.write(".aos/tasks.json", json.dumps(doc))
        self.assertEqual(self.tick().returncode, 0)                                 # 內部的 $env 沒跑到就不解


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


def check_record(case, rec, raw=False):
    """P-213 的跨欄位規則＋（有 jsonschema 時）tick-record schema。raw＝傳進來的是 record.json 本體，只驗 schema 的 RecordFile。"""
    if raw:
        return _check_schema(rec, raw=True)
    if rec.get("ended"):
        case.assertEqual(rec["exit"], 0)                  # 寫得到收尾就是 0，任務成敗不影響
        if "blocked_before" in rec:                    # 第十六批：被擋下的那一項（位置 ran）沒跑，不會在 tasks 裡
            case.assertNotIn(rec["blocked_before"], [t["id"] for t in rec["tasks"] if t["index"] == rec["ran"]])
    else:
        case.assertNotIn("exit", rec)
    idx = [t["index"] for t in rec["tasks"]]           # 第八批：只記不是 0 的，index 遞增、都 < ran
    case.assertEqual(idx, sorted(set(idx)))
    case.assertTrue(all(0 <= i < rec["ran"] for i in idx))
    case.assertNotIn({"exit": 0}, [{k: v for k, v in t.items() if k == "exit"} for t in rec["tasks"]])
    _check_schema(rec)


def _check_schema(rec, raw=False):
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return
    sd = os.path.join(HERE, "..", "..", "..", "spec", "protocol", "schemas")
    res = {}
    for n in ("common.schema.json", "tick-record.schema.json"):
        with open(os.path.join(sd, n), encoding="utf-8") as f:
            res[n] = Resource.from_contents(json.load(f))
    reg = Registry().with_resources(res.items())
    schema = res["tick-record.schema.json"].contents
    if raw:                                            # 第九批：record.json 本體（ran／tasks／hooks 是 $ref）
        schema = {"$ref": "tick-record.schema.json#/$defs/RecordFile"}
    Draft202012Validator(schema, registry=reg).validate(rec)


if __name__ == "__main__":
    unittest.main()
