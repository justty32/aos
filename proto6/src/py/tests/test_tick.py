"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

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

from _util import Base, PY

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


# 使用者 2026-10-01：沒有 AOS_TICK_RECORD，任務從 $AOS_TICK_CWD/<dirname>/tick/current.json 找紀錄；
# dirname 照 AOS_DIRNAME 三態（沒設＝.aos、空字串＝直接在工作資料夾下、其他＝那個名字）
CAT_REC = 'd=${AOS_DIRNAME-.aos}; cat "$AOS_TICK_CWD/${d:+$d/}tick/current.json"'


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

    def rec(self, name="current", cwd=""):
        return json.loads(self.read(os.path.join(cwd, ".aos/tick/%s.json" % name)))


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
        self.assertEqual(self.rec(cwd="n")["tasks"], [{"id": "r", "exit": 0}])

    def test_metainfo_optional(self):
        # 裁定 2026-10-01：頂層 _metainfo 不是必填；每項 _metainfo 照 inst 規則可省（沒寫＝posix 第 1 版）
        self.write(".aos/tasks.json", json.dumps({"tasks": [
            {"id": "a", "argv": ["sh", "-c", "echo a >> ran"]},
            sh("b", "echo b >> ran")]}))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("ran"), "a\nb\n")
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}, {"id": "b", "exit": 0}])

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
        self.tasks(sh("a", "echo > .aos/tick/stop"), bad)
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}])

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
            cur, last = self.read(".aos/tick/current.json"), self.read(".aos/tick/last.json")
            self.write(".aos/tick-blocked", "壞了\n")                 # 鎖先：上一格沒跑完時回 busy 不是 blocked
            r = self.tick()
            self.assertEqual(r.returncode, 0)
            self.assertIn("busy:", r.stderr)
            self.assertNotIn("blocked:", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
            self.assertEqual(self.read(".aos/tick/current.json"), cur)   # 紀錄與 seq 都不動
            self.assertEqual(self.read(".aos/tick/last.json"), last)
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
        cur, last_exists = self.read(".aos/tick/current.json"), self.exists(".aos/tick/last.json")
        self.write(".aos/tick-blocked", "壞了\n")
        r = self.tick()
        self.assertEqual(r.returncode, 0)                 # 正常中斷也是 0（使用者 2026-10-01 再改）
        self.assertIn("blocked: 壞了", r.stderr)
        self.assertEqual(self.read("ran.txt"), "ran\n")
        self.assertEqual(self.read(".aos/tick/current.json"), cur)
        self.assertEqual(self.exists(".aos/tick/last.json"), last_exists)
        os.unlink(os.path.join(self.d, ".aos/tick-blocked"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec()["seq"], 2)


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
        self.assertFalse(self.exists(".aos/tick/last.json"))


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
        cur, last = self.read(".aos/tick/current.json"), self.read(".aos/tick/last.json")
        self.write(".aos/tasks.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_table:", r.stderr)
        self.assertEqual(self.read(".aos/tick/current.json"), cur)
        self.assertEqual(self.read(".aos/tick/last.json"), last)
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
        self.assertEqual([t["id"] for t in self.rec()["tasks"]], ["a", "a", "b"])

    def test_no_id(self):
        # 使用者 2026-10-01：沒寫 id 就用它在 tasks 陣列的位置（從 0 起）轉字串；撞了不管
        self.tasks(sh("1", "true"),
                   {"argv": ["sh", "-c", 'echo "$AOS_TASK_ID" > id.txt; exit 4']},
                   {"argv": ["sh", "-c", "echo > .aos/tick/stop"]}, sh("d", "touch d.ran"))
        r = self.tick(env={"AOS_TASK_ID": "外層的"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("id.txt"), "1\n")
        self.assertFalse(self.exists("d.ran"))
        rec = self.rec()
        self.assertEqual(rec["tasks"], [{"id": "1", "exit": 0}, {"id": "1", "exit": 4},
                                        {"id": "2", "exit": 0}])
        self.assertEqual(rec["stopped_after"], "2")


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
        self.assertEqual([t["id"] for t in self.rec()["tasks"]], ["build", "report", "clean"])
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
        self.put({"stderr": {"$ref": "nope.json"}, "tasks": [sh("a", "echo > .aos/tick/stop")]})
        self.assertEqual(self.tick().returncode, 1)              # 對照：頂層預設的值本身讀表時解一層
        self.put({"tasks": [sh("a", "echo > .aos/tick/stop"), broken]})
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}])
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
        self.assertEqual(json.loads(self.read("rec.json"))["tasks"], [{"id": "a", "exit": 0}])
        self.assertNotIn("user_mismatch", r.stderr)          # user 不看，照 tick 自己的帳號跑
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}, {"id": "b", "exit": 0},
                                               {"id": "c", "signal": 9}, {"id": "d", "exit": 0},
                                               {"id": "f", "exit": 3},
                                               {"id": "g", "exit": 0}])
        check_record(self, self.rec())

class Step6Stop(TickCase):

    def test_stop_file(self):
        # 使用者 2026-10-01：停格檔不算中斷，回 0（暫定）
        self.tasks(sh("a", "true"), sh("b", "echo 手動停 > .aos/tick/stop"), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("stopped: 手動停", r.stderr)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["stopped_after"], rec["exit"], len(rec["tasks"])), ("b", 0, 2))
        check_record(self, rec)
        self.tasks(sh("a", "true"), sh("b", "true"), sh("c", "touch c.ran"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("c.ran"))
        self.assertFalse(self.exists(".aos/tick/stop"))

    def test_stop_file_after_error(self):
        self.tasks(sh("a", "exit 1"), sh("b", "echo 停 > .aos/tick/stop"), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["stopped_after"], rec["exit"]), ("b", 0))
        check_record(self, rec)


