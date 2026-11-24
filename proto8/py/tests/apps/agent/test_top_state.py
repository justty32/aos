"""Test aos-agent state (11-24 ops item 5): the same as ctl state at the top level; a ctl action typed at the top level hints at ctl."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"


class TopState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="top-state-"))
        self.d = self.tmp / "d"
        (self.d / "procs" / "ann").mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"ann": {"phase": "stopped", "stack": "procs/ann",
                                                                                "reason": "exited 1"}}}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def agent(self, *args):
        return subprocess.run([str(BIN), "-d", str(self.d)] + list(args), env=env_helper.clean_env(TZ="UTC"),
                              capture_output=True, text=True, timeout=30)

    def test_state_is_ctl_state(self):
        for args in (("state", "-t", "ann"), ("-t", "ann", "state"), ("state", "-t", "ann", "-j")):
            with self.subTest(args=args):
                top, ctl = self.agent(*args), self.agent("ctl", *args) if args[0] == "state" else self.agent("-t", "ann", "ctl", "state")
                self.assertEqual(top.returncode, 0, top.stderr)
                strip = (lambda out: json.dumps(dict(json.loads(out), time=None))) if "-j" in args else \
                    (lambda out: "\n".join(l for l in out.splitlines() if not l.startswith("time ")))
                self.assertEqual(strip(top.stdout), strip(ctl.stdout))              # same output, but for the clock
                self.assertTrue(top.stdout.strip())

    def test_ctl_action_at_top_level_hints_ctl(self):
        r = self.agent("stop", "ann")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CommandUnknown unknown subcommand stop", r.stderr)
        self.assertIn("did you mean aos-agent ctl stop?", r.stderr)
        r = self.agent("nonsense")
        self.assertNotIn("did you mean", r.stderr)
        self.assertIn("state", self.agent("--help").stdout)


if __name__ == "__main__":
    unittest.main()
