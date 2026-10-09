import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ENTRY = Path(__file__).resolve().parents[1] / "aos7-diag"

TOP = ENTRY.parents[2]
ARCHIVE = TOP / "archive/llmdiag/aos7-llmdiag"
STUB = TOP / "modules/llmdiag/aos7-llmdiag"
BYTECODE_BEFORE = set(ENTRY.parent.glob("__pycache__/aos7_diag_llm*.pyc"))


def put(node, relative, text):
    path = node / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot(node):
    result = {}
    for path in [node, *node.rglob("*")]:
        mode = path.lstat().st_mode
        if path.is_symlink():
            content = ("link", os.readlink(path))
        else:
            content = None if path.is_dir() else path.read_bytes()
        result[str(path.relative_to(node))] = (mode & 0o7777, content)
    return result


class LlmdiagTests(unittest.TestCase):
    def run_entry(self, node):
        return subprocess.run([sys.executable, str(ENTRY), "--llm", str(node)],
                              capture_output=True, text=True, check=False)

    def test_sorted_tables_and_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            node = Path(temporary) / "node"
            node.mkdir()
            put(node, "llmcall/z/rawcall/request.json", "{}")
            put(node, "llmcall/z/rawcall/raw.json", "{broken")
            put(node, "llmcall/a/wait/request.json", "{}")
            put(node, "llmcall/a/done/request.json", "{}")
            put(node, "llmcall/a/done/receipt.json", "{broken")
            put(node, "llmcall/a/bad/request.json", "{broken")
            put(node, "llmcall/a/list/request.json", "[]")
            put(node, "llmcall/a/nan/request.json", '{"value":NaN}')
            put(node, "jobs/z_req_ABCDEF12/frame.json",
                '{"phase":"halted","halt":{"kind":"z","why":"late"}}')
            put(node, "jobs/a_req_89abcdef/frame.json",
                '{"phase":"halted","halt":{"kind":"a","why":"pending"}}')
            put(node, "jobs/a_req_123456789/frame.json", '{"phase":"halted"}')
            put(node, "jobs/a_req_12345678/frame.json", '{"phase":"running"}')
            put(node, "jobs/a_req_00000000/frame.json", "{broken")
            put(node, "jobs/missing_12345678/frame.json", '{"phase":"halted"}')
            (node / "author/req/a_req").mkdir(parents=True)
            (node / "author/req/z_req").mkdir(parents=True)
            put(node, "budget/z/ledger.json", '{"inflight":3}')
            put(node, "budget/a/ledger.json", '{"inflight":2}')
            put(node, "budget/bool/ledger.json", '{"inflight":true}')
            put(node, "budget/zero/ledger.json", '{"inflight":0}')
            put(node, "budget/bad/ledger.json", "{broken")
            put(node, "budget/list/ledger.json", "[]")
            before = snapshot(node)
            result = self.run_entry(node)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout.count("\n"), 1)
            self.assertTrue(result.stdout.endswith("\n"))
            self.assertEqual(json.loads(result.stdout), {
                "v": 1,
                "llmcall_pending": [
                    {"budget": "a", "call_id": "wait", "stage": "request"},
                    {"budget": "z", "call_id": "rawcall", "stage": "raw"},
                ],
                "author_halted": [
                    {"job": "a_req_89abcdef", "rid": "a_req",
                     "kind": "a", "why": "pending"},
                    {"job": "z_req_ABCDEF12", "rid": "z_req",
                     "kind": "z", "why": "late"},
                ],
                "budget_inflight": [
                    {"budget": "a", "inflight": 2},
                    {"budget": "z", "inflight": 3},
                ],
            })
            self.assertEqual(snapshot(node), before)
            self.compare_archive(node)

    def test_non_directory_exits_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file"
            path.write_text("untouched", encoding="utf-8")
            result = self.run_entry(path)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(path.read_text(encoding="utf-8"), "untouched")

    def compare_archive(self, node):
        if not ARCHIVE.exists():
            self.skipTest("archive 不在")
        before = snapshot(node)
        old = subprocess.run([sys.executable, str(ARCHIVE), str(node)], capture_output=True)
        new = subprocess.run([str(ENTRY), "--llm", str(node)], capture_output=True)
        self.assertEqual((old.returncode, new.returncode), (0, 0))
        self.assertEqual((old.stderr, new.stderr), (b"", b""))
        self.assertEqual(old.stdout, new.stdout)
        self.assertEqual(snapshot(node), before)

    def test_archive_bytes(self):
        self.compare_archive(TOP / "packs/author/examples/aos-module-diag/fixture")
        with tempfile.TemporaryDirectory() as temporary:
            node = Path(temporary)
            self.compare_archive(node)
            put(node, "budget/only/ledger.json", '{"inflight":4}')
            self.compare_archive(node)

    @unittest.skipIf(os.geteuid() == 0, "root 可讀 chmod 000")
    def test_unreadable(self):
        for relative in ("llmcall", "llmcall/a/c/request.json", "budget/a/ledger.json"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as temporary:
                node = Path(temporary)
                put(node, "llmcall/a/c/request.json", "{}")
                put(node, "budget/a/ledger.json", '{"inflight":2}')
                path = node / relative
                mode = path.stat().st_mode
                path.chmod(0)
                try:
                    result = self.run_entry(node)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertTrue(result.stderr.startswith("aos7-diag: 不確定："))
                    self.assertEqual(len(result.stderr.splitlines()), 1)
                finally:
                    path.chmod(mode)

    def test_symlink_loop_is_unsure(self):
        """os.stat 判 errno：ELOOP 不當「不存在」（舊 Path.exists／is_dir 會吞掉）。"""
        cases = {
            "receipt": "llmcall/a/c/receipt.json",
            "raw": "llmcall/a/c/raw.json",
            "child": "llmcall/a/loop",
            "req": "author/req/r",
        }
        for name, relative in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                node = Path(temporary)
                put(node, "llmcall/a/c/request.json", "{}")
                put(node, "jobs/r_12345678/frame.json", '{"phase":"halted"}')
                (node / "author/req").mkdir(parents=True)
                loop = node / relative
                loop.symlink_to(loop.name)
                result = self.run_entry(node)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr.startswith("aos7-diag: 不確定："), result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_dangling_symlink_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            node = Path(temporary)
            put(node, "llmcall/a/c/request.json", "{}")
            (node / "llmcall/a/c/receipt.json").symlink_to("nowhere")
            self.compare_archive(node)

    def test_messages_one_line_and_specific(self):
        with tempfile.TemporaryDirectory() as temporary:
            odd = Path(temporary) / "a\nb"
            cases = [
                (["--llm", str(odd)], 2, "不是資料夾"),
                (["--lmm", "x"], 2, "不認得的選項 --lmm"),
                (["--llm"], 2, "--llm 後面要恰好一個 node 資料夾"),
                (["a", "b", "c"], 2, "參數太多"),
                ([str(odd)], 2, "不是資料夾"),
            ]
            for args, code, text in cases:
                with self.subTest(args=args):
                    result = subprocess.run([str(ENTRY), *args], capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
                    self.assertIn(text, result.stderr)
                    self.assertIn("。", result.stderr)
            dash = Path(temporary) / "--help"
            put(dash, "budget/b/ledger.json", '{"inflight":1}')
            result = subprocess.run([str(ENTRY), "--llm", "--help"], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"budget_inflight":[{"budget":"b","inflight":1}]', result.stdout)

    def test_root_mode_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            plain = subprocess.run([str(ENTRY), temporary], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertEqual(json.loads(plain.stdout)["nodes"], {})
            if os.geteuid() != 0:
                put(Path(temporary), ".aosd/status.json", "{}")
                status = Path(temporary) / ".aosd/status.json"
                status.chmod(0)
                try:
                    result = subprocess.run([str(ENTRY), temporary], capture_output=True, text=True)
                finally:
                    status.chmod(0o600)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertTrue(result.stderr.startswith("aos7-diag: 不確定："), result.stderr)

    def test_cli_and_bytecode(self):
        caches = lambda: set(ENTRY.parent.glob("__pycache__/aos7_diag_llm*.pyc"))
        before = BYTECODE_BEFORE
        for args, code in ((["--help"], 0), (["-h"], 0), ([], 2), (["--llm"], 2),
                           (["--llm", "x", "y"], 2), (["--bogus"], 2)):
            result = subprocess.run([str(ENTRY), *args], capture_output=True)
            self.assertEqual(result.returncode, code, result.stderr)
            if code == 0:
                self.assertEqual(result.stderr, b"")
                self.assertLessEqual(len(result.stdout.splitlines()), 15)
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(self.run_entry(temporary).returncode, 0)
        self.assertEqual(caches(), before)
        for args, code in ((["x"], 1), (["--help"], 0)):
            result = subprocess.run([str(STUB), *args], capture_output=True)
            self.assertEqual(result.returncode, code)
            if code == 1:
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertIn(b"aos7-diag --llm", result.stderr)
            else:
                self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
