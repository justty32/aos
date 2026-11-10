# Check lock release still frees cleanly and stays exclusive under parallel senders after the close-before-rename change.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

PROTO = Path(__file__).resolve().parents[3]
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
ENV['PATH'] = ':'.join(str(PROTO / 'impls' / p / 'bin') for p in ('aos-lock', 'aos-post')) + ':' + ENV['PATH']
# 跑在別的檔案系統（例 /mnt/c）：AOS_LOCK_TEST_DIR＝要用的上層資料夾
BASE = os.environ.get('AOS_LOCK_TEST_DIR') or None


def run(*argv, stdin=''):
    return subprocess.run(list(argv), input=stdin, env=ENV, capture_output=True, text=True, timeout=60)


class Release(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-lock-release-', dir=BASE)
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_cli_acquire_release(self):
        t = self.d / 'data.json'
        t.write_text('{}')
        self.assertEqual(run('aos-lock', 'acquire', str(t)).returncode, 0)
        self.assertTrue((self.d / 'data.json.lock').is_dir())
        p = run('aos-lock', 'release', str(t))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(x.name for x in self.d.iterdir()), ['data.json'])
        p = run('aos-lock', 'release', str(t))
        self.assertEqual(p.returncode, 1)
        self.assertIn('LockMissing', p.stderr)

    def test_parallel_ordered_sends_hold_and_release_flock_locks(self):
        # --ordered 用庫的鎖（holder.flock 開著）：放鎖先掛 .reaping、關 fd 再改名；並發下序號不重複、不留殘骸
        box = self.d / 'box'
        self.assertEqual(run('aos-post', 'init', str(box)).returncode, 0)
        with ThreadPoolExecutor(8) as pool:
            got = list(pool.map(lambda i: run('aos-post', 'send', '--ordered', str(box), stdin=json.dumps({'i': i})),
                                range(24)))
        bad = [p.stderr for p in got if p.returncode]
        self.assertEqual(bad, [])
        names = [p.stdout.strip() for p in got]
        self.assertEqual(len(set(names)), 24)
        self.assertFalse((box / 'order.lock').exists())   # 鎖本身一定放掉
        # 改名走的殘骸：ext4 上一定刪乾淨；/mnt/c 偶爾留一個（刪的那一刻別人開著裡面的檔，不擋人，README「殘骸」）
        left = [x.name for x in box.iterdir() if '.releasing.' in x.name]
        if BASE is None:
            self.assertEqual(left, [])


if __name__ == '__main__':
    unittest.main()
