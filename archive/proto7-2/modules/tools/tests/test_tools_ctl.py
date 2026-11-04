"""〔tools〕工具包：aos7-ctl（固定檔名無損編碼、task 子命令）。

從 tests/core/test_matrix_a3.py 的 TestOwnerNames（A2-13、A3-06）與 tests/core/test_ctl.py 的 test_aos7_ctl_task 搬來，內容未改。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import contextlib
import errno
import fcntl
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest  # noqa: E402
from unittest.mock import patch

from base import BIN, SLEEP, CoreCase, DaemonCase  # noqa: E402
import aos7_ctl  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402,F401


# ---------- A3-06 ----------

class TestOwnerNames(DaemonCase):
    """〔tools〕aos7-ctl 的固定檔名無損編碼（A2-13、A3-06，F57）。"""
    def test_fixed_name_lossless(self):
        """A3-06：甲／乙、A/B 與 A+B、x? 與 x!（owner、by、node 各段）都編成不同檔名；很長的也不同、不超過 255 bytes。"""
        pairs = [("甲", "乙"), ("A/B", "A+B"), ("x?", "x!"), ("a.b", "a@b"), ("%41", "A"),
                 ("l" * 300 + "1", "l" * 300 + "2")]
        for a, b in pairs:
            self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", "a", a), aos7_ctl.fixed_name("cli", "pause", "a", b),
                                "owner %r 與 %r 撞名" % (a, b))
            self.assertNotEqual(aos7_ctl.fixed_name(a, "pause", "n"), aos7_ctl.fixed_name(b, "pause", "n"),
                                "by %r 與 %r 撞名" % (a, b))
            self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", a), aos7_ctl.fixed_name("cli", "pause", b),
                                "node %r 與 %r 撞名" % (a, b))
            for x in (a, b):
                self.assertLessEqual(len(aos7_ctl.fixed_name(x, "pause", x, x).encode()), 255)
        self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", "a", ""), aos7_ctl.fixed_name("cli", "pause", "a"))

    def test_non_ascii_owner_pauses_both_kept(self):
        """A3-06：daemon 沒起前送兩份 pause（owner 甲、乙），起來後兩個 owner 都在 paused.json。"""
        self.mknode("a", interval_ms=120)
        a = self.ctl("pause", "a", "--owner", "甲")
        b = self.ctl("pause", "a", "--owner", "乙")
        self.assertNotEqual(a, b, "不同 owner 的 pause 寫成同一個檔")
        self.start_daemon(register=["a"])
        self.wait_receipt(a)
        self.wait_receipt(b)
        owners = ((read_json(os.path.join(self.root, ".aosd", "paused.json"), {}) or {}).get("paused") or {}).get("a")
        self.assertEqual(sorted(owners or []), sorted(["甲", "乙"]))


# ---------- A3-03 ----------


class TestCtlTask(CoreCase):
    """〔tools〕aos7-ctl task 寫 ctl.json（F57）。"""
    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def test_aos7_ctl_task(self):
        """〔tools〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.prog("aos7-ctl", "task", self.slot(node, "s"), "kill", "why", "--run", "1")
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])



