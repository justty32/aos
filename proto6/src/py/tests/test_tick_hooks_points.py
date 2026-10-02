"""aos-tick 的 hooks（掛點；plan m1h-hooks-module.md、spec B-635）。真的開 bin/aos-tick 子程序。

本檔：第十七批新掛點 before_all、after_task、after_every_task（NewPoints）。

使用者裁定 2026-10-01：hooks 設定在 tasks.json 頂層 `hooks`（跟 `tasks` 同層；同日改：「就不讓他當模組了，
直接讓他變頂層key」，展開時機比照 tasks）；目前只開 `after_all`
（照表跑完、含被停格檔停下之後跑），值是一串、寫法比照 tasks、吃頂層預設；不看停格檔；碼照實記進
本格紀錄的 `hooks.after_all`（第九批拆檔後在 `tick/current/hook-exits.json`，record.json 用 $ref 指過去）、不影響 tick 的結束碼；擋板、busy、表壞時不跑。
第八批（使用者 2026-10-01）：「hooks也是」——只記不是 0 的，每筆 {"id","index","exit"}；hooks 不記 ran。
第十批（使用者 2026-10-01）：hook 拿到 AOS_HOOK_POINT／AOS_HOOK_INDEX／AOS_HOOK_ID，不給 AOS_TASK_ID／INDEX；
任務照舊只有 AOS_TASK_*、拿不到 AOS_HOOK_*（外層環境繼承來的也拿掉）。
"""
import json
import os
import unittest

from _tick_util import check_record, sh, task, CAT_REC
from _tick_hooks_util import HooksCase


ENVS = 'echo "$AOS_HOOK_POINT|$AOS_HOOK_INDEX|$AOS_HOOK_ID|${AOS_TASK_ID-none}|${AOS_TASK_INDEX-none}|${AOS_TASK_EXIT-none}" >> h.log'


