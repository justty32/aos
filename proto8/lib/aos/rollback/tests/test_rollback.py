# Verify rollback without a previous version leaves the definition unchanged.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[4]


class RollbackAcceptance(unittest.TestCase):
    def test_previous_version_missing_preserves_definition(self):
        with tempfile.TemporaryDirectory(prefix='aos-rollback-', dir='/tmp') as tmp:
            root = Path(tmp)
            (root / 'd').mkdir()
            payload = b'original\x00\xff\n'
            (root / 'd/data').write_bytes(payload)
            env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
            env['PATH'] = str(PROTO / 'impls/aos-exec/bin') + os.pathsep + env['PATH']
            env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
            result = subprocess.run(['aos-exec', str(PROTO / 'lib/aos/rollback')],
                                    input=json.dumps({'defs': str(root), 'target': 'd'}),
                                    env=env, cwd=root, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('PrevMissing', result.stderr)
            self.assertEqual(result.stdout.strip(), result.stderr.strip())
            self.assertEqual((root / 'd/data').read_bytes(), payload)
            self.assertFalse((root / '.prev').exists())


if __name__ == '__main__':
    unittest.main()
