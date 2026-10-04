"""〔audit〕稽核包：包裝程式 aos7-audit 讓 Python 任務的寫入記進 writes.jsonl；沒包的任務不記。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

from base import MODULES, CoreCase  # noqa: E402
from aos7_fs import read_jsonl  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
