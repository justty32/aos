"""啟動前檢查（kernel-cli.md 的 check）：只用假家、flock 與手寫的 summary.json，不啟動 daemon。"""
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
        tmp = tempfile.TemporaryDirectory(prefix='aos-kcheck-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home, self.daemon = self.root / 'K', self.root / 'D'
        self.daemon.mkdir()
        self.config = self.root / 'llm.json'
        self.put(self.config, {'_metainfo': {'_type': 'llm_config', '_version': 1},
                               'models': {'small': {'endpoint': 'http://localhost:4000/v1', 'model': 'test'}}})
        kernel.init(self.home, {'daemon': str(self.daemon), 'pools': {
            'default': {'count': 1}, 'llm': {'count': 1, 'envs': {'AOS_LLM_CONFIG': str(self.config)}}}})
        self.info = aos_home.read_json(self.home / 'info.json')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in check.COMMANDS:
            self.executable(self.bin / name)
        env = patch.dict(os.environ, {'PATH': str(self.bin)})
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

    def lock_daemon(self, daemon=None, pid=None):
        daemon = daemon or self.daemon
        daemon.mkdir(exist_ok=True)
        lock = (daemon / '.daemon.lock').open('w')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.put(daemon / 'state.json', {'pid': pid or os.getpid()})

    def agent(self, **fields):
        agent = self.root / 'agent'
        self.put(agent / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                      'llm': {'model': 'small'}, **fields})
        return agent

    # ---- 帳本與 daemon 摘要 ----
    def ledger(self, phase='running', pools=None):
        pools = pools or {'kernel': 1, 'default': 1, 'llm': 1}
        entries = {}
        for name, sent in pools.items():
            entry = kernel.new_pool(str(self.daemon), name)
            entry['sent'] = {'count': sent, 'skip': []}
            entries[name] = entry
        self.put(self.home / 'state.json', {'chain': 'c', 'phase': phase, 'pools': entries, 'busy': {}, 'procs': {}})

    def summary(self, dpool, running, **extra):
        self.put(self.daemon / 'pools' / dpool / 'summary.json',
                 {'pool': dpool, 'count': running, 'running': running, 'pending': 0, 'dead': 0, 'failed': 0,
                  'killing': 0, 'draining': 0, **extra})

    # ---- info／daemon／path ----
    def test_valid_info_llm_and_daemon_warning(self):
        text = self.run_check()
        for expected in ('ok   info:', 'warn daemon: daemon 沒在跑：%s（池 default、llm、kernel）' % self.daemon, '先開 daemon',
                         'ok   path:', check.SHELL_NOTE, 'ok   pools: 池：default 1、llm 1、kernel 1',
                         'ok   llm/llm: 模型代號：small', '設定檢查通過；未測模型連線'):
            self.assertIn(expected, text)

    def test_bad_info_stops_checks(self):
        self.put(self.home / 'info.json', {})
        text = self.run_check(code=1)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn('bad  info: NotAHome:', text)

    def test_every_daemon_in_pool_table_is_checked(self):
        other = self.root / 'D2'
        self.info['pools']['gpu'] = {'count': 1, 'daemon': str(other)}
        self.save()
        self.lock_daemon(pid=999999999)
        text = self.run_check()
        self.assertIn('ok   daemon: daemon 活著：%s（池 default、llm、kernel）' % self.daemon, text)
        self.assertIn('warn daemon: daemon 沒在跑：%s（池 gpu）；先開 daemon：aos-daemon boot --target %s' % (other, other), text)

    def test_pool_without_daemon_is_bad(self):
        del self.info['daemon']
        self.save()
        text = self.run_check(code=1)
        self.assertIn('bad  daemon: 池 default 解不出 daemon 家（boot 會報 NoDaemon）', text)

    def test_daemon_target_adds_one_and_supplies_path(self):
        other = self.root / 'D2'
        self.lock_daemon(other, pid=2 ** 31 - 1)
        text = self.run_check('--daemon-target', other)
        self.assertIn('ok   daemon: daemon 活著：%s（--daemon-target，池表沒用到）' % other, text)
        self.assertIn(check.SHELL_NOTE, text)   # /proc 讀不到就退回 shell

    def test_path_missing_commands(self):
        with patch.dict(os.environ, {'PATH': str(self.root / 'missing')}):
            text = self.run_check(code=1)
        self.assertIn('bad  path:', text)
        self.assertIn('export PATH=%s:$PATH' % (Path(check.__file__).resolve().parents[1] / 'cli'), text)

    def test_kernel_daemon_proc_environment(self):
        self.lock_daemon()
        with patch.object(check.shutil, 'which', return_value='/bin/tool'):
            text = self.run_check()
        self.assertIn('（daemon 的 PATH）', text)

    # ---- dirs ----
    def test_required_dirs(self):
        self.assertIn('ok   dirs: requests/、responses/、pools/ 都在', self.run_check())
        for name in ('requests', 'responses', 'pools'):
            (self.home / name).rmdir()
        text = self.run_check(code=1)
        expected = '、'.join(str(self.home / name) + '/' for name in ('requests', 'responses', 'pools'))
        self.assertIn('bad  dirs: 缺 %s；手建的家請 mkdir -p 補上（aos-kernel init 會建）' % expected, text)

    # ---- pools／llm ----
    def test_pools_do_not_require_llm(self):
        del self.info['pools']['llm']
        del self.info['pools']['default']
        self.save()
        text = self.run_check()
        self.assertIn('ok   pools: 池：kernel 1', text)
        self.assertNotIn('llm/', text)

    def test_llm_every_pool_with_config(self):
        self.info['pools']['big'] = {'count': 0, 'envs': {'AOS_LLM_CONFIG': str(self.root / 'missing.json')}}
        self.save()
        text = self.run_check(code=1)
        self.assertIn('ok   llm/llm:', text)
        self.assertIn('bad  llm/big:', text)
        self.assertNotIn('llm/default', text)

    def test_llm_invalid_configs(self):
        for value in (str(self.root / 'missing.json'), 'relative.json', ''):
            with self.subTest(value=value):
                self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = value
                self.save()
                self.assertIn('bad  llm/llm:', self.run_check(code=1))
        self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = str(self.config)
        self.save()
        for raw in ('{', '{}', '{"_metainfo":{"_type":"llm_config","_version":1},"models":{"bad":{}}}'):
            self.config.write_text(raw)
            self.assertIn('bad  llm/llm:', self.run_check(code=1))

    def test_llm_env_reference_and_unknown_directive(self):
        envs = self.info['pools']['llm']['envs']
        envs['AOS_LLM_CONFIG'] = {'$env': 'MODEL_CONFIG'}
        self.save()
        with patch.dict(os.environ, {'MODEL_CONFIG': str(self.config)}):
            self.assertIn('ok   llm/llm:', self.run_check())
        with patch.dict(os.environ, {'PATH': str(self.bin)}, clear=True):
            self.assertIn('bad  llm/llm:', self.run_check(code=1))
        envs['AOS_LLM_CONFIG'] = {'$ref': 'config.json'}
        self.save()
        self.assertIn('無法靜態判斷', self.run_check())

    def test_pool_envs_json_overrides_info(self):
        self.info['pools']['llm']['envs']['AOS_LLM_CONFIG'] = '/does/not/exist'
        self.save()
        envs = self.home / 'pools/llm/envs.json'
        self.put(envs, {'AOS_LLM_CONFIG': str(self.config), 'PATH': str(self.bin)})
        text = self.run_check()
        self.assertIn('warn envs/llm: %s 跟 info 的 envs 不同' % envs, text)
        self.assertIn('ok   path/llm:', text)
        self.assertIn('ok   llm/llm:', text)
        self.put(envs, {'AOS_LLM_CONFIG': str(self.config), 'PATH': '/missing'})
        self.assertIn('bad  path/llm:', self.run_check(code=1))
        self.put(envs, [])
        self.assertIn('bad  envs/llm:', self.run_check(code=1))

    def test_whole_envs_directive_warns(self):
        self.info['pools']['llm']['envs'] = {'$ref': 'envs.json'}
        self.save()
        self.assertNotIn('llm/llm', self.run_check())   # 沒 --agent：看不出有沒有 AOS_LLM_CONFIG 就不查
        self.assertIn('warn llm/llm: envs 無法靜態判斷', self.run_check('--agent', self.agent(), code=1))

    # ---- --agent ----
    def test_agent_valid(self):
        text = self.run_check('--agent', self.agent())
        for item in ('agent', 'agent/tick.pool', 'agent/llm.pool', 'agent/tool_pool', 'agent/llm.model'):
            self.assertIn('ok   %s:' % item, text)

    def test_agent_uses_only_its_llm_pool(self):
        self.info['pools']['other'] = {'count': 1, 'envs': {'AOS_LLM_CONFIG': str(self.root / 'missing.json')}}
        self.save()
        text = self.run_check('--agent', self.agent())
        self.assertIn('ok   llm/llm:', text)
        self.assertNotIn('llm/other', text)
        agent = self.agent(llm={'pool': 'default', 'model': 'small'})
        text = self.run_check('--agent', agent, code=1)
        self.assertIn('bad  llm/default: 沒設 AOS_LLM_CONFIG', text)
        self.assertIn('bad  agent/llm.model:', text)

    def test_agent_unknown_kernel_and_empty_pools(self):
        self.info['pools']['empty'] = {'count': 0}
        self.save()
        agent = self.agent(tick={'pool': 'kernel'}, llm={'pool': 'missing', 'model': 'unknown'}, tool_pool='empty')
        text = self.run_check('--agent', agent, code=1)
        self.assertIn('bad  agent/tick.pool: 池 kernel 是 kernel 池', text)
        self.assertIn('bad  agent/llm.pool: 池 missing 不在 pools；請修改 agent info，或 aos-kernel cpu add --target %s --pool missing'
                      % self.home, text)
        self.assertIn('warn agent/tool_pool: 池 empty 的 count 是 0，工作會一直排隊', text)
        self.assertIn('bad  agent/llm.model:', text)

    def test_agent_invalid_info(self):
        agent = self.agent()
        self.put(agent / 'info.json', {})
        self.assertIn('bad  agent: MetainfoInvalid:', self.run_check('--agent', agent, code=1))

    def test_agent_tools(self):
        agent = self.agent(tools=['tools.json'])
        local = agent / 'tool'
        self.executable(local)

        def tool(name, cmd):
            return {'type': 'function', 'function': {'name': name}, '_meta': {'argv': [cmd]}}
        self.put(agent / 'tools.json', [tool('relative', './tool'), tool('path', 'aos-exec'),
                                       {'type': 'function', 'function': {'name': 'dyn'}, '_meta': {'argv': [{'$env': 'T'}]}}])
        text = self.run_check('--agent', agent)
        self.assertIn('ok   agent/tool/relative', text)
        self.assertIn('ok   agent/tool/path', text)
        self.assertIn('warn agent/tool/dyn:', text)
        local.chmod(0o644)
        self.assertIn('bad  agent/tool/relative', self.run_check('--agent', agent, code=1))

    # ---- cpus（各池摘要） ----
    def test_cpus_all_present(self):
        self.lock_daemon(pid=999999999)
        self.ledger()
        for pool in ('kernel', 'default', 'llm'):
            self.summary(pool, 1)
        self.assertIn('ok   cpus: 各池都在 daemon 那邊（kernel 1、default 1、llm 1）', self.run_check())

    def test_cpus_kernel_missing_error_gone_short(self):
        self.lock_daemon(pid=999999999)
        for phase in ('running', 'stopping'):
            with self.subTest(phase=phase):
                self.ledger(phase, {'kernel': 1, 'default': 2, 'llm': 1})
                state = aos_home.read_json(self.home / 'state.json')
                state['pools']['llm']['error'] = {'code': 'NameTaken', 'message': 'owner /x'}
                aos_home.write_json(self.home / 'state.json', state)
                self.summary('kernel', 0, pending=1)
                self.summary('default', 1, dead=1)
                text = self.run_check(code=1)
                self.assertIn('bad  cpus: kernel cpu 不在（daemon 重開過或還在拉）；池 llm：NameTaken（owner /x）：'
                              '執行 aos-kernel boot --target %s' % self.home, text)
                self.assertIn('warn cpus: 池 default 少 1 顆（daemon 在補；看 aos-daemon ls --target %s --pool default）'
                              % self.daemon, text)
        self.ledger()
        self.summary('kernel', 1)
        text = self.run_check(code=1)
        self.assertIn('bad  cpus: 池 llm：池不見了', text)

    def test_cpus_skipped_without_ledger_stopped_or_dead_daemon(self):
        self.assertNotIn('cpus:', self.run_check())
        self.ledger()
        self.assertNotIn('cpus:', self.run_check())       # daemon 沒活
        self.lock_daemon(pid=999999999)
        self.ledger('stopped')
        self.assertNotIn('cpus:', self.run_check())

    def test_probe_uses_llm_configs(self):
        with patch.object(check, 'probe_endpoint', return_value=('ok', '通')) as probe:
            text = self.run_check('--probe')
        probe.assert_called_once()
        self.assertIn('ok   probe/small: 通', text)
        self.assertIn('設定檢查通過；模型連線也測過', text)
