# Verify aos-mcp's --hooks DEF: before_tool changes / blocks a call, after_tool changes the result, no --hooks = no hooks, a failing hook = isError.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
MCP = PROTO / 'cmd' / 'aos-mcp' / 'bin' / 'aos-mcp'
PRELUDE = """import json, os, sys
ev = json.load(sys.stdin)
with open(%r, 'a') as f:
    f.write(json.dumps(ev) + '\\n')
"""


class McpHooks(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-hooks-'))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.defn, self.st, self.bin = self.root / 'def', self.root / 'st', self.root / 'bin'
        for d in (self.defn, self.st, self.bin):
            d.mkdir()
        (self.defn / 'interfaces.json').write_text(json.dumps({'aos-agent': {'tools': 'tools.json', 'hooks': 'hooks.json'}}))
        self.reg = self.defn / 'tools.json'
        self.reg.write_text('{}')
        self.log, self.calls = self.root / 'hooks.jsonl', self.root / 'calls.jsonl'
        fake = self.bin / 'aos-tools'                # ls 列一個 echo；call 記一行、把 stdin 原樣印回
        fake.write_text('#!%s\nimport json, sys\nif "ls" in sys.argv:\n    print(json.dumps([{"name": "echo", "path": "/fake/echo", "tooldef": {}}]))\n'
                        'else:\n    data = sys.stdin.read()\n    open(%r, "a").write(data + "\\n")\n    print(data)\n'
                        % (sys.executable, str(self.calls)))
        fake.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['PATH'] = os.pathsep.join([str(self.bin), os.path.expanduser('~/.local/bin'), self.env['PATH']])

    def hook(self, name, body=''):
        path = self.defn / (name + '.py')
        path.write_text('#!' + sys.executable + '\n' + PRELUDE % str(self.log) + body)
        path.chmod(0o755)
        return path.name

    def declare(self, table):
        (self.defn / 'hooks.json').write_text(json.dumps({'hooks': table}))

    def serve(self, *flags, n=1):
        msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}]
        msgs += [{'jsonrpc': '2.0', 'id': 7 + i, 'method': 'tools/call', 'params': {'name': 'echo', 'arguments': {'x': 1}}}
                 for i in range(n)]
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.st), *flags, str(self.reg)],
                           input=''.join(json.dumps(m) + '\n' for m in msgs), capture_output=True, text=True,
                           timeout=30, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        replies = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
        return [m['result'] for m in replies if m.get('id', 0) >= 7], r.stderr

    def events(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def text(self, result):
        return '\n'.join(c['text'] for c in result['content'])

    def test_tool_before_changes_arguments(self):
        self.declare({'ch': {'event': 'before_tool', 'intercept': True, 'condition': 'echo',
                             'handler': self.hook('ch', 'print(json.dumps({"arguments": {"x": 2}}))\n')}})
        (res,), _ = self.serve('--hooks', self.defn)
        self.assertEqual(json.loads(self.text(res)), {'x': 2})
        self.assertFalse(res['isError'])
        (ev,) = self.events()
        self.assertEqual((ev['event'], ev['name'], ev['id'], ev['arguments']), ('before_tool', 'echo', '7', {'x': 1}))

    def test_tool_before_blocks(self):
        self.declare({'blk': {'event': 'before_tool', 'intercept': True, 'handler': self.hook('blk', 'print("not now"); sys.exit(10)\n')}})
        (res,), _ = self.serve('--hooks', self.defn)
        self.assertEqual((self.text(res), res['isError']), ('not now\n', False))
        self.assertFalse(self.calls.exists())
        self.declare({'blk': {'event': 'before_tool', 'intercept': True, 'handler': self.hook('blk', 'sys.exit(10)\n')}})
        (res,), _ = self.serve('--hooks', self.defn)
        self.assertEqual(self.text(res), '[aos] hook: tool echo blocked by hook blk.')
        self.assertEqual([e['event'] for e in self.events()], ['before_tool', 'before_tool'])   # 攔下的不觸發 after_tool

    def test_tool_after_changes_content(self):
        self.declare({'af': {'event': 'after_tool', 'intercept': True, 'handler': self.hook('af', 'print(json.dumps({"content": "changed"}))\n')}})
        (res,), _ = self.serve('--hooks', self.defn)
        self.assertEqual((self.text(res), res['isError']), ('changed', False))
        (ev,) = self.events()
        self.assertEqual((ev['event'], ev['code'], ev['timed_out'], json.loads(ev['content'])), ('after_tool', 0, False, {'x': 1}))

    def test_no_hooks_flag_no_hooks(self):
        self.declare({'blk': {'event': 'before_tool', 'intercept': True, 'handler': self.hook('blk', 'sys.exit(10)\n')}})
        (res,), _ = self.serve()
        self.assertEqual(json.loads(self.text(res)), {'x': 1})
        self.assertEqual(self.events(), [])

    def test_failing_hook_is_error_server_lives(self):
        self.declare({'bad': {'event': 'before_tool', 'handler': self.hook('bad', 'sys.exit(3)\n')}})
        (r1, r2), _ = self.serve('--hooks', self.defn, n=2)
        for res in (r1, r2):
            self.assertTrue(res['isError'])
            self.assertIn('aos-mcp: error: HookFailed hook bad (event before_tool) failed: exited 3', self.text(res))
        self.assertFalse(self.calls.exists())

    def test_on_fail_continue_warns(self):
        self.declare({'bad': {'event': 'after_tool', 'on_error': 'continue', 'handler': self.hook('bad', 'sys.exit(3)\n')}})
        (res,), err = self.serve('--hooks', self.defn)
        self.assertFalse(res['isError'])
        self.assertIn('aos-mcp: warning: hook bad (event after_tool) failed: exited 3', err)

    def test_hooks_flag_needs_folder(self):
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--hooks', str(self.root / 'nope'), str(self.reg)],
                           input='', capture_output=True, text=True, timeout=30, env=self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('aos-mcp: error: ArgumentsBad --hooks', r.stderr)


if __name__ == '__main__':
    unittest.main()
