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
        kernel.init(self.home, {'k': {'pool': 'kernel'}, '0': {}, 'llm': {
            'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': str(self.root / 'llm.json')}}})
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
                     'ok   agent:', 'ok   agent/tick.pool:', 'ok   agent/llm.pool:', 'ok   agent/llm.model:'):
            self.assertIn(item, out)
        self.assertEqual(lines[-1], '設定檢查通過；未測模型連線（--probe 會測）')
        self.assertNotIn('probe/', out)

    def test_kernel_from_tick_json_and_recorded_daemon(self):
        self.put(self.agent / 'tick.json', {'argv': ['aos-agent', 'tick'], 'envs': {'AOS_KERNEL_HOME': str(self.home)}})
        info = aos_home.read_json(self.home / 'info.json')
        info['daemon'] = str(self.daemon)
        self.put(self.home / 'info.json', info)
        out, _ = self.agent_check()
        self.assertTrue(out.startswith('ok   kernel: K＝%s（取自 tick.json）\n' % self.home), out)
        # 沒設 AOS_DAEMON_HOME：用 K 的 info 記的 daemon（boot 寫的），不是目前資料夾
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
        self.assertIn('bad  agent/llm.pool: 池 gpu 不存在', out)
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


TOP = {'_metainfo', 'health', 'kernel', 'cpus', 'procs', 'queue', 'counts'}
KERNEL = {'home', 'chain', 'phase', 'last_seq', 'daemon', 'cpu', 'settings'}
CPU = {'name', 'pool', 'kernel', 'busy', 'proc', 'req', 'discard', 'child'}
PROC = {'name', 'once', 'pool', 'status', 'runs', 'fails', 'pending', 'target', 'mark', 'look'}


class LsJson(Homes):
    LONG = 'aw-amy-think-1790000000000000000-77-3'

    def setUp(self):
        super().setUp()
        info = aos_home.read_json(self.home / 'info.json')
        info['daemon'] = str(self.daemon)
        self.put(self.home / 'info.json', info)
        lock = (self.daemon / '.daemon.lock').open('w')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        children = {name: {'target': str(self.home / 'cpus' / name / 'inst.json'), 'state': 'running'}
                    for name in ('k', '0', 'llm')}
        self.put(self.daemon / 'state.json', {'pid': os.getpid(), 'children': children})
        ledger = kernel.new_state(kernel.load_info(self.home), '17-1', 'k', kernel.CLI)
        ledger.update(phase='running', last_seq=7, queue=['agent-amy'])
        ledger['cpus']['0'] = {'req': 'k-17-1-7-0.json', 'proc': self.LONG, 'discard': False}
        for name, once, status in (('agent-amy', False, 'queued'), (self.LONG, True, 'running'),
                                   ('broken', False, 'bad')):
            ledger['procs'][name] = {'target': str(self.agent / 'tick.json'), 'once': once, 'pool': 'default',
                                     'status': status, 'runs': 2, 'fails': 1 if status == 'bad' else 0,
                                     'not_before': 0, 'pending': {'name': 'x.json', 'id': 'x'} if once else None}
        self.put(self.home / 'state.json', ledger)

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
        self.assertEqual(data['_metainfo'], {'_type': 'aos_kernel_ls', '_version': 1})
        self.assertEqual(set(data['health']), {'code', 'message'})
        self.assertEqual(set(data['kernel']), KERNEL)
        self.assertEqual(set(data['kernel']['daemon']), {'home', 'alive'})
        self.assertEqual(set(data['kernel']['cpu']), {'name', 'current', 'requests'})
        self.assertEqual(set(data['kernel']['settings']), {'tick_ms', 'interval_ms', 'timeout_ms', 'done_exit', 'bad_after'})
        self.assertEqual(set(data['counts']), {'cpus', 'procs', 'queue'})
        self.assertEqual(set(data['counts']['cpus']), {'total', 'busy', 'idle'})
        self.assertEqual(set(data['counts']['procs']), {'total', 'repeat', 'once', 'status'})
        for cpu in data['cpus']:
            self.assertEqual(set(cpu), CPU)
        for proc in data['procs']:
            self.assertEqual(set(proc), PROC)

    def test_values(self):
        data = json.loads(self.ls('--json')[0])
        self.assertEqual(data['kernel']['home'], str(self.home))
        self.assertEqual((data['kernel']['phase'], data['kernel']['last_seq']), ('running', 7))
        self.assertEqual(data['kernel']['daemon'], {'home': str(self.daemon), 'alive': True})
        cpus = {c['name']: c for c in data['cpus']}
        self.assertEqual((cpus['0']['busy'], cpus['0']['proc'], cpus['0']['child']), (True, self.LONG, 'running'))
        self.assertTrue(cpus['k']['kernel'])
        self.assertEqual(data['counts']['cpus'], {'total': 2, 'busy': 1, 'idle': 1})
        self.assertEqual(data['counts']['procs'], {'total': 3, 'repeat': 2, 'once': 1,
                                                   'status': {'queued': 1, 'running': 1, 'bad': 1}})
        procs = {p['name']: p for p in data['procs']}
        self.assertTrue(procs[self.LONG]['pending'])
        self.assertEqual(procs['broken']['look'], str(self.agent / 'tick.json'))
        self.assertIsNone(procs['agent-amy']['look'])

    def test_health_matches_text_first_line_and_exit_codes(self):
        text, _ = self.ls()
        data = json.loads(self.ls('--json')[0])
        self.assertEqual(text.splitlines()[0], 'health ' + data['health']['message'])
        (self.home / 'state.json').write_text('{')
        for flags in ((), ('--json',)):
            out, err = self.ls(*flags, code=1)
            self.assertEqual(out, '')
            self.assertTrue(err.startswith('aos-kernel: '), err)

    def test_daemon_dead_child_is_null(self):
        (self.daemon / '.daemon.lock').unlink()
        data = json.loads(self.ls('--json')[0])
        self.assertEqual({c['child'] for c in data['cpus']}, {None})
        self.assertEqual(data['health']['code'], 'daemon')

    def test_text_table_aligned_and_long_names_cut(self):
        text, _ = self.ls()
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
        self.assertIn('cpu     3 顆：忙 1、閒 1、kernel 1', text)
        self.assertIn('queue   1：agent-amy', text)

    def test_verbose_shows_full_names_and_paths(self):
        text, _ = self.ls('-v')
        self.assertIn(self.LONG, text)
        self.assertIn('  K       %s' % self.home, text)
        self.assertIn('  D       %s' % self.daemon, text)
        self.assertIn('  chain   17-1', text)
        self.assertIn('target %s' % (self.agent / 'tick.json'), text)

    def test_cut_keeps_head_and_tail(self):
        cut = aos_kernel_ls._cut(self.LONG, 24)
        self.assertLessEqual(aos_kernel_ls._width(cut), 24)
        self.assertTrue(cut.startswith('aw-amy') and cut.endswith('-77-3') and '…' in cut, cut)
        self.assertEqual(aos_kernel_ls._cut('短名', 24), '短名')


if __name__ == '__main__':
    unittest.main()
