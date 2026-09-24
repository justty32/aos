"""第 4 隊（記憶與紀錄）：context、events、usage、compact（含 KILL 崩潰窗口、tick 鎖、自動、申請）、history --archive。"""
import contextlib
import fcntl
import http.server
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_batch as batch_api
import aos_agent_compact as compact_api
import aos_agent_context as context_api
import aos_agent_events as events_api
import aos_agent_info as info_api
import aos_home
import aos_llm_call as llm
import test_agent_tick as fixture

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def call(cid, name='read', args='{"path": "a.txt"}'):
    return {'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': args}}


def rounds(n, *, tools=2, fat=400, tag=''):
    """n 輪：user → (assistant 叫工具 → tool 結果)×tools → assistant 答。"""
    h = []
    for r in range(n):
        h.append({'role': 'user', 'content': '%s第 %d 個問題' % (tag, r)})
        for j in range(tools):
            cid = 'c%d_%d' % (r, j)
            h.append({'role': 'assistant', 'content': '讓我查查', 'tool_calls': [call(cid, 'read' if j else 'bash')]})
            h.append({'role': 'tool', 'tool_call_id': cid, 'content': 'x' * fat})
        h.append({'role': 'assistant', 'content': '答案 %d' % r})
    return h


def tree(root, skip=()):
    """整棵資料夾的 (相對路徑, 內容, mtime_ns)——比對「沒改任何檔」；skip 的檔名不比。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if name in skip:
                continue
            out.append((str(p.relative_to(root)), p.read_bytes(), p.stat().st_mtime_ns))
        for name in sorted(dirnames):
            out.append((str((Path(dirpath) / name).relative_to(root)) + '/', b'', 0))
    return sorted(out)


class MemoryBase(fixture.AgentTickTests):
    """借 tick 測試的假 K 家；不跑它的測試。"""

    def run(self, result=None):
        if type(self) is MemoryBase:
            return result
        return super().run(result)

    def history(self, value=None):
        path = self.base / 'prompts/history.json'
        if value is not None:
            self.put(path, value)
        return self.read(path)

    def cli(self, *args, env=None):
        with patch.dict(os.environ, env if env is not None else self.env, clear=True), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            try:
                code = agent.main(list(args) + ['--target', str(self.base)])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def events(self, dedupe=True):
        rows = events_api.read(self.base / 'log/events.jsonl')
        return events_api.dedupe(rows) if dedupe else rows


# 這幾條測試只在子類別跑
for _name in [n for n in dir(fixture.AgentTickTests) if n.startswith('test_')]:
    setattr(MemoryBase, _name, None)


# ============================================================ context ======

class ContextTests(MemoryBase):
    def test_tokens_estimate(self):
        self.assertEqual(context_api.tokens(''), 0)
        self.assertEqual(context_api.tokens('abcd'), 1)
        self.assertEqual(context_api.tokens('abcde'), 2)
        self.assertEqual(context_api.tokens('中文字'), 3)
        self.assertEqual(context_api.tokens('ab中'), 2)

    def test_rounds_split(self):
        h = [{'role': 'assistant', 'content': '開場'}, {'role': 'user', 'content': 'a'}, {'role': 'user', 'content': 'b'},
             {'role': 'assistant', 'content': 'c'}, {'role': 'user', 'content': 'd'}]
        self.assertEqual(context_api.rounds(h), [(0, 1), (1, 4), (4, 5)])
        self.assertEqual(context_api.rounds(rounds(2)), [(0, 6), (6, 12)])

    def test_context_equals_talk(self):
        """驗收①：aos-agent context 印的跟 talk /context 一模一樣（同一個函式）。"""
        self.put(self.base / 'prompts/system.json', {'content': '你是助理 helper'})
        self.history(rounds(3))
        self.put(self.base / 'tools.json', [{'type': 'function', 'function': {'name': 'read', 'description': '讀'},
                                             '_meta': {'argv': ['cat']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools.json']))
        code, mine = self.cli('context', env={})
        self.assertEqual(code, 0)
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdin', io.StringIO('/context\n')), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            agent.main(['talk', '--target', str(self.base)])
        self.assertEqual(out.getvalue(), mine)
        self.assertIn('history 18 則，', mine)
        self.assertIn('3 輪（user 3／assistant 9／tool 6）', mine)
        m = context_api.measure(info_api.load(self.base, env={}))
        self.assertIn('約 %d token' % m['total']['tokens'], mine)
        self.assertEqual(m['total']['tokens'], m['system']['tokens'] + m['history']['tokens'] + m['tools']['tokens'])

    def test_context_json_and_by_round(self):
        h = rounds(2)
        h[4]['content'] = 'y' * 900  # 第 1 輪最胖的是 read
        self.history(h)
        code, out = self.cli('context', '--json', '--by-round', env={})
        value = json.loads(out)
        self.assertEqual(value['history']['count'], 12)
        self.assertEqual(len(value['rounds']), 2)
        self.assertEqual(value['rounds'][0]['fattest'], {'tool': 'read', 'chars': 900, 'index': 5})
        code, out = self.cli('context', '--by-round', env={})
        self.assertIn('最胖：read 900 字（第 5 則）', out)

    def test_context_is_read_only(self):
        self.history(rounds(2))
        before = tree(self.base)
        self.cli('context', env={})
        self.assertEqual(tree(self.base), before)


# ============================================================= events ======

class EventTests(MemoryBase):
    def test_think_cycle_records_start_end(self):
        """驗收②：一批 think 記起訖與成敗；收件記一筆。"""
        self.put(self.base / 'input.json', '你好')
        self.assertEqual(self.tick(), 0)                       # intake
        self.assertEqual(self.tick(), 0)                       # 建批送出
        name = self.state()['batch']['calls'][0]['name']
        inst = self.read(self.base / 'work' / (name + '.inst.json'))
        self.assertEqual(inst['envs'], {'AOS_LLM_BATCH': name.rsplit('-', 1)[0]})
        self.respond(name, dict(fixture.RESULT, ms=1234))
        self.output(name)
        self.assertEqual(self.tick(), 0)                       # 收回結清
        evs = self.events()
        self.assertEqual([e['ev'] for e in evs], ['intake', 'think_start', 'think_end'])
        self.assertEqual(evs[0]['files'], ['input.json'])
        self.assertEqual(evs[0]['messages'], 1)
        bid = name.rsplit('-', 1)[0]
        self.assertEqual(evs[1]['id'], bid)
        self.assertEqual({k: evs[2][k] for k in ('id', 'ok', 'ms', 'tool_calls')},
                         {'id': bid, 'ok': True, 'ms': 1234, 'tool_calls': 0})
        self.assertLessEqual(evs[1]['at'], evs[2]['at'])

    def test_think_failure_recorded(self):
        name = self.prepare('think')
        self.respond(name, dict(fixture.RESULT, code=1))
        self.assertEqual(self.tick(), 0)
        end = self.events()[-1]
        self.assertEqual((end['ev'], end['ok'], end['count']), ('think_end', False, True))
        self.assertIn('aos-llm call exit 1', end['reason'])

    def test_act_cycle_calls(self):
        self.prepare('act')
        self.put(self.base / 'state.json', {'state': 'act'})
        self.assertEqual(self.tick(), 0)
        name = self.state()['batch']['calls'][0]['name']
        self.respond(name, dict(fixture.RESULT, ms=7))
        (self.base / 'work' / (name + '.out')).write_text('ok')
        self.assertEqual(self.tick(), 0)
        start, end = self.events()
        self.assertEqual((start['ev'], start['tools']), ('act_start', ['sh']))
        self.assertEqual((end['ev'], end['ok'], end['calls']), ('act_end', True, [{'tool': 'sh', 'ok': True, 'ms': 7}]))

    def test_act_failed_and_missing_tool(self):
        self.put(self.base / 'prompts/history.json',
                 [{'role': 'assistant', 'content': None, 'tool_calls': [call('c1', 'sh'), call('c2', 'nope')]}])
        self.info['tools'] = ['tools.json']
        self.put(self.base / 'tools.json', [fixture.TOOL])
        self.put(self.base / 'info.json', self.info)
        self.put(self.base / 'state.json', {'state': 'act'})
        self.tick()
        name = self.state()['batch']['calls'][0]['name']
        self.respond(name, dict(fixture.RESULT, code=3, ms=5))
        self.tick()
        end = self.events()[-1]
        self.assertEqual(end['calls'], [{'tool': 'sh', 'ok': False, 'ms': 5}, {'tool': 'nope', 'ok': False, 'ms': None}])
        self.assertFalse(end['ok'])

    def test_crash_after_event_before_commit_dedupes(self):
        """至少一次：事件寫了、state 還沒提交就崩 → 重做再寫一次，dedupe 後只剩一筆。"""
        self.put(self.base / 'state.json', {'state': 'think'})
        real = events_api.batch_start

        def boom(run):
            real(run)
            raise fixture.Crash('after event')
        with patch.object(batch_api.events, 'batch_start', boom), self.assertRaises(fixture.Crash):
            self.tick()
        self.assertEqual(self.tick(), 0)  # 重做：同一批再送（已放過的單不重放）
        raw = self.events(dedupe=False)
        self.assertEqual([e['ev'] for e in raw], ['think_start', 'think_start'])
        self.assertEqual(raw[0]['id'], raw[1]['id'])
        self.assertEqual(len(self.events()), 1)

    def test_crash_before_event_not_lost(self):
        self.put(self.base / 'state.json', {'state': 'think'})
        with self.crash_at('request.post'), self.assertRaises(fixture.Crash):
            self.tick()
        self.assertEqual(self.events(), [])
        self.assertEqual(self.tick(), 0)
        self.assertEqual([e['ev'] for e in self.events()], ['think_start'])

    def test_unwritable_log_does_not_break_tick(self):
        (self.base / 'log').write_text('不是資料夾')
        self.put(self.base / 'input.json', '你好')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')

    def test_events_cli(self):
        events_api.emit(self.base, 'intake', 'x1', files=['a.json'], messages=1)
        events_api.emit(self.base, 'intake', 'x1', files=['a.json'], messages=1)
        (self.base / 'log/events.jsonl').open('a').write('{壞行\n')
        events_api.emit(self.base, 'think_start', 'b1', base_len=1)
        code, out = self.cli('events', env={})
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)
        code, out = self.cli('events', '--last', '1', '--json', env={})
        self.assertEqual([e['ev'] for e in json.loads(out)], ['think_start'])
        code, out = self.cli('events', '--usage', env={})
        self.assertIn('還沒有用量紀錄', out)
        code, _ = self.cli('events', '--last', 'x', env={})
        self.assertEqual(code, 2)


class _Fake(http.server.BaseHTTPRequestHandler):
    body = None

    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        data = json.dumps(self.body).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class UsageTests(MemoryBase):
    def serve(self, body):
        handler = type('H', (_Fake,), {'body': body})
        server = http.server.HTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        cfg = self.root / 'llm.json'
        self.put(cfg, {'_metainfo': {'_type': 'llm_config', '_version': 1},
                       'models': {'small': {'endpoint': 'http://127.0.0.1:%d/v1' % server.server_port, 'model': 'real-m'}}})
        return {'AOS_LLM_CONFIG': str(cfg)}

    def test_usage_recorded_with_batch(self):
        """驗收②（假端點）：usage.jsonl 有 token 數與批 id。"""
        env = self.serve({'choices': [{'message': {'role': 'assistant', 'content': '嗨'}}],
                          'usage': {'prompt_tokens': 12, 'completion_tokens': 3, 'total_tokens': 15}})
        env['AOS_LLM_BATCH'] = 'aw-bob-1-2'
        msg = llm.call(self.base, env=env)
        self.assertEqual(msg['content'], '嗨')
        rows = events_api.read(self.base / 'log/usage.jsonl')
        self.assertEqual(len(rows), 1)
        self.assertEqual({k: rows[0][k] for k in ('batch', 'alias', 'model', 'usage')},
                         {'batch': 'aw-bob-1-2', 'alias': 'small', 'model': 'real-m',
                          'usage': {'prompt_tokens': 12, 'completion_tokens': 3, 'total_tokens': 15}})
        self.assertIsInstance(rows[0]['ms'], int)
        code, out = self.cli('events', '--usage', env={})
        self.assertIn('prompt 12  completion 3  total 15', out)

    def test_usage_missing_and_bad_message_still_logged(self):
        env = self.serve({'choices': [{'message': {'role': 'user', 'content': 'x'}}]})
        with self.assertRaises(Exception):
            llm.call(self.base, env=env)
        rows = events_api.read(self.base / 'log/usage.jsonl')
        self.assertEqual((rows[0]['batch'], rows[0]['usage']), (None, None))

    def test_usage_write_failure_ignored(self):
        env = self.serve({'choices': [{'message': {'role': 'assistant', 'content': '嗨'}}], 'usage': {'total_tokens': 1}})
        (self.base / 'log').write_text('不是資料夾')
        self.assertEqual(llm.call(self.base, env=env)['content'], '嗨')


# ============================================================ compact ======

KILL_SCRIPT = r'''
import os, signal, sys
sys.path.insert(0, sys.argv[1])
import aos_agent_compact as c
step = sys.argv[3]
def hook(actual):
    if actual == step:
        os.kill(os.getpid(), signal.SIGKILL)
c._hook = hook
if sys.argv[4] == 'cli':
    sys.exit(c.compact(sys.argv[2], keep_rounds=1, max_tokens=int(sys.argv[5])))
import aos_agent
sys.exit(aos_agent.tick(sys.argv[2], env={'AOS_KERNEL_HOME': sys.argv[5]}))
'''


class CompactTests(MemoryBase):
    def setUp(self):
        super().setUp()
        self.original = rounds(5)
        self.history(self.original)

    def compact(self, *args):
        return self.cli('compact', *args, env={})

    def assert_valid_memory(self):
        """驗收④：記憶照 agent §3.2 驗得過（aos_agent_info.load）、tool_calls 與結果成對、送得出去的 body 組得起來。"""
        info = info_api.load(self.base, env={})
        compact_api.check_pairs(info['history'])
        cfg = {'models': {'small': {'endpoint': 'http://x/v1', 'model': 'm', 'timeout_ms': 1}}}
        body, _ = llm.build_request(self.base, cfg, env={})
        return info['history'], body

    def test_dry_run_changes_nothing(self):
        """驗收③：--dry-run 不改任何檔（連鎖檔、archive、事件都不建）。"""
        before = tree(self.base)
        code, out = self.compact('--keep-rounds', '1', '--max-tokens', '200', '--dry-run')
        self.assertEqual(code, 0)
        self.assertIn('（dry-run，沒寫）', out)
        self.assertEqual(tree(self.base), before)
        self.assertFalse((self.base / '.tick.lock').exists())

    def test_compact_valid_archive_under_limit(self):
        """驗收④：驗得過、成對、archive 在且是原檔、縮完低於 --max-tokens。"""
        raw = (self.base / 'prompts/history.json').read_bytes()
        code, out = self.compact('--keep-rounds', '2', '--max-tokens', '800')
        self.assertEqual(code, 0, out)
        history, body = self.assert_valid_memory()
        self.assertLess(context_api.history_tokens(history), 800)
        archives = list((self.base / 'prompts/archive').glob('*.json'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), raw)
        self.assertEqual(history[-12:], self.original[-12:])                  # 最後 2 輪原樣
        self.assertEqual(history[:3], [self.original[0], history[1], self.original[5]])
        self.assertTrue(history[1]['content'].startswith('[aos 已壓縮這一輪中間的 4 則：叫了 bash×1、read×1；原文在 prompts/archive/'))
        ev = self.events()[-1]
        self.assertEqual((ev['ev'], ev['auto'], ev['before']['count'], ev['after']['count']),
                         ('compact', False, 30, len(history)))

    def test_seal_oldest_rounds(self):
        code, out = self.compact('--keep-rounds', '1', '--max-tokens', '300')
        history, _ = self.assert_valid_memory()
        self.assertTrue(history[0]['content'].startswith('[aos 已封存較早的 '))
        self.assertLessEqual(context_api.history_tokens(history), 300)
        self.assertEqual(history[-6:], self.original[-6:])
        self.assertIn('封存', out)

    def test_over_limit_warns(self):
        code, out = self.compact('--keep-rounds', '5', '--max-tokens', '100')
        self.assertEqual(code, 0)
        self.assertIn('nothing to compact', out)
        self.assertIn('還超過 --max-tokens 100', out)
        self.assertEqual(self.history(), self.original)

    def test_second_run_is_noop(self):
        self.compact('--keep-rounds', '1')
        once = self.history()
        code, out = self.compact('--keep-rounds', '1')
        self.assertIn('nothing to compact', out)
        self.assertEqual(self.history(), once)
        self.assertEqual(len(list((self.base / 'prompts/archive').glob('*.json'))), 1)

    def test_compress_keeps_round_without_final_reply(self):
        h = [{'role': 'user', 'content': 'q'}, {'role': 'assistant', 'content': None, 'tool_calls': [call('a')]},
             {'role': 'tool', 'tool_call_id': 'a', 'content': 'r'}, {'role': 'user', 'content': 'q2'},
             {'role': 'assistant', 'content': 'done'}]
        self.history(h)
        self.compact('--keep-rounds', '1')
        history, _ = self.assert_valid_memory()
        self.assertEqual([m['role'] for m in history], ['user', 'user', 'user', 'assistant'])

    def test_unfinished_task_rounds_kept(self):
        """驗收⑤：信頭寫著還沒 done 的單號，那幾輪原樣留；done 的照縮。"""
        team = self.root / 'team'
        home = team / 'members' / 'w1'
        home.mkdir(parents=True)
        (team / 'team.json').write_text('{}')
        for tid, status in (('t-0001', 'working'), ('t-0002', 'done')):
            self.put(team / 'team' / 'tasks' / (tid + '.json'), {'id': tid, 'status': status})
        h = rounds(4)
        h[0]['content'] = '【來信 lead → w1 · REQUEST · t-0002 rev1 · 09-25 10:03】做 A'
        h[6]['content'] = '【來信 lead → w1 · REQUEST · t-0001 rev1 · 09-25 10:04】做 B'
        h[12]['content'] = '【來信 lead → w1 · REQUEST · t-0009 rev1 · 09-25 10:05】沒有單的檔'
        self.put(home / 'info.json', self.info)
        self.put(home / 'prompts/history.json', h)
        self.base = home
        code, out = self.compact('--keep-rounds', '1')
        new, _ = self.assert_valid_memory()
        self.assertTrue(new[1]['content'].startswith('[aos 已壓縮'))  # t-0002 done：縮了
        windows = [new[i:i + 6] for i in range(len(new))]
        self.assertIn(h[6:12], windows)    # t-0001 沒完：原樣
        self.assertIn(h[12:18], windows)   # 讀不到的單：寧可留
        self.assertIn('沒做完的任務 2', out)
        # 上限壓得再低也不封存沒做完的那幾輪（寧可超過）
        self.put(home / 'prompts/history.json', h)
        code, out = self.compact('--keep-rounds', '1', '--max-tokens', '100')
        new, _ = self.assert_valid_memory()
        windows = [new[i:i + 6] for i in range(len(new))]
        self.assertIn(h[6:12], windows)
        self.assertIn(h[12:18], windows)
        self.assertTrue(new[0]['content'].startswith('[aos 已封存較早的 1 輪'))
        self.assertIn('還超過', out)

    def test_busy_lock_101_and_untouched(self):
        """驗收⑦：鎖被佔退 101、不動檔（dry-run 也一樣）。"""
        fd = os.open(self.base / '.tick.lock', os.O_RDWR | os.O_CREAT)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, b'4242\n')
        before = tree(self.base)
        for extra in ((), ('--dry-run',)):
            code, out = self.compact('--keep-rounds', '1', *extra)
            self.assertEqual(code, 101)
            self.assertIn('busy', self.err.getvalue())
            self.assertIn('4242', self.err.getvalue())
            self.assertEqual(tree(self.base), before)

    def test_refuses_when_not_idle(self):
        """驗收⑦：batch 不是 null（或 think／act、intake 做到一半）拒絕、不動檔。"""
        cases = [{'state': 'think'},
                 {'state': 'idle', 'batch': {'kind': 'think', 'kernel': str(self.k), 'base_len': 0, 'sent': True,
                                              'calls': [{'name': 'aw-bob-1-2-0', 'done': None, 'acked': False}]}},
                 {'state': 'idle', 'intake': {'id': '1-2', 'base_len': 30, 'files': []}}]
        for st in cases:
            with self.subTest(st=st):
                self.put(self.base / 'state.json', st)
                # 拿到鎖會把自己的 pid 寫進 .tick.lock（跟 tick 一樣），這個不算動檔
                before = tree(self.base, skip=('.tick.lock',))
                code, _ = self.compact('--keep-rounds', '1')
                self.assertEqual(code, 1)
                self.assertIn('NotIdle', self.err.getvalue())
                self.assertEqual(tree(self.base, skip=('.tick.lock',)), before)

    def test_invalid_history_refused(self):
        h = rounds(3)
        del h[-4]  # 最後一輪少一個工具結果
        self.history(h)
        code, _ = self.compact('--keep-rounds', '1')
        self.assertEqual(code, 1)
        self.assertIn('HistoryInvalid', self.err.getvalue())
        self.assertEqual(self.history(), h)

    def test_usage_errors(self):
        for args in (('--max-tokens', '5'), ('--keep-rounds', '-1'), ('--prune-archive', '3', '--dry-run')):
            with self.subTest(args=args):
                self.assertEqual(self.compact(*args)[0], 2)

    # ---- KILL 在窗口裡 --------------------------------------------------

    def kill_run(self, step, mode='cli', limit=100000):
        extra = str(self.k) if mode == 'tick' else str(limit)
        proc = subprocess.run([sys.executable, '-c', KILL_SCRIPT, LIB, str(self.base), step, mode, extra],
                              capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(proc.returncode, -signal.SIGKILL, proc.stderr)

    def clean_result(self, limit=100000):
        """同一份記憶在沒崩的副本上縮一次，拿來比。"""
        twin = self.root / 'twin'
        twin.mkdir()
        self.put(twin / 'info.json', self.read(self.base / 'info.json'))
        self.put(twin / 'prompts/history.json', self.original)
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(compact_api.compact(twin, keep_rounds=1, max_tokens=limit, env={}), 0)
        return self.read(twin / 'prompts/history.json')

    def test_kill_after_archive_before_history(self):
        """驗收⑥：寫完 archive、還沒換記憶就 KILL → 記憶還是完整舊版；重跑結果跟沒崩一樣。"""
        raw = (self.base / 'prompts/history.json').read_bytes()
        self.kill_run('compact.archive')
        self.assertEqual((self.base / 'prompts/history.json').read_bytes(), raw)   # 從不缺、沒半截
        self.assertEqual(len(list((self.base / 'prompts/archive').glob('*.json'))), 1)
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(compact_api.compact(self.base, keep_rounds=1, max_tokens=100000, env={}), 0)
        self.assertEqual(self.history(), self.clean_result())
        self.assertEqual(len(list((self.base / 'prompts/archive').glob('*.json'))), 1)
        self.assert_valid_memory()

    def test_kill_after_history_replaced(self):
        self.kill_run('compact.history', limit=300)
        after = self.history()
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(compact_api.compact(self.base, keep_rounds=1, max_tokens=300, env={}), 0)
        self.assertIn('nothing to compact', out.getvalue())
        self.assertEqual(self.history(), after)
        self.assertEqual(after, self.clean_result(300))

    def test_kill_inside_tick_auto_compact(self):
        """tick 自動壓縮崩在 archive 之後：下一格重做，結果跟沒崩一樣。"""
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 500, 'keep_rounds': 1}))
        raw = (self.base / 'prompts/history.json').read_bytes()
        self.kill_run('compact.archive', mode='tick')
        self.assertEqual((self.base / 'prompts/history.json').read_bytes(), raw)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.history(), self.clean_result(500))

    def test_many_kill_points_history_never_missing(self):
        """每個持久化點都 KILL 一次再重跑：記憶檔每次都在、驗得過，最後都一樣。"""
        want = self.clean_result(300)
        for step in ('compact.archive', 'compact.history'):
            with self.subTest(step=step):
                self.history(self.original)
                for p in (self.base / 'prompts/archive').glob('*'):
                    p.unlink()
                self.kill_run(step, limit=300)
                self.assertTrue((self.base / 'prompts/history.json').exists())
                info_api.load(self.base, env={})
                with patch('sys.stdout', new_callable=io.StringIO):
                    compact_api.compact(self.base, keep_rounds=1, max_tokens=300, env={})
                self.assertEqual(self.history(), want)


# ======================================================= 自動與申請 =========

class AutoCompactTests(MemoryBase):
    def setUp(self):
        super().setUp()
        self.original = rounds(5)
        self.history(self.original)
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 500, 'keep_rounds': 1}))

    def test_tick_auto_compacts_under_same_lock(self):
        """驗收⑦：tick（持著 .tick.lock）在 idle 直接叫壓縮，不另拿鎖、不死鎖；下一格沒事退 101。"""
        self.assertEqual(self.tick(), 0)
        history = self.history()
        self.assertLessEqual(context_api.history_tokens(history), 500)
        compact_api.check_pairs(history)
        ev = self.events()[-1]
        self.assertEqual((ev['ev'], ev['auto'], ev['reason']), ('compact', True, 'auto'))
        self.assertEqual(self.tick(), 101)

    def test_tick_auto_in_subprocess_no_deadlock(self):
        proc = subprocess.run([sys.executable, os.path.join(os.path.dirname(LIB), 'cli', 'aos-agent'), 'tick',
                               '--target', str(self.base)], capture_output=True, text=True, timeout=30,
                              env=dict(os.environ, AOS_KERNEL_HOME=str(self.k), PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertLess(len(self.history()), len(self.original))

    def test_auto_off_without_config(self):
        self.put(self.base / 'info.json', self.info)
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.history(), self.original)

    def test_auto_waits_for_pending_input(self):
        self.put(self.base / 'input.json', '新的一句')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')          # 先收輸入
        self.assertEqual(self.history()[:-1], self.original)

    def test_auto_skip_when_cannot_shrink(self):
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 100, 'keep_rounds': 5}))
        with patch.object(compact_api, 'plan', wraps=compact_api.plan) as spy:
            self.assertEqual(self.tick(), 101)
            self.assertEqual(self.tick(), 101)
        self.assertEqual(spy.call_count, 1)                       # 第二格看 log/compact-skip 就不重算
        self.assertEqual(self.history(), self.original)

    def test_auto_skips_invalid_history_once(self):
        h = rounds(3)
        del h[-4]
        self.history(h)
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 100, 'keep_rounds': 1}))
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.err.getvalue().count('自動壓縮沒做'), 1)
        self.assertEqual(self.events()[-1]['ev'], 'compact_fail')

    def test_bad_config_does_not_break_tick(self):
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 'x'}))
        self.put(self.base / 'input.json', '你好')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')

    def test_request_consumed_by_tick(self):
        self.put(self.base / 'info.json', self.info)             # 沒開自動：只看申請
        self.put(self.base / 'compact-req/r1.json', {'id': 'r1', 'from': 'w1', 'keep_rounds': 2})
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.history()[-12:], self.original[-12:])
        self.assertLess(len(self.history()), len(self.original))
        self.assertFalse((self.base / 'compact-req/r1.json').exists())
        self.assertEqual(len(list((self.base / 'compact-req/done').glob('r1.json.*.done'))), 1)
        self.assertIn('申請 r1（w1）', self.events()[-1]['reason'])
        self.assertEqual(self.tick(), 101)

    def test_request_crash_before_move_reruns_as_noop(self):
        self.put(self.base / 'info.json', self.info)
        self.put(self.base / 'compact-req/r1.json', {'id': 'r1', 'from': 'w1'})
        def crash(step):
            if step == 'compact.history':   # 記憶已換、申請還沒搬
                raise fixture.Crash(step)
        with patch.object(compact_api, '_hook', crash), self.assertRaises(fixture.Crash):
            self.tick()
        once = self.history()
        self.assertLess(len(once), len(self.original))
        self.assertTrue((self.base / 'compact-req/r1.json').exists())
        self.assertEqual(self.tick(), 0)                         # 重做：縮是空轉，申請搬走
        self.assertEqual(self.history(), once)
        self.assertFalse((self.base / 'compact-req/r1.json').exists())
        self.assertEqual([e['ev'] for e in self.events()].count('compact'), 1)
        self.assertEqual(self.tick(), 101)


class RequestHandlerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        from aos_team_format import Layout
        self.lay = Layout(temp.name)
        self.roster = {'members': {'w1': {'template': 'worker'}, 'w2': {'template': 'worker'}}}
        for name in ('w1', 'w2'):
            self.lay.member(name).mkdir(parents=True)

    def req(self, **kw):
        base = {'id': '1790000000000000000-1-w1', 'from': 'w1', 'kind': 'compact', 'at': '2026-09-25T10:00:00+08:00'}
        base.update(kw)
        return base

    def test_registered_and_drops_file(self):
        from aos_team_requests import handler
        fn = handler('compact')
        self.assertEqual(fn(self.lay, self.roster, self.req(keep_rounds=2, reason='太長')), [])
        path = self.lay.member('w1') / 'compact-req' / (self.req()['id'] + '.json')
        body = json.loads(path.read_text())
        self.assertEqual((body['keep_rounds'], body['reason'], body['from']), (2, '太長', 'w1'))
        path.write_text('{"id": "動過"}')
        fn(self.lay, self.roster, self.req(keep_rounds=2))           # 再叫一次：不覆蓋
        self.assertIn('動過', path.read_text())

    def test_not_redropped_after_done(self):
        from aos_agent_compact import on_request
        folder = self.lay.member('w1') / 'compact-req' / 'done'
        folder.mkdir(parents=True)
        (folder / (self.req()['id'] + '.json.1-2.done')).write_text('{}')
        on_request(self.lay, self.roster, self.req())
        self.assertFalse((folder.parent / (self.req()['id'] + '.json')).exists())

    def test_rules(self):
        from aos_agent_compact import on_request
        from aos_team_format import TeamError
        bad = [(self.req(member='w2'), 'NotAllowed'), (dict(self.req(member='zz'), **{'from': 'human'}), 'BadRecipient'),
               (self.req(keep_rounds=-1), 'FormatInvalid'), (self.req(max_tokens=5), 'FormatInvalid'),
               (self.req(extra=1), 'FormatInvalid'), (self.req(reason=3), 'FormatInvalid')]
        for req, code in bad:
            with self.subTest(req=req), self.assertRaises(TeamError) as cm:
                on_request(self.lay, self.roster, req)
            self.assertEqual(cm.exception.code, code)
        human = self.req(member='w2', id='1790000000000000000-1-human')
        human['from'] = 'human'
        on_request(self.lay, self.roster, human)
        self.assertTrue((self.lay.member('w2') / 'compact-req' / (human['id'] + '.json')).exists())


# ===================================================== history --archive ====

class ArchiveTests(MemoryBase):
    def setUp(self):
        super().setUp()
        self.original = rounds(4)
        self.history(self.original)
        with patch('sys.stdout', new_callable=io.StringIO):
            compact_api.compact(self.base, keep_rounds=1, env={})
        self.sha = next((self.base / 'prompts/archive').glob('*.json')).stem

    def test_list_show_grep(self):
        code, out = self.cli('history', '--archive', env={})
        self.assertEqual(code, 0)
        self.assertIn('%s  ' % self.sha, out)
        self.assertIn('24 則', out)
        code, out = self.cli('history', '--archive', self.sha[:6], env={})
        self.assertIn('第 24 則  assistant: 答案 3', out)
        code, out = self.cli('history', '--archive', '--grep', '答案 1', env={})
        self.assertEqual(out.strip(), '%s 第 12 則  assistant: 答案 1' % self.sha)
        code, out = self.cli('history', '--archive', '--grep', 'bash', '--json', env={})
        self.assertEqual(len(json.loads(out)), 4)

    def test_errors(self):
        self.assertEqual(self.cli('history', env={})[0], 2)
        code, _ = self.cli('history', '--archive', 'ffff', env={})
        self.assertEqual(code, 1)
        self.assertIn('NotFound', self.err.getvalue())

    def test_prune_keeps_referenced(self):
        old = self.root / 'bob/prompts/archive/0000000000000000.json'
        old.write_text('[]')
        os.utime(old, (1, 1))
        os.utime(self.base / 'prompts/archive' / (self.sha + '.json'), (1, 1))
        code, out = self.cli('compact', '--prune-archive', '1', env={})
        self.assertEqual(code, 0)
        self.assertFalse(old.exists())
        self.assertTrue((self.base / 'prompts/archive' / (self.sha + '.json')).exists())  # 記憶還指著它


class CliMiscTests(MemoryBase):
    def test_init_template_reserved(self):
        import aos_agent_init
        target = self.root / 'new'
        if hasattr(aos_agent_init, 'init_from_template'):
            self.skipTest('第 1 隊的 init_from_template 已合進來')
        with patch('sys.stdout', new_callable=io.StringIO):
            code = agent.main(['init', '--target', str(target), '--template', 'worker'])
        self.assertEqual(code, 1)
        self.assertIn('NotImplemented', self.err.getvalue())

    def test_notes_usage(self):
        self.assertEqual(self.cli('notes', 'show', env={})[0], 2)
        self.assertEqual(self.cli('notes', 'ls', 'x', env={})[0], 2)


if __name__ == '__main__':
    unittest.main()
