"""advice-r1：aos-agent check（從 aos-kernel check --agent 搬來）與 aos-kernel ls 的對齊表／--json。"""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aos_agent_cli
import aos_home
import aos_kernel as kernel
import aos_kernel_check
import aos_kernel_cli
import aos_kernel_ls
from test_kernel_fix_r5 import Server

CLI = Path(__file__).resolve().parents[2] / 'cli'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Homes(unittest.TestCase):
    """假 K、假 D、一個 agent 家；不開 daemon。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home, self.daemon = self.root / 'K', self.root / 'D'
        self.daemon.mkdir()
        self.llm('http://127.0.0.1:%d/v1' % free_port())
        # 池式（proto5-2 納入）：info 第 2 版是池表，daemon 家寫在 info 頂層。
        kernel.init(self.home, {'pools': {'default': {'count': 1}, 'llm': {
            'count': 1, 'envs': {'AOS_LLM_CONFIG': str(self.root / 'llm.json')}}}}, daemon=str(self.daemon))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in aos_kernel_check.COMMANDS:
            path = self.bin / name
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if k not in ('AOS_KERNEL_HOME', 'AOS_DAEMON_HOME')}
        env.update(PATH=str(self.bin))
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.agent = self.root / 'amy'
        self.put(self.agent / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                            'llm': {'model': 'small'}})

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(path, value)

    def llm(self, endpoint):
        self.put(self.root / 'llm.json', {'_metainfo': {'_type': 'llm_config', '_version': 1},
                                          'models': {'small': {'endpoint': endpoint, 'model': 'm'}}})

    def agent_check(self, *args, code=0, env=None, target=True):
        out, err = io.StringIO(), io.StringIO()
        argv = ['check', *(['--target', str(self.agent)] if target else []), *map(str, args)]
        with patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = aos_agent_cli.main(argv)
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()


class AgentCheck(Homes):
    def test_kernel_from_env_runs_kernel_and_agent_items(self):
        out, err = self.agent_check(env={'AOS_KERNEL_HOME': str(self.home), 'AOS_DAEMON_HOME': str(self.daemon)})
        self.assertEqual(err, '')
        lines = out.splitlines()
        self.assertEqual(lines[0], 'ok   kernel: K＝%s（取自 AOS_KERNEL_HOME）' % self.home)
        for item in ('ok   info:', 'ok   dirs:', 'warn daemon:', 'ok   pools:', 'ok   llm/llm: 模型代號：small',
                     'ok   agent:', 'ok   agent/tick.pool:', 'ok   agent/llm.pool:', 'ok   agent/tool_pool:',
                     'ok   agent/llm.model:'):
            self.assertIn(item, out)
        self.assertEqual(lines[-1], '設定檢查通過；未測模型連線（--probe 會測）')
        self.assertNotIn('probe/', out)

    def test_kernel_from_tick_json_and_recorded_daemon(self):
        self.put(self.agent / 'tick.json', {'argv': ['aos-agent', 'tick'], 'envs': {'AOS_KERNEL_HOME': str(self.home)}})
        out, _ = self.agent_check()
        self.assertTrue(out.startswith('ok   kernel: K＝%s（取自 tick.json）\n' % self.home), out)
        # 沒設 AOS_DAEMON_HOME：用 K 的池表記的 daemon，不是目前資料夾
        self.assertIn('aos-daemon boot --target %s' % self.daemon, out)

    def test_no_kernel_is_bad_but_agent_still_checked(self):
        out, _ = self.agent_check(code=1)
        self.assertIn('bad  kernel: 找不到 K：沒設 AOS_KERNEL_HOME，也沒有 tick.json', out)
        self.assertIn('ok   agent: agent 設定讀驗通過', out)
        self.assertIn('warn agent/pools: K 讀不到', out)
        self.assertEqual(out.splitlines()[-1], '有 bad，照上面的提示修好再 aos-agent start')

    def test_relative_env_and_mismatch_are_bad(self):
        out, _ = self.agent_check(code=1, env={'AOS_KERNEL_HOME': 'K'})
        self.assertIn('bad  kernel: AOS_KERNEL_HOME 不是絕對路徑：K', out)
        self.put(self.agent / 'tick.json', {'envs': {'AOS_KERNEL_HOME': str(self.root / 'other')}})
        out, _ = self.agent_check(code=1, env={'AOS_KERNEL_HOME': str(self.home)})
        self.assertIn('ok   kernel: K＝%s（取自 AOS_KERNEL_HOME）' % self.home, out)
        self.assertIn('KernelMismatch', out)
        self.assertIn('ok   info:', out)  # 照 AOS_KERNEL_HOME 那個 K 繼續查

    def test_broken_kernel_reports_and_still_checks_agent(self):
        (self.home / 'info.json').write_text('{')
        out, err = self.agent_check(code=1, env={'AOS_KERNEL_HOME': str(self.home)})
        self.assertEqual(err, '')
        self.assertIn('bad  info:', out)
        self.assertIn('（K＝%s，取自 AOS_KERNEL_HOME）' % self.home, out)
        self.assertIn('warn agent/pools:', out)
        self.assertEqual(out.splitlines()[-1], '有 bad，照上面的提示修好再 aos-agent start')

    def test_agent_problems_are_bad(self):
        self.put(self.agent / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                            'llm': {'model': 'nope', 'pool': 'gpu'}})
        out, _ = self.agent_check(code=1, env={'AOS_KERNEL_HOME': str(self.home)})
        self.assertIn('bad  agent/llm.pool: 池 gpu 不在 pools', out)
        self.assertIn('bad  agent/llm.model: 模型 nope 不在 llm 設定', out)

    def test_not_an_agent(self):
        empty = self.root / 'empty'
        empty.mkdir()
        for target, text in ((empty, '沒有 info.json'), (self.home, '是 kernel 家，不是 agent 家')):
            with self.subTest(target=target):
                self.agent = target
                out, err = self.agent_check(code=1, env={'AOS_KERNEL_HOME': str(self.home)})
                self.assertEqual(out, '')
                self.assertTrue(err.startswith('aos-agent: NotAnAgent:'), err)
                self.assertIn(text, err)

    def test_default_target_is_cwd(self):
        old = os.getcwd()
        os.chdir(self.agent)
        self.addCleanup(os.chdir, old)
        out, _ = self.agent_check(env={'AOS_KERNEL_HOME': str(self.home)}, target=False)
        self.assertIn('ok   agent/llm.model:', out)

    def test_probe_ok_and_bad(self):
        server = Server({'data': [{'id': 'm'}]})
        self.addCleanup(server.close)
        self.llm(server.url)
        out, _ = self.agent_check('--probe', env={'AOS_KERNEL_HOME': str(self.home)})
        self.assertIn('ok   probe/small: endpoint 通，模型清單裡有 m', out)
        self.assertEqual(out.splitlines()[-1], '設定檢查通過；模型連線也測過')
        self.llm('http://127.0.0.1:%d/v1' % free_port())
        out, _ = self.agent_check('--probe', code=1, env={'AOS_KERNEL_HOME': str(self.home)})
        self.assertIn('bad  probe/small: 連不上', out)
        self.assertEqual(out.splitlines()[-1], '有 bad，照上面的提示修好再 aos-agent start')

    def test_tick_json_unreadable_matches_start(self):
        """astra 必修 1：tick.json 在但讀不到字串 K，跟 start 一樣算 KernelMismatch。"""
        tick = self.agent / 'tick.json'
        for content in ('{', '{}', '{"envs": {}}', '{"envs": {"AOS_KERNEL_HOME": null}}'):
            with self.subTest(content=content):
                tick.write_text(content)
                out, _ = self.agent_check(code=1, env={'AOS_KERNEL_HOME': str(self.home)})
                self.assertIn('讀不到合法的 K', out)
                self.assertIn('KernelMismatch', out)
                out, _ = self.agent_check(code=1)
                self.assertIn('bad  kernel: 找不到 K：沒設 AOS_KERNEL_HOME，%s 也讀不到合法的絕對路徑 K' % tick, out)
        tick.write_text(json.dumps({'envs': {'AOS_K': str(self.home)}}))  # fix-r4 前的舊鍵也認
        out, _ = self.agent_check()
        self.assertIn('（取自 tick.json）', out)

    def test_help_and_usage(self):
        result = subprocess.run([sys.executable, str(CLI / 'aos-agent'), '-h'], capture_output=True, text=True)
        self.assertIn('check', result.stdout)
        result = subprocess.run([sys.executable, str(CLI / 'aos-agent'), 'check', '-h'], capture_output=True, text=True)
        for flag in ('--target', '--probe'):
            self.assertIn(flag, result.stdout)
        for args in (('check', '--json'), ('check', '--agent', 'x'), ('status', '--probe')):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                aos_agent_cli.main(list(args))
            self.assertEqual(raised.exception.code, 2)

    def test_kernel_check_no_longer_checks_agents(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            aos_kernel_cli.main(['check', '--target', str(self.home), '--daemon-target', str(self.daemon)])
        self.assertNotIn('agent', out.getvalue())


TOP = {'_metainfo', 'health', 'kernel', 'pools', 'procs', 'queue', 'counts'}
KERNEL = {'home', 'chain', 'phase', 'last_seq', 'daemon', 'cpu', 'settings'}
POOL = {'pool', 'want', 'daemon', 'dpool', 'daemon_alive', 'summary', 'declared', 'removing', 'moving',
        'new_location', 'phase', 'sent', 'busy', 'idle', 'draining', 'pending', 'error', 'waiting', 'gone'}
PROC = {'name', 'once', 'pool', 'status', 'runs', 'fails', 'pending', 'target', 'mark', 'look'}


class LsJson(Homes):
    """ls 的 --json 第 2 版（池式納入）與對齊表；帳本、daemon 摘要都是手寫的，不開 daemon。"""
    LONG = 'aw-amy-think-1790000000000000000-77-3'

    def setUp(self):
        super().setUp()
        lock = (self.daemon / '.daemon.lock').open('w')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.put(self.daemon / 'state.json', {'pid': os.getpid()})
        ledger = kernel.new_state('17-1', kernel.CLI)
        ledger.update(last_seq=7)
        for pool, count in (('kernel', 1), ('default', 1), ('llm', 1)):
            entry = kernel.new_pool(str(self.daemon), pool)
            entry.update(want=count, sent={'count': count, 'skip': []}, dirty=False, redeclare=False, acquired=True)
            ledger['pools'][pool] = entry
            self.summary(pool, running=count)
        ledger['pools']['llm']['free'] = [0]
        ledger['busy']['default/0'] = {'req': 'k-17-1-7-0.json', 'proc': self.LONG}
        ledger['on'][self.LONG] = 'default/0'
        for name, once, status in (('agent-amy', False, 'queued'), (self.LONG, True, 'running'),
                                   ('broken', False, 'bad')):
            ledger['procs'][name] = {'target': str(self.agent / 'tick.json'), 'once': once, 'pool': 'default',
                                     'status': status, 'runs': 2, 'fails': 1 if status == 'bad' else 0,
                                     'not_before': 0, 'pending': {'name': 'x.json', 'id': 'x'} if once else None}
        self.put(self.home / 'state.json', ledger)

    def summary(self, pool, **counts):
        body = {'pool': pool, 'owner': str(self.home), 'count': 1, 'ver': 1, 'running': 0, 'restarting': 0,
                'pending': 0, 'dead': 0, 'failed': 0, 'killing': 0, 'draining': 0, 'updated': 0}
        body.update(counts)
        self.put(self.daemon / 'pools' / pool / 'summary.json', body)

    def ls(self, *flags, code=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(aos_kernel_cli.main(['ls', '--target', str(self.home), *flags]), code)
        return out.getvalue(), err.getvalue()

    def test_schema_keys_are_stable(self):
        out, err = self.ls('--json')
        self.assertEqual(err, '')
        data = json.loads(out)  # stdout 整份就是一個 JSON 物件
        self.assertEqual(out.count('\n'), 1)
        self.assertEqual(set(data), TOP)
        self.assertEqual(data['_metainfo'], {'_type': 'aos_kernel_ls', '_version': 2})
        self.assertEqual(set(data['health']), {'code', 'message'})
        self.assertEqual(set(data['kernel']), KERNEL)
        self.assertEqual(set(data['kernel']['daemon']), {'home', 'alive'})
        self.assertEqual(set(data['kernel']['cpu']), {'name', 'current', 'requests'})
        self.assertEqual(set(data['kernel']['settings']), {'tick_ms', 'interval_ms', 'timeout_ms', 'done_exit', 'bad_after'})
        self.assertEqual(set(data['counts']), {'pools', 'procs', 'queue'})
        self.assertEqual(set(data['counts']['pools']), {'total', 'want', 'sent', 'busy', 'idle', 'draining'})
        self.assertEqual(set(data['counts']['procs']), {'total', 'repeat', 'once', 'status'})
        self.assertEqual(list(data['pools']), ['kernel', 'default', 'llm'])
        for row in data['pools'].values():
            self.assertEqual(set(row), POOL)
        for proc in data['procs']:
            self.assertEqual(set(proc), PROC)
        data = json.loads(self.ls('--json', '--pool', 'default')[0])
        self.assertEqual(list(data['pools']), ['default'])
        self.assertEqual(set(data['pools']['default']), POOL | {'cpus'})
        self.assertEqual(set(data['pools']['default']['cpus'][0]), {'cpu', 'status', 'proc', 'daemon', 'declared'})

    def test_values(self):
        data = json.loads(self.ls('--json')[0])
        self.assertEqual(data['kernel']['home'], str(self.home))
        self.assertEqual((data['kernel']['phase'], data['kernel']['last_seq']), ('running', 7))
        self.assertEqual(data['kernel']['daemon'], {'home': str(self.daemon), 'alive': True})
        self.assertEqual(data['kernel']['cpu']['name'], 'kernel/0')
        default = data['pools']['default']
        self.assertEqual((default['want'], default['sent'], default['busy'], default['idle']), (1, 1, 1, 0))
        self.assertEqual(default['summary']['running'], 1)
        self.assertEqual(data['counts']['pools'], {'total': 2, 'want': 2, 'sent': 2, 'busy': 1, 'idle': 1, 'draining': 0})
        self.assertEqual(data['counts']['procs'], {'total': 3, 'repeat': 2, 'once': 1,
                                                   'status': {'queued': 1, 'running': 1, 'bad': 1}})
        self.assertEqual((data['queue'], data['counts']['queue']), (['agent-amy'], 1))
        procs = {p['name']: p for p in data['procs']}
        self.assertTrue(procs[self.LONG]['pending'])
        self.assertEqual(procs['broken']['look'], str(self.agent / 'tick.json'))
        self.assertIsNone(procs['agent-amy']['look'])
        cpus = json.loads(self.ls('--json', '--pool', 'default')[0])['pools']['default']['cpus']
        self.assertEqual([(c['cpu'], c['status'], c['proc']) for c in cpus], [('default/0', 'busy', self.LONG)])

    def test_health_matches_text_first_line_and_exit_codes(self):
        text, _ = self.ls()
        data = json.loads(self.ls('--json')[0])
        self.assertEqual(text.splitlines()[0], 'health ' + data['health']['message'])
        (self.home / 'state.json').write_text('{')
        for flags in ((), ('--json',)):
            out, err = self.ls(*flags, code=1)
            self.assertEqual(out, '')
            self.assertTrue(err.startswith('aos-kernel: '), err)

    def test_daemon_dead(self):
        (self.daemon / '.daemon.lock').unlink()
        data = json.loads(self.ls('--json')[0])
        self.assertEqual({row['daemon_alive'] for row in data['pools'].values()}, {False})
        self.assertFalse(data['kernel']['daemon']['alive'])
        self.assertEqual(data['health']['code'], 'daemon')
        self.assertIn('daemon 沒在跑', self.ls()[0].split('\n', 1)[1])

    def test_text_table_aligned_and_long_names_cut(self):
        text, _ = self.ls('--procs')
        self.assertNotIn(self.LONG, text)
        self.assertNotIn(str(self.home), text.split('\n', 1)[1])  # 長路徑不進主表
        rows = [line for line in text.splitlines() if line.startswith('  ') and ('反覆' in line or 'once' in line
                                                                               or '種類' in line)]
        self.assertEqual(len(rows), 4)
        cols = {aos_kernel_ls._width(row[:row.index('反覆' if '反覆' in row else 'once' if 'once' in row else '種類')])
                for row in rows}
        self.assertEqual(len(cols), 1, rows)  # 種類欄對齊（中文算兩格）
        self.assertIn('broken 壞了，看 %s' % (self.agent / 'tick.json'), text)
        self.assertIn('proc    3 個（反覆 2、once 1）：bad 1、queued 1、running 1', text)
        self.assertIn('pool    2 個工作池：要 2 顆、忙 1、閒 1', text)
        self.assertIn('  default  want 1  sent 1  busy 1  idle 0  draining 0   daemon default: running 1', text)
        self.assertIn('queue   1：agent-amy', text)

    def test_default_lists_only_procs_with_trouble(self):
        text, _ = self.ls()
        rows = [line.split()[0] for line in text.splitlines()
                if line.startswith('  ') and ('反覆' in line or 'once' in line) and '種類' not in line]
        self.assertEqual(rows, ['broken'])
        self.assertIn('  （其餘 2 個沒事的沒列；--procs 全列）', text)
        self.assertNotIn('其餘', self.ls('--procs')[0])

    def test_pool_filter_adds_cpu_rows(self):
        text, _ = self.ls('--pool', 'default')
        self.assertIn('    default/0  busy %s' % self.LONG, text)
        self.assertNotIn('  llm ', text)
        _, err = self.ls('--pool', 'nope', code=1)
        self.assertTrue(err.startswith('aos-kernel: NotFound: '), err)

    def test_verbose_shows_full_names_and_paths(self):
        text, _ = self.ls('-v', '--procs')
        self.assertIn(self.LONG, text)
        self.assertIn('  K       %s' % self.home, text)
        self.assertIn('  D       %s' % self.daemon, text)
        self.assertIn('  chain   17-1', text)
        self.assertIn('target %s' % (self.agent / 'tick.json'), text)

    def test_proc_fields_normalized(self):
        """astra 必修 2、3：缺鍵／null／錯型別照 cli-ls.md 的型別輸出，status 統計不會撞鍵。"""
        ledger = aos_home.read_json(self.home / 'state.json')
        ledger['procs'] = {'a': {}, 'b': {'status': None, 'runs': None, 'pool': 3},
                           'c': {'status': 'null', 'target': 'rel', 'fails': 'x'}}
        self.put(self.home / 'state.json', ledger)
        out, _ = self.ls('--json')
        data = json.loads(out)
        self.assertEqual(out.count('"null": '), 1)
        procs = {p['name']: p for p in data['procs']}
        self.assertEqual({k: procs['a'][k] for k in ('pool', 'status', 'runs', 'fails', 'target')},
                         {'pool': None, 'status': 'unknown', 'runs': 0, 'fails': 0, 'target': None})
        self.assertEqual((procs['b']['status'], procs['b']['runs'], procs['b']['pool']), ('unknown', 0, None))
        self.assertEqual(procs['c']['fails'], 0)
        self.assertEqual(data['counts']['procs']['status'], {'unknown': 2, 'null': 1})
        self.assertIn('null 1、unknown 2', self.ls()[0])

    def test_look_without_literal_stderr_is_target(self):
        """astra 必修 4。"""
        self.put(self.agent / 'tick.json', {'stderr': {'$env': 'ERR'}})
        data = json.loads(self.ls('--json')[0])
        self.assertEqual(next(p for p in data['procs'] if p['name'] == 'broken')['look'], str(self.agent / 'tick.json'))

    def test_broken_health_exits_one(self):
        """astra 必修 5：status() 讀完後帳本才消失，health 判 broken，也要退 1、stdout 空。"""
        real = aos_kernel_cli.status
        def vanish(home):
            snapshot = real(home)
            (self.home / 'state.json').unlink()
            return snapshot
        with patch('aos_kernel_cli.status', vanish):
            out, err = self.ls('--json', code=1)
        self.assertEqual(out, '')
        self.assertTrue(err.startswith('aos-kernel: ReadFailed: kernel 家讀不到'), err)

    def test_json_ignores_verbose(self):
        self.assertEqual(self.ls('--json')[0], self.ls('--json', '-v')[0])

    def test_cut_keeps_head_and_tail(self):
        cut = aos_kernel_ls._cut(self.LONG, 24)
        self.assertLessEqual(aos_kernel_ls._width(cut), 24)
        self.assertTrue(cut.startswith('aw-amy') and cut.endswith('-77-3') and '…' in cut, cut)
        self.assertEqual(aos_kernel_ls._cut('短名', 24), '短名')


if __name__ == '__main__':
    unittest.main()
