"""kernel boot（kernel/boot.md）與崩潰窗口（kernel-pools §5、kernel-tick 第 8 步、boot 崩在哪）。

2026-09-24 one-boot：沒有 kernel 池／kernel cpu／開機交接；boot＝寫 sqlite 帳本＋向 daemon 登記開 tick。
舊的第 2 版 K/state.json 帳本裡的 kernel 池 boot 時縮到 0、等收乾淨（Legacy 那組）。

「崩」＝在某一步丟出 Crash（BaseException），記憶體全丟、磁碟停在那一刻；下一格／下一次 boot 照常跑。
"""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_daemon_ticks
import aos_home
import aos_kernel_boot
import aos_kernel_store
import aos_kernel_engine
import aos_kernel_info
from _kernel_fake import Crash, FakeCase


def crash(*args, **kwargs):
    raise Crash()


class Boot(FakeCase):
    def reg(self):
        return aos_daemon_ticks.peek(self.D, self.K.absolute())

    def test_fresh_boot(self):
        self.init({"default": {"count": 2}}, tick_ms=250, tick_timeout_ms=9000)
        self.boot()
        st = self.state()
        chain = st["chain"]
        # 只寄一張：向 daemon 登記開 tick（工作池第一格才宣告；沒有 kernel 池）
        self.assertEqual(self.fake.seen, [("k-%s-boot-tick.json" % chain, {
            "home": str(self.K.absolute()), "cli": str(aos_kernel_info.CLI.resolve()), "every_ms": 250, "timeout_ms": 9000})])
        self.assertEqual(self.reg(), {"home": str(self.K.absolute()), "cli": str(aos_kernel_info.CLI.resolve()),
                                      "every_ms": 250, "timeout_ms": 9000})
        self.assertIsNone(self.fake.pool("kernel"))
        self.assertNotIn("kcpu", st)
        self.assertNotIn("kernel", st["pools"])
        self.assertEqual((st["last_seq"], st["phase"], st["ticker"]), (0, "running", self.D))
        self.assertIn("park", st["features"])
        self.assertTrue(st["pools"]["default"]["dirty"] and st["pools"]["default"]["redeclare"])
        self.assertFalse((self.K / "pools/kernel").exists())
        self.assertEqual(st["acks"], [])                                     # 登記的回音 boot 當場 ack
        self.fake.process()
        self.assertEqual(list(Path(self.D, "responses").glob("*boot*")), [])
        st = self.tick()
        self.assertEqual(st["last_seq"], 1)
        self.assertEqual(self.fake.pool("default")["count"], 2)

    def test_boot_restores_queue_dirs(self):
        """納入後文件組實測：手建的家少了 requests/、responses/，boot 先補上，不留到 add／halt 才 WriteFailed。"""
        self.init()
        for name in ("requests", "responses"):
            (self.K / name).rmdir()
        self.boot()
        self.assertTrue((self.K / "requests").is_dir() and (self.K / "responses").is_dir())

    def test_no_daemon_and_not_running(self):
        aos_kernel_info.init(self.K, {"pools": {"default": {"count": 1}}}, daemon=None)
        info = self.info()
        info.pop("daemon", None)
        aos_home.write_json(self.K / "info.json", info)
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            aos_kernel_boot.boot(self.K, 500)
        self.assertEqual(cm.exception.code, "NoDaemon")
        info["daemon"] = self.D
        aos_home.write_json(self.K / "info.json", info)
        self.fake.set_alive(False)
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            aos_kernel_boot.boot(self.K, 500)
        self.assertEqual(cm.exception.code, "NotRunning")
        self.assertFalse(aos_kernel_store.exists(self.K))

    def test_tick_registration_refused(self):
        """daemon 不肯登記（停機中）：boot 退錯；帳本已寫（提交在登記之前），health 報沒人開 tick，再 boot 就好。"""
        self.init()
        self.fake.stopping = True
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot()
        self.assertEqual(cm.exception.code, "Stopping")
        self.assertIsNone(self.reg())
        self.assertEqual(self.state()["phase"], "running")
        from aos_kernel_health import health
        self.assertEqual(health(self.K)[0], "tick")
        self.fake.process()
        self.assertEqual(list(Path(self.D, "responses").glob("*")), [])       # 被拒的回音也 ack 掉
        self.fake.stopping = False
        self.boot()
        self.assertIsNotNone(self.reg())

    def test_reboot_handoff(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.add("a")
        self.add("b")
        st = self.tick()
        self.assertEqual(len(st["busy"]), 2)
        # 留一張還沒放的 scale 單在 sends，再 boot：丟掉、那池下一格當 Interrupted 重送
        self.edit_info(default={"count": 3})
        with mock.patch.object(aos_kernel_engine.Kernel, "post_dispatched", crash):
            with self.assertRaises(Crash):
                self.tick(process=False)
        st = self.state()
        self.assertEqual(len(st["sends"]), 1)
        pending = st["pools"]["default"]["pending"]["name"]
        old_chain = st["chain"]
        n = len(self.fake.seen)
        self.boot()
        st = self.state()
        self.assertNotEqual(st["chain"], old_chain)
        self.assertEqual(st["sends"], [])
        self.assertEqual(sorted(st["recent"]), sorted(st["busy"]))
        self.assertTrue(st["pools"]["default"]["redeclare"])
        self.assertEqual([name for name, _ in self.fake.seen[n:]], ["k-%s-boot-tick.json" % st["chain"]])  # 只重登記
        self.tick()
        self.assertIn({"event": "scale_echo", "pool": "default", "request": pending, "result": "Interrupted"},
                      self.log_events())
        st = self.ticks(2)
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 3)
        # 舊 kernel cpu 裡還排著的舊格（帶 --chain／--seq）自滅
        self.assertEqual(aos_kernel_engine.tick(self.K, old_chain, 99), 0)
        # 忙的照舊收
        for key in list(st["busy"]):
            if st["busy"][key]["proc"] in ("a", "b"):
                self.respond(key)
        st = self.tick()
        self.assertEqual({st["procs"]["a"]["runs"], st["procs"]["b"]["runs"]}, {1})

    def legacy_ledger(self):
        """做一份第 2 版 K/state.json（kernel cpu 那一版）：帳本裡有 kernel 池，假 daemon 那邊 kernel 池 1 顆在跑。"""
        self.init()
        self.boot()
        self.settle()
        self.add("a")
        st = self.tick()
        st.pop("ticker", None)
        st.pop("on", None)
        st["kcpu"] = "kernel/0"
        st["pools"]["kernel"] = dict(st["pools"]["default"], dpool="kernel", sent={"count": 1, "skip": []},
                                     pending=None, free=[])
        self.fake._scale({"jsonrpc": "2.0", "id": "x", "method": "scale",
                          "params": {"pool": "kernel", "owner": str(self.K.absolute()), "count": 1, "skip": []}})
        for name in ("ledger.sqlite", "ledger.sqlite-wal", "ledger.sqlite-shm"):
            (self.K / name).unlink(missing_ok=True)
        aos_home.write_state(self.K, st)
        self.assertTrue(aos_kernel_store.legacy(self.K))
        return st

    def test_legacy_boot_waits_for_old_kernel_cpu(self):
        """舊帳本的 kernel 池：boot 送 count 0、等 daemon 收乾淨才寫新帳本；等不到＝AlreadyRunning，什麼都沒換。"""
        old = self.legacy_ledger()
        self.fake.linger.add("kernel")
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot(wait_ms=200)
        self.assertEqual(cm.exception.code, "AlreadyRunning")
        self.assertTrue(aos_kernel_store.legacy(self.K))                      # 還是舊的 state.json
        self.assertEqual(self.fake.pool("kernel")["count"], 0)               # 縮 0 的單已送、不撤回
        self.fake.gone("kernel")
        self.fake.linger.clear()
        self.boot()
        st = self.state()
        self.assertFalse(aos_kernel_store.legacy(self.K))
        self.assertTrue((self.K / "state.json.v2-old").is_file())
        self.assertNotIn("kernel", st["pools"])
        self.assertNotIn("kcpu", st)
        self.assertNotEqual(st["chain"], old["chain"])
        self.assertEqual(st["procs"]["a"]["status"], "running")               # 行程留著
        self.assertEqual(sorted(st["recent"]), sorted(st["busy"]))
        self.assertIsNone(self.fake.pool("kernel"))
        self.assertEqual(len(st["acks"]), 1)                                  # 縮 0 的回音記帳、第一格出貨 ack
        self.respond(st["on"]["a"])
        st = self.settle()
        self.assertEqual(list(Path(self.D, "responses").glob("*")), [])       # 縮 0 與登記的回音都 ack 了
        self.assertEqual(st["procs"]["a"]["runs"], 1)

    def test_legacy_import_rereads_after_old_tick_stopped(self):
        """astra 必修 1：舊程式的 tick 沒有 .tick.lock，boot 等舊 kernel 池收乾淨期間它還可能提交 state.json；
        匯入的要是停妥之後重讀的那份，不是 boot 一開始讀到的。"""
        import threading, time
        self.legacy_ledger()
        self.fake.linger.add("kernel")
        def old_tick_commits_then_exits():
            time.sleep(.2)
            st = aos_home.read_state(self.K)
            st["procs"]["late"] = dict(st["procs"]["a"], request="late.json", status="queued")
            aos_home.write_state(self.K, st)            # 舊 tick 在等待期間又提交了一次
            self.fake.gone("kernel")
            self.fake.linger.clear()
        worker = threading.Thread(target=old_tick_commits_then_exits)
        worker.start()
        self.boot()
        worker.join()
        self.assertIn("late", self.state()["procs"])

    def test_old_ledger_refused(self):
        self.init()
        aos_home.write_json(self.K / "state.json", {"chain": "1-1", "cpus": {}, "queue": []})
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot()
        self.assertEqual(cm.exception.code, "LedgerVersion")

    def test_boot_after_halt(self):
        self.init({"default": {"count": 1}})
        self.boot()
        self.settle()
        self.stop_kernel()
        st = self.ticks(5)
        self.assertEqual(st["phase"], "stopped")
        self.assertIsNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))      # 停好那格撤登記
        self.boot()
        st = self.settle()
        self.assertEqual(st["phase"], "running")
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 1)
        self.assertEqual(list(Path(self.D, "responses").glob("*")), [])
        self.assertIsNotNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))   # 重新登記


