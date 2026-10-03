"""掛載（S-23）與寫入紀錄的測試：tick 建掛載點、resolve、restart 照樣掛、argv 展開、aos7-ctl 吃掛載點、越界寫入抓得到。"""
import os
import subprocess
import sys
import unittest

from test_core import BIN, CoreCase, text  # 匯入 test_core 時 lib/ 已放進 sys.path

import aos7_audit  # noqa: E402
import aos7_ctl  # noqa: E402
import aos7_mount  # noqa: E402
from aos7_fs import env_with_bin, read_json, write_json  # noqa: E402

WRITE = "import sys; open(sys.argv[1], 'w').write('hi')"


class TestMount(CoreCase):
    def test_tick_makes_mounts(self):
        node = self.mknode("a", [{"name": "s", "argv": ["python3", "-c", WRITE, "$AOS7_TASK/mnt/box/hi.txt"],
                                  "mounts": {"box": "b/inbox", "bad": "../x", ".no": "b"}}])
        self.tick()
        td = self.tdir(node, "s-r1")
        self.wait_for(lambda: self.state(node, "s-r1") == "ended")
        m = read_json(os.path.join(td, "birth.json"))["mounts"]
        self.assertEqual(m["box"], {"to": "b/inbox", "at": os.path.join(td, "mnt", "box")})
        self.assertEqual(sorted(k for k in m if "error" in m[k]), ["?0", "?1"])   # 壞宣告記錯誤、不掛
        link = os.readlink(os.path.join(td, "mnt", "box"))
        self.assertFalse(os.path.isabs(link))                                   # 相對連結
        self.assertEqual(text(os.path.join(self.root, "b", "inbox", "hi.txt")), "hi")  # 目標自動建好、經掛載點寫進去
        self.assertEqual(read_json(os.path.join(td, "exit.json"))["code"], 0)

    def test_restart_keeps_mounts(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": ["python3", "-c", "import time; time.sleep(60)"],
                                  "mounts": {"box": "b/inbox"}}])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r1"), "restart")
        self.assertEqual(self.tick()["started"], ["s-r2"])
        m = read_json(os.path.join(self.tdir(node, "s-r2"), "birth.json"))["mounts"]
        self.assertEqual(m["box"]["to"], "b/inbox")
        self.assertTrue(os.path.isdir(os.path.join(self.tdir(node, "s-r2"), "mnt", "box")))

    def test_resolver(self):
        td = os.path.join(self.root, "t")
        write_json(os.path.join(td, "birth.json"),
                   {"mounts": aos7_mount.make(self.root, td, {"b": "x/b", "bi": "x/b/inbox", "d": ".aosd"})})
        r = aos7_mount.resolver(td)
        self.assertEqual(r("x/b/inbox/1.json"), os.path.join(td, "mnt", "bi", "1.json"))   # 最長的先
        self.assertEqual(r("x/b/.aos/round.json"), os.path.join(td, "mnt", "b", ".aos/round.json"))
        self.assertEqual(r("x/b"), os.path.join(td, "mnt", "b"))
        self.assertEqual(r(".aosd/ctl"), os.path.join(td, "mnt", "d", "ctl"))
        self.assertIsNone(r("x/bb"))
        self.assertIsNone(r("y"))
        self.assertIsNone(r("../x/b"))

    def test_ctl_accepts_mounted_dirs(self):
        os.makedirs(os.path.join(self.root, ".aosd", "ctl"))
        td = os.path.join(self.root, "t")
        aos7_mount.make(self.root, td, {"d": ".aosd", "c": ".aosd/ctl"})
        want = os.path.join(self.root, ".aosd", "ctl")
        for where in (self.root, os.path.join(td, "mnt", "d"), os.path.join(td, "mnt", "c")):
            p = aos7_ctl.daemon_ctl(where, "rescan", by="test")
            self.assertEqual(os.path.realpath(os.path.dirname(p)), want)


