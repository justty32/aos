"""Test that before_run / after_run are wired at compile time (no flag files any more, the user 11-21 "編譯時決定"): an agent.py or kernel.py writes on_before_run / on_after_run into loop.json only when a hook listens to them; on_start / on_stop whenever hooks are declared; all through aos-hook fire --stop-on-nonzero --def $AOS_CD."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_spec_helpers import agent  # noqa: E402
from aos.py.kernel import defs as kdefs  # noqa: E402

FIRE = ["aos-hook", "fire", "-q", "--stop-on-nonzero", "--def", {"$env": "AOS_CD"}]


class AgentWiring(unittest.TestCase):
    def test_no_hooks_declared_no_loop_points(self):
        loop = agent().dry_run()["loop.json"]
        self.assertFalse({"on_start", "on_stop", "on_before_run", "on_after_run"} & set(loop))

    def test_hooks_but_not_on_the_run_points(self):
        loop = agent(hooks={"t": {"event": "after_tool", "handler": "h"}}).dry_run()["loop.json"]
        self.assertEqual(loop["on_start"], {"argv": FIRE + ["after_start"]})
        self.assertEqual(loop["on_stop"], {"argv": FIRE + ["after_stop"]})
        self.assertFalse({"on_before_run", "on_after_run", "on_before_run_if", "on_after_run_if"} & set(loop))
        self.assertIn("recompile", loop["description"])

    def test_a_hook_on_before_run_wires_it(self):
        loop = agent(hooks={"b": {"event": "before_run", "handler": "h"}}).dry_run()["loop.json"]
        self.assertEqual(loop["on_before_run"], {"argv": FIRE + ["before_run"]})
        self.assertNotIn("on_after_run", loop)
        loop = agent(hooks=[{"b": {"event": "before_run", "handler": "h"}, "a": {"event": "after_run", "handler": "h"}},
                            {"b": None}]).dry_run()["loop.json"]
        self.assertEqual((loop.get("on_before_run"), loop["on_after_run"]), (None, {"argv": FIRE + ["after_run"]}))


class KernelWiring(unittest.TestCase):
    def test_loop_body(self):
        files = kdefs.Kernel("K.", body=kdefs.loop()).dry_run()
        self.assertEqual(files["loop.json"]["on_start"], {"argv": FIRE + ["after_start"]})
        self.assertNotIn("on_before_run", files["loop.json"])
        files = kdefs.Kernel("K.", body=kdefs.loop(), hooks={"r": {"event": "after_run", "handler": "h"}}).dry_run()
        self.assertEqual(files["loop.json"]["on_after_run"], {"argv": FIRE + ["after_run"]})
        self.assertEqual(files["kernel_hookeds.json"]["r"], {"event": "after_run", "handler": "h"})


if __name__ == "__main__":
    unittest.main()