class CrashScale(FakeCase):
    """kernel 改宣告一半死（kernel-pools §5、protocol §4）。"""

    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 1}})
        self.boot()
        self.settle()

    def scale_names(self):
        return [n for n, _ in self.fake.seen if "scale-default" in n]

    def test_pending_recorded_request_not_posted(self):
        self.edit_info(default={"count": 2})
        real = aos_kernel_engine.Kernel.flush_outboxes
        calls = []
        def flush(self_):
            calls.append(1)
            if len(calls) == 2:  # 第 10 步出貨前死
                raise Crash()
            return real(self_)
        with mock.patch.object(aos_kernel_engine.Kernel, "flush_outboxes", flush):
            with self.assertRaises(Crash):
                self.tick()
        st = self.state()
        self.assertEqual(len(st["sends"]), 1)
        name = st["pools"]["default"]["pending"]["name"]
        self.assertFalse((Path(self.D) / "requests" / name).exists())
        n = len(self.scale_names())
        st = self.tick()  # 第 4 步補放；假 daemon 處理
        st = self.tick()
        self.assertEqual(self.scale_names()[n:], [name])
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)
        self.assertEqual(sorted(st["pools"]["default"]["free"]), [0, 1])

    def test_posted_echo_arrived_ledger_not_written(self):
        self.edit_info(default={"count": 2})
        st = self.tick()  # 放了單、daemon 回了音
        name = st["pools"]["default"]["pending"]["name"]
        self.assertTrue((Path(self.D) / "responses" / name).exists())
        with mock.patch.object(aos_kernel_engine.Kernel, "stopping", crash):  # 讀了回音、提交點 B 前死
            with self.assertRaises(Crash):
                self.tick()
        st = self.state()
        self.assertEqual(st["pools"]["default"]["pending"]["name"], name)
        st = self.tick()
        self.assertIsNone(st["pools"]["default"]["pending"])
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)
        self.assertEqual(self.scale_names().count(name), 1)
        self.tick()
        self.assertFalse((Path(self.D) / "responses" / name).exists())

    def test_flushed_but_not_cleared(self):
        """放完單、清帳前死：下一格重放同名單時回音已在就不再放（不讓 daemon 處理兩次）。"""
        self.edit_info(default={"count": 2})
        real = aos_kernel_store.Store.save
        calls = []
        def write(store, state):
            calls.append(1)
            if len(calls) == 2:  # 提交點 C 之前死（B 已寫）
                raise Crash()
            return real(store, state)
        with mock.patch.object(aos_kernel_store.Store, "save", write):
            with self.assertRaises(Crash):
                self.tick()
        self.assertEqual(len(self.state()["sends"]), 1)
        name = self.state()["sends"][0]["name"]
        n = len(self.scale_names())
        st = self.ticks(2)
        self.assertEqual(self.scale_names()[n:].count(name), 1)
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)


