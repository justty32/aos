# Verify exact forwarding of subprocess streams and status, pack errors, and child accounting.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-forward-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, PATH=str(self.root), AOS_LLM_KERNEL='/parent')
        self.body = {'endpoint': {'to': 'fake', 'kernel': '../child'},
                     'request': {'messages': [], 'extra': {'kept': True}},
                     'priority': {'level': 'high', 'deadline': 123.75, 'custom': [1,2]}}
        self.shim = self.root / 'aos-llm'
        self.python = os.path.realpath(os.sys.executable)

    def install(self, stdout='{"message":{},"letter":"abc","usage":{"x":2},"extra":[1]}\n', stderr='', code=0):
        self.shim.write_text('#!'+self.python+'\n# Capture the child request and return fixed bytes.\n'
            'import json,os,pathlib,sys\n'
            'pathlib.Path('+repr(str(self.root/'captured'))+').write_text(json.dumps({"body":json.load(sys.stdin),"kernel":os.environ["AOS_LLM_KERNEL"],"argv":sys.argv[1:]}))\n'
            'sys.stdout.buffer.write('+repr(stdout.encode())+')\n'
            'sys.stderr.buffer.write('+repr(stderr.encode())+')\n'
            'sys.exit('+repr(code)+')\n')
        self.shim.chmod(0o755)

    def run_entry(self, body=None, flags=()):
        return subprocess.run([self.python, str(ENTRY), *flags],
            input=json.dumps(self.body) if body is None else body, capture_output=True,
            text=True, env=self.env, timeout=5)

    def test_success_preserves_fields_priority_and_child_env(self):
        self.install()
        result = self.run_entry()
        self.assertEqual((result.returncode,result.stderr), (0,''))
        self.assertEqual(json.loads(result.stdout), {'message':{},'usage':{'x':2},'extra':[1],
                         'child':{'kernel':'../child','letter':'abc'}})
        captured = json.loads((self.root/'captured').read_text())
        self.assertEqual(captured, {'body':{'endpoint':'fake','request':self.body['request'],
            'priority':self.body['priority']}, 'kernel':'../child','argv':['ask','--full']})
        self.assertEqual(self.env['AOS_LLM_KERNEL'], '/parent')
        del self.body['priority']
        self.run_entry()
        self.assertNotIn('priority', json.loads((self.root/'captured').read_text())['body'])

    def test_downstream_failures_preserve_bytes_and_status(self):
        for code in (1,3,10,143):
            with self.subTest(code=code):
                stdout = '{"error": {"code":"X", "msg":"y"}}\n'
                stderr = 'aos-llm: warning: test\naos-llm: error: X y\n'
                self.install(stdout,stderr,code)
                result = self.run_entry()
                self.assertEqual((result.returncode,result.stdout,result.stderr), (code,stdout,stderr))

    def test_failure_streams_preserve_crlf_and_non_utf8_bytes(self):
        self.install('failure\r\n', 'detail\r\n', 3)
        # Write bytes directly to prove the forwarder does not decode the child streams.
        script = self.shim.read_text().replace("b'failure\\r\\n'", "b'failure\\xff\\r\\n'")
        self.shim.write_text(script)
        result = subprocess.run([self.python,str(ENTRY)],input=json.dumps(self.body).encode(),
                                capture_output=True,env=self.env,timeout=5)
        self.assertEqual((result.returncode,result.stdout,result.stderr),
                         (3,b'failure\xff\r\n',b'detail\r\n'))

    def test_bad_stdin_and_pack(self):
        for body in ('not JSON','[]','{}','{"endpoint":[]}'):
            with self.subTest(body=body):
                result = self.run_entry(body)
                self.assertEqual((result.returncode,result.stdout), (1,''))
                self.assertTrue(result.stderr.startswith('llm_forward: error: CfgBad '))
        for key in ('to','kernel'):
            original = self.body['endpoint'].pop(key)
            result = self.run_entry()
            self.assertEqual(result.stderr, 'llm_forward: error: CfgBad endpoint pack has no "'+key+'"\n')
            self.body['endpoint'][key] = original
            for value in (None,1,False,''):
                self.body['endpoint'][key] = value
                result = self.run_entry()
                self.assertEqual(result.returncode,1)
                self.assertIn(': error: CfgBad ',result.stderr)
            self.body['endpoint'][key] = original

    def test_launch_and_reply_errors(self):
        result = self.run_entry()
        self.assertIn(': error: LaunchFailed ',result.stderr)
        for reply in ('bad','[]','{}','{"letter":1}','{"letter":""}', '{\n"letter":"x"\n}'):
            with self.subTest(reply=reply):
                self.install(reply)
                result = self.run_entry()
                self.assertEqual((result.returncode,result.stdout), (1,''))
                self.assertIn(': error: ReplyBad ',result.stderr)

    def test_help(self):
        result = self.run_entry('', ['--help'])
        self.assertEqual((result.returncode,result.stderr), (0,''))
        self.assertIn('preserve stdout, stderr, and exit status',result.stdout)


if __name__ == '__main__':
    unittest.main()
