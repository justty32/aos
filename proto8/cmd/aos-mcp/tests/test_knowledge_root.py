# Verify aos-mcp --knowledge NAME: a knowledge base given = its root in the initialize instructions; none given (KnowledgeMissing) = quiet; given but not a folder = warning (11-10 tool-packs).
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
MCP = PROTO / 'cmd' / 'aos-mcp' / 'bin' / 'aos-mcp'
READER = PROTO / 'lib' / 'agent' / 'knowledge_read'


class KnowledgeRoot(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-knowledge-'))
        self.kb = self.root / 'kb'
        self.kb.mkdir()
        (self.kb / '_description.json').write_text(json.dumps('Test knowledge. Read notes/ first.'))
        (self.kb / '_index.json').write_text('{}')
        self.reg = self.root / 'tools.json'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['PATH'] = os.pathsep.join([str(PROTO / 'cmd' / 'aos-tools' / 'bin'), os.path.expanduser('~/.local/bin'),
                                            self.env['PATH']])

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def initialize(self, env):
        cell = {'path': str(READER)}
        if env is not None:
            cell['env'] = {'AOS_KNOWLEDGE': env}
        self.reg.write_text(json.dumps({'tools': {'knowledge_read': cell}}))
        stdin = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n'
        r = subprocess.run([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), '--knowledge', 'knowledge_read', str(self.reg)],
                           input=stdin, capture_output=True, text=True, timeout=30, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        reply = json.loads(r.stdout.splitlines()[0])
        return reply['result'].get('instructions'), r.stderr

    def test_given(self):
        text, err = self.initialize(str(self.kb))
        self.assertIn('Test knowledge. Read notes/ first.', text)
        self.assertEqual(err, '')

    def test_not_given_is_quiet(self):
        text, err = self.initialize(None)
        self.assertIsNone(text)
        self.assertEqual(err, '')

    def test_not_a_folder_warns(self):
        text, err = self.initialize(str(self.root / 'nope'))
        self.assertIsNone(text)
        self.assertIn('aos-mcp: warning: --knowledge knowledge_read', err)


if __name__ == '__main__':
    unittest.main()
