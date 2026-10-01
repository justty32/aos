"""aos-tick 的 hooks（掛點；plan m1h-hooks-module.md、spec B-635）。真的開 bin/aos-tick 子程序。

使用者裁定 2026-10-01：hooks 設定在 tasks.json 頂層 `hooks`（跟 `tasks` 同層；同日改：「就不讓他當模組了，
直接讓他變頂層key」，展開時機比照 tasks）；目前只開 `after_all`
（照表跑完、含被停格檔停下之後跑），值是一串、寫法比照 tasks、吃頂層預設；不看停格檔；碼照實記進
本格紀錄的 `hooks.after_all`（第九批拆檔後在 `tick/current/hook-exits.json`，record.json 用 $ref 指過去）、不影響 tick 的結束碼；擋板、busy、表壞時不跑。
第八批（使用者 2026-10-01）：「hooks也是」——只記不是 0 的，每筆 {"id","index","exit"}；hooks 不記 ran。
第十批（使用者 2026-10-01）：hook 拿到 AOS_HOOK_POINT／AOS_HOOK_INDEX／AOS_HOOK_ID，不給 AOS_TASK_ID／INDEX；
任務照舊只有 AOS_TASK_*、拿不到 AOS_HOOK_*（外層環境繼承來的也拿掉）。
"""
import fcntl
import json
import os

from test_tick import TickCase, check_record, sh, task, CAT_REC

LOG = 'echo "$AOS_HOOK_ID $AOS_HOOK_INDEX ${X-}" >> h.log'


class HooksCase(TickCase):

    def put(self, doc):
        self.write(".aos/tasks.json", json.dumps(doc, ensure_ascii=False))

    def hooks(self, after_all, tasks=None, **top):
        doc = dict(top, tasks=tasks if tasks is not None else [sh("a", "echo task >> h.log")],
                   hooks={"after_all": after_all})
        self.put(doc)


