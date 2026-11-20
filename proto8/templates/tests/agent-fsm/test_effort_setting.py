"""agent-fsm 的腦設定 effort（思考程度，11-21）：llm_settings.effort_of 給 brain.py 填進請求信 body 的 effort；壞值 body_fields 也擋（defs check 走那支）。"""
import importlib.util
from pathlib import Path
import unittest

CELLS = Path(__file__).resolve().parents[2] / "agent-fsm"
_spec = importlib.util.spec_from_file_location("llm_settings_effort", CELLS / "llm_settings.py")
llm_settings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_settings)


class Effort(unittest.TestCase):
    def test_effort_is_given_back_and_not_put_into_the_request(self):
        cfg = {"model": "sol", "effort": "high", "temperature": "0.5"}
        self.assertEqual(llm_settings.effort_of(cfg), "high")
        self.assertEqual(llm_settings.body_fields(cfg), ("sol", {"temperature": 0.5}))
        self.assertEqual(llm_settings.effort_of({" effort": "x"}), None)
        self.assertEqual(llm_settings.effort_of({"effort": " max "}), "max")

    def test_not_set_is_none(self):
        self.assertIsNone(llm_settings.effort_of({"model": "sol"}))

    def test_bad_value_is_refused_by_both(self):
        for bad in ("", "  ", 3, None, ["high"]):
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, llm_settings.effort_of, {"effort": bad})
                self.assertRaises(ValueError, llm_settings.body_fields, {"effort": bad})

    def test_effort_is_a_known_key(self):
        self.assertIn("effort", llm_settings.KEYS)
        iface = (CELLS / "interfaces.json").read_text()
        self.assertIn('"effort"', iface)


if __name__ == "__main__":
    unittest.main()
