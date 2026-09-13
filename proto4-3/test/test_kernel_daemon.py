"""aos-kernel：真的開 daemon 跑整條（tick 由 daemon 叫、cpu 掉了補回、換人不留空窗、syscall 單子）。"""

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
from _kernel_base import *   # noqa: F401,F403  （KernelTest、wait_until、各執行檔路徑、json／os／time…）
from _kernel_base import KernelTest
from aos_kernel_schedule import _one_cpu

class KernelDaemonTest(KernelTest):
    """真的開 daemon 的那幾條。"""

    def cpus_on_daemon(self, ncpu):
        return all(self.cpu_key(n) in self.table() for n in range(ncpu))

    def test_boot_adds_the_kernel_with_configured_run_flags(self):
        self.spawn_daemon()
        self.init(1, interval_ms=73, timeout_ms=456)
        r = self.kernel_boot(self.k, "--home", self.home.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ok=", r.stdout)
        key = os.path.realpath(self.at("inst.json"))
        self.assertTrue(wait_until(lambda: key in self.table()), self.table())
        self.assertEqual(self.table()[key]["args"],
                         ["--interval-ms", "73", "--timeout-ms", "456"])

    def test_rm_proc_on_cpu_idles_it_without_leaving_a_done_proc(self):
        self.spawn_daemon()
        self.init(1, interval_ms=40, quantum=100)
        self.assertEqual(self.kernel_boot(self.k).returncode, 0)
        inst = self.write_inst("stay.json", {"argv": ["true"], "cwd": self.tmp})
        self.assertEqual(self.kernel("add", self.k, inst, "--name", "stay").returncode, 0)
        self.assertTrue(wait_until(lambda: self.on_cpus().get("0") == "stay"), self.kstate())
        r = self.kernel("rm", self.k, "stay")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("原本在 cpu0", r.stdout)
        self.assertTrue(wait_until(lambda: self.kstate()["cpus"]["0"] is None))
        with open(self.at("cpus", "0.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), IDLE_INST)
        self.assertFalse(os.path.exists(self.at("procs", "done", "stay.json")))

    def test_rm_missing_proc_returns_the_negative_kernel_reply(self):
        self.spawn_daemon()
        self.init(1, interval_ms=40)
        self.put_syscall("1-rm-nobody.json", {"op": "rm", "pid": "nobody"})
        h = KHome(self.k)
        handle_syscalls(h, h.config(), h.state(), [])
        reply = os.path.join(h.syscalls_done, "1-rm-nobody.json")
        with open(reply, encoding="utf-8") as f:
            self.assertFalse(json.load(f)["ok"])
        os.unlink(reply)
        self.assertEqual(self.kernel_boot(self.k).returncode, 0)
        r = self.kernel("rm", self.k, "nobody-either")
        self.assertEqual(r.returncode, 1)
        self.assertIn("找不到這個行程：nobody-either", r.stdout)

    def test_two_observations_of_aos_125_move_the_proc_to_bad(self):
        self.spawn_daemon()
        self.init(1, interval_ms=40, quantum=100)
        self.assertEqual(self.kernel_boot(self.k).returncode, 0)
        inst = self.write_inst("fails.json", {"argv": ["true"], "cwd": self.tmp,
                                               "stdout": "missing/out.txt"})
        self.assertEqual(self.kernel("add", self.k, inst, "--name", "fails").returncode, 0)
        bad = self.at("procs", "bad", "fails.json")
        self.assertTrue(wait_until(lambda: os.path.exists(bad)), self.table())
        self.assertTrue(wait_until(lambda: self.kstate()["cpus"]["0"] is None))
        with open(self.at("cpus", "0.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), IDLE_INST)
        with open(self.at("kernel.log"), encoding="utf-8") as f:
            self.assertIn("連續回 125", f.read())

    def test_boot_is_harmless_when_the_kernel_is_already_running(self):
        self.spawn_daemon()
        self.init(1, interval_ms=80)
        first = self.kernel_boot(self.k)
        self.assertEqual(first.returncode, 0, first.stderr)
        key = os.path.realpath(self.at("inst.json"))
        self.assertTrue(wait_until(lambda: key in self.table()), self.table())
        pid = self.table()[key]["pid"]
        again = self.kernel_boot(self.k)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("已經在跑", again.stdout)
        self.assertEqual(self.table()[key]["pid"], pid)

    def test_done_exit_moves_the_proc_to_done_and_idles_the_cpu(self):
        self.spawn_daemon()
        self.init(1, interval_ms=50, quantum=100)
        boot = self.kernel_boot(self.k)
        self.assertEqual(boot.returncode, 0, boot.stderr)
        inst = self.write_inst("finish.json", {"argv": ["sh", "-c", "exit 100"],
                                                "cwd": self.tmp, "stderr": "err.txt"})
        add = self.kernel("add", self.k, inst, "--name", "7")
        self.assertEqual(add.returncode, 0, add.stderr)
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)), self.table())
        self.assertTrue(wait_until(lambda: os.path.exists(self.at("procs", "done", "7.json"))),
                        self.table())
        self.assertFalse(os.path.exists(self.at("procs", "7.json")))
        self.assertIsNone(self.kstate()["cpus"]["0"])
        with open(self.at("cpus", "0.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), IDLE_INST)
        self.assertIn("done: 7", self.kernel("ls", cwd=self.k).stdout)

    def test_a_previous_exit_cannot_finish_the_new_proc(self):
        self.init(1, quantum=100)
        h = KHome(self.k)
        self.put_proc("5", body={"argv": ["true"], "cwd": self.tmp})
        os.replace(h.proc("5"), h.cpu(0))
        st = {"cpus": {"0": {"pid": "5", "since": 1, "runs_at": 10}}, "queue": []}
        notes = []
        _one_cpu(h, h.config(), st, [], notes, 2, 0,
                 {0: {"runs": 11, "last_kind": "child", "last_exit": 100}})
        self.assertEqual(st["cpus"]["0"]["pid"], "5")
        self.assertFalse(os.path.exists(h.proc_done("5")))
        with open(h.cpu(0), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["argv"], ["true"])

    def test_ls_hides_previous_exit_when_new_proc_has_zero_runs(self):
        self.init(1, quantum=100)
        h = KHome(self.k)
        self.put_proc("old")
        os.replace(h.proc("old"), h.cpu(0))
        st = {"cpus": {"0": {"pid": "old", "since": 1, "runs_at": 0,
                                "seen_runs": 0}}, "queue": [], "waiting": {}}
        self.put_proc("new")
        ent = {"runs": 2, "last_kind": "child", "last_exit": 100,
               "state": "running"}
        _one_cpu(h, h.config(), st, ["new"], [], 2, 0, {0: ent})
        queue = ["new"]
        _one_cpu(h, h.config(), st, queue, [], 3, 0, {0: ent})
        h.save(st)
        self.home.ensure()
        with open(self.home.statef, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "runs": {self.cpu_key(0): ent}}, f)
        row = next(line for line in self.kernel("ls", self.k).stdout.splitlines()
                   if line.startswith("0 "))
        self.assertIn("new", row)
        self.assertRegex(row, r"\s0\s+-\s+")

    def test_done_exit_zero_disables_finishing(self):
        self.spawn_daemon()
        self.init(1, interval_ms=50, quantum=100, done_exit=0)
        self.put_proc("7", body={"argv": ["sh", "-c", "exit 100"], "cwd": self.tmp})
        self.tick()
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)), self.table())
        self.tick()
        runs_at = self.kstate()["cpus"]["0"]["runs_at"]
        self.assertTrue(wait_until(
            lambda: self.table()[self.cpu_key(0)]["runs"] - runs_at >= 2), self.table())
        self.tick()
        self.assertEqual(self.on_cpus()["0"], "7")
        self.assertFalse(os.path.exists(self.at("procs", "done", "7.json")))

    def test_the_first_tick_plugs_the_cpus_into_the_daemon(self):
        self.spawn_daemon()
        self.init(2, interval_ms=100)
        self.tick()
        for n in range(2):
            with open(self.at("cpus", "%d.json" % n), encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"argv": ["true"], "cwd": "."})
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(2)), self.table())
        for n in range(2):
            self.assertEqual(self.table()[self.cpu_key(n)]["args"],
                             ["--interval-ms", "100"])
        self.tick()                                   # 已經在表上了＝不再 add
        self.assertEqual(len(self.table()), 2)
        with open(self.at("kernel.log"), encoding="utf-8") as f:
            self.assertIn("cpu0 插上 daemon 成功", f.read())

    def test_three_procs_take_turns_on_two_cpus(self):
        self.spawn_daemon()
        self.init(2, interval_ms=100, quantum=2)
        logs = [self.put_proc(p) for p in ("3", "5", "7")]
        self.tick()
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(2)))
        seen = set()
        t0 = time.monotonic()
        while time.monotonic() - t0 < 12:
            self.tick()
            seen.add(tuple(sorted(self.on_cpus().items())))
            if len(seen) > 1 and all(os.path.exists(p) for p in logs):
                break
            time.sleep(0.15)
        for p in logs:                                # 三個都真的跑過
            self.assertTrue(os.path.exists(p), p)
            with open(p) as f:
                self.assertTrue(f.read().strip())
        self.assertGreater(len(seen), 1)              # cpu 上的人換過
        self.assertEqual(len(set(self.on_cpus().values())), 2)   # 兩顆 cpu 上不是同一位
        self.assertEqual(len(self.kstate()["queue"]), 1)         # 一個在等

    def test_a_swap_never_leaves_the_cpu_file_missing(self):
        self.spawn_daemon()
        self.init(1, interval_ms=100, quantum=1)
        self.put_proc("3")
        self.put_proc("5")
        self.tick()
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)))
        first, swapped = None, False
        t0 = time.monotonic()
        while time.monotonic() - t0 < 10:
            self.assertTrue(os.path.exists(self.at("cpus", "0.json")))   # 換人前
            self.tick()
            self.assertTrue(os.path.exists(self.at("cpus", "0.json")))   # 換人後
            now = self.on_cpus()["0"]
            first = first or now
            if now != first:
                swapped = True
                break
            time.sleep(0.15)
        self.assertTrue(swapped, "quantum 到了卻沒換人")
        back = self.at("procs", "%s.json" % first)
        self.assertTrue(os.path.exists(back))         # 舊的回到 procs/
        self.assertEqual(self.kstate()["queue"], [first])
        with open(back, encoding="utf-8") as f:       # 內容還是它自己的
            self.assertIn("p%s" % first, json.load(f)["cwd"])

    def test_a_cpu_that_was_removed_comes_back_next_tick(self):
        self.spawn_daemon()
        self.init(1, interval_ms=100)
        self.put_proc("3")
        self.tick()
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)))
        self.tick()
        self.assertEqual(self.on_cpus()["0"], "3")
        r = self.ctl("rm", self.at("cpus", "0.json"))            # 拔掉那顆 cpu
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(self.cpu_key(0), self.table())
        self.tick()                                              # 下一回合補回去
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)), self.table())
        self.assertEqual(self.on_cpus()["0"], "3")               # 上面那位沒被踢掉

    def test_the_daemon_runs_the_kernel_itself(self):
        """開機順序：daemon → init → ctl add K/inst.json，之後不用人手動 tick。"""
        self.spawn_daemon()
        self.init(1, interval_ms=100)
        self.put_proc("3")
        r = self.ctl("add", self.at("inst.json"), "--interval-ms", "200")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(wait_until(lambda: self.cpus_on_daemon(1)), self.table())
        self.assertTrue(wait_until(lambda: self.on_cpus().get("0") == "3"), self.kstate())
        log = os.path.join(self.tmp, "p3", "log.txt")
        self.assertTrue(wait_until(lambda: os.path.exists(log)))  # 行程真的被 cpu 跑起來了
        with open(self.at("kernel.log"), encoding="utf-8") as f:
            self.assertGreater(len(f.read().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
