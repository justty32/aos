"""〔diag〕診斷包：aos7-diag 按需重算判不出的槽、照抄 status 的錯誤並給恢復步驟；它是唯讀的。

從 tests/core/test_matrix_misc.py 的 TestDiagnostics（A2-08）搬來改寫：核心 status 不再放 `uncertain`，改由這個工具按需算。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import json  # noqa: E402
import subprocess  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

from base import MODULES, SLEEP  # noqa: E402
from _matrix import Fault, MatrixCase  # noqa: E402
import aos7_daemon_timeline  # noqa: E402
import aos7_fs  # noqa: E402
import aos7_proc  # noqa: E402
from aos7_fs import write_json  # noqa: E402

DIAG = os.path.join(MODULES, "diag", "aos7-diag")


class _FakeDaemon:
    def __init__(self, root):
        self.root = root


class TestDiag(MatrixCase):
    """〔diag〕aos7-diag 的輸出（F53）。"""

    def diag(self, *args, env=None):
        p = subprocess.run([sys.executable, DIAG, self.root, *args], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_timeline_err_keeps_kind_prefix(self):
        """時間線的長錯誤（hold 格式）保留開頭、≤ 320 字、kind 分欄；diag 照抄並對到恢復步驟（找持鎖者、不要 unlink 鎖檔）。"""
        node = self.mknode("a")
        tl = aos7_daemon_timeline.Timeline(_FakeDaemon(self.root), "a", None)
        tl.err("action-lock", None, "stale-holder-unverified：" + "x" * 2000, kind="stale-holder-unverified")
        e = tl.last_error
        self.assertTrue(e["why"].startswith("stale-holder-unverified"), e["why"][:80])
        self.assertLessEqual(len(e["why"]), 320)
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), {"nodes": {"a": {}}})
        write_json(os.path.join(self.root, ".aosd", "status.json"), {"nodes": {"a": {"phase": "error", "last_error": e}}})
        out = self.diag()["nodes"]["a"]
        self.assertEqual(out["last_error"]["kind"], "stale-holder-unverified")
        self.assertTrue(any("fuser" in h["hint"] for h in out["hints"]), out["hints"])
        self.assertTrue(os.path.isdir(node))

    def test_unsure_listed(self):
        """starttime 讀不到的任務：tock 總結的 errors 留 unsure（核心），diag 按需重算也列在 uncertain、給恢復步驟。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.itock()
        self.itick()
        with mock.patch.object(aos7_proc, "proc_starttime", lambda pid: None), \
                mock.patch.object(aos7_fs, "proc_starttime", lambda pid: None):
            lr = self.itock()
        self.assertIn("k#1", lr["alive"])
        self.assertTrue([x for x in self.errors_for(lr, "k") if x.get("kind") == "unsure" and x.get("why")], lr.get("errors"))
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), {"nodes": {"a": {}}})
        runner = self.birth(node, "k")["runner"]["pid"]
        f = Fault("proc-stat:/proc/%d/stat:EIO;proc-stat:/proc/%d/stat:EIO" % (pid, runner))
        try:
            out = self.diag("a", env=f.env)["nodes"]["a"]
            f.check_rules()   # task 與 runner 兩條 proc-stat 各自要中（T8-07）
        finally:
            f.close()
        self.assertEqual([(u["slot"], u["run"]) for u in out["uncertain"]], [("k", 1)], out)
        self.assertTrue(out["hints"] and out["hints"][0]["slot"] == "k", out["hints"])

    def test_diag_is_read_only(self):
        """跑 diag 前後空間裡的檔案（名字、大小、mtime、內容）完全不變。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}, {"name": "j", "argv": ["true"]}])
        self.itick()
        self.wait_pid(node, "k")
        self.settle(node, "j")
        self.itock()
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), {"nodes": {"a": {}}})
        with open(os.path.join(self.slot(node, "j"), "birth.json"), "w") as fh:
            fh.write("{")   # 一個壞掉的槽：diag 只列出來、給步驟，不碰它

        def snap():
            out = {}
            for d, _ds, ns in os.walk(self.root):
                for n in ns:
                    p = os.path.join(d, n)
                    st = os.lstat(p)
                    with open(p, "rb") as fh:
                        out[p] = (st.st_size, st.st_mtime_ns, fh.read())
            return out
        before = snap()
        out = self.diag()
        self.assertEqual(snap(), before, "aos7-diag 改了檔案")
        self.assertTrue(any(u["slot"] == "j" and "birth.json 壞了" in u["why"] for u in out["nodes"]["a"]["uncertain"]))


if __name__ == "__main__":
    unittest.main()
