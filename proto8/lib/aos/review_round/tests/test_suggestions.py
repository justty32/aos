# Verify growth evidence, static references and measured per-node context medians.
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import round_runner as rr


def node(name, kind='agent', children=()):
    return {'def': name, 'kind': kind, 'children': list(children)}


class Suggestions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.defs = self.root / 'defs'
        for name in ('group/used', 'group/cold', 'solo/only'):
            path = self.defs / name
            path.mkdir(parents=True)
            (path / 'interfaces.json').write_text('{"aos-agent": {}}')
        self.rows = [{'path': name, 'brain': True, 'tools': ['read'], 'endpoint': 'low', 'knowledge': None}
                     for name in ('group/used', 'group/cold', 'solo/only')]

    def call(self, name, target, args):
        return {'defs_ls': {'defs': self.rows}, 'defs_dup': {'groups': [{'key': 'k', 'members': ['group/used', 'group/cold']}]},
                'defs_refs': {'refs': ['caller']}}[name]

    def test_retire_three_reviews_siblings_callers_and_singleton(self):
        old = {'tree': node('caller', children=[node('/lib/agent/subagent', 'script', [node('group/cold')])])}
        recent = [{'tree': node('group/used')} for _ in range(3)]
        rows = rr.retire(self.defs, [old] + recent, refs=lambda name: ['static'])
        self.assertEqual(rows, [{'def': 'group/cold', 'signal': 'unused_3_cases',
            'siblings_called': ['group/used'], 'callers': ['caller'], 'refs': ['static'], 'merge_into': None}])
        self.assertEqual(rr.retire(self.defs, recent[:2]), [])

    def test_bridge_signature_history_duplicates_and_context(self):
        tree = node('group/used', children=[node('/lib/agent/thought', 'script', [node('group/cold')])])
        reviews = [{'case': 'one', 'tree': tree}]
        with patch.object(rr, 'call', side_effect=self.call):
            rr.suggestions(self.defs, reviews, {})
            reviews.append({'case': 'two', 'tree': tree})
            tree['prompt_tokens_median'] = 14000
            result = rr.suggestions(self.defs, reviews, {})
            self.assertEqual([r['signal'] for r in result['specialize']], ['repeated_child', 'context_too_big'])
            self.assertIn('group/cold', result['specialize'][0]['existing'])
            self.assertIsNone(result['differentiate'][0]['same_duty'])
            self.assertIsNone(result['specialize'][1]['proposal'])
            tree['prompt_tokens_median'] = None
            self.rows[1]['endpoint'] = 'high'
            self.rows[1]['knowledge'] = 'new-knowledge'
            changed = rr.suggestions(self.defs, reviews, {})['specialize']
            self.assertEqual(changed[0]['signal'], 'repeated_child')
            self.assertEqual(changed[0]['proposal']['endpoint'], 'high')
            reviews[-1]['case'] = 'one'
            self.assertEqual(rr.suggestions(self.defs, reviews, {})['specialize'], [])
            reviews[-1]['case'] = 'two'
            self.rows[1]['tools'] = ['write']
            self.assertEqual(rr.suggestions(self.defs, reviews, {})['specialize'], [])

    def test_context_uses_current_node_medians_without_aggregating(self):
        tree = node('group/used', children=[node('group/cold')])
        reviews = [{'tree': tree}]
        with patch.object(rr, 'call', side_effect=self.call):
            for value in (None, 0, 10000, '14000', True):
                tree['prompt_tokens_median'] = value
                self.assertEqual(rr.suggestions(self.defs, reviews, {})['specialize'], [])
            tree['children'][0]['prompt_tokens_median'] = 10000.5
            result = rr.suggestions(self.defs, reviews, {})['specialize']
            self.assertEqual(result, [{'from': 'group/cold', 'signal': 'context_too_big',
                'evidence': {'prompt_tokens_median': 10000.5, 'max_prompt_tokens_median': 10000},
                'proposal': None, 'existing': None}])
            self.assertEqual(rr.suggestions(self.defs, reviews,
                {'max_prompt_tokens_median': 10001})['specialize'], [])
            tree['children'][0].pop('prompt_tokens_median')
            self.assertEqual(rr.suggestions(self.defs, reviews, {})['specialize'], [])


if __name__ == '__main__':
    unittest.main()
