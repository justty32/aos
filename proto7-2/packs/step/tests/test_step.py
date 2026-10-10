"""step 任務包測試。"""
from _step import *  # noqa: F403

class TestStepProbes(StepCase):
    """〔step〕中斷探針（astra 探針表、綜合 §1 第 6 點）：手動 tick／tock，直譯器是真的 keep 任務。"""

    def setup_job(self, job, table):
        node = self.mknode("a")
        self.set_tasks(node, [self.install(node, job, table)])
        return node

    def test_expired_intent_unknown(self):
        """過期 intent（R8-13）：不再直接停，走 on_unknown——stop 停 unknown、receipt 當 ok、resend 同 request 派 a2。"""
        for mode in ("stop", "receipt", "resend"):
            with self.subTest(mode=mode):
                a = {"receipt": {"exists": "${job}/rcpt"}} if mode == "receipt" else {"on_unknown": mode}
                node = self.setup_job("ei", probe_table("ei", a=a))
                self.crash_at(node, "ei", "after-intent")
                self.cycle(node, "ei")
                self.wait_ended(node, "step-ei")
                req = self.frame(node, "ei")["pending"]["request"]
                self.set_enabled(node, "step-ei", False)
                if mode == "receipt":
                    open(self.jd(node, "ei", "rcpt"), "w").close()
                for _ in range(4):
                    self.cycle(node, "ei", wait=False)
                self.set_enabled(node, "step-ei", True)
                self.run_until(node, "ei", lambda: self.frame(node, "ei").get("phase") in ("halted", "ended"))
                fr = self.frame(node, "ei")
                if mode == "stop":
                    self.assertEqual((fr["halt"]["kind"], fr["pending"]["state"]), ("unknown", "intent"))
                elif mode == "receipt":
                    self.assertTrue(fr["accepted"]["a"]["receipt"])
                else:
                    self.assertEqual(fr["end"], "ok")
                    self.assertEqual(fr["accepted"]["a"]["request"], req)
                    self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                self.assertEqual(len(self.ran(node, "ei-a")), int(mode == "resend"))
                self.reap_space()

    def test_intent_round_tick_overlap(self):
        """R8-22 時序驗證：直譯器讀到回合 r（tick r 已開、還沒讀表）就加項，once 在 r 起、沒結果就死、tock r+1 刪槽；
        r+1 時不准補加同一 attempt（D5 縮窗：補加只准同回合）→ halt unknown、只跑一次。舊窗口（≤ intent_round+1）會跑兩次。"""
        node = self.mknode("a")
        self.install(node, "ov", probe_table("ov", gate=True))
        self.set_tasks(node, [])
        open(self.jd(node, "ov", "gate-a"), "w").close()
        r = self.tick()["round"] + 1
        self.tock()
        def one(override=False):
            code = "import sys; sys.path.insert(0, %r); import aos7_step as s; " % PACK
            if override:
                code += "orig=s.node_round; calls=iter([%d]); s.node_round=lambda *a: next(calls, None) or orig(*a); " % r
            return subprocess.run([PY, "-c", code + "s.run_pass(sys.argv[1], int(sys.argv[2]))",
                                   "jobs/ov", str(r if override else r + 1)], cwd=node,
                                  env=dict(os.environ), timeout=30).returncode
        self.crash_at(node, "ov", "after-add")
        self.assertEqual(one(True), -9)
        p = self.frame(node, "ov")["pending"]
        self.assertEqual((p["state"], p["intent_round"]), ("intent", r))
        self.assertEqual(self.step_items(node)[0]["x"]["step"]["attempt"], p["attempt"])
        self.assertEqual(self.tick()["round"], r)
        self.wait_for(lambda: os.path.exists(self.jd(node, "ov", "gate-a.entered")))
        os.killpg(self.wait_pid(node, "step-ov-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-ov-a")
        self.assertEqual(self.results(node, "ov", "a"), [])
        self.tock()
        self.tick()
        self.tock()
        self.assertFalse(os.path.exists(self.slot(node, "step-ov-a")))
        self.assertEqual(one(), 0)
        for _ in range(2):
            self.tick()
            self.tock()
        self.wait_for(lambda: len(self.ran(node, "ov-a")) >= 1)
        self.assertEqual(len(self.ran(node, "ov-a")), 1)
        self.assertEqual(self.frame(node, "ov")["halt"]["kind"], "unknown")

    def test_sweep_dead_tmp(self):
        """C8-03 step 份：直譯器啟動時清工作資料夾與 results/<步>/ 裡寫者已死的暫存檔，活寫者的不碰。"""
        node = self.setup_job("tmp", probe_table("tmp"))
        os.makedirs(self.jd(node, "tmp", "results", "a"))
        paths = [self.jd(node, "tmp", ".frame.json.tmp.%d" % dead_pid()),
                 self.jd(node, "tmp", "results", "a", ".x.json.tmp.%d" % dead_pid()),
                 self.jd(node, "tmp", ".keep.json.tmp.%d" % os.getpid())]
        for path in paths:
            open(path, "w").close()
        self.run_until(node, "tmp", lambda: self.frame(node, "tmp").get("phase") == "ended")
        self.assertEqual([os.path.exists(path) for path in paths], [False, False, True])

    def test_interp_killed_reattaches_same_attempt(self):
        """子工作還在跑時 SIGKILL 直譯器：keep 重開接回同一個 attempt，不多派；放閘門後照常走完。"""
        node = self.setup_job("k", probe_table("k", gate=True))
        open(self.jd(node, "k", "gate-a"), "w").close()
        self.run_until(node, "k", lambda: os.path.exists(self.jd(node, "k", "gate-a.entered")), msg="a 沒起")
        att = self.frame(node, "k")["pending"]["attempt"]
        self.kill_interp(node, "k")
        for _ in range(3):
            self.cycle(node, "k")
            self.assertEqual(self.step_items(node, "a"), [])
        self.assertEqual(self.frame(node, "k")["pending"]["attempt"], att)
        os.unlink(self.jd(node, "k", "gate-a"))
        self.run_until(node, "k", lambda: self.frame(node, "k").get("phase") == "ended", msg="沒走完")
        fr = self.frame(node, "k")
        self.assertEqual((fr["end"], fr["accepted"]["a"]["attempt"]), ("ok", att))
        self.assertEqual((len(self.ran(node, "k-a")), len(self.ran(node, "k-b"))), (1, 1))

    def test_crash_points_advance_once(self):
        """先驗 SIGKILL 與死亡快照，再恢復；過期 intent 要人手重送。"""
        for point in ("after-intent", "after-add", "before-accept"):
            with self.subTest(point=point):
                job = point.replace("-", "")
                node = self.setup_job(job, probe_table(job))
                self.crash_at(node, job, point)
                for _ in range(12):
                    self.cycle(node, job)
                    b, ex = self.birth(node, "step-" + job), self.exit_raw(node, "step-" + job)
                    if not os.path.exists(self.jd(node, job, ".step-crash")):
                        self.wait_ended(node, "step-" + job, b["run"])
                        ex = self.exit_raw(node, "step-" + job)
                        self.assertEqual((ex["run"], ex["code"]), (b["run"], -9))
                        break
                else:
                    self.fail("%s 沒打中" % point)
                # 全是手動回合，下一次 tick 前 keep 不會重開。
                fr = self.frame(node, job)
                p = fr["pending"]
                if point == "before-accept":
                    self.assertTrue(self.results(node, job, "a"))
                    self.assertNotIn("a", fr["accepted"])
                    self.assertEqual(fr["pc"], "a")
                else:
                    self.assertEqual(p["state"], "intent")
                    if point == "after-intent":
                        self.assertEqual(self.step_items(node), [])
                    else:
                        self.assertTrue(any(i["x"]["step"]["attempt"] == p["attempt"]
                                            for i in self.step_items(node))
                                        or aos7_step.attempt_of(self.birth(node, p["task"])) == p["attempt"])
                if point == "after-intent":
                    self.run_until(node, job, lambda: self.frame(node, job).get("phase") == "halted")
                    self.assertEqual(self.frame(node, job)["halt"]["kind"], "unknown")
                    self.assertEqual(self.ran(node, job + "-a"), [])
                    self.assertEqual(self.step_cli(node, "resume", "jobs/" + job, "--resend").returncode, 0)
                self.run_until(node, job, lambda: self.frame(node, job).get("phase") == "ended", msg=point)
                fr = self.frame(node, job)
                self.assertEqual(fr["end"], "ok", fr)
                self.assertEqual((len(self.ran(node, job + "-a")), len(self.ran(node, job + "-b"))), (1, 1), point)
                self.assertEqual(fr["visits"], {"a": 1, "b": 1, "done": 1})
                self.assertEqual(sorted(fr["tries"].values()), [1, 2] if point == "after-intent" else [1, 1])
                if point == "after-intent":
                    self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                self.assertFalse(os.path.exists(self.jd(node, job, ".step-crash")), "%s 沒打中" % point)
                self.reap_space()

    def test_once_slot_gone_result_carries_on(self):
        """直譯器停了好幾回合、子工作的 once 槽已被刪：重開後靠槽外結果繼續，不重派。"""
        node = self.setup_job("g", probe_table("g"))
        self.cycle(node, "g")                                    # 第 1 回合：直譯器派 a
        self.kill_interp(node, "g")
        self.set_enabled(node, "step-g", False)
        self.cycle(node, "g", wait=False)                        # 第 2 回合：tick 起 a
        self.wait_for(lambda: self.results(node, "g", "a"), 10, "a 沒結果")
        for _ in range(3):                                       # 報完再一回合，槽被刪
            self.cycle(node, "g", wait=False)
        self.assertFalse(os.path.exists(self.slot(node, "step-g-a")), "a 的槽還在，測不到")
        self.assertEqual(len(self.results(node, "g", "a")), 1)
        self.set_enabled(node, "step-g", True)
        self.run_until(node, "g", lambda: self.frame(node, "g").get("phase") == "ended")
        self.assertEqual((len(self.ran(node, "g-a")), len(self.ran(node, "g-b"))), (1, 1))

    def test_killed_after_artifact_before_result(self):
        """產物寫了、結果沒寫時 kill 子工作：停在 unknown（不誤報成功、不當沒做、不自動重送）。"""
        node = self.setup_job("u", probe_table("u", gate=True))
        open(self.jd(node, "u", "gate-a"), "w").close()
        self.run_until(node, "u", lambda: os.path.exists(self.jd(node, "u", "gate-a.entered")), msg="a 沒起")
        self.assertTrue(os.path.exists(self.jd(node, "u", "out", "a.txt")))
        aos7_ctl.task_ctl(self.slot(node, "step-u-a"), why="probe", run=self.birth(node, "step-u-a")["run"])
        self.run_until(node, "u", lambda: self.frame(node, "u").get("phase") == "halted", msg="沒停住")
        for _ in range(3):
            self.cycle(node, "u")
        fr = self.frame(node, "u")
        self.assertEqual(fr["halt"]["kind"], "unknown", fr)
        self.assertIn("沒有結果檔", fr["halt"]["why"])
        self.assertNotIn("a", fr["accepted"])
        self.assertEqual(self.results(node, "u", "a"), [])
        self.assertEqual(self.step_items(node), [])
        self.assertEqual(len(self.ran(node, "u-a")), 1)
        self.assertEqual(self.ran(node, "u-b"), [])
        # 人看過之後 resume --resend：同一個 request、新 attempt
        os.unlink(self.jd(node, "u", "gate-a"))
        r = self.step_cli(node, "resume", "jobs/u", "--resend")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.run_until(node, "u", lambda: self.frame(node, "u").get("phase") == "ended")
        acc = self.frame(node, "u")["accepted"]["a"]
        self.assertEqual((acc["request"].endswith("-a-1"), acc["attempt"].endswith("-a2")), (True, True), acc)

    def test_backup_rotate_unknown_not_retried(self):
        """備份：rotate（不冪等）轉完、結果寫出前被殺 → unknown 停住，不重送（只轉過一次）。"""
        node = self.mknode("a")
        item = self.install(node, "bk", example="backup")
        jd = self.jd(node, "bk")
        with open(os.path.join(jd, "rotate.sh"), "a") as f:
            f.write('touch "$2/../gate.entered"; while [ -e "$2/../gate" ]; do sleep 0.03; done\n')
        open(os.path.join(jd, "gate"), "w").close()
        self.set_tasks(node, [item])
        self.run_until(node, "bk", lambda: os.path.exists(os.path.join(jd, "gate.entered")), limit=15,
                       msg="rotate 沒起")
        slot = "step-backup-rotate"          # 槽名取表上的 job（backup），不是資料夾名
        aos7_ctl.task_ctl(self.slot(node, slot), why="probe", run=self.birth(node, slot)["run"])
        self.run_until(node, "bk", lambda: self.frame(node, "bk").get("phase") == "halted", msg="沒停住")
        for _ in range(3):
            self.cycle(node, "bk")
        fr = self.frame(node, "bk")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("unknown", "rotate"), fr)
        self.assertEqual(self.step_items(node), [])
        with open(os.path.join(jd, "archive", "rotations.log")) as f:
            self.assertEqual(f.read().split(), ["rotated"])        # 只轉過一次

    def test_backup_rotate_fail_not_retried(self):
        """備份：rotate 直接失敗 → 走 fail（結束 failed），不重試。"""
        node = self.mknode("a")
        item = self.install(node, "bf", example="backup")
        with open(self.jd(node, "bf", "rotate.sh"), "w") as f:
            f.write("exit 1\n")
        self.set_tasks(node, [item])
        self.run_until(node, "bf", lambda: self.frame(node, "bf").get("phase") == "ended", limit=15)
        fr = self.frame(node, "bf")
        self.assertEqual(fr["end"], "failed", fr)
        self.assertEqual(len(self.results(node, "bf", "rotate")), 1)
        self.assertEqual(fr["tries"][fr["accepted"]["rotate"]["request"]], 1)

    def test_idempotent_resend_keeps_request(self):
        """冪等步＋on_unknown: resend：被殺後自動重派一次，request 不變、attempt +1。"""
        node = self.setup_job("r", probe_table("r", a={"on_unknown": "resend"}, gate=True))
        open(self.jd(node, "r", "gate-a"), "w").close()
        self.run_until(node, "r", lambda: os.path.exists(self.jd(node, "r", "gate-a.entered")), msg="a 沒起")
        first = self.frame(node, "r")["pending"]
        aos7_ctl.task_ctl(self.slot(node, "step-r-a"), why="probe", run=self.birth(node, "step-r-a")["run"])
        self.run_until(node, "r", lambda: (self.frame(node, "r").get("pending") or {}).get("attempt", "").endswith("-a2"),
                       msg="沒重派")
        os.unlink(self.jd(node, "r", "gate-a"))
        self.run_until(node, "r", lambda: self.frame(node, "r").get("phase") == "ended")
        acc = self.frame(node, "r")["accepted"]["a"]
        self.assertEqual(acc["request"], first["request"])
        self.assertEqual(acc["attempt"], first["request"] + "-a2")
        self.assertEqual(len(self.ran(node, "r-a")), 2)

    def test_max_resends_two(self):
        """max_resends: 2：被殺兩次都自動重派（同 request、a2、a3），第三次 unknown 才停；共跑 3 次。"""
        node = self.setup_job("m", probe_table("m", a={"on_unknown": "resend", "max_resends": 2}, gate=True))
        open(self.jd(node, "m", "gate-a"), "w").close()
        req = None
        for k in (1, 2, 3):
            self.run_until(node, "m", lambda: len(self.ran(node, "m-a")) == k
                           and (self.birth(node, "step-m-a") or {}).get("run"), msg="a%d 沒起" % k)
            p = self.frame(node, "m")["pending"]
            req = req or p["request"]
            self.assertEqual((p["request"], p["attempt"]), (req, "%s-a%d" % (req, k)))
            self.wait_for(lambda: os.path.exists(self.jd(node, "m", "gate-a.entered")), 10, "a%d 沒進閘門" % k)
            os.unlink(self.jd(node, "m", "gate-a.entered"))
            aos7_ctl.task_ctl(self.slot(node, "step-m-a"), why="probe", run=self.birth(node, "step-m-a")["run"])
            if k < 3:
                self.run_until(node, "m", lambda: (self.frame(node, "m").get("pending") or {}).get("attempt")
                               == "%s-a%d" % (req, k + 1), msg="沒重派 a%d" % (k + 1))
        self.run_until(node, "m", lambda: self.frame(node, "m").get("phase") == "halted", msg="沒停住")
        fr = self.frame(node, "m")
        self.assertEqual((fr["halt"]["kind"], fr["tries"][req], len(self.ran(node, "m-a"))), ("unknown", 3, 3), fr)

    def test_unknown_codes_results(self):
        """A8-10(b)：退出碼列在 unknown_codes → on_unknown（同 request 新 attempt、受 max_resends 限、超額停 unknown）；
        不開時照舊 halted failed，resume --resend 同 request 派 a2。"""
        for mode in ("once", "always", "default"):
            with self.subTest(mode=mode):
                a = {"run": child("uc-a", "${out}/a.txt", code=3)}
                if mode != "default":
                    a.update(unknown_codes=[3], on_unknown="resend", max_resends=1)
                if mode == "default":
                    a["run"] = ["sh", "${job}/call.sh"]
                node = self.setup_job("uc", probe_table("uc", a=a))
                if mode == "default":
                    with open(self.jd(node, "uc", "call.sh"), "w") as f:
                        f.write("exit 3\n")
                if mode == "once":
                    # 腳本計次；第二次成功，仍用 child 記實際執行。
                    script = 'n=$(cat "$1/n" 2>/dev/null || echo 0); echo $((n+1)) > "$1/n"; c=3; [ "$n" -lt 1 ] || c=0; exec "$2" "$3" uc-a "$1/out/a.txt" - "$c"'
                    t = probe_table("uc", a=dict(a, run=["sh", "-c", script, "sh", "${job}", PY, CHILD]))
                    write_json(self.jd(node, "uc", "steps.json"), t)
                self.run_until(node, "uc", lambda: self.frame(node, "uc").get("phase") in ("halted", "ended"))
                fr = self.frame(node, "uc")
                req = aos7_step.request_of(fr, "a")
                if mode == "default":
                    self.assertEqual(fr["halt"]["kind"], "failed")
                    with open(self.jd(node, "uc", "call.sh"), "w") as f:
                        f.write('mkdir -p jobs/uc/out; touch jobs/uc/out/a.txt; exit 0\n')
                    self.assertEqual(self.step_cli(node, "resume", "jobs/uc", "--resend").returncode, 0)
                    self.run_until(node, "uc", lambda: self.frame(node, "uc").get("phase") == "ended")
                    acc = self.frame(node, "uc")["accepted"]["a"]
                    self.assertEqual((acc["request"], acc["attempt"]), (req, req + "-a2"))
                else:
                    self.assertEqual((fr["tries"][req], fr["resends"][req], len(self.results(node, "uc", "a"))),
                                     (2, 1, 2))
                    self.assertEqual(len(self.ran(node, "uc-a")), 2)
                    if mode == "once":
                        self.assertEqual(fr["end"], "ok")
                        self.assertEqual(fr["accepted"]["a"]["request"], req)
                        self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                    else:
                        self.assertEqual(fr["halt"]["kind"], "unknown")
                        self.assertNotIn("a", fr["accepted"])
                self.reap_space()

    def test_resend_budget_survives_bad_table(self):
        """R8-14：自動重送額度記在 request 層；重送那次被壞表拒寫後額度不重設，下一次 unknown 就停（共跑 2 次）；
        resume --resend 歸零。"""
        node = self.setup_job("rb", probe_table("rb", a={"on_unknown": "resend", "max_resends": 1}, gate=True))
        open(self.jd(node, "rb", "gate-a"), "w").close()
        self.run_until(node, "rb", lambda: os.path.exists(self.jd(node, "rb", "gate-a.entered")))
        req = self.frame(node, "rb")["pending"]["request"]
        good = self.tasks(node)
        os.killpg(self.wait_pid(node, "step-rb-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-rb-a")
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{bad")
        self.run_until(node, "rb", lambda: self.err(node, "rb").get("kind") == "bad"
                       and self.frame(node, "rb")["pending"] is None)
        self.assertEqual(self.frame(node, "rb")["resends"][req], 1)
        self.set_tasks(node, good)
        os.unlink(self.jd(node, "rb", "gate-a.entered"))
        self.run_until(node, "rb", lambda: os.path.exists(self.jd(node, "rb", "gate-a.entered")))
        self.assertTrue(self.frame(node, "rb")["pending"]["attempt"].endswith("-a3"))
        os.killpg(self.wait_pid(node, "step-rb-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-rb-a", self.birth(node, "step-rb-a")["run"])
        self.run_until(node, "rb", lambda: self.frame(node, "rb").get("phase") == "halted")
        self.assertEqual((self.frame(node, "rb")["halt"]["kind"], len(self.ran(node, "rb-a"))), ("unknown", 2))
        self.assertEqual(self.step_cli(node, "resume", "jobs/rb", "--resend").returncode, 0)
        self.assertNotIn(req, self.frame(node, "rb")["resends"])

    def test_bad_tasks_json_refused(self):
        """壞 tasks.json：直譯器拒寫（表原封不動）、撤掉意圖、記 error.json；修好後照常派、走完。"""
        node = self.setup_job("t", probe_table("t", gate=True))
        open(self.jd(node, "t", "gate-a"), "w").close()
        self.run_until(node, "t", lambda: os.path.exists(self.jd(node, "t", "gate-a.entered")), msg="a 沒起")
        os.unlink(self.jd(node, "t", "gate-a"))
        self.wait_for(lambda: self.results(node, "t", "a"), 10, "a 沒結果")
        good = self.tasks(node)
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{bad")
        rnd = self.cycle(node, "t")
        with open(os.path.join(node, ".aos", "tasks.json")) as f:
            self.assertEqual(f.read(), "{bad")
        fr, e = self.frame(node, "t"), self.err(node, "t")
        self.assertEqual((fr["pc"], fr["pending"]), ("b", None), fr)
        self.assertEqual((e["kind"], e["tock"]), ("bad", rnd), e)
        write_json(os.path.join(node, ".aos", "tasks.json"), {"tasks": good})
        self.run_until(node, "t", lambda: self.frame(node, "t").get("phase") == "ended")
        fr = self.frame(node, "t")
        self.assertTrue(fr["accepted"]["b"]["attempt"].endswith("-a2"), fr)    # 被拒那次算一個 attempt 號
        self.assertEqual(len(self.ran(node, "t-b")), 1)

    def test_broken_frame_and_changed_table(self):
        """框架壞掉：不前進、記錯、不從結果檔反推；工作進行中改了步驟表：停（version）。"""
        node = self.setup_job("f", probe_table("f"))
        self.cycle(node, "f")                                    # 派了 a
        path = self.jd(node, "f", "frame.json")
        with open(path, "w") as f:
            f.write("{")
        for _ in range(2):
            self.cycle(node, "f")
        self.wait_for(lambda: self.results(node, "f", "a"), 10, "a 沒結果")
        self.cycle(node, "f")
        with open(path) as f:
            self.assertEqual(f.read(), "{")
        self.assertEqual(self.err(node, "f")["kind"], "frame")
        self.assertEqual((self.step_items(node), self.ran(node, "f-b")), ([], []))
        node2 = self.setup_job("v", probe_table("v"))
        self.cycle(node2, "v")
        t = probe_table("v")
        t["note"] = "改過"
        write_json(self.jd(node2, "v", "steps.json"), t)
        self.cycle(node2, "v")
        self.assertEqual(self.frame(node2, "v")["halt"]["kind"], "version")

    def test_wait_timeout_and_receipt(self):
        """wait 耐性 2 回合到期 → 停（timeout，預設 unknown）；條件之後成立、resume 後照走。receipt 成立的 run 步不派。"""
        t = {"job": "w", "start": "a", "steps": {
            "a": {"run": child("w-a", "${out}/a.txt"), "finite": True, "receipt": {"exists": "${out}/a.txt"},
                  "ok": "w"},
            "w": {"wait": {"exists": "${job}/ack"}, "patience": 2, "then": "done"},
            "done": {"end": "ok"}}}
        node = self.setup_job("w", t)
        os.makedirs(self.jd(node, "w", "out"))
        open(self.jd(node, "w", "out", "a.txt"), "w").close()
        self.run_until(node, "w", lambda: self.frame(node, "w").get("phase") == "halted", msg="沒逾時")
        fr = self.frame(node, "w")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("timeout", "w"), fr)
        self.assertGreater(fr["halt"]["round"] - fr["since"], 2)
        self.assertTrue(fr["accepted"]["a"]["receipt"])
        self.assertEqual(self.ran(node, "w-a"), [])
        open(self.jd(node, "w", "ack"), "w").close()
        self.assertEqual(self.step_cli(node, "resume", "jobs/w").returncode, 0)
        self.run_until(node, "w", lambda: self.frame(node, "w").get("phase") == "ended")
        self.assertEqual(self.step_cli(node, "close", "jobs/w").returncode, 0)
        self.assertFalse(os.path.exists(self.jd(node, "w", "results")))
        self.assertTrue(self.frame(node, "w")["closed"])

    def test_start_wait_patience(self):
        """start 就是 wait（耐性 2）：建框架那圈就有耐性起點，條件不成立照 patience 停在 timeout（A4-03）。"""
        t = {"job": "sw", "start": "w", "steps": {
            "w": {"wait": {"exists": "${job}/never"}, "patience": 2, "then": "done"},
            "done": {"end": "ok"}}}
        node = self.setup_job("sw", t)
        self.run_until(node, "sw", lambda: self.frame(node, "sw").get("phase") == "halted", limit=8, msg="沒逾時")
        fr = self.frame(node, "sw")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("timeout", "w"), fr)
        self.assertIsNotNone(fr["since"])
        self.assertEqual(fr["halt"]["round"] - fr["since"], 3)


if __name__ == "__main__":
    unittest.main()
