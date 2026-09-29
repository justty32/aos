import os
import signal
import subprocess
from support import Case, BIN, ENV, write_json
from aosproto.common import Fault, read_inst
from aosproto.inst import validate
from aosproto.runner import run_snapshot


class Runner(Case):
    def test_exit_file(self):
        report = self.inst({'argv': ['sh', '-c', 'exit 7'], 'exit': 'result'}, code=7)
        self.assertEqual(report, {'started': True, 'exit_code': 7})
        self.assertEqual((self.path / 'result').read_text(), '7\n')

    def test_append_mkdir_streams_exit(self):
        obj = {'argv': ['sh', '-c', 'cat; echo error >&2'], 'stdin': 'in',
               'stdout': {'$opt': ['mkdir', 'append'], '$val': 'out/result'},
               'stderr': {'$opt': 'merge'}, 'exit': {'$opt': ['mkdir', 'append'], '$val': 'out/exit'}}
        (self.path / 'in').write_text('input\n')
        self.inst(obj)
        self.inst(obj)
        self.assertEqual((self.path / 'out/result').read_text(), 'input\nerror\n' * 2)
        self.assertEqual((self.path / 'out/exit').read_text(), '0\n0\n')

    def test_cwd_mkdir_environment_clear(self):
        self.inst({'argv': ['sh', '-c', 'printf "%s" "$VALUE" > result; test -z "$HOME"'],
                   'cwd': {'$opt': 'mkdir', '$val': 'sub'},
                   'envs': {'$opt': 'clear', '$val': {'VALUE': 'literal value'}}})
        self.assertEqual((self.path / 'sub/result').read_text(), 'literal value')

    def test_environment_overlay(self):
        self.inst({'argv': ['sh', '-c', 'test -n "$PATH"; printf "%s" "$VALUE" > env'],
                   'envs': {'VALUE': 'yes'}})
        self.assertEqual((self.path / 'env').read_text(), 'yes')

    def test_stderr_override(self):
        self.inst({'argv': ['sh', '-c', 'echo yes >&2'], 'stderr': {'$opt': 'merge'}},
                  stderr=self.path / 'diagnostic')
        self.assertEqual((self.path / 'diagnostic').read_text(), 'yes\n')

    def test_inherit(self):
        file = self.path / 'job.json'
        write_json(file, {'argv': ['cat'], 'stdin': {'$opt': 'inherit'}, 'stdout': {'$opt': 'inherit'}})
        result = self.cli('run', file, input='hello\n')
        self.assertEqual(result.stdout, 'hello\n')
        self.cli('run', file, '--json', code=2)

    def test_127(self):
        result = self.inst({'argv': ['aos-no-such-executable'], 'exit': 'exit'}, code=127)
        self.assertTrue(result['started'])
        self.assertEqual((self.path / 'exit').read_text(), '127\n')

    def test_126(self):
        program = self.path / 'non-executable'
        program.write_text('hello')
        result = self.inst({'argv': [str(program)], 'exit': 'exit'}, code=126)
        self.assertTrue(result['started'])
        self.assertEqual((self.path / 'exit').read_text(), '126\n')

    def test_signal(self):
        result = self.inst({'argv': ['sh', '-c', 'kill -TERM $$'], 'exit': 'exit'}, code=143)
        self.assertEqual(result['signal'], 15)
        self.assertEqual((self.path / 'exit').read_text(), '143\n')

    def test_timeout(self):
        result = self.inst({'argv': ['sleep', '60'], 'exit': 'exit'}, code=143, timeout_ms=50)
        self.assertEqual(result['signal'], signal.SIGTERM)

    def test_timeout_ignores_term(self):
        result = self.inst({'argv': ['sh', '-c', 'trap "" TERM; exec sleep 60']}, code=137, timeout_ms=100)
        self.assertEqual(result['signal'], signal.SIGKILL)

    def test_unauthorized_no_exit(self):
        result = self.inst({'argv': ['true'], 'user': os.getuid() + 1, 'exit': 'exit'}, code=125)
        self.assertFalse(result['started'])
        self.assertEqual(result['error']['code'], 'UserNotGranted')
        self.assertFalse((self.path / 'exit').exists())

    def test_preflight_errors(self):
        cases = [([], 'NotAnObject'), ({}, 'EmptyArgv'), ({'argv': []}, 'EmptyArgv'),
                 ({'argv': ['']}, 'EmptyArgv'), ({'argv': 'true'}, 'FieldTypeMismatch'),
                 ({'argv': ['true'], '_metainfo': {}}, 'MetainfoInvalid'),
                 ({'argv': ['true'], '_metainfo': {'_type': 'other', '_version': 1}}, 'UnsupportedInstType'),
                 ({'argv': ['true'], '_metainfo': {'_type': 'posix', '_version': True}}, 'UnsupportedInstVersion'),
                 ({'argv': ['true'], 'envs': {'': 'x'}}, 'EnvKeyInvalid'),
                 ({'argv': ['true'], 'envs': {'A=B': 'x'}}, 'EnvKeyInvalid'),
                 ({'argv': ['true'], 'stdout': 1}, 'FieldTypeMismatch'),
                 ({'argv': ['true'], 'user': {'$env': 'USER'}}, 'UserInvalid'),
                 ({'argv': ['true'], 'user': None}, 'UserInvalid'),
                 ({'argv': [{'$env': 'PROGRAM'}]}, 'DirectiveUnsupported'),
                 ({'$ref': 'other'}, 'DirectiveUnsupported'),
                 ({'argv': ['true'], 'stdin': {'$opt': 'append', '$val': 'x'}}, 'UnknownOption'),
                 ({'argv': ['true'], 'stdout': {'$opt': 'append'}}, 'OptionConflict'),
                 ({'argv': ['true'], 'stdout': {'$opt': 'inherit', '$val': 'x'}}, 'OptionConflict'),
                 ({'argv': ['true'], 'stdout': {'$opt': 3}}, 'DirectiveValueTypeMismatch'),
                 ({'argv': ['true'], 'stdout': {'$opt': ['append', 'append'], '$val': 'x'}}, 'UnknownOption'),
                 ({'argv': ['true'], 'stderr': {'$opt': ['merge', 'append'], '$val': 'x'}}, 'OptionConflict'),
                 ({'argv': ['true'], 'stdout': {'$opt': 'mkdir', '$val': {'$opt': 'append', '$val': 'x'}}}, 'UnknownOption')]
        for obj, code in cases:
            with self.subTest(code=code, obj=obj):
                result = self.inst(obj, code=125)
                self.assertEqual(result['error']['code'], code)
                self.assertFalse(result['started'])

    def test_ignored_unknown_fields(self):
        self.inst({'argv': ['true'], 'unknown': 123,
                   '_metainfo': {'_type': 'posix', '_version': 1, 'unknown': True}})

    def test_snapshot_changed(self):
        file = self.path / 'job.json'
        write_json(file, {'argv': ['true']})
        raw, _, _ = read_inst(file)
        file.write_text('{"argv":["false"]}')
        result = run_snapshot(raw, file, os.getuid())
        self.assertEqual(result['error']['code'], 'UserMismatch')
        self.assertFalse(result['started'])

    def test_directory_base_and_fallback(self):
        write_json(self.path / 'inst.json', {'argv': ['sh', '-c', 'echo yes > result']})
        self.cli('run', self.path)
        self.assertTrue((self.path / 'result').exists())

    def test_descendant_detached_is_cleaned(self):
        # A child creates a new session; runner's subreaper still owns cleanup.
        script = ('import os,time; p=os.fork(); '
                  '\nif p==0:\n os.setsid(); open("child.pid","w").write(str(os.getpid())); time.sleep(60)'
                  '\nelse:\n'
                  ' import pathlib\n'
                  ' while not pathlib.Path("child.pid").exists(): time.sleep(.001)')
        self.inst({'argv': ['python3', '-c', script]})
        pid = int((self.path / 'child.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_status_fd_not_inherited(self):
        from aosproto.runner import snapshot_fd
        file = self.path / 'job.json'
        r, w = os.pipe()
        obj = {'argv': ['python3', '-c', 'import os,sys;\ntry: os.fstat(int(sys.argv[1]))\nexcept OSError: sys.exit(0)\nsys.exit(9)', str(w)]}
        write_json(file, obj)
        fd = snapshot_fd(file.read_bytes())
        proc = subprocess.Popen([str(BIN / 'aos-runner'), '--target', str(file), '--inst-fd', str(fd),
                                 '--status-fd', str(w), '--authorized-uid', str(os.getuid())], env=ENV, pass_fds=(fd, w))
        os.close(fd)
        os.close(w)
        with os.fdopen(r, 'rb') as stream:
            report = stream.read()
        self.assertEqual(proc.wait(timeout=5), 0, report)
