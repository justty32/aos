# Verify batch four acceptance cases through the real measure and metadata tools.
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import unittest

MEASURE = Path(__file__).resolve().parents[1]
PROTO = MEASURE.parents[2]


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aos-batch4-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('AOS_')}
        bins = [str(p) for group in ('impls', 'cmd') for p in (PROTO / group).glob('*/bin')]
        self.env.update(PATH=os.pathsep.join(bins + [self.env['PATH']]),
                        PYTHONPATH=str(PROTO / 'lib'), AOS_WS=str(self.root),
                        AOS_STACK=str(self.root / 'stack'))

    def measure(self, case, repeat=3, **extra):
        result = subprocess.run(['aos-exec', str(MEASURE), '--repeat', str(repeat)],
            input=json.dumps({'case': str(case), 'defs': str(PROTO), **extra}),
            capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def tool(self, name, source):
        target = self.root / name
        target.mkdir()
        entry = target / '_entry'
        entry.write_text('#!/usr/bin/env python3\n# Run a local acceptance fixture.\n' + source)
        entry.chmod(0o755)
        return target

    def case(self, target):
        case = self.root / 'case'
        case.mkdir()
        (case / 'run.json').write_text(json.dumps({'exec': str(target), 'stdin': 'stdin.json'}))
        (case / 'stdin.json').write_text('{}\n')
        return case

    def test_smoke_suite_and_wrong_answer(self):
        smoke = self.root / 'smoke'
        shutil.copytree(PROTO / 'cases/smoke', smoke)
        result = self.measure(smoke)
        self.assertTrue(result['check']['pass'])
        self.assertEqual(result['consistency'], {'scores': [1.0, 1.0], 'pass': True})
        self.assertEqual(len(result['samples']), 3)
        self.assertEqual(len(result['cases']), 2)
        self.assertEqual(result['cost']['time_ms'],
                         statistics.median(s['cost']['time_ms'] for s in result['samples']))
        self.assertEqual(result['tree']['cost']['time_ms'],
                         sum(c['cost']['time_ms'] for c in result['tree']['children']))
        self.assertEqual(result['size_bytes'], sum(p.stat().st_size for p in smoke.glob('*/stdin.json')))
        self.assertTrue(all('check' in s and 'code' in s for s in result['samples']))
        (smoke / 'addition/expect/stdout.json').write_bytes(b'43\n')
        wrong = self.measure(smoke)
        self.assertFalse(wrong['check']['pass'])
        self.assertEqual(wrong['check']['diff'], ['addition/stdout.json'])
        self.assertTrue(wrong['consistency']['pass'])

    def test_custom_comparator_cost_is_separate(self):
        comparator = self.tool('compare_half',
            'import json, os, observed\n'
            'args=json.load(__import__("sys").stdin)\n'
            'assert all(os.path.isabs(args[k]) for k in ("expect", "got", "input"))\n'
            'observed.append_strict(os.environ["AOS_STACK"], {"kind":"think",'
            '"endpoint":"fake-account", "usage":{"prompt_tokens":5,"completion_tokens":2}})\n'
            'print(json.dumps({"score":0.5,"diff":["stdout.json"],"why":"Fixed fixture score."}))\n')
        result = self.measure(PROTO / 'cases/smoke/addition',
                              check={'compare': str(comparator), 'min_score': 0.6})
        self.assertFalse(result['check']['pass'])
        self.assertEqual(result['check']['scores'], [0.5, 0.5, 0.5])
        self.assertEqual(result['cost']['token']['in'], 0)
        self.assertEqual(result['cost']['counter_calls'], 0)
        # Three answer checks plus two consistency comparisons each cost five tokens.
        self.assertEqual(result['check']['cost']['token']['in'], 25)
        self.assertEqual(result['check']['cost']['counter_calls'], 5)
        self.assertGreater(result['check']['cost']['time_ms'], 0)
        self.assertEqual(result['samples'][0]['check']['why'], 'Fixed fixture score.')

    def test_timestamp_and_fixed_output_consistency(self):
        target = self.tool('clock_output', 'import time\nprint(time.time_ns())\n')
        case = self.case(target)
        changing = self.measure(case)
        self.assertFalse(changing['consistency']['pass'])
        self.assertEqual(changing['consistency']['scores'], [0.0, 0.0])
        (target / '_entry').write_text('#!/usr/bin/env python3\n# Return a stable fixture answer.\nprint("fixed")\n')
        stable = self.measure(case)
        self.assertTrue(stable['check']['pass'])
        self.assertEqual(stable['consistency'], {'scores': [1.0, 1.0], 'pass': True})
        once = self.measure(case, repeat=1)
        self.assertNotIn('consistency', once)

    def test_measure_input_bytes_reach_metadata_formula(self):
        target = self.tool('claimed',
            'import os, observed\n'
            'observed.append_strict(os.environ["AOS_STACK"], {"kind":"think",'
            '"endpoint":"fake-account", "usage":{"prompt_tokens":3,"completion_tokens":0}})\n'
            'print("fixed")\n')
        (target / '_metainfo.json').write_text(json.dumps({'cost': {'token': {'in': {'cal': 'in_bytes'}}}}))
        result = self.measure(self.case(target), repeat=2)
        checked = subprocess.run(['aos-exec', str(PROTO / 'lib/aos/metainfo_check')],
            input=json.dumps({'def': str(target), 'observed': [result]}),
            capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        row = next(r for r in json.loads(checked.stdout)['defs'] if r['key'] == '/token/in')
        self.assertEqual((row['claimed'], row['observed'], row['ratio'], row['verdict']),
                         (3, 3, 1, 'close'))


if __name__ == '__main__':
    unittest.main()
