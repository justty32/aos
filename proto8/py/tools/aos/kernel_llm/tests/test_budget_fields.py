# Check BudgetMissing refusals carry scope/window/since/resets_at/limit/max, and window_next on fixed times.
import calendar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest

import test_ledger

for folder in ('py', 'py/tools/aos/kernel', 'py/tools/aos/kernel_llm'):
    sys.path.insert(0, str(test_ledger.PROTO / folder))
import budget  # noqa: E402

ISO = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$')


class WindowNext(unittest.TestCase):
    def at(self, tz, text):
        self.addCleanup(self.restore, os.environ.get('TZ'))
        os.environ['TZ'] = tz
        time.tzset()
        return time.mktime(time.strptime(text, '%Y-%m-%d %H:%M:%S'))

    def restore(self, old):
        if old is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = old
        time.tzset()

    def test_hour_and_day_in_utc(self):
        now = self.at('UTC', '2026-11-14 10:37:12')
        self.assertEqual(budget.window_since('hour', now), '2026-11-14T10:00:00+00:00')
        self.assertEqual(budget.window_next('hour', now), '2026-11-14T11:00:00+00:00')
        self.assertEqual(budget.window_next('day', now), '2026-11-15T00:00:00+00:00')

    def test_all_has_no_next_window(self):
        self.assertIsNone(budget.window_next('all', time.time()))

    def test_rollover_at_midnight_month_and_year_ends(self):
        now = self.at('UTC', '2026-12-31 23:59:59')
        self.assertEqual(budget.window_next('hour', now), '2027-01-01T00:00:00+00:00')
        self.assertEqual(budget.window_next('day', now), '2027-01-01T00:00:00+00:00')

    def test_offset_zone_keeps_the_offset(self):
        now = self.at('Asia/Taipei', '2026-11-14 23:30:00')
        self.assertEqual(budget.window_next('hour', now), '2026-11-15T00:00:00+08:00')
        self.assertEqual(budget.window_next('day', now), '2026-11-15T00:00:00+08:00')

    def test_dst_fall_back_hour_is_start_plus_3600(self):
        # US fall back 2026-11-01 06:00 UTC: local 01:00-01:59 happens twice. The second 01:30 (EST) is 06:30 UTC.
        self.at('America/New_York', '2026-11-01 00:00:00')
        second = calendar.timegm((2026, 11, 1, 6, 30, 0))
        self.assertEqual(time.strftime('%H:%M %Z', time.localtime(second)), '01:30 EST')
        self.assertEqual(budget.window_next('hour', second), '2026-11-01T02:00:00-05:00')   # never in the past
        # the first 01:30 (EDT, 05:30 UTC): the next window is one hour on, 01:00 EST
        first = second - 3600
        self.assertEqual(time.strftime('%H:%M %Z', time.localtime(first)), '01:30 EDT')
        self.assertEqual(budget.window_next('hour', first), '2026-11-01T01:00:00-05:00')

    def test_dst_day_window_spans_23_or_25_hours(self):
        now = self.at('America/New_York', '2026-11-01 12:00:00')
        self.assertEqual(budget.window_since('day', now), '2026-11-01T00:00:00-04:00')
        self.assertEqual(budget.window_next('day', now), '2026-11-02T00:00:00-05:00')

    def test_format_matches_window_since(self):
        now = time.time()
        for window in ('hour', 'day'):
            self.assertRegex(budget.window_next(window, now), ISO)


