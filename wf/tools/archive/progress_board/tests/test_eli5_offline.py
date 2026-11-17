"""Verify explanation caching, changed-only prompts, cleanup, partial replies and CLI offline."""
import contextlib
import io
import json
import sys
from unittest.mock import patch
import unittest
from eli5_support import OfflineBoard, WORDS, eli5, nest
import dash


class GenerationTests(OfflineBoard):
    def test_first_run_no_change_and_changed_line_interval(self):
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertEqual(set(self.calls[0]), {'summary', 'lines.alpha', 'lines.beta'})
        self.assertEqual(set(self.calls[1]), {'lines.alpha.timeline', 'lines.alpha.handoff',
                                             'lines.beta.timeline', 'codex', 'reports'})
        self.calls.clear()
        self.assertEqual(self.generate(), ('skipped', 'skipped'))
        self.assertEqual(self.calls, [])
        self.events[0]['text'] = 'Changed evidence with the very same timestamp.'
        self.flush()
        self.assertEqual(self.generate(), ('skipped', 'skipped'))
        self.assertEqual(self.calls, [])
        state = eli5.eli5_state(self.board, self.cfg)
        self.assertTrue(state['main']['lines']['alpha']['stale'])
        self.assertTrue(state['detail']['lines']['alpha']['timeline']['stale'])
        self.age('main')
        self.age('detail')
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertEqual([set(x) for x in self.calls],
                         [{'lines.alpha'}, {'lines.alpha.timeline'}])
        state = eli5.eli5_state(self.board, self.cfg)
        self.assertFalse(state['main']['lines']['alpha']['stale'])
        self.assertFalse(state['detail']['lines']['alpha']['timeline']['stale'])
        costs = [json.loads(x) for x in (self.board/'summary/cost.jsonl').read_text().splitlines()]
        self.assertEqual(len(costs), 4)
        self.assertEqual({x['kind'] for x in costs}, {'eli5-main', 'eli5-detail'})
        for item in costs:
            self.assertTrue(item['ok'])
            self.assertEqual([item[k] for k in ('prompt_tokens','completion_tokens','total_tokens')],
                             [11, 7, 18])

    def test_partial_main_ignores_extra_retries_only_missing(self):
        self.responses = [{'items': {'summary': WORDS, 'lines.alpha': WORDS, 'intruder': WORDS}}]
        self.assertEqual(eli5.maybe_main(self.board, self.cfg), 'ok')
        saved = self.stored('main')
        self.assertEqual(saved['summary']['text'], WORDS)
        self.assertEqual(set(saved['lines']), {'alpha'})
        self.assertNotIn('intruder', saved)
        costs = [json.loads(x) for x in (self.board/'summary/cost.jsonl').read_text().splitlines()]
        self.assertTrue(costs[-1]['ok'])
        self.assertTrue(costs[-1]['error'])
        self.calls.clear()
        self.assertEqual(eli5.maybe_main(self.board, self.cfg), 'skipped')
        self.assertEqual(self.calls, [])
        self.age('main')
        self.assertEqual(eli5.maybe_main(self.board, self.cfg), 'ok')
        self.assertEqual(set(self.calls[-1]), {'lines.beta'})

    def test_partial_detail_and_zero_valid_failure_throttle(self):
        self.responses = [{'items': {'lines.alpha.timeline': WORDS, 'invented': WORDS}}]
        self.assertEqual(eli5.maybe_detail(self.board, self.cfg), 'ok')
        self.assertEqual(set(self.stored('detail')['lines']['alpha']), {'timeline'})
        self.age('detail')
        self.calls.clear()
        self.assertEqual(eli5.maybe_detail(self.board, self.cfg), 'ok')
        self.assertEqual(set(self.calls[-1]), {'lines.alpha.handoff', 'lines.beta.timeline',
                                              'codex', 'reports'})
        self.events[0]['text'] = 'Another change.'
        self.flush()
        self.age('detail')
        self.responses = [{'items': {'invented': WORDS}}]
        self.assertEqual(eli5.maybe_detail(self.board, self.cfg), 'error')
        count = len(self.calls)
        self.assertEqual(eli5.maybe_detail(self.board, self.cfg), 'skipped')
        self.assertEqual(len(self.calls), count)

    def test_answer_and_removed_line_cleanup_without_generation(self):
        ask = self.event('alpha', 'Choose the next step.', id='question', status='ask',
                         options=[{'key': 'a', 'text': 'Continue'}], recommend='a')
        self.events.append(ask)
        self.flush()
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertEqual(set(self.stored('main')['asks']), {'question'})
        self.write('data/answers.jsonl', json.dumps(dict(ts=ask['ts'], id='question',
                    line='alpha', choice='a', comment=''))+'\n')
        self.cfg['lines'] = self.cfg['lines'][:1]
        self.events = [x for x in self.events if x['line'] != 'beta']
        self.flush()
        self.calls.clear()
        self.generate()
        self.assertNotIn('question', self.stored('main').get('asks', {}))
        self.assertNotIn('beta', self.stored('main').get('lines', {}))
        self.assertNotIn('beta', self.stored('detail').get('lines', {}))
        self.assertEqual(self.calls, [])

    def test_legacy_file_cache_is_empty_and_immediately_eligible(self):
        for kind, field in [('main', 'fingerprint'), ('detail', 'fingerprints')]:
            self.write(f'eli5/{kind}.json', json.dumps({field: 'legacy',
                       'generated_at': __import__('collect').iso_now(),
                       'lines': {'alpha': 'Legacy explanation'}}))
        state = eli5.eli5_state(self.board, self.cfg)
        self.assertEqual(state['main']['lines'], {})
        self.assertEqual(state['detail']['lines'], {})
        self.assertIsNone(state['main']['generated_at'])
        self.assertIsNone(state['detail']['generated_at'])
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.assertEqual(len(self.calls), 2)

    def test_quality_rewrite_preserves_valid_items_on_subset_empty_and_failure(self):
        first = {'items': {'summary': WORDS, 'lines.alpha': 'codex is working',
                           'lines.beta': WORDS}}
        def broken(_):
            raise OSError('Synthetic offline failure')
        for second in [{'items': {'lines.alpha': WORDS}}, {'items': {}}, broken]:
            with self.subTest(second=str(second)):
                self.responses = [first, second]
                self.assertEqual(eli5.maybe_main(self.board, self.cfg,
                                                force=True, all_items=True), 'ok')
                stored = self.stored('main')
                self.assertEqual(stored['summary']['text'], WORDS)
                self.assertEqual(set(stored['lines']), {'alpha', 'beta'})
                self.assertEqual(stored['lines']['beta']['text'], WORDS)

    def test_top_level_next_eligible_is_earliest_changed_file(self):
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.events[0]['text'] = 'New content.'
        self.flush()
        state = eli5.eli5_state(self.board, self.cfg)
        self.assertIn('next_eligible_ts', state)
        stamp = __import__('collect').parse_ts
        self.assertEqual((stamp(state['main']['next_eligible_ts']) -
                          stamp(state['main']['generated_at'])).total_seconds(), 240)
        self.assertEqual(state['next_eligible_ts'], min(state[k]['next_eligible_ts']
                                                      for k in ('main', 'detail')))

    def test_cli_force_changed_only_and_all_regenerates(self):
        self.assertEqual(self.generate(), ('ok', 'ok'))
        self.calls.clear()
        def cli(*args):
            with patch.object(sys, 'argv', ['dash.py', 'eli5', *args]), \
                 patch('dash.load_config', return_value=self.cfg), \
                 patch('dash.snapshot') as snap, contextlib.redirect_stdout(io.StringIO()):
                code = dash.main()
                snap.assert_called_once()
                return code
        self.assertEqual(cli('--force'), 0)
        self.assertEqual(self.calls, [])
        self.events[0]['text'] = 'Changed evidence.'
        self.flush()
        self.assertEqual(cli('--force'), 0)
        self.assertEqual([set(x) for x in self.calls],
                         [{'lines.alpha'}, {'lines.alpha.timeline'}])
        self.calls.clear()
        self.assertEqual(cli('--all'), 0)
        self.assertEqual(set(self.calls[0]), {'summary', 'lines.alpha', 'lines.beta'})
        self.assertIn('lines.alpha.handoff', self.calls[1])


if __name__ == '__main__':
    unittest.main()