class TestCtlErrors(unittest.TestCase):
    """A10-09：用法錯不寫檔；壞輸入與讀寫故障維持不確定、不洩漏 traceback。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fx1-c-ctl-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def cli(self, *argv, env=None):
        return subprocess.run([sys.executable, "-B", os.path.join(BIN, "aos7-ctl"), *argv],
                              cwd=self.root, env=dict(os.environ, HOME=str(self.root), **(env or {})),
                              capture_output=True, text=True, timeout=10)

    def restart_node(self):
        node = self.root / "node"
        slot = node / ".aos/tasks/w"
        slot.mkdir(parents=True)
        write_json(str(slot / "birth.json"), {"run": 1, "name": "w", "argv": ["true"]})
        write_json(str(node / ".aos/tasks.json"), {"tasks": []})
        return node, slot

    def check_restart_error(self, result, code):
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt["ok"], receipt)
        self.check_error(subprocess.CompletedProcess(result.args, result.returncode, "", result.stderr), code)
        self.assertEqual(receipt["outcome"], "unknown" if code == 3 else "refused")
        return receipt

    def test_a10_09_restart_lock_busy_is_unknown(self):
        node, slot = self.restart_node()
        table = node / ".aos/tasks.json"
        before = table.read_bytes()
        with open(str(table) + ".lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.check_restart_error(self.cli("task", str(slot), "restart", "--id", "fx1-restart"), 3)
        self.assertEqual(table.read_bytes(), before)
        self.assertFalse((slot / "ctl.json").exists())

    def test_a10_09_restart_eio_is_unknown(self):
        node, slot = self.restart_node()
        table = node / ".aos/tasks.json"
        before = table.read_bytes(), (slot / "birth.json").read_bytes()
        for target, reload in ((slot / "birth.json", False), (table, False), (table, True)):
            with self.subTest(target=target.name, reload=reload):
                hits = self.root / "fault-hits"
                hits.write_text("")
                result = self.cli("task", str(slot), "restart", "--id", "fx1-restart",
                                  *(("--reload",) if reload else ()),
                                  env={"AOS7_TEST_FAULT": "open:%s:EIO" % target,
                                       "AOS7_TEST_FAULT_HITS": str(hits)})
                self.check_restart_error(result, 3)
                self.assertIn("open\tEIO\t%s" % target, hits.read_text())
                self.assertEqual((table.read_bytes(), (slot / "birth.json").read_bytes()), before)
                self.assertFalse((slot / "ctl.json").exists())

    def test_a10_09_restart_true_refusal_is_one(self):
        node, slot = self.restart_node()
        table = node / ".aos/tasks.json"
        before = table.read_bytes()
        # 可讀的表沒有 reload 定義＝確定拒絕；不存在的 birth 也是確定缺前提。
        self.check_restart_error(self.cli("task", str(slot), "restart", "--reload"), 1)
        (slot / "birth.json").unlink()
        self.check_restart_error(self.cli("task", str(slot), "restart"), 1)
        self.assertEqual(table.read_bytes(), before)
        self.assertFalse((slot / "ctl.json").exists())

    def check_error(self, result, code):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("aos7-ctl: " + ("不確定：" if code == 3 else "")))
        self.assertIn("。", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a10_09_bad_args_no_write(self):
        for args in (("--no-such-option",), ("daemon", "new", "register"),
                     ("daemon", "new", "register", "n", "--rounds", "bad"),
                     ("task", "new", "kill", "--reload"), ("add", "new", "{"),
                     ("add", "new", "[]"), ("add", "new", '{}', '[]')):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.check_error(result, 2)
                self.assertIn("例：", result.stderr)
                self.assertEqual(list(self.root.rglob("*")), [])

    def test_a10_09_unknown_birth_and_tasks(self):
        for kind in ("birth", "tasks"):
            with self.subTest(kind=kind):
                target = self.root / ("slot/birth.json" if kind == "birth" else "node/.aos/tasks.json")
                target.parent.mkdir(parents=True)
                target.write_text("{")
                args = ("task", str(target.parent), "kill") if kind == "birth" else (
                    "add", str(self.root / "node"), '{"name":"x","argv":["true"]}')
                self.check_error(self.cli(*args), 3)
                self.assertEqual(target.read_text(), "{")
                self.assertFalse((target.parent / "ctl.json").exists())

    def test_a10_09_oserror_no_traceback(self):
        blocked = self.root / "blocked"
        blocked.write_text("unchanged")
        for args in (("daemon", str(blocked), "register", "n"),
                     ("task", str(blocked), "kill", "--run", "1"),
                     ("add", str(blocked), '{}')):
            with self.subTest(args=args):
                self.check_error(self.cli(*args), 3)
                self.assertEqual(blocked.read_text(), "unchanged")
                self.assertEqual(list(self.root.rglob("*")), [blocked])
        # core 重現腳本的 write_json 邊界注入，不依賴 chmod／root 權限。
        with patch.object(aos7_ctl, "write_json", side_effect=OSError(errno.EIO, "fx1 write failure")), \
                contextlib.redirect_stderr(io.StringIO()) as err, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(aos7_ctl.main(["daemon", str(self.root), "register", "n"]), 3)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(err.getvalue().startswith("aos7-ctl: 不確定："))
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertEqual(list(self.root.rglob("*")), [blocked])

    def test_a10_09_unexpected_error_no_traceback(self):
        with patch.object(aos7_ctl, "daemon_ctl", side_effect=RuntimeError("fx1 unexpected")), \
                contextlib.redirect_stderr(io.StringIO()) as err, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(aos7_ctl.main(["daemon", str(self.root), "register", "n"]), 3)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(err.getvalue().startswith("aos7-ctl: 不確定："))
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertEqual(list(self.root.rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
