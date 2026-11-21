"""Test defs.loop (line aos-pylib-k4-1120, second commit; open question 8 of thinking/2026-11/20/aos-pylib-plan-1120/08, the user chose "加一個宣告"): defs.Agent(..., loop=defs.loop(interval_ms=N, ...)) writes those keys into loop.json as they are, over the compile's own (user 11-21: "任意鍵照傳", "every_ms感覺可以拿掉，反正有interval_ms？"); without loop= the files are what they were."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import HEAD, TEMPLATES, WithHome, agent, defs, run_agent  # noqa: E402


class Loop(WithHome):
    def test_interval_ms_changes_only_the_pause(self):
        plain, timed = agent(hooks={}).dry_run(), agent(hooks={}, loop=defs.loop(interval_ms=1000)).dry_run()
        self.assertEqual(plain["loop.json"]["interval_ms"], 300)
        self.assertEqual(timed["loop.json"]["interval_ms"], 1000)
        self.assertEqual(dict(timed["loop.json"], interval_ms=300), plain["loop.json"])   # only the pause changes
        self.assertEqual({k: v for k, v in timed.items() if k != "loop.json"}, {k: v for k, v in plain.items() if k != "loop.json"})
        self.assertEqual(list(timed["loop.json"]), list(plain["loop.json"]))                 # same keys, same order
        self.assertEqual(agent(loop=defs.loop(interval_ms=0)).dry_run()["loop.json"]["interval_ms"], 0)

    def test_any_key_goes_through(self):
        """11-21「任意鍵照傳」：any key, as it is, unchecked; a key the compile writes is replaced in place (yours wins); defs.loop() = no loop=."""
        plain = agent(hooks={}).dry_run()["loop.json"]
        made = agent(hooks={}, loop=defs.loop(interval_ms=1000, max=50, made_up_key={"a": [1]}, on_start=["true"], exec="mine.json")).dry_run()
        loop = made["loop.json"]
        self.assertEqual(loop, dict(plain, interval_ms=1000, max=50, made_up_key={"a": [1]}, on_start=["true"], exec="mine.json"))
        self.assertEqual(list(loop)[:len(plain)], list(plain))                       # compile's keys keep their place, new ones at the end
        self.assertEqual(agent(hooks={}, loop=defs.loop(interval_ms=-7)).dry_run()["loop.json"], dict(plain, interval_ms=-7))   # unchecked
        self.assertEqual(agent(hooks={}, loop=defs.loop(interval_ms="soon")).dry_run()["loop.json"]["interval_ms"], "soon")   # unchecked
        self.assertEqual(agent(hooks={}, loop=defs.loop()).dry_run(), agent(hooks={}).dry_run())
        self.assertEqual(agent(loop=defs.loop(**{"odd-name": 1})).dry_run()["loop.json"]["odd-name"], 1)

    def test_without_loop_the_agent_fsm_template_loop(self):
        """no loop=: loop.json is still the agent-fsm template's (apart from its description), 300 ms."""
        loop = json.loads((TEMPLATES / "agent-fsm" / "loop.json").read_text())
        made = agent(hooks={}).dry_run()["loop.json"]
        self.assertEqual({k: v for k, v in made.items() if k != "description"}, {k: v for k, v in loop.items() if k != "description"})

    def test_spec_bad(self):
        cases = {"not from defs.loop": ({"interval_ms": 1000}, "must come from defs.loop"),
                 "a number": (1000, "must come from defs.loop"),
                 "a key not JSON": (defs.loop(max={1, 2}), "cannot be written as JSON")}
        for why, (value, line) in cases.items():
            with self.subTest(why=why):
                self.assertRaisesRegex(defs.SpecBad, line, agent(loop=value).dry_run)
        self.assertRaises(TypeError, defs.loop, 1000)                  # by name only: defs.loop(interval_ms=1000)
        eca = self.folder("eca")
        (eca / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json", "system": "system.txt"}}))
        self.assertRaisesRegex(defs.SpecBad, "loop needs fsm", agent(fsm=None, loop=defs.loop(interval_ms=1000)).dry_run, str(eca))

    def test_compile_and_load(self):
        base = self.folder("base")
        (base / "agent.py").write_text(HEAD + "defs.main(defs.Agent('B.', system='', tools=[], llm={}, fsm=defs.std.fsm(), "
                                              "loop=defs.loop(interval_ms=1500)))\n")
        r = run_agent(base / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((base / "loop.json").read_text())["interval_ms"], 1500)
        got = defs.load(str(base))
        self.assertEqual(got.loop, {"kind": "loop", "keys": {"interval_ms": 1500}})
        self.assertEqual(agent(loop=got.loop).dry_run()["loop.json"]["interval_ms"], 1500)    # loop=base.loop takes it over
        self.assertEqual(agent().dry_run()["loop.json"]["interval_ms"], 300)                  # like every field: only when written
        (base / "agent.py").write_text(HEAD + "defs.main(defs.Agent('B.', system='', tools=[], llm={}, fsm=defs.std.fsm(), "
                                              "loop=defs.loop(max={1})))\n")
        r = run_agent(base / "agent.py", "--compile", home=self.home)
        self.assertEqual((r.returncode, len(r.stderr.splitlines())), (1, 1), r.stderr)
        self.assertIn("base: error: SpecBad a declared value cannot be written as JSON", r.stderr)
        self.assertEqual(json.loads((base / "loop.json").read_text())["interval_ms"], 1500)  # nothing written


if __name__ == "__main__":
    unittest.main()
