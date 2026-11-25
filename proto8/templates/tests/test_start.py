"""test_start - the two starter templates (start-api, start-eca) stay verbatim copies of the templates they were made from, except the few files their README names and the cell programs start-api's ann links dynamically from $AOS_HOME, and carry the same thin env.sh."""
# 起手範本（使用者 11-17 L-10 A）裡的 root/、llm/、perm/、agents/ann/ 是 daemon-root、kernel/llm-kernel、kernel/procs-kernel、agent-fsm、eca-claude 的抄本：
# 原範本改了沒同步抄過來，這支就紅（逐檔比內容與執行位）。樹裡 env.sh 的行為（AOS_HOME 沒設報錯、轉去家裡那份）在
# py/tests/test_env_sh.py 驗。只讀檔、不起任何行程。
# 11-21 起 start-api 的 ann 不帶格程式：fsm.json 四格與 hook 宣告（11-21 起叫 hooks.json）動態連結（使用者 11-20「起手範本確實該改成要借的」，
#   紀錄 thinking/2026-11/21/起手範本-動態連結-1121.md）；README 是 agent-fsm 那份原樣再接一段。
# 11-24 templates 三分：範本分進類別夾（starts/、daemons/、kernels/、agents/），格程式搬到 $AOS_HOME/lib/aos/apps/agent_fsm，
#   agent-fsm 範本自己也動態連結，ann 跟它的差別只剩 llm.json、fsm.json（std.fsm() 編出來的樣子）、README 與多一份 .env。
import filecmp
import json
import os
from pathlib import Path
import unittest

TEMPLATES = Path(__file__).resolve().parents[1]

