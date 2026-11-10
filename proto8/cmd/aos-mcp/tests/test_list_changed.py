# Verify aos-mcp sends notifications/tools/list_changed right after a tools/call that changed the list (11-10 tools-def, "3.同一輪就生效"), not after one that did not, and that --own FILE is used as soon as it exists.
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
GROW = '''import json, os, sys
reg, base = sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else None
data = json.load(open(reg)) if os.path.exists(reg) else {"$override": base, "tools": {}}
data["tools"]["clock2"] = {"path": sys.argv[2]}
json.dump(data, open(reg, "w"))
print("added clock2")
'''


class ListChanged(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-changed-'))
        self.reg = self.root / 'tools.json'
        grow = self.root / 'grow'
        grow.mkdir()
        (grow / 'grow.py').write_text(GROW)
        (grow / '_entry.json').write_text(json.dumps({'argv': ['python3', 'grow.py', str(self.reg), str(CLOCK)]}))
        (grow / '_tooldef.json').write_text(json.dumps({'description': 'Add clock2 to the list.'}))
        self.reg.write_text(json.dumps({'tools': {'grow': {'path': str(grow)}, 'peek_now_time': {'path': str(CLOCK)}}}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for p in (PROTO / 'impls').glob('*/bin')] + [str(PROTO / 'cmd' / 'aos-tools' / 'bin')]
        self.env['PATH'] = os.pathsep.join(bins + [os.path.expanduser('~/.local/bin'), self.env['PATH']])
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_notify_after_a_call_that_changed_the_list(self):
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'peek_now_time', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'grow', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list', 'params': {}},
                {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'clock2', 'arguments': {}}}]
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), str(self.reg)],
                           input=''.join(json.dumps(m) + '\n' for m in msgs), capture_output=True, text=True,
                           timeout=60, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
        self.assertTrue(out[0]['result']['capabilities']['tools']['listChanged'])
        order = [m.get('id', m.get('method')) for m in out]
        self.assertEqual(order, [1, 2, 3, 'notifications/tools/list_changed', 4, 5])
        self.assertIn('clock2', [t['name'] for t in out[4]['result']['tools']])
        self.assertFalse(out[5]['result'].get('isError'), out[5])

    def test_own_registry_made_during_the_session(self):
        own = self.root / 'st' / 'tools.json'
        (self.root / 'st').mkdir()
        grow = self.root / 'grow'
        (grow / '_entry.json').write_text(json.dumps({'argv': ['python3', 'grow.py', str(own), str(CLOCK), str(self.reg)]}))
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'grow', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'clock2', 'arguments': {}}}]
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), '--own', str(own), str(self.reg)],
                           input=''.join(json.dumps(m) + '\n' for m in msgs), capture_output=True, text=True,
                           timeout=60, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
        self.assertEqual([m.get('id', m.get('method')) for m in out], [1, 2, 'notifications/tools/list_changed', 3])
        self.assertFalse(out[3]['result'].get('isError'), out[3])


if __name__ == '__main__':
    unittest.main()
