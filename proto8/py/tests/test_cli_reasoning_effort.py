"""Test that reasoning_effort in an eca definition's llm.json (11-21 line top-1121-ecaeffort) becomes claude's --effort or pi's --thinking, read again every turn, and that a level the CLI does not take is CfgBad."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.agentlib import cli_cfg  # noqa: E402


class ReasoningEffort(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name)) / "def"
        self.stack = Path(os.path.realpath(self.tmp.name)) / "stack"
        self.d.mkdir()
        self.stack.mkdir()
        (self.d / "interfaces.json").write_text(json.dumps({"aos-agent": {"llm": "llm.json", "llm_keys": ["model", "reasoning_effort"]}}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env["AOS_STACK"] = str(self.stack)

    def load(self, kind, llm, own=None, flags=None):
        cfg = {"kind": kind}
        if flags is not None:
            cfg["flags"] = flags
        (self.d / "cli.json").write_text(json.dumps(cfg))
        (self.d / "llm.json").write_text(json.dumps(llm))
        if own is not None:
            (self.stack / "llm.json").write_text(json.dumps(own))
        with patch.dict(os.environ, self.env, clear=True):
            return cli_cfg.load_cfg(str(self.d))

    def fails(self, kind, llm, own=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.load(kind, llm, own)
        self.assertEqual(cm.exception.code, 1)
        line = err.getvalue().strip().splitlines()[-1]
        self.assertIn("error: CfgBad ", line)
        return line

    def test_claude_gets_effort(self):
        cfg = self.load("claude", {"model": "sonnet", "reasoning_effort": "high"})
        self.assertEqual(cfg["flags"], ["--model", "sonnet", "--effort", "high"])
        self.assertEqual(cfg["reasoning_effort"], "high")

    def test_pi_gets_thinking(self):
        cfg = self.load("pi", {"reasoning_effort": "off"})
        self.assertEqual(cfg["flags"], ["--thinking", "off"])

    def test_stack_copy_overrides_definition(self):
        """aos-agent llm set reasoning_effort=max writes the stack copy; it wins over the definition's value."""
        cfg = self.load("claude", {"reasoning_effort": "low"}, own={"reasoning_effort": "max"})
        self.assertEqual(cfg["flags"], ["--effort", "max"])

    def test_none_leaves_flags_alone(self):
        cfg = self.load("claude", {"model": "sonnet"})
        self.assertEqual(cfg["flags"], ["--model", "sonnet"])
        self.assertIsNone(cfg["reasoning_effort"])

    def test_flag_in_cli_json_is_replaced(self):
        cfg = self.load("claude", {"reasoning_effort": "xhigh"}, flags=["--effort", "low", "--strict-mcp-config"])
        self.assertEqual(cfg["flags"], ["--effort", "xhigh", "--strict-mcp-config"])
        cfg = self.load("pi", {"reasoning_effort": "minimal"}, flags=["--thinking=high"])
        self.assertEqual(cfg["flags"], ["--thinking=minimal"])

    def test_level_the_cli_does_not_take(self):
        line = self.fails("claude", {"reasoning_effort": "none"})
        self.assertIn('reasoning_effort "none" in llm.json is not a level claude takes (--effort takes: low, medium, high, xhigh, max)', line)
        line = self.fails("pi", {"reasoning_effort": "none"})
        self.assertIn("--thinking takes: off, minimal, low, medium, high, xhigh, max", line)
        self.fails("claude", {"reasoning_effort": "off"})

    def test_not_a_string(self):
        self.assertIn("must be a non-empty string", self.fails("claude", {"reasoning_effort": ""}))
        self.assertIn("must be a non-empty string", self.fails("pi", {"reasoning_effort": 3}))

    def test_codex_refuses(self):
        self.assertIn("not supported for kind codex", self.fails("codex", {"reasoning_effort": "high"}))


if __name__ == "__main__":
    unittest.main()
