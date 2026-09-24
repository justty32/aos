"""09-24 listen 微調：--last [N]、不給看法＝用法錯、--show-calls／--show-calls-full（三種看法都有效）。"""
from datetime import datetime
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_listen as listen_api
import aos_agent_listen_render as render
import test_agent_tick as fixture

CLI = Path(__file__).resolve().parents[2] / 'cli' / 'aos-agent'


def call(cid, name, **args):
    return {'id': cid, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}


def said(text):
    return {'role': 'user', 'content': text}


def reply(text):
    return {'role': 'assistant', 'content': text}


def asked(*calls, content=None):
    return {'role': 'assistant', 'content': content, 'tool_calls': list(calls)}


def result(cid, content):
    return {'role': 'tool', 'tool_call_id': cid, 'content': content}


# 三輪：第 1 輪直接答；第 2 輪叫 date；第 3 輪叫 read（長參數、多行結果）。
HISTORY = [said('你好'), reply('嗨'),
           said('幾點'), asked(call('c1', 'date')), result('c1', '2026-09-24 14:03:12\n'), reply('現在 14:03'),
           said('讀檔'), asked(call('c2', 'read', path='hello.py', note='x' * 80), content='讓我看看'),
           result('c2', 'line1\nline2\nline3\n'), reply('讀完了')]


class ListenTweakTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def cli(self, *args, env=None):
        self.err.truncate(0)
        self.err.seek(0)
        with patch.dict(os.environ, env or {}, clear=True), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            try:
                code = agent.main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def listen(self, *flags, env=None):
        return self.cli('listen', '--target', str(self.base), *flags, env=env)

    def history(self, messages=HISTORY):
        self.put(self.base / 'prompts/history.json', messages)

    # 用法 ---------------------------------------------------------------------

    def test_no_mode_is_usage_error(self):
        self.history()
        code, output = self.listen()
        self.assertEqual((code, output), (2, ''))
        self.assertIn('listen 要選一種看法：--last [N]', self.err.getvalue())
        self.assertIn('--follow', self.err.getvalue())
        # 只給 --show-calls 也不算選了看法
        self.assertEqual(self.listen('--show-calls')[0], 2)

    def test_last_count_must_be_positive_integer(self):
        self.history()
        for value in ('abc', '0', '-1', '1.5', '+2', ' 3'):
            with self.subTest(value=value):
                self.assertEqual(self.listen('--last', value)[0], 2)
                self.assertIn('--last 後面要是正整數', self.err.getvalue())

    def test_modes_and_show_flags_exclusive(self):
        self.history()
        for flags in (('--last', '2', '--follow'), ('--last', '--wait', '3'),
                      ('--last', '--show-calls', '--show-calls-full')):
            with self.subTest(flags=flags):
                self.assertEqual(self.listen(*flags)[0], 2)

    # --last N ---------------------------------------------------------------

    def test_last_one_unchanged(self):
        self.history()
        self.assertEqual(self.listen('--last'), (0, '讀完了\n'))
        self.assertEqual(self.listen('--last', '1'), (0, '讀完了\n'))

    def test_last_n_rounds_in_order(self):
        self.history()
        code, output = self.listen('--last', '3')
        self.assertEqual(code, 0)
        # 「讓我看看」有字（中間句），算一則回話；只叫工具的 c1 那則不算
        self.assertEqual(output, '── 第 2 輪 ──\n現在 14:03\n── 第 3 輪 ──\n讓我看看\n讀完了\n')
        self.assertEqual(self.listen('--last', '2')[1], '── 第 3 輪 ──\n讓我看看\n讀完了\n')

    def test_last_n_more_than_exist(self):
        self.history()
        code, output = self.listen('--last', '10')
        self.assertEqual(code, 0)
        self.assertEqual(output.splitlines(),
                         ['── 第 1 輪 ──', '嗨', '── 第 2 輪 ──', '現在 14:03', '── 第 3 輪 ──', '讓我看看', '讀完了'])
        self.assertIn('aos-agent: note: 記憶裡只有 4 則回話，全印', self.err.getvalue())

    def test_last_n_mid_turn_tail_counts(self):
        self.history(HISTORY[:8])  # 第 3 輪只走到叫工具
        code, output = self.listen('--last', '2')
        self.assertEqual(output, '── 第 2 輪 ──\n現在 14:03\n── 第 3 輪 ──\n讓我看看\n')
        self.history(HISTORY[:4])  # 第 2 輪只有 tool_calls
        code, output = self.listen('--last', '2')
        self.assertEqual(output, '── 第 1 輪 ──\n嗨\n── 第 2 輪 ──\n(tool_calls: date)\n')

    def test_header_time_from_intake_archive(self):
        self.history()
        self.put(self.base / 'state.json', {'input': 'input'})
        done = self.base / 'input/done'
        stamp = 1790000000 * 10**9
        self.put(done / ('say-1-1.json.%d-7.done' % stamp), said('幾點'))
        self.put(done / ('say-2-1.json.%d-7.done' % (stamp + 60 * 10**9)), said('讀檔'))
        self.put(done / 'noise.done', said('你好'))  # 名字不合的不算
        _, output = self.listen('--last', '4')
        first = datetime.fromtimestamp(1790000000).strftime('%m-%d %H:%M:%S')
        second = datetime.fromtimestamp(1790000060).strftime('%m-%d %H:%M:%S')
        self.assertEqual(output.splitlines()[0], '── 第 1 輪 ──')
        self.assertIn('── 第 2 輪 · 收話 %s ──' % first, output)
        self.assertIn('── 第 3 輪 · 收話 %s ──' % second, output)

    def test_last_json_lines(self):
        self.history()
        _, output = self.listen('--last', '2', '--json')
        self.assertEqual([json.loads(l) for l in output.splitlines()], [HISTORY[7], HISTORY[9]])

    # --show-calls ------------------------------------------------------------

    def test_show_calls_short(self):
        self.history()
        code, output = self.listen('--last', '3', '--show-calls')
        self.assertEqual(code, 0)
        lines = output.splitlines()
        self.assertEqual(lines[:4], ['── 第 2 輪 ──', '[呼叫 date]', '[結果 date：2026-09-24 14:03:12]', '現在 14:03'])
        self.assertEqual(lines[4:6], ['── 第 3 輪 ──', '讓我看看'])
        self.assertTrue(lines[6].startswith('[呼叫 read path=hello.py note=' + 'x' * 40 + '…'), lines[6])
        self.assertNotIn('x' * 41, lines[6])
        self.assertEqual(lines[7:], ['[結果 read 3 行：line1]', '讀完了'])

    def test_show_calls_last_one_starts_after_previous_reply(self):
        self.history(HISTORY[:6])
        _, output = self.listen('--last', '--show-calls')
        self.assertEqual(output, '── 第 2 輪 ──\n[呼叫 date]\n[結果 date：2026-09-24 14:03:12]\n現在 14:03\n')

    def test_show_calls_odd_arguments_and_failures(self):
        self.history([said('跑'), asked({'id': 'c9', 'type': 'function',
                                          'function': {'name': 'sh', 'arguments': '{不是 JSON'}}),
                      result('c9', '工具 sh 失敗（exit 1）：boom'), result('zz', ''), reply('失敗了')])
        _, output = self.listen('--last', '--show-calls')
        self.assertIn('[呼叫 sh 參數不是 JSON：{不是 JSON]', output)
        self.assertIn('[結果 sh：工具 sh 失敗（exit 1）：boom]', output)
        self.assertIn('[結果 ?：（空）]', output)

    def test_show_calls_full_with_truncation(self):
        big = 'y' * (render.FULL_LIMIT + 500)
        self.history([said('大'), asked(call('c1', 'read', path='a.txt')), result('c1', big), reply('好')])
        code, output = self.listen('--last', '--show-calls-full')
        self.assertEqual(code, 0)
        lines = output.splitlines()
        self.assertEqual(lines[:5], ['── 第 1 輪 ──', '[呼叫 read id=c1]', '  {', '    "path": "a.txt"', '  }'])
        self.assertEqual(lines[5], '[結果 read id=c1 1 行 %d 字]' % len(big))
        self.assertEqual(lines[6], '  ' + 'y' * render.FULL_LIMIT)
        self.assertEqual(lines[7], '  …（截斷：共 %d 字，只印前 %d 字；全文在記憶檔）' % (len(big), render.FULL_LIMIT))
        self.assertEqual(lines[8:], ['好'])

    def test_show_calls_full_multiline_result_indented(self):
        self.history(HISTORY[:6])
        _, output = self.listen('--last', '--show-calls-full')
        self.assertIn('[結果 date id=c1 1 行 20 字]\n  2026-09-24 14:03:12\n', output)

    def test_show_calls_json_includes_tool_messages(self):
        self.history(HISTORY[:6])
        _, output = self.listen('--last', '--show-calls', '--json')
        self.assertEqual([json.loads(l) for l in output.splitlines()], HISTORY[3:6])

    # --wait／--follow 也吃 --show-calls -------------------------------------------

    def test_wait_show_calls_prints_round(self):
        self.put(self.base / 'tick.json', {'envs': self.env})
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'fails': 0}}, 'replies': []})
        self.history(HISTORY[:2])

        def advance(_):
            self.history(HISTORY[:6])
        with patch('aos_kernel_health.health', return_value=('ok', 'ok')), \
                patch.object(listen_api.time, 'sleep', side_effect=advance):
            code, output = self.listen('--wait', '5', '--show-calls', env=self.env)
        self.assertEqual((code, output),
                         (0, '── 第 2 輪 ──\n[呼叫 date]\n[結果 date：2026-09-24 14:03:12]\n現在 14:03\n'))

    def test_follow_show_calls_live(self):
        """真的開一支 --follow --show-calls：叫工具那一刻就印呼叫行，不等輪完。"""
        self.history(HISTORY[:2])
        proc = subprocess.Popen([sys.executable, str(CLI), 'listen', '--follow', '--show-calls',
                                 '--target', str(self.base)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        time.sleep(.5)
        self.history(HISTORY[:4])  # 只叫了工具，還沒結果
        first = proc.stdout.readline()
        self.assertEqual(first, '[呼叫 date]\n')
        self.history(HISTORY[:6])
        self.assertEqual(proc.stdout.readline(), '[結果 date：2026-09-24 14:03:12]\n')
        self.assertEqual(proc.stdout.readline(), '現在 14:03\n')
        proc.send_signal(signal.SIGINT)
        _, err = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0, err)

    def test_follow_plain_unchanged(self):
        """沒開 --show-calls 的 --follow 照舊：工具結果不印、只叫工具那則印 (tool_calls: …)。"""
        self.history(HISTORY[:2])
        proc = subprocess.Popen([sys.executable, str(CLI), 'listen', '--follow', '--target', str(self.base)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        time.sleep(.5)
        self.history(HISTORY[:6])
        time.sleep(.5)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=5)
        self.assertEqual((proc.returncode, out), (0, '(tool_calls: date)\n現在 14:03\n'), err)

    # 印法小件 -----------------------------------------------------------------

    def test_result_line_shapes(self):
        self.assertEqual(render.result_line('x', ''), '[結果 x：（空）]')
        self.assertEqual(render.result_line('x', '\n\n  hi  \nb'), '[結果 x 4 行：hi]')
        self.assertTrue(render.result_line('x', 'z' * 100).endswith('z' * render.SHORT_RESULT + '…]'))

    def test_call_line_caps_whole_args(self):
        line = render.call_line(call('c', 'w', **{'k%d' % i: 'v' * 30 for i in range(10)}))
        self.assertLessEqual(len(line), len('[呼叫 w ]') + render.SHORT_ARGS + 1)
        self.assertTrue(line.endswith('…]'))


if __name__ == '__main__':
    unittest.main()
