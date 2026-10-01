"""記住狀態模組驗收（plan m3m-daemon-modules.md 模組三）。真的開 bin/aos-daemon、Ctrl-C、再開。

設定寫 `"modules": {"state": {"$ref": "aos-state.json"}}`（使用者 2026-10-01）。都用暫存資料夾、
短週期、假 inst；時限寬鬆、計時用 monotonic（見 test_ctl 檔頭）。
"""
import json
import os
import signal
import time
import unittest

import aos_daemon
from test_ctl import CONTROL, STAMP, CtlCase
from test_daemon import sh

STATE = {"state": {"$ref": "aos-state.json"}}
BOTH = dict(CONTROL, **STATE)


class StateCase(CtlCase):

    def boot(self, insts, interval_ms, modules=None, **top):
        mods = BOTH if modules is None else modules
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": mods, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        if "control" in mods:
            self.wait_for(lambda: self.exists("aos.sock"))
        return p, out, err

    def down(self, p):
        """Ctrl-C，等它回 0。"""
        p.send_signal(signal.SIGINT)
        self.assertEqual(p.wait(timeout=5), 0)

    def state(self):
        return json.loads(self.read("aos-state.json"))

    @staticmethod
    def texts(out):
        return [l.split(" ", 1)[1] for l in list(out)]


