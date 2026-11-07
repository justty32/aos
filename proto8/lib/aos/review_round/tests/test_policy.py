# Verify watch exclusions, tree selection, history baselines and retirement decisions.
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import round_runner
from review_data import add_cost, write


def cost(tokens):
    return {'token': {'in': tokens, 'out': 2, 'cached': 0}, 'counter_calls': 1, 'time_ms': 5}


def node(name, tokens=10, kind='agent', children=None):
    return {'def': name, 'kind': kind, 'cost': cost(tokens), 'children': children or []}


def measurement(tree=None, tokens=100):
    return {'cost': cost(tokens), 'size_bytes': 100, 'tree': tree or node('d'),
            'check': {'pass': True, 'scores': [1, 1], 'cost': cost(3)},
            'samples': [{'cost': cost(tokens)}, {'cost': cost(tokens)}],
            'consistency': {'pass': True, 'scores': [1]}}


class ReviewPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-review-policy-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.defs, self.ws = self.root / 'defs', self.root / 'ws'
        self.defs.mkdir()
        self.ws.mkdir()
        self.settings = self.root / 'ladder.json'
        write(self.settings, {'ladder': ['high', 'low'], 'repeat': 2, 'min_score': .9,
                              'promote_by': 'self', 'watch': {
                                  'window': 3, 'tolerance': .1, 'metric': '/token/in', 'baseline_cases': 3}})
        self.args = {'defs': str(self.defs), 'case': str(self.root / 'case'),
                     'ws': str(self.ws), 'ladder': str(self.settings), 'daemons': []}
        self.calls = []
        self.measures = []
        self.feed = {'changes': []}
        self.busy = False

    def definition(self, name, endpoint='high'):
        folder = self.defs / name
        folder.mkdir(parents=True)
        write(folder / 'llm.json', {'endpoint': endpoint})
        write(folder / 'interfaces.json', {'aos-agent': {}})

    def call(self, name, target, args, **kwargs):
        self.calls.append((name, copy.deepcopy(args)))
        if name.startswith('measure_'):
            return copy.deepcopy(self.measures.pop(0))
        if name == 'watch_feed':
            return self.feed
        if name == 'promote':
            if self.busy:
                raise round_runner.Error('DefBusy', 'a proc is using d')
            return {'promoted_at': '2026-11-07T10:00:00.000Z'}
        if name == 'watch_open':
            return {'changes': [{'target': args['target'], 'state': 'watching', 'reason': 'Opened.'}]}
        self.fail('Unexpected tool call: ' + name)

    def run_round(self):
        with patch.dict(os.environ, {'AOS_STACK': str(self.root / 'stack')}), patch.object(
                round_runner, 'call', side_effect=self.call):
            result = round_runner.run(self.args)
        return json.loads(Path(result['review']).read_text())

    def test_watch_and_external_nodes_are_skipped_before_cost_sorting(self):
        self.definition('d', 'unknown')
        self.definition('watching')
        self.definition('reverted')
        reviews = self.ws / 'reviews'
        reviews.mkdir()
        write(reviews / 'watch.json', {'watch': [
            {'target': 'watching', 'state': 'watching', 'defs': str(self.defs)},
            {'target': 'reverted', 'state': 'rolled_back', 'defs': str(self.defs)}]})
        self.feed = {'changes': [{'target': 'reverted', 'state': 'rolled_back', 'reason': 'Gate failed.'}]}
        tree = node('root', 0, 'script', [node(str(self.root / 'external'), 999),
                    node('watching', 888), node('reverted', 777), node('d', 20)])
        self.measures = [measurement(tree)]
        review = self.run_round()
        self.assertEqual(review['target']['def'], 'd')
        self.assertEqual(review['action'], 'prescribe')
        self.assertEqual(review['tried'], [])
        self.assertEqual(review['consistency']['pass'], True)
        self.assertEqual([call[0] for call in self.calls], ['measure_0', 'watch_feed'])

    def test_no_agent_still_records_seven_steps_and_only_retires_after_three_rounds(self):
        self.definition('unused')
        self.definition('used')
        self.measures = [measurement(node('used', kind='script')) for _ in range(3)]
        for index in range(3):
            review = self.run_round()
            self.assertEqual(review['action'], 'none')
            self.assertEqual(len(review['steps']), 7)
            self.assertIsNone(review['proposed'])
            self.assertEqual(review['suggest']['retire'], ['unused'] if index == 2 else [])
        self.assertEqual(review['suggest']['specialize'], [])

    def test_baseline_uses_recent_three_before_unit_costs_and_spent_counts_every_repeat(self):
        self.definition('d')
        reviews = self.ws / 'reviews'
        for index, tokens in enumerate((900, 200, 300)):
            previous = reviews / ('2000-01-01T00-00-0%d.000Z' % index)
            previous.mkdir(parents=True)
            write(previous / 'review.json', {'before': cost(tokens), 'size_bytes': 100,
                                            'tree': node('d')})
        baseline, cheaper = measurement(tokens=100), measurement(tokens=50)
        self.measures = [baseline, cheaper]
        review = self.run_round()
        opened = next(args for name, args in self.calls if name == 'watch_open')
        self.assertEqual(opened['baseline'], 2)
        self.assertEqual(review['action'], 'downgrade')
        self.assertEqual(review['spent'], add_cost([cost(3), cost(100), cost(100),
                                                   cost(3), cost(50), cost(50)]))

    def test_busy_promotion_records_pending_without_opening_watch(self):
        self.definition('d')
        self.busy = True
        self.measures = [measurement(tokens=100), measurement(tokens=50)]
        review = self.run_round()
        self.assertEqual(review['action'], 'downgrade')
        self.assertEqual(review['pending_promote']['target'], 'd')
        self.assertIn('DefBusy', review['steps']['record']['error'])
        self.assertNotIn('watch_open', [name for name, _ in self.calls])


if __name__ == '__main__':
    unittest.main()
