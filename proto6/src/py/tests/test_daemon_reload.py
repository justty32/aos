"""重讀設定模組驗收（plan m3m-daemon-modules.md 模組一）。真的開 bin/aos-daemon，改設定檔、送 SIGHUP。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。量週期用任務寫的 /proc/uptime（不會跳；
WSL 的牆上時鐘偶爾往前跳好幾秒，見 test_ctl 檔頭），等條件一律用 monotonic 計時的 wait_for，時限寬鬆。
"""
import os
import signal
import time
import unittest

from test_ctl import CONTROL, STAMP, UPTIME, CtlCase
from test_daemon import INHERIT, sh

RELOAD = {"reload": {}}
BOTH = dict(CONTROL, **RELOAD)


class ReloadCase(CtlCase):

    def boot(self, insts, interval_ms, modules=None, **top):
        """開一個掛了重讀設定（預設也掛控制）的 daemon；回 (Popen, out, err)。"""
        mods = BOTH if modules is None else modules
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": mods, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        if "control" in mods:
            self.wait_for(lambda: self.exists("aos.sock"))
        return p, out, err

    def rewrite(self, p, insts, interval_ms, modules=None, **top):
        """改寫 config.json、送 SIGHUP，等 stdout 出現 reloaded（第幾次以 count 計）。"""
        mods = BOTH if modules is None else modules
        self.config(dict({"interval_ms": interval_ms, "modules": mods, "insts": insts}, **top))
        self.hup(p)

    def hup(self, p):
        os.kill(p.pid, signal.SIGHUP)

    def reloads(self, out):
        return sum(1 for l in list(out) if l.endswith(" reloaded"))


