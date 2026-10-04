"""〔subd〕子 daemon 包：包裝程式 aos7-subd 起子 daemon——所有權（stop-guard.json＋owner.json）、allow-stop、stopped.json、
人手重開、子根位置檢查與重複認領（從 tests/test_subdaemon_modules.py 拆出；原本由核心 tick 做，現在由包裝程式做）。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

from base import MODULES, SLEEP, DaemonCase  # noqa: E402
import aos7_proc  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

SUBD = os.path.join(MODULES, "subd", "aos7-subd")
# 子 daemon 任務：先往子根的 ctl/ 寫 register（子 daemon 還沒起也行），再 exec 子 daemon
BOOT = ["sh", "-c", 'aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by boot > /dev/null && exec aos7-daemon "$AOS7_SUBROOT"']


def subd(sub, *cmd, allow_stop=False):
    """tasks.json 的 argv：aos7-subd <sub> [--allow-stop] -- cmd..."""
    return [sys.executable, SUBD, sub] + (["--allow-stop"] if allow_stop else []) + ["--"] + list(cmd)


class SubCase(DaemonCase):
    def setup_child(self, allow_stop=False):
        a = self.mknode("a", [{"name": "sub", "mode": "keep", "argv": subd("a/sub", *BOOT, allow_stop=allow_stop)}],
                        interval_ms=100)
        self.sub = os.path.join(a, "sub")
        n1 = self.mknode("a/sub/n1", [{"name": "s", "mode": "keep", "argv": SLEEP}], interval_ms=100)
        p = self.start_daemon(register=["a"])
        self.wait_for(lambda: self.node_round("n1", self.sub) >= 2, 20, "子 daemon 沒跑起來")
        return a, n1, p

    def owner_json(self):
        return read_json(os.path.join(self.sub, ".aosd", "owner.json"))

    def guard(self):
        return read_json(os.path.join(self.sub, ".aosd", "stop-guard.json"))

    def out_log(self, node, slot):
        try:
            with open(os.path.join(self.slot(node, slot), "out.log"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""


class TestOwnership(SubCase):
    """〔subd〕子 daemon 所有權（F50）：包裝程式寫 stop-guard.json 與 owner.json，核心只看守門檔。"""
    def test_owner_blocks_and_stop_refused(self):
        a, n1, p = self.setup_child()
        ow = self.owner_json()
        self.assertEqual(ow["owner"], {"node": "a", "tid": "sub", "allow_stop": False})
        self.assertEqual(ow["daemon"]["pid"], self.status(self.sub)["pid"])
        self.assertIs(self.guard()["allow"], False)
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
        write_json(os.path.join(self.slot(a, "sub"), "ctl.json"), {"op": "kill", "run": self.birth(a, "sub")["run"], "by": "t"})
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15, "子 daemon 沒被收")
        self.wait_for(lambda: not aos7_proc.pid_alive(child_task), 15, "子 daemon 的任務沒被帶走")

    def test_allow_stop_writes_stopped_and_parent_does_not_restart(self):
        """允許的 stop：包裝程式寫 stopped.json；父 keep 再起它時包裝程式退出碼 1（總結 ended 看得到）、子 daemon 沒起；
        刪掉 stopped.json 就再起。以前是父 tick 不起、記 tasks_error（核心不再知道子根）。"""
        a, n1, p = self.setup_child(allow_stop=True)
        child_pid = self.status(self.sub)["pid"]
        r = self.wait_receipt(self.ctl("stop", "--kill", root=self.sub))
        self.assertTrue(r["result"]["ok"], r)
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15)
        self.wait_for(lambda: os.path.exists(os.path.join(self.sub, ".aosd", "stopped.json")), 10, "沒寫 stopped.json")
        self.wait_for(lambda: any(e.get("code") == 1 for e in self.last_round(a).get("ended", [])
                                  if e.get("run", "").startswith("sub#")), 10, "父 keep 再起時包裝程式沒擋下")
        self.assertIn("stop", self.out_log(a, "sub"))
        self.assertTrue(self.status(self.sub).get("stopped"), "被擋時子 daemon 起來了")
        os.remove(os.path.join(self.sub, ".aosd", "stopped.json"))
        self.wait_for(lambda: (self.status(self.sub).get("pid") or 0) not in (0, child_pid)
                      and not self.status(self.sub).get("stopped"), 15, "刪掉 stopped.json 後沒再起")

    def test_manual_restart_keeps_owner_block(self):
        """人手直接起 aos7-daemon（繞過包裝）：守門檔與 owner 塊照舊留著（核心不碰它們），stopped.json 也留著
        （刪不刪由人決定；刪了父 keep 才會再起它）。以前 daemon 起來時會更新 owner.json 的 daemon 塊、刪 stopped.json。"""
        a, n1, p = self.setup_child(allow_stop=True)
        child_pid = self.status(self.sub)["pid"]
        self.wait_receipt(self.ctl("pause", "a"))   # 父那邊先別再起它
        self.wait_receipt(self.ctl("stop", "--kill", root=self.sub))
        self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15)
        q = self.start_daemon(root=self.sub)       # 人手重開：不經包裝程式
        self.wait_for(lambda: self.status(self.sub).get("pid") == q.pid, 10)
        ow = self.owner_json()
        self.assertEqual(ow["owner"], {"node": "a", "tid": "sub", "allow_stop": True})
        self.assertIs(self.guard()["allow"], True)
        self.assertTrue(os.path.exists(os.path.join(self.sub, ".aosd", "stopped.json")))


class TestSubrootChecks(SubCase):
    """〔subd〕subroot 位置檢查與重複認領（F50）：不合的由包裝程式擋下（退出碼 1、out.log 說明），不起 argv。"""
    def test_subroot_rules(self):
        a = self.mknode("a", [{"name": "x", "argv": subd("a", *SLEEP)},
                              {"name": "y", "argv": subd("b", *SLEEP)},
                              {"name": "z", "argv": subd("a/reg", *SLEEP)},
                              {"name": "s1", "argv": subd("a/s", *SLEEP)},
                              {"name": "s2", "argv": subd("a/s", *SLEEP)}])
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), {"nodes": {"a": {}, "a/reg/n": {}}})
        out = self.tick()
        self.assertEqual(sorted(out["started"]), ["s1#1", "s2#1", "x#1", "y#1", "z#1"])
        for n in ("x", "y", "z"):
            self.assertEqual(self.wait_ended(a, n)["code"], 1, n)
        self.assertIn("底下", self.out_log(a, "x") + self.out_log(a, "y"))
        self.assertIn("包住了父 daemon 已登記的 node", self.out_log(a, "z"))
        # 同一個子根兩項：一項拿到 subd.lock 起了，另一項退出碼 1（已經有別的 aos7-subd 認領）
        self.wait_for(lambda: self.exit_of(a, "s1") or self.exit_of(a, "s2"), 10, "重複認領沒被擋")
        loser = "s1" if self.exit_of(a, "s1") else "s2"
        winner = "s2" if loser == "s1" else "s1"
        self.assertEqual(self.exit_of(a, loser)["code"], 1)
        self.assertIn("認領", self.out_log(a, loser))
        self.assertIsNone(self.exit_of(a, winner))
        pid = self.wait_pid(a, winner)["pid"]
        kids = [int(c) for c in open("/proc/%d/task/%d/children" % (pid, pid)).read().split()]
        self.assertTrue(kids, "包裝程式沒起子程序")
        with open("/proc/%d/environ" % kids[0], "rb") as f:
            env = f.read().split(b"\0")
        self.assertIn(("AOS7_SUBROOT=" + os.path.join(a, "s")).encode(), env)


if __name__ == "__main__":
    unittest.main()
