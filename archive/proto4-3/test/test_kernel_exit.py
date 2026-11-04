"""aos-kernel：退出碼政策——done_exit 收工、wait_exit 標 waiting 與讓 cpu、bad_after 退件、125 連兩次退件。"""

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
from _kernel_base import *   # noqa: F401,F403  （KernelTest、wait_until、各執行檔路徑、json／os／time…）
from _kernel_base import KernelTest
from aos_kernel_schedule import _one_cpu
from aos_kernel_schedule import _observe_exit

class KernelExitPolicyTest(KernelTest):
    def put_on_cpu(self, pid):
        h = KHome(self.k)
        self.put_proc(pid)
        os.replace(h.proc(pid), h.cpu(0))
        return h, {"cpus": {"0": {"pid": pid, "since": 1, "runs_at": 0,
                                     "seen_runs": 0}},
                   "queue": [], "waiting": {}}

    def test_wait_exit_stays_on_an_empty_cpu_and_ls_says_waiting(self):
        self.init(1)
        h, st = self.put_on_cpu("waiter")
        ent = {"runs": 1, "last_kind": "child", "last_exit": 101, "state": "running"}
        _one_cpu(h, h.config(), st, [], [], 2, 0, {0: ent})
        ent["runs"] = 2
        _one_cpu(h, h.config(), st, [], [], 3, 0, {0: ent})
        self.assertEqual(st["cpus"]["0"]["waiting"], True)
        self.assertEqual(st["cpus"]["0"]["wait_runs"], 2)
        self.assertEqual(st["cpus"]["0"]["pid"], "waiter")
        h.save(st)
        self.home.ensure()
        with open(self.home.statef, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "runs": {self.cpu_key(0): ent}}, f)
        out = self.kernel("ls", self.k).stdout
        self.assertIn("waiting", out)
        self.assertIn("等了 2 回合", out)

    def test_waiting_proc_yields_when_someone_is_queued(self):
        self.init(1, quantum=100)
        h, st = self.put_on_cpu("waiter")
        ent = {0: {"runs": 1, "last_kind": "child", "last_exit": 101}}
        _one_cpu(h, h.config(), st, [], [], 2, 0, ent)
        self.assertEqual(st["cpus"]["0"]["pid"], "waiter")
        self.put_proc("next")
        queue, notes = ["next"], []
        _one_cpu(h, h.config(), st, queue, notes, 3, 0, ent)
        self.assertEqual(st["cpus"]["0"]["pid"], "next")
        self.assertEqual(queue, ["waiter"])
        self.assertEqual(st["waiting"], {"waiter": 1})
        self.assertTrue(os.path.exists(h.proc("waiter")))
        st["queue"] = queue
        h.save(st)
        out = self.kernel("ls", self.k).stdout
        self.assertIn("waiter (waiting，等了 1 回合)", out)

    def test_bad_after_moves_repeated_nonzero_exit_to_bad_with_reason(self):
        self.init(1, quantum=100, bad_after=3)
        h, st = self.put_on_cpu("broken")
        notes = []
        for runs in range(1, 4):
            _one_cpu(h, h.config(), st, [], notes, 2, 0,
                     {0: {"runs": runs, "last_kind": "child", "last_exit": 3}})
        self.assertIsNone(st["cpus"]["0"])
        self.assertTrue(os.path.exists(os.path.join(h.bad, "broken.json")))
        self.assertIn("連續 3 次退 3", notes[-1])
        h.save(st)
        h.log(notes[-1])
        self.assertIn("連續 3 次退 3", self.kernel("ls", self.k).stdout)

    def test_bad_after_zero_keeps_retrying_forever(self):
        self.init(1, quantum=100, bad_after=0)
        h, st = self.put_on_cpu("broken")
        _one_cpu(h, h.config(), st, [], [], 2, 0,
                 {0: {"runs": 50, "last_kind": "child", "last_exit": 3}})
        self.assertEqual(st["cpus"]["0"]["pid"], "broken")
        self.assertFalse(os.path.exists(os.path.join(h.bad, "broken.json")))

    def test_a_new_aos_run_resets_exit_streaks(self):
        self.init(1, quantum=100, bad_after=3)
        h, st = self.put_on_cpu("broken")
        st["cpus"]["0"].update({"seen_runs": 5, "bad_runs": 2, "bad_exit": 3})
        _one_cpu(h, h.config(), st, [], [], 2, 0,
                 {0: {"runs": 0, "last_kind": "child", "last_exit": 3}})
        self.assertNotIn("bad_runs", st["cpus"]["0"])

    def test_special_exit_codes_break_the_bad_run(self):
        cfg = {"done_exit": 100, "wait_exit": 101}
        for special in (101, 100, 125):
            cur = {}
            _observe_exit(cfg, cur, {"last_kind": "child", "last_exit": 3}, 1)
            self.assertEqual(cur["bad_runs"], 1)
            _observe_exit(cfg, cur, {"last_kind": "child", "last_exit": special}, 1)
            self.assertNotIn("bad_runs", cur)
        cur = {"waiting": True, "wait_runs": 7}
        _observe_exit(cfg, cur, {"last_kind": "child", "last_exit": 0}, 1)
        self.assertNotIn("waiting", cur)

    def test_ls_only_says_dead_when_a_known_daemon_pid_is_dead(self):
        self.init(1)
        self.home.ensure()
        with open(self.home.statef, "w", encoding="utf-8") as f:
            json.dump({"pid": 999999999, "runs": {}}, f)
        self.assertIn("daemon dead", self.kernel("ls", self.k).stdout)