class CrashDispatch(FakeCase):
    def test_post_half_then_recent_reposts(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.add("a")
        self.add("b")
        real = aos_kernel_engine.Kernel._post_work
        calls = []
        def post(self_, key, req, proc):
            calls.append(key)
            if len(calls) == 2:
                raise Crash()
            return real(self_, key, req, proc)
        with mock.patch.object(aos_kernel_engine.Kernel, "_post_work", post):
            with self.assertRaises(Crash):
                self.tick()
        st = self.state()
        self.assertEqual(len(st["busy"]), 2)
        posted = [k for k, v in st["busy"].items() if (self.cpu(k) / "requests" / v["req"]).exists()]
        self.assertEqual(len(posted), 1)
        self.assertEqual(sorted(st["recent"]), sorted(st["busy"]))
        st = self.tick()
        for key, slot in st["busy"].items():
            self.assertTrue((self.cpu(key) / "requests" / slot["req"]).exists())
            self.respond(key)
        st = self.tick()
        self.assertEqual((st["procs"]["a"]["runs"], st["procs"]["b"]["runs"]), (1, 1))


class CrashBoot(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.add("a")
        self.tick()

    def reboot_and_check(self):
        self.boot()
        st = self.settle()
        self.assertEqual(st["phase"], "running")
        self.assertIsNotNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)
        self.respond(st["on"]["a"])
        st = self.tick()
        self.assertEqual(st["procs"]["a"]["runs"], 1)

    def crash_boot(self, target, attr):
        with mock.patch.object(target, attr, crash):
            with self.assertRaises(Crash):
                self.boot()

    def test_before_ledger_built(self):
        """拿了鎖、還沒建帳本就死：帳本照舊（同 chain），鎖跟著行程放掉，再 boot 照常。"""
        old = self.state()["chain"]
        self.crash_boot(aos_kernel_boot, "Kernel")
        self.assertEqual(self.state()["chain"], old)
        self.reboot_and_check()

    def test_after_ledger_built_before_commit(self):
        """建家（寫池檔）時死：帳本那筆交易還沒提交＝整筆沒發生（one-boot：以前這裡已寫了新 chain）。"""
        old = self.state()["chain"]
        self.crash_boot(aos_kernel_engine.Kernel, "write_pool_files")
        self.assertEqual(self.state()["chain"], old)
        self.reboot_and_check()

    def test_after_commit_before_registration(self):
        """帳本寫好、還沒向 daemon 登記就死：daemon 不開 tick，health 報 tick；再 boot 就好。"""
        from aos_kernel_health import health
        aos_daemon_ticks.reg_path(self.D, self.K.absolute()).unlink()   # 例如 halt 之後重開
        old = self.state()["chain"]
        self.crash_boot(aos_kernel_boot, "_call")
        self.assertNotEqual(self.state()["chain"], old)
        self.assertIsNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))
        self.assertEqual(health(self.K)[0], "tick")
        self.reboot_and_check()


CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-kernel"
HAS_POOL_SUMMARY = "def pool_summary" in (Path(__file__).resolve().parents[1] / "aos_daemon.py").read_text()


class Cli(FakeCase):
    """init／boot／tick／add／rm／ack／ls 用真的 aos-kernel 指令跑（假 daemon 在本行程的執行緒裡）。"""

    def run_cli(self, *args, timeout=20):
        import subprocess
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, timeout=timeout)

    def popen(self, *args):
        import subprocess
        return subprocess.Popen([sys.executable, str(CLI), *map(str, args)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def cli_tick(self):
        self.seq += 1
        r = self.run_cli("tick", "--target", self.K)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state()["last_seq"], self.seq)
        self.fake.process()

    def test_add_tick_rm_ack_ls(self):
        self.init({"default": {"count": 1}})
        self.boot()
        for _ in range(3):
            self.cli_tick()
        adder = self.popen("add", "--target", self.K, "--name", "bob", str(self.root / "w.json"))
        for _ in range(200):
            if list((self.K / "requests").glob("cli-*")):
                break
            __import__("time").sleep(.01)
        self.cli_tick()
        out, err = adder.communicate(timeout=20)
        self.assertEqual((adder.returncode, out.strip()), (0, "bob"), err)
        self.assertEqual(self.state()["on"]["bob"], "default/0")
        once = self.popen("add", "--target", self.K, "--once", str(self.root / "w.json"))
        out, err = once.communicate(timeout=20)
        self.assertEqual(once.returncode, 0, err)
        req, path = out.split()
        self.cli_tick()
        self.respond("default/0")
        self.cli_tick()
        self.cli_tick()
        self.respond("default/0")
        self.cli_tick()
        self.assertIn("result", aos_home.read_json(path))
        r = self.run_cli("ack", "--target", self.K, req)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.cli_tick()
        self.assertFalse(Path(path).exists())
        remover = self.popen("rm", "--target", self.K, "bob")
        for _ in range(200):
            if list((self.K / "requests").glob("cli-*")):
                break
            __import__("time").sleep(.01)
        self.cli_tick()
        out, err = remover.communicate(timeout=20)
        self.assertEqual((remover.returncode, out.strip()), (0, "bob"), err)
        r = self.run_cli("ls", "--target", self.K)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("default  want", r.stdout)
        r = self.run_cli("ls", "--target", self.K, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(HAS_POOL_SUMMARY, "daemon 隊的 aos_daemon.pool_summary 還沒進來")
    def test_boot_and_halt_cli(self):
        self.init({"default": {"count": 1}})
        self.fake.start()
        try:
            r = self.run_cli("boot", "--target", self.K, "--wait-ms", 5000)
        finally:
            self.fake.stop()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("booted", r.stdout)

    def test_boot_cli_no_daemon(self):
        aos_kernel_info.init(self.K, {"pools": {}})
        info = self.info()
        info.pop("daemon", None)
        aos_home.write_json(self.K / "info.json", info)
        r = self.run_cli("boot", "--target", self.K)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NoDaemon", r.stderr)
        r = self.run_cli("boot", "--target", self.K, "--daemon-target", self.D)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
