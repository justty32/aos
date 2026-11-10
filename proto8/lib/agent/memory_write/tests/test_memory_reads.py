"""Verify title-first memory search and ignored-name notices without changing node rules."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[2] / "memory" / "_entry"


class MemoryReadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="memory-read-", dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "README.md").write_text("# Knowledge\nSummary\n")
        (self.root / "note.md").write_text("# Note\nNeedle\n")

    def run_tool(self, **args):
        env = dict(os.environ, AOS_MEMORY=str(self.root), AOS_CD=str(ENTRY.parent))
        return subprocess.run([str(ENTRY)], input=json.dumps({"op": "find", **args}),
                              text=True, capture_output=True, env=env)

    def paths(self, **args):
        result = self.run_tool(**args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [line.split()[0] for line in result.stdout.splitlines() if line.startswith("  ")]

    def test_title_matches_precede_body_matches_before_limit(self):
        for i in range(25):
            (self.root / ('body%d.md' % i)).write_text('# Body\nNeedle\n')
        (self.root / 'z_title.md').write_text('# NEEDLE title\nSummary\n')
        (self.root / 'y_title.json').write_text('{"title":"Needle JSON"}')
        paths = self.paths(query='needle')
        self.assertEqual(paths[:2], ['y_title', 'z_title'])
        self.assertEqual(len([path for path in paths if path != "…"]), 20)

    def test_ls_and_read_report_ignored_names_at_end(self):
        for name in ('Upper.md', '.hidden.md', '_private.md', 'bad name.json'):
            (self.root / name).write_text('# Hidden\n')
        (self.root / 'BadFolder').mkdir()
        for op in ('ls', 'read'):
            result = self.run_tool(op=op)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.rstrip().endswith(
                '5 files ignored (names must be [a-z0-9_-])'), result.stdout)
            self.assertNotIn('Upper', result.stdout)
        result = self.run_tool(op='read', path='note')
        self.assertNotIn('files ignored', result.stdout)


if __name__ == "__main__":
    unittest.main()
