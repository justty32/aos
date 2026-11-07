# Verify boxed and open definitions through actual sandbox and measure boundaries.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
BOXED = ROOT / 'cmd/aos-sandbox/examples/bash-boxed'
CASE = ROOT / 'cases/box-probe'
CHECK = ROOT / 'lib/aos/box_check'


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('AOS_')}
        bins = [str(path) for group in ('impls', 'cmd') for path in (ROOT / group).glob('*/bin')]
        s6 = Path.home() / 'code/try/sandbox/s6-root/bin'
        self.env['PATH'] = os.pathsep.join(bins + [str(s6), self.env['PATH']])
        self.env['PYTHONPATH'] = str(ROOT / 'lib')
        self.env['AOS_WS'] = str(self.root / 'ws')
        self.env['AOS_STACK'] = str(self.root / 'stack/tools/bash')
        Path(self.env['AOS_WS']).mkdir()
        Path(self.env['AOS_STACK']).mkdir(parents=True)

    def call(self, target, args):
        return subprocess.run(['aos-exec', str(target)], input=json.dumps(args),
                              text=True, capture_output=True, env=self.env, timeout=40)

    def test_real_boxed_whitelist_and_writes(self):
        rg = self.call(BOXED, {'command': 'rg --version'})
        self.assertEqual(rg.returncode, 0, rg.stderr)
        self.assertIn('ripgrep', rg.stdout)
        self.assertTrue(rg.stdout.rstrip().endswith('[exit code 0]'), rg.stdout)
        curl = self.call(BOXED, {'command': 'curl --version'})
        self.assertEqual(curl.returncode, 0, curl.stderr)
        self.assertTrue(curl.stdout.rstrip().endswith('[exit code 127]'), curl.stdout)
        write = self.call(BOXED, {'command': 'echo x > "$AOS_WS/x"'})
        self.assertEqual(write.returncode, 0, write.stderr)
        self.assertTrue(write.stdout.rstrip().endswith('[exit code 0]'), write.stdout)
        self.assertEqual((self.root / 'ws/x').read_text(), 'x\n')
        records = [json.loads(line) for line in (Path(self.env['AOS_STACK']) / 'observed.jsonl').read_text().splitlines()]
        self.assertTrue(any(row['kind'] == 'cmd' for row in records))

    def measure(self, tool):
        defs = self.root / 'defs'
        (defs / 'tools').mkdir(parents=True)
        (defs / 'tools/bash').symlink_to(tool, target_is_directory=True)
        result = self.call(ROOT / 'lib/aos/measure', {'case': str(CASE), 'defs': str(defs), 'check': {'compare': str(CHECK)}})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_measure_boxed_passes(self):
        result = self.measure(BOXED)
        self.assertTrue(result['check']['pass'], result)
        self.assertFalse(Path('/tmp/aos-box-probe').exists())

    def test_measure_open_fails_and_cleans_escape(self):
        result = self.measure(ROOT / 'lib/base/bash')
        self.assertFalse(result['check']['pass'], result)
        self.assertFalse(Path('/tmp/aos-box-probe').exists())

    def test_comparator_rejects_missing_markers_and_extra_binaries(self):
        meta = json.loads((BOXED / '_metainfo.json').read_text())
        allowed = {path for path in meta['sandbox']['ro'] if path.startswith('/usr/bin/')}
        allowed.update(str(Path(path).resolve()) for path in list(allowed))
        history = self.root / 'stack/history.jsonl'
        probe_path = self.env['AOS_STACK'] + '/../../history.jsonl'
        output = 'P5 ' + probe_path + '\nR1 0\nR2 1\nR3 0\nR4 0\nR5 1\nH /etc\n' + ''.join('B ' + path + '\n' for path in sorted(allowed))
        got = self.root / 'got'
        got.mkdir()
        for text, score in ((output, 1), (output.replace('R2 1\n', ''), 0), (output + 'B /usr/bin/curl\n', 0), (output.replace('R5 1', 'R5 0'), 1), (output.replace('P5 ' + probe_path + '\n', ''), 0), (output + 'P5 ' + probe_path + '\n', 0)):
            (got / 'stdout.json').write_text(text)
            result = self.call(CHECK, {'expect': str(got), 'got': str(got), 'input': str(CASE)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['score'], score)
        history.write_text('escaped\n')
        (got / 'stdout.json').write_text(output)
        result = self.call(CHECK, {'expect': str(got), 'got': str(got), 'input': str(CASE)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['score'], 0)
        self.assertFalse(history.exists())

    def test_declaration_and_pointer(self):
        entry = json.loads((BOXED / '_entry').read_text())
        self.assertEqual(entry, ['aos-sandbox', '_metainfo.json#/sandbox', 'aos-exec', 'inner'])
        meta = json.loads((BOXED / '_metainfo.json').read_text())
        self.assertEqual(meta['sandbox']['commands'], ['aos-exec'])
        self.assertNotIn('/usr/bin', meta['sandbox']['base'])
        self.assertFalse((BOXED / 'sandbox.json').exists())
        result = subprocess.run(['aos-sandbox', '--dry-run', str(BOXED / '_metainfo.json') + '#/sandbox', 'true'],
                                cwd=BOXED, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('bwrap', result.stdout)


if __name__ == '__main__':
    unittest.main()
