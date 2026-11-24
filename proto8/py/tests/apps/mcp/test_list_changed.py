# Verify aos-mcp sends notifications/tools/list_changed right after a tools/call that changed the list (11-10 tools-def, "3.同一輪就生效"), not after one that did not, and that --own FILE is used as soon as it exists.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def converse(argv, msgs, env):
    """像用戶端那樣一則一則講：寄一則、有 id 就讀到它的回覆才寄下一則（11-24 起 tools/call 同時跑、回覆照 id 回，
    一次全灌進去就不保證順序）。回 (結束碼, 收到的每一則, stderr)。"""
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    out = []
    for m in msgs:
        p.stdin.write(json.dumps(m) + '\n')
        p.stdin.flush()
        while 'id' in m:
            line = p.stdout.readline()
            if not line:
                break
            out.append(json.loads(line))
            if out[-1].get('id') == m['id']:
                break
    rest, err = p.communicate(timeout=60)
    out += [json.loads(line) for line in rest.splitlines() if line.strip()]
    return p.returncode, out, err

PROTO = Path(__file__).resolve().parents[4]
MCP = PROTO / 'bin' / 'aos-mcp'
CLOCK = PROTO / 'py' / 'tools' / 'base' / 'peek_now_time'
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
        bins = [str(PROTO / 'bin')] + [str(PROTO / 'bin')]
        self.env['PATH'] = os.pathsep.join(bins + [self.env['PATH']])
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_notify_after_a_call_that_changed_the_list(self):
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'peek_now_time', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'grow', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list', 'params': {}},
                {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'clock2', 'arguments': {}}}]
        code, out, err = converse([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), str(self.reg)], msgs, self.env)
        self.assertEqual(code, 0, err)
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
        code, out, err = converse([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), '--own', str(own), str(self.reg)],
                                  msgs, self.env)
        self.assertEqual(code, 0, err)
        self.assertEqual([m.get('id', m.get('method')) for m in out], [1, 2, 'notifications/tools/list_changed', 3])
        self.assertFalse(out[3]['result'].get('isError'), out[3])


if __name__ == '__main__':
    unittest.main()
