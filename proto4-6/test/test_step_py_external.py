import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "aos-step-py"
EXEC = ROOT.parent / "proto4-3" / "aos-exec"
FAKE_OPENAI = ROOT.parent / "proto4-5" / "test" / "_fake_openai.py"


class StepPyExternalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-step-py-external-")
        self.home = Path(self.tmp.name)
        self.prog = self.home / "job.py"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, source):
        self.prog.write_text(source, encoding="utf-8")

    def run_tool(self, *, prog=None):
        return subprocess.run([str(TOOL), str(prog or self.prog)], cwd=self.home,
                              text=True, capture_output=True, check=False)

    def state(self):
        return json.loads((self.home / "job.state.json").read_text())

    def test_llm_against_fake_server(self):
        server = subprocess.Popen([sys.executable, str(FAKE_OPENAI)], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        try:
            port = int(server.stdout.readline().strip()); server.stdout.close()
            (self.home / "endpoint.json").write_text(json.dumps({
                "name": "fake", "kind": "openai", "base_url": f"http://127.0.0.1:{port}/v1",
                "model": "fake-model"}))
            self.write("def ask(state):\n    r=aos.llm('endpoint.json', {'messages':[{'role':'user','content':'echo:hi'}]}, 'out.json')\n    state['text']=aos.llm_text(r)\n")
            result = self.run_tool()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.state()["state"]["text"], "hi")
            self.assertTrue((self.home / "out.json.req.json").exists())
        finally:
            os.killpg(server.pid, signal.SIGTERM); server.wait(timeout=2)

    def test_aos_exec_runs_step_program_to_done(self):
        self.write("def a(state): pass\ndef b(state): pass\ndef c(state): pass\ndef d(state): pass\n")
        inst = self.home / "step.json"
        inst.write_text(json.dumps({"argv": [str(TOOL), str(self.prog)], "cwd": str(self.home)}))
        codes = [subprocess.run([str(EXEC), str(inst)]).returncode for _ in range(5)]
        self.assertEqual(codes, [0, 0, 0, 0, 100])

    def test_error_files_are_per_program_and_success_removes_own_file(self):
        other = self.home / "other.py"
        self.write("def fail(state): raise RuntimeError('first')\n")
        other.write_text("def fail(state): raise RuntimeError('second')\n")
        self.assertEqual(self.run_tool().returncode, 1)
        self.assertEqual(self.run_tool(prog=other).returncode, 1)
        first_error, second_error = self.home / "job.py.error", self.home / "other.py.error"
        self.assertIn("first", first_error.read_text())
        self.assertIn("second", second_error.read_text())
        self.write("def pass_now(state): state['ok'] = True\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertFalse(first_error.exists())
        self.assertTrue(second_error.exists())


if __name__ == "__main__":
    unittest.main()
