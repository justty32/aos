"""第三輪：未結帳回答遇到 step 模板失敗仍落證據且可接續。"""
import contextlib
import io
from unittest.mock import patch
from menucase import MenuCase, simple
import aos7_menu_run as driver


class MenuRunReview2(MenuCase):
    def test_unsettled_step_error_preserves_reply_and_warns_on_retry(self):
        obj = simple()
        obj['layers']['one']['options'][0]['set'] = {'file': '{missing}'}
        menu = self.fixture(obj)
        stderr = io.StringIO()
        with patch.object(driver, 'ai', return_value=('選：1', 17, 4)) as ai, contextlib.redirect_stderr(stderr):
            self.assertEqual(driver.main(['run', str(self.node), str(menu), '--llm', 'fake']), 2)
        self.assertEqual(ai.call_count, 1)
        self.assertIn('帳還沒結清', stderr.getvalue())
        self.assertEqual(len(stderr.getvalue().splitlines()), 1)
        state = self.state('test')
        self.assertEqual(state['pending']['received'], {'reply': '選：1', 'used': 17, 'rc': 4})
        self.assertEqual(state['calls'], [])
        row = self.logs('test')[-1]
        self.assertEqual(row['kind'], 'reply-error')
        self.assertTrue(row['unsettled'])
        self.assertEqual(row['call_id'], state['pending']['call_id'])
        stderr = io.StringIO()
        with patch.object(driver, 'ai', side_effect=AssertionError('不可重問')), contextlib.redirect_stderr(stderr):
            self.assertEqual(driver.main(['run', str(self.node), str(menu), '--llm', 'fake']), 2)
        self.assertIn('帳還沒結清', stderr.getvalue())
        # 修復環境中的變數後，接續消化原回答；不重問也不重複登記 calls。
        state = self.state('test')
        state['vars']['missing'] = 'fixed'
        driver.save(self.node / 'menu/test', state)
        stderr = io.StringIO()
        with patch.object(driver, 'ai', side_effect=AssertionError('不可重問')), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(driver.main(['run', str(self.node), str(menu), '--llm', 'fake']), 0)
        self.assertIn('帳還沒結清', stderr.getvalue())
        state = self.state('test')
        self.assertEqual(len(state['calls']), 1)
        self.assertIsNone(state['pending'])
        self.assertEqual(state['vars']['file'], 'fixed')
