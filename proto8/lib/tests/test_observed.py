# Verify shared observation initialization, strict failures and measured call cells.
import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import observed


class Observed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name) / 'stack'

    def records(self):
        return [json.loads(line) for line in (self.stack / 'observed.jsonl').read_text().splitlines()]

    def test_self_once_and_declaration_merge(self):
        self.stack.mkdir()
        (self.stack / 'interfaces.json').write_text('{"custom":{"file":"data"}}')
        with patch.dict(os.environ, {'AOS_CD':'/def', 'AOS_WS':'/ws', 'AOS_LLM_KERNEL':'/kernel'}):
            observed.append_strict(self.stack, {'kind':'think'})
            observed.append_strict(self.stack, {'kind':'tool'})
        rows = self.records()
        self.assertEqual([r['kind'] for r in rows], ['self', 'think', 'tool'])
        self.assertEqual(rows[0]['llm_kernel'], '/kernel')
        self.assertRegex(rows[0]['started_at'], r'\.\d{3}Z$')
        declaration = json.loads((self.stack / 'interfaces.json').read_text())
        self.assertEqual(declaration['custom'], {'file':'data'})
        self.assertEqual(declaration['aos-observed'], {'file':'observed.jsonl'})

    def test_self_without_kernel_omits_key(self):
        with patch.dict(os.environ, {}, clear=True):
            observed.append_strict(self.stack, {'kind': 'think'})
        self.assertNotIn('llm_kernel', self.records()[0])

    def test_real_exec_preserves_two_level_ledgers_and_raw_bytes(self):
        lib = Path(__file__).resolve().parents[1]
        binary = lib.parent / 'impls/aos-exec/bin/aos-exec'
        self.assertTrue(binary.is_file(), 'build aos-exec before running this integration test')
        root = Path(self.tmp.name)
        child = root / 'child.py'
        child.write_text('#!' + sys.executable + '\n'
                         '# Record a child observation and return raw output with a failure code.\n'
                         'import os, sys, observed\n'
                         'payload = sys.stdin.buffer.read()\n'
                         'observed.append_strict(os.environ["AOS_STACK"], {"kind":"cmd", "exit":7})\n'
                         'sys.stdout.buffer.write(payload + b"\\x00out")\n'
                         'sys.stderr.buffer.write(b"raw\\xfferr")\n'
                         'sys.exit(7)\n')
        child.chmod(0o755)
        parent = root / 'parent.py'
        parent.write_text('#!' + sys.executable + '\n'
                          '# Call the child through the shared observation API and forward its result.\n'
                          'import sys, observed\n'
                          'code, out, err = observed.call("child", sys.argv[1], sys.stdin.buffer.read())\n'
                          'sys.stdout.buffer.write(out)\n'
                          'sys.stderr.buffer.write(err)\n'
                          'sys.exit(code)\n')
        env = dict(os.environ, AOS_STACK=str(self.stack), AOS_CD=str(root), AOS_WS=str(root),
                   PATH=str(binary.parent) + os.pathsep + os.environ['PATH'], PYTHONPATH=str(lib))
        payload = '雪'.encode() + b'\x00'
        result = subprocess.run([sys.executable, str(parent), str(child)], input=payload,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (7, payload + b'\x00out', b'raw\xfferr'))
        row = self.records()[-1]
        self.assertEqual((row['code'], row['in_bytes'], row['out_bytes']),
                         (7, len(payload), len(result.stdout)))
        child_stack = self.stack / row['stack']
        declaration = json.loads((child_stack / 'interfaces.json').read_text())
        child_rows = [json.loads(line) for line in
                      (child_stack / declaration['aos-observed']['file']).read_text().splitlines()]
        self.assertEqual([row['kind'] for row in child_rows], ['self', 'cmd'])
        self.assertEqual(child_rows[-1]['exit'], 7)

    def test_relative_stack_is_absolute_in_child_environment(self):
        with patch('observed.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b''
            run.return_value.stderr = b''
            relative = os.path.relpath(self.stack)
            observed.call('echo', '/target', b'', stack=relative)
        self.assertEqual(run.call_args.kwargs['env']['AOS_STACK'], str(self.stack / 'tools/echo'))

    def test_strict_failure_and_best_effort_warning(self):
        self.stack.mkdir()
        (self.stack / 'observed.jsonl').mkdir()
        with self.assertRaises(OSError):
            observed.append_strict(self.stack, {'kind':'tool'})
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            observed.append(self.stack, {'kind':'tool'})
        self.assertIn('warning: cannot append', errors.getvalue())

    def test_call_bytes_environment_and_no_stack(self):
        fake = Path(self.tmp.name) / 'aos-exec'
        fake.write_text('#!' + sys.executable + '\nimport os,sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\nsys.stderr.write(os.environ.get("AOS_STACK", ""))\nsys.exit(7)\n')
        fake.chmod(0o755)
        with patch.dict(os.environ, {'PATH': self.tmp.name + os.pathsep + os.environ['PATH']}):
            code, out, err = observed.call('echo', '/target', '雪', stack=str(self.stack))
            self.assertEqual((code, out), (7, '雪'.encode()))
            self.assertEqual(err.decode(), str(self.stack / 'tools/echo'))
            row = self.records()[-1]
            self.assertEqual((row['def'], row['stack'], row['in_bytes']), ('/target', 'tools/echo', 3))
            with patch.dict(os.environ, {}, clear=True):
                os.environ['PATH'] = self.tmp.name
                self.assertEqual(observed.call('echo', '/target', b'x')[1], b'x')


if __name__ == '__main__':
    unittest.main()
