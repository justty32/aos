"""〔audit〕稽核包：包裝程式 aos7-audit 讓 Python 任務的寫入記進 writes.jsonl；沒包的任務不記。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

from base import MODULES, CoreCase, DaemonCase  # noqa: E402
from aos7_taskside import read_jsonl  # noqa: E402
sys.path.insert(0, os.path.join(MODULES, "audit"))
import aos7_audit  # noqa: E402

AUDIT = os.path.join(MODULES, "audit", "aos7-audit")
WRITE = "open('out.txt', 'w').write('x')"


class TestAuditWrapper(CoreCase):
    """〔audit〕aos7-audit -- <argv>：設 AOS7_AUDIT 與 PYTHONPATH 再起 argv（F55）。"""

    def test_wrapped_python_task_writes_recorded(self):
        node = self.mknode("a", [{"name": "w", "argv": [sys.executable, AUDIT, "--", sys.executable, "-c", WRITE]},
                                 {"name": "p", "argv": [sys.executable, "-c", WRITE.replace("out", "plain")]}])
        self.tick()
        self.wait_ended(node, "w")
        self.wait_ended(node, "p")
        self.assertEqual(self.exit_of(node, "w")["code"], 0, self.exit_of(node, "w"))
        recs = read_jsonl(os.path.join(self.slot(node, "w"), "writes.jsonl"))
        hits = [r for r in recs if str(r.get("path", "")).endswith(os.path.join("a", "out.txt"))]
        self.assertTrue(hits, "包裝過的任務寫檔沒記到：%r" % recs)
        self.assertTrue(all(r.get("ok") for r in hits), hits)
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "p"), "writes.jsonl")), "沒包的任務也記了")


# 任務：起來先標 ready、等 release，再寫巢狀 node 裡的檔與自己 node 的檔
LATE = ("import pathlib, time\np = pathlib.Path\np('ready').write_text('1')\n"
        "while not p('release').exists(): time.sleep(0.02)\n"
        "p('nested/result.txt').write_text('x')\np('own.txt').write_text('x')\n")


class TestAuditRegistration(DaemonCase):
    """〔audit〕登記邊界跟著 nodes.json 走：任務執行中才登記的巢狀 node 也算別人的（A4-05）。"""

    def test_nested_registered_while_running(self):
        node = self.mknode("a", [{"name": "w", "mode": "once",
                                  "argv": [sys.executable, AUDIT, "--", sys.executable, "-c", LATE]}])
        nested = self.mknode("a/nested", [])
        d = self.start_daemon(register=["a"])
        self.wait_for(lambda: os.path.exists(os.path.join(node, "ready")))
        self.assertTrue(self.wait_receipt(self.ctl("register", "a/nested"))["result"]["ok"])
        with open(os.path.join(node, "release"), "w") as f:
            f.write("go")
        self.wait_for(lambda: os.path.exists(os.path.join(node, "own.txt")))
        recs = read_jsonl(os.path.join(self.slot(node, "w"), "writes.jsonl"))
        ok = {os.path.basename(str(r.get("path"))): r.get("ok") for r in recs}
        self.assertEqual((ok.get("result.txt"), ok.get("own.txt")), (False, True), recs)
        bad = [r["path"] for _, r in aos7_audit.scan(self.root)["bad"]]
        self.assertEqual(bad, [os.path.join(os.path.realpath(nested), "result.txt")])
        self.stop_daemon(d)


if __name__ == "__main__":
    unittest.main()
