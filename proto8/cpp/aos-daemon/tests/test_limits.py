# 驗證 daemon 的份額天花板、rlimit、收屍標記與重起行為。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from support import ENV, Fixture, dc, read, until, write


class Limits(unittest.TestCase):
    def fixture(self, name, **cfg):
        f = Fixture('limits-' + name)
        self.addCleanup(f.close)
        write(f.config, dict(read(f.config), **cfg))
        return f

    def script(self, f, name, body):
        p = f.root / (name + '.sh')
        p.write_text('#!/bin/sh\n# Run the bounded resource fixture.\n' + body + '\n')
        p.chmod(0o755)
        return str(p)

    def add(self, f, specs):
        result = dc.ask(str(f.stack), {'procs_added': specs})
        self.assertTrue(result['applied'], result)

    def stopped(self, f, name='job'):
        return until(lambda: (r if (r := f.rows().get(name)) and r['phase'] == 'stopped' else None), timeout=15)

    def cpu_limits(self, row):
        for line in Path('/proc/%s/limits' % row['pid']).read_text().splitlines():
            if line.startswith('Max cpu time'):
                return tuple(int(n) for n in line.split()[3:5])
        self.fail('Max cpu time is missing')

    def test_cpu_hit(self):
        f = self.fixture('cpu').start()
        body = self.script(f, 'cpu', 'while :; do :; done')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 1}}})
        row = self.stopped(f)
        self.assertEqual((row['signal'], row['code'], row['limit_hit']), (24, 152, 'cpu_s'))
        self.assertNotIn('limit_suspect', row)

    def test_file_hit(self):
        f = self.fixture('file').start()
        body = self.script(f, 'file', 'exec head -c 2097152 /dev/zero > "$AOS_STACK/out"')
        self.add(f, {'job': {'exec': body, 'limits': {'file_mb': 1}}})
        row = self.stopped(f)
        self.assertEqual((row['signal'], row['code'], row['limit_hit']), (25, 153, 'file_mb'))

    def test_memory_suspect(self):
        f = self.fixture('memory').start()
        body = self.script(f, 'memory', 'LC_ALL=C exec python3 -c "x = bytearray(1024 * 1024 * 1024)"')
        self.add(f, {'job': {'exec': body, 'limits': {'mem_mb': 256}}})
        row = self.stopped(f)
        self.assertEqual(row['code'], 1)
        self.assertEqual(row['limit_suspect'], 'mem_mb')
        self.assertNotIn('limit_hit', row)
        self.assertIn('MemoryError', (f.cell / 'stderr.txt').read_text())

    def test_empty_uses_default(self):
        f = self.fixture('empty', limits={'files': 256}).start()
        body = self.script(f, 'empty', 'ulimit -n > "$AOS_STACK/files"; exec sleep 30')
        self.add(f, {'job': {'exec': body, 'limits': {}}})
        until(lambda: (f.cell / 'files').exists())
        self.assertEqual(f.row()['limits'], {'files': 256})
        self.assertEqual((f.cell / 'files').read_text().strip(), '256')

    def test_ceiling_rejects_only_bad_rows(self):
        f = self.fixture('max', limits={'cpu_s': 5}, limits_max={'cpu_s': 10}).start()
        body = self.script(f, 'sleep', 'exec sleep 30')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 100}},
                     'missing': {'exec': body, 'limits': {'files': 64}},
                     'good': {'exec': body}})
        self.assertIn('LimitBad cpu_s 100 exceeds limits_max 10', self.stopped(f)['reason'])
        self.assertIn('cpu_s unlimited exceeds limits_max 10', self.stopped(f, 'missing')['reason'])
        self.assertEqual(f.rows()['good']['phase'], 'running')
        self.assertIsNone(f.proc.poll())
        self.assertNotIn('limit_suspect', f.row())

    def test_bad_max_config(self):
        cases = [
            ({'limits_max': {'cpu_s': 10}},
             'limits_max needs limits to name a default for every capped key'),
            ({'limits': {'cpu_s': 20}, 'limits_max': {'cpu_s': 10}},
             'limits.cpu_s 20 exceeds limits_max.cpu_s 10'),
            ({'limits': {'files': 64}, 'limits_max': {'cpu_s': 10}},
             'limits.cpu_s is missing but limits_max.cpu_s is 10'),
            ({'limits_max': {'user': 'root'}},
             'limits_max.user is not allowed (limits_max only caps numbers)'),
            ({'limits_max': {'user': None}},
             'limits_max.user is not allowed (limits_max only caps numbers)'),
        ]
        for i, (cfg, message) in enumerate(cases):
            with self.subTest(cfg=cfg):
                f = self.fixture('bad-max-%d' % i, **cfg)
                r = subprocess.run(['aos-daemon', str(f.config)], cwd=f.root,
                                   env=dict(ENV, AOS_STACK=str(f.stack)), capture_output=True,
                                   text=True, timeout=10)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stderr.strip(), 'aos-daemon: error: CfgBad ' + message)

    def test_procs_warning_once_until_limits_change(self):
        f = self.fixture('procs').start()
        body = self.script(f, 'builtin', ':; exit 0')
        spec = {'exec': body, 'limits': {'procs': 50}, 'auto_restart': True}
        self.add(f, {'job': spec})
        self.stopped(f)
        needle = 'procs 50 counts every process of uid'
        self.assertEqual((f.root / 'daemon.err').read_text().count(needle), 1)
        f.ctl('start', 'job')
        self.stopped(f)
        self.assertEqual((f.root / 'daemon.err').read_text().count(needle), 1)
        spec['limits'] = {'procs': 51}
        self.add(f, {'job': spec})
        f.ctl('start', 'job')
        self.stopped(f)
        self.assertEqual((f.root / 'daemon.err').read_text().count('procs 51 counts every process of uid'), 1)

    def test_clamped_keeps_once_and_is_removed_from_loop(self):
        f = self.fixture('clamped').start()
        body = self.script(f, 'sleep', 'exec sleep 30')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 5}, 'limits_clamped': ['cpu_s']},
                     'loop': {'exec': body, 'interval_ms': 30, 'limits': {'cpu_s': 5},
                              'limits_clamped': ['cpu_s']}})
        until(lambda: f.rows().get('job', {}).get('phase') == 'running' and
              (f.stack / 'procs/loop/loop.json').exists())
        self.assertFalse((f.cell / 'loop.json').exists())
        self.assertNotIn('limits_clamped', f.row())
        cfg = read(f.stack / 'procs/loop/loop.json')
        self.assertEqual(cfg['interval_ms'], 30)
        self.assertNotIn('limits_clamped', cfg)

    def test_cpu_soft_and_hard(self):
        f = self.fixture('cpu-window').start()
        body = self.script(f, 'ready', 'touch "$AOS_STACK/ready" && exec sleep 30')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 2}}})
        until(lambda: (f.cell / 'ready').exists())
        self.assertEqual(self.cpu_limits(f.row()), (2, 3))

    def test_inherited_hard_preflight_and_cpu_fallback(self):
        f = self.fixture('inherited')
        popen = subprocess.Popen
        def limited(argv, **kwargs):
            return popen(['prlimit', '--cpu=5:5', '--', *argv], **kwargs)
        with patch('support.subprocess.Popen', side_effect=limited):
            f.start()
        body = self.script(f, 'ready', 'touch "$AOS_STACK/ready" && exec sleep 30')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 10, 'mem_mb': 256}},
                     'good': {'exec': body, 'limits': {'cpu_s': 5}}})
        row = self.stopped(f)
        self.assertIn('exceeds the daemon\'s own hard limit 5', row['reason'])
        self.assertIsNone(row['signal'])
        self.assertNotIn('limit_suspect', row)
        until(lambda: (f.stack / 'procs/good/ready').exists())
        self.assertEqual(self.cpu_limits(f.rows()['good']), (5, 5))
        self.assertIsNone(f.proc.poll())

    def test_default_user_survives_numeric_replacement(self):
        f = self.fixture('default-user', limits={'user': 'aos-test-no-such-user', 'files': 256}).start()
        body = self.script(f, 'builtin', ':; exit 0')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 2}}})
        row = self.stopped(f)
        self.assertEqual(row['limits'], {'cpu_s': 2, 'user': 'aos-test-no-such-user'})
        self.assertIn('no such user', row['reason'])

    def test_adopt_preserves_hit_and_start_clears_it(self):
        f = self.fixture('adopt-hit').start()
        body = self.script(f, 'cpu', 'while :; do :; done')
        self.add(f, {'job': {'exec': body, 'limits': {'cpu_s': 1}}})
        self.assertEqual(self.stopped(f)['limit_hit'], 'cpu_s')
        f.close()
        f.start()
        self.assertEqual(f.row()['limit_hit'], 'cpu_s')
        self.script(f, 'cpu', 'exec sleep 30')
        f.ctl('start', 'job')
        until(lambda: f.row()['phase'] == 'running')
        self.assertNotIn('limit_hit', f.row())
        self.assertNotIn('limit_suspect', f.row())


if __name__ == '__main__':
    unittest.main(verbosity=2)