class TestMountRequest(CoreCase):
    """執行中加掛（M-6 選 (b)）：任務寫 mount-req/，下一個 tick 依 tasks.json 的 mount_allow 審核。"""

    def test_tick_serves_requests(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": ["python3", "-c", "import time; time.sleep(60)"],
                                  "mounts": {"box": "b/inbox"}}])
        t = read_json(os.path.join(node, ".aos", "tasks.json"))
        t["mount_allow"] = ["b", "c/inbox"]
        write_json(os.path.join(node, ".aos", "tasks.json"), t)
        self.tick()
        td = self.tdir(node, "s-r1")
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        self.assertEqual(aos7_mount.request(td, "b/inbox/x.json"), "mounted")
        self.assertEqual(aos7_mount.request(td, "c/inbox", why="test"), "pending")
        self.assertEqual(aos7_mount.request(td, "c/inbox"), "pending")             # 不重寫
        self.assertEqual(aos7_mount.request(td, "d/inbox"), "pending")             # 不在允許清單
        write_json(os.path.join(td, "mount-req", "box.json"), {"name": "box", "path": "b/other"})   # 名字撞
        write_json(os.path.join(td, "mount-req", "junk.json"), [])
        self.tick()
        summary = read_json(os.path.join(node, ".aos", "round.json"))["mounts"]
        self.assertEqual(sorted((str(m["name"]), m["ok"]) for m in summary),
                         [("None", False), ("box", False), ("c_inbox", True), ("d_inbox", False)])
        self.assertEqual(os.listdir(os.path.join(td, "mount-req")), [])
        self.assertTrue(read_json(os.path.join(td, "mount-done", "c_inbox.json"))["result"]["ok"])
        self.assertIn("mount_allow", read_json(os.path.join(td, "mount-done", "d_inbox.json"))["result"]["msg"])
        self.assertEqual(read_json(os.path.join(td, "birth.json"))["mounts"]["c_inbox"]["to"], "c/inbox")
        self.assertTrue(os.path.isdir(os.path.join(td, "mnt", "c_inbox")))
        self.assertEqual(aos7_mount.request(td, "c/inbox"), "mounted")
        self.assertTrue(aos7_mount.request(td, "d/inbox").startswith("refused"))
        # restart：加掛的也一起帶到新任務
        self.prog("aos7-ctl", "task", td, "restart")
        self.tick()
        self.assertEqual(sorted(read_json(os.path.join(self.tdir(node, "s-r3"), "birth.json"))["mounts"]),
                         ["box", "c_inbox"])


class TestAudit(CoreCase):
    """AOS7_AUDIT：任務的寫入記在 writes.jsonl；寫出自己的 node 與掛載點的會被標出來（只記不擋）。"""

    def tick_audit(self, nid):
        env = env_with_bin()
        env["AOS7_AUDIT"] = "1"
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-tick"), self.root, nid],
                           env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_audit_flags_writes_outside(self):
        self.mknode("b")
        self.mknode("a/kid")    # a 裡面巢狀的別的 node
        node = self.mknode("a", [
            {"name": "good", "argv": ["python3", "-c", WRITE, "$AOS7_TASK/mnt/box/ok.txt"], "mounts": {"box": "b/inbox"}},
            {"name": "own", "argv": ["python3", "-c", WRITE, "work.txt"]},
            {"name": "peek", "argv": ["python3", "-c", WRITE, os.path.join(self.root, "b", "x.txt")]},
            {"name": "kid", "argv": ["python3", "-c", WRITE, "kid/y.txt"]},
        ])
        self.tick_audit("a")
        for t in ("good-r1", "own-r1", "peek-r1", "kid-r1"):
            self.wait_for(lambda t=t: self.state(node, t) == "ended")
        au = aos7_audit.scan(self.root)
        bad = sorted((os.path.basename(d), os.path.relpath(r["path"], self.root)) for d, r in au["bad"])
        self.assertEqual(bad, [("kid-r1", "a/kid/y.txt"), ("peek-r1", "b/x.txt")])
        recs = text(os.path.join(self.tdir(node, "good-r1"), "writes.jsonl"))
        self.assertIn('"via"', recs)                       # 經過掛載點寫的，記得寫的時候用的路徑
        self.assertGreaterEqual(au["tasks"], 4)


if __name__ == "__main__":
    unittest.main()
