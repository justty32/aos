"""跨信記憶：存檔、找前件、要檔回合、提示上限與寄信前後的當機重接。"""
import hashlib
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
from base import DaemonCase, read_json, write_json
from brain_node import setup
from aos7_mail import letter
import aos7_up_brain as brain
import aos7_up_memory as memory

HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
LETTERS = TOP / 'modules/up/examples/longtask/letters'


def rows(node, name='INDEX.md'):
    path = node / 'notes/done' / name
    return [s for s in path.read_text().splitlines() if s.startswith('- ')] if path.exists() else []


def example(number):
    return (LETTERS / f'{number:02}.txt').read_text()


def weekly_title():
    return example(1).splitlines()[0].removeprefix('# ').replace('13 回合', '2 回合')


class MemoryUnitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-memory-')
        self.addCleanup(tmp.cleanup)
        self.node = Path(tmp.name)

    def record(self, ident, ask='測試標題', body='結論全文'):
        memory.record(self.node, ident, ask, 'DONE', body)

    def test_record_twelve(self):
        for k in range(12):
            self.record(f'letter-{k:02}')
        done = list((self.node / 'notes/done').glob('letter-*.md'))
        self.assertEqual(len(done), 12)
        self.assertEqual(len(rows(self.node)), 12)
        self.assertEqual(done[0].read_text(), '# 測試標題\n\n狀態：DONE\n\n結論全文\n')

    def test_rotation_and_old_id_replay(self):
        for k in range(51):
            self.record(f'letter-{k:02}')
        self.assertEqual(len(rows(self.node)), 50)
        self.assertEqual(rows(self.node)[0].split('｜')[0], '- letter-01')
        self.assertEqual(rows(self.node)[-1].split('｜')[0], '- letter-50')
        self.assertEqual(rows(self.node, 'INDEX-old.md'), ['- letter-00｜測試標題｜DONE 結論全文'])
        before = rows(self.node), rows(self.node, 'INDEX-old.md')
        self.record('letter-00', '不同標題', '不同內容')
        self.assertEqual((rows(self.node), rows(self.node, 'INDEX-old.md')), before)

    def test_record_idempotent_and_flat(self):
        ask = '  週報｜標題\n  第二行 ' + '字' * 40
        body = '\n\n #>*_`- 結論｜內容\n更多全文'
        self.record('same', ask, body)
        path = self.node / 'notes/done/same.md'
        old = path.read_bytes(), path.stat().st_mtime_ns
        self.record('same', '別的題目', '別的全文')
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), old)
        flat_ask = ' '.join(ask.split()).replace('｜', '|')[:30]
        self.assertEqual(rows(self.node), [f'- same｜{flat_ask}｜DONE 結論|內容'])

    def test_fid(self):
        self.assertEqual(memory.fid('a/b 中文:c'), 'a-b----c')
        ident = 'a' * 70 + '中文'
        self.assertEqual(memory.fid(ident), 'a' * 47 + '-' + hashlib.sha1(ident.encode()).hexdigest()[:16])
        self.assertEqual(len(memory.fid(ident)), 64)
        self.assertEqual(memory.fid('INDEX'), 'id-INDEX')
        self.record('INDEX', body='不能蓋掉目錄')
        self.assertTrue((self.node / 'notes/done/id-INDEX.md').exists())
        self.assertIsNone(memory.attach(self.node, 'INDEX'))

    def test_pick_examples(self):
        self.record('weekly-01', example(1).splitlines()[0].removeprefix('# '))
        self.assertEqual(memory.pick(self.node, example(11)), 'weekly-01')
        for k in [*range(2, 11), 12]:
            with self.subTest(letter=k):
                self.assertIsNone(memory.pick(self.node, example(k)))
        self.assertEqual(memory.pick(self.node, '請拿 weekly-01'), 'weekly-01')
        (self.node / 'notes/done/weekly-01.md').unlink()
        self.assertIsNone(memory.pick(self.node, example(11)))

    def test_pick_latest_tie_and_ignore_old(self):
        for ident in ('first', 'latest'):
            self.record(ident, '火星報告')
        self.assertEqual(memory.pick(self.node, '上次火星報告'), 'latest')
        self.assertIsNone(memory.pick(self.node, '火星報告'))
        for k in range(50):
            self.record(f'other-{k}', '別的事項')
        self.assertIsNone(memory.pick(self.node, '上次火星報告'))
        self.assertIsNone(memory.pick(self.node, 'latest'))

    def test_attach_limit_and_bad_reference(self):
        self.record('long', body='字' * 3500)
        text = (self.node / 'notes/done/long.md').read_text()
        got = memory.attach(self.node, 'long')
        self.assertEqual(got, text[:3000] + f'\n（後面還有 {len(text) - 3000} 字沒附上）')
        (self.node / 'notes/x.md').write_text('外面的檔案')
        for ref in ('../x', '/x', 'a/b', '', 'missing', 'a' * 65):
            with self.subTest(ref=ref):
                self.assertIsNone(memory.attach(self.node, ref))

    def test_index_text_keeps_newest_within_limit(self):
        self.assertEqual(memory.index_text(self.node), '')
        for k in range(50):
            self.record(f'id-{k:02}', '標題' * 20, '結論' * 30)
        text = memory.index_text(self.node)
        self.assertLessEqual(len(text), 2000)
        self.assertTrue(text)
        self.assertEqual(text.splitlines(), rows(self.node)[-len(text.splitlines()):])

    def test_want_protocol_and_sections(self):
        for text in ('\n  要檔案：<abc-01.md> 多餘的字', '要檔案：abc-01'):
            self.assertEqual(memory.want_of(text), 'abc-01')
        self.assertIsNone(memory.want_of('回信：要檔案：abc-01'))
        self.assertEqual(memory.want_step('abc-01'), '繼續：要看前件 abc-01 的全文\n停在哪：要檔案 abc-01')
        self.assertEqual(memory.wanted({'line': '要檔案 abc-01'}), 'abc-01')
        self.assertIsNone(memory.wanted({'line': '第 1 回合'}))
        self.assertEqual(memory.section(self.node, None, None), '')
        self.record('abc-01')
        section = memory.section(self.node, 'abc-01', memory.attach(self.node, 'abc-01'))
        self.assertIn(memory.index_text(self.node), section)
        self.assertIn('附上前件 abc-01 的全文：\n', section)
        self.assertIn('要的前件 missing 沒有這個檔', memory.section(self.node, 'missing', None))

    def test_fit_cut_order(self):
        parts = dict(trail='t' * 100, skill='s' * 200, attach='a' * 500)
        for limit, trail, skill in ((1000, parts['trail'], parts['skill']),
                                     (950, '', parts['skill']), (850, '', '')):
            with self.subTest(limit=limit):
                got, size = memory.fit(dict(parts), 1000, limit)
                self.assertEqual(got['trail'], trail)
                self.assertEqual(got['skill'], skill)
                self.assertEqual(got['attach'], parts['attach'])
                self.assertEqual(size, 1000 - sum(len(parts[k]) - len(got[k]) for k in parts))
                self.assertLessEqual(size, limit)
        got, size = memory.fit(dict(parts), 1000, 500)
        self.assertEqual(got['trail'], '')
        self.assertEqual(got['skill'], '')
        self.assertTrue(got['attach'].startswith('a'))
        self.assertIn('（太長，只附前 ', got['attach'])
        self.assertLessEqual(size, 500)
        self.assertEqual(size, 1000 - sum(len(parts[k]) - len(got[k]) for k in parts))


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class MemoryBrainTests(DaemonCase):
    def setUp(self):
        super().setUp()
        self.node = setup(Path(self.mknode('bob')), interval_ms=200)

    def send(self, title, body=None):
        args = [sys.executable, '-B', str(TOP / 'modules/mail/aos7-mail'),
                'send', 'you', 'bob', 'REQUEST', title]
        if body is not None:
            path = Path(self.root) / 'letter-body.txt'
            path.write_text(body)
            args.append(str(path))
        p = subprocess.run([*args, '--root', self.root], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout)['id']

    def replies(self, ident):
        return [l for p in (Path(self.root) / 'you/inbox').rglob('*.md')
                if (l := letter(p))['re'] == ident]

    def ended(self, ident):
        return (any(l['status'] != 'PROGRESS' for l in self.replies(ident))
                and not any((self.node / 'brain' / n).exists()
                            for n in ('task.json', 'last.md', 'pending.json')))

    def wait_end(self, ident):
        self.wait_for(lambda: self.ended(ident), timeout=45, msg='brain 沒結案')

    def state(self):
        return '\n'.join(p.read_text() for p in (self.node / 'wf/handoffs').glob('*/STATE.md'))

    def calls(self, ident, steps):
        sends = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        for step in range(1, steps + 1):
            cid = brain.call_id(ident, step)
            self.assertEqual(sends.get(cid), 1)
            self.assertTrue((self.node / 'llmcall/llm' / cid / 'receipt.json').exists())
        self.assertNotIn(brain.call_id(ident, steps + 1), sends)

    def assert_memory(self, ids):
        self.assertCountEqual([p.stem for p in (self.node / 'notes/done').glob('*.md')
                               if p.name not in ('INDEX.md', 'INDEX-old.md')],
                              [memory.fid(i) for i in ids])
        self.assertCountEqual([r.split('｜')[0][2:] for r in rows(self.node)],
                              [memory.fid(i) for i in ids])

    def assert_done(self, ident, ref=None):
        replies = self.replies(ident)
        self.assertEqual([l['status'] for l in replies], ['DONE'])
        if ref:
            self.assertIn(f'（附了前件 {memory.fid(ref)}）', replies[0]['body'])

    def test_weekly_then_reference(self):
        first = self.send(weekly_title(), example(1))
        self.start_daemon(register=['bob'])
        self.wait_end(first)
        second = self.send(example(11).splitlines()[0].removeprefix('# '), example(11))
        self.wait_end(second)
        self.assert_done(first)
        self.assert_done(second, first)
        self.assert_memory([first, second])
        self.assertTrue((self.node / 'notes/done' / (memory.fid(first) + '.md')).read_text()
                        .startswith('# ' + weekly_title() + '\n'))
        self.calls(first, 2)
        self.calls(second, 1)

    def test_want_file_two_rounds(self):
        first = self.send('先辦一般事項')
        self.start_daemon(register=['bob'])
        self.wait_end(first)
        second = self.send('要檔案，請看先前全文')
        self.wait_end(second)
        self.assert_done(second, first)
        self.assert_memory([first, second])
        self.calls(second, 2)
        state = self.state()
        self.assertEqual(sum(f'第 1 回合 {second}：' in r for r in state.splitlines()), 1)
        self.assertIn('要檔案 ' + memory.fid(first), state)

    def request_fixture(self, wanted=False):
        memory.record(self.node, 'previous', '火星報告', 'DONE', '前件全文獨特標記')
        work = self.node / 'brain'
        work.mkdir(exist_ok=True)
        path = Path(self.root) / 'request-letter.md'
        path.write_text('這封沒有指涉前件的字詞')
        current = dict(id='current', title='一般信', file=str(path))
        write_json(str(work / 'task.json'), dict(id='current', step=2,
                   line='要檔案 previous' if wanted else '第 1 回合', stall=0,
                   trail=['軌跡獨特標記' * 400], skill='chosen'))
        skill = self.node / 'skills/chosen'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('技能全文獨特標記' * 400)
        (work / 'last.md').write_text('上一回合成果' * 800)
        return current

    def test_request_wanted_attaches_without_keyword_match(self):
        current = self.request_fixture(wanted=True)
        brain.request(self.node, current, 'current-s2', {'model': 'x'})
        now = (self.node / 'brain/now.md').read_text()
        self.assertIn('附上前件 previous 的全文：', now)
        self.assertIn('前件全文獨特標記', now)
        self.assertEqual(read_json(str(self.node / 'brain/req.json'))['litellm']['model'], 'x')

    def test_request_pick_attaches_reference(self):
        current = self.request_fixture()
        (self.node / 'brain/task.json').unlink()
        Path(current['file']).write_text('請照你前面交的火星報告改寫')
        brain.request(self.node, current, 'current', {'model': 'x'})
        now = (self.node / 'brain/now.md').read_text()
        self.assertIn('附上前件 previous 的全文：', now)
        self.assertIn('前件全文獨特標記', now)

    def test_prompt_limit_keeps_index(self):
        current = self.request_fixture()
        # 模板本身可超過 1500 字；縮短非受測的工作簿，讓 1500 真有空間。
        for name in ('AGENTS.md', 'wf/SESSION-LOG.md', 'wf/handoffs/NEXT-SESSION.md'):
            (self.node / name).write_text('短工作簿\n')
        with patch.object(brain, 'checked', wraps=brain.checked) as render:
            brain.request(self.node, current, 'current-s2', dict(model='x', max_prompt_chars=1500))
        now = (self.node / 'brain/now.md').read_text()
        self.assertNotIn('軌跡獨特標記', now)
        self.assertNotIn('技能全文獨特標記', now)
        self.assertIn('做完的件（notes/done/INDEX.md', now)
        self.assertIn('- previous｜火星報告｜DONE', now)
        obj = read_json(str(self.node / 'brain/req.json'))
        self.assertLessEqual(sum(len(m['content']) for m in obj['litellm']['messages']), 1500)
        self.assertLessEqual(sum('render' in c.args for c in render.call_args_list), 3)
        self.assertGreaterEqual(len((self.node / 'brain/last.md').read_text()), 200)

    def test_prompt_still_too_long_is_trouble(self):
        current = self.request_fixture()
        Path(current['file']).write_text('很長的信' * 1000)
        with self.assertRaises(brain.Trouble) as got:
            brain.request(self.node, current, 'current-s2', dict(model='x', max_prompt_chars=1500))
        self.assertIn('max_prompt_chars', str(got.exception))

    def exercise_crashes(self, points):
        self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node)) if t['name'] != 'brain'])
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        ident = self.send('當機窗口測試')
        slot = self.node / 'direct-brain'
        slot.mkdir()
        def launch(rnd, crash=''):
            write_json(str(slot / 'tock.json'), dict(round=rnd, run=1))
            env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node),
                       AOS7_NODE_ID='bob', AOS7_TASK=str(slot), AOS7_TID='brain',
                       AOS7_RUN='1', AOS7_TEST_CRASH=crash)
            p = subprocess.Popen([sys.executable, '-B', str(TOP / 'modules/up/aos7_up_brain.py'),
                                  'brain', str(self.node)], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.procs.append(p)
            return p
        original = None
        for rnd, point in enumerate(points, 1):
            self.assertEqual(launch(rnd, point).wait(30), -9, point + ' 沒打中自殺點')
            self.assertTrue((self.node / 'brain/pending.json').exists())
            path = self.node / 'notes/done' / (memory.fid(ident) + '.md')
            saved = path.read_bytes(), path.stat().st_mtime_ns
            if original is None:
                original = saved
            self.assertEqual(saved, original, '重接不該重寫 done')
            if point == 'up-brain-after-done':
                self.assertEqual(rows(self.node), [])
                self.assertEqual(self.replies(ident), [])
            elif point == 'up-brain-after-index':
                self.assertEqual(len(rows(self.node)), 1)
                self.assertEqual(self.replies(ident), [])
            else:
                self.assert_done(ident)
        p = launch(len(points) + 1)
        self.wait_end(ident)
        p.terminate()
        p.wait(5)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), original)
        self.assert_memory([ident])
        self.assert_done(ident)
        self.assertEqual(self.state().count('回了 ' + ident), 1)
        self.calls(ident, 1)
        self.assertEqual(read_json(str(self.node / 'llmcall/fake-remote.json'))['sends'],
                         {brain.call_id(ident, 1): 1})

    def test_killed_after_done(self):
        self.exercise_crashes(['up-brain-after-done'])

    def test_killed_after_index(self):
        self.exercise_crashes(['up-brain-after-index'])

    def test_killed_after_mail(self):
        self.exercise_crashes(['up-brain-after-mail'])

    def test_three_consecutive_kills(self):
        self.exercise_crashes(['up-brain-after-done', 'up-brain-after-index', 'up-brain-after-mail'])
