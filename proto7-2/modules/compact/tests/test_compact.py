"""compact 的真 CLI、故障恢復與帳任務整合測試。"""
import contextlib
import io
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

TOP = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOP / 'tests'))
from base import CoreCase  # noqa: E402
import _proc  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

CLI = TOP / 'modules/compact/aos7-compact'
BUDGET = TOP / 'packs/budget/bin/aos7-budget'
EVENTS = TOP / 'modules/events/aos7-events'


def tree(node):
    return {str(p.relative_to(node)): p.read_bytes() for p in node.rglob('*') if p.is_file()}


def stable(text):
    # 每個測試的 UTC job 不同，摘要本文與保留原文仍須完全一致。
    return re.sub(r'c\d{14}-[0-9a-f]{8}', '<job>', text)


class TestCompact(CoreCase):
    """〔compact〕open 原文、整理界線與每個換檔故障點。"""

    def setUp(self):
        super().setUp()
        self.node = Path(self.root) / 'n'
        self.node.mkdir()

    def cli(self, *args, rc=0, env=None, binary=CLI, node=None):
        p = subprocess.run([sys.executable, str(binary), *map(str, args)], cwd=node or self.node,
                           capture_output=True, text=True, timeout=20,
                           env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        if rc >= 0:
            self.assertIsInstance(json.loads(p.stdout.strip().splitlines()[-1]), dict)
        return p

    def now(self, *args, **kw):
        node = kw.pop('node', self.node)
        return self.cli('now', node, *args, node=node, **kw)

    def config(self, node=None, **kw):
        node = node or self.node
        cfg = dict(files=['journal.jsonl'], max_bytes=1000000, keep_recent=10,
                   on_stage_change=True, summary_max_chars=1200, llm=None)
        cfg.update(kw)
        write_json(str(node / 'compact.json'), cfg)

    def fixture(self, node=None, suffix='jsonl'):
        node = node or self.node
        name = 'journal.' + suffix
        self.config(node, files=[name])
        old, opened, recent, rows = [], [], [], []
        for i in range(200):
            text = '%03d 已完成，保留檔名 file-%03d.txt 與數字 %d。' % (i, i, i) + '原始長文' * 45
            line = (json.dumps({'text': text}, ensure_ascii=False) + '\n' if suffix == 'jsonl'
                    else '- ' + text + '\n  續行原文\n')
            old.append(line)
            rows.append(line)
            if i % 10 == 0:
                line = (json.dumps({'open': True, 'text': '待辦 %d 逐字保留' % i}, ensure_ascii=False) + '\n'
                        if suffix == 'jsonl' else '- [ ] 待辦 %d 逐字保留\n  不可遺失的續行\n' % i)
                opened.append(line)
                rows.append(line)
        for i in range(10):
            line = (json.dumps({'recent': i}, ensure_ascii=False) + '\n' if suffix == 'jsonl'
                    else '* 最近 %d\n  最近續行\n' % i)
            recent.append(line)
            rows.append(line)
        if suffix == 'md':
            rows.insert(0, '# 記憶\n\n段落骨架\n| 表 | 格 |\n')
            rows.insert(101, '\n### 中段\n原地骨架\n\n')
        path = node / name
        path.write_text(''.join(rows), encoding='utf-8')
        return path, old, opened, recent

    def assert_compacted(self, path, old, opened, recent):
        text = path.read_text()
        for line in opened + recent:
            self.assertEqual(text.count(line), 1)
        self.assertEqual(sum(text.count(line) for line in opened), 20)
        self.assertLessEqual(path.stat().st_size, len(''.join(old + opened + recent).encode()) * .4)
        archives = list((path.parent / 'compact/archive').glob('*'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_text(), ''.join(old))
        if path.suffix == '.jsonl':
            summaries = [json.loads(line) for line in text.splitlines() if line.strip()]
            self.assertEqual(sum(r.get('compact') == 'summary' for r in summaries), 1)
            ref = next(r['ref'] for r in summaries if r.get('compact') == 'summary')
        else:
            ref = re.search(r'（原文 (ref://compact/[^）]+)）', text).group(1)
        archive = path.parent / 'compact/archive' / (ref.removeprefix('ref://compact/') + path.suffix)
        self.assertEqual(archive.read_bytes(), ''.join(old).encode())
        if path.suffix == '.md':
            self.assertEqual(text.count('（摘要 '), 1)
            for skeleton in ['# 記憶\n\n段落骨架\n| 表 | 格 |\n', '\n### 中段\n原地骨架\n\n']:
                self.assertIn(skeleton, text)

    def test_open_archive_recent_jsonl_and_md(self):
        for suffix in ['jsonl', 'md']:
            with self.subTest(suffix=suffix):
                node = self.node / suffix
                node.mkdir()
                path, old, opened, recent = self.fixture(node, suffix)
                original = path.read_bytes()
                self.now('--force', node=node)
                self.assert_compacted(path, old, opened, recent)
                if suffix == 'jsonl':
                    marker = path.read_bytes().splitlines(keepends=True)[0]
                    summary = json.loads(marker)
                    archive = node / 'compact/archive' / (summary['ref'].split('/')[-1] + path.suffix)
                    expanded = path.read_bytes().replace(marker, archive.read_bytes(), 1)
                    for protected in opened + recent:
                        original = original.replace(protected.encode(), b'', 1)
                        expanded = expanded.replace(protected.encode(), b'', 1)
                    self.assertEqual(expanded, original)

    def module(self):
        spec = importlib.util.spec_from_file_location('compact_review_test', CLI.with_name('aos7_compact.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_forget_crash_retry_only_once(self):
        for point in ['pending', 'summary', 'archive', 'replace']:
            for first, last in [(1, 2), (5, 6), (1, 6)]:
                with self.subTest(point=point, first=first, last=last):
                    node = self.node / ('%s-%s-%s' % (point, first, last))
                    node.mkdir()
                    self.config(node)
                    path = node / 'journal.jsonl'
                    rows = [json.dumps({'n': i}) + '\n' for i in range(6)]
                    path.write_text(''.join(rows))
                    args = ('forget', node, '--file', path.name, '--from', first, '--to', last)
                    self.cli(*args, rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-' + point})
                    self.cli(*args)
                    self.assertEqual(path.read_text(), ''.join(rows[:first - 1] + rows[last:]))
                    self.assertEqual(len(list((node / 'compact/archive').glob('*'))), 1)
                    self.assertEqual(len((node / 'compact/log.jsonl').read_text().splitlines()), 1)

    def test_forget_other_pending_requires_review(self):
        path, *_ = self.fixture()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        reply = self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 2, rc=1)
        self.assertIn('這次沒忘掉任何則', reply.stdout)
        self.assertIn('--dry-run', reply.stderr)
        self.assertIn('"compact": "summary"', path.read_text())

    def test_write_lock_waits_and_keeps_append(self):
        path, *_ = self.fixture()
        work = self.node / 'compact'
        work.mkdir()
        ready, release = work / 'ready', work / 'release'
        writer = subprocess.Popen([sys.executable, '-c', """
import fcntl, sys, time
from pathlib import Path
work, path = map(Path, sys.argv[1:])
with (work / 'write.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    (work / 'ready').touch()
    while not (work / 'release').exists(): time.sleep(.01)
    with path.open('a') as stream: stream.write('{"open":true,"added":1}\\n')
""", str(work), str(path)], start_new_session=True)
        _proc.track(self, writer, group=True)
        self.wait_for(ready.exists)
        process = subprocess.Popen([sys.executable, str(CLI), 'now', str(self.node), '--force'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, process, group=True)
        self.wait_for(lambda: read_json(str(work / 'pending.json'), {}).get('summary') or process.poll() is not None)
        self.assertIsNone(process.poll())
        self.assertFalse((work / 'archive').exists())
        release.touch()
        self.assertEqual(writer.wait(timeout=5), 0)
        out, err = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, out + err)
        self.assertTrue(path.read_text().endswith('{"open":true,"added":1}\n'))

    def test_unicode_open_physical_lines_and_stage(self):
        module = self.module()
        for suffix in ['jsonl', 'md']:
            for char in ['\u2028', '\u0085']:
                with self.subTest(suffix=suffix, char=char):
                    path = self.node / ('journal.' + suffix)
                    opened = (json.dumps({'open': True, 'text': 'first' + char + '- second'}, ensure_ascii=False)
                              if suffix == 'jsonl' else '- [ ] first' + char + '- second') + '\r\n'
                    old = ['{"n":0}\r\n', '{"n":1}\r\n'] if suffix == 'jsonl' else ['- zero\r\n', '- one\r\n']
                    path.write_bytes((opened + ''.join(old)).encode())
                    self.config(files=[path.name], keep_recent=0)
                    rec = [r for r in module.records(opened, path.suffix) if r['index'] is not None]
                    self.assertEqual(len(rec), 1)
                    self.assertTrue(rec[0]['open'])
                    self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 1, rc=2)
                    self.now('--force')
                    self.assertIn(opened.encode(), path.read_bytes())
        md = self.node / 'stage.md'
        md.write_text('## active\ntext\u2028- fake record\n## next\n')
        self.config(files=[md.name])
        self.assertEqual(module.stage_count(self.node, module.config(self.node)), 0)
        md.write_text('## active\n- one\u2028## 假標題\n- two\n')
        self.assertEqual(module.stage_count(self.node, module.config(self.node)), 2)

    def test_replace_crash_then_append_finishes_log_event(self):
        path, *_ = self.fixture()
        events = self.node / 'events'
        events.mkdir()
        cfg = read_json(str(self.node / 'compact.json'), {})
        cfg['events'] = True
        write_json(str(self.node / 'compact.json'), cfg)
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-replace'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        added = '{"open":true,"text":"新的一"}\n{"new":2}\n'
        with path.open('a') as stream:
            stream.write(added)
        self.now()
        log = [json.loads(s) for s in (self.node / 'compact/log.jsonl').read_text().splitlines()]
        self.assertEqual([e['job'] for e in log], [pending['job']])
        self.assertNotIn('abandoned', str(log))
        self.assertTrue(path.read_text().endswith(added))
        reply = self.cli('read', '--events', events, '--kind', 'compact.done', binary=EVENTS)
        self.assertEqual(len(json.loads(reply.stdout.splitlines()[-1])['records']), 1)

    def test_stage_due_survives_abandoned_pending(self):
        md = self.node / 'stage.md'
        md.write_text('## active\n- one\n- two\n- three\n')
        path = self.node / 'journal.jsonl'
        path.write_text(''.join(json.dumps({'n': n}) + '\n' for n in range(15)))
        self.config(files=[md.name, path.name])
        self.now()
        md.write_text('## active\n')
        self.now()
        md.write_text('## active\n- 設計宇宙航行導航介面\n- 觀測天體運行軌跡\n')
        self.now(rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        rewritten = path.read_text().replace('"n": 0', '"n": 99')
        path.write_text(rewritten)
        self.now()
        # 舊 pending 因改寫被放棄；同一次接著以 stage_due 重評這個檔並整理成功，due 才清。
        log = [json.loads(x) for x in (self.node / 'compact/log.jsonl').read_text().splitlines()]
        self.assertEqual([e.get('status') for e in log], ['abandoned', None])
        self.assertEqual(log[1]['trigger'], 'stage_change')
        self.assertIn('"n": 99', (self.node / 'compact/archive' / (log[1]['job'] + '.jsonl')).read_text())
        self.assertFalse(read_json(str(self.node / 'compact/state.json'))['stage_due'])

    def test_resumed_pending_does_not_consume_new_stage_trigger(self):
        """〔compact〕astra 二審 2：接完舊 force pending 後，同檔仍照新段落觸發重評。"""
        md = self.node / 'stage.md'
        md.write_text('## active\n- one\n- two\n- three\n')
        path = self.node / 'journal.jsonl'
        path.write_text(''.join(json.dumps({'n': n}) + '\n' for n in range(15)))
        self.config(files=[md.name, path.name])
        self.now()
        md.write_text('## active\n')
        self.now()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        with path.open('a') as f:
            f.write(''.join(json.dumps({'m': n}) + '\n' for n in range(3)))
        md.write_text('## active\n- 設計宇宙航行導航介面\n- 觀測天體運行軌跡\n')
        self.now()
        log = [json.loads(x) for x in (self.node / 'compact/log.jsonl').read_text().splitlines()]
        journal_jobs = [e for e in log if e['file'] == path.name]
        self.assertEqual([e['trigger'] for e in journal_jobs], ['force', 'stage_change'])
        self.assertFalse(read_json(str(self.node / 'compact/state.json'))['stage_due'])

    def test_active_section_never_summarized(self):
        """〔compact〕astra 二審 1：現役段是進行中的工作，force 也不摘；段落證據保持原文。"""
        md = self.node / 'SESSION-LOG.md'
        head = ''.join('- 舊 %d\n' % i for i in range(5))
        live = ''.join('- 現役 %d\n' % i for i in range(4))
        md.write_text(head + '## 最新進度\n' + live + '## 別段\n- 尾\n')
        self.config(files=[md.name], keep_recent=0)
        self.now()
        before = read_json(str(self.node / 'compact/state.json'))['stage_last']
        self.now('--force')
        text = md.read_text()
        self.assertIn('## 最新進度\n' + live + '## 別段\n', text)
        self.assertEqual(text.count('（摘要 '), 1)
        self.now()
        self.assertEqual(read_json(str(self.node / 'compact/state.json'))['stage_last'], before)

    def test_long_node_event_and_pub_failure_reason(self):
        node = self.node / ('n' * 96)
        node.mkdir()
        self.fixture(node)
        (node / 'events').mkdir()
        self.config(node, events=True)
        self.now('--force', node=node)
        log = json.loads((node / 'compact/log.jsonl').read_text())
        reply = self.cli('read', '--events', node / 'events', binary=EVENTS)
        self.assertEqual(json.loads(reply.stdout.splitlines()[-1])['records'][0]['event_id'], 'compact/' + log['job'])
        module = self.module()
        self.fixture()
        (self.node / 'events').mkdir()
        cfg = read_json(str(self.node / 'compact.json'), {})
        cfg['events'] = True
        write_json(str(self.node / 'compact.json'), cfg)
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-replace'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        failed = subprocess.CompletedProcess([], 2, 'progress\n{"why":"拒絕測試事件"}\n', 'stderr 診斷')
        with mock.patch.object(module.subprocess, 'run', return_value=failed):
            entry = module.resume(self.node, self.node / 'compact', pending)
        self.assertEqual(entry['event'], 'failed')
        self.assertFalse((self.node / 'compact/pending.json').exists())
        logs = [json.loads(line) for line in (self.node / 'compact/log.jsonl').read_text().splitlines()]
        self.assertEqual(logs[-1]['status'], 'event_failed')
        self.assertIn('拒絕測試事件', logs[-1]['why'])
        self.assertNotIn('event', logs[0])
        blocked = self.node / 'blocked'
        blocked.mkdir()
        self.fixture(blocked)
        self.config(blocked, events=True)
        (blocked / 'events').write_text('普通檔案')
        reply = self.now('--force', node=blocked)
        self.assertEqual(json.loads(reply.stdout.splitlines()[-1])['files'][0]['event'], 'failed')
        self.assertEqual(reply.stderr, '')
        self.assertFalse((blocked / 'compact/pending.json').exists())

    def test_sweep_dead_json_and_compact_tmp(self):
        path, *_ = self.fixture()
        work = self.node / 'compact'
        (work / 'archive').mkdir(parents=True)
        leftovers = [work / '.pending.json.tmp.2147483647', work / 'archive/.old.jsonl.tmp.2147483647',
                     path.with_name('.journal.jsonl.compact-tmp'), work / 'archive/.old.jsonl.compact-tmp']
        for tmp in leftovers:
            tmp.write_text('私人原文')
        self.now()
        self.assertFalse(any(tmp.exists() for tmp in leftovers))

    def test_litellm_presence_selects_transport_without_source_scan(self):
        module = self.module()
        path, *_ = self.fixture()
        self.config(llm={'gateway': 'litellm'})
        work = self.node / 'compact'
        work.mkdir()
        cfg = module.config(self.node)
        p = module.pending(work, path.name, path.read_text(), [0, 1], 'force', cfg)
        real_is_file = Path.is_file
        def present(path):
            return path.name == 'aos7_llmcall_litellm.py' or real_is_file(path)
        result = work / ('result-' + p['job'] + '.json')
        write_json(str(result), {'outcome': 'answered', 'text': '真傳輸摘要'})
        with mock.patch.object(Path, 'is_file', present), mock.patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(module.summarize(self.node, work, p), '真傳輸摘要')
        with mock.patch.object(Path, 'is_file', return_value=False), mock.patch.object(module.subprocess, 'run', side_effect=AssertionError('缺傳輸不得呼叫')):
            with self.assertRaises(module.Failure) as caught:
                module.summarize(self.node, work, p)
        self.assertEqual(caught.exception.code, 3)

    def test_human_lines_before_json_for_each_file(self):
        self.fixture()
        md = self.node / 'other.md'
        md.write_text('- one\n- two\n- three\n')
        self.config(files=['journal.jsonl', md.name], keep_recent=0)
        dry = self.now('--dry-run', '--force').stdout.splitlines()
        self.assertRegex(dry[0], r'journal.jsonl：230 則，open 20，會摘掉 210 則')
        self.assertIn('other.md：3 則', dry[1])
        done = self.now('--force').stdout.splitlines()
        self.assertRegex(done[0], r'journal.jsonl：230 則 → 21 則（摘掉 210、open 20 全留）')
        self.assertIn('bytes，原文在 compact/archive/', done[1])
        preview = self.cli('forget', self.node, '--file', md.name, '--from', 1, '--to', 1, '--dry-run')
        self.assertIn('other.md：會忘掉 1 則，open 0', preview.stdout.splitlines()[0])
        reply = self.cli('forget', self.node, '--file', md.name, '--from', 1, '--to', 1)
        self.assertIn('other.md：1 則 → 0 則（忘掉 1', reply.stdout.splitlines()[0])
        self.assertIn('不需要整理', self.now('--dry-run').stdout)

    def test_readme_first_run_demo(self):
        readme = CLI.with_name('README.md').read_text()
        section = readme.split('## 第一次跑')[1].split('## 想做更多')[0]
        shell = section.split(chr(96) * 3 + 'sh')[1].split(chr(96) * 3)[0]
        self.assertEqual(len([s for s in shell.splitlines() if s.startswith('python3 ')]), 3)
        reply = subprocess.run(['sh', '-c', shell], cwd=TOP.parent, capture_output=True, text=True, timeout=20)
        self.assertEqual(reply.returncode, 0, reply.stdout + reply.stderr)
        self.assertIn('已造好', reply.stdout)
        self.assertIn('220 則，open 20，會摘掉 200 則', reply.stdout)
        self.assertIn('220 則 → 21 則（摘掉 200、open 20 全留），125650 → 2437 bytes', reply.stdout)
        # 第一次跑不用 --force：計畫行與結果行印同一個原因（新手回改）。
        self.assertNotIn('--force', shell)
        self.assertEqual(reply.stdout.count('（原因：大小超過 2048）'), 2)
        self.assertLessEqual(len(readme.encode()), 4096)
        concepts = readme.split('## 先懂這四個詞')[1].split('## 第一次跑')[0]
        self.assertEqual(len(re.findall(r'^\d\. ', concepts, re.M)), 4)
        for word in ['退出碼', 'llmcall', 'pending', 'events']:
            self.assertNotIn(word, readme)
        advanced = CLI.with_name('ADVANCED.md').read_text()
        for word in ['退出碼', '../../notes/blueprint-errors.md', 'events']:
            self.assertIn(word, advanced)
        self.assertLessEqual(len(advanced.encode()), 12288)

    def brain_node(self, rounds=20):
        """仿 brain：journal 每回合一則（re／step／text＝停在哪｜成果），STATE 每回合一行。"""
        letter = 'you-20261009T185412-4f20668237ce'
        journal = self.node / 'notes/journal.jsonl'
        journal.parent.mkdir()
        state = self.node / 'wf/handoffs/2026-10-09/STATE.md'
        state.parent.mkdir(parents=True)
        rows, lines = [], ['# 續行點 2026-10-09\n', '\n', '## 進度\n']
        for k in range(1, rounds + 1):
            rows.append(json.dumps(dict(by='brain', re=letter, step=k, at='2026-10-09T18:%02d:00' % k,
                                        text=f'已寫第 {k} 節；下一回合寫第 {k + 1} 節｜' + '成果原文' * 40), ensure_ascii=False) + '\n')
            lines.append(f'- 18:{k:02d} 第 {k} 回合 {letter}：已寫第 {k} 節；下一回合寫第 {k + 1} 節\n')
        lines.insert(5, '- [ ] 等人補人數\n')
        journal.write_text(''.join(rows))
        state.write_text(''.join(lines))
        return letter, journal, state, rows, lines

    def test_default_includes_state_and_summary_says_what_was_done(self):
        """預設 files 含 wf/handoffs/*/STATE.md；摘要按信列出每回合做了什麼；open 與最近 5 則原文留下。"""
        letter, journal, state, rows, lines = self.brain_node()
        plan = self.now('--dry-run').stdout
        self.assertIn('wf/handoffs/2026-10-09/STATE.md：21 則，open 1，會摘掉 15 則（原因：大小超過 2048）', plan)
        self.assertIn('notes/journal.jsonl：20 則，open 0，會摘掉 15 則（原因：大小超過 2048）', plan)
        self.now()
        text = journal.read_text().splitlines()
        self.assertEqual(text[1:], [r.rstrip('\n') for r in rows[-5:]])
        summary = json.loads(text[0])['text']
        self.assertIn('you-…4f20668237ce 15 則（第 1～15 回合）：已寫第 1 節；下一回合寫第 2 節', summary)
        self.assertIn('已寫第 15 節', summary)
        self.assertNotIn('{"by"', summary)
        self.assertNotIn('成果原文', summary)
        after = state.read_text()
        self.assertTrue(after.startswith('# 續行點 2026-10-09\n\n## 進度\n'))
        self.assertIn('- [ ] 等人補人數\n', after)
        self.assertTrue(after.endswith(''.join(lines[-5:])))
        marker = next(s for s in after.splitlines() if s.startswith('- （摘要 '))
        self.assertIn('you-…4f20668237ce 15 則（第 1～15 回合）：已寫第 1 節', marker)
        self.assertLess(len(after.encode()), 0.6 * len(''.join(lines).encode()))
        # 再長一輪後重摘：舊摘要併進「更早」，不丟。
        with state.open('a') as f:
            f.writelines(f'- 19:{k:02d} 第 {k} 回合 {letter}：已寫第 {k} 節\n' for k in range(21, 40))
        self.now()
        again = state.read_text()
        self.assertIn('更早：', again)
        self.assertIn('- [ ] 等人補人數\n', again)

    def test_state_lock_waits_for_wfnode_writer(self):
        """整理 STATE.md 換檔時持 wf/handoffs/.state.lock（aos7-wfnode state 追加時拿的鎖）。"""
        _, _, state, _, _ = self.brain_node()
        lock = os.open(self.node / 'wf/handoffs/.state.lock', os.O_WRONLY | os.O_CREAT, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        p = subprocess.Popen([sys.executable, str(CLI), 'now', str(self.node)], cwd=self.node,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                p.wait(timeout=1.5)
            with state.open('a') as f:
                f.write('- 19:00 鎖內追加的一行\n')
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            os.close(lock)
        out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, out + err)
        self.assertTrue(state.read_text().endswith('- 19:00 鎖內追加的一行\n'))

    def test_summary_many_letters_and_odd_input(self):
        """12 封信擠不下時第一段與最近幾段照列、中間標「另 N 段略」；寄件人名帶 -／數字也認得；孤立 surrogate 不讓整理卡住。"""
        spec = importlib.util.spec_from_file_location('aos7_compact_t', CLI.with_name('aos7_compact.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = [dict(text=json.dumps(dict(re=f'team-{k}-20261009T1854{k:02d}-4f20668237{k:02d}', step=1,
                                          text=f'第 {k} 封做完｜' + '長' * 50), ensure_ascii=False) + '\n')
                for k in range(1, 13)]
        text = mod.local_summary(rows, 200)
        self.assertLessEqual(len(text), 200)
        self.assertIn('team-1-…4f2066823701', text)
        self.assertIn('第 12 封做完', text)
        self.assertRegex(text, r'…另 \d+ 段略…')
        self.assertEqual(mod.local_summary(rows, 1), '本')
        self.config(files=['journal.jsonl'], keep_recent=0)
        (self.node / 'journal.jsonl').write_text('{"text": "' + chr(92) + 'ud800 壞字"}' + chr(10) + '{"text": "好"}' + chr(10))
        self.now('--force')
        self.assertIn(chr(92) * 2 + 'ud800 壞字', (self.node / 'journal.jsonl').read_text())

    def test_state_lock_symlink_refused_and_dup_paths(self):
        """.state.lock 是 symlink 就不跟（退 3、pending 留著）；明列與樣式指到同一檔只整理一次。"""
        _, _, state, _, _ = self.brain_node()
        outside = Path(self.root) / 'outside.lock'
        (self.node / 'wf/handoffs/.state.lock').symlink_to(outside)
        self.config(files=['wf/SESSION-LOG.md', 'wf/handoffs/*/STATE.md', 'wf/handoffs/2026-10-09/STATE.md'], keep_recent=5, max_bytes=2048)
        plan = self.now('--dry-run').stdout
        self.assertEqual(plan.count('STATE.md：'), 1)
        self.now(rc=3)
        self.assertFalse(outside.exists())
        self.assertTrue((self.node / 'compact/pending.json').exists())
        (self.node / 'wf/handoffs/.state.lock').unlink()
        self.now()
        self.assertIn('- （摘要 ', state.read_text())

    def test_small_old_part_waits(self):
        """超過門檻但可摘的舊則不到門檻一半：先不摘（免得每回合整理）。"""
        self.config(max_bytes=1000, keep_recent=2)
        path = self.node / 'journal.jsonl'
        small, big = json.dumps({'text': 'x' * 100}) + '\n', json.dumps({'text': 'x' * 450}) + '\n'
        path.write_text(small * 2 + big * 2)
        self.assertIn('不需要整理', self.now('--dry-run').stdout)
        self.assertIn('會摘掉 2 則', self.now('--dry-run', '--force').stdout)
        path.write_text(big * 2 + big * 2)
        self.assertIn('會摘掉 2 則（原因：大小超過 1000）', self.now('--dry-run').stdout)

    def test_size_and_dry_run_tree(self):
        path, *_ = self.fixture()
        before = tree(self.node)
        self.now('--dry-run', '--force')
        self.assertEqual(tree(self.node), before)
        self.now()
        self.assertEqual(path.read_bytes(), before[path.name])
        self.config(max_bytes=path.stat().st_size)
        self.now()
        self.assertEqual(path.read_bytes(), before[path.name])
        self.config(max_bytes=path.stat().st_size - 1)
        self.now()
        self.assertNotEqual(path.read_bytes(), before[path.name])

    def test_no_need_and_dry_run_do_not_create_state(self):
        self.config()
        (self.node / 'journal.jsonl').write_text('{"n":1}\n')
        self.now('--dry-run')
        self.assertFalse((self.node / 'compact').exists())
        self.now()
        self.assertFalse((self.node / 'compact/state.json').exists())

    def test_state_writes_only_changes(self):
        module = self.module()
        md = self.node / 'stage.md'
        md.write_text('## active\n- one\n')
        self.config(files=[md.name])
        self.now()
        with mock.patch.object(module, 'write_json', side_effect=AssertionError('不應寫入')):
            module.once(self.node, module.config(self.node))
        work = self.node / 'compact'
        with mock.patch.object(module, 'write_json', side_effect=AssertionError('假值等價')):
            module.save_state(work, {}, dict(stage_last='', stage_ended=False, stage_due=False))

    def test_events_disabled_leaves_directory_untouched(self):
        for exists in [False, True]:
            with self.subTest(exists=exists):
                node = self.node / str(exists)
                node.mkdir()
                self.fixture(node)
                if exists:
                    (node / 'events').mkdir()
                result = self.now('--force', node=node)
                self.assertNotIn('event', json.loads(result.stdout.splitlines()[-1])['files'][0])
                self.assertEqual((node / 'events').exists(), exists)
                if exists:
                    self.assertEqual(list((node / 'events').iterdir()), [])

    def test_events_type_and_argument_errors(self):
        for bad in [1, 'true', None, [], {}]:
            self.config(events=bad)
            reply = self.now(rc=2)
            self.assertFalse((self.node / 'compact').exists())
            self.assertEqual(len(reply.stderr.splitlines()), 1)
            self.assertTrue(reply.stderr.startswith('aos7-compact: '))
            self.assertIn('。', reply.stderr)
            self.assertIn('例：', reply.stderr)
        for args in [('now',), ('--bogus',)]:
            reply = self.cli(*args, rc=2)
            self.assertEqual(len(reply.stderr.splitlines()), 1)
            self.assertTrue(reply.stderr.startswith('aos7-compact: '))
            self.assertIn('。', reply.stderr)
            self.assertIn('例：', reply.stderr)

    def test_help_exits_zero(self):
        for args in [('--help',), ('now', '--help')]:
            reply = subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True)
            self.assertEqual(reply.returncode, 0)
            self.assertEqual(reply.stderr, '')

    def test_unclassified_exception_is_unknown(self):
        module = self.module()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(module, 'config', side_effect=RuntimeError('測試\n例外')), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(module.main(['now', str(self.node)]), 3)
        self.assertFalse(json.loads(out.getvalue())['ok'])
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertTrue(err.getvalue().startswith('aos7-compact: 不確定：'))
        self.assertIn('RuntimeError', err.getvalue())
        self.assertIn('pending／archive 留著', err.getvalue())

    def test_corrupt_own_json_is_unknown(self):
        self.fixture()
        (self.node / 'compact').mkdir()
        for name in ['pending.json', 'state.json']:
            with self.subTest(name=name):
                bad = self.node / 'compact' / name
                bad.write_text('{"job": ')
                reply = self.now(rc=3)
                self.assertTrue(reply.stderr.startswith('aos7-compact: 不確定：'))
                self.assertEqual(bad.read_text(), '{"job": ')
                bad.unlink()

    def test_event_failure_log_unwritable_still_ok(self):
        module = self.module()
        self.fixture()
        self.config(events=True)
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-replace'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        failed = subprocess.CompletedProcess([], 2, '{"why":"x"}\n', '')
        real = module.append_jsonl
        def append(path, entry):
            if entry.get('status') == 'event_failed':
                raise OSError(28, 'No space left on device')
            return real(path, entry)
        with mock.patch.object(module.subprocess, 'run', return_value=failed), mock.patch.object(module, 'append_jsonl', append):
            entry = module.resume(self.node, self.node / 'compact', pending)
        self.assertEqual(entry['event'], 'failed')
        self.assertFalse((self.node / 'compact/pending.json').exists())

    def test_success_stderr_empty(self):
        self.fixture()
        self.assertEqual(self.now('--force').stderr, '')

    def stage_fixture(self):
        md = self.node / 'SESSION-LOG.md'
        text = '- 修復資料庫索引查詢效能\n- 分析交易鎖競爭延遲\n- 新增資料庫備份驗證\n'
        md.write_text('# 進度\n## 現役\n' + text + '## 下段\n- 不算現役\n')
        journal = self.node / 'journal.jsonl'
        journal.write_text(''.join(json.dumps({'n': n}) + '\n' for n in range(15)))
        self.config(files=[md.name, journal.name])
        self.now()
        md.write_text('# 進度\n## 現役\n## 下段\n- 不算現役\n')
        before = journal.read_bytes()
        self.now()
        self.assertEqual(journal.read_bytes(), before)
        state = read_json(str(self.node / 'compact/state.json'))
        self.assertEqual(state['stage_last'], text)
        self.assertTrue(state['stage_ended'])
        self.assertFalse(state['stage_due'])
        return md, journal, text, before

    def test_stage_change_compacts_small_journal(self):
        md, journal, _, before = self.stage_fixture()
        (self.node / 'events').mkdir()
        cfg = read_json(str(self.node / 'compact.json'), {})
        cfg['events'] = True
        write_json(str(self.node / 'compact.json'), cfg)
        md.write_text('## 現役\n- 繪製星系觀測動畫\n- 選擇畫布配色與字體\n')
        dry_tree = tree(self.node)
        preview = self.now('--dry-run')
        self.assertEqual(tree(self.node), dry_tree)
        self.assertIn('上一段已清空，新段相似度', preview.stdout)
        plans = json.loads(preview.stdout.splitlines()[-1])['files']
        evidence = plans[1]['evidence']
        self.assertTrue(evidence['ended'])
        self.assertLess(evidence['similarity'], .2)
        result = self.now()
        self.assertIn('上一段已清空，新段相似度', result.stdout)
        self.assertNotEqual(journal.read_bytes(), before)
        log = json.loads((self.node / 'compact/log.jsonl').read_text())
        self.assertEqual(log['evidence'], evidence)
        event = self.cli('read', '--events', self.node / 'events', binary=EVENTS)
        payload = json.loads(event.stdout.splitlines()[-1])['records'][0]['payload']
        self.assertEqual(payload['evidence'], evidence)
        self.assertEqual(payload['ref'], log['ref'])
        state = read_json(str(self.node / 'compact/state.json'))
        self.assertFalse(state['stage_ended'])
        self.assertFalse(state['stage_due'])

    def test_stage_similar_restart_does_not_trigger(self):
        md, journal, text, before = self.stage_fixture()
        md.write_text('## 現役\n' + text.replace('效能', '效能改善'))
        self.assertNotIn('會摘掉', self.now('--dry-run').stdout)
        self.now()
        self.assertEqual(journal.read_bytes(), before)
        self.assertFalse((self.node / 'compact/log.jsonl').exists())
        self.assertFalse(read_json(str(self.node / 'compact/state.json'))['stage_ended'])

    def test_stage_bigram_and_threshold_validation(self):
        module = self.module()
        self.assertEqual(module.stage_jaccard(' A B C ', 'abc'), 1)
        self.assertAlmostEqual(module.stage_jaccard('abcd', 'abxy'), 1 / 5)
        self.assertEqual(module.stage_jaccard('aaaa', 'bbbb'), 0)
        with mock.patch.object(module, 'stage_text', return_value='abxy'):
            state = dict(stage_last='abcd', stage_ended=True)
            for threshold, due in [(0.0, False), (.2, False), (.21, True), (1.0, True)]:
                observed = module.observe_stage(self.node, dict(on_stage_change=True, stage_similarity=threshold), state)
                self.assertEqual(observed['stage_due'], due)
                self.assertEqual(observed['stage_last'], 'abxy')
                self.assertFalse(observed['stage_ended'])
            observed = module.observe_stage(self.node, dict(on_stage_change=False, stage_similarity=1.0), state)
            self.assertFalse(observed['stage_due'])
        for bad in [-.1, 1.1, True, '0.2', float('nan'), float('inf')]:
            self.config(stage_similarity=bad)
            self.now(rc=2)
        for threshold in [0.0, .2, 1.0]:
            self.config(stage_similarity=threshold)
            self.now('--dry-run')

    def test_crash_each_point_three_times(self):
        reference = self.node / 'reference'
        reference.mkdir()
        path, *_ = self.fixture(reference)
        self.now('--force', node=reference)
        want = stable(path.read_text())
        for point in ['pending', 'summary', 'archive', 'replace']:
            for repeat in range(3):
                with self.subTest(point=point, repeat=repeat):
                    node = self.node / ('%s-%d' % (point, repeat))
                    node.mkdir()
                    path, old, opened, recent = self.fixture(node)
                    self.now('--force', node=node, rc=-signal.SIGKILL,
                             env={'AOS7_TEST_CRASH': 'compact-after-' + point})
                    self.now(node=node)
                    self.assertEqual(stable(path.read_text()), want)
                    self.assert_compacted(path, old, opened, recent)
                    self.assertFalse((node / 'compact/pending.json').exists())

    def test_append_during_summary_is_retained(self):
        path, old, opened, recent = self.fixture()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        added = '{"new":1}\n{"new":2}\n'
        with path.open('a') as f:
            f.write(added)
        self.now()
        self.assertTrue(path.read_text().endswith(added))
        self.assert_compacted(path, old, opened, recent)

    def test_rewrite_discards_pending_then_replans(self):
        path, *_ = self.fixture()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        rewritten = path.read_text().replace('已完成', '別人改寫', 1)
        path.write_text(rewritten)
        self.now()
        self.assertEqual(path.read_text(), rewritten)
        self.assertFalse((self.node / 'compact/pending.json').exists())
        self.now('--force')
        self.assertNotEqual(path.read_text(), rewritten)

    def test_forget_range_open_refusal_and_override(self):
        path = self.node / 'journal.jsonl'
        lines = [json.dumps({'n': n, 'open': n == 6}) + '\n' for n in range(10)]
        path.write_text(''.join(lines))
        self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 5, '--dry-run')
        self.assertEqual(path.read_text(), ''.join(lines))
        (self.node / 'events').mkdir()
        cfg = read_json(str(self.node / 'compact.json'), {})
        cfg['events'] = True
        write_json(str(self.node / 'compact.json'), cfg)
        self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 5)
        log = json.loads((self.node / 'compact/log.jsonl').read_text())
        self.assertEqual(log['ref'], 'ref://compact/' + log['job'] + '-forget')
        reply = self.cli('read', '--events', self.node / 'events', binary=EVENTS)
        self.assertEqual(json.loads(reply.stdout.splitlines()[-1])['records'][0]['payload']['ref'], log['ref'])
        self.assertEqual(path.read_text(), ''.join(lines[5:]))
        self.assertEqual(next((self.node / 'compact/archive').glob('*')).read_text(), ''.join(lines[:5]))
        before = tree(self.node)
        self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 2, rc=2)
        self.assertEqual(tree(self.node), before)
        self.cli('forget', self.node, '--file', path.name, '--from', 1, '--to', 2, '--include-open')
        self.assertEqual(path.read_text(), ''.join(lines[7:]))
        self.cli('forget', self.node, '--file', path.name, '--from', 0, '--to', 2, rc=2)

    def test_bad_config_and_lock(self):
        (self.node / 'compact.json').write_text('{壞JSON')
        self.now(rc=2)
        self.config()
        directory = self.node / 'compact'
        directory.mkdir(exist_ok=True)
        with (directory / 'lock').open('w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            reply = self.now(rc=3)
            self.assertTrue(reply.stderr.startswith('aos7-compact: 不確定：'))
            self.assertEqual(len(reply.stderr.splitlines()), 1)

    def test_watch_two_tocks(self):
        path, *_ = self.fixture()
        self.config(max_bytes=1)
        task = self.node / '.aos/tasks/compact'
        task.mkdir(parents=True)
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node), AOS7_NODE_ID='n',
                   AOS7_TASK=str(task), AOS7_TID='compact', AOS7_RUN='1')
        p = subprocess.Popen([sys.executable, str(CLI), 'watch', '--rounds', '2'], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        write_json(str(task / 'tock.json'), {'round': 1, 'run': 1})
        self.wait_for(lambda: '摘要' in path.read_text(), msg='watch 沒有處理第一回合')
        write_json(str(task / 'tock.json'), {'round': 2, 'run': 1})
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0, out + err)
        self.assertIsInstance(json.loads(out.strip().splitlines()[-1]), dict)

    def test_watch_recovers_before_first_tock(self):
        path, *_ = self.fixture()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        task = self.node / '.aos/tasks/compact'
        task.mkdir(parents=True)
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node), AOS7_NODE_ID='n',
                   AOS7_TASK=str(task), AOS7_TID='compact', AOS7_RUN='1')
        p = subprocess.Popen([sys.executable, str(CLI), 'watch', '--rounds', '1'], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: not (self.node / 'compact/pending.json').exists(),
                      msg='watch 啟動後未收到 tock，沒有先恢復 pending')
        self.assertIn('摘要', path.read_text())
        self.assertFalse((task / 'tock.json').exists())
        self.assertIsNone(p.poll())
        write_json(str(task / 'tock.json'), {'round': 1, 'run': 1})
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0, out + err)
        self.assertIsInstance(json.loads(out.strip().splitlines()[-1]), dict)

    def test_events_same_job_is_one_record(self):
        self.fixture()
        events = self.node / 'events'
        events.mkdir()
        cfg = read_json(str(self.node / 'compact.json'), {})
        cfg['events'] = True
        write_json(str(self.node / 'compact.json'), cfg)
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-replace'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        self.now()
        write_json(str(self.node / 'compact/pending.json'), pending)
        self.now()
        p = self.cli('read', '--events', events, '--kind', 'compact.done', binary=EVENTS)
        records = json.loads(p.stdout.strip().splitlines()[-1])['records']
        self.assertEqual(len(records), 1)
        self.assertIn(pending['job'], records[0]['event_id'])

    def ledger(self, gateway='fake'):
        write_json(str(self.node / '.aos/round.json'), {'round': 5, 'open': False})
        bd = self.node / 'budget/llm'
        write_json(str(bd / 'grant.json'), {'v': 1, 'grant': 'g1', 'budget': 'llm', 'holder': 'compact',
                   'resource': 'llm.tokens', 'gateway': 'llm.' + gateway, 'amount': 1000000,
                   'clock': 'completed_tock', 'from': 0, 'until': 1000, 'delegate': False})
        self.cli('init', 'budget/llm', binary=BUDGET)
        p = subprocess.Popen([sys.executable, str(BUDGET), 'ledger', 'budget/llm'], cwd=self.node,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: (bd / 'ledger.lock').exists())
        self.config(llm={'budget': 'budget/llm', 'holder': 'compact', 'reserve': 100000,
                         'gateway': gateway, 'model': 'chatgpt-gpt-6-sol-high', 'deadline': 10, 'patience': 2})

    def test_llm_delivered_unsettled_finishes_pending_once(self):
        module = self.module()
        for billing in ['pending', 'overrun']:
            with self.subTest(billing=billing):
                node = self.node / billing
                node.mkdir()
                path, old, opened, recent = self.fixture(node)
                self.config(node, llm={'gateway': 'fake'})

                def delivered_reply(argv, **kwargs):
                    receipt = dict(outcome='answered', billing=billing, text='已交付完整摘要')
                    body = json.dumps(receipt, ensure_ascii=False)
                    Path(argv[argv.index('--out') + 1]).write_text(body)
                    return subprocess.CompletedProcess(argv, 4, body, '')

                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(module.subprocess, 'run', side_effect=delivered_reply) as call, \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(module.main(['now', str(node), '--force']), 0, out.getvalue() + err.getvalue())
                    self.assert_compacted(path, old, opened, recent)
                    self.assertIn('已交付完整摘要', path.read_text())
                    self.assertFalse((node / 'compact/pending.json').exists())
                    self.assertEqual(len((node / 'compact/log.jsonl').read_text().splitlines()), 1)
                    self.assertEqual(module.main(['now', str(node)]), 0)
                    self.assertEqual(call.call_count, 1)
                self.assertEqual(err.getvalue(), '')

    def test_llm_unsettled_failure_keeps_pending_and_original(self):
        module = self.module()
        for outcome, billing in [('failed', 'pending'), ('failed', 'overrun'), ('rejected', 'pending')]:
            with self.subTest(outcome=outcome, billing=billing):
                node = self.node / (outcome + '-' + billing)
                node.mkdir()
                self.config(node, keep_recent=1, llm={'gateway': 'fake'})
                path = node / 'journal.jsonl'
                original = ''.join(json.dumps({'text': f'完成工作 {i}'}) + '\n' for i in range(3))
                path.write_text(original)

                def failed_reply(argv, **kwargs):
                    body = json.dumps(dict(outcome=outcome, billing=billing, text='不可收下的失敗文字'))
                    Path(argv[argv.index('--out') + 1]).write_text(body)
                    return subprocess.CompletedProcess(argv, 4, body, 'aos7-llmcall: 帳未清。查看回條\n')

                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(module.subprocess, 'run', side_effect=failed_reply), \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(module.main(['now', str(node), '--force']), 1)
                self.assertFalse(json.loads(out.getvalue())['ok'])
                self.assertEqual(path.read_text(), original)
                pending = read_json(str(node / 'compact/pending.json'))
                self.assertEqual(pending['original'], original)
                self.assertNotIn('summary', pending)
                self.assertFalse((node / 'compact/archive').exists())
                self.assertFalse((node / 'compact/log.jsonl').exists())
                self.assertEqual(len(err.getvalue().splitlines()), 1)
                self.assertTrue(err.getvalue().startswith('aos7-compact: '))
                self.assertNotIn('不確定：', err.getvalue())

    def test_llm_exit_failure_keeps_pending_and_original(self):
        module = self.module()
        for llm_rc, expected in [(1, 1), (2, 1), (3, 3), (-signal.SIGKILL, 3), (5, 3)]:
            with self.subTest(llm_rc=llm_rc):
                node = self.node / str(llm_rc)
                node.mkdir()
                self.config(node, keep_recent=1, llm={'gateway': 'fake'})
                path = node / 'journal.jsonl'
                original = ''.join(json.dumps({'text': f'完成工作 {i}'}) + '\n' for i in range(3))
                path.write_text(original)
                reply = subprocess.CompletedProcess([], llm_rc, '{"text":"不可收下"}', '')
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(module.subprocess, 'run', return_value=reply), \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(module.main(['now', str(node), '--force']), expected)
                self.assertFalse(json.loads(out.getvalue())['ok'])
                self.assertEqual(path.read_text(), original)
                pending = read_json(str(node / 'compact/pending.json'))
                self.assertEqual(pending['original'], original)
                self.assertNotIn('summary', pending)
                self.assertFalse((node / 'compact/archive').exists())
                self.assertFalse((node / 'compact/log.jsonl').exists())
                self.assertEqual(len(err.getvalue().splitlines()), 1)
                self.assertNotIn('Traceback', err.getvalue())
                self.assertTrue(err.getvalue().startswith('aos7-compact: '))
                self.assertEqual('不確定：' in err.getvalue(), expected == 3)

    def test_llm_summary_resume_sends_once(self):
        path, old, opened, recent = self.fixture()
        self.ledger()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-summary'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        spec = importlib.util.spec_from_file_location('compact_resume_test', CLI.with_name('aos7_compact.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module, 'summarize', side_effect=AssertionError('已有摘要不可重叫摘要者')):
            module.resume(self.node, self.node / 'compact', pending)
        self.now()
        self.assertEqual(read_json(str(self.node / 'llmcall/fake-remote.json'))['sends'][pending['job']], 1)
        self.assert_compacted(path, old, opened, recent)

    def test_llm_fake_failure_keeps_pending_and_original(self):
        path, *_ = self.fixture()
        self.ledger()
        before = path.read_bytes()
        self.now('--force', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'compact-after-pending'})
        pending = read_json(str(self.node / 'compact/pending.json'))
        write_json(str(self.node / ('compact/req-%s.json' % pending['job'])),
                   {'fake': {'mode': 'fail', 'usage': 100, 'text': '不應拿到摘要'}})
        self.now(rc=1)
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue((self.node / 'compact/pending.json').exists())

    def test_ref_expansion_restores_contiguous_original_bytes(self):
        for suffix in ['jsonl', 'md']:
            with self.subTest(suffix=suffix):
                path = self.node / ('journal.' + suffix)
                rows = ([json.dumps({'text': f'開發紀錄 {i}'}, ensure_ascii=False) + '\r\n' for i in range(4)]
                        if suffix == 'jsonl' else [f'- 開發紀錄 {i}\r\n  續行 {i}\r\n' for i in range(4)])
                tail = ('{"open":true,"text":"等待驗證"}\r\n{"recent":1}\r\n' if suffix == 'jsonl'
                        else '- [ ] 等待驗證\r\n- 最近一則\r\n')
                head = '' if suffix == 'jsonl' else '# 日誌\r\n\r\n'
                original = (head + ''.join(rows) + tail).encode()
                path.write_bytes(original)
                self.config(files=[path.name], keep_recent=1)
                self.now('--force')
                content = path.read_bytes()
                marker = next(line for line in content.splitlines(keepends=True) if b'ref://compact/' in line)
                ref_id = re.search(rb'ref://compact/(c[0-9]+-[0-9a-f]+)', marker).group(1).decode()
                archive = self.node / 'compact/archive' / (ref_id + path.suffix)
                self.assertEqual(archive.read_bytes(), ''.join(rows).encode())
                self.assertEqual(content.replace(marker, archive.read_bytes(), 1), original)

    def test_litellm_local_http_content_and_truncation(self):
        path = self.node / 'journal.jsonl'
        old = ''.join(json.dumps({'text': f'修改檔案 code-{i}.py，通過 {i + 2} 項測試'}, ensure_ascii=False) + '\n'
                      for i in range(4))
        path.write_text(old + '{"open":true,"text":"等待審查"}\n')
        self.ledger('litellm')
        self.config(keep_recent=0, summary_max_chars=100,
                    llm={'gateway': 'litellm', 'reserve': 100000, 'deadline': 10})
        bodies = []
        content = ['保留決定、數字 42 與 code.py，待確認延遲。', '摘要過長' * 50]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                bodies.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = json.dumps({'choices': [{'message': {'content': content[len(bodies) - 1]}}],
                                   'usage': {'total_tokens': 100}}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02})
        worker.start()
        try:
            env = {'AOS7_LITELLM_URL': f'http://127.0.0.1:{server.server_port}/v1', 'AOS7_LITELLM_KEY': ''}
            self.now('--force', env=env)
            summary = json.loads(path.read_text().splitlines()[0])
            self.assertEqual(summary['text'], content[0])
            body = bodies[0]
            self.assertEqual(body['model'], 'chatgpt-gpt-6-sol-high')
            self.assertNotIn('max_tokens', body)
            self.assertEqual(body['messages'][1], {'role': 'user', 'content': '以下是共 4 則舊紀錄：\n' + old})
            for phrase in ['agent', '一段繁體中文', '≤100 字', '決定', '數字', '檔名', '未解問題', 'open', '只輸出摘要本文']:
                self.assertIn(phrase, body['messages'][0]['content'])
            self.assertNotIn('truncated', json.loads((self.node / 'compact/log.jsonl').read_text()))
            path.write_text(old + '{"open":true,"text":"新的審查"}\n')
            self.now('--force', env=env)
            self.assertEqual(json.loads(path.read_text().splitlines()[0])['text'], content[1][:100])
            logs = [json.loads(line) for line in (self.node / 'compact/log.jsonl').read_text().splitlines()]
            self.assertTrue(logs[-1]['truncated'])
            self.assertEqual(len(bodies), 2)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)

    def test_jsonl_bad_line_and_open_string_recent_untouched(self):
        path = self.node / 'journal.jsonl'
        rows = ['{"n":0}\r\n', '{"n":1}\r\n', '壞 JSON 原樣\r\n',
                '"含 - [ ] 未完成"\r\n', '{"status":"open"}\r\n',
                '{"nested":{"text":"- [ ] 仍待辦"}}\r\n', '\r\n', '{"recent":true}\r\n']
        path.write_bytes(''.join(rows).encode())
        self.config(keep_recent=1)
        self.now('--force')
        content = path.read_bytes()
        for row in rows[2:]:
            self.assertIn(row.encode(), content)
        self.assertIn(b'"compact":', content)



if __name__ == '__main__':
    unittest.main()
