# Verify ls exposes backend names in both the JSON window and the text columns.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin/aos-llm'


class BackendWindow(unittest.TestCase):
    def test_backend_column_and_absent_value(self):
        with tempfile.TemporaryDirectory(prefix='aos-ls-backend-') as temp:
            root = Path(temp)
            (root/'requests').mkdir()
            window = {'local':{'speed':'fast','backend':'lmstudio','summary':'local model'},
                      'remote':{'speed':'normal'}}
            (root/'endpoints.json').write_text(json.dumps(window))
            env = dict(os.environ,AOS_LLM_KERNEL=temp)
            result = subprocess.run([str(BIN),'ls','--json'],env=env,capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(result.stdout),window)
            result = subprocess.run([str(BIN),'ls'],env=env,capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.splitlines(), ['local\tfast\t-\t-\t-\tlmstudio\tlocal model',
                                                         'remote\tnormal\t-\t-\t-\t-\t-'])