class Add(ReloadCase):

    def test_add_runs_now(self):
        for n in ("a", "b", "c"):
            self.inst(sh(STAMP), "%s.json" % n)
        p, out, _ = self.boot({"a.json": {}, "b.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json") and self.results(out, "b.json"))
        self.rewrite(p, {"a.json": {}, "b.json": {}, "c.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "c.json"), timeout=5)
        self.assertTrue(self.has(out, "inst=c.json added"))
        self.assertTrue(self.has(out, "reloaded"))
        lines = [l.split(" ", 1)[1] for l in list(out)]
        self.assertLess(lines.index("inst=c.json added"), lines.index("reloaded"))
        time.sleep(0.5)
        # 原本兩項的週期不受影響：沒有因為重讀多跑
        self.assertEqual((len(self.results(out, "a.json")), len(self.results(out, "b.json"))), (1, 1))
        # 新加的項控制指令認得
        self.assertEqual(self.send({"status": "c.json"})["inst"], "c.json")

    def test_new_item_gets_env(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.inst(sh('echo "$AOS_DAEMON_INST" > env.txt'), "e.json")
        p, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json"))
        self.rewrite(p, {"a.json": {}, "e.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "e.json"), timeout=5)
        self.assertEqual(self.read("env.txt").strip(), "e.json")


class Remove(ReloadCase):

    def test_remove_running(self):
        # 正在跑的那次不殺、跑完照樣印 exit=；之後不再跑，控制指令回 unknown_inst
        self.inst(sh(UPTIME + " >> starts; sleep 1"), "r.json")
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"r.json": {}, "a.json": {}}, 100)
        self.wait_for(lambda: len(self.runs("starts")) >= 1)
        self.rewrite(p, {"a.json": {}}, 100)
        self.wait_for(lambda: self.has(out, "inst=r.json removed"))
        n = len(self.runs("starts"))
        self.wait_for(lambda: len(self.results(out, "r.json")) == n, timeout=5)   # 那次照樣印完
        lines = [l.split(" ", 1)[1] for l in list(out)]
        self.assertLess(lines.index("inst=r.json removed"),
                        max(i for i, l in enumerate(lines) if l.startswith("inst=r.json exit=")))
        time.sleep(1.0)
        self.assertEqual(len(self.runs("starts")), n)
        self.assertEqual(len(self.results(out, "r.json")), n)
        self.assertEqual(self.send({"status": "r.json"}),
                         {"ok": False, "error": "unknown_inst", "detail": "r.json"})
        self.assertGreater(len(self.results(out, "a.json")), 3)       # 其他項照跑

    def test_readd_is_new(self):
        # 拿掉又加回來＝新的一項：原本暫停的，加回來後不暫停、立刻跑
        self.inst(sh(STAMP), "r.json")
        p, out, _ = self.boot({"r.json": {}}, 30000)
        self.wait_for(lambda: len(self.runs()) == 1)
        self.send({"pause": "r.json"})
        self.rewrite(p, {}, 30000)
        self.wait_for(lambda: self.reloads(out) == 1)
        self.rewrite(p, {"r.json": {}}, 30000)
        self.wait_for(lambda: self.reloads(out) == 2)
        self.wait_for(lambda: len(self.runs()) == 2, timeout=5)
        self.assertFalse(self.send({"status": "r.json"})["paused"])


class Change(ReloadCase):

    def test_interval_shorter(self):
        # 10 秒改 100 毫秒：上一次結束＋新週期早就過了，立刻跑，之後密集跑
        self.inst(sh(STAMP), "r.json")
        p, out, _ = self.boot({"r.json": {}}, 10000)
        self.wait_for(lambda: len(self.runs()) == 1)
        self.wait_for(lambda: self.send({"status": "r.json"})["last_end"] is not None)
        self.rewrite(p, {"r.json": {"interval_ms": 100}}, 10000)
        self.wait_for(lambda: len(self.runs()) >= 4, timeout=5)

    def test_interval_longer(self):
        # 300 毫秒改 3 秒（從上一次結束算）：重讀後至少 1.5 秒內不再跑
        self.inst(sh(STAMP), "r.json")
        p, out, _ = self.boot({"r.json": {}}, 300)
        self.wait_for(lambda: len(self.runs()) >= 2)
        self.rewrite(p, {"r.json": {}}, 3000)
        self.wait_for(lambda: self.reloads(out) == 1)
        t = float(self.read_uptime())
        time.sleep(0.6)                                       # 重讀那一刻正在跑的那次讓它跑完
        n = len(self.runs())
        time.sleep(1.5)
        self.assertEqual(len(self.runs()), n)
        self.wait_for(lambda: len(self.runs()) == n + 1, timeout=5)
        self.assertGreater(self.runs()[-1] - t, 1.5)

    def read_uptime(self):
        with open("/proc/uptime") as f:
            return f.read().split()[0]

    def test_paused_and_stopped_kept(self):
        self.inst(sh(STAMP), "r.json")
        self.inst({"argv": ["false"]}, "f.json")
        p, out, _ = self.boot({"r.json": {}, "f.json": {"stop_on_nonzero": True}}, 100)
        self.wait_for(lambda: self.has(out, "inst=f.json stopped"))
        self.send({"pause": "r.json"})
        self.wait_for(lambda: self.has(out, "inst=r.json paused"))
        # 設定沒動它們（只動頂層週期、f 的 stop_on_nonzero 改 false）：暫停、已停照留
        self.rewrite(p, {"r.json": {}, "f.json": {}}, 200)
        self.wait_for(lambda: self.reloads(out) == 1)
        time.sleep(0.3)
        n = len(self.runs())
        time.sleep(0.8)
        self.assertEqual(len(self.runs()), n)
        self.assertTrue(self.send({"status": "r.json"})["paused"])
        self.assertTrue(self.send({"status": "f.json"})["stopped"])
        self.assertEqual(self.results(out, "f.json"), [1])

    def test_exec_out_path_not_applied(self):
        # 頂層 exec_out_path／exec_err_path 改了：不套用（照舊寫 one.log），stdout 警告要重開（第十二批）；
        # 新加的項也照開起來時的設定寫；第幾項照新的鍵順序
        self.inst(sh("echo hi; echo oops >&2", stdout=INHERIT, stderr=INHERIT), "a.json")
        self.inst(sh("echo zz", stdout=INHERIT), "z.json")
        p, out, _ = self.boot({"a.json": {}}, 300, exec_out_path="one.log", exec_err_path="one.err")
        self.wait_for(lambda: self.exists("one.log") and self.exists("one.err"))
        self.rewrite(p, {"z.json": {}, "a.json": {}}, 300, exec_out_path="two.log", exec_err_path="two.err")
        self.wait_for(lambda: self.reloads(out) == 1)
        self.assertTrue(self.has(out, "reload: need restart: exec_out_path"))
        self.assertTrue(self.has(out, "reload: need restart: exec_err_path"))
        self.assertFalse(self.has(out, "reload: need restart: cwd"))
        self.wait_for(lambda: "index=1 inst=a.json" in self.read("one.log")
                      and "index=0 inst=z.json" in self.read("one.log"), timeout=5)
        self.assertFalse(self.exists("two.log") or self.exists("two.err"))


class NeedRestart(ReloadCase):

    def test_cwd_changed(self):
        self.inst(sh(STAMP), "r.json")
        os.makedirs(os.path.join(self.d, "elsewhere"))
        p, out, _ = self.boot({"r.json": {}}, 200)
        self.wait_for(lambda: len(self.runs()) >= 1)
        self.rewrite(p, {"r.json": {}}, 200, cwd="elsewhere")
        self.wait_for(lambda: self.reloads(out) == 1)
        self.assertTrue(self.has(out, "reload: need restart: cwd"))
        n = len(self.runs())
        self.wait_for(lambda: len(self.runs()) >= n + 3, timeout=5)   # 照舊在原本的起點跑

    def test_modules_changed(self):
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json"))
        self.rewrite(p, {"a.json": {}}, 30000, modules=dict(BOTH, later={}))
        self.wait_for(lambda: self.reloads(out) == 1)
        self.assertTrue(self.has(out, "reload: need restart: modules"))
        self.assertFalse(self.has(out, "reload: need restart: cwd"))
        # 控制 socket 照舊在
        self.assertEqual(self.send({"status": "a.json"})["inst"], "a.json")

    def test_nothing_changed(self):
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json"))
        self.hup(p)
        self.wait_for(lambda: self.reloads(out) == 1)
        texts = [l.split(" ", 1)[1] for l in list(out)]
        self.assertEqual(len(texts), 2)                             # 沒有 added／removed／need restart
        self.assertTrue(texts[0].startswith("inst=a.json exit=0 "))
        self.assertEqual(texts[1], "reloaded")


class Broken(ReloadCase):

    def test_bad_then_fixed(self):
        self.inst(sh(STAMP), "r.json")
        self.inst({"argv": ["true"]}, "c.json")
        p, out, err = self.boot({"r.json": {}}, 200)
        self.wait_for(lambda: len(self.runs()) >= 1)
        self.write("config.json", "{bad json")
        self.hup(p)
        self.wait_for(lambda: any(l.startswith("aos-daemon: reload: ") for l in list(err)))
        # 缺 interval_ms 也算壞
        self.config({"modules": BOTH, "insts": {"r.json": {}, "c.json": {}}})
        self.hup(p)
        self.wait_for(lambda: sum(1 for l in list(err) if l.startswith("aos-daemon: reload: ")) == 2)
        self.assertEqual(len(err), 2)
        self.assertIsNone(p.poll())
        self.assertEqual(self.reloads(out), 0)
        self.assertFalse(self.results(out, "c.json"))
        n = len(self.runs())
        self.wait_for(lambda: len(self.runs()) >= n + 3, timeout=5)   # 舊設定照跑
        self.rewrite(p, {"r.json": {}, "c.json": {}}, 200)
        self.wait_for(lambda: self.results(out, "c.json"), timeout=5)
        self.assertEqual(self.reloads(out), 1)

    def test_many_hups(self):
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json"))
        for _ in range(20):
            self.hup(p)
        self.wait_for(lambda: self.reloads(out) >= 1)
        time.sleep(0.5)
        self.assertIsNone(p.poll())
        self.assertEqual(len(self.results(out, "a.json")), 1)


class NotMounted(ReloadCase):

    def test_sighup_default(self):
        # 沒掛模組：SIGHUP 照 Python 預設，daemon 被殺（跟 m3、m3n 一樣）
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules={})
        self.wait_for(lambda: self.results(out, "a.json"))
        self.hup(p)
        self.assertEqual(p.wait(timeout=5), -signal.SIGHUP)

    def test_reload_only(self):
        # 只掛 reload、不掛控制：照樣重讀
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules=RELOAD)
        self.wait_for(lambda: self.results(out, "a.json"))
        self.rewrite(p, {"a.json": {}, "b.json": {}}, 30000, modules=RELOAD)
        self.wait_for(lambda: self.results(out, "b.json"), timeout=5)
        self.assertFalse(self.exists("aos.sock"))


if __name__ == "__main__":
    unittest.main()
