"""〔subd〕子 daemon 的所有權（2.7、Q5、K-08 的 owner／daemon 兩塊）、subroot 檢查（從 tests/test_subdaemon_modules.py 拆出；counter／歷史 module 的案例搬到 modules/tests/）。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base、_matrix
import os
import subprocess
import sys
import time
import unittest

from base import SLEEP, DaemonCase
import aos7_proc
from aos7_fs import read_json, write_json

# 子 daemon 任務：先往子根的 ctl/ 寫 register（子 daemon 還沒起也行），再 exec 子 daemon
CHILD = ["sh", "-c", 'aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by boot > /dev/null && exec aos7-daemon "$AOS7_SUBROOT"']


class SubCase(DaemonCase):
    def setup_child(self, allow_stop=None):
        item = {"name": "sub", "mode": "keep", "argv": CHILD, "subroot": "a/sub"}
        if allow_stop is not None:
            item["allow_stop"] = allow_stop
        a = self.mknode("a", [item], interval_ms=100)
        self.sub = os.path.join(a, "sub")
        n1 = self.mknode("a/sub/n1", [{"name": "s", "mode": "keep", "argv": SLEEP}], interval_ms=100)
        p = self.start_daemon(register=["a"])
        self.wait_for(lambda: self.node_round("n1", self.sub) >= 2, 20, "子 daemon 沒跑起來")
        return a, n1, p

    def owner_json(self):
        return read_json(os.path.join(self.sub, ".aosd", "owner.json"))


class TestOwnership(SubCase):
    """〔subd〕子 daemon 所有權（F50）。"""
    def test_owner_blocks_and_stop_refused(self):
        a, n1, p = self.setup_child()
        ow = self.owner_json()
        self.assertEqual(ow["owner"], {"node": "a", "tid": "sub", "allow_stop": False})
        self.assertEqual(ow["daemon"]["pid"], self.status(self.sub)["pid"])
        r = self.wait_receipt(self.ctl("stop", root=self.sub))
        self.assertFalse(r["result"]["ok"])
        self.assertIn("屬於 node a", r["result"]["msg"])
        # 父 daemon 不收子根底下的 node
        r = self.wait_receipt(self.ctl("register", "a/sub/n1"))
        self.assertFalse(r["result"]["ok"])
        self.assertIn("daemon a/sub", r["result"]["msg"])

    def test_parent_kill_takes_child_tasks(self):
        a, n1, p = self.setup_child()
        child_task = self.wait_pid(n1, "s")["pid"]
        child_pid = self.status(self.sub)["pid"]
        write_json(os.path.join(self.slot(a, "sub"), "ctl.json"), {"op": "kill", "by": "t"})
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15, "子 daemon 沒被收")
        self.wait_for(lambda: not aos7_proc.pid_alive(child_task), 15, "子 daemon 的任務沒被帶走")

    def test_allow_stop_writes_stopped_and_parent_does_not_restart(self):
        a, n1, p = self.setup_child(allow_stop=True)
        child_pid = self.status(self.sub)["pid"]
        r = self.wait_receipt(self.ctl("stop", "--kill", root=self.sub))
        self.assertTrue(r["result"]["ok"], r)
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15)
        self.assertTrue(os.path.exists(os.path.join(self.sub, ".aosd", "stopped.json")))
        self.wait_for(lambda: any("stop" in e for e in self.last_round(a).get("tasks_error", [])), 10,
                      "父 tick 沒擋下有 stopped.json 的子根")
        os.remove(os.path.join(self.sub, ".aosd", "stopped.json"))
        self.wait_for(lambda: (self.status(self.sub).get("pid") or 0) not in (0, child_pid)
                      and not self.status(self.sub).get("stopped"), 15, "刪掉 stopped.json 後沒再起")

    def test_manual_restart_keeps_owner_block(self):
        a, n1, p = self.setup_child(allow_stop=True)
        child_pid = self.status(self.sub)["pid"]
        self.wait_receipt(self.ctl("pause", "a"))   # 父那邊先別再起它
        self.wait_receipt(self.ctl("stop", "--kill", root=self.sub))
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15)
        q = self.start_daemon(root=self.sub)       # 人手重開：沒有 owner 環境變數
        self.wait_for(lambda: self.status(self.sub).get("pid") == q.pid, 10)
        ow = self.owner_json()
        self.assertEqual(ow["owner"], {"node": "a", "tid": "sub", "allow_stop": True})
        self.assertEqual(ow["daemon"]["pid"], q.pid)
        self.assertFalse(os.path.exists(os.path.join(self.sub, ".aosd", "stopped.json")))


class TestSubrootChecks(DaemonCase):
    """〔subd〕subroot 位置檢查與認領（F50）。"""
    def test_subroot_rules(self):
        a = self.mknode("a", [{"name": "x", "argv": ["true"], "subroot": "a"},
                              {"name": "y", "argv": ["true"], "subroot": "b"},
                              {"name": "z", "argv": ["true"], "subroot": "a/reg"},
                              {"name": "s1", "argv": SLEEP, "subroot": "a/s"},
                              {"name": "s2", "argv": SLEEP, "subroot": "a/s"}])
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), {"nodes": {"a": {}, "a/reg/n": {}}})
        out = self.tick()
        self.assertEqual(out["started"], ["s1#1"])
        errs = " ".join(self.round_json(a)["tasks_error"])
        self.assertIn("底下", errs)
        self.assertIn("包住了父 daemon 已登記的 node", errs)
        self.assertIn("已經有別項認領", errs)
        with open("/proc/%d/environ" % self.wait_pid(a, "s1")["pid"], "rb") as f:
            env = f.read().split(b"\0")
        self.assertIn(b"AOS7_OWNER_TID=s1", env)
        self.assertIn(("AOS7_SUBROOT=" + os.path.join(a, "s")).encode(), env)


if __name__ == "__main__":
    unittest.main()
