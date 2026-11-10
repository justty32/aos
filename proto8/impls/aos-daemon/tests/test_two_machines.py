# Check two-machines daemon fixes: copies never adopt the original tree, and mailbox rows re-resolve directives on start.
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

from support import ENV, read, until, write

BODY = '''#!/usr/bin/env python3
# Record who started me (stack, workspace, script name), then idle.
import json, os, pathlib, sys, time
s = pathlib.Path(os.environ['AOS_STACK'])
(s / 'seen.json').write_text(json.dumps({'pid': os.getpid(), 'stack': os.environ['AOS_STACK'],
    'ws': os.environ.get('AOS_WS'), 'tag': os.path.basename(sys.argv[0])}))
time.sleep(60)
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        return 'zombie' not in Path('/proc/%d/status' % pid).read_text().lower()
    except OSError:
        return False


def environ(pid):
    raw = Path('/proc/%d/environ' % pid).read_bytes().split(b'\0')
    return dict(kv.decode().split('=', 1) for kv in raw if b'=' in kv)


class Tree:
    """One daemon tree in a folder: daemon.json, stack/, body scripts."""

    def __init__(self, root, procs=None):
        self.root = Path(root)
        self.stack = self.root / 'stack'
        self.proc = None
        self.pids = set()
        if procs is not None:
            self.stack.mkdir(parents=True, exist_ok=True)
            for name in ('body_a.py', 'body_b.py'):
                (self.root / name).write_text(BODY)
                (self.root / name).chmod(0o755)
            write(self.root / 'daemon.json', {'interval_ms': 20, 'procs': procs})

    def start(self, **env):
        self.err = open(self.root / 'daemon.err', 'a')
        self.proc = subprocess.Popen(['aos-daemon', str(self.root / 'daemon.json')], cwd=self.root,
                                     env=dict(ENV, AOS_STACK=str(self.stack), **env),
                                     stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (read(self.stack / 'procs_state.json', {}) or {}).get('pid') == self.proc.pid)
        return self

    def rows(self):
        return (read(self.stack / 'procs_state.json', {}) or {}).get('procs', {})

    def running(self, name):
        def got():
            r = self.rows().get(name)
            if r and r.get('phase') == 'running' and r.get('pid'):
                seen = read(self.stack / 'procs' / name / 'seen.json')
                if seen:
                    self.pids.add(r['pid'])
                    return r
            return None
        return until(got, timeout=10)

    def post(self, body):
        p = subprocess.run(['aos-post', 'send', str(self.stack / 'procs_requests')], input=json.dumps(body),
                           text=True, capture_output=True, env=ENV, timeout=10)
        assert p.returncode == 0, p.stderr

    def stop(self, sig=signal.SIGTERM):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(sig)
            self.proc.wait(timeout=20)
        if self.proc is not None:
            self.err.close()
        self.proc = None

    def kill_all(self):
        self.stop(signal.SIGKILL)
        for pid in self.pids:
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                pass


class TwoMachines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-daemon-tm-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def tree(self, name, procs=None):
        t = Tree(self.base / name, procs)
        self.addCleanup(t.kill_all)
        return t

    def test_copy_of_running_tree_starts_its_own_children(self):
        # 原樹還在跑時 cp -a、起副本：副本自己起子項（設定裡的、信箱加的都算），原樹的行程不被接管，停副本不影響原樹（I2 ④ 的反面）
        a = self.tree('a', {'job': './body_a.py'}).start()
        a.post({'procs_added': {'mail': {'exec': str(a.root / 'body_b.py'), 'interval_ms': 0}}})
        orig = {n: a.running(n)['pid'] for n in ('job', 'mail')}
        shutil.copytree(a.root, self.base / 'b', symlinks=True)
        b = self.tree('b')
        b.start()
        for n in ('job', 'mail'):
            row = b.running(n)
            self.assertNotEqual(row['pid'], orig[n], n)
            self.assertTrue(alive(orig[n]), n)
            # seen.json 是 cp 時從原樹帶過來的舊檔；等副本自己的子項寫上它（機器忙時要一點時間）
            end = time.monotonic() + 10
            while True:
                seen = read(b.stack / 'procs' / n / 'seen.json')
                if str(seen.get('stack', '')).startswith(str(b.root)) or time.monotonic() > end:
                    break
                time.sleep(.05)
            self.assertTrue(seen['stack'].startswith(str(b.root)), seen)
            self.assertTrue(environ(row['pid'])['AOS_STACK'].startswith(str(b.root)))
        b.stop()
        time.sleep(.3)
        for n in ('job', 'mail'):
            self.assertTrue(alive(orig[n]), n)
            self.assertEqual(a.rows()[n]['pid'], orig[n])

    def test_restarted_daemon_still_adopts_its_own_children(self):
        # 自己的子項照舊接回：exec 型（exec 了）與內嵌單子（fork 後沒 exec，environ 是 daemon 的）
        a = self.tree('a', {'job': './body_a.py', 'inst': {'exec': {'argv': ['./body_b.py']}}}).start()
        before = {n: a.running(n)['pid'] for n in ('job', 'inst')}
        a.stop(signal.SIGKILL)
        a.start()
        time.sleep(.3)
        for n in ('job', 'inst'):
            row = a.running(n)
            self.assertEqual(row['pid'], before[n], n)
            self.assertTrue(alive(before[n]))

    def test_mailbox_row_keeps_directives_and_resolves_on_each_start(self):
        # 信箱加的列寫 {"$env": …}：表上存原形；改環境變數、重起 daemon＝子項照新值（使用者「兩台各自設一次...不要限制只設一次」）
        a = self.tree('a', {})
        for w in ('ws1', 'ws2'):
            (a.root / w).mkdir()
        env1 = dict(MY_WS=str(a.root / 'ws1'), MY_BODY='body_a.py', MY_LOOP_BODY=str(a.root / 'body_a.py'))
        a.start(**env1)
        a.post({'procs_added': {
            'once': {'exec': {'$env': 'MY_BODY'}, 'ws': {'$env': 'MY_WS'}},
            'looped': {'exec': {'$env': 'MY_LOOP_BODY'}, 'ws': {'$env': 'MY_WS'}, 'interval_ms': 0}}})
        for n in ('once', 'looped'):
            row = a.running(n)
            self.assertEqual(row['as_written']['ws'], {'$env': 'MY_WS'})
            self.assertIn('$env', row['as_written']['exec'])
            seen = read(a.stack / 'procs' / n / 'seen.json')
            self.assertEqual((seen['ws'], seen['tag']), (str(a.root / 'ws1'), 'body_a.py'), n)
        a.stop()
        for n in ('once', 'looped'):
            (a.stack / 'procs' / n / 'seen.json').unlink()
        env2 = dict(MY_WS=str(a.root / 'ws2'), MY_BODY='body_b.py', MY_LOOP_BODY=str(a.root / 'body_b.py'))
        a.start(**env2)
        for n in ('once', 'looped'):
            row = a.running(n)
            seen = read(a.stack / 'procs' / n / 'seen.json')
            self.assertEqual((seen['ws'], seen['tag']), (str(a.root / 'ws2'), 'body_b.py'), n)
            self.assertEqual(row['as_written']['ws'], {'$env': 'MY_WS'})
            self.assertEqual(os.path.normpath(os.path.join(a.stack, row['ws'])), str(a.root / 'ws2'))
        # 拿掉變數再起：解不開＝留 stopped＋原因，不起舊值
        a.stop()
        a.start()
        row = until(lambda: (r if (r := a.rows().get('once')) and r['phase'] == 'stopped' else None))
        self.assertIn('DirectiveBad', row['reason'])


if __name__ == '__main__':
    unittest.main()
