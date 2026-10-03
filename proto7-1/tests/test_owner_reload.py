"""使用者 10-03 的兩個裁定：Q5 子 daemon 歸屬起它的 node（路二 stop 要 allow_stop）、Q6 restart 加 reload。"""
import os
import subprocess
import sys
import time
import unittest

from test_core import BIN, SLEEPER
from test_core_daemon import DaemonCase
import aos7_mount
from aos7_fs import read_json, read_jsonl, write_json

V1 = SLEEPER + ["v1"]
V2 = SLEEPER + ["v2"]


def owner_env(pid):
    with open("/proc/%d/environ" % pid, "rb") as f:
        env = dict(x.decode().split("=", 1) for x in f.read().split(b"\0") if b"=" in x)
    return {"node": env.get("AOS7_OWNER_NODE"), "tid": env.get("AOS7_OWNER_TID"),
            "allow_stop": env.get("AOS7_ALLOW_STOP") == "1"}


def done(tdir):
    return read_json(os.path.join(tdir, "ctl-done.json"))


class TestOwnerTick(DaemonCase):
    """tick 這邊：寫 owner.json、看到 stopped.json 不起、allow_stop 型別、restart 帶 allow_stop。"""

    def owner(self, node, tid):
        """tick 交給任務的擁有者（astra-7 H-02：owner.json 由子 daemon 拿到鎖後才寫，tick 只經環境變數交棒）。"""
        pid = self.wait_for(lambda: read_json(os.path.join(self.tdir(node, tid), "pid.json")))["pid"]
        return owner_env(pid)

    def test_owner_json_and_stopped_blocks_keep_and_spawn(self):
        node = self.mknode("lab", [{"name": "d", "mode": "keep", "argv": SLEEPER, "subroot": "lab/sub"}])
        self.assertEqual(self.tick("lab")["started"], ["d-r1"])
        ow = self.owner(node, "d-r1")
        self.assertEqual((ow["node"], ow["tid"], ow["allow_stop"]), ("lab", "d-r1", False))
        self.assertFalse(os.path.exists(os.path.join(node, "sub", ".aosd", "owner.json")))   # tick 不寫，子 daemon 才寫
        # 子 daemon 被路二 stop（allow_stop 允許時它自己寫標記）；這裡直接寫標記、收掉任務
        write_json(os.path.join(node, "sub", ".aosd", "stopped.json"), {"by": "B", "why": "測", "at": "t0", "kill": True})
        self.prog("aos7-ctl", "task", self.tdir(node, "d-r1"), "kill")
        self.tock("lab")
        write_json(os.path.join(node, ".aos", "spawn", "x.json"), {"name": "d2", "argv": SLEEPER, "subroot": "lab/sub"})
        self.assertEqual(self.tick("lab")["started"], [])
        errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
        self.assertEqual(len(errs), 2, errs)
        self.assertTrue(all("被 B 在 t0 stop" in e and "stopped.json" in e for e in errs), errs)
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "x.json")))
        self.assertFalse(os.path.exists(self.tdir(node, "d-r2")))   # 沒佔 tid
        self.tock("lab")
        os.remove(os.path.join(node, "sub", ".aosd", "stopped.json"))
        self.assertEqual(self.tick("lab")["started"], ["d-r3"])
        self.assertEqual(self.owner(node, "d-r3")["tid"], "d-r3")

    def test_allow_stop_type_and_restart_carries_it(self):
        node = self.mknode("lab", [{"name": "bad", "argv": SLEEPER, "subroot": "lab/s2", "allow_stop": "yes"},
                                   {"name": "d", "mode": "keep", "argv": SLEEPER, "subroot": "lab/sub",
                                    "allow_stop": True}])
        self.assertEqual(self.tick("lab")["started"], ["d-r1"])
        errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
        self.assertTrue(any("allow_stop" in e for e in errs), errs)
        self.assertTrue(self.owner(node, "d-r1")["allow_stop"])
        self.wait_for(lambda: self.state(node, "d-r1") == "live")
        self.tock("lab")
        self.prog("aos7-ctl", "task", self.tdir(node, "d-r1"), "restart")
        self.assertEqual(self.tick("lab")["started"], ["d-r2"])
        b = read_json(os.path.join(self.tdir(node, "d-r2"), "birth.json"))
        self.assertEqual((b["allow_stop"], b["subroot"], b["restart_of"]), (True, "lab/sub", "d-r1"))
        self.assertEqual((self.owner(node, "d-r2")["tid"], self.owner(node, "d-r2")["allow_stop"]), ("d-r2", True))


