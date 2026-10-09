"""STATE 提示、compact 預設與壓縮後的回合去重。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / p) for p in
               ('lib', 'tests', 'modules/mail', 'modules/up', 'modules/up/examples')]
from base import DaemonCase, write_json
from brain_node import setup
import aos7_up_brain as brain
import aos7_up_memory as memory

HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
SUMMARY = '- （摘要 cX，3 則）舊事摘要內容（原文 ref://compact/cX）'


class StateTextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-br2-memory-')
        self.addCleanup(tmp.cleanup)
        self.node = Path(tmp.name)
        self.handoffs = self.node / 'wf/handoffs'
        self.handoffs.mkdir(parents=True)

    def state(self, day, text):
        path = self.handoffs / day / 'STATE.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_latest_pointer_and_fallback(self):
        self.assertEqual(memory.state_text(self.node), '')
        self.state('2026-10-08', '# 續行點\n' + SUMMARY + '\n- 最近一行\n  續行忽略\n')
        self.state('2026-10-09', '- 字典序最新\n')
        pointer = self.handoffs / 'NEXT-SESSION.md'
        pointer.write_text('> 最新：[2026-10-08/STATE.md](2026-10-08/STATE.md)\n')
        self.assertEqual(memory.state_text(self.node),
                         '續行點（wf/handoffs/2026-10-08/STATE.md，最近的在下面）：\n' +
                         SUMMARY + '\n- 最近一行\n\n')
        pointer.write_text('> 最新：[missing/STATE.md](missing/STATE.md)\n')
        self.assertIn('字典序最新', memory.state_text(self.node))
        pointer.unlink()
        self.assertIn('字典序最新', memory.state_text(self.node))
        self.state('2026-10-09', '# 沒有記錄\n')
        self.assertEqual(memory.state_text(self.node), '')

    def test_long_state_keeps_summary_and_recent(self):
        rows = [SUMMARY] + [f'- 舊事 {i} ' + '字' * 100 for i in range(30)] + ['- 最後一行']
        self.state('2026-10-09', '\n'.join(rows))
        text = memory.state_text(self.node)
        header, content = text.split('\n', 1)
        self.assertIn(SUMMARY, content)
        self.assertIn('- 最後一行', content)
        self.assertRegex(content, r'- （中間 \d+ 行略，全文在 wf/handoffs/2026-10-09/STATE.md）')
        self.assertLessEqual(len(text), memory.STATE_MAX + len(header) + 3)
        kept = [row for row in content.splitlines() if row in rows]
        self.assertEqual(kept, [row for row in rows if row in kept])

    def test_summary_truncation(self):
        self.state('2026-10-09', '- （摘要 cX，3 則）' + '字' * 1500 + '\n- 最後一行\n')
        text = memory.state_text(self.node)
        summary = next(row for row in text.splitlines() if row.startswith('- （摘要 '))
        self.assertLessEqual(len(summary), 600)
        self.assertTrue(summary.endswith('…'))
        self.assertIn('- 最後一行', text)

    def test_fit_order(self):
        parts = dict(trail='t' * 100, skill='k' * 100, state='s' * 100, attach='a' * 500)
        for limit, empty in [(750, ['trail']), (650, ['trail', 'skill']),
                             (550, ['trail', 'skill', 'state'])]:
            with self.subTest(limit=limit):
                got, size = memory.fit(parts, 800, limit)
                for key in empty:
                    self.assertEqual(got[key], '')
                for key in parts.keys() - set(empty):
                    self.assertEqual(got[key], parts[key])
                self.assertLessEqual(size, limit)
        got, size = memory.fit(parts, 800, 400)
        self.assertEqual([got[k] for k in ('trail', 'skill', 'state')], ['', '', ''])
        self.assertLess(len(got['attach']), 500)
        self.assertLessEqual(size, 400)
        self.assertEqual(parts['trail'], 't' * 100)


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainStateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-br2-')
        self.addCleanup(tmp.cleanup)
        self.node = setup(Path(tmp.name) / 'bob')
        (self.node / 'brain').mkdir()

    def state(self):
        return '\n'.join(p.read_text() for p in (self.node / 'wf/handoffs').glob('*/STATE.md'))

    def compact_line(self):
        for path in (self.node / 'wf/handoffs').glob('*/STATE.md'):
            path.write_text('# 續行點\n' + SUMMARY + '\n')

    def ledger(self):
        return json.loads((self.node / 'brain/state.json').read_text())

    def test_compact_uses_default_state_threshold_and_disabled(self):
        brain.checked(brain.WF, 'state', self.node, '開頭', node=self.node)
        path = next((self.node / 'wf/handoffs').glob('*/STATE.md'))
        path.write_text('# 續行點\n' + '\n'.join(f'- 12:00 舊事 {i} ' + '內容' * 30 for i in range(30)) + '\n')
        self.assertGreater(path.stat().st_size, 2048)
        self.assertLess(path.stat().st_size, 16384)
        self.assertFalse((self.node / 'compact.json').exists())
        journal = self.node / 'notes/journal.jsonl'
        journal.parent.mkdir(exist_ok=True)
        journal.write_text('')
        self.assertLess((self.node / 'wf/SESSION-LOG.md').stat().st_size, 2048)
        before = path.read_bytes(), path.stat().st_mtime_ns
        with patch.object(brain, 'run', wraps=brain.run) as run:
            self.assertFalse(brain.compact_if_big(self.node, {'compact': False}))
            run.assert_not_called()
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertTrue(brain.compact_if_big(self.node, {}))
        self.assertIn('（摘要 ', path.read_text())
        self.assertLess(len(path.read_text().splitlines()), len(before[0].splitlines()))
        after = path.read_bytes(), path.stat().st_mtime_ns
        self.assertFalse(brain.compact_if_big(self.node, {}))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), after)

    def test_compact_failure_does_not_escape(self):
        for code, output in [(1, '{"files":[{"job":"bad"}]}'), (0, 'not json'), (0, '')]:
            with self.subTest(code=code, output=output), patch.object(
                    brain, 'run', return_value=subprocess.CompletedProcess([], code, output, '')):
                self.assertFalse(brain.compact_if_big(self.node, {}))
        with patch.object(brain, 'run', side_effect=subprocess.TimeoutExpired('compact', 1)):
            self.assertFalse(brain.compact_if_big(self.node, {}))

    def test_step_replay_after_state_compacted(self):
        letter = dict(id='step-letter', title='兩回合')
        text = '繼續：成果\n停在哪：下一步'
        def crash(point):
            if point == 'up-brain-after-step':
                raise RuntimeError('模擬被殺')
        with patch.object(brain, 'test_point', side_effect=crash):
            with self.assertRaises(RuntimeError):
                brain.step_on(self.node, letter, text, dict(progress_every=0, compact=False))
        self.assertEqual(brain.state_count(self.node, '第 1 步 step-letter：下一步'), 1)
        self.assertFalse((self.node / 'brain/task.json').exists())
        self.compact_line()
        brain.step_on(self.node, letter, text, dict(progress_every=0, compact=False))
        self.assertNotIn('第 1 步 step-letter：下一步', self.state())
        self.assertIn('step-letter#s1', self.ledger()['done'])
        self.assertEqual(json.loads((self.node / 'brain/task.json').read_text())['step'], 2)

    def test_finish_replay_after_state_compacted(self):
        pending = dict(id='end-letter', line='結案續行點', state_count=0)
        write_json(str(self.node / 'brain/pending.json'), pending)
        def crash(point):
            if point == 'up-brain-after-state':
                raise RuntimeError('模擬被殺')
        with patch.object(brain, 'test_point', side_effect=crash):
            with self.assertRaises(RuntimeError):
                brain.finish(self.node, pending, [])
        self.assertEqual(brain.state_count(self.node, pending['line']), 1)
        self.compact_line()
        brain.finish(self.node, pending, [])
        self.assertNotIn(pending['line'], self.state())
        self.assertFalse((self.node / 'brain/pending.json').exists())
        self.assertIn('end-letter#end', self.ledger()['done'])
        brain.drop_task(self.node, None)
        self.assertIn('end-letter#end', self.ledger()['done'])

    def test_doing_before_state_retries_once(self):
        with patch.object(brain, 'checked', side_effect=RuntimeError('STATE 未寫')):
            with self.assertRaises(RuntimeError):
                brain.state_once(self.node, 'doing#s1', '中斷續行點')
        self.assertEqual(self.ledger()['doing'], dict(key='doing#s1', count=0))
        brain.state_once(self.node, 'doing#s1', '中斷續行點', before=99)
        brain.state_once(self.node, 'doing#s1', '中斷續行點')
        self.assertEqual(brain.state_count(self.node, '中斷續行點'), 1)
        self.assertEqual(self.ledger(), dict(done=['doing#s1'], doing=None))

    def test_doing_after_state_does_not_repeat(self):
        real_write = brain.write_json
        def crash(path, value):
            if Path(path).name == 'state.json' and value['doing'] is None:
                raise RuntimeError('done 未寫')
            return real_write(path, value)
        with patch.object(brain, 'write_json', side_effect=crash):
            with self.assertRaises(RuntimeError):
                brain.state_once(self.node, 'doing#s1', '已寫續行點')
        self.assertEqual(self.ledger()['doing'], dict(key='doing#s1', count=0))
        self.assertEqual(brain.state_count(self.node, '已寫續行點'), 1)
        brain.state_once(self.node, 'doing#s1', '已寫續行點', before=99)
        self.assertEqual(brain.state_count(self.node, '已寫續行點'), 1)
        self.assertIsNone(self.ledger()['doing'])

    def test_bad_ledger_and_same_text_different_keys(self):
        for raw in ('broken', '[]', '{"done":[],"doing":42}'):
            with self.subTest(raw=raw):
                (self.node / 'brain/state.json').write_text(raw)
                before = brain.state_count(self.node, '同一句')
                brain.state_once(self.node, 'new#s1', '同一句')
                self.assertEqual(brain.state_count(self.node, '同一句'), before + 1)
        brain.state_once(self.node, 'other#s1', '同一句')
        self.assertEqual(self.ledger()['done'], ['new#s1', 'other#s1'])

    def test_done_keeps_last_fifty(self):
        write_json(str(self.node / 'brain/state.json'), dict(done=[str(i) for i in range(50)], doing=None))
        brain.state_once(self.node, 'last#end', '最新')
        self.assertEqual(self.ledger()['done'], [str(i) for i in range(1, 50)] + ['last#end'])


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainPromptTests(DaemonCase):
    def test_fake_round_prompt_has_compacted_state(self):
        node = setup(Path(self.mknode('bob')), interval_ms=200)
        self.set_tasks(str(node), [t for t in self.tasks(str(node)) if t['name'] != 'brain'])
        brain.checked(brain.WF, 'state', node, '最近那行', node=node)
        path = next((node / 'wf/handoffs').glob('*/STATE.md'))
        path.write_text('# 續行點\n' + SUMMARY + '\n- 12:00 最近那行\n')
        (node / 'notes').mkdir(exist_ok=True)
        (node / 'notes/journal.jsonl').write_text('{"text":"journal 獨特標記"}\n')
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        brain.mail(node, 'send', 'you', 'bob', 'REQUEST', '2 回合的工作')
        brain.once(node, 1)
        now = (node / 'brain/now.md').read_text()
        self.assertIn(SUMMARY, now)
        self.assertIn('最近那行', now)
        self.assertLess(now.index(SUMMARY), now.index('收到的信：'))
        self.assertNotIn('journal 獨特標記', now)
        self.assertEqual(json.loads((node / 'brain/task.json').read_text())['step'], 2)