class Pause(StateCase):

    def test_pause_survives_restart(self):
        self.inst(sh(STAMP), "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        insts = {"a.json": {}, "b.json": {}}
        p, out, _ = self.boot(insts, 300)
        self.wait_for(lambda: len(self.runs()) >= 1)
        self.assertFalse(self.exists("aos-state.json"))            # 全部正常：還沒建
        self.assertEqual(self.send({"pause": "a.json"}), {"ok": True})
        self.assertEqual(self.state(), {"insts": {"a.json": {"paused": True}}})
        time.sleep(0.5)                                             # 正在跑的那次讓它跑完
        self.down(p)
        n = len(self.runs())
        p, out, _ = self.boot(insts, 300)
        self.wait_for(lambda: len(self.results(out, "b.json")) >= 3)
        self.assertEqual(len(self.runs()), n)                       # a 沒有先跑那一次
        self.assertIn("inst=a.json paused", self.texts(out))
        self.assertTrue(self.send({"status": "a.json"})["paused"])
        self.assertEqual(self.send({"resume": "a.json"}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == n + 1, timeout=5)
        self.assertEqual(self.state(), {"insts": {}})

    def test_paused_line_before_runs(self):
        # 恢復的那行在任何 exit 行之前印
        self.write("aos-state.json", json.dumps({"insts": {"a.json": {"paused": True}}}))
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        _, out, _ = self.boot({"a.json": {}, "b.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "b.json"))
        self.assertEqual(self.texts(out)[0], "inst=a.json paused")
        self.assertFalse(self.results(out, "a.json"))


class Stopped(StateCase):

    def test_stopped_survives_restart(self):
        self.inst(sh(STAMP + "; exit 1"), "f.json")
        self.inst({"argv": ["true"]}, "b.json")
        insts = {"f.json": {"stop_on_nonzero": True}, "b.json": {}}
        p, out, _ = self.boot(insts, 200)
        self.wait_for(lambda: self.has(out, "inst=f.json stopped"))
        self.wait_for(lambda: self.exists("aos-state.json"))
        self.assertEqual(self.state(), {"insts": {"f.json": {"stopped": True}}})
        self.down(p)
        p, out, _ = self.boot(insts, 200)
        self.wait_for(lambda: len(self.results(out, "b.json")) >= 3)
        self.assertEqual(len(self.runs()), 1)
        self.assertIn("inst=f.json stopped", self.texts(out))
        self.assertEqual(self.send({"wake": "f.json"}),
                         {"ok": False, "error": "stopped", "detail": "f.json"})

    def test_without_control(self):
        # 只掛 state：記得住 stop_on_nonzero 停掉的，重開也不跑（救回只能刪狀態檔）
        self.inst(sh(STAMP + "; exit 1"), "f.json")
        insts = {"f.json": {"stop_on_nonzero": True}}
        p, out, _ = self.boot(insts, 200, modules=STATE)
        self.wait_for(lambda: self.exists("aos-state.json"))
        self.down(p)
        p, out, _ = self.boot(insts, 200, modules=STATE)
        self.wait_for(lambda: self.has(out, "inst=f.json stopped"))
        time.sleep(0.6)
        self.assertEqual(len(self.runs()), 1)
        self.down(p)
        os.unlink(os.path.join(self.d, "aos-state.json"))
        p, out, _ = self.boot(insts, 200, modules=STATE)
        self.wait_for(lambda: len(self.runs()) == 2, timeout=5)


class FileRules(StateCase):

    def test_stale_key_dropped(self):
        # 檔裡有設定檔已經沒有的鍵：重開時忽略，下一次寫檔時它就不見了
        self.write("aos-state.json", json.dumps({"insts": {"gone.json": {"paused": True}}}))
        self.inst({"argv": ["true"]}, "a.json")
        _, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json"))
        self.assertNotIn("inst=gone.json paused", self.texts(out))
        self.assertEqual(self.state(), {"insts": {"gone.json": {"paused": True}}})   # 還沒寫過
        self.send({"pause": "a.json"})
        self.assertEqual(self.state(), {"insts": {"a.json": {"paused": True}}})

    def test_no_file(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        _, out, _ = self.boot({"a.json": {}, "b.json": {}}, 30000)
        self.wait_for(lambda: self.results(out, "a.json") and self.results(out, "b.json"))
        self.assertFalse(self.exists("aos-state.json"))
        # 暫停又恢復：檔建出來、內容回到空的
        self.send({"pause": "a.json"})
        self.send({"resume": "a.json"})
        self.assertEqual(self.state(), {"insts": {}})
        self.assertEqual(sorted(os.listdir(self.d)),
                         ["a.json", "aos-state.json", "aos.sock", "b.json", "config.json", "config.json.lock"])

    def test_ref_relative_to_config(self):
        # $ref 照其他 $ref，以設定檔所在資料夾為準（不是起點）
        self.inst({"argv": ["true"]}, "a.json")
        cfg = self.config({"interval_ms": 30000, "modules": BOTH, "insts": {"a.json": {}}},
                          "conf/daemon.json")
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: self.exists("aos.sock"))
        self.send({"pause": "a.json"})
        self.assertTrue(self.exists("conf/aos-state.json"))
        self.assertFalse(self.exists("aos-state.json"))

    def test_both_flags(self):
        self.write("aos-state.json", json.dumps({"insts": {"a.json": {"paused": True, "stopped": True}}}))
        self.inst({"argv": ["true"]}, "a.json")
        _, out, _ = self.boot({"a.json": {}}, 30000)
        self.wait_for(lambda: len(out) >= 2)
        self.assertEqual(self.texts(out)[:2], ["inst=a.json paused", "inst=a.json stopped"])
        self.send({"resume": "a.json"})                             # resume 兩個都清
        self.wait_for(lambda: self.results(out, "a.json"))
        self.assertEqual(self.state(), {"insts": {}})


class Config(StateCase):

    def test_not_a_ref(self):
        for bad in ({"path": "./aos-state.json"}, {"$ref": "s.json#/x"}, {"$ref": ""},
                    {"$ref": "s.json", "$at": "/x"}, "aos-state.json"):
            r = self.run_cfg(self.config({"interval_ms": 5, "insts": {}, "modules": {"state": bad}}))
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("aos-daemon: config: modules.state", r.stderr)

    def test_load_full(self):
        self.write("conf/aos-state.json", json.dumps({"insts": {"a": {"paused": True}}}))
        cfg = self.config({"interval_ms": 5, "insts": {"a": {}}, "modules": {"state": {"$ref": "aos-state.json"},
                                                                         "reload": {}}},
                          "conf/daemon.json")
        s = aos_daemon.load_full(cfg)
        path = os.path.join(self.d, "conf", "aos-state.json")
        self.assertEqual((s.state_path, s.modules["state"], s.reload), (path, path, True))
        self.assertEqual(s.state_data, {"insts": {"a": {"paused": True}}})
        self.assertEqual(aos_daemon.load_full(cfg, read_state=False).state_data, {"insts": {}})
        os.unlink(path)
        self.assertEqual(aos_daemon.load_full(cfg).state_data, {"insts": {}})   # 不在＝空的，不算設定錯


class WithReload(StateCase):

    def test_reload_memory_wins(self):
        # 重讀以記憶體為準：拿掉的項從檔裡不見；檔被人改了也不拿來覆蓋記憶體
        mods = dict(BOTH, reload={})
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        p, out, _ = self.boot({"a.json": {}, "b.json": {}}, 30000, modules=mods)
        self.wait_for(lambda: self.results(out, "a.json") and self.results(out, "b.json"))
        self.send({"pause": "a.json"})
        self.send({"pause": "b.json"})
        self.assertEqual(set(self.state()["insts"]), {"a.json", "b.json"})
        self.write("aos-state.json", json.dumps({"insts": {"b.json": {"paused": True},
                                                           "c.json": {"paused": True}}}))
        self.inst({"argv": ["true"]}, "c.json")
        self.config({"interval_ms": 30000, "modules": mods, "insts": {"b.json": {}, "c.json": {}}})
        os.kill(p.pid, signal.SIGHUP)
        self.wait_for(lambda: self.has(out, "reloaded"))
        self.wait_for(lambda: self.results(out, "c.json"), timeout=5)   # 新加的項從頭，不照檔暫停
        self.assertFalse(self.send({"status": "c.json"})["paused"])
        self.assertEqual(self.state(), {"insts": {"b.json": {"paused": True}}})


if __name__ == "__main__":
    unittest.main()
