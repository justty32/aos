import json
from pathlib import Path
import subprocess
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "aos-step-json"


class StepJsonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-step-json-")
        self.home = Path(self.tmp.name)
        self.prog = self.home / "job.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, value):
        self.prog.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def run_tool(self, *args, cwd=None):
        return subprocess.run(
            [str(TOOL), str(self.prog), *args], cwd=cwd, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def state(self):
        return json.loads((self.home / "job.state.json").read_text(encoding="utf-8"))

    def test_initial_status_is_pc_zero_without_creating_state(self):
        self.write([{"argv": ["true"]}] * 3)
        result = self.run_tool("--status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"pc": 0, "n": 3, "done": False})
        self.assertFalse((self.home / "job.state.json").exists())

    def test_first_step_writes_file_and_result_state(self):
        self.write([{"argv": ["sh", "-c", "printf one > first.txt"]}])
        result = self.run_tool()
        state = self.state()
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.home / "first.txt").read_text(), "one")
        self.assertEqual(state["pc"], 1)
        self.assertEqual(state["last"]["pc"], 0)
        self.assertEqual(state["history"], [state["last"]])

    def test_relative_cwd_is_based_on_program_directory(self):
        (self.home / "sub").mkdir()
        self.write([{"argv": ["sh", "-c", "pwd > where.txt"], "cwd": "sub"}])
        self.assertEqual(self.run_tool(cwd="/").returncode, 0)
        self.assertEqual((self.home / "sub/where.txt").read_text().strip(), str(self.home / "sub"))

    def test_missing_cwd_defaults_to_program_directory(self):
        self.write([{"argv": ["sh", "-c", "pwd > where.txt"]}])
        self.assertEqual(self.run_tool(cwd="/").returncode, 0)
        self.assertEqual((self.home / "where.txt").read_text().strip(), str(self.home))

    def test_child_failure_stays_and_fixed_step_advances(self):
        self.write([{"argv": ["sh", "-c", "exit 3"]}])
        failed = self.run_tool()
        self.assertEqual(failed.returncode, 3)
        self.assertEqual(self.state()["pc"], 0)
        self.assertIn("第 0 個元素（0 起算）失敗：exit=3", failed.stderr)
        self.write([{"argv": ["true"]}])
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["pc"], 1)

    def test_done_returns_100_and_stays_done(self):
        self.write([{"argv": ["true"]}])
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["done"])
        self.assertEqual(self.run_tool().returncode, 100)
        self.assertEqual(self.run_tool().returncode, 100)

    def test_reset_returns_to_initial_status(self):
        self.write([{"argv": ["true"]}])
        self.run_tool()
        self.assertEqual(self.run_tool("--reset").returncode, 0)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertEqual(json.loads(self.run_tool("--status").stdout)["pc"], 0)

    def test_note_is_removed_before_aos_exec(self):
        self.write([{"note": "給人看的", "argv": ["true"]}])
        self.assertEqual(self.run_tool().returncode, 0)
        current = json.loads((self.home / ".aos-step-json/current.json").read_text())
        self.assertNotIn("note", current)

    def test_program_must_be_array(self):
        self.write({"argv": ["true"]})
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("必須是一個 JSON 陣列", result.stderr)

    def test_element_without_argv_is_usage_failure_and_pc_does_not_move(self):
        self.write([{"note": "少了 argv"}])
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertEqual(json.loads(self.run_tool("--status").stdout)["pc"], 0)

    def test_missing_cwd_is_aos_failure_and_pc_does_not_move(self):
        self.write([{"argv": ["true"], "cwd": "missing"}])
        result = self.run_tool()
        self.assertEqual(result.returncode, 125)
        self.assertEqual(self.state()["pc"], 0)
        self.assertEqual(self.state()["last"]["kind"], "aos")

    def test_stderr_dash_shows_child_error(self):
        self.write([{"argv": ["sh", "-c", "echo typo-message >&2; exit 4"]}])
        result = self.run_tool("--stderr", "-")
        self.assertEqual(result.returncode, 4)
        self.assertIn("typo-message", result.stderr)

    def test_changed_program_warns_but_runs_current_pc(self):
        self.write([{"argv": ["true"]}, {"argv": ["sh", "-c", "printf old > mark"]}])
        self.assertEqual(self.run_tool().returncode, 0)
        self.write([
            {"argv": ["sh", "-c", "printf inserted > inserted"]},
            {"argv": ["sh", "-c", "printf shifted > mark"]},
            {"argv": ["true"]},
        ])
        result = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertIn("PROG 改過了（上次 2 個、現在 3 個）", result.stderr)
        self.assertEqual((self.home / "mark").read_text(), "shifted")

    def test_state_has_exact_top_level_keys_and_valid_json(self):
        self.write([{"argv": ["true"]}])
        self.run_tool()
        state = self.state()
        self.assertEqual(set(state), {"pc", "n", "done", "src", "last", "history"})
        self.assertEqual(state["src"]["n"], 1)
        self.assertEqual(len(state["src"]["sha256"]), 64)

    def test_history_keeps_only_latest_fifty_attempts(self):
        self.write([{"argv": ["false"]}])
        for _ in range(52):
            self.run_tool()
        self.assertEqual(len(self.state()["history"]), 50)


if __name__ == "__main__":
    unittest.main()
