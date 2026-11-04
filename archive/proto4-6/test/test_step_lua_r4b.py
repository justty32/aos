import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "aos-step-lua"


class StepLuaR4bTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-step-lua-r4b-")
        self.home = Path(self.tmp.name)
        self.prog = self.home / "job.lua"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, source):
        self.prog.write_text(source, encoding="utf-8")

    def run_tool(self, *, prog=None):
        return subprocess.run([str(TOOL), str(prog or self.prog)], cwd=self.home,
                              text=True, capture_output=True, check=False)

    def state(self):
        return json.loads((self.home / "job.state.json").read_text())

    def test_help_is_successful(self):
        result = subprocess.run([str(TOOL), "--help"], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: aos-step-lua", result.stdout)

    def test_ms_uses_wall_clock(self):
        self.write("local function nap(s) os.execute('sleep 0.2') end\nreturn {{name='nap',fn=nap}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertGreater(self.state()["last"]["ms"], 0)

    def test_unlisted_functions_warn_but_underscore_helpers_do_not(self):
        self.write("local function listed(s) s.ok=true end\n"
                   "local function missing(s) end\nfunction global_missing(s) end\n"
                   "local function _helper(s) end\n"
                   "return {{name='listed',fn=listed}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("這些函式沒列進 return 表，不會被執行：missing, global_missing", result.stderr)
        self.assertNotIn("_helper", result.stderr)

    def test_error_files_are_per_program_and_success_removes_own_file(self):
        other = self.home / "other.lua"
        self.write("local function fail(s) error('first') end\nreturn {{name='fail',fn=fail}}\n")
        other.write_text("local function fail(s) error('second') end\nreturn {{name='fail',fn=fail}}\n")
        self.assertEqual(self.run_tool().returncode, 1)
        self.assertEqual(self.run_tool(prog=other).returncode, 1)
        first_error, second_error = self.home / "job.lua.error", self.home / "other.lua.error"
        self.assertIn("first", first_error.read_text())
        self.assertIn("second", second_error.read_text())
        self.write("local function pass_now(s) s.ok=true end\nreturn {{name='pass_now',fn=pass_now}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertFalse(first_error.exists())
        self.assertTrue(second_error.exists())


if __name__ == "__main__":
    unittest.main()