# starter -> [(folder in the starter, template it copies, files allowed to differ)]
# 11-20 llm kernel 改成掛在根上的一列 llm/（使用者「掛同一塊板子」），加選裝不開的權限站 perm/（使用者「加一份選裝、預設不開」）。
STARTERS = {
    "starts/start-api": [("root", "daemons/daemon-root", {".env"}),
                         ("llm", "kernels/llm-kernel", set()),
                         ("perm", "kernels/procs-kernel", {"kernel.json"}),
                         ("agents/ann", "agents/agent-fsm", {"llm.json", "fsm.json", "README.md"})],
    "starts/start-eca": [("root", "daemons/daemon-root", {".env"}),
                         ("agents/ann", "agents/eca-claude", {"cli.json"})],
}
EXTRA = {("starts/start-api", "agents/ann"): {".env"}}   # files a copy has on top of its template
MISSING = {("starts/start-eca", "agents/ann"): {"compact_hook"}}   # files a copy borrows from its template instead of carrying (11-25)
BORROWED_HOOK = "$AOS_HOME/templates/agents/eca-claude/compact_hook"
CELLS = ("idle.py", "brain.py", "wait.py", "act.py")
SHARED = ("atomic_file.py", "cell_common.py", "compact.py", "llm_settings.py")
# files ann links dynamically from $AOS_HOME/lib/aos/apps/agent_fsm instead of carrying: nothing in ann may name them
LINKED = set(CELLS + SHARED + ("hooks.json",))
LLM_LINE = {"starts/start-api": "AOS_LLM_KERNEL=${AOS_STACK}/procs/llm\n",
            "starts/start-eca": "AOS_LLM_KERNEL=${AOS_WS}/llms/stacks/llm\n"}
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
                    self.assertEqual(files(b), (files(a) | EXTRA.get((starter, sub), set())) - MISSING.get((starter, sub), set()),
                                     "%s/%s has other files than %s: copy it again" % (starter, sub, src))
                    for rel in sorted(files(a) - differ - MISSING.get((starter, sub), set())):
                        self.assertTrue(filecmp.cmp(a / rel, b / rel, shallow=False),
                                        "%s/%s/%s differs from %s/%s: copy it again" % (starter, sub, rel, src, rel))
                        self.assertEqual(os.access(a / rel, os.X_OK), os.access(b / rel, os.X_OK),
                                         "%s/%s/%s: executable bit differs from %s/%s" % (starter, sub, rel, src, rel))
                    for rel in sorted(differ):
                        self.assertFalse(filecmp.cmp(a / rel, b / rel, shallow=False),
                                         "%s/%s/%s is listed as changed but equals %s/%s" % (starter, sub, rel, src, rel))

    def test_ann_links_the_cells(self):
        ann, fsm = TEMPLATES / "starts" / "start-api" / "agents" / "ann", TEMPLATES / "agents" / "agent-fsm"
        self.assertEqual((ann / "fsm.json").read_bytes(), (TEMPLATES / "agents" / "agent-python/fsm.json").read_bytes(),
                         "start-api/agents/ann/fsm.json must be what std.fsm() compiles (templates/agents/agent-python/fsm.json)")
        states = json.loads((ann / "fsm.json").read_text(encoding="utf-8"))["states"]
        self.assertEqual(sorted(s["exec"]["argv"][1]["$path"] for s in states.values()),
                         sorted("/lib/aos/apps/agent_fsm/" + c for c in CELLS))
        for s in states.values():
            prog = s["exec"]["argv"][1]
            self.assertEqual(prog["$env"], "AOS_HOME")
            self.assertTrue((TEMPLATES.parent / "py" / prog["$path"][len("/lib/"):]).is_file(), prog)   # the source of lib/
        self.assertEqual((ann / "interfaces.json").read_bytes(), (fsm / "interfaces.json").read_bytes())
        self.assertTrue((ann / "README.md").read_bytes().startswith((fsm / "README.md").read_bytes()),
                        "start-api/agents/ann/README.md must start with templates/agents/agent-fsm/README.md as it is")
        self.assertFalse(files(ann) & LINKED, "ann carries cell programs it should link")
        for rel in sorted(files(ann) - {"README.md"}):
            text = (ann / rel).read_text(encoding="utf-8")
            for name in sorted(LINKED):
                self.assertNotIn('"%s"' % name, text, "%s names %s, which ann does not carry" % (rel, name))

    def test_eca_ann_borrows_compact_hook(self):
        """start-eca's ann has eca-claude's cli.json, except that its three Claude Code hooks run $AOS_HOME's compact_hook (11-25, user "17.要")."""
        ann = TEMPLATES / "starts" / "start-eca" / "agents" / "ann"
        a = json.loads((TEMPLATES / "agents" / "eca-claude" / "cli.json").read_text(encoding="utf-8"))
        b = json.loads((ann / "cli.json").read_text(encoding="utf-8"))
        hooks_a, hooks_b = a["settings"].pop("hooks"), b["settings"].pop("hooks")
        self.assertEqual(a, b, "start-eca/agents/ann/cli.json differs from eca-claude's in more than the hook commands")
        self.assertEqual(sorted(hooks_a), sorted(hooks_b))
        self.assertTrue((TEMPLATES / BORROWED_HOOK[len("$AOS_HOME/templates/"):]).is_file())
        for event in hooks_a:
            for ga, gb in zip(hooks_a[event], hooks_b[event], strict=True):
                self.assertEqual({k: v for k, v in ga.items() if k != "hooks"}, {k: v for k, v in gb.items() if k != "hooks"})
                for ha, hb in zip(ga["hooks"], gb["hooks"], strict=True):
                    what = ha["command"].rsplit(" ", 1)[1]                     # pre / post / start
                    self.assertEqual({k: v for k, v in ha.items() if k != "command"}, {k: v for k, v in hb.items() if k != "command"})
                    self.assertEqual(hb["command"], 'f="%s"; [ -f "$f" ] && exec python3 "$f" %s; '
                                     'echo "compact_hook: warning: $f is not a file" >&2' % (BORROWED_HOOK, what))

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
        self.assertEqual((TEMPLATES / "starts/start-api/agents/ann/llm.json").read_text(encoding="utf-8").strip(), '{"model": "fake"}')
        self.assertEqual((TEMPLATES / "starts/start-api/perm/kernel.json").read_text(encoding="utf-8").strip(), "{}")
        ann_env = (TEMPLATES / "starts/start-api/agents/ann/.env").read_text(encoding="utf-8")
        self.assertIn("\n# AOS_KERNEL=${AOS_DAEMON}/procs/perm/requests\n", ann_env)   # optional, off by default
        self.assertNotRegex(ann_env, r"(?m)^AOS_")


if __name__ == "__main__":
    unittest.main()