class BudgetFields(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp

    def kernel(self, cfg, sender=None, tz='UTC'):
        ws = self.stack / 'agents/a'
        ws.mkdir(parents=True, exist_ok=True)
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True, exist_ok=True)
        folder = self.stack / 'requests/new/L1'
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'sender': str(ws), 'sent_at': '2026-11-10T00:00:00+08:00',
            'reply_to': str(box), 'body': {'request': {'messages': []}}}))
        self.config.write_text(json.dumps(dict({'exec': str(test_ledger.FAKE.parent), 'endpoints': {'fake': {}},
                                                'endpoint': 'fake'}, **cfg)))
        self.env['TZ'] = tz
        before = time.time()
        p = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                           capture_output=True, text=True, timeout=10)
        after = time.time()
        self.assertEqual(p.returncode, 0, p.stderr)
        (reply,) = [json.loads(path.read_text()) for path in (box / 'new').glob('*/letter.json')]
        return reply['body']['error'], (before, after)

    def expect(self, window, bounds):
        """resets_at/since must be the boundaries of the window the kernel ran in (UTC)."""
        os.environ['TZ'] = 'UTC'
        time.tzset()
        return {budget.window_next(window, bounds[0]), budget.window_next(window, bounds[1])}

    def test_total_calls_hour(self):
        err, bounds = self.kernel({'budget': {'max_calls': 0, 'window': 'hour'}})
        self.assertEqual(err['msg'], 'budget for this window (hour) is used up; not run')
        self.assertEqual((err['code'], err['scope'], err['window'], err['limit'], err['max']),
                         ('BudgetMissing', 'total', 'hour', 'max_calls', 0))
        self.assertEqual(set(err), {'code', 'msg', 'scope', 'window', 'since', 'resets_at', 'limit', 'max'})
        self.assertIn(err['resets_at'], self.expect('hour', bounds))
        self.assertRegex(err['since'], ISO)
        self.assertTrue(err['since'].endswith(':00:00+00:00') and err['resets_at'].endswith(':00:00+00:00'))

    def test_total_tokens_day(self):
        err, bounds = self.kernel({'budget': {'max_tokens': 0, 'window': 'day'}})
        self.assertEqual((err['scope'], err['window'], err['limit'], err['max']), ('total', 'day', 'max_tokens', 0))
        self.assertIn(err['resets_at'], self.expect('day', bounds))
        self.assertTrue(err['since'].endswith('T00:00:00+00:00') and err['resets_at'].endswith('T00:00:00+00:00'))

    def test_total_all_has_null_since_and_resets_at(self):
        err, _ = self.kernel({'budget': {'max_calls': 0, 'window': 'all'}})
        self.assertEqual(err['msg'], 'budget for this window (all) is used up; not run')
        self.assertIsNone(err['since'])
        self.assertIsNone(err['resets_at'])
        self.assertEqual((err['scope'], err['window']), ('total', 'all'))

    def test_endpoint_scope_names_the_endpoint(self):
        err, bounds = self.kernel({'endpoints': {'fake': {'budget': {'max_calls': 0}}}})
        self.assertEqual(err['msg'], 'endpoint fake: max_calls 0 reached in this window (day); not run '
                                     '(no fallback: pick another endpoint name)')
        self.assertEqual((err['scope'], err['endpoint'], err['window'], err['limit'], err['max']),
                         ('endpoint', 'fake', 'day', 'max_calls', 0))
        self.assertNotIn('key', err)
        self.assertIn(err['resets_at'], self.expect('day', bounds))

    def test_endpoint_tokens_limit(self):
        err, _ = self.kernel({'endpoints': {'fake': {'budget': {'max_tokens': 0}}}, 'budget': {'window': 'all'}})
        self.assertEqual((err['scope'], err['limit'], err['max'], err['resets_at']), ('endpoint', 'max_tokens', 0, None))

    def test_sender_scope_keeps_the_key_as_written(self):
        err, bounds = self.kernel({'budget': {'senders': {'agents/a': {'max_calls': 0}}, 'window': 'hour'}})
        self.assertEqual(err['msg'], 'budget.senders key "agents/a" (sender %s): max_calls 0 reached in this window '
                                     '(hour); not run' % (self.stack / 'agents/a'))
        self.assertEqual((err['scope'], err['key'], err['window'], err['limit'], err['max']),
                         ('sender', 'agents/a', 'hour', 'max_calls', 0))
        self.assertNotIn('endpoint', err)
        self.assertIn(err['resets_at'], self.expect('hour', bounds))

    def test_wait_mode_sends_no_refusal(self):
        ws = self.stack / 'agents/a'
        self.config.write_text(json.dumps({'exec': str(test_ledger.FAKE.parent), 'endpoints': {'fake': {}},
                                           'endpoint': 'fake', 'budget': {'max_calls': 0, 'spent': 'wait'}}))
        folder = self.stack / 'requests/new/L1'
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'sender': str(ws), 'reply_to': str(self.stack / 'replies'),
            'body': {'request': {'messages': []}}}))
        p = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(folder.exists())   # still waiting in new/


if __name__ == '__main__':
    unittest.main()
