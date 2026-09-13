import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from _util import CLI, CpuCase, EXEC, PY


class HomeTest(CpuCase):
    def test_init_layout_examples_and_absolute_inst(self):
        fresh = Path(self.temp.name) / "fresh"
        made = self.cli("init", fresh)
        self.assertEqual(made.returncode, 0, made.stderr)
        doc = json.loads((fresh / "endpoints.json").read_text())
        self.assertEqual([x["name"] for x in doc["endpoints"]],
                         ["local", "deepseek", "pi"])
        self.assertFalse(doc["endpoints"][2]["enabled"])
        inst = json.loads((fresh / "inst.json").read_text())
        self.assertTrue(Path(inst["argv"][0]).is_absolute())
        self.assertEqual(inst["cwd"], str(fresh.absolute()))
        for relative in ("requests/running", "requests/done", "results", "log"):
            self.assertTrue((fresh / relative).is_dir())

    def test_submit_file(self):
        source = Path(self.temp.name) / "req.json"
        source.write_text('{"messages":[{"role":"user","content":"x"}]}')
        result = self.cli("submit", self.home, source, "--name", "file")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("results/file.json", result.stdout)
        self.assertTrue((self.home / "requests/file.json").exists())

    def test_submit_stdin_and_name(self):
        result = self.cli("submit", self.home, "-", "--name", "stdin",
                          input_data='{"messages":[]}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.home / "requests/stdin.json").read_text()),
                         {"messages": []})

    def test_submit_rejects_duplicate_name(self):
        self.request("same")
        result = self.cli("submit", self.home, "-", "--name", "same",
                          input_data="{}")
        self.assertEqual(result.returncode, 1)

    def _bad(self, request_id, body, phrase):
        self.write_json("requests/%s.json" % request_id, body)
        self.tick()
        result = self.result(request_id)
        self.assertEqual(result["error"]["kind"], "bad_request")
        self.assertIn(phrase, result["error"]["msg"])
        self.assertTrue((self.home / "requests/done" / (request_id + ".json")).exists())

    def test_bad_request_missing_messages(self):
        self._bad("missing", {}, "messages")

    def test_bad_request_non_object(self):
        self._bad("array", [], "JSON 物件")

    def test_bad_request_forbids_model(self):
        self._bad("model", {"messages": [{}], "model": "x"}, "不准指定 model")

    def test_bad_request_unknown_endpoint(self):
        self._bad("unknown", {"messages": [{}], "endpoint": "nope"}, "不認得")

    def test_bad_request_process_endpoint(self):
        doc = json.loads((self.home / "endpoints.json").read_text())
        doc["endpoints"].append({"name": "pi", "kind": "process",
                                 "argv": ["pi", "-p"], "enabled": False})
        self.write_json("endpoints.json", doc)
        self._bad("pi", {"messages": [{}], "endpoint": "pi"}, "不支援 process")

    def test_tick_bad_endpoints_is_still_zero_and_logs(self):
        (self.home / "endpoints.json").write_text("{")
        result = self.cli("tick", self.home)
        self.assertEqual(result.returncode, 0)
        self.assertIn("error=", (self.home / "llm-cpu.log").read_text())

    def test_ls_is_one_screen_summary(self):
        self.request("q")
        result = self.cli("ls", self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("local (default)", result.stdout)
        self.assertIn("queued: 1", result.stdout)

    def test_aos_exec_runs_exactly_one_tick(self):
        before = json.loads((self.home / "state.json").read_text())["ticks"]
        result = subprocess.run(
            [PY, str(EXEC), str(self.home), "--dir-target", "inst.json"],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads((self.home / "state.json").read_text())["ticks"]
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()
