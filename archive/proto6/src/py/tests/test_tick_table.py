"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

本檔：讀表、驗表、頂層預設（Step4Table、Step4Check、Step4Defaults）。

〔使用者方向 2026-10-01〕POC 默認一切正常：驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
同資料夾互斥同日加回最簡版（拿不到鎖回 0，見 Step1Lock）；表壞在換紀錄之前，不佔 seq。
結束碼照 aos 體系慣例（0＝預料之中，含正常中斷；非 0＝要額外處理；1＝通用錯誤；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import subprocess
import unittest

from _util import PY
from _tick_util import CLEAN_ENV, POSIX, TICK, TickCase, check_record, sh, table, task


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
    """使用者 2026-10-01：tasks.json 頂層可放 inst 的七個欄位當每一項的預設；淺層合併、項蓋過；
    頂層 cwd 不改 tick 自己的 cwd、相對以工作資料夾為起點。頂層 `_metainfo`、`id`、`kind`、`modules` 不當預設。
    第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」——開格時已知的鍵整個展開，`$ref:""`／`#…` 指整份
    tasks.json、相對檔名以工作資料夾為準、值是開格那一刻的；展開失敗＝bad_table、不開格。"""

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

    def test_ref_points_to_whole_table(self):
        # 第二十批：`#/id` 指整份 tasks.json 的頂層 id，不是合併後的這一項；頂層 id 不當預設
        self.put({"id": "TOP", "envs": {"WHO": {"$ref": "#/id"}}, "tasks": [
            sh("a", 'echo "$WHO" >> who'), sh("b", 'echo "$WHO" >> who')]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("who"), "TOP\nTOP\n")

    def test_ref_relative_to_work_dir_not_item_cwd(self):
        # 相對檔名以工作資料夾為準；那一項的 cwd 是 sub/ 也一樣（sub/ 底下同名檔不會被讀）
        self.write("v.json", json.dumps("from-top"))
        self.write("sub/v.json", json.dumps("from-sub"))
        self.put({"tasks": [sh("a", 'echo "$V" > v.out', cwd="sub", envs={"V": {"$ref": "v.json"}})]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("sub/v.out"), "from-top\n")

    def test_item_interior_expanded_at_open(self):
        # 第二項內部有壞 $env／$ref：開格就展開，bad_table、回 1、不開格（第一項也沒跑）
        broken = {"id": "x", "argv": ["true"], "envs": {"X": {"$env": "AOSTEST_SURELY_NOT_SET"}}}
        for b in (broken, dict(broken, envs={}, stdout={"$ref": "nope.json"}),
                  {"id": "x", "argv": ["sh", "-c", {"$fmt": {"$val": "${v}", "v": {"$ref": "#/nope"}}}]}):
            self.put({"tasks": [sh("a", "touch a.ran"), b]})
            r = self.tick()
            self.assertEqual(r.returncode, 1, b)
            self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("a.ran"))
        self.assertFalse(self.exists(".aos/tick/current"))

    def test_values_fixed_at_open(self):
        # 值是開格那一刻的：前面的任務改了被 $ref 的檔，後面的項讀到的還是舊的
        self.write("v.json", json.dumps("old"))
        self.put({"tasks": [sh("a", "echo '\"new\"' > v.json"),
                            sh("b", 'echo "$V" > v.out', envs={"V": {"$ref": "v.json"}})]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("v.out"), "old\n")
        # 指向前面任務才會產生的檔：開格就 bad_table
        self.put({"tasks": [sh("a", "echo 1 > later.json"),
                            sh("b", "true", envs={"V": {"$ref": "later.json"}})]})
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("later.json"))

    def test_options_kept_and_val_expanded(self):
        # 選項物件照用：`$val` 裡的指示詞開格就展開，`$opt` 原樣交給 inst 規則
        self.put({"dir": "made", "tasks": [sh("a", "pwd > here", cwd={"$opt": "mkdir", "$val": {"$ref": "#/dir"}})]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("made/here"), os.path.join(self.d, "made") + "\n")

    def test_unknown_keys_and_metainfo_not_expanded(self):
        # 第二十批「除了陌生鍵和_metainfo」：頂層與每項的陌生鍵、頂層 _metainfo 不解，寫壞的指示詞不影響開格
        bad = {"$ref": "nope.json"}
        self.put({"_metainfo": bad, "junk": bad, "hooks": {"before_task": bad},
                  "tasks": [sh("a", "touch a.ran", group=bad, needs=bad)]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("a.ran"))
        import aos_tick_table
        tbl = aos_tick_table.check_table({"tasks": [{"argv": ["true"], "x": bad, "_metainfo": bad}]}, self.d)
        self.assertEqual((tbl.items[0]["x"], tbl.items[0]["_metainfo"]), (bad, bad))

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


if __name__ == "__main__":
    unittest.main()
