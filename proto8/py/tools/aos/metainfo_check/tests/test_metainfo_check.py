# Verify cost verdicts, formula ratios, ledger extraction, and read-only tool errors.
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'
loader = importlib.machinery.SourceFileLoader('metainfo_check_entry', str(ENTRY))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)

    def run_check(self, claims, observations):
        meta = self.target / '_metainfo.json'
        if claims is not None:
            meta.write_text(json.dumps({'cost': claims}))
        before = {p.name: p.read_bytes() for p in self.target.iterdir()}
        result = module.check({'def': str(self.target), 'observed': observations})
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.target.iterdir()})
        self.assertTrue(result['checked_at'].endswith('Z'))
        return {r['key']: r for r in result['defs']}

    def test_design_examples(self):
        rows = self.run_check({'time_ms': 14750, 'token': {'in': 7004}},
                              [{'cost': {'time_ms': 20300, 'token': {'in': 7577}}}])
        self.assertEqual(rows['/token/in']['verdict'], 'close')
        self.assertEqual(rows['/time_ms']['verdict'], 'off')

    def test_large_mismatch_and_boundaries(self):
        for observed, verdict in [(1000, 'off'), (8, 'close'), (12.5, 'close'), (7.99, 'off')]:
            with self.subTest(observed=observed):
                rows = self.run_check({'time_ms': 10}, [{'cost': {'time_ms': observed}}])
                self.assertEqual(rows['/time_ms']['verdict'], verdict)

    def test_missing_metadata_and_unknown_evaluator(self):
        rows = self.run_check(None, [{'cost': {'time_ms': 2}}])
        self.assertEqual(rows['/time_ms']['verdict'], 'unclaimed')
        rows = self.run_check({'token': {'in': {'lua': '1'}}}, [{'cost': {'token': {'in': 0}}}])
        self.assertEqual(rows['/token/in']['verdict'], 'unclaimed')

    def test_formula_median_of_ratios_not_ratio_of_medians(self):
        rows = self.run_check({'time_ms': {'cal': 'in_bytes'}}, [
            {'in_bytes': 1, 'cost': {'time_ms': 1}},
            {'in_bytes': 10, 'cost': {'time_ms': 100}},
            {'in_bytes': 100, 'cost': {'time_ms': 110}}])
        self.assertAlmostEqual(rows['/time_ms']['ratio'], 1.1)
        self.assertEqual(rows['/time_ms']['verdict'], 'close')

    def test_samples_do_not_double_count_aggregate_or_tree(self):
        rows = self.run_check({'time_ms': 10}, [{'cost': {'time_ms': 1000},
            'tree': {'def': str(self.target), 'cost': {'time_ms': 1000}},
            'samples': [{'cost': {'time_ms': 10}}, {'cost': {'time_ms': 10}}]}])
        self.assertEqual(rows['/time_ms']['ratio'], 1)

    def test_observed_ledger_and_other_definitions(self):
        rows = self.run_check({'time_ms': 10, 'token': {'in': 7004}}, [
            {'kind': 'self', 'def': str(self.target)},
            {'kind': 'think', 'usage': {'prompt_tokens': 7577}},
            {'kind': 'tool', 'def': str(self.target), 'elapsed_ms': 10, 'in_bytes': 2},
            {'kind': 'tool', 'def': '/elsewhere', 'elapsed_ms': 9999}])
        self.assertEqual(rows['/time_ms']['ratio'], 1)
        self.assertEqual(rows['/token/in']['observed'], 7577)

    def test_tree_selects_matching_definition(self):
        rows = self.run_check({'time_ms': 10}, [{'tree': {
            'def': '/elsewhere', 'cost': {'time_ms': 999}, 'children': [
                {'def': str(self.target), 'cost': {'time_ms': 10}}]}}])
        self.assertEqual(rows['/time_ms']['observed'], 10)

    def test_cmd_rows_are_ignored(self):
        rows = self.run_check({'time_ms': 10}, [
            {'kind': 'cmd', 'elapsed_ms': 9999, 'argv': ['echo', 'hello']},
            {'kind': 'tool', 'def': str(self.target), 'elapsed_ms': 10}])
        self.assertEqual(rows['/time_ms']['ratio'], 1)

    def test_self_rows_split_think_samples(self):
        rows = self.run_check({'token': {'in': 10}}, [
            {'kind': 'self', 'def': str(self.target)},
            {'kind': 'think', 'usage': {'prompt_tokens': 4}},
            {'kind': 'think', 'usage': {'prompt_tokens': 6}},
            {'kind': 'self', 'def': '/elsewhere'},
            {'kind': 'think', 'usage': {'prompt_tokens': 9999}},
            {'kind': 'self', 'def': str(self.target)},
            {'kind': 'think', 'usage': {'prompt_tokens': 12}}])
        self.assertEqual(rows['/token/in']['observed'], 11)
        self.assertAlmostEqual(rows['/token/in']['ratio'], 1.1)

    def test_tree_input_size_overrides_sample_size(self):
        rows = self.run_check({'time_ms': {'cal': 'in_bytes'}}, [
            {'in_bytes': 999, 'samples': [{'in_bytes': 500, 'tree': {
                'def': '/elsewhere', 'in_bytes': 200, 'cost': {'time_ms': 999},
                'children': [{'def': str(self.target), 'in_bytes': 10,
                              'cost': {'time_ms': 10}}]}}]}])
        self.assertEqual(rows['/time_ms']['claimed'], 10)
        self.assertEqual(rows['/time_ms']['ratio'], 1)

    def test_zero_estimate(self):
        for value, verdict, ratio in [(0, 'close', 1), (1, 'off', None)]:
            rows = self.run_check({'time_ms': 0}, [{'cost': {'time_ms': value}}])
            self.assertEqual(rows['/time_ms']['verdict'], verdict)
            self.assertEqual(rows['/time_ms']['ratio'], ratio)

    def test_invalid_inputs_exit_with_shared_error(self):
        for value in [{}, {'def': str(self.target), 'observed': []},
                      {'def': str(self.target), 'observed': [1]},
                      {'def': str(self.target), 'observed': [{'cost': {'time_ms': -1}}]}]:
            result = subprocess.run([sys.executable, str(ENTRY)], input=json.dumps(value),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('error: ArgumentsBad', result.stderr)
            self.assertEqual(result.stdout, result.stderr)

    def test_bad_claims_are_skipped_with_notes(self):
        """壞的宣稱＝當沒宣稱（unclaimed），頂層 notes 說略過了什麼；沒略過就沒有 notes。"""
        observed = [{'cost': {'time_ms': 1, 'token': {'in': 2}}}]
        for claims in ({'time_ms': {'cal': 'in_bytes'}}, {'time_ms': 'soon'}, {'time_ms': -5},
                       {'time_ms': {'cal': '1 -'}}):
            with self.subTest(claims=claims):
                (self.target / '_metainfo.json').write_text(json.dumps({'cost': claims}))
                result = module.check({'def': str(self.target), 'observed': observed})
                rows = {r['key']: r for r in result['defs']}
                self.assertEqual(rows['/time_ms']['verdict'], 'unclaimed')
                self.assertIsNone(rows['/time_ms']['claimed'])
                self.assertEqual(len(result['notes']), 1, result['notes'])
        for meta in ('{', json.dumps({'cost': 5}), json.dumps({'cost': {'token': 3}}), '[]'):
            with self.subTest(meta=meta):
                (self.target / '_metainfo.json').write_text(meta)
                result = module.check({'def': str(self.target), 'observed': observed})
                self.assertEqual({r['verdict'] for r in result['defs']}, {'unclaimed'})
                self.assertTrue(result['notes'])
        rows = self.run_check({'time_ms': {'cal': 'in_bytes'}},     # 一個樣本算不出＝整格不算，不混著前面算出的
                              [{'in_bytes': 5, 'cost': {'time_ms': 5}}, {'cost': {'time_ms': 5}}])
        self.assertEqual(rows['/time_ms']['verdict'], 'unclaimed')
        (self.target / '_metainfo.json').write_text(json.dumps({'cost': {'time_ms': 1}}))
        self.assertNotIn('notes', module.check({'def': str(self.target), 'observed': observed}))

    def test_bad_metadata_runs_through_the_tool(self):
        (self.target / '_metainfo.json').write_text('{')
        result = subprocess.run([sys.executable, str(ENTRY)], text=True, capture_output=True,
                                input=json.dumps({'def': str(self.target), 'observed': [{'cost': {'time_ms': 1}}]}))
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out['defs'][0]['verdict'], 'unclaimed')
        self.assertIn('skipped', out['notes'][0])


if __name__ == '__main__':
    unittest.main()
