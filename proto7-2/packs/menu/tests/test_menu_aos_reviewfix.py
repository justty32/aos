"""MN2 review regressions: transport faults, section boundaries and issue budgets."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import time
from unittest.mock import patch

import test_menu_aos as cases

spec = importlib.util.spec_from_file_location('menu_aos_build_reviewfix', cases.BUILD)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class MenuAosReviewFix(cases.MenuCase):
    build = cases.MenuAos.build
    result = cases.MenuAos.result
    materialize = cases.MenuAos.materialize
    fake = cases.MenuAos.fake

    def success(self):
        return {'ok': True, 'failed_gate': None,
                'gates': {str(n): {'ok': True, 'issues': []} for n in (1, 2, 3)}}

    def test_body_section_headers_rejected_in_every_section(self):
        run, candidate = self.materialize()
        for name in [*candidate['files'], 'row', 'report']:
            path = run / 'out' / name
            original = path.read_text()
            for header in ('=== row ===\n', '=== packs/other/x.py ===\r\n', '=== report ==='):
                with self.subTest(name=name, header=header):
                    path.write_text('first line\n' + header)
                    value = self.result('check', run, cases.REQUEST, rc=1)
                    self.assertEqual(value['gate'], 1)
                    self.assertEqual(value['issues'], '第1關：format ' + name +
                                     ' 第2行：內容裡不能有段頭行（=== … ===），改寫那一行')
                    self.assertFalse((run / 'candidate.txt').exists())
            path.write_text(original)

    def test_similar_body_lines_that_author_does_not_split_are_allowed(self):
        run, _ = self.materialize()
        path = run / 'out/packs/mailcount/README.md'
        lines = [' === row ===', '=== two words ===', '=== row === ',
                 'prefix === row ===', '=== row ==', '===\trow ===']
        path.write_text('\n'.join(lines))
        self.result('check', run, cases.REQUEST, env=self.fake(self.success()))
        for line in lines:
            self.assertIn(line, (run / 'candidate.txt').read_text())

    def test_child_exit_status_is_not_a_candidate_failure(self):
        run, _ = self.materialize()
        failure = {'ok': False, 'failed_gate': 1,
                   'gates': {'1': {'ok': False, 'issues': [{'rule': 'schema', 'why': 'bad'}]}}}
        for author in (False, True):
            extra = ['--review', 'fake-model'] if author else []
            for rc in (2, 3):
                for raw in (False, True):
                    with self.subTest(author=author, rc=rc, raw=raw):
                        receipt = {'ok': False, 'why': 'invalid', 'check': failure} if author else failure
                        env = self.fake(receipt, rc=rc, author=author, raw='argument error' if raw else None)
                        self.result('check', run, cases.REQUEST, *extra, rc=rc, env=env)
        receipt = {'ok': False, 'why': 'unknown', 'check': failure}
        self.result('check', run, cases.REQUEST, '--review', 'fake-model', rc=3,
                    env=self.fake(receipt, rc=1, author=True))

    def test_request_io_failures_distinguish_bad_input_from_uncertainty(self):
        for number, expected in ((errno.EIO, 3), (errno.EACCES, 3), (errno.EMFILE, 3),
                                 (errno.ENOENT, 2), (errno.ENOTDIR, 2), (errno.EISDIR, 2)):
            with self.subTest(errno=number), patch.object(Path, 'read_text', side_effect=OSError(number, 'fault')):
                with self.assertRaises(build.Problem) as caught:
                    build.request(Path('request.json'))
                self.assertEqual(caught.exception.code, expected)

    def test_review_delivery_failed_after_rules_pass_is_uncertain(self):
        run, _ = self.materialize()
        for error in ('模型那邊確定沒做成', '模型那邊確定沒做成：grant amount 400000 不足 reserve 1000000'):
            # propose_checks returns the unchanged successful rules check, not
            # failed_gate=3, when delivery returned no review artifact.
            receipt = {'ok': False, 'why': 'invalid', 'llm': None,
                       'candidate_path': str(run / 'candidate.txt'), 'candidate_sha': 'a' * 64,
                       'job': 'mailcount_aaaaaaaa', 'rules_check': self.success(),
                       'check': self.success(), 'error': error,
                       'review': {'llm': {'model': 'fake-model', 'exit': 1,
                                         'reserve': 1000000, 'receipt_path': None}, 'path': None}}
            with self.subTest(error=error):
                p = self.build('check', run, cases.REQUEST, '--review', 'fake-model', rc=3,
                               env=self.fake(receipt, rc=1, author=True))
                self.assertFalse(json.loads(p.stdout)['ok'])
                self.assertIn('審查', p.stderr)
                self.assertTrue('帳' in p.stderr or '模型' in p.stderr)
                self.assertNotIn('修好再交', p.stderr)

    def test_timeout_reaps_own_process_group_including_grandchild(self):
        run, _ = self.materialize()
        fake = self.node / 'sleep-gates.py'
        ids = self.node / 'sleep-pids.json'
        fake.write_text('import json,os,subprocess,sys,time\n'
                        'from pathlib import Path\n'
                        'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n'
                        'Path(' + repr(str(ids)) + ').write_text(json.dumps([os.getpid(),child.pid,os.getpgrp()]))\n'
                        'time.sleep(30)\n')
        pgid = None
        try:
            self.result('check', run, cases.REQUEST, rc=3,
                        env={'AOS7_AOS_TOOL_GATES': str(fake), 'AOS7_AOS_TOOL_TIMEOUT': '0.35'})
            parent, child, pgid = json.loads(ids.read_text())
            self.assertEqual(parent, pgid)
            self.assertNotIn(pgid, (0, 1, os.getpgrp()))
            def running(pid):
                try:
                    return Path('/proc/%d/stat' % pid).read_text().split(') ', 1)[1][0] != 'Z'
                except FileNotFoundError:
                    return False
            deadline = time.monotonic() + 2
            while any(running(pid) for pid in (parent, child)) and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertFalse(running(parent), 'gates survived timeout')
            self.assertFalse(running(child), 'grandchild survived timeout')
        finally:
            # Test cleanup is limited to the subprocess session we created.
            if pgid is None and ids.exists():
                pgid = json.loads(ids.read_text())[2]
            if pgid is not None and pgid > 1 and pgid != os.getpgrp():
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_long_traceback_before_answer_keeps_both_causes(self):
        traceback = '\n'.join(['Traceback (most recent call last):'] +
                              ['  File "test_wrong.py", line 100, in test_count'] * 50 +
                              ['    self.assertEqual(actual, expected)', 'AssertionError: wrong total', '',
                               '----------------------------------------------------------------------',
                               'Ran 3 tests in 0.002s', '', 'FAILED (failures=1)'])
        check = {'failed_gate': 2, 'gates': {'2': {'issues': [
            {'rule': 'test', 'file': 'tests/test_wrong.py', 'why': traceback},
            {'rule': 'answer', 'file': 'check_answer.py', 'why': [
                '邊界資料（空目錄也要列出）：答案不合：得到 {"n": 0}；應為 {"n": 1}']},
        ]}}}
        text = build.summary(check)
        self.assertLessEqual(len(text), 580)
        for detail in ('test tests/test_wrong.py', 'AssertionError: wrong total',
                       'answer check_answer.py', '空目錄也要列出', '答案不合'):
            self.assertIn(detail, text)
        self.assertEqual(text.count('line 100'), 1)
        self.assertNotIn('Ran 3 tests', text)

    def test_long_suggestion_before_review_rejection_keeps_actual_reasons(self):
        check = {'failed_gate': 3, 'gates': {'3': {'issues': [
            {'rule': 'review', 'why': ['建議：' + '可以改善可讀性。' * 200,
                                      '錯誤：空目錄被忽略，違反需求', '退出碼錯誤，必須回傳 2']},
        ]}}}
        text = build.summary(check)
        self.assertLessEqual(len(text), 580)
        self.assertTrue(text.startswith('第3關：'))
        self.assertIn('錯誤：空目錄被忽略，違反需求', text)
        self.assertIn('退出碼錯誤，必須回傳 2', text)
        if '建議：' in text:
            self.assertLess(text.index('錯誤：'), text.index('建議：'))
