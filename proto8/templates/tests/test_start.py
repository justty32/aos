"""test_start - the two starter templates (start-api, start-eca) stay verbatim copies of the templates they were made from, except the few files their README names, and carry the same thin env.sh."""
# 起手範本（使用者 11-17 L-10 A）裡的 root/、llms/def/、agents/ann/ 是 daemon-root、kernel/llm-kernel、agent-fsm、eca-claude 的抄本：
# 原範本改了沒同步抄過來，這支就紅（逐檔比內容與執行位）。樹裡 env.sh 的行為（AOS_HOME 沒設報錯、轉去家裡那份）在
# py/tests/apps/tree_start/test_env_sh.py 驗。只讀檔、不起任何行程。
import filecmp
import os
from pathlib import Path
import unittest

TEMPLATES = Path(__file__).resolve().parents[1]

# starter -> [(folder in the starter, template it copies, files allowed to differ)]
STARTERS = {
    "start-api": [("root", "daemon-root", {".env"}),
                  ("llms/def", "kernel/llm-kernel", set()),
                  ("agents/ann", "agent-fsm", {"llm.json"})],
    "start-eca": [("root", "daemon-root", {".env"}),
                  ("agents/ann", "eca-claude", set())],
}
TOP = {"README.md", "env.sh"}           # the only files directly in a starter, besides the folders above


def files(folder):
    """Relative paths of every file under folder (no __pycache__)."""
    out = set()
    for dirpath, dirnames, names in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for n in names:
            out.add(os.path.relpath(os.path.join(dirpath, n), folder))
    return out


class StartTest(unittest.TestCase):
    def test_copies_match_their_templates(self):
        for starter, parts in STARTERS.items():
            for sub, src, differ in parts:
                with self.subTest(starter=starter, folder=sub):
                    a, b = TEMPLATES / src, TEMPLATES / starter / sub
                    self.assertEqual(files(b), files(a), "%s/%s has other files than %s: copy it again" % (starter, sub, src))
                    for rel in sorted(files(a) - differ):
                        self.assertTrue(filecmp.cmp(a / rel, b / rel, shallow=False),
                                        "%s/%s/%s differs from %s/%s: copy it again" % (starter, sub, rel, src, rel))
                        self.assertEqual(os.access(a / rel, os.X_OK), os.access(b / rel, os.X_OK),
                                         "%s/%s/%s: executable bit differs from %s/%s" % (starter, sub, rel, src, rel))
                    for rel in sorted(differ):
                        self.assertFalse(filecmp.cmp(a / rel, b / rel, shallow=False),
                                         "%s/%s/%s is listed as changed but equals %s/%s" % (starter, sub, rel, src, rel))

    def test_nothing_else_at_the_top(self):
        for starter, parts in STARTERS.items():
            with self.subTest(starter=starter):
                top = {p.name for p in (TEMPLATES / starter).iterdir() if p.is_file()}
                self.assertEqual(top, TOP)
                dirs = {p.relative_to(TEMPLATES / starter).as_posix() for p in (TEMPLATES / starter).rglob("*") if p.is_dir()}
                outer = {d for d in dirs if not any(d == s or d.startswith(s + "/") for s, _, _ in parts)}
                self.assertEqual(outer, {s.split("/")[0] for s, _, _ in parts if "/" in s})

    def test_same_env_sh(self):
        a, b = (TEMPLATES / s / "env.sh" for s in STARTERS)
        self.assertTrue(filecmp.cmp(a, b, shallow=False), "start-api/env.sh and start-eca/env.sh must be the same file")

    def test_overrides(self):
        for starter in STARTERS:
            env = (TEMPLATES / starter / "root" / ".env").read_text(encoding="utf-8")
            self.assertIn("AOS_LLM_KERNEL=${AOS_WS}/llms/stacks/llm\n", env)
            self.assertTrue(env.endswith("AOS_HOME=${AOS_HOME}\n"))      # still the required-AOS_HOME check (daemon-root README)
        self.assertEqual((TEMPLATES / "start-api/agents/ann/llm.json").read_text(encoding="utf-8").strip(), '{"model": "fake"}')


if __name__ == "__main__":
    unittest.main()
