# Verify aos-mcp keeps serving when one registry entry is broken (path gone): tools/list leaves it out, tools/call of the others works (11-12 tool-path-broken).
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
MCP = PROTO / 'cmd' / 'aos-mcp' / 'bin' / 'aos-mcp'
CLOCK = PROTO / 'lib' / 'base' / 'peek_now_time'


class BrokenEntry(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-broken-'))
        (self.root / 'st').mkdir()
        self.reg = self.root / 'tools.json'
        self.reg.write_text(json.dumps({'tools': {'clock': {'path': str(CLOCK)},
                                                  'aos_cache': {'path': str(self.root / 'tools' / 'aos_cache')}}}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['PATH'] = os.pathsep.join([str(PROTO / 'cmd' / 'aos-tools' / 'bin'), os.path.expanduser('~/.local/bin'),
                                            self.env['PATH']])

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_list_and_call_with_one_broken(self):
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'clock', 'arguments': {}}}]
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), str(self.reg)],
                           input=''.join(json.dumps(m) + '\n' for m in msgs), capture_output=True, text=True,
                           timeout=60, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        replies = {m.get('id'): m for m in map(json.loads, r.stdout.splitlines()) if m.get('id') is not None}
        self.assertEqual([t['name'] for t in replies[2]['result']['tools']], ['clock'])
        self.assertFalse(replies[3]['result']['isError'], replies[3])
        self.assertIn('aos-tools: warning: tool aos_cache skipped: PathMissing', r.stderr)
        self.assertNotIn('error:', r.stderr)


if __name__ == '__main__':
    unittest.main()
