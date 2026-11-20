"""test_start - the two starter templates (start-api, start-eca) stay verbatim copies of the templates they were made from, except the few files their README names, and carry the same thin env.sh."""
# 起手範本（使用者 11-17 L-10 A）裡的 root/、llm/、perm/、agents/ann/ 是 daemon-root、kernel/llm-kernel、kernel/procs-kernel、agent-fsm、eca-claude 的抄本：
# 原範本改了沒同步抄過來，這支就紅（逐檔比內容與執行位）。樹裡 env.sh 的行為（AOS_HOME 沒設報錯、轉去家裡那份）在
# py/tests/test_env_sh.py 驗。只讀檔、不起任何行程。
import filecmp
import os
from pathlib import Path
import unittest

TEMPLATES = Path(__file__).resolve().parents[1]

# starter -> [(folder in the starter, template it copies, files allowed to differ)]
# 11-20 llm kernel 改成掛在根上的一列 llm/（使用者「掛同一塊板子」），加選裝不開的權限站 perm/（使用者「加一份選裝、預設不開」）。
STARTERS = {
    "start-api": [("root", "daemon-root", {".env"}),
                  ("llm", "kernel/llm-kernel", set()),
                  ("perm", "kernel/procs-kernel", {"kernel.json"}),
                  ("agents/ann", "agent-fsm", {"llm.json"})],
    "start-eca": [("root", "daemon-root", {".env"}),
                  ("agents/ann", "eca-claude", set())],
}
EXTRA = {("start-api", "agents/ann"): {".env"}}   # files a copy has on top of its template
LLM_LINE = {"start-api": "AOS_LLM_KERNEL=${AOS_STACK}/procs/llm\n", "start-eca": "AOS_LLM_KERNEL=${AOS_WS}/llms/stacks/llm\n"}
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
                    self.assertEqual(files(b), files(a) | EXTRA.get((starter, sub), set()),
                                     "%s/%s has other files than %s: copy it again" % (starter, sub, src))
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
            self.assertIn(LLM_LINE[starter], env)
            self.assertNotRegex(env, r"(?m)^AOS_KERNEL=")                 # the llm kernel would inherit it (start-api README)
            self.assertTrue(env.endswith("AOS_HOME=${AOS_HOME}\n"))      # still the required-AOS_HOME check (daemon-root README)
        self.assertEqual((TEMPLATES / "start-api/agents/ann/llm.json").read_text(encoding="utf-8").strip(), '{"model": "fake"}')
        self.assertEqual((TEMPLATES / "start-api/perm/kernel.json").read_text(encoding="utf-8").strip(), "{}")
        ann_env = (TEMPLATES / "start-api/agents/ann/.env").read_text(encoding="utf-8")
        self.assertIn("\n# AOS_KERNEL=${AOS_DAEMON}/procs/perm/requests\n", ann_env)   # optional, off by default
        self.assertNotRegex(ann_env, r"(?m)^AOS_")


if __name__ == "__main__":
    unittest.main()
