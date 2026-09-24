"""kernel 健康優先序、錯誤邊界及 ls 輸出。"""
import contextlib
import io
import json
import os
from unittest.mock import patch

import aos_home
import aos_kernel as kernel
from aos_kernel_health import health
from _kernel_util import KernelCase


class KernelHealth(KernelCase):
    def setUp(self):
        super().setUp()
        self.initialize(daemon=str(self.daemon))
        self.ledger = kernel.new_state(self.info, 'chain', 'k', kernel.CLI)
        self.write(self.home / 'state.json', self.ledger)
        self.children = {name: {'state': 'alive'} for name in self.info['cpus']}
        self.alive = patch('aos_daemon.is_alive', return_value=True).start()
        self.addCleanup(patch.stopall)
        patch('aos_daemon.read_state', return_value={'children': self.children}).start()
        self.now = (self.home / 'state.json').stat().st_mtime
        self.boot = 'aos-kernel boot --target %s --daemon-target %s' % (self.home, self.daemon)

    def save(self):
        self.write(self.home / 'state.json', self.ledger)

    def test_ok(self):
        self.assertEqual(health(self.home, now=self.now), ('ok', 'ok'))

    def test_missing_requests_precedes_stopped(self):
        (self.home / 'requests').rmdir()
        self.ledger['phase'] = 'stopped'
        self.save()
        self.assertEqual(health(self.home), ('dirs', 'K 家缺目錄：%s/requests/（跑 aos-kernel check --target %s）' %
                                           (self.home, self.home)))

    def test_all_required_dirs(self):
        for name in ('requests', 'responses', 'cpus'):
            (self.home / name).rmdir()
        self.assertEqual(health(self.home)[1], 'K 家缺目錄：%s（跑 aos-kernel check --target %s）' % (
            '、'.join(str(self.home / name) + '/' for name in ('requests', 'responses', 'cpus')), self.home))

    def test_stopped_precedes_dead_daemon(self):
        self.ledger['phase'] = 'stopped'
        self.save()
        self.alive.return_value = False
        self.assertEqual(health(self.home), ('stopped', '停機中（%s）' % self.boot))

    def test_never_booted(self):
        (self.home / 'state.json').unlink()
        self.assertEqual(health(self.home)[0], 'stopped')

    def test_daemon_precedes_missing_cpu(self):
        self.alive.return_value = False
        self.children.clear()
        self.assertEqual(health(self.home), ('daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s，再 %s）' %
                                           (self.daemon, self.daemon, self.boot)))

    def test_cpu_missing_precedes_stall(self):
        self.children.pop('0')
        self.children['llm']['state'] = 'missing'
        self.assertEqual(health(self.home, now=self.now + 100),
                         ('cpus', 'cpu missing：0、llm（跑 %s）' % self.boot))

    def test_ledger_only_cpu_and_kernel_cpu(self):
        self.ledger['cpus']['old'] = kernel._idle()
        self.ledger['kcpu'] = 'old-k'
        self.save()
        self.assertEqual(health(self.home), ('cpus', 'cpu missing：old、old-k（跑 %s）' % self.boot))

    def test_stall(self):
        self.assertEqual(health(self.home, now=self.now + 11),
                         ('stall', 'tick 停住：11 秒沒前進（跑 aos-kernel check --target %s）' % self.home))

    def test_stall_threshold(self):
        for tick_ms, threshold in ((0, 10), (1000, 10), (2000, 20)):
            with self.subTest(tick_ms=tick_ms):
                self.info['tick_ms'] = tick_ms
                self.assertEqual(health(self.home, info=self.info, now=self.now + threshold)[0], 'ok')
                self.assertEqual(health(self.home, info=self.info, now=self.now + threshold + .1)[0], 'stall')

    def test_stopping_does_not_stall(self):
        self.ledger['phase'] = 'stopping'
        self.save()
        self.assertEqual(health(self.home, now=self.now + 100), ('ok', 'ok'))

    def test_broken_ledger(self):
        for raw in ('{', '[]', '\xff'):
            (self.home / 'state.json').write_bytes(raw.encode('latin1'))
            code, message = health(self.home)
            self.assertEqual(code, 'broken')
            self.assertTrue(message.startswith('kernel 家讀不到：'))
            self.assertTrue(message.endswith('（跑 aos-kernel check --target %s）' % self.home))
            self.assertEqual(len(message.splitlines()), 1)

    def test_not_kernel_home(self):
        self.assertEqual(health(self.daemon)[0], 'broken')
        self.assertEqual(health(self.root / 'absent')[0], 'broken')

    def test_read_exceptions_are_broken_and_single_line(self):
        for error in (aos_home.HomeError('ReadFailed', '壞\n帳本'), OSError('讀\n失敗'), ValueError('壞值')):
            with patch('aos_kernel_health.load_info', side_effect=error):
                code, message = health(self.home)
            self.assertEqual(code, 'broken')
            self.assertEqual(len(message.splitlines()), 1)

    def test_supplied_snapshot_and_info_are_reused(self):
        snapshot = kernel.status(self.home)
        with patch('aos_kernel_health.load_info', side_effect=AssertionError('reread')), \
                patch('aos_home.read_state', side_effect=AssertionError('reread')), \
                patch('aos_daemon.read_state', side_effect=AssertionError('reread')), \
                patch('aos_daemon.is_alive', side_effect=AssertionError('reread')):
            self.assertEqual(health(self.home, snapshot, self.info, self.now), ('ok', 'ok'))

    def test_default_daemon_and_relative_home(self):
        self.info.pop('daemon')
        self.alive.return_value = False
        with patch.dict(os.environ, {'AOS_DAEMON_HOME': str(self.daemon)}):
            self.assertIn(self.boot, health(os.path.relpath(self.home), info=self.info)[1])

    def test_ls_first_line_and_no_duplicate_hint(self):
        self.alive.return_value = False
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(kernel.main(['ls', '--target', str(self.home)]), 0)
        self.assertEqual(out.getvalue().splitlines()[0], 'health ' + health(self.home)[1])
        self.assertNotIn('hint ', out.getvalue())

    def test_ls_json_health_and_other_fields_unchanged(self):
        expected = kernel.status(self.home)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(kernel.main(['ls', '--target', str(self.home), '--json']), 0)
        actual = json.loads(out.getvalue())
        self.assertEqual(actual['health'], {'code': 'ok', 'message': 'ok'})
        self.assertEqual((actual['kernel']['chain'], actual['kernel']['phase'], actual['kernel']['last_seq']),
                         (expected['chain'], expected['phase'], expected['last_seq']))
        self.assertEqual(actual['queue'], expected['queue'])

    def test_ls_broken_ledger_retains_failure(self):
        (self.home / 'state.json').write_text('{')
        for flags in ([], ['--json']):
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(kernel.main(['ls', '--target', str(self.home), *flags]), 1)
            self.assertEqual(out.getvalue(), '')
