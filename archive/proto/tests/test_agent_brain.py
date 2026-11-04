"""範例 agent 的每圈機器面摘要與 fail_streak。"""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN = os.path.join(ROOT, "examples", "agent", "brain.py")
REAL_BRAIN = os.path.join(ROOT, "examples", "agent-real", "brain.py")


def load_brain():
    spec = importlib.util.spec_from_file_location("test_agent_brain_module", BRAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAgentProgress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-agent-brain-")
        self.brain = load_brain()
        self.brain.LAND = self.tmp
        self.brain.STATE = os.path.join(self.tmp, "state")
        self.brain.ROUNDS = os.path.join(self.brain.STATE, "rounds")
        self.brain.ANSWER = os.path.join(self.brain.STATE, "answer.txt")
        os.makedirs(os.path.join(self.tmp, ".aos"), exist_ok=True)
        with open(os.path.join(self.tmp, "agent.json"), "w", encoding="utf-8") as f:
            json.dump({"tools": ["allowed"], "max_rounds": 9, "max_llm_calls": 9}, f)
        self.brain.write(self.brain.ANSWER, "TOOL: forbidden thing\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_three_failed_rounds_write_progress_and_stop_with_fail_streak(self):
        for _ in range(3):
            self.assertEqual(self.brain.op_act(), 0)

        for n in range(1, 4):
            with open(os.path.join(self.brain.ROUNDS, "%03d" % n, "round.json"),
                      "r", encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary, {
                "round": n, "tool": "forbidden thing", "ok": False,
                "reason": "tool_failed",
            })
        with open(os.path.join(self.tmp, ".aos", "agent-progress.json"),
                  "r", encoding="utf-8") as f:
            progress = json.load(f)
        self.assertEqual(progress["fail_streak"], 3)
        self.assertEqual(progress["latest"]["round"], 3)
        with open(os.path.join(self.brain.STATE, "done.json"), "r", encoding="utf-8") as f:
            done = json.load(f)
        self.assertEqual(done["why"], "fail_streak")
        self.assertEqual(self.brain.read(os.path.join(self.brain.STATE, "next.txt")).strip(), "end")

    def test_agent_brains_remain_identical_copies(self):
        with open(BRAIN, "rb") as f:
            first = f.read()
        with open(REAL_BRAIN, "rb") as f:
            second = f.read()
        self.assertEqual(first, second)
