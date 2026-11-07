# Verify new agent births preserve metadata and record literal lineage arguments.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / '_entry'


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.template = self.root / 'template'
        self.template.mkdir()
        (self.template / 'interfaces.json').write_text('{"aos-agent": {}}')
        (self.template / '_metainfo.json').write_text(json.dumps({
            'summary': 'Copied definition', 'cost': {'time_ms': 42},
            'custom': {'keep': True}, 'lineage': {'from': 'old', 'review': 'old'}}))
        (self.root / 'alias').symlink_to(self.template, target_is_directory=True)
        binary = self.root / 'aos-agent'
        binary.write_text('''#!/usr/bin/env python3
# Provide a local daemon command fixture for birth tests.
import json, os, sys
args = sys.argv[3:]
if args[:2] == ['ctl', 'ls']:
    print('[]')
elif args[:2] == ['ctl', 'who']:
    print('{}')
elif args[:2] == ['ctl', 'add']:
    print(os.path.join(os.environ['AOS_DAEMON'], 'kid'))
else:
    sys.exit(2)
''')
        binary.chmod(0o755)
        self.env = dict(os.environ, AOS_WS=str(self.root),
                        AOS_DAEMON=str(self.root / 'daemon'),
                        AOS_STACK=str(self.root / 'stack'),
                        PATH=str(self.root) + os.pathsep + os.environ['PATH'])

    def run_new(self, **changes):
        args = {'op': 'new', 'name': 'kid', 'path': 'born', 'from': './alias/../alias'}
        args.update(changes)
        return subprocess.run([sys.executable, str(SOURCE)], input=json.dumps(args),
                              text=True, capture_output=True, env=self.env, timeout=10)

    def metadata(self):
        return json.loads((self.root / 'born' / '_metainfo.json').read_text())

    def test_default_reason_preserves_literal_source_and_other_metadata(self):
        original = (self.template / '_metainfo.json').read_bytes()
        result = self.run_new()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.metadata(), {'summary': 'Copied definition', 'cost': {'time_ms': 42},
                                          'custom': {'keep': True},
                                          'lineage': {'from': './alias/../alias', 'reason': 'manual'}})
        self.assertEqual((self.template / '_metainfo.json').read_bytes(), original)

    def test_explicit_reason_review_and_files_metadata(self):
        for reason in ['specialize', 'split', 'fix', 'manual']:
            with self.subTest(reason=reason):
                result = self.run_new(path=reason, reason=reason, review='./reviews/../review.json',
                                      files={'_metainfo.json': '{"summary":"Override","timeout_ms":99}'})
                self.assertEqual(result.returncode, 0, result.stderr)
                meta = json.loads((self.root / reason / '_metainfo.json').read_text())
                self.assertEqual(meta, {'summary': 'Override', 'timeout_ms': 99,
                    'lineage': {'from': './alias/../alias', 'reason': reason,
                                'review': './reviews/../review.json'}})

    def test_files_only_creates_metadata_with_null_source(self):
        result = self.run_new(**{'from': None, 'files': {'README.md': 'New definition\n'}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.metadata(), {'lineage': {'from': None, 'reason': 'manual'}})

    def test_absolute_source_is_preserved(self):
        source = str(self.root / 'alias')
        result = self.run_new(**{'from': source})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.metadata()['lineage']['from'], source)

    def test_invalid_birth_fields_fail_before_daemon_call(self):
        for changes in [{'reason': 'downgrade'}, {'reason': []},
                        {'review': 3}, {'review': {}}]:
            with self.subTest(changes=changes):
                result = self.run_new(**changes)
                self.assertEqual(result.returncode, 1)
                self.assertIn('error: ArgumentsBad ', result.stdout)
                self.assertFalse((self.root / 'born').exists())

    def test_invalid_metadata_is_rejected_and_temporary_copy_removed(self):
        result = self.run_new(files={'_metainfo.json': '[]'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('error: DefBad ', result.stdout)
        self.assertFalse((self.root / 'born').exists())
        self.assertEqual(list(self.root.glob('.born.new-*')), [])


if __name__ == '__main__':
    unittest.main()
