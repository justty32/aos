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
KERNEL_INIT = ROOT.parent / "proto4-3" / "aos-kernel-init"
KERNEL_TICK = ROOT.parent / "proto4-3" / "aos-kernel-tick"
LLM_MODULE = ROOT.parent / "proto4-5" / "llm_cpu_module.py"


class StepPyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-step-py-")
        self.home = Path(self.tmp.name)
        self.prog = self.home / "job.py"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, source):
        self.prog.write_text(source, encoding="utf-8")

    def run_tool(self, *args, prog=None, env=None):
        return subprocess.run(
            [str(TOOL), str(prog or self.prog), *args], cwd=self.home,
            text=True, capture_output=True, check=False, env=env,
        )

    def state(self):
        return json.loads((self.home / "job.state.json").read_text(encoding="utf-8"))

    def test_helper_is_skipped_and_steps_follow_definition_order(self):
        self.write("def second(state): pass\ndef _helper(x): return x\ndef first(state): pass\n")
        result = self.run_tool("--status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["steps"], ["second", "first"])

    def test_state_crosses_steps_and_state_file_has_readable_fields(self):
        self.write("def load(state): state['x'] = 4\ndef compute(state): state['x'] *= 3\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.run_tool().returncode, 0)
        state = self.state()
        self.assertEqual(state["state"], {"x": 12})
        self.assertEqual(state["steps"], ["load", "compute"])
        self.assertEqual(list(state)[:2], ["state", "pc"])

    def test_binary_state_is_base64_and_crosses_steps_as_bytes(self):
        self.write("def save(state): state['raw'] = b'\\x00\\xff\\x01'\n"
                   "def check(state): state['same'] = state['raw'] == b'\\x00\\xff\\x01'\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["state"]["raw"], {"$b64": "AP8B"})
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["state"]["same"])

    def test_aos_b64_and_unb64_round_trip(self):
        self.write("def convert(state):\n"
                   "    encoded = aos.b64(b'\\x00\\xff\\x01')\n"
                   "    state['encoded'] = encoded\n"
                   "    state['same'] = aos.unb64(encoded) == b'\\x00\\xff\\x01'\n"
                   "    state['plain'] = aos.unb64('AP8B') == b'\\x00\\xff\\x01'\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["state"],
                         {"encoded": {"$b64": "AP8B"}, "same": True, "plain": True})

    def test_reads_lua_binary_state_as_bytes(self):
        self.write("def check(state): state['same'] = state['raw'] == b'\\x00\\xff\\x01'\n")
        (self.home / "job.state.json").write_text(
            '{"state":{"raw":{"$b64":"AP8B"}},"pc":0,"n":1,"done":false,"steps":["check"]}\n',
            encoding="utf-8",
        )
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["state"]["same"])

    def test_exception_rolls_back_and_writes_traceback_with_name_and_line(self):
        self.write("def good(state): state['kept'] = 1\n\ndef boom(state):\n    state['kept'] = 9\n    raise RuntimeError('bad first line\\nmore')\n")
        self.assertEqual(self.run_tool().returncode, 0)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.state()["pc"], self.state()["state"]), (1, {"kept": 1}))
        self.assertIn("第 1 格 boom", result.stderr)
        self.assertIn("PROG 第 5 行", result.stderr)
        error = (self.home / "job.py.error").read_text()
        self.assertIn("Traceback", error)
        self.assertIn("RuntimeError: bad first line", error)
        self.assertIn("RuntimeError", self.run_tool("--status").stderr)

    def test_success_reports_step_name(self):
        self.write("def greet(state): state['ok'] = True\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertIn("第 0 格 ok（greet）", result.stderr)

    def test_non_json_state_fails_without_advancing(self):
        self.write("def bad(state): state['x'] = {1, 2}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertIn("state 裡有 JSON 放不進的東西：set", result.stderr)

    def test_syntax_error_is_exit_two(self):
        self.write("def broken(:\n    pass\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("載不起 PROG", result.stderr)
        self.assertFalse((self.home / "job.state.json").exists())

    def test_done_returns_100_repeatedly(self):
        self.write("def only(state): pass\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["done"])
        self.assertEqual(self.run_tool().returncode, 100)
        self.assertEqual(self.run_tool().returncode, 100)

    def test_wait_for_blocks_until_file_then_runs_next_step(self):
        self.write("def submit(state): return aos.wait_for('out.json')\n"
                   "def consume(state): open(here + '/next.txt', 'w').write('ran')\n")
        self.assertEqual(self.run_tool().returncode, 0)
        first = self.state()
        self.assertEqual((first["pc"], first["waiting"]["checks"]), (1, 0))
        self.assertEqual(first["waiting"]["for"], str(self.home / "out.json"))
        waiting = self.run_tool()
        self.assertEqual(waiting.returncode, 101)
        self.assertIn(f"在等 {self.home / 'out.json'}（第 1 次）", waiting.stderr)
        blocked = self.state()
        self.assertEqual(blocked["waiting"]["checks"], 1)
        self.assertEqual((blocked["last"], blocked["history"]),
                         (first["last"], first["history"]))
        self.assertFalse((self.home / "next.txt").exists())
        (self.home / "out.json").touch()
        self.assertEqual(self.run_tool().returncode, 0)
        state = self.state()
        self.assertNotIn("waiting", state)
        self.assertEqual((self.home / "next.txt").read_text(), "ran")
        self.assertIn("(wait)", [item.get("step") for item in state["history"]])

    def test_last_python_step_can_wait_before_done_exit(self):
        self.write("def only(state): return aos.wait_for('last.out')\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertFalse(self.state()["done"])
        self.assertEqual(self.run_tool().returncode, 101)
        (self.home / "last.out").touch()
        self.assertEqual(self.run_tool().returncode, 100)
        self.assertTrue(self.state()["done"])

    def test_waiting_status_and_reset(self):
        self.write("def only(state): return aos.wait_for('pending.out')\n")
        self.run_tool()
        status = self.run_tool("--status")
        self.assertIn("waiting", json.loads(status.stdout))
        self.assertIn("在等 " + str(self.home / "pending.out"), status.stderr)
        self.assertEqual(self.run_tool("--reset").returncode, 0)
        self.assertNotIn("waiting", json.loads(self.run_tool("--status").stdout))

    def test_llm_submit_wait_for_with_manual_kernel_ticks(self):
        k = self.home / "K"
        env = dict(os.environ, AOS_DAEMON_HOME=str(self.home / "dead-daemon"))
        init = subprocess.run([str(KERNEL_INIT), str(k), "--ncpu", "1", "--interval-ms", "100",
                               "--module", str(LLM_MODULE)], env=env, text=True,
                              capture_output=True, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        server = subprocess.Popen([sys.executable, str(FAKE_OPENAI)], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        try:
            port = int(server.stdout.readline().strip()); server.stdout.close()
            tick = lambda: subprocess.run([str(KERNEL_TICK)], cwd=k, env=env, text=True,
                                          capture_output=True, check=False)
            self.assertEqual(tick().returncode, 0)
            (k / "llm/endpoints.json").write_text(json.dumps({
                "default": "local", "endpoints": [{"name": "local", "kind": "openai",
                "base_url": f"http://127.0.0.1:{port}/v1", "model": "fake-model",
                "max_concurrent": 1, "timeout_ms": 2000}]}), encoding="utf-8")
            self.write(
                f"def submit(state):\n    state['r'] = aos.llm_submit({str(k)!r}, "
                "{'messages':[{'role':'user','content':'echo:hi'}]}, 'q1')\n"
                "    return aos.wait_for(state['r'])\n"
                "def consume(state):\n    import json\n    state['text'] = json.load(open(state['r']))['text']\n")
            proc = subprocess.Popen([str(TOOL), str(self.prog)], cwd=self.home, env=env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = __import__("time").time() + 5
            while proc.poll() is None and __import__("time").time() < deadline:
                if list((k / "syscalls").glob("*.json")):
                    tick()
                else:
                    __import__("time").sleep(0.01)
            out, err = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, err or out)
            deadline = __import__("time").time() + 5
            while self.state()["pc"] < 2 and __import__("time").time() < deadline:
                self.assertEqual(tick().returncode, 0)
                self.run_tool(env=env)
                __import__("time").sleep(0.03)
            self.assertEqual(self.state()["state"]["text"], "hi")
            self.assertTrue((self.home / "q1.req.json").is_file())
        finally:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=2)

    def test_reset_removes_progress_and_error(self):
        self.write("def only(state): raise RuntimeError('old boom')\n")
        self.assertEqual(self.run_tool().returncode, 1)
        error = self.home / "job.py.error"
        self.assertTrue(error.exists())
        self.assertEqual(self.run_tool("--reset").returncode, 0)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertFalse(error.exists())
        status = self.run_tool("--status")
        self.assertEqual(json.loads(status.stdout)["pc"], 0)
        self.assertEqual(status.stderr, "")

    def test_changed_source_warns_and_runs_current_pc(self):
        self.write("def one(state): pass\ndef two(state): state['which'] = 'old'\n")
        self.run_tool()
        self.write("# edited\ndef one(state): pass\ndef two(state): state['which'] = 'new'\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertIn("PROG 改過了（上次 2 個、現在 2 個）", result.stderr)
        self.assertEqual(self.state()["state"]["which"], "new")

    def test_changed_next_function_name_warns(self):
        self.write("def one(state): pass\ndef old_name(state): pass\n")
        self.run_tool()
        self.write("def one(state): pass\ndef new_name(state): pass\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertIn("函式名對不上（上次 old_name、現在 new_name）", result.stderr)

    def test_here_and_pc_are_available(self):
        self.write("def first(state): state['at'] = here; state['pc0'] = pc\ndef second(state): state['pc1'] = pc\n")
        self.run_tool()
        self.run_tool()
        self.assertEqual(self.state()["state"], {"at": str(self.home), "pc0": 0, "pc1": 1})

    def test_call_dir_read_and_json(self):
        child = self.home / "child"
        (child / ".aos").mkdir(parents=True)
        (child / ".aos/inst.json").write_text(json.dumps({
            "argv": ["sh", "-c", "printf '{\\\"answer\\\":42}'"], "stdout": "out.json"}))
        self.write("def tool(state):\n    r = aos.call_dir('child', read='child/out.json', json=True)\n    state['r'] = r['value']\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["state"]["r"], {"answer": 42})

    def test_call_child_exit_three(self):
        script = self.home / "exit3"
        script.write_text("#!/bin/sh\nexit 3\n")
        script.chmod(0o755)
        self.write("def tool(state): state['r'] = aos.call('./exit3')\n")
        self.assertEqual(self.run_tool().returncode, 0)
        result = self.state()["state"]["r"]
        self.assertEqual((result["code"], result["kind"]), (3, "child"))
        self.assertEqual(set(result), {"code", "kind", "out", "err", "value"})

    def test_call_plain_file_with_args(self):
        script = self.home / "args"
        script.write_text("#!/bin/sh\nprintf '<%s>|<%s>' \"$@\"\n")
        script.chmod(0o755)
        self.write("def tool(state): state['out'] = aos.call('./args', args=['a b', '--stderr'], capture=True)['out']\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["state"]["out"], "<a b>|<--stderr>")

    def test_call_json_rejects_args(self):
        (self.home / "one.json").write_text('{"argv":["true"]}')
        self.write("def tool(state): aos.call_json('one.json', args=['extra'])\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", result.stderr)

    def test_call_dir_rejects_even_empty_args(self):
        (self.home / "child").mkdir()
        self.write("def tool(state): aos.call_dir('child', args=[])\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", result.stderr)

    def test_stderr_option_reaches_aos_exec(self):
        script = self.home / "noisy"
        script.write_text("#!/bin/sh\necho seen >&2\n")
        script.chmod(0o755)
        self.write("def tool(state): state['ok'] = aos.ok(aos.call('./noisy'))\n")
        result = self.run_tool("--stderr", "child.err")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "child.err").read_text().strip(), "seen")
        self.run_tool("--reset")
        shown = self.run_tool("--stderr", "-")
        self.assertEqual(shown.returncode, 0)
        self.assertIn("seen", shown.stderr)

if __name__ == "__main__":
    unittest.main()
