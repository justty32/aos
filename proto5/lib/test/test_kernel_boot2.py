"""proto5-2 kernel boot 交接（handoff §1）與崩潰窗口（kernel-pools §5、kernel-tick 第 8 步、handoff §1 崩在哪）。

「崩」＝在某一步丟出 Crash（BaseException），記憶體全丟、磁碟停在那一刻；下一格／下一次 boot 照常跑。
"""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_home
import aos_kernel_boot
import aos_kernel_engine
import aos_kernel_info
from _kernel_fake import Crash, FakeCase


def crash(*args, **kwargs):
    raise Crash()


class Boot(FakeCase):
    def test_fresh_boot(self):
        self.init({"default": {"count": 2}, "kernel": {"count": 1, "dpool": "k1-kernel"}})
        self.boot()
        st = self.state()
        chain = st["chain"]
        epoch = int(chain.split("-")[0])
        seen = [(n, p["pool"], p["count"], p["decl"]) for n, p in self.fake.seen]
        self.assertEqual(seen, [("k-%s-boot-scale-kernel-down.json" % chain, "k1-kernel", 0, [epoch, 0]),
                                ("k-%s-boot-scale-kernel.json" % chain, "k1-kernel", 1, [epoch, 0])])
        self.assertEqual(self.fake.pool("k1-kernel")["target"], str(self.K / "pools/kernel/cpus") + "/{name}/inst.json")
        self.assertEqual((st["kcpu"], st["last_seq"], st["phase"]), ("kernel/0", 0, "running"))
        self.assertEqual(st["pools"]["kernel"]["sent"], {"count": 1, "skip": []})
        self.assertTrue(st["pools"]["default"]["dirty"] and st["pools"]["default"]["redeclare"])
        first = self.K / "pools/kernel/cpus/0/requests" / ("k-%s-1.json" % chain)
        body = aos_home.read_json(first)
        self.assertEqual(body["params"]["args"], ["tick", "--target", str(self.K), "--chain", chain, "--seq", "1"])
        self.assertEqual(len(st["acks"]), 2)
        self.tick()
        self.assertEqual(list(Path(self.D, "responses").glob("*boot*")), [])  # boot 的回音第一格 ack 掉

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
        self.assertFalse((self.K / "state.json").exists())

    def test_kernel_pool_name_taken(self):
        self.init()
        (Path(self.D) / "pools" / "kernel").mkdir(parents=True)
        aos_home.write_json(Path(self.D) / "pools/kernel/pool.json",
                            {"pool": "kernel", "owner": "/abs/other", "count": 1, "skip": [], "ver": 1, "decl": None})
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot()
        self.assertEqual(cm.exception.code, "NameTaken")
        self.assertFalse((self.K / "state.json").exists())

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
        kernel_scales = [(p["pool"], p["count"]) for _, p in self.fake.seen[n:]]
        self.assertEqual(kernel_scales, [("kernel", 0), ("kernel", 1)])
        self.tick()
        self.assertIn({"event": "scale_echo", "pool": "default", "request": pending, "result": "Interrupted"},
                      self.log_events())
        st = self.ticks(2)
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 3)
        # 舊鏈的殘格自滅
        self.assertEqual(aos_kernel_engine.tick(self.K, old_chain, 99), 0)
        # 忙的照舊收
        for key in list(st["busy"]):
            if st["busy"][key]["proc"] in ("a", "b"):
                self.respond(key)
        st = self.tick()
        self.assertEqual({st["procs"]["a"]["runs"], st["procs"]["b"]["runs"]}, {1})

    def test_boot_waits_for_old_kernel_cpu(self):
        self.init()
        self.boot()
        self.fake.linger.add("kernel")
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot(wait_ms=200)
        self.assertEqual(cm.exception.code, "AlreadyRunning")
        self.fake.gone("kernel")
        self.fake.linger.clear()
        self.boot()
        self.assertEqual(self.fake.pool("kernel")["count"], 1)

    def test_boot_moves_kernel_pool(self):
        self.init()
        self.boot()
        self.edit_info(kernel={"count": 1, "dpool": "k2-kernel"})
        self.boot()
        self.assertIsNone(self.fake.pool("kernel"))
        self.assertEqual(self.fake.pool("k2-kernel")["count"], 1)
        self.assertEqual(self.state()["pools"]["kernel"]["dpool"], "k2-kernel")

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
        self.boot()
        st = self.settle()
        self.assertEqual(st["phase"], "running")
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 1)
        self.assertEqual(list(Path(self.D, "responses").glob("*")), [])


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
        with mock.patch.object(aos_kernel_engine.Kernel, "stopping", crash):  # 讀了回音、提交點 3 前死
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
        real = aos_home.write_state
        calls = []
        def write(home, state):
            calls.append(1)
            if len(calls) == 3:  # 提交點 4 之前死（1、3 已寫）
                raise Crash()
            return real(home, state)
        with mock.patch.object(aos_home, "write_state", write):
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
        self.assertEqual(self.fake.pool("kernel")["count"], 1)
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)
        self.respond(st["on"]["a"])
        st = self.tick()
        self.assertEqual(st["procs"]["a"]["runs"], 1)

    def crash_boot(self, target, attr):
        with mock.patch.object(target, attr, crash):
            with self.assertRaises(Crash):
                self.boot()

    def test_after_step2_before_step3(self):
        old = self.state()["chain"]
        self.crash_boot(aos_kernel_boot, "Kernel")
        self.assertEqual(self.state()["chain"], old)
        self.assertIsNone(self.fake.summary("kernel"))  # kernel 池 0 顆
        self.reboot_and_check()

    def test_after_step3_before_step5(self):
        old = self.state()["chain"]
        self.crash_boot(aos_kernel_engine.Kernel, "write_pool_files")
        self.assertNotEqual(self.state()["chain"], old)
        self.assertIsNone(self.fake.summary("kernel"))
        self.reboot_and_check()

    def test_after_step5_before_step6(self):
        self.crash_boot(aos_kernel_engine.Kernel, "tick_request")
        self.assertEqual(self.fake.pool("kernel")["count"], 1)
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
        r = self.run_cli("tick", "--target", self.K, "--chain", self.state()["chain"], "--seq", self.seq)
        self.assertEqual(r.returncode, 0, r.stderr)
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
