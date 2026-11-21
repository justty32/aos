"""Test the eca-claude template's compact_hook as Claude Code runs it (11-21 top-1121-ecaeffort): pre fires before_compact (change the instructions, give restore text, block = exit 2), post fires after_compact, start prints the restore text once; with no aos-hook it works as before."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
TEMPLATE = PROTO / "templates" / "eca-claude"
HANDLER = '''#!/usr/bin/env python3
import json, os, sys
ev = json.load(sys.stdin)
with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "seen.jsonl"), "a") as f:
    f.write(json.dumps(ev) + "\\n")
if ev["event"] == "before_compact":
    if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(__file__)), "block")):
        print("not now")
        sys.exit(10)
    print(json.dumps({"instructions": "KEEP THE NAMES", "restore": "RESTORE-MARK"}))
'''


class CompactHook(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="t-ch-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(os.path.realpath(tmp.name))
        self.defn = self.t / "def"
        shutil.copytree(TEMPLATE, self.defn)
        (self.defn / "hk").write_text(HANDLER)
        (self.defn / "hk").chmod(0o755)
        table = json.loads((self.defn / "hooks.json").read_text())
        table["hooks"] = {"t_" + ev: {"event": ev, "handler": "hk", "on_error": "continue", "timeout_ms": 10000}
                          for ev in ("before_compact", "after_compact")}
        (self.defn / "hooks.json").write_text(json.dumps(table))
        self.stack = self.t / "stack"
        self.stack.mkdir()

    def run_hook(self, what, given, home=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_STACK=str(self.stack), AOS_CLI_DEF=str(self.defn), PYTHONDONTWRITEBYTECODE="1")
        if home:
            env["AOS_HOME"] = str(PROTO)
        return subprocess.run([sys.executable, str(self.defn / "compact_hook"), what], input=json.dumps(given),
                              env=env, capture_output=True, text=True, timeout=60)

    def seen(self):
        p = self.defn / "seen.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def test_pre_post_start(self):
        r = self.run_hook("pre", {"trigger": "manual", "custom_instructions": "keep it short"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "KEEP THE NAMES")
        ev = self.seen()[0]
        self.assertEqual((ev["event"], ev["trigger"], ev["asked"], ev["restore"]), ("before_compact", "manual", "keep it short", None))
        self.assertIn("When you write the summary, keep:", ev["instructions"])
        restore = self.stack / "claude" / "compact_restore.txt"
        self.assertEqual(restore.read_text(), "RESTORE-MARK")
        r = self.run_hook("post", {"trigger": "manual", "compact_summary": "SUM"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({k: self.seen()[1][k] for k in ("event", "trigger", "summary")},
                         {"event": "after_compact", "trigger": "manual", "summary": "SUM"})
        r = self.run_hook("start", {"source": "compact"})
        self.assertIn("[aos] compact: this conversation was just compacted", r.stdout)
        self.assertIn("[aos] restored after compact:\nRESTORE-MARK", r.stdout)
        self.assertFalse(restore.exists())                       # printed once
        self.assertNotIn("RESTORE-MARK", self.run_hook("start", {}).stdout)

    def test_block(self):
        (self.defn / "block").write_text("")
        (self.stack / "claude").mkdir()
        (self.stack / "claude" / "compact_restore.txt").write_text("OLD")   # left from an earlier pre: a block clears it
        r = self.run_hook("pre", {"trigger": "auto", "custom_instructions": None})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("compact blocked by hook t_before_compact: not now", r.stderr)
        self.assertEqual(self.seen()[0]["asked"], "")
        self.assertFalse((self.stack / "claude" / "compact_restore.txt").exists())

    def test_without_aos_home_prints_the_template_text(self):
        r = self.run_hook("pre", {"trigger": "manual"}, home=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("When you write the summary, keep:"))
        self.assertEqual(self.seen(), [])

    def test_ann_is_the_same_file(self):
        ann = PROTO / "templates" / "start-eca" / "agents" / "ann" / "compact_hook"
        self.assertEqual(ann.read_bytes(), (TEMPLATE / "compact_hook").read_bytes())


if __name__ == "__main__":
    unittest.main()
