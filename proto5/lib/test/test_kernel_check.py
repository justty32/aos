"""啟動前檢查：只用假家與 flock，不需启动 daemon。"""
import contextlib
import fcntl
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aos_home
import aos_kernel as kernel
import aos_kernel_check as check


class KernelCheck(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home, self.daemon = self.root / 'K', self.root / 'D'
        self.daemon.mkdir()
        self.config = self.root / 'llm.json'
        self.put(self.config, {'_metainfo': {'_type': 'llm_config', '_version': 1},
                               'models': {'small': {'endpoint': 'http://localhost:1234/v1', 'model': 'test'}}})
        kernel.init(self.home, {'k': {'pool': 'kernel'}, '0': {}, 'llm': {
            'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': str(self.config)}}})
        self.info = aos_home.read_json(self.home / 'info.json')
        self.info['daemon'] = str(self.daemon)
        self.save()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in check.COMMANDS:
            self.executable(self.bin / name)
        env = patch.dict(os.environ, {'PATH': str(self.bin), 'AOS_DAEMON_HOME': str(self.daemon)})
        env.start()
        self.addCleanup(env.stop)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(path, value)

    def save(self):
        self.put(self.home / 'info.json', self.info)

    def executable(self, path):
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)

    def run_check(self, *args, code=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = kernel.main(['check', '--target', str(self.home), *map(str, args)])
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        self.assertEqual(err.getvalue(), '')
        return out.getvalue()

    def lock_daemon(self, pid=None):
        lock = (self.daemon / '.daemon.lock').open('w')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.put(self.daemon / 'state.json', {'pid': pid or os.getpid(), 'children': {}})

    def agent(self, **fields):
        agent = self.root / 'agent'
        self.put(agent / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                      'llm': {'model': 'small'}, **fields})
        return agent

    def test_valid_info_llm_and_daemon_warning(self):
        text = self.run_check()
        for expected in ('ok   info:', 'warn daemon:', '先開 daemon', 'ok   path:',
                         check.SHELL_NOTE, 'ok   pools:', 'ok   llm/llm: 模型代號：small'):
            self.assertIn(expected, text)

    def test_daemon_option_overrides_info(self):
        other = self.root / 'D2'
        other.mkdir()
        self.daemon = other
        self.lock_daemon(pid=2 ** 31 - 1)
        cli = Path(check.__file__).resolve().parents[1] / 'cli'
        with patch.dict(os.environ, {'PATH': str(cli)}):
            text = self.run_check('--daemon-target', other)
        self.assertIn('ok   daemon: daemon 活著：%s' % other, text)

    def test_bad_info_stops_checks(self):
        self.put(self.home / 'info.json', {})
        text = self.run_check(code=1)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn('bad  info: NotAHome:', text)
        self.assertIn('請修正', text)

    def test_path_missing_commands(self):
        with patch.dict(os.environ, {'PATH': str(self.root / 'missing')}):
            text = self.run_check(code=1)
        self.assertIn('bad  path:', text)
        self.assertIn('export PATH=%s:$PATH' % (Path(check.__file__).resolve().parents[1] / 'cli'), text)
        for command in check.COMMANDS:
            self.assertIn(command, text)

    def test_daemon_proc_environment_overrides_shell(self):
        self.lock_daemon()
        expected = dict(os.fsdecode(item).split('=', 1) for item in
                        Path('/proc/%d/environ' % os.getpid()).read_bytes().split(b'\0') if b'=' in item)
        env, note = check.daemon_environment(self.daemon, True)
        self.assertEqual(env, expected)
        self.assertEqual(note, '（daemon 的 PATH）')
        with patch.object(check.shutil, 'which', return_value='/bin/tool') as which:
            text = self.run_check()
        self.assertIn('ok   daemon:', text)
        self.assertIn('（daemon 的 PATH）', text)
        for call in which.call_args_list:
            self.assertEqual(call.kwargs['path'], expected.get('PATH', os.defpath))

    def test_unreadable_proc_falls_back(self):
        self.lock_daemon(999999999)
        text = self.run_check()
        self.assertIn('ok   daemon:', text)
        self.assertIn(check.SHELL_NOTE, text)

    def test_pools_missing_default_warn_and_llm_bad(self):
        del self.info['cpus']['0']
        self.save()
        self.assertIn('warn pools: default', self.run_check())
        del self.info['cpus']['llm']
        self.save()
        text = self.run_check(code=1)
        self.assertIn('bad  pools: llm', text)
        self.assertIn('"pool": "llm"', text)
        self.assertIn('AOS_LLM_CONFIG', text)

    def test_llm_missing_config_env(self):
        self.info['cpus']['llm'].pop('envs')
        self.save()
        self.assertIn('bad  llm/llm: 沒設 AOS_LLM_CONFIG', self.run_check(code=1))

    def test_llm_missing_invalid_and_relative_config(self):
        for value in (str(self.root / 'missing.json'), 'relative.json', ''):
            with self.subTest(value=value):
                self.info['cpus']['llm']['envs']['AOS_LLM_CONFIG'] = value
                self.save()
                self.assertIn('bad  llm/llm:', self.run_check(code=1))
        self.info['cpus']['llm']['envs']['AOS_LLM_CONFIG'] = str(self.config)
        self.save()
        for raw in ('{', '{}', '{"_metainfo":{"_type":"llm_config","_version":1},"models":{"bad":{}}}'):
            self.config.write_text(raw)
            self.assertIn('bad  llm/llm:', self.run_check(code=1))

    def test_llm_env_reference_and_unknown_directive(self):
        envs = self.info['cpus']['llm']['envs']
        envs['AOS_LLM_CONFIG'] = {'$env': 'MODEL_CONFIG'}
        self.save()
        with patch.dict(os.environ, {'MODEL_CONFIG': str(self.config)}):
            self.assertIn('ok   llm/llm:', self.run_check())
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn('bad  llm/llm:', self.run_check(code=1))
        envs['AOS_LLM_CONFIG'] = {'$ref': 'config.json'}
        self.save()
        self.assertIn('無法靜態判斷', self.run_check())

    def test_llm_reference_uses_daemon_environment(self):
        self.info['cpus']['llm']['envs']['AOS_LLM_CONFIG'] = {'$env': 'MODEL_CONFIG'}
        self.save()
        env = {'PATH': str(self.bin), 'MODEL_CONFIG': str(self.config)}
        with patch.object(check, 'daemon_environment', return_value=(env, '（daemon 的 PATH）')):
            self.assertIn('ok   llm/llm:', self.run_check())

    def test_effective_inst_envs_override_info_and_path(self):
        self.info['cpus']['llm']['envs']['AOS_LLM_CONFIG'] = '/does/not/exist'
        self.save()
        inst = self.home / 'cpus/llm/inst.json'
        self.put(inst, {'envs': {'AOS_LLM_CONFIG': str(self.config), 'PATH': str(self.bin)}})
        text = self.run_check()
        self.assertIn('inst.json 已建，改 info 不生效，要 aos-kernel halt --target %s 後改 ' % self.home, text)
        self.assertIn('ok   path/llm:', text)
        self.assertIn('ok   llm/llm:', text)
        self.put(inst, {'envs': {'AOS_LLM_CONFIG': str(self.config), 'PATH': '/missing'}})
        self.assertIn('bad  path/llm:', self.run_check(code=1))
        self.put(inst, {})
        self.assertIn('沒設 AOS_LLM_CONFIG', self.run_check(code=1))

    def test_info_cpu_literal_path_and_complex_envs(self):
        self.info['cpus']['0']['envs'] = {'PATH': '/missing'}
        self.save()
        self.assertIn('bad  path/0:', self.run_check(code=1))
        self.info['cpus']['0'].pop('envs')
        self.info['cpus']['llm']['envs'] = {'$ref': 'envs.json'}
        self.save()
        self.assertIn('warn llm/llm: envs 無法靜態判斷', self.run_check())

    def test_broken_inst_is_bad(self):
        self.put(self.home / 'cpus/llm/inst.json', [])
        self.assertIn('bad  llm/llm:', self.run_check(code=1))

    def test_agent_valid_pools_and_model(self):
        text = self.run_check('--agent', self.agent())
        for item in ('agent', 'agent/tick.pool', 'agent/llm.pool', 'agent/llm.model'):
            self.assertIn('ok   %s:' % item, text)

    def test_agent_invalid_info_reports_code(self):
        agent = self.agent()
        self.put(agent / 'info.json', {})
        text = self.run_check('--agent', agent, code=1)
        self.assertIn('bad  agent: MetainfoInvalid:', text)

    def test_agent_unknown_pools_and_model(self):
        agent = self.agent(tick={'pool': 'absent'}, llm={'pool': 'missing', 'model': 'unknown'})
        text = self.run_check('--agent', agent, code=1)
        for item in ('agent/tick.pool', 'agent/llm.pool', 'agent/llm.model'):
            self.assertIn('bad  %s:' % item, text)

    def test_agent_tool_relative_absolute_path_and_permissions(self):
        agent = self.agent(tools=['tools.json'])
        local = agent / 'tool'
        self.executable(local)
        def tool(name, cmd):
            return {'type': 'function', 'function': {'name': name}, '_meta': {'argv': [cmd]}}
        self.put(agent / 'tools.json', [tool('relative', './tool'), tool('absolute', str(local)),
                                       tool('path', 'aos-exec')])
        text = self.run_check('--agent', agent)
        for name in ('relative', 'absolute', 'path'):
            self.assertIn('ok   agent/tool/' + name, text)
        local.chmod(0o644)
        self.put(agent / 'tools.json', [tool('relative', './tool'), tool('missing', 'missing-executable')])
        text = self.run_check('--agent', agent, code=1)
        for name in ('relative', 'missing'):
            self.assertIn('bad  agent/tool/' + name, text)

    def test_agent_tool_directive_warns(self):
        agent = self.agent(tools=['tools.json'])
        self.put(agent / 'tools.json', [{'type': 'function', 'function': {'name': 'dynamic'},
                                       '_meta': {'argv': [{'$env': 'TOOL'}]}}])
        self.assertIn('warn agent/tool/dynamic:', self.run_check('--agent', agent))

    def test_required_dirs_present_without_cpu_homes(self):
        self.assertEqual(list((self.home / 'cpus').iterdir()), [])
        self.assertIn('ok   dirs: requests/、responses/、cpus/ 都在', self.run_check())

    def test_required_dirs_missing(self):
        for name in ('requests', 'responses', 'cpus'):
            (self.home / name).rmdir()
        text = self.run_check(code=1)
        expected = '、'.join(str(self.home / name) + '/' for name in ('requests', 'responses', 'cpus'))
        self.assertIn('bad  dirs: 缺 %s；手建的家請 mkdir -p 補上（aos-kernel init 會建）' % expected, text)
        self.assertEqual(text.count('dirs:'), 1)

    def test_required_dir_replaced_by_file(self):
        (self.home / 'requests').rmdir()
        (self.home / 'requests').write_text('不是資料夾')
        self.assertIn('bad  dirs: 缺 %s/requests/' % self.home, self.run_check(code=1))

    def cpu_ledger(self, phase='running', kcpu='k', children=None):
        self.put(self.home / 'state.json', {'phase': phase, 'kcpu': kcpu})
        self.put(self.daemon / 'state.json', {'pid': 999999999, 'children': children or {}})

    def owned_children(self):
        return {name: {'target': str(self.home / 'cpus' / name / 'inst.json')}
                for name in self.info['cpus']}

    def test_running_cpus_all_present(self):
        self.lock_daemon(999999999)
        self.cpu_ledger(children=self.owned_children())
        self.assertIn('ok   cpus: 帳本裡的 cpu 都在 daemon 孩子表', self.run_check())

    def test_restarted_daemon_missing_cpus_running_and_stopping(self):
        self.lock_daemon(999999999)
        for phase in ('running', 'stopping'):
            with self.subTest(phase=phase):
                self.cpu_ledger(phase)
                self.assertIn('bad  cpus: daemon 重開過／cpu 不在（k, 0, llm）：執行 aos-kernel boot --target %s --daemon-target %s' %
                              (self.home, self.daemon), self.run_check(code=1))

    def test_ledger_kernel_cpu_not_in_info_is_checked(self):
        self.lock_daemon(999999999)
        children = self.owned_children()
        self.cpu_ledger(kcpu='old', children=children)
        self.assertIn('cpu 不在（old）', self.run_check(code=1))
        children['old'] = {'target': str(self.home / 'cpus/old/inst.json')}
        self.cpu_ledger(kcpu='old', children=children)
        self.assertIn('ok   cpus:', self.run_check())

    def test_same_named_foreign_child_is_missing(self):
        self.lock_daemon(999999999)
        for target in (self.root / 'other/cpus/k/inst.json', self.home / 'cpus-other/k/inst.json',
                       self.home / 'cpus/../../other/inst.json'):
            with self.subTest(target=target):
                children = self.owned_children()
                children['k']['target'] = str(target)
                self.cpu_ledger(children=children)
                self.assertIn('cpu 不在（k）', self.run_check(code=1))

    def test_cpu_check_skipped_without_ledger_or_when_stopped(self):
        self.lock_daemon(999999999)
        self.assertNotIn('cpus:', self.run_check())
        self.cpu_ledger('stopped')
        self.assertNotIn('cpus:', self.run_check())

    def test_cpu_check_skipped_when_daemon_dead(self):
        self.cpu_ledger()
        text = self.run_check()
        self.assertIn('warn daemon:', text)
        self.assertNotIn('cpus:', text)

    def test_cpu_check_uses_daemon_override(self):
        self.cpu_ledger()
        other = self.root / 'D2'
        other.mkdir()
        self.daemon = other
        self.lock_daemon(999999999)
        self.cpu_ledger(children=self.owned_children())
        self.assertIn('ok   cpus:', self.run_check('--daemon-target', other))

    def test_daemon_target_three_sources_and_info_mismatch_warns(self):
        other = self.root / 'D2'
        other.mkdir()
        text = self.run_check('--daemon-target', other)
        self.assertIn('warn daemon: daemon 沒在跑；先開 daemon：aos-daemon boot --target %s' % other, text)
        self.assertIn('warn daemon: info.json 記的 daemon 是 %s' % self.daemon, text)
        with patch.dict(os.environ, {'AOS_DAEMON_HOME': str(other)}):
            self.assertIn('aos-daemon boot --target %s' % other, self.run_check())
        env = {k: v for k, v in os.environ.items() if k != 'AOS_DAEMON_HOME'}
        cwd = os.getcwd()
        try:
            os.chdir(other)
            with patch.dict(os.environ, env, clear=True):
                text = self.run_check()
        finally:
            os.chdir(cwd)
        self.assertIn('aos-daemon boot --target %s' % other, text)
        self.assertNotIn('~/.aos-daemon', text)
        text = self.run_check()
        self.assertNotIn('info.json 記的 daemon', text)
