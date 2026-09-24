"""09-24 使用者裁決 1：檔案工具的根＝整個 /work（掛進來的全部），唯讀掛點寫不進去、錯誤看得懂。

真的跑 bwrap 的那組在這台沒 bwrap 時 skip；不用 bwrap 的那組直接給 AOS_TOOL_ROOT／AOS_TOOL_FENCE。
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_jail import BASE_TOOLS, CLI, bwrap_works


def last_json(text):
    return json.loads(text.strip().splitlines()[-1])


@unittest.skipUnless(bwrap_works(), '這台沒有可用的 bwrap')
class JailedFileToolsTests(unittest.TestCase):
    """擺設：ws/（可寫、起點，a.txt）、ref/（唯讀，doc.txt）、amy/（沒掛，有祕密）。"""

    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-round2-')))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        for name in ('ws', 'ref', 'amy'):
            (self.d / name).mkdir()
        (self.d / 'ws' / 'a.txt').write_text('in ws\n')
        (self.d / 'ref' / 'doc.txt').write_text('reference text\n')
        (self.d / 'amy' / 'info.json').write_text('{"secret": "amy-secret"}')

    def tool(self, name, args):
        argv = [sys.executable, str(CLI), '--mount', 'ws=%s' % (self.d / 'ws'),
                '--mount-ro', 'ref=%s' % (self.d / 'ref'), '--chdir', 'ws', '--', str(BASE_TOOLS / name)]
        return subprocess.run(argv, input=json.dumps(args), capture_output=True, text=True, timeout=30)

    def test_read_second_mount(self):
        for path in ('../ref/doc.txt', '/work/ref/doc.txt'):
            with self.subTest(path=path):
                r = self.tool('read', {'path': path})
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn('reference text', r.stdout)

    def test_ls_find_grep_see_all_mounts(self):
        r = self.tool('ls', {'path': '/work'})
        self.assertEqual(r.stdout.split(), ['ref/', 'ws/'])
        self.assertEqual(self.tool('ls', {}).stdout.split(), ['a.txt'])      # 起點照舊是 ws
        r = self.tool('find', {'pattern': '*.txt', 'path': '/work'})
        self.assertEqual(r.stdout.split(), ['../ref/doc.txt', 'a.txt'])
        r = self.tool('grep', {'pattern': 'reference', 'path': '../ref'})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('../ref/doc.txt:1:reference text', r.stdout)

    def test_write_into_readonly_mount_is_refused(self):
        r = self.tool('write', {'path': '../ref/new.txt', 'content': 'x'})
        self.assertEqual(r.returncode, 1)
        err = last_json(r.stdout)
        self.assertEqual(err['error'], 'ReadOnly')
        self.assertIn('read-only', err['message'])
        self.assertIn('Writable folders: /work/ws.', err['message'])
        self.assertFalse((self.d / 'ref' / 'new.txt').exists())
        r = self.tool('write', {'path': '/work/ref/sub/new.txt', 'content': 'x'})     # 要建資料夾也一樣
        self.assertEqual(last_json(r.stdout)['error'], 'ReadOnly')
        r = self.tool('edit', {'path': '../ref/doc.txt', 'old_string': 'reference', 'new_string': 'changed'})
        self.assertEqual(last_json(r.stdout)['error'], 'ReadOnly')
        self.assertEqual((self.d / 'ref' / 'doc.txt').read_text(), 'reference text\n')

    def test_write_directly_in_work_is_refused(self):
        r = self.tool('write', {'path': '/work/loose.txt', 'content': 'x'})
        err = last_json(r.stdout)
        self.assertEqual(err['error'], 'ReadOnly')
        self.assertIn('directly in /work', err['message'])
        r = self.tool('bash', {'command': 'touch /work/loose.txt'})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Read-only file system', r.stdout)

    def test_writable_mount_still_works(self):
        r = self.tool('write', {'path': 'b.txt', 'content': 'new'})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('created b.txt', r.stdout)
        self.assertEqual((self.d / 'ws' / 'b.txt').read_text(), 'new')

    def test_outside_work_still_refused(self):
        for path in ('/etc/passwd', '../../etc/passwd', str(self.d / 'amy' / 'info.json')):
            with self.subTest(path=path):
                r = self.tool('read', {'path': path})
                self.assertIn(last_json(r.stdout)['error'], ('OutsideRoot', 'NotFound'))
                self.assertNotIn('amy-secret', r.stdout)
        self.assertIn('outside the project directory /work', self.tool('read', {'path': '/etc/passwd'}).stdout)


class FenceEnvTests(unittest.TestCase):
    """不用 bwrap：AOS_TOOL_FENCE 包住 AOS_TOOL_ROOT 才算數。"""

    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.d)
        (self.d / 'top' / 'ws').mkdir(parents=True)
        (self.d / 'top' / 'ref').mkdir()
        (self.d / 'top' / 'ref' / 'x.txt').write_text('fenced-in')
        (self.d / 'outside.txt').write_text('outside')

    def read(self, path, **env):
        full = {k: v for k, v in os.environ.items() if k != 'AOS_TOOL_FENCE'}
        full.update(AOS_TOOL_ROOT=str(self.d / 'top' / 'ws'), **env)
        return subprocess.run([sys.executable, str(BASE_TOOLS / 'read')], input=json.dumps({'path': path}),
                              cwd=self.d, env=full, capture_output=True, text=True, timeout=30)

    def test_fence_reaches_sibling(self):
        r = self.read('../ref/x.txt', AOS_TOOL_FENCE=str(self.d / 'top'))
        self.assertIn('fenced-in', r.stdout)
        r = self.read('../../outside.txt', AOS_TOOL_FENCE=str(self.d / 'top'))
        self.assertEqual(last_json(r.stdout)['error'], 'OutsideRoot')

    def test_no_fence_is_old_behaviour(self):
        self.assertEqual(last_json(self.read('../ref/x.txt').stdout)['error'], 'OutsideRoot')

    def test_fence_not_containing_root_is_ignored(self):
        r = self.read('../ref/x.txt', AOS_TOOL_FENCE=str(self.d / 'top' / 'ref'))
        self.assertEqual(last_json(r.stdout)['error'], 'OutsideRoot')


if __name__ == '__main__':
    unittest.main()
