"""Test the eca-claude template's compact_hook as Claude Code runs it (11-21 top-1121-ecaeffort): pre fires before_compact (change the instructions, give restore text, block = exit 2), post fires after_compact, start prints the restore text once; with no aos-hook it works as before.
11-21 top-1121-hooknew: compact_hook reads aos-hook fire's raw result itself: the first exit 10 blocks, exit-0 stdout objects set instructions / restore in name order, every handler gets the same event, a failure is one warning."""
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
        self.hook({"t_" + ev: {"event": ev, "handler": "hk", "timeout_ms": 10000} for ev in ("before_compact", "after_compact")})
        self.stack = self.t / "stack"
        self.stack.mkdir()

    def hook(self, cells):
        """Put these cells in the definition's hookeds.json (in place of the template's own)."""
        table = json.loads((self.defn / "hookeds.json").read_text())
        table = {"description": table["description"], **cells}
        (self.defn / "hookeds.json").write_text(json.dumps(table))

    def handler(self, name, body):
        (self.defn / name).write_text("#!/usr/bin/env python3\nimport json, os, sys\n" + body)
        (self.defn / name).chmod(0o755)

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

    def test_name_order_same_event(self):
        """Two handlers: both get the same event (the second does not see the first's change); later names win per key."""
        log = self.t / "ev.jsonl"
        common = "ev = json.load(sys.stdin)\nopen(%r, 'a').write(json.dumps([sys.argv[0], ev]) + '\\n')\n" % str(log)
        self.handler("h_a", common + "print(json.dumps({'instructions': 'FROM A', 'restore': 'R-A'}))\n")
        self.handler("h_b", common + "print(json.dumps({'instructions': 'FROM B'}))\n")
        self.hook({"b": {"event": "before_compact", "handler": "h_b"}, "a": {"event": "before_compact", "handler": "h_a"}})
        r = self.run_hook("pre", {"trigger": "manual"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "FROM B")
        self.assertEqual((self.stack / "claude" / "compact_restore.txt").read_text(), "R-A")
        rows = [json.loads(l) for l in log.read_text().splitlines()]
        self.assertEqual([os.path.basename(p) for p, _ in rows], ["h_a", "h_b"])
        self.assertEqual(rows[0][1]["instructions"], rows[1][1]["instructions"])
        self.assertTrue(rows[1][1]["instructions"].startswith("When you write the summary, keep:"))

    def test_failure_is_a_warning(self):
        """A failing handler (exit 3, or stdout not an object) is one warning line; the others still count; exit 0."""
        self.handler("h_a", "json.load(sys.stdin)\nprint('boom', file=sys.stderr)\nsys.exit(3)\n")
        self.handler("h_b", "json.load(sys.stdin)\nprint('not json')\n")
        self.handler("h_c", "json.load(sys.stdin)\nprint(json.dumps({'instructions': 'FROM C'}))\n")
        self.hook({n: {"event": "before_compact", "handler": "h_" + n} for n in ("a", "b", "c")})
        r = self.run_hook("pre", {"trigger": "auto"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "FROM C")
        self.assertIn("compact_hook: warning: hook a (event before_compact) failed", r.stderr)
        self.assertIn("compact_hook: warning: hook b (event before_compact) printed something that is not a JSON object", r.stderr)

    def test_first_block_wins(self):
        """The first exit 10 in name order is the one that blocks (a later exit 10 is not named)."""
        self.handler("h_a", "json.load(sys.stdin)\nprint(json.dumps({'instructions': 'X'}))\n")
        self.handler("h_b", "json.load(sys.stdin)\nprint('stop b')\nsys.exit(10)\n")
        self.handler("h_c", "json.load(sys.stdin)\nprint('stop c')\nsys.exit(10)\n")
        self.hook({n: {"event": "before_compact", "handler": "h_" + n} for n in ("a", "b", "c")})
        r = self.run_hook("pre", {"trigger": "manual"})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("compact blocked by hook b: stop b", r.stderr)
        self.assertNotIn("stop c", r.stderr)

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
