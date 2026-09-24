"""kernel 健康優先序（kernel-cli.md 的 ls）、錯誤邊界及 ls 第一行。用假 daemon，不拉真行程。"""
import contextlib
import io
import json
import os
from unittest.mock import patch

import aos_home
import aos_kernel as kernel
from aos_kernel_info import load_info
from aos_kernel_health import agents_health, health
from _kernel_fake import FakeCase, FakeDaemon


class KernelHealth(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 2}, "llm": {"count": 1}})
        self.boot()
        self.settle()
        self.boot_hint = 'aos-kernel boot --target %s' % self.K

    def now(self):
        return (self.K / 'state.json').stat().st_mtime

    def summary(self, dpool, **fields):
        path = self.fake.home / 'pools' / dpool / 'summary.json'
        data = aos_home.read_json(path)
        data.update(fields)
        aos_home.write_json(path, data)

    def test_ok(self):
        self.assertEqual(health(self.K, now=self.now()), ('ok', 'ok'))

    def test_missing_dirs_precede_stopped(self):
        state = self.state()
        state['phase'] = 'stopped'
        aos_home.write_state(self.K, state)
        (self.K / 'requests').rmdir()
        self.assertEqual(health(self.K), ('dirs', 'K 家缺目錄：%s/requests/（跑 aos-kernel check --target %s）' %
                                          (self.K, self.K)))

    def test_all_required_dirs(self):
        import shutil
        for name in ('requests', 'responses', 'pools'):
            shutil.rmtree(self.K / name)
        self.assertEqual(health(self.K)[1], 'K 家缺目錄：%s（跑 aos-kernel check --target %s）' % (
            '、'.join(str(self.K / name) + '/' for name in ('requests', 'responses', 'pools')), self.K))

    def test_never_booted_and_stopped_precede_dead_daemon(self):
        state = self.state()
        state['phase'] = 'stopped'
        aos_home.write_state(self.K, state)
        self.fake.set_alive(False)
        self.assertEqual(health(self.K), ('stopped', '停機中（%s）' % self.boot_hint))
        (self.K / 'state.json').unlink()
        self.assertEqual(health(self.K)[0], 'stopped')

    def test_dead_daemon(self):
        self.fake.set_alive(False)
        self.assertEqual(health(self.K), ('daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s；之後 health 還不是 ok 再 %s）'
                                          % (self.D, self.D, self.boot_hint)))

    def test_work_pool_daemon_dead(self):
        other = FakeDaemon(self.root / 'D2')
        self.addCleanup(other.close)
        self.edit_info(gpu={'count': 1, 'daemon': str(other.home)})
        self.tick()
        other.process()
        self.ticks(2)
        other.process()
        self.assertEqual(health(self.K, now=self.now())[0], 'ok')
        other.set_alive(False)
        self.assertEqual(health(self.K, now=self.now()),
                         ('daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s）' % (other.home, other.home)))

    def test_kernel_cpu_missing_precedes_stall(self):
        self.summary('kernel', running=0, pending=1)
        self.assertEqual(health(self.K, now=self.now() + 100),
                         ('cpus', 'kernel cpu 不在（daemon 沒在跑或還在拉；跑 %s）' % self.boot_hint))
        self.fake.gone('kernel')
        self.assertEqual(health(self.K)[0], 'cpus')

    def test_stall_and_threshold(self):
        self.assertEqual(health(self.K, now=self.now() + 11),
                         ('stall', 'tick 停住：11 秒沒前進（跑 aos-kernel check --target %s）' % self.K))
        info = kernel.load_info(self.K)
        for tick_ms, threshold in ((0, 10), (1000, 10), (2000, 20)):
            with self.subTest(tick_ms=tick_ms):
                info['tick_ms'] = tick_ms
                self.assertEqual(health(self.K, info=info, now=self.now() + threshold)[0], 'ok')
                self.assertEqual(health(self.K, info=info, now=self.now() + threshold + .1)[0], 'stall')

    def test_pool_error_and_gone(self):
        self.fake.errors['default'] = ['NameTaken']
        self.edit_info(default={'count': 3})
        self.ticks(2)
        code, message = health(self.K, now=self.now())
        self.assertEqual(code, 'pools')
        self.assertEqual(message, '池 default：NameTaken（NameTaken）')
        self.fake.gone('llm')
        self.assertEqual(health(self.K, now=self.now()),
                         ('pools', '池 default：NameTaken（NameTaken）；池 llm：池不見了（跑 %s）' % self.boot_hint))

    def test_shrinking_to_zero_is_not_gone(self):
        self.edit_info(llm={'count': 0})
        self.tick()   # 送 count 0 的單、假 daemon 收完就把池拿掉，但回音還沒收
        self.assertEqual(self.state()['pools']['llm']['sent']['count'], 1)
        self.assertEqual(health(self.K, now=self.now())[0], 'ok')

    def test_pool_short_is_recovering(self):
        self.summary('default', running=1, dead=1)
        self.assertEqual(health(self.K, now=self.now()),
                         ('recovering', '池 default 少 1 顆（daemon 在補；看 aos-daemon ls --target %s --pool default）' % self.D))

    def test_moving_is_recovering(self):
        self.fake.linger.add('default')
        self.edit_info(default={'count': 2, 'dpool': 'moved'})
        self.ticks(2)
        code, message = health(self.K, now=self.now())
        self.assertEqual(code, 'recovering')
        self.assertEqual(message, '搬池中：池 default（舊位置 %s default 收完才換）' % self.D)

    def test_stopping_does_not_stall_or_short(self):
        self.stop_kernel()
        self.tick(process=False)
        self.assertEqual(self.state()['phase'], 'stopping')
        self.summary('default', running=0)
        self.assertEqual(health(self.K, now=self.now() + 100), ('ok', 'ok'))

    def test_broken_ledger(self):
        for raw in ('{', '[]', '\xff'):
            (self.K / 'state.json').write_bytes(raw.encode('latin1'))
            code, message = health(self.K)
            self.assertEqual(code, 'broken')
            self.assertTrue(message.startswith('kernel 家讀不到：'))
            self.assertTrue(message.endswith('（跑 aos-kernel check --target %s）' % self.K))
            self.assertEqual(len(message.splitlines()), 1)

    def test_not_kernel_home(self):
        self.assertEqual(health(self.D)[0], 'broken')
        self.assertEqual(health(self.root / 'absent')[0], 'broken')

    def test_read_exceptions_are_broken_and_single_line(self):
        for error in (aos_home.HomeError('ReadFailed', '壞\n帳本'), OSError('讀\n失敗'), ValueError('壞值')):
            with patch('aos_kernel_health.load_info', side_effect=error):
                code, message = health(self.K)
            self.assertEqual(code, 'broken')
            self.assertEqual(len(message.splitlines()), 1)

    def test_supplied_snapshot_and_info_are_reused(self):
        snapshot = kernel.status(self.K)
        info = kernel.load_info(self.K)
        with patch('aos_kernel_health.load_info', side_effect=AssertionError('reread')), \
                patch('aos_kernel_boot.status', side_effect=AssertionError('reread')), \
                patch('aos_daemon.pool_summary', side_effect=AssertionError('reread')), \
                patch('aos_daemon.is_alive', side_effect=AssertionError('reread')):
            self.assertEqual(health(self.K, snapshot, info, self.now()), ('ok', 'ok'))

    def test_relative_home(self):
        self.fake.set_alive(False)
        self.assertIn(self.boot_hint, health(os.path.relpath(self.K))[1])

    def test_ls_first_line(self):
        self.fake.set_alive(False)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(kernel.main(['ls', '--target', str(self.K)]), 0)
        self.assertEqual(out.getvalue().splitlines()[0], 'health ' + health(self.K)[1])

    def test_ls_json_health(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(kernel.main(['ls', '--target', str(self.K), '--json']), 0)
        actual = json.loads(out.getvalue())
        self.assertEqual(actual['health'], {'code': 'ok', 'message': 'ok'})
        expected = kernel.status(self.K)
        self.assertEqual(actual['_metainfo'], {'_type': 'aos_kernel_ls', '_version': 2})
        self.assertEqual((actual['kernel']['chain'], actual['kernel']['phase'], actual['kernel']['last_seq']),
                         (expected['chain'], expected['phase'], expected['last_seq']))
        self.assertEqual(sorted(actual['pools']), sorted(set(expected['pools']) | set(load_info(self.K)['pools'])))

    def test_ls_broken_ledger_retains_failure(self):
        (self.K / 'state.json').write_text('{')
        for flags in ([], ['--json']):
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(kernel.main(['ls', '--target', str(self.K), *flags]), 1)
            self.assertEqual(out.getvalue(), '')


class AgentsHealth(FakeCase):
    def test_order_paused_retrying_resuming(self):
        marks = {'agent-a': ('retrying', '重試中（連敗 1/3）'), 'agent-b': ('resuming', 'x'),
                 'agent-c': ('manual_paused', 'y')}
        self.assertEqual(agents_health(marks),
                         ('agents_paused', 'agent 暫停中：agent-c（手動）（修好原因後 aos-agent continue --all）'))
        del marks['agent-c']
        self.assertEqual(agents_health(marks), ('retrying', '重試中：agent-a（連敗 1/3）'))
        del marks['agent-a']
        self.assertEqual(agents_health(marks), ('resuming', '已解除暫停，等下一次成功：agent-b'))
        self.assertIsNone(agents_health({}))
