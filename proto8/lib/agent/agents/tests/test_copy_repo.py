# Verify op new copies a repo template as written ($env AOS_HOME paths, no symlinks, with or without AOS_HOME) and keeps literal from paths.
import json
import os
import shutil
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

    def test_repo_template_is_copied_as_written(self):
        tpl = PROTO / 'templates' / 'agent-fsm'
        for env in ({'AOS_HOME': str(PROTO)}, {}):
            with self.subTest(env=env):
                r = self.run_new(str(tpl), **env)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                self.assertNotIn('note:', r.stdout)
                self.assertEqual(self.tools(), json.loads((tpl / 'tools.json').read_text())['tools'])
                self.assertEqual(self.tools()['memory']['path'], {'$env': 'AOS_HOME', '$path': '/lib/agent/memory'})
                self.assertNotIn(str(PROTO), (self.root / 'born' / 'tools.json').read_text())
                self.assertFalse(any(p.is_symlink() for p in (self.root / 'born').rglob('*')))
                shutil.rmtree(self.root / 'born')

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


    def test_env_file_and_override_rebased(self):
        """11-10 晚：複製定義時 env_file、$override 的相對路徑跟 path 一樣換算成從新位置走回同一個目標。"""
        tpl = self.root / 'tpls' / 'tpl'
        tpl.mkdir(parents=True)
        (self.root / 'tpls' / 'tool').mkdir()
        (self.root / 'tpls' / 'k.env').write_text('K=1\n')
        (self.root / 'tpls' / 'base.json').write_text('{"tools": {}}')
        (tpl / 'interfaces.json').write_text('{"aos-agent": {"tools": "tools.json"}}')
        (tpl / 'tools.json').write_text('{"$override": "../base.json", "tools": {"t": {"path": "../tool", "env_file": "../k.env"}}}')
        r = self.run_new('tpls/tpl')
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        reg = json.loads((self.root / 'born' / 'tools.json').read_text())
        self.assertEqual(reg['tools']['t'], {'path': '../tpls/tool', 'env_file': '../tpls/k.env'})
        self.assertEqual(reg['$override'], '../tpls/base.json')

if __name__ == '__main__':
    unittest.main()