class TestOwnerDaemon(DaemonCase):
    """子 daemon 收到路二的 stop：擁有者沒允許就不停；允許就停、留 stopped.json，父的 keep 不再起；刪掉標記才再起。"""

    def test_stop_needs_owner_permission(self):
        node = self.mknode("lab", [{"name": "d", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_SUBROOT"],
                                    "subroot": "lab/sub"}], interval_ms=100)
        sub = os.path.join(node, "sub")
        self.start_daemon()
        st = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "status.json")), msg="子 daemon 沒起來")
        gen = st["gen"]
        cdir = os.path.join(sub, ".aosd", "ctl")
        write_json(os.path.join(cdir, "s1.json"), {"op": "stop", "kill": True, "by": "B"})
        r = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "ctl-done", "s1.json")))["result"]
        self.assertFalse(r["ok"])
        self.assertIn("屬於 node lab（任務 d-r1）", r["msg"])
        self.assertIn("allow_stop", r["msg"])
        time.sleep(0.3)
        st = read_json(os.path.join(sub, ".aosd", "status.json"))
        self.assertFalse(st["stopping"])
        self.assertFalse(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")))
        # 擁有者直接改 owner.json 允許
        ow = read_json(os.path.join(sub, ".aosd", "owner.json"))
        write_json(os.path.join(sub, ".aosd", "owner.json"), dict(ow, allow_stop=True))
        write_json(os.path.join(cdir, "s2.json"), {"op": "stop", "kill": True, "by": "B", "why": "收工"})
        r = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "ctl-done", "s2.json")))["result"]
        self.assertTrue(r["ok"], r)
        self.wait_for(lambda: (read_json(os.path.join(sub, ".aosd", "status.json")) or {}).get("stopped"))
        mark = read_json(os.path.join(sub, ".aosd", "stopped.json"))
        self.assertEqual((mark["by"], mark["why"], mark["kill"]), ("B", "收工", True))
        self.wait_for(lambda: self.state(node, "d-r1") == "ended")
        time.sleep(0.8)   # 幾個回合：父的 keep 不再起
        self.assertEqual(read_json(os.path.join(sub, ".aosd", "gen.json"))["gen"], gen)
        self.assertEqual([t for t in os.listdir(os.path.join(node, ".aos", "tasks")) if t.startswith("d-")], ["d-r1"])
        errs = [e for x in read_jsonl(os.path.join(node, ".aos", "rounds.jsonl")) for e in x.get("tasks_error", [])]
        self.assertTrue(any("被 B" in e for e in errs), errs)
        # 刪掉標記：下一回合 keep 照常起
        os.remove(os.path.join(sub, ".aosd", "stopped.json"))
        self.wait_for(lambda: (read_json(os.path.join(sub, ".aosd", "gen.json")) or {}).get("gen", 0) > gen,
                      msg="刪掉 stopped.json 後沒再起")
        self.wait_for(lambda: (read_json(os.path.join(sub, ".aosd", "status.json")) or {}).get("gen", 0) > gen)
        # 路一（父 stop --kill → SIGTERM）照舊，不寫 stopped.json
        self.ctl("stop", "--kill")
        self.wait_for(lambda: (read_json(os.path.join(sub, ".aosd", "status.json")) or {}).get("stopped"))
        self.assertFalse(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")))

    def test_top_level_stop_and_manual_start_clears_mark(self):
        write_json(os.path.join(self.root, ".aosd", "stopped.json"), {"by": "B", "at": "t0"})
        self.mknode("a", interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes"))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".aosd", "stopped.json")))
        ev = [x for x in self.log() if x.get("ev") == "stopped-cleared"]
        self.assertEqual(ev[0]["was"]["by"], "B")
        self.ctl("stop")
        self.assertEqual(p.wait(10), 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".aosd", "stopped.json")))   # 頂層不寫


