# 驗 eca-pi 範本（11-18）：cli.json 讀得過、kind pi、畫面子介面同 eca-claude、工具登記檔跟 eca-claude 同一份、hook 格都驗得過。
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

    def test_screen_and_tools_same_as_eca_claude(self):
        decl = json.loads((PI / "interfaces.json").read_text())["aos-agent"]
        self.assertEqual(decl["screen"], "screen")                 # 11-18 丙案：aos-agent open 開 pi 的畫面
        for name in ("_entry", "interfaces.json"):
            self.assertEqual((PI / "screen" / name).read_text(), (PROTO / "templates/eca-claude/screen" / name).read_text())
        self.assertEqual((PI / "tools.json").read_text(), (PROTO / "templates/eca-claude/tools.json").read_text())
        self.assertEqual((PI / "_entry").read_text(), (PROTO / "templates/eca-claude/_entry").read_text())

    def test_hooks_validate(self):
        table = json.loads((PI / "hookeds.json").read_text())
        self.assertIsInstance(table.pop("description"), str)
        self.assertEqual(sorted(table), ["mail_notify", "screen_linger_start", "screen_linger_stop", "timer"])
        claude = json.loads((PROTO / "templates/eca-claude/hookeds.json").read_text())
        for name in ("screen_linger_start", "screen_linger_stop"):
            self.assertEqual(table[name], claude[name])
        for entry in table.values():
            hooks.check_entry(entry)


if __name__ == "__main__":
    unittest.main()
