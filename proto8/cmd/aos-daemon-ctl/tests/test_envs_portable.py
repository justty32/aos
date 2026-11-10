# Verify add_letter's --envs single: with the daemon stack given, the target is {"$env": "AOS_DAEMON", "$path": relative}, so a moved tree still starts; without it, the old absolute path.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO8 = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROTO8 / 'py'))
import daemon_ctl as dc  # noqa: E402


def join_path(base, sub):
    """N-45 的 $path 字串拼接（去掉基底結尾 /、去掉 $path 開頭 /、中間一個 /；# 開頭直接接）。"""
    if sub.startswith('#'):
        return base + sub
    return base.rstrip('/') + '/' + sub.lstrip('/')


class EnvsTarget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.proj = self.root / 'a' / 'proj'
        self.stack = self.proj / 'stacks' / 'root'
        self.stack.mkdir(parents=True)
        self.agent = self.proj / 'defs' / 'p'
        self.agent.mkdir(parents=True)
        (self.agent / '_entry').write_text('#!/bin/sh\necho "K=$K" > "$OUT"\n')
        (self.agent / '_entry').chmod(0o755)
        self.loop = self.proj / 'defs' / 'looper'
        self.loop.mkdir()
        (self.loop / '_entry').write_text(json.dumps({'exec': {'argv': ['true']}, 'interval_ms': 500}))

    def spec(self, target, **kw):
        name, body = dc.add_letter(str(target), **kw)
        return body['procs_added'][name]

    def test_without_daemon_keeps_absolute(self):
        on = self.spec(self.agent, envs={'K': 'v'})
        self.assertEqual(on['exec'], {'argv': ['aos-exec', '--', str(self.agent)], 'envs': {'K': 'v'}})

    def test_with_daemon_writes_env_directive(self):
        on = self.spec(self.agent, envs={'K': 'v'}, daemon=str(self.stack))
        tgt = on['exec']['argv'][2]
        self.assertEqual(tgt, {'$env': 'AOS_DAEMON', '$path': '../../defs/p'})
        self.assertNotIn(str(self.root), json.dumps(on['exec']))   # 單子裡沒有這台的絕對路徑
        self.assertEqual(os.path.realpath(join_path(str(self.stack) + '/', tgt['$path'])), str(self.agent))

    def test_other_fields_unchanged(self):
        old = self.spec(self.agent, envs={'K': 'v'}, ws=str(self.proj), auto_restart=True)
        new = self.spec(self.agent, envs={'K': 'v'}, ws=str(self.proj), auto_restart=True, daemon=str(self.stack))
        old.pop('exec'), new.pop('exec')
        self.assertEqual(old, new)

    def test_no_envs_ignores_daemon(self):
        self.assertEqual(self.spec(self.agent, daemon=str(self.stack)), self.spec(self.agent))
        self.assertEqual(self.spec(self.loop, daemon=str(self.stack)), self.spec(self.loop))

    def test_extra_args_untouched(self):
        job = self.proj / 'job'
        job.write_text('#!/bin/sh\nexit 0\n')
        job.chmod(0o755)
        on = self.spec(job, extra=['a', '/abs/b'], envs={'K': 'v'}, daemon=str(self.stack))
        self.assertEqual(on['exec']['argv'], ['aos-exec', '--', {'$env': 'AOS_DAEMON', '$path': '../../job'}, 'a', '/abs/b'])

    def test_target_outside_daemon_tree_uses_dotdot(self):
        far = self.root / 'elsewhere' / 'q'
        far.mkdir(parents=True)
        (far / '_entry').write_text('#!/bin/sh\nexit 0\n')
        (far / '_entry').chmod(0o755)
        on = self.spec(far, envs={'K': 'v'}, daemon=str(self.stack))
        self.assertEqual(on['exec']['argv'][2], {'$env': 'AOS_DAEMON', '$path': '../../../../elsewhere/q'})

    def test_inline_single_keeps_pointer(self):
        on = self.spec(self.loop, envs={'K': 'v'}, daemon=str(self.stack))
        self.assertEqual(on['exec']['argv'][2], {'$env': 'AOS_DAEMON', '$path': '../../defs/looper/_entry#/exec'})

    def test_daemon_through_symlink_uses_real_path(self):
        link = self.root / 'link'
        link.symlink_to(self.stack)
        on = self.spec(self.agent, envs={'K': 'v'}, daemon=str(link))
        self.assertEqual(on['exec']['argv'][2]['$path'], '../../defs/p')   # 同 daemon 給的 AOS_DAEMON：解開捷徑


@unittest.skipUnless(shutil.which('aos-exec'), 'aos-exec not on PATH')
class MovedTree(unittest.TestCase):
    """真的 aos-exec 解這份單子：搬到另一個前綴、AOS_DAEMON 換成新位置，照樣起、拿得到 envs；單子檔不被改寫。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))

    def make(self, proj):
        (proj / 'stacks' / 'root').mkdir(parents=True)
        agent = proj / 'defs' / 'p'
        agent.mkdir(parents=True)
        (agent / '_entry').write_text('#!/bin/sh\necho "K=$K" > "$OUT"\n')
        (agent / '_entry').chmod(0o755)
        return agent

    def run_single(self, path, daemon, out):
        env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        if daemon is not None:
            env['AOS_DAEMON'] = daemon
        env['OUT'] = str(out)
        return subprocess.run(['aos-exec', '--', str(path) + '#/exec'], env=env, capture_output=True, text=True,
                              timeout=20, stdin=subprocess.DEVNULL)

    def test_move_and_rerun(self):
        a = self.root / 'a' / 'proj'
        agent = self.make(a)
        name, body = dc.add_letter(str(agent), envs={'K': 'hello'}, daemon=str(a / 'stacks' / 'root'))
        single = a / 'stacks' / 'root' / 'exec.json'
        single.write_text(json.dumps({'exec': body['procs_added'][name]['exec']}))
        before = single.read_text()
        r = self.run_single(single, str(a / 'stacks' / 'root') + '/', self.root / 'out_a')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / 'out_a').read_text(), 'K=hello\n')
        b = self.root / 'b' / 'deeper' / 'proj'
        b.parent.mkdir(parents=True)
        shutil.move(str(a), str(b))
        shutil.rmtree(self.root / 'a')
        moved = b / 'stacks' / 'root' / 'exec.json'
        r = self.run_single(moved, str(b / 'stacks' / 'root') + '/', self.root / 'out_b')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / 'out_b').read_text(), 'K=hello\n')
        self.assertEqual(moved.read_text(), before)   # 解出來的值沒寫回檔

    def test_env_unset_fails(self):
        a = self.root / 'a' / 'proj'
        agent = self.make(a)
        name, body = dc.add_letter(str(agent), envs={'K': 'hello'}, daemon=str(a / 'stacks' / 'root'))
        single = self.root / 'exec.json'
        single.write_text(json.dumps({'exec': body['procs_added'][name]['exec']}))
        r = self.run_single(single, None, self.root / 'out')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('AOS_DAEMON', r.stderr)


if __name__ == '__main__':
    unittest.main()
