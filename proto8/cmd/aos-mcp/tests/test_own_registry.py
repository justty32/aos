# Verify aos-mcp serves an agent's own registry ("$override" of the definition's) and the definition's, and has no --overlay flag (11-10 aos-tools-cli step 4).
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
MCP = PROTO / 'cmd' / 'aos-mcp' / 'bin' / 'aos-mcp'
CLOCK = PROTO / 'lib' / 'base' / 'wall_clock'


class OwnRegistry(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-own-'))
        (self.root / 'def').mkdir()
        (self.root / 'st').mkdir()
        self.defn = self.root / 'def' / 'tools.json'
        self.defn.write_text(json.dumps({'tools': {'wall_clock': {'path': str(CLOCK)}}}))
        self.own = self.root / 'st' / 'tools.json'
        self.own.write_text(json.dumps({'$override': '../def/tools.json',
                                        'tools': {'wall_clock': None, 'clock2': {'path': str(CLOCK)}}}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['PATH'] = os.pathsep.join([str(PROTO / 'cmd' / 'aos-tools' / 'bin'), os.path.expanduser('~/.local/bin'),
                                            self.env['PATH']])

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def serve(self, *args):
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}]
        stdin = ''.join(json.dumps(m) + '\n' for m in msgs)
        return subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), *map(str, args)],
                              input=stdin, capture_output=True, text=True, timeout=30, env=self.env)

    def names(self, reg):
        r = self.serve(reg)
        self.assertEqual(r.returncode, 0, r.stderr)
        replies = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
        listed = next(m for m in replies if m.get('id') == 2)
        return sorted(t['name'] for t in listed['result']['tools'])

    def test_own_registry(self):
        self.assertEqual(self.names(self.own), ['clock2'])

    def test_definition_registry(self):
        self.assertEqual(self.names(self.defn), ['wall_clock'])

    def test_overlay_flag_is_gone(self):
        r = self.serve('--overlay', self.own, self.defn)
        self.assertEqual(r.returncode, 1)
        self.assertIn('FlagUnknown', r.stderr)


if __name__ == '__main__':
    unittest.main()
