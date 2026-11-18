# 驗 eca-pi 範本（11-18）：cli.json 讀得過、kind pi、沒有畫面子介面、工具登記檔跟 eca-claude 同一份、hook 格都驗得過。
import json
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "py"))
from aos.agentlib import cli_cfg, hooks  # noqa: E402

PI = PROTO / "templates" / "eca-pi"


class EcaPiTemplate(unittest.TestCase):
    def test_cli_json_loads_as_pi(self):
        old = os.environ.pop("AOS_STACK", None)
        try:
            cfg = cli_cfg.load_cfg(str(PI))
        finally:
            if old is not None:
                os.environ["AOS_STACK"] = old
        self.assertEqual(cfg["kind"], "pi")
        self.assertEqual(cli_cfg.reserved_flags("pi", cfg.get("flags", [])), [])
        self.assertNotIn("--model", cfg.get("flags", []))          # llm.json {} = pi's own default model
        self.assertTrue(cfg["registry"].endswith("tools.json"))

    def test_no_screen_and_same_tools_as_eca_claude(self):
        decl = json.loads((PI / "interfaces.json").read_text())["aos-agent"]
        self.assertNotIn("screen", decl)
        self.assertFalse((PI / "screen").exists())
        self.assertEqual((PI / "tools.json").read_text(), (PROTO / "templates/eca-claude/tools.json").read_text())
        self.assertEqual((PI / "_entry").read_text(), (PROTO / "templates/eca-claude/_entry").read_text())

    def test_hooks_validate(self):
        table = json.loads((PI / "hooks.json").read_text())["hooks"]
        self.assertEqual(sorted(table), ["mail_notify", "timer"])
        for entry in table.values():
            hooks.validate_entry(entry)


if __name__ == "__main__":
    unittest.main()