class NewPoints(HooksCase):
    """使用者 2026-10-01 第十七批：before_all、after_task（{任務 id: [inst…]}）、after_every_task；
    跟任務有關的兩個另給剛跑完那一項的 AOS_TASK_ID／INDEX／EXIT。"""

    def lines(self):
        return self.read("h.log").splitlines()

    def test_order_and_env(self):
        self.put({"tasks": [sh("a", "echo task-a >> h.log; exit 3"), {"argv": ["sh", "-c", "echo task-1 >> h.log; kill -9 $$"]}],
                  "hooks": {"before_all": [sh("b0", ENVS)],
                            "after_task": {"a": [sh("ta", ENVS), sh("tb", ENVS)], "1": [sh("t1", ENVS)], "nope": [sh("x", "touch x.ran")]},
                            "after_every_task": [sh("ev", ENVS)],
                            "after_all": [sh("aa", ENVS)]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.lines(), [
            "before_all|0|b0|none|none|none",
            "task-a",
            "after_task|0|ta|a|0|3", "after_task|1|tb|a|0|3",         # 先 after_task.<id>
            "after_every_task|0|ev|a|0|3",                             # 再 after_every_task
            "task-1",
            "after_task|0|t1|1|1|137",                                 # 沒寫 id 的用位置；被訊號 9 殺＝128+9
            "after_every_task|0|ev|1|1|137",
            "after_all|0|aa|none|none|none"])
        self.assertFalse(self.exists("x.ran"))                         # 不存在的 id：不跑、不報錯
        rec = self.rec()
        self.assertEqual(list(rec["hooks"]), ["before_all", "after_task", "after_every_task", "after_all"])
        self.assertEqual(rec["hooks"], {"before_all": [], "after_task": [], "after_every_task": [], "after_all": []})
        check_record(self, rec)

    def test_nonzero_recorded_with_task_index(self):
        self.put({"tasks": [sh("a", "true"), sh("b", "true")],
                  "hooks": {"before_all": [sh("b0", "exit 2")], "after_task": {"b": [sh("tb", "exit 5")]},
                            "after_every_task": [sh("ev", '[ "$AOS_TASK_ID" = a ] && exit 4; exit 0')]}})
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        rec = self.rec()
        self.assertEqual(rec["hooks"], {"before_all": [{"id": "b0", "index": 0, "exit": 2}],
                                        "after_task": [{"id": "tb", "index": 0, "task_index": 1, "exit": 5}],
                                        "after_every_task": [{"id": "ev", "index": 0, "task_index": 0, "exit": 4}]})
        self.assertEqual((rec["ran"], rec["tasks"]), (2, []))
        check_record(self, rec)

    def test_blocked_task_not_triggered_and_hooks_ignore_file(self):
        # b 被 tasks-blocked 擋下：不觸發；after_task 寫了 tasks-blocked 也不擋後面的 hook，只擋下一項任務
        self.put({"tasks": [sh("a", "true"), sh("b", "touch b.ran")],
                  "hooks": {"after_task": {"a": [sh("blk", ": > .aos/tick/tasks-blocked"), sh("t2", ENVS)], "b": [sh("tb", ENVS)]},
                            "after_every_task": [sh("ev", ENVS)]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("b.ran"))
        self.assertEqual(self.lines(), ["after_task|1|t2|a|0|0", "after_every_task|0|ev|a|0|0"])
        self.assertEqual(self.rec()["blocked_before"], "b")

    def test_before_all_runs_before_tasks_blocked_check(self):
        # before_all 在第一項（含 tasks-blocked 的檢查）之前：它寫的 tasks-blocked 擋下第一項
        self.put({"tasks": [sh("a", "touch a.ran")], "hooks": {"before_all": [sh("b0", ": > .aos/tick/tasks-blocked")]}})
        self.assertEqual(self.tick().returncode, 0)
        self.assertFalse(self.exists("a.ran"))
        self.assertEqual((self.rec()["blocked_before"], self.rec()["ran"]), ("a", 0))

    def test_before_all_not_run_when_tick_not_opened(self):
        self.put({"tasks": [sh("a", "true")], "hooks": {"before_all": [sh("b0", "touch b0.ran")]}})
        self.write(".aos/tick-blocked", "")
        self.assertEqual(self.tick().returncode, 0)
        self.assertFalse(self.exists("b0.ran"))
        os.unlink(os.path.join(self.d, ".aos/tick-blocked"))
        self.put({"tasks": [{"id": "a"}], "hooks": {"before_all": [sh("b0", "touch b0.ran")]}})
        self.assertEqual(self.tick().returncode, 1)                   # 表壞
        self.assertFalse(self.exists("b0.ran"))

    def test_task_exit_not_leaked(self):
        # AOS_TASK_EXIT 只有 after_task／after_every_task 有；外層繼承來的一律先拿掉
        self.put({"tasks": [sh("a", 'echo "task ${AOS_TASK_EXIT-none}" >> h.log')],
                  "hooks": {"before_all": [sh("b0", 'echo "before ${AOS_TASK_EXIT-none}" >> h.log')],
                            "after_all": [sh("aa", 'echo "after ${AOS_TASK_EXIT-none}" >> h.log')]}})
        r = self.tick(env={"AOS_TASK_EXIT": "外層"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.lines(), ["before none", "task none", "after none"])

    def test_hook_record_while_running(self):
        # 格中就有 hooks：before_all 跑的時候讀得到 ended:false、hooks 已備好
        self.put({"tasks": [sh("a", "true")], "hooks": {"before_all": [sh("look", CAT_REC + " > seen.json")]}})
        self.assertEqual(self.tick().returncode, 0)
        seen = json.loads(self.read("seen.json"))
        self.assertEqual((seen["ended"], seen["hooks"]), (False, {"before_all": []}))
        check_record(self, seen)

    def test_bad_shapes(self):
        for hooks in ({"before_all": {}}, {"after_task": []}, {"after_task": {"a": {}}}, {"after_every_task": [{"id": "x"}]}):
            self.put({"tasks": [sh("a", "touch a.ran")], "hooks": hooks})
            r = self.tick()
            self.assertEqual(r.returncode, 1, hooks)
            self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("a.ran"))

    def test_exec_failed_labels(self):
        self.put({"tasks": [sh("a", "true")],
                  "hooks": {"before_all": [task("p", ["no-such-program-aos"])],
                            "after_task": {"a": [task("q", ["no-such-program-aos"])]}}})
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("exec_failed: before_all/p:", r.stderr)
        self.assertIn("exec_failed: after_task/a/q:", r.stderr)


if __name__ == "__main__":
    unittest.main()
