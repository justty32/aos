# Verify op new from a repo template uses the copy-out rewrite (env when AOS_HOME is set, else absolute) and keeps literal from paths.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / '_entry'
PROTO = Path(__file__).resolve().parents[4]
FAKE = '''#!/usr/bin/env python3
# Provide a local daemon command fixture for birth tests.
import json, os, sys
args = sys.argv[3:]
if args[:2] == ['ctl', 'ls']:
    print('[]')
elif args[:2] == ['ctl', 'who']:
    print('{}')
elif args[:2] == ['ctl', 'add']:
    print(os.path.join(os.environ['AOS_DAEMON'], 'kid'))
else:
    sys.exit(2)
'''


class CopyRepoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        binary = self.root / 'aos-agent'
        binary.write_text(FAKE)
        binary.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env.update(AOS_WS=str(self.root), AOS_DAEMON=str(self.root / 'daemon'), AOS_STACK=str(self.root / 'stack'),
                        PATH=str(self.root) + os.pathsep + os.environ['PATH'], PYTHONDONTWRITEBYTECODE='1')

    def run_new(self, src, **env):
        args = {'op': 'new', 'name': 'kid', 'path': 'born', 'from': src}
        return subprocess.run([sys.executable, str(SOURCE)], input=json.dumps(args), text=True,
                              capture_output=True, env=dict(self.env, **env), timeout=20)

    def tools(self):
        return json.loads((self.root / 'born' / 'tools.json').read_text())['tools']

    def test_repo_template_env_mode(self):
        r = self.run_new(str(PROTO / 'templates' / 'agent-fsm'), AOS_HOME=str(PROTO))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(self.tools()['wall_clock']['path'], {'$env': 'AOS_HOME', '$path': '/lib/base/wall_clock'})
        self.assertEqual(self.tools()['memory']['path'], 'tools/memory')
        mem = json.loads((self.root / 'born' / 'tools' / 'memory' / '_memory.json').read_text())
        self.assertEqual(mem['base'], {'$env': 'AOS_HOME', '$path': '/knowledge/aos'})
        text = (self.root / 'born' / 'tools.json').read_text()
        self.assertNotIn(str(PROTO), text)

    def test_repo_template_absolute_when_env_unset(self):
        r = self.run_new(str(PROTO / 'templates' / 'agent-fsm'))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(self.tools()['wall_clock']['path'], str(PROTO / 'lib' / 'base' / 'wall_clock'))
        self.assertIn('note: AOS_HOME is not set', r.stdout)

    def test_outside_template_through_symlink_uses_literal_path(self):
        real = self.root / 'far' / 'deep' / 'tpl'
        real.mkdir(parents=True)
        (self.root / 'far' / 'deep' / 'tool').mkdir()
        (real / 'interfaces.json').write_text('{"aos-agent": {"tools": "tools.json"}}')
        (real / 'tools.json').write_text('{"tools": {"t": {"path": "../tool"}}}')
        (self.root / 'alias').symlink_to(real, target_is_directory=True)
        r = self.run_new('alias')
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        # 字面路徑 alias/../tool＝<ws>/tool（不是解開捷徑後的 far/deep/tool）
        self.assertEqual(self.tools()['t']['path'], '../tool')


if __name__ == '__main__':
    unittest.main()
