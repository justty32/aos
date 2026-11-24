# Verify ls exposes backend names in both the JSON window and the text columns.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[3] / 'bin/aos-llm'


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
                                                         'remote\tnormal\t-\t-\t-\t-\t-',
                                                         '# kernel: slots -, reserved for high -, in flight 0, queued 0'])

    def test_whole_kernel_line(self):
        with tempfile.TemporaryDirectory(prefix='aos-ls-whole-') as temp:
            root = Path(temp)
            for box, names in (('cur', ['a', 'b']), ('new', ['c', '.d-being-written']), ('tmp', ['e'])):
                for name in names:
                    (root/'requests'/box/name).mkdir(parents=True)
            (root/'requests'/'new'/'stray.txt').write_text('not a letter')
            (root/'endpoints.json').write_text(json.dumps({'fake':{'speed':'fast'}}))
            (root/'slots.json').write_text(json.dumps({'slots':4,'reserved':{'high':1}}))
            env = dict(os.environ,AOS_LLM_KERNEL=temp)
            result = subprocess.run([str(BIN),'ls'],env=env,capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.splitlines(), ['fake\tfast\t-\t-\t-\t-\t-',
                                                         '# kernel: slots 4, reserved for high 1, in flight 2, queued 1'])
            result = subprocess.run([str(BIN),'ls','--json'],env=env,capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(result.stdout), {'fake':{'speed':'fast'}})
            (root/'slots.json').write_text('not json')
            result = subprocess.run([str(BIN),'ls'],env=env,capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.splitlines()[-1], '# kernel: slots -, reserved for high -, in flight 2, queued 1')
