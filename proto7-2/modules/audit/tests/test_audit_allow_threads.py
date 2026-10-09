"""〔audit〕通用巢狀邊界豁免（N-66）與各 thread 的寫入紀錄（R8-25）。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

from base import MODULES, DaemonCase  # noqa: E402
from aos7_taskside import read_jsonl  # noqa: E402
import aos7_proc  # noqa: E402

AUDIT = os.path.join(MODULES, "audit", "aos7-audit")
SUBD = os.path.join(MODULES, "subd", "aos7-subd")


class TestAuditAllow(DaemonCase):
    """〔audit〕豁免只放寬自己 node 裡的巢狀邊界，每次判定重讀環境。"""

    def run_python(self, code):
        node = self.mknode("a", [{"name": "w", "argv": [sys.executable, AUDIT, "--", sys.executable, "-c", code]}])
        self.tick()
        self.assertEqual(self.wait_ended(node, "w")["code"], 0)
        return read_jsonl(os.path.join(self.slot(node, "w"), "writes.jsonl"))

    def test_audit_wraps_subd_writes(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep",
                                  "argv": [sys.executable, AUDIT, "--", sys.executable, SUBD, "a/sub", "--",
                                           "sh", "-c", 'exec aos7-daemon "$AOS7_SUBROOT"']}])
        sub = os.path.join(node, "sub")
        d = self.start_daemon(register=["a"])
        child_pid = None
        try:
            child_pid = self.wait_for(lambda: self.status(sub).get("pid"), 20, "子 daemon 沒起來")
            owner = os.path.join(sub, ".aosd", "owner.json")
            self.wait_for(lambda: os.path.exists(owner))
            recs = read_jsonl(os.path.join(self.slot(node, "s"), "writes.jsonl"))
            hits = [r for r in recs if r.get("path", "").startswith(os.path.join(sub, ".aosd") + os.sep)]
            paths = {r["path"] for r in hits}
            for name in ("subd-life.json", "stop-guard.json", "owner.json", "status.json"):
                self.assertIn(os.path.join(sub, ".aosd", name), paths)
            self.assertTrue(all(r.get("ok") is True for r in hits), hits)
        finally:
            self.stop_daemon(d)
            if child_pid:
                self.wait_for(lambda: not aos7_proc.pid_alive(child_pid), 15, "父停了但子 daemon 還活著")

    def test_nested_without_allow_is_false(self):
        node = self.mknode("a")
        target = os.path.join(node, "sub2", ".aosd", "x")
        os.makedirs(os.path.dirname(target))
        recs = self.run_python("import os\nos.environ.pop('AOS7_AUDIT_ALLOW', None)\nopen(%r, 'w').close()" % target)
        hits = [r for r in recs if r.get("path") == target]
        self.assertTrue(hits)
        self.assertTrue(all(r.get("ok") is False for r in hits), hits)

    def test_allow_outside_node_is_ignored(self):
        outside = self.mknode("ab")  # 同前綴也不能算在 node a 裡
        target = os.path.join(outside, "x")
        recs = self.run_python("import os\nos.environ['AOS7_AUDIT_ALLOW'] = %r\nopen(%r, 'w').close()" % (outside, target))
        hits = [r for r in recs if r.get("path") == target]
        self.assertTrue(hits)
        self.assertTrue(all(r.get("ok") is False for r in hits), hits)

    def test_allow_dynamic_realpath_and_absolute_entries(self):
        node = self.mknode("a")
        sub = os.path.join(node, "sub2")
        os.makedirs(os.path.join(sub, ".aosd"))
        alias = os.path.join(node, "alias")
        os.symlink(sub, alias)
        target = os.path.join(sub, ".aosd", "x")
        code = """import os
target = %r
os.environ.pop('AOS7_AUDIT_ALLOW', None)
open(target, 'w').close()
os.environ['AOS7_AUDIT_ALLOW'] = os.pathsep.join([%r, %r])
open(target, 'w').close()
os.environ['AOS7_AUDIT_ALLOW'] = 'sub2'
open(target, 'w').close()
""" % (target, os.path.join(self.root, "ab"), alias)
        hits = [r for r in self.run_python(code) if r.get("path") == target]
        self.assertEqual([r.get("ok") for r in hits], [False, True, False], hits)


class TestAuditThreads(DaemonCase):
    """〔audit〕八個 thread 各寫五十個檔，不能因另一個 thread 正在記錄而漏掉。"""

    def test_all_thread_writes_recorded(self):
        code = """import threading
ready = threading.Barrier(8)
def write(i):
    ready.wait()
    for j in range(50):
        with open('thread-%d-%d.txt' % (i, j), 'w') as f:
            f.write('x')
threads = [threading.Thread(target=write, args=(i,)) for i in range(8)]
for t in threads: t.start()
for t in threads: t.join()
"""
        node = self.mknode("a", [{"name": "w", "argv": [sys.executable, AUDIT, "--", sys.executable, "-c", code]}])
        self.tick()
        self.assertEqual(self.wait_ended(node, "w")["code"], 0)
        want = {os.path.join(node, "thread-%d-%d.txt" % (i, j)) for i in range(8) for j in range(50)}
        self.assertTrue(all(os.path.isfile(p) for p in want), "任務沒有真的寫完四百個檔")
        recs = read_jsonl(os.path.join(self.slot(node, "w"), "writes.jsonl"))
        seen = {r.get("path") for r in recs if r.get("op") == "open"} & want
        self.assertEqual(len(seen), 400, "四百個寫入只記到 %d 個" % len(seen))


if __name__ == "__main__":
    unittest.main()
