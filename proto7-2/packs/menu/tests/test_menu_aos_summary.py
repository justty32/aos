"""MN2 真實 luna-1 第二關回條與跨題摘要回歸。"""
import importlib.util
import json
from pathlib import Path
import unittest

PACK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('menu_aos_build_summary',
                                              PACK / 'examples/aos-tool/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def unittest_failure_output(first='test_empty', second='test_exit', separator=True):
    boundary = '=' * 70 + '\n' if separator else ''
    return ('FE\n' + boundary + f'FAIL: {first} (test_mailcount.TestMail)\n'
            + '-' * 70 + '\nTraceback (most recent call last):\n'
            + '  File "tests/test_mailcount.py", line 18, in test_empty\n' * 40
            + '    self.assertEqual(actual, expected)\nAssertionError: empty\n\n'
            + boundary + f'ERROR: {second} (test_mailcount.TestMail)\n'
            + '-' * 70 + '\nTraceback (most recent call last):\n'
            + '  File "tests/test_mailcount.py", line 30, in test_exit\n' * 40
            + '    raise ValueError("exit")\nValueError: exit\n\n'
            + '-' * 70 + '\nRan 2 tests in 0.002s\n\nFAILED (failures=1, errors=1)\n')


class MenuAosSummary(unittest.TestCase):
    def test_same_issue_keeps_each_unittest_failure(self):
        for separator in (True, False):
            with self.subTest(separator=separator):
                check = {'failed_gate': 2, 'issues': [{
                    'rule': 'test', 'file': 'tests/test_mailcount.py',
                    'why': unittest_failure_output(separator=separator)}]}
                text = build.summary(check)
                for detail in ('FAIL: test_empty (test_mailcount.TestMail)',
                               'AssertionError: empty',
                               'ERROR: test_exit (test_mailcount.TestMail)',
                               'ValueError: exit'):
                    self.assertIn(detail, text)
                self.assertNotIn('Traceback', text)
                self.assertNotIn('Ran 2 tests', text)
                self.assertNotIn('FAILED (', text)
                self.assertNotIn('\n', text)
                self.assertLessEqual(len(text), 580)

    def test_long_test_names_preserve_exceptions_with_other_issue(self):
        for as_list in (False, True):
            with self.subTest(as_list=as_list):
                output = unittest_failure_output('test_empty_' + 'x' * 600,
                                                'test_exit_' + 'y' * 600)
                check = {'failed_gate': 2, 'issues': [
                    {'rule': 'test', 'why': [output] if as_list else output},
                    {'rule': 'schema', 'why': 'required field missing'},
                ]}
                text = build.summary(check)
                for detail in ('FAIL: test_empty_', 'AssertionError: empty',
                               'ERROR: test_exit_', 'ValueError: exit',
                               'required field missing'):
                    self.assertIn(detail, text)
                self.assertLessEqual(len(text), 580)

    def test_luna1_real_answer_keeps_all_conventions(self):
        # Actual author check from MN2.smoke/luna-1; no model call is replayed.
        check = json.loads((PACK / 'tests/fixtures/luna1-gate2.json').read_text())
        text = build.summary(check)
        self.assertTrue(text.startswith('第2關：answer check_answer.py：'))
        self.assertLessEqual(len(text), 580)
        for explanation in ('inbox/done/，仍是那個人的信',
                            '. 開頭的檔與資料夾都不是信',
                            'teams/ 是團隊資料夾，不是人；團隊信不算'):
            self.assertIn(explanation, text)
        messages = check['gates']['2']['issues'][0]['why']
        for message in messages:
            self.assertIn(message.split('：答案不合', 1)[0] + '：答案不合', text)
        self.assertEqual(text.count('得到 '), 1)
        self.assertEqual(text.count('應為 '), 1)
        self.assertNotIn('"v": 1', text)
        self.assertNotIn('\n', text)

    def test_other_topics_and_first_colon_fallback(self):
        check = {'failed_gate': 2, 'gates': {'2': {'issues': [{'rule': 'answer', 'why': [
            '序號（含重複）：答案不合：得到 {"label": "two words", "n": 4}；應為 {"n": 3}',
            '排序（由舊至新）：答案不合：得到 {"second": true}；應為 {"second": false}',
            '固定時間（不讀時鐘）：退出碼不合：得到 {"third": 0}；應為 {"third": 2}',
        ]}]}}}
        text = build.summary(check)
        self.assertIn('序號（含重複）：答案不合', text)
        self.assertIn('排序（由舊至新）：答案不合', text)
        self.assertIn('固定時間（不讀時鐘）：退出碼不合', text)
        self.assertIn('得到 {"label":"two words","n":4}', text)
        self.assertIn('應為 {"n":3}', text)
        self.assertNotIn('"second"', text)
        self.assertNotIn('"third"', text)
        self.assertLessEqual(len(text), 580)


if __name__ == '__main__':
    unittest.main()
