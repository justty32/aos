"""aos-kernel：真的開一支 aos-daemon（家在 /tmp、走 `AOS_DAEMON_HOME`）＋真的跑
aos-kernel-init／aos-kernel-tick／aos-kernel（現在只剩 ls）。

`aos-kernel-init` 建家、`aos-kernel-tick` 把 N 顆 cpu 插上 daemon、三個行程在兩顆 cpu 上
輪流、沒寫 cwd 的退件、cpu 被 `ctl rm` 掉下一回合補回、換人時 `cpus/n.json` 不留空窗、
kernel 被 daemon 自己跑（走的就是 `aos-kernel-init` 寫進 `inst.json` 的 `aos-kernel-tick`）。
每條測試跑完 kill daemon、刪家，不留孤兒。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import _util           # noqa: F401  （它把 proto4-3 放進 sys.path）
from aos_home import Home, alive
from aos_kernel import IDLE_INST, KHome
from aos_kernel_tick import _one_cpu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KERNEL_BIN = os.path.join(ROOT, "aos-kernel")
INIT_BIN = os.path.join(ROOT, "aos-kernel-init")
BOOT_BIN = os.path.join(ROOT, "aos-kernel-boot")
TICK_BIN = os.path.join(ROOT, "aos-kernel-tick")
DAEMON_BIN = os.path.join(ROOT, "aos-daemon")
CTL_BIN = os.path.join(ROOT, "aos-daemon-ctl")


def wait_until(cond, secs=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-proto4-3-kernel-")
        self.addCleanup(self.cleanup)
        self.home = Home(os.path.join(self.tmp, "dhome"))
        self.env = dict(os.environ, AOS_DAEMON_HOME=self.home.dir)
        self.k = os.path.join(self.tmp, "k")
        self.proc = None

    # ---- 開關機 ----
    def spawn_daemon(self):
        self.home.ensure()
        log = open(os.path.join(self.tmp, "daemon.out"), "ab")
        self.addCleanup(log.close)
        self.proc = subprocess.Popen([sys.executable, DAEMON_BIN], env=self.env,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     start_new_session=True, cwd=self.home.dir)
        self.assertTrue(wait_until(lambda: self.home.alive()))

    def cleanup(self):
        pid = self.home.pid()
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except OSError:
                    pass
        if pid and alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 叫程式 ----
    def kernel(self, *args, cwd=None):
        return subprocess.run([sys.executable, KERNEL_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=60)
    def ctl(self, *args):
        return subprocess.run([sys.executable, CTL_BIN] + [str(a) for a in args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def kernel_init(self, *args):
        return subprocess.run([sys.executable, INIT_BIN] + [str(a) for a in args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def kernel_tick(self, *args, cwd=None):
        return subprocess.run([sys.executable, TICK_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=60)

    def kernel_boot(self, *args, cwd=None):
        return subprocess.run([sys.executable, BOOT_BIN] + [str(a) for a in args],
                              env=self.env, cwd=cwd, capture_output=True, text=True,
                              timeout=30)

    def init(self, ncpu=2, **kw):
        args = [self.k, "--ncpu", ncpu]
        for flag, v in kw.items():
            args += ["--" + flag.replace("_", "-"), v]
        r = self.kernel_init(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def tick(self):
        r = self.kernel_tick(cwd=self.k)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    # ---- 看東西 ----
    def at(self, *rel):
        return os.path.join(self.k, *rel)

    def table(self):
        return (self.home.state() or {}).get("runs", {})

    def cpu_key(self, n):
        return os.path.realpath(self.at("cpus", "%d.json" % n))

    def kstate(self):
        with open(self.at("state.json"), encoding="utf-8") as f:
            return json.load(f)

    def on_cpus(self):
        cpus = self.kstate()["cpus"]
        return {n: (c or {}).get("pid") for n, c in cpus.items()}

    def put_proc(self, pid, body=None, cwd=True):
        """寫一個等著上 cpu 的行程：它每跑一次就往自己 cwd 的 log.txt 加一行。"""
        d = os.path.join(self.tmp, "p%s" % pid)
        os.makedirs(d, exist_ok=True)
        if body is None:
            body = {"argv": ["sh", "-c", "echo hi >> log.txt"]}
            if cwd:
                body["cwd"] = d
        with open(self.at("procs", "%s.json" % pid), "w", encoding="utf-8") as f:
            f.write(body if isinstance(body, str) else json.dumps(body))
        return os.path.join(d, "log.txt")

    def write_inst(self, rel, body):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        return path


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
                    os.path.join("procs", "done"), "cpus"):
            self.assertTrue(os.path.isdir(self.at(rel)), rel)
        for rel in ("inst.json", "config.json", "state.json", "kernel.log"):
            self.assertTrue(os.path.exists(self.at(rel)), rel)
        with open(self.at("inst.json"), encoding="utf-8") as f:
            inst = json.load(f)
        self.assertEqual(inst, {"argv": [TICK_BIN], "cwd": "."})
        with open(self.at("config.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"ncpu": 2, "interval_ms": 100,
                                            "timeout_ms": 500, "quantum": 3,
                                            "done_exit": 100})
        self.assertEqual(self.kstate(), {"cpus": {"0": None, "1": None}, "queue": []})
        self.assertIn("aos-kernel-boot %s" % self.k, r.stdout)
        self.assertIn("aos-kernel add %s" % self.k, r.stdout)

    def test_init_refuses_a_dir_that_is_already_there(self):
        self.init(1)
        r = self.kernel_init(self.k, "--ncpu", 1)
        self.assertEqual((r.returncode, "已經有這個資料夾" in r.stderr), (1, True), r.stderr)

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
        self.assertEqual((r.returncode, "config.json" in r.stderr), (1, True), r.stderr)
        self.assertEqual(self.kernel("ls", cwd=self.tmp).returncode, 1)
        self.assertEqual(self.kernel("nope").returncode, 2)
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
        self.assertIn("CPU  PID", out)
        self.assertIn("沒插上", out)                        # daemon 沒起來
        self.assertIn("佇列（1 個）：3", out)

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


class KernelDaemonTest(KernelTest):
    """真的開 daemon 的那幾條。"""

    def cpus_on_daemon(self, ncpu):
        return all(self.cpu_key(n) in self.table() for n in range(ncpu))

    def test_boot_adds_the_kernel_with_configured_run_flags(self):
        self.spawn_daemon()
        self.init(1, interval_ms=73, timeout_ms=456)
        r = self.kernel_boot(self.k, "--home", self.home.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        key = os.path.realpath(self.at("inst.json"))
        self.assertTrue(wait_until(lambda: key in self.table()), self.table())
        self.assertEqual(self.table()[key]["args"],
                         ["--interval-ms", "73", "--timeout-ms", "456"])

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