class TestRestartReload(DaemonCase):
    def setup_v1(self, extra=None):
        node = self.mknode("a", [dict({"name": "s", "mode": "keep", "argv": V1}, **(extra or {}))])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        self.tock()
        return node

    def set_tasks(self, node, tasks):
        write_json(os.path.join(node, ".aos", "tasks.json"), {"tasks": tasks})

    def test_reload_takes_new_definition(self):
        node = self.setup_v1()
        self.set_tasks(node, [{"name": "s", "mode": "keep", "argv": V2, "mounts": {"box": "a/box"}, "from_round": 1}])
        out = self.prog("aos7-ctl", "task", self.tdir(node, "s-r1"), "restart", "換版", "--reload")
        self.assertTrue(read_json(out["wrote"])["reload"])
        self.assertEqual(self.tick()["started"], ["s-r2"])
        b = read_json(os.path.join(self.tdir(node, "s-r2"), "birth.json"))
        self.assertEqual((b["argv"], b["restart_of"]), (V2, "s-r1"))
        self.assertEqual(b["mounts"]["box"]["to"], "a/box")
        r = done(self.tdir(node, "s-r1"))["result"]
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["diff"]["argv"], {"old": V1, "new": V2})
        self.assertEqual(r["diff"]["mounts"], {"old": {}, "new": {"box": "a/box"}})
        self.assertIn("reload", r["msg"])
        self.assertIn("v2", r["msg"])
        self.wait_for(lambda: self.state(node, "s-r1") == "ended")

    def test_plain_restart_still_uses_birth(self):
        node = self.setup_v1()
        self.set_tasks(node, [{"name": "s", "mode": "keep", "argv": V2}])
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r1"), "restart")
        self.assertEqual(self.tick()["started"], ["s-r2"])
        self.assertEqual(read_json(os.path.join(self.tdir(node, "s-r2"), "birth.json"))["argv"], V1)
        self.assertNotIn("diff", done(self.tdir(node, "s-r1"))["result"])

    def test_reload_refused_without_kill(self):
        node = self.setup_v1()
        td = self.tdir(node, "s-r1")
        cases = [
            ({"op": "restart", "reload": "yes"}, None, "reload 要是 true 或 false"),
            ({"op": "restart", "reload": True}, [{"name": "other", "argv": V2}], "沒有名為 s 的項目"),
            ({"op": "restart", "reload": True}, [{"name": "s", "argv": "v2"}], "不合格"),
        ]
        for ctl, tasks, want in cases:
            if tasks is not None:
                self.set_tasks(node, tasks)
            write_json(os.path.join(td, "ctl.json"), ctl)
            self.tick()
            self.assertEqual(read_json(os.path.join(node, ".aos", "round.json"))["ctl"],
                             [{"tid": "s-r1", "op": "restart", "ok": False}])
            self.tock()
            r = done(td)["result"]
            self.assertIn(want, r["msg"])
            self.assertIn("沒 kill", r["msg"])
            self.assertEqual(self.state(node, "s-r1"), "live")
            self.assertFalse(os.listdir(os.path.join(node, ".aos", "spawn")) if os.path.isdir(
                os.path.join(node, ".aos", "spawn")) else [])
        # tasks.json 讀不懂
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{bad")
        write_json(os.path.join(td, "ctl.json"), {"op": "restart", "reload": True})
        self.tick()
        self.assertIn("tasks.json 讀不懂", done(td)["result"]["msg"])
        self.assertEqual(self.state(node, "s-r1"), "live")

    def test_reload_carries_dynamic_mounts(self):
        os.makedirs(os.path.join(self.root, "c", "inbox"))
        node = self.setup_v1()
        td = self.tdir(node, "s-r1")
        aos7_mount.request(td, "c/inbox")
        self.tick()   # 審核加掛
        self.assertTrue(read_json(os.path.join(td, "birth.json"))["mounts"]["c_inbox"]["dyn"])
        self.tock()
        self.set_tasks(node, [{"name": "s", "mode": "keep", "argv": V2}])
        self.prog("aos7-ctl", "task", td, "restart", "--reload")
        self.assertEqual(self.tick()["started"], ["s-r3"])
        m = read_json(os.path.join(self.tdir(node, "s-r3"), "birth.json"))["mounts"]
        self.assertEqual((m["c_inbox"]["to"], m["c_inbox"]["dyn"]), ("c/inbox", True))
        self.assertNotIn("mounts", done(td)["result"]["diff"])   # 加掛的兩邊都有，不算差異
        # 再 plain restart 一次：dyn 標記照樣帶著
        self.wait_for(lambda: self.state(node, "s-r3") == "live")
        self.tock()
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r3"), "restart")
        self.assertEqual(self.tick()["started"], ["s-r4"])
        self.assertTrue(read_json(os.path.join(self.tdir(node, "s-r4"), "birth.json"))["mounts"]["c_inbox"]["dyn"])

    def test_ctl_reload_only_for_restart(self):
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-ctl"), "task", self.root, "kill", "--reload"],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.root, "ctl.json")))


if __name__ == "__main__":
    unittest.main()
