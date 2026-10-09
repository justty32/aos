import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ENTRY = Path(__file__).resolve().parents[1] / "aos7-llmdiag"


def put(node, relative, text):
    path = node / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot(node):
    result = {}
    for path in [node, *node.rglob("*")]:
        result[str(path.relative_to(node))] = (
            path.stat().st_mode & 0o7777,
            None if path.is_dir() else path.read_bytes(),
        )
    return result


class LlmdiagTests(unittest.TestCase):
    def run_entry(self, node):
        return subprocess.run([sys.executable, str(ENTRY), str(node)],
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

    def test_non_directory_exits_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file"
            path.write_text("untouched", encoding="utf-8")
            result = self.run_entry(path)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(path.read_text(encoding="utf-8"), "untouched")


if __name__ == "__main__":
    unittest.main()
