# 驗 eca 範本的延後關畫面 hook 兩格存在、驗格成功且啟動撤單排第一。
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "py"))
from aos.agentlib import hooks


class ScreenLinger(unittest.TestCase):
    def test_default_hooks(self):
        table = json.loads((PROTO / "templates/eca-claude/hooks.json").read_text())["hooks"]
        self.assertEqual(next(iter(table)), "screen_linger_start")
        self.assertEqual(sorted(n for n, e in table.items() if e["event"] == "after_start")[0], "screen_linger_start")
        for name, event in (("screen_linger_start", "after_start"), ("screen_linger_stop", "after_stop")):
            hooks.validate_entry(table[name])
            self.assertEqual(table[name]["event"], event)
            self.assertEqual(table[name]["on_error"], "continue")
            self.assertEqual(table[name]["timeout_ms"], 4000)
            self.assertEqual(table[name]["handler"]["$path"], "/lib/tools/agent/screen_linger")


if __name__ == "__main__":
    unittest.main()
