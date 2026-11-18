"""Verify ls-only kernel selection from stack artifacts, a flag, environment, and daemon table."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[3] / 'bin/aos-llm'


class KernelSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='llm-ls-kernel-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.daemon = self.root / 'daemon-stack'
        self.daemon.mkdir()
        self.first = self.make_kernel('first')
        self.second = self.make_kernel('second')
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('AOS_')}
        self.env['AOS_DAEMON'] = str(self.daemon)

    def make_kernel(self, name, requests=True):
        stack = self.root / name
        stack.mkdir()
        (stack / 'endpoints.json').write_text(json.dumps({name: {'summary': name}}))
        if requests:
            (stack / 'requests').mkdir()
        return stack

    def table(self, rows):
        (self.daemon / 'procs_state.json').write_text(json.dumps({'procs': rows}))

    def row(self, stack=None, **fields):
        return dict({'stack': os.path.relpath(stack or self.first, self.daemon)}, **fields)

    def call(self, *args, env=None):
        return subprocess.run([str(BIN), 'ls', '--json', *args], cwd=self.root,
                              env=self.env if env is None else env, capture_output=True, text=True, timeout=10)

    def listed(self, *args, name='first', env=None):
        result = self.call(*args, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {name: {'summary': name}})

    def missing(self, *args):
        result = self.call(*args)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('LlmKernelMissing', result.stderr)
        self.assertIn('--kernel', result.stderr)
        return result.stderr

    def test_explicit_absolute_and_relative_stack_without_table(self):
        self.listed('--kernel', str(self.first))
        self.listed('--kernel', './first')

    def test_explicit_stack_overrides_environment(self):
        self.env['AOS_LLM_KERNEL'] = str(self.second)
        self.listed('--kernel', str(self.first))

    def test_named_row_overrides_environment_and_needs_no_detection(self):
        stack = self.make_kernel('explicit', requests=False)
        self.table({'chosen': self.row(stack, exec='/tools/custom-function')})
        self.env['AOS_LLM_KERNEL'] = str(self.second)
        self.listed('--kernel', 'chosen', name='explicit')

    def test_environment_overrides_discovery(self):
        self.table({'other': self.row(self.second)})
        self.env['AOS_LLM_KERNEL'] = '../first'
        self.listed()

    def test_definition_folder_exec_with_public_stack_artifacts(self):
        definition = self.root / 'kern/llm-sol'
        definition.mkdir(parents=True)
        (definition / '_entry').write_text('["aos-loop", "loop.json"]')
        (definition / 'loop.json').write_text(json.dumps({'exec': {'argv': [
            'aos-exec', {'$env': 'AOS_HOME', '$path': '/lib/tools/aos/kernel_llm'}]}}))
        self.table({'llm-sol': self.row(exec=os.path.relpath(definition, self.daemon))})
        self.listed()

    def test_only_endpoints_without_requests_is_not_candidate(self):
        stack = self.make_kernel('window-only', requests=False)
        self.table({'other': self.row(stack)})
        self.missing()
        self.table({'brain': self.row(), 'other': self.row(stack)})
        self.listed()

    def test_only_requests_without_endpoints_is_not_candidate(self):
        stack = self.root / 'mailbox-only'
        (stack / 'requests').mkdir(parents=True)
        self.table({'other': self.row(stack)})
        self.missing()

    def test_artifact_types_must_be_file_and_directory(self):
        directory_window = self.root / 'directory-window'
        (directory_window / 'endpoints.json').mkdir(parents=True)
        (directory_window / 'requests').mkdir()
        file_requests = self.make_kernel('file-requests', requests=False)
        (file_requests / 'requests').write_text('not a directory')
        self.table({'directory-window': self.row(directory_window),
                    'file-requests': self.row(file_requests)})
        self.missing()

    def test_exec_and_def_names_do_not_identify_candidates(self):
        stack = self.root / 'empty'
        stack.mkdir()
        self.table({'legacy': self.row(stack, exec='/bin/aos-llm-kernel',
                                       **{'def': '/definitions/llm-kernel'})})
        self.missing()

    def test_stack_artifacts_work_without_exec_or_def(self):
        self.table({'brain': self.row()})
        self.listed()

    def test_absolute_stack(self):
        self.table({'brain': {'stack': str(self.first)}})
        self.listed()

    def test_relative_stack_uses_real_daemon_location(self):
        alias = self.root / 'aliases/daemon'
        alias.parent.mkdir()
        alias.symlink_to(self.daemon, target_is_directory=True)
        self.env['AOS_DAEMON'] = str(alias)
        self.table({'brain': self.row()})
        self.listed()

    def test_table_parts(self):
        (self.daemon / 'part.json').write_text(json.dumps({'brain': self.row()}))
        self.table({'$ref': ['part.json']})
        self.listed()

    def test_none_and_multiple_matches(self):
        self.table({})
        self.assertIn('no llm kernel rows', self.missing())
        self.table({'alpha': self.row(), 'beta': self.row(self.second)})
        error = self.missing()
        self.assertIn('alpha', error)
        self.assertIn('beta', error)

    def test_unknown_name_missing_table_and_invalid_stack(self):
        self.missing()
        self.table({})
        self.missing('--kernel', 'unknown')
        self.table({'absent': {}, 'null': {'stack': None}, 'empty': {'stack': ''},
                    'missing': {'stack': 'does-not-exist'}})
        self.missing()
        self.missing('--kernel', 'absent')

    def test_no_daemon_requires_explicit_path_or_environment(self):
        self.env.pop('AOS_DAEMON')
        self.missing()
        self.listed('--kernel', str(self.first))
        self.env['AOS_LLM_KERNEL'] = './first'
        self.listed()

    def test_other_commands_do_not_accept_kernel_flag(self):
        result = subprocess.run([str(BIN), 'send', '--kernel', str(self.first)], cwd=self.root,
                                env=self.env, input='{}', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FlagUnknown', result.stderr)


if __name__ == '__main__':
    unittest.main()
