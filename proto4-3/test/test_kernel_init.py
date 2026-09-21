"""aos-kernel：init 建家、boot 上 daemon、add／rm／ls 給人用的那幾支（不真開 daemon 的部分）。"""

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
from _kernel_base import *   # noqa: F401,F403  （KernelTest、wait_until、各執行檔路徑、json／os／time…）
from _kernel_base import KernelTest

class KernelInitTest(KernelTest):
    def test_boot_refuses_a_home_that_was_not_initialized(self):
        r = self.kernel_boot(self.k, "--home", self.home.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-kernel-init", r.stderr)

    def test_boot_refuses_when_the_daemon_is_not_running(self):
        self.init(1)
        r = self.kernel_boot(self.k)
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-daemon", r.stderr)

    def test_init_builds_the_home_and_the_kernel_inst(self):
        r = self.init(2, interval_ms=100, timeout_ms=500, quantum=3)
        self.assertIn(self.k, r.stdout)
        for rel in ("procs", os.path.join("procs", "bad"),
                    os.path.join("procs", "done"), "cpus", "syscalls",
                    os.path.join("syscalls", "done")):
            self.assertTrue(os.path.isdir(self.at(rel)), rel)
        for rel in ("inst.json", "config.json", "state.json", "kernel.log"):
            self.assertTrue(os.path.exists(self.at(rel)), rel)
        with open(self.at("inst.json"), encoding="utf-8") as f:
            inst = json.load(f)
        self.assertEqual(inst, {"argv": [TICK_BIN], "cwd": "."})
        with open(self.at("config.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"ncpu": 2, "interval_ms": 100,
                                            "timeout_ms": 500, "quantum": 3,
                                            "done_exit": 100, "wait_exit": 101,
                                            "bad_after": 10, "modules": []})
        self.assertEqual(self.kstate(), {"cpus": {"0": None, "1": None}, "queue": [],
                                         "waiting": {}})
        self.assertIn("aos-kernel-boot %s" % self.k, r.stdout)
        self.assertIn("aos-kernel add %s" % self.k, r.stdout)
        self.assertIn("aos-kernel rm %s" % self.k, r.stdout)

    def test_init_refuses_a_dir_that_is_already_there(self):
        self.init(1)
        r = self.kernel_init(self.k, "--ncpu", 1)
        self.assertEqual((r.returncode, "已經有這個資料夾" in r.stderr), (1, True), r.stderr)
        self.assertIn("module 要在 init 時就 --module 掛", r.stderr)

    def test_old_config_gets_waiting_and_bad_defaults(self):
        self.init(1)
        with open(self.at("config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.pop("wait_exit")
        cfg.pop("bad_after")
        with open(self.at("config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        loaded = KHome(self.k).config()
        self.assertEqual((loaded["wait_exit"], loaded["bad_after"]), (101, 10))

    def test_init_accepts_wait_exit_and_bad_after(self):
        self.init(1, wait_exit=77, bad_after=4)
        cfg = KHome(self.k).config()
        self.assertEqual((cfg["wait_exit"], cfg["bad_after"]), (77, 4))
        bad = self.kernel_init(os.path.join(self.tmp, "bad-k"), "--ncpu", 1,
                               "--bad-after", -1)
        self.assertEqual(bad.returncode, 2)

    def test_kernel_init_subcommand_is_gone(self):
        """init 拆成獨立指令 aos-kernel-init 之後，aos-kernel init 要退出碼 2、提示改路。"""
        r = self.kernel("init", self.k, "--ncpu", 1)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("aos-kernel-init", r.stderr)
        self.assertFalse(os.path.exists(self.k))

    def test_kernel_tick_subcommand_is_gone(self):
        """tick 拆成獨立指令 aos-kernel-tick 之後，aos-kernel tick 要退出碼 2、提示改路。"""
        self.init(1)
        r = self.kernel("tick", cwd=self.k)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("aos-kernel-tick", r.stderr)

    def test_tick_and_ls_need_to_be_in_a_home(self):
        r = self.kernel_tick(cwd=self.tmp)
        self.assertEqual((r.returncode, "aos-kernel-init" in r.stderr), (1, True), r.stderr)
        self.assertEqual(self.kernel("ls", cwd=self.tmp).returncode, 1)
        unknown = self.kernel("nope")
        self.assertEqual(unknown.returncode, 1)
        self.assertIn("aos-kernel-init", unknown.stderr)
        self.assertEqual(self.kernel().returncode, 2)

    def test_a_proc_without_cwd_is_sent_to_bad(self):
        """§17.1：cwd 這道檢查只在 kernel 做。daemon 沒起來也照檢查、照退出 0。"""
        self.init(1)
        good = self.put_proc("3")
        self.put_proc("5", cwd=False)                       # 沒寫 cwd
        self.put_proc("7", body={"cwd": "/tmp"})            # 沒有 argv
        self.put_proc("9", body="{壞掉的 JSON")              # 不是 JSON
        self.put_proc("11", body=[1, 2])                    # 不是物件
        self.put_proc("13", body={"argv": ["true"], "cwd": 7})   # cwd 不是字串
        self.tick()
        self.assertEqual(sorted(os.listdir(self.at("procs", "bad"))),
                         ["11.json", "13.json", "5.json", "7.json", "9.json"])
        self.assertEqual([n for n in os.listdir(self.at("procs")) if n.endswith(".json")],
                         ["3.json"])
        self.assertEqual(self.kstate()["queue"], ["3"])     # 好的那個在排隊
        self.assertFalse(os.path.exists(good))              # daemon 沒起來＝沒人跑它
        with open(self.at("kernel.log"), encoding="utf-8") as f:
            self.assertIn("退件 5.json（沒寫 cwd）", f.read())

    def test_ls_prints_the_cpus_and_the_queue(self):
        self.init(2)
        self.put_proc("3")
        self.tick()
        out = self.kernel("ls", cwd=self.k).stdout
        self.assertIn("ncpu=2", out)
        self.assertIn("CPU  PROC", out)
        self.assertIn("LAST_EXIT", out)
        self.assertIn("沒插上", out)                        # daemon 沒起來
        self.assertIn("佇列（1 個）：3", out)

    def test_ls_without_daemon_home_says_the_home_is_unknown(self):
        self.init(1)
        env = dict(os.environ)
        env.pop("AOS_DAEMON_HOME", None)
        r = subprocess.run([sys.executable, KERNEL_BIN, "ls", self.k], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("找不到 daemon 的家（AOS_DAEMON_HOME 沒設？）", r.stdout)

    def test_ls_accepts_the_home_from_another_directory(self):
        self.init(1)
        from_home = self.kernel("ls", cwd=self.k)
        by_dir = self.kernel("ls", self.k, cwd=self.tmp)
        self.assertEqual(by_dir.returncode, 0, by_dir.stderr)
        self.assertEqual(by_dir.stdout, from_home.stdout)

    def test_ls_prints_bad_count_and_latest_reason(self):
        self.init(1)
        self.put_proc("5", cwd=False)
        self.tick()
        out = self.kernel("ls", self.k, cwd=self.tmp).stdout
        self.assertIn("bad: 1", out)
        self.assertIn("退件 5.json（沒寫 cwd）", out)

    def test_add_makes_relative_cwd_and_argv0_absolute(self):
        self.init(1)
        work = os.path.join(self.tmp, "src", "work")
        os.makedirs(os.path.join(work, "bin"))
        program = os.path.join(work, "bin", "task")
        with open(program, "w", encoding="utf-8") as f:
            f.write("not run in this test")
        inst = self.write_inst("src/job.json", {"argv": ["bin/task"], "cwd": "work",
                                                 "stderr": "err.txt"})
        r = self.kernel("add", self.k, inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.at("procs", "1.json"), encoding="utf-8") as f:
            queued = json.load(f)
        self.assertEqual(queued["cwd"], work)
        self.assertEqual(queued["argv"][0], program)

    def test_add_without_cwd_uses_the_inst_directory(self):
        self.init(1)
        inst = self.write_inst("jobs/job.json", {"argv": ["sh"], "stderr": "err.txt"})
        r = self.kernel("add", inst, cwd=self.k)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.at("procs", "1.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["cwd"], os.path.dirname(inst))

    def test_add_auto_number_skips_bad_and_done(self):
        self.init(1)
        self.write_inst(os.path.join("k", "procs", "done", "3.json"), {})
        self.write_inst(os.path.join("k", "procs", "bad", "5.json"), {})
        inst = self.write_inst("job.json", {"argv": ["true"], "stderr": "err.txt"})
        r = self.kernel("add", self.k, inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.at("procs", "6.json")))

    def test_add_named_proc_and_rejects_the_same_name(self):
        self.init(1)
        inst = self.write_inst("job.json", {"argv": ["true"], "stderr": "err.txt"})
        first = self.kernel("add", self.k, inst, "--name", "foo")
        again = self.kernel("add", self.k, inst, "--name", "foo")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(os.path.isfile(self.at("procs", "foo.json")))
        self.assertEqual(again.returncode, 1)

    def test_add_rejects_a_missing_cwd_without_queuing(self):
        self.init(1)
        inst = self.write_inst("job.json", {"argv": ["true"], "cwd": "missing",
                                             "stderr": "err.txt"})
        r = self.kernel("add", self.k, inst)
        self.assertEqual(r.returncode, 1)
        self.assertIn(os.path.join(self.tmp, "missing"), r.stderr)
        self.assertEqual([n for n in os.listdir(self.at("procs")) if n.endswith(".json")], [])

    def test_add_warns_when_stderr_is_missing(self):
        self.init(1)
        inst = self.write_inst("job.json", {"argv": ["true"]})
        r = self.kernel("add", self.k, inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("沒寫 stderr", r.stderr)

    def test_add_accepts_relative_kernel_and_inst_from_another_directory(self):
        self.init(1)
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        self.write_inst("other/x.json", {"argv": ["true"], "stderr": "err.txt"})
        r = self.kernel("add", os.path.relpath(self.k, other), "x.json", cwd=other)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.at("procs", "1.json")))

    def test_rm_queued_proc_is_handled_without_a_daemon(self):
        self.init(1)
        self.put_proc("queued")
        self.put_syscall("1-rm-queued.json", {"op": "rm", "pid": "queued"})
        h = KHome(self.k)
        st, notes = h.state(), []
        handle_syscalls(h, h.config(), st, notes)
        self.assertFalse(os.path.exists(h.proc("queued")))
        with open(os.path.join(h.syscalls_done, "1-rm-queued.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"ok": True, "msg": "rm queued（原本在佇列）"})
        self.assertIn("rm queued（原本在佇列）", notes)

    def test_unknown_syscall_gets_a_negative_reply(self):
        self.init(1)
        self.put_syscall("1-wat.json", {"op": "wat"})
        h = KHome(self.k)
        handle_syscalls(h, h.config(), h.state(), [])
        with open(os.path.join(h.syscalls_done, "1-wat.json"), encoding="utf-8") as f:
            out = json.load(f)
        self.assertFalse(out["ok"])
        self.assertIn("看不懂這張單", out["msg"])
        self.assertFalse(os.path.exists(os.path.join(h.syscalls, "1-wat.json")))

    def test_add_rejects_a_bad_inst_field_without_queuing(self):
        """add 只做幾個表面檢查，剩下的交給 aos-exec 的完整規則：型別錯就不排。"""
        self.init(1)
        inst = self.write_inst("job.json", {"argv": ["true"], "envs": {"A": 1}})
        r = self.kernel("add", self.k, inst)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FieldTypeMismatch", r.stderr)
        self.assertEqual([n for n in os.listdir(self.at("procs")) if n.endswith(".json")], [])

    def test_manually_queued_bad_field_goes_to_bad_with_exact_validator_error(self):
        self.init(1)
        self.put_proc("badfield", {"argv": ["true"], "cwd": self.tmp,
                                   "envs": {"A": 1}})
        self.tick()
        self.assertTrue(os.path.exists(self.at("procs", "bad", "badfield.json")))
        with open(self.at("kernel.log"), encoding="utf-8") as f:
            log = f.read()
        self.assertIn("FieldTypeMismatch", log)
        self.assertIn("要是字串", log)

    def test_ls_of_a_missing_home_points_to_kernel_init(self):
        missing = os.path.join(self.tmp, "missing")
        results = (self.kernel("ls", missing),
                   self.kernel("add", missing, "job.json"),
                   self.kernel("rm", missing, "nobody"))
        for r in results:
            self.assertEqual(r.returncode, 1)
            self.assertIn("aos-kernel-init", r.stderr)