class ExitCodes(TickCase):
    """aos 結束碼慣例下的 tick 結束碼（使用者 2026-10-01）：任務的碼只記、不影響 tick。"""

    def test_task_codes_only_recorded(self):
        self.tasks(sh("a", "exit 1"), sh("b", "exit 2"), sh("c", "exit 127"),
                   sh("d", "kill -2 $$"), sh("e", "touch e.ran"))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("e.ran"))             # 回 2、回錯都照常跑下一項
        rec = self.rec()
        self.assertEqual(rec["tasks"], [{"id": "a", "exit": 1}, {"id": "b", "exit": 2},
                                        {"id": "c", "exit": 127}, {"id": "d", "signal": 2},
                                        {"id": "e", "exit": 0}])     # 照實記原碼
        self.assertEqual(rec["exit"], 0)
        check_record(self, rec)

    def test_bad_current_json_is_error(self):
        self.tasks(sh("t", "touch ran"))
        self.write(".aos/tick/current.json", "{壞")
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
            sh("b", "echo 停 > .aos2/tick/stop"), sh("c", "touch c.ran"))))
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stopped: 停", r.stderr)
        self.assertFalse(self.exists("c.ran"))
        self.assertEqual(self.read("a.txt"), ".aos2\n")
        self.assertEqual(json.loads(self.read("a.json"))["seq"], 1)        # 從 $AOS_TICK_CWD/.aos2/tick/ 找得到
        rec = json.loads(self.read(".aos2/tick/current.json"))
        self.assertEqual((rec["seq"], rec["stopped_after"]), (1, "b"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, ".aos2"))), ["tasks.json", "tick", "tick.lock"])
        self.write(".aos2/tick-blocked", "擋\n")
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 0)
        self.assertIn("blocked: 擋", r.stderr)
        os.unlink(os.path.join(self.d, ".aos2/tick-blocked"))
        self.assertTrue(self.exists(".aos2/tick/stop"))
        self.write(".aos2/tasks.json", json.dumps(table(sh("c", "touch c.ran"))))
        self.assertEqual(self.tick(env=self.ENV).returncode, 0)
        self.assertTrue(self.exists("c.ran"))                         # 停格檔在 .aos2/tick/ 被刪
        self.assertEqual(json.loads(self.read(".aos2/tick/last.json"))["seq"], 1)
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
    tasks.json、tick.lock、tick-blocked、tick/stop、tick/current.json、last.json 都直接在工作資料夾下。
    跟「沒設」（＝.aos）分得開。"""

    ENV = {"AOS_DIRNAME": ""}

    def test_all_directly_under_cwd(self):
        self.tasks(sh("wrong", "touch wrong.ran"))                     # .aos/tasks.json 不該被用
        self.write("tasks.json", json.dumps(table(
            sh("a", 'echo "[$AOS_DIRNAME]" > a.txt; ' + CAT_REC + " > a.json"),
            sh("b", "echo 停 > tick/stop"), sh("c", "touch c.ran"))))
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stopped: 停", r.stderr)
        self.assertFalse(self.exists("c.ran"))
        self.assertEqual(self.read("a.txt"), "[]\n")
        self.assertEqual(json.loads(self.read("a.json"))["seq"], 1)        # 從 $AOS_TICK_CWD/tick/ 找得到
        self.assertEqual(json.loads(self.read("tick/current.json"))["seq"], 1)
        self.assertTrue(self.exists("tick.lock"))
        self.assertEqual(os.listdir(os.path.join(self.d, ".aos")), ["tasks.json"])   # .aos/ 沒被碰
        self.write("tick-blocked", "擋\n")
        r = self.tick(env=self.ENV)
        self.assertEqual(r.returncode, 0)
        self.assertIn("blocked: 擋", r.stderr)
        os.unlink(os.path.join(self.d, "tick-blocked"))
        self.write("tasks.json", json.dumps(table(sh("c", "touch c.ran"))))
        self.assertEqual(self.tick(env=self.ENV).returncode, 0)
        self.assertTrue(self.exists("c.ran"))                         # 停格檔 tick/stop 被刪
        self.assertFalse(self.exists("tick/stop"))
        self.assertEqual(json.loads(self.read("tick/last.json"))["seq"], 1)
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
        self.assertTrue(self.exists(".aos/tick/current.json"))
        self.assertFalse(self.exists("tick"))

class Step9Whole(TickCase):

    def test_b626_only_true_no_daemon(self):
        self.tasks(task("t", ["true"]))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertNotIn("standard:", r.stderr)
        check_record(self, self.rec())


def check_record(case, rec):
    """P-213 的跨欄位規則＋（有 jsonschema 時）tick-record schema。"""
    if rec.get("ended"):
        case.assertEqual(rec["exit"], 0)                  # 寫得到收尾就是 0，任務成敗不影響
        if "stopped_after" in rec:
            case.assertEqual(rec["tasks"][-1]["id"], rec["stopped_after"])
    else:
        case.assertNotIn("exit", rec)
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
    Draft202012Validator(res["tick-record.schema.json"].contents, registry=reg).validate(rec)


if __name__ == "__main__":
    unittest.main()