class NoHooks(HooksCase):

    def test_no_hooks_unchanged(self):
        # 沒寫 hooks、hooks 裡沒有 after_all（別的鍵照收不理、也不解）：紀錄裡都沒有 hooks
        for extra in ({}, {"hooks": {}}, {"hooks": {"before_all": {"$ref": "nope.json"}}}):
            self.put(dict({"tasks": [sh("a", "true")]}, **extra))
            r = self.tick()
            self.assertEqual((r.returncode, r.stderr), (0, ""), extra)
            rec = self.rec()
            self.assertNotIn("hooks", rec)
            self.assertEqual((rec["ran"], rec["tasks"]), (1, []))
            check_record(self, rec)

    def test_modules_hooks_is_not_hooks(self):
        # 使用者改裁定：hooks 不當模組；寫在 modules 底下照收不理、不跑
        self.put({"tasks": [sh("a", "true")], "modules": {"hooks": {"after_all": [sh("h", "touch h.ran")]}}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("h.ran"))
        self.assertNotIn("hooks", self.rec())


class AfterAll(HooksCase):

    def test_sequence_defaults_override(self):
        # 依序跑、在任務之後；吃頂層預設（argv、envs），項自己寫了就蓋過（envs 整包換）；沒寫 id 用位置
        self.hooks([{}, {"id": "two", "envs": {"X": "own"}}, {"argv": ["sh", "-c", "echo third >> h.log"]}],
                   tasks=[sh("a", "echo task >> h.log")],
                   argv=["sh", "-c", LOG], envs={"X": "top"})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("h.log"), "task\n0 0 top\ntwo 1 own\nthird\n")
        rec = self.rec()
        self.assertEqual((rec["ran"], rec["tasks"]), (1, []))
        self.assertEqual(rec["hooks"], {"after_all": []})         # 三個都是 0，不記（第八批）
        self.assertEqual((rec["ended"], rec["exit"]), (True, 0))
        check_record(self, rec)

    def test_env_and_cwd_like_tasks(self):
        # cwd 跟任務一樣（頂層 cwd 是預設、相對工作資料夾）；環境：AOS_TICK_CWD、AOS_HOOK_POINT／INDEX／ID（第十批），
        # 沒有 AOS_TASK_*（連外層環境繼承來的也拿掉）；任務那邊拿不到 AOS_HOOK_*（同上）
        os.makedirs(os.path.join(self.d, "work"))
        self.hooks([sh("x", "true"), sh("h", "env > hook.env; pwd > hook.pwd"), {"argv": ["sh", "-c", "env > nid.env"]}],
                   tasks=[sh("a", "env > task.env")], cwd="work")
        outer = {"AOS_TASK_ID": "外層", "AOS_TASK_INDEX": "9", "AOS_HOOK_POINT": "外層", "AOS_HOOK_INDEX": "9",
                 "AOS_HOOK_ID": "外層"}
        r = self.tick(env=outer)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        read_env = lambda p: dict(l.split("=", 1) for l in self.read(p).splitlines() if "=" in l)
        env = read_env("work/hook.env")
        self.assertEqual((env["AOS_TICK_CWD"], env["AOS_HOOK_POINT"], env["AOS_HOOK_INDEX"], env["AOS_HOOK_ID"]),
                         (self.d, "after_all", "1", "h"))
        self.assertNotIn("AOS_TASK_ID", env)
        self.assertNotIn("AOS_TASK_INDEX", env)
        self.assertNotIn("AOS_TICK_LOCK_FD", env)
        nid = read_env("work/nid.env")                       # 沒寫 id：位置轉字串
        self.assertEqual((nid["AOS_HOOK_INDEX"], nid["AOS_HOOK_ID"]), ("2", "2"))
        tenv = read_env("work/task.env")
        self.assertEqual((tenv["AOS_TICK_CWD"], tenv["AOS_TASK_ID"], tenv["AOS_TASK_INDEX"]), (self.d, "a", "0"))
        for k in ("AOS_HOOK_POINT", "AOS_HOOK_INDEX", "AOS_HOOK_ID"):
            self.assertNotIn(k, tenv)
        self.assertEqual(self.read("work/hook.pwd"), os.path.join(self.d, "work") + "\n")

    def test_hook_sees_ended_record(self):
        # 寫在收尾之後：hook 讀得到 ended:true、本格各項與前面 hook 的碼
        self.hooks([sh("first", "exit 4"), sh("look", CAT_REC + " > seen.json")])
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        seen = json.loads(self.read("seen.json"))
        self.assertEqual((seen["ended"], seen["exit"], seen["ran"], seen["tasks"]), (True, 0, 1, []))
        self.assertEqual(seen["hooks"], {"after_all": [{"id": "first", "index": 0, "exit": 4}]})

    def test_nonzero_recorded_tick_0_next_runs(self):
        self.hooks([sh("f", "exit 3"), sh("k", "kill -9 $$"), task("n", ["no-such-program-aos"]),
                    sh("z", "touch z.ran")])
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("exec_failed: after_all/n:", r.stderr)
        self.assertTrue(self.exists("z.ran"))
        self.assertEqual(self.rec()["hooks"]["after_all"],
                         [{"id": "f", "index": 0, "exit": 3}, {"id": "k", "index": 1, "signal": 9},
                          {"id": "n", "index": 2, "exit": 127}])          # z 是 0，不記
        check_record(self, self.rec())

    def test_runs_after_blocked_and_ignores_tasks_blocked(self):
        # 被 tasks-blocked 擋下照跑（after_all 跟任務無關，第十六批）；hook 不看 tasks-blocked；hook 寫的整格最後一樣刪
        self.hooks([sh("s", "echo > .aos/tick/tasks-blocked"), sh("h", "touch h.ran")],
                   tasks=[sh("a", "echo > .aos/tick/tasks-blocked"), sh("b", "touch b.ran")])
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(self.exists("b.ran"))
        self.assertTrue(self.exists("h.ran"))
        rec = self.rec()
        self.assertEqual((rec["blocked_before"], rec["ran"], rec["tasks"]), ("b", 1, []))
        self.assertEqual(rec["hooks"]["after_all"], [])
        check_record(self, rec)
        self.assertFalse(self.exists(".aos/tick/tasks-blocked"))

    def test_empty_after_all_and_unknown_points(self):
        self.put({"tasks": [sh("a", "true")],
                  "hooks": {"after_all": [], "before_all": [sh("x", "touch x.ran")]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.rec()["hooks"], {"after_all": []})
        self.assertFalse(self.exists("x.ran"))                 # 還沒開的掛點照收不理

    def test_ref_layers_like_tasks(self):
        # 展開時機比照 tasks：hooks、after_all、每一元素各解一層（整串、整項都可以 $ref）
        self.write("hooks.d/one.json", json.dumps(sh("one", "touch one.ran; exit 1")))
        self.write("hooks.d/list.json", json.dumps([{"$ref": "hooks.d/one.json"},
                                                    sh("two", "touch two.ran; exit 2")]))
        self.write("hooks.d/hooks.json", json.dumps({"after_all": {"$ref": "hooks.d/list.json"}}))
        self.put({"tasks": [sh("a", "true")], "hooks": {"$ref": "hooks.d/hooks.json"}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("one.ran") and self.exists("two.ran"))
        self.assertEqual([h["id"] for h in self.rec()["hooks"]["after_all"]], ["one", "two"])

    def test_interior_resolved_when_run_against_merged_item(self):
        # 值的內部跑到時才展開，`#…` 指合併後的這一項（跟 tasks 一樣），不是整份 tasks.json
        self.put({"envs": {"X": "top"}, "tasks": [sh("a", "true")], "k": "整份表的",
                  "hooks": {"after_all": [{"argv": ["sh", "-c", {"$fmt": {"$val": "echo ${v} $X > h.out",
                                                                            "v": {"$ref": "#/k"}}}],
                                           "k": "這一項的"}]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("h.out"), "這一項的 top\n")

    def test_into_last(self):
        self.hooks([sh("h", "exit 2")])
        self.assertEqual(self.tick().returncode, 0)
        self.put({"tasks": [sh("a", "true")]})                # 第二格沒 hooks
        self.assertEqual(self.tick().returncode, 0)
        last, cur = self.rec("last"), self.rec()
        self.assertEqual((last["seq"], last["hooks"]), (1, {"after_all": [{"id": "h", "index": 0, "exit": 2}]}))
        self.assertEqual(cur["seq"], 2)
        self.assertNotIn("hooks", cur)
        check_record(self, last)
        self.assertTrue(self.exists(".aos/tick/last/hook-exits.json"))
        self.assertFalse(self.exists(".aos/tick/current/hook-exits.json"))

    def test_hook_exits_file(self):
        # 第九批：有 hooks 時收尾先寫 hook-exits.json（{"after_all":[]}）、record.json 加 "hooks":{"$ref":"hook-exits.json"}；
        # 之後只有不是 0 的 hook 才重寫它
        self.hooks([sh("look", "cat .aos/tick/current/hook-exits.json > h0.json; "
                               "cat .aos/tick/current/record.json > r0.json"), sh("bad", "exit 6")])
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(json.loads(self.read("h0.json")), {"after_all": []})
        r0 = json.loads(self.read("r0.json"))
        self.assertEqual((r0["hooks"], r0["ended"]), ({"$ref": "hook-exits.json"}, True))
        self.assertEqual(json.loads(self.read(".aos/tick/current/record.json")), r0)   # hooks 跑時 record.json 不再寫
        self.assertEqual(json.loads(self.read(".aos/tick/current/hook-exits.json")),
                         {"after_all": [{"id": "bad", "index": 1, "exit": 6}]})


class NotRun(HooksCase):

    def test_blocked(self):
        self.hooks([sh("h", "touch h.ran")])
        self.write(".aos/tick-blocked", "壞了\n")
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")                    # 第十六批：靜靜結束，hooks 根本不啟動
        self.assertFalse(self.exists("h.ran"))
        self.assertFalse(self.exists(".aos/tick"))

    def test_busy(self):
        self.hooks([sh("h", "touch h.ran")])
        fd = os.open(os.path.join(self.d, ".aos", "tick.lock"), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = self.tick()
        finally:
            os.close(fd)
        self.assertEqual(r.returncode, 0)
        self.assertIn("busy:", r.stderr)
        self.assertFalse(self.exists("h.ran"))
        self.assertFalse(self.exists("h.log"))

    def test_bad_table_elsewhere(self):
        self.hooks([sh("h", "touch h.ran")], tasks=[{"id": "noargv"}])
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad_table:", r.stderr)
        self.assertFalse(self.exists("h.ran"))

    def test_bad_after_all_is_bad_table(self):
        # 在開格前查到：一項都不跑、紀錄與 seq 都不動
        self.put({"tasks": [sh("a", "true")]})
        self.assertEqual(self.tick().returncode, 0)
        cur = self.snap(".aos/tick/current")
        bad = [{"after_all": sh("h", "true")},              # 不是陣列
               {"after_all": [sh("h", "true"), "true"]},    # 某項不是物件
               {"after_all": [{"id": "h"}]},                # 合併預設後沒 argv
               [sh("h", "true")],                           # hooks 不是物件
               {"after_all": [{"$ref": "nope.json"}]},      # 讀表那一層解不開
               {"$ref": "nope.json"}]
        for hooks in bad:
            self.put({"tasks": [sh("a", "touch a.ran")], "hooks": hooks})
            r = self.tick()
            self.assertEqual(r.returncode, 1, hooks)
            self.assertIn("bad_table:", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
            self.assertFalse(self.exists("a.ran"))
            self.assertEqual(self.snap(".aos/tick/current"), cur)
            self.assertFalse(self.exists(".aos/tick/last"))

    def test_top_argv_satisfies_hook(self):
        self.put({"argv": ["sh", "-c", "touch \"${AOS_TASK_ID-}${AOS_HOOK_ID-}.ran\""], "tasks": [{"id": "a"}],
                  "hooks": {"after_all": [{"id": "h"}]}})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("a.ran") and self.exists("h.ran"))


if __name__ == "__main__":
    import unittest
    unittest.main()
