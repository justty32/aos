"""Behavior and read-only checks for the usage tool."""
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "bin" / "aos7-usage"


class UsageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.node = Path(temporary.name) / "node"
        self.node.mkdir()
        request = {"request": {"model": "m"}, "endpoint": "e", "holder": "h"}
        self.put("budget/a/ledger.json", {"used": 4})
        self.put("budget/b/ledger.json", {"used": 9})
        for call in ("c1", "c2", "c3", "c4", "c6", "c7"):
            self.put("llmcall/a/%s/request.json" % call, request)
        self.put("llmcall/a/c1/receipt.json", {"used": 3, "overrun": 0})
        self.put("llmcall/a/c1/raw.json", {"at": 0})
        self.put("llmcall/a/c2/receipt.json", {"used": None, "overrun": None})
        self.put("llmcall/a/c2/raw.json", {"at": 3600})
        self.put("llmcall/a/c3/receipt.json", {"used": 4, "overrun": 2})
        self.put("llmcall/a/c3/raw.json", {"at": 0})
        self.put("llmcall/a/c5/request.json", "{")
        self.put("llmcall/a/c6/receipt.json", "{")
        self.put("llmcall/a/c7/receipt.json", {"used": 10, "overrun": 0})
        self.put("llmcall/a/c7/raw.json", "{")
        self.put("llmcall/a/ignored/receipt.json", {"used": 99})
        self.put("llmcall/b/c8/request.json",
                 {"request": {"model": 5}, "endpoint": "e", "holder": "h"})
        self.put("llmcall/b/c8/receipt.json", {"used": 6, "overrun": 0})

    def put(self, relative, value):
        path = self.node / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(ENTRY), str(self.node), *args],
                              capture_output=True, text=True, check=False)

    def snapshot(self):
        return {str(path.relative_to(self.node)): (stat.S_IMODE(path.stat().st_mode),
                None if path.is_dir() else path.read_bytes())
                for path in (self.node, *self.node.rglob("*"))}

    def test_day_hour_and_read_only(self):
        before = self.snapshot()
        day_run = self.run_tool()
        hour_run = self.run_tool("--by", "hour")
        self.assertEqual(before, self.snapshot())
        for result in (day_run, hour_run):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("\n"), 1)
        day = json.loads(day_run.stdout)
        hour = json.loads(hour_run.stdout)
        self.assertEqual((day["v"], day["by"], hour["by"]), (1, "day", "hour"))
        self.assertEqual(day["groups"], [
            {"model": "e", "holder": "h", "period": "-", "calls": 1, "used": 6, "overrun": 0},
            {"model": "m", "holder": "h", "period": "1970-01-01", "calls": 3,
             "used": 7, "overrun": 2}])
        self.assertEqual(hour["groups"], [
            day["groups"][0],
            {"model": "m", "holder": "h", "period": "1970-01-01T00", "calls": 2,
             "used": 7, "overrun": 2},
            {"model": "m", "holder": "h", "period": "1970-01-01T01", "calls": 1,
             "used": 0, "overrun": 0}])
        self.assertEqual(day["budgets"], {
            "a": {"receipts_used": 7, "ledger_used": 4, "diff": -3},
            "b": {"receipts_used": 6, "ledger_used": 9, "diff": 3}})
        self.assertEqual(day["gaps"], [
            {"budget": "a", "call_id": "c3", "why": "overrun"},
            {"budget": "a", "call_id": "c4", "why": "no_receipt"},
            {"budget": "a", "call_id": "c5", "why": "bad_json"},
            {"budget": "a", "call_id": "c6", "why": "bad_json"},
            {"budget": "a", "call_id": "c7", "why": "bad_json"}])
        self.assertEqual(hour["gaps"], day["gaps"])

    def test_missing_receipt_amounts_are_bad_json(self):
        request = {"request": {"model": "m"}, "endpoint": "e", "holder": "h"}
        for call, receipt in (("missing_both", {}),
                              ("missing_overrun", {"used": 20}),
                              ("missing_used", {"overrun": 5})):
            self.put("llmcall/a/%s/request.json" % call, request)
            self.put("llmcall/a/%s/receipt.json" % call, receipt)
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(sum(group["calls"] for group in data["groups"]), 4)
        self.assertEqual(data["budgets"]["a"],
                         {"receipts_used": 7, "ledger_used": 4, "diff": -3})
        self.assertEqual(data["gaps"][-3:], [
            {"budget": "a", "call_id": call, "why": "bad_json"}
            for call in ("missing_both", "missing_overrun", "missing_used")])

    def test_invalid_and_missing_ledgers(self):
        self.put("budget/a/ledger.json", {"used": True})
        self.put("budget/c/ledger.json", "{")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        budgets = json.loads(result.stdout)["budgets"]
        self.assertEqual(budgets["a"], {"receipts_used": 7, "ledger_used": None,
                                        "diff": None})
        self.assertEqual(budgets["c"], {"receipts_used": 0, "ledger_used": None,
                                        "diff": None})

    def test_non_directory_node_exits_two(self):
        missing = self.node / "missing"
        result = subprocess.run([sys.executable, str(ENTRY), str(missing)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
