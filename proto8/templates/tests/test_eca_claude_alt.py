"""test_eca_claude_alt - eca-claude-alt stays a verbatim copy of eca-claude except its README, and carries the same CLAUDE_CONFIG_DIR line in .env and screen/.env."""
# 使用者 11-23「就是proto8/template中提供一個eca-claude-alt就好」：除了 README 與兩份 .env，逐檔（內容＋執行位）等於 eca-claude；
# eca-claude 改了沒同步抄過來就紅。畫面（aos-agent open 起 screen/ 子入口）讀 screen/.env、loop 讀頂層 .env，兩份不同＝答話與畫面用不同帳號。只讀檔。
import filecmp
import os
from pathlib import Path
import unittest

TEMPLATES = Path(__file__).resolve().parents[1]
SRC, ALT = TEMPLATES / "agents" / "eca-claude", TEMPLATES / "agents" / "eca-claude-alt"
DIFFER = {"README.md"}
EXTRA = {".env", os.path.join("screen", ".env")}
LINE = "CLAUDE_CONFIG_DIR=${HOME}/.claude-alt"


def files(folder):
    """Relative paths of every file under folder (no __pycache__)."""
    out = set()
    for dirpath, dirnames, names in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for n in names:
            out.add(os.path.relpath(os.path.join(dirpath, n), folder))
    return out


def settings(path):
    """The NAME=VALUE lines of a .env file (comments and blank lines left out)."""
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]


class EcaClaudeAltTest(unittest.TestCase):
    def test_same_files_as_eca_claude(self):
        self.assertEqual(files(ALT), files(SRC) | EXTRA, "eca-claude-alt has other files than eca-claude: copy it again")

    def test_copies_match(self):
        for rel in sorted(files(SRC) - DIFFER):
            with self.subTest(file=rel):
                self.assertTrue(filecmp.cmp(SRC / rel, ALT / rel, shallow=False),
                                "eca-claude-alt/%s differs from eca-claude/%s: copy it again" % (rel, rel))
                self.assertEqual(os.access(SRC / rel, os.X_OK), os.access(ALT / rel, os.X_OK),
                                 "eca-claude-alt/%s: executable bit differs from eca-claude/%s" % (rel, rel))

    def test_both_env_files_set_the_account(self):
        for rel in sorted(EXTRA):
            with self.subTest(file=rel):
                self.assertEqual(settings(ALT / rel), [LINE])
                self.assertTrue((ALT / rel).read_text(encoding="utf-8").startswith("# .env - "))


if __name__ == "__main__":
    unittest.main()
