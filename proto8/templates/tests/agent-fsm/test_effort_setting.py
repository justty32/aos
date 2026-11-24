"""agent-fsm 的腦設定 reasoning_effort（思考程度，11-21）：llm_settings.reasoning_effort_of 給 brain.py 填進請求信 body；不進 request；壞值 body_fields 也擋（defs check 走那支）。"""
import importlib.util
from pathlib import Path
import unittest

PROTO = Path(__file__).resolve().parents[3]
CELLS = PROTO / "py" / "aos" / "apps" / "agent_fsm"   # 格的程式（11-24 起搬出範本，裝好在 lib/aos/apps/agent_fsm）
TEMPLATE = PROTO / "templates" / "agents" / "agent-fsm"   # 範本本身（給人抄的定義）
_spec = importlib.util.spec_from_file_location("llm_settings_effort", CELLS / "llm_settings.py")
llm_settings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_settings)


class ReasoningEffort(unittest.TestCase):
    def test_given_back_and_not_put_into_the_request(self):
        cfg = {"model": "sol", "reasoning_effort": "high", "temperature": "0.5"}
        self.assertEqual(llm_settings.reasoning_effort_of(cfg), "high")
        self.assertEqual(llm_settings.body_fields(cfg), ("sol", {"temperature": 0.5}))
        self.assertEqual(llm_settings.reasoning_effort_of({"reasoning_effort": " max "}), "max")

    def test_not_set_is_none_and_the_old_name_is_not_read(self):
        self.assertIsNone(llm_settings.reasoning_effort_of({"model": "sol"}))
        self.assertIsNone(llm_settings.reasoning_effort_of({"effort": "high"}))

    def test_bad_value_is_refused_by_both(self):
        for bad in ("", "  ", 3, None, ["high"]):
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, llm_settings.reasoning_effort_of, {"reasoning_effort": bad})
                self.assertRaises(ValueError, llm_settings.body_fields, {"reasoning_effort": bad})

    def test_is_a_known_key(self):
        self.assertIn("reasoning_effort", llm_settings.KEYS)
        self.assertNotIn("effort", llm_settings.KEYS)
        self.assertIn('"reasoning_effort"', (TEMPLATE / "interfaces.json").read_text())


if __name__ == "__main__":
    unittest.main()
