# Verify shell stages, public account ownership, shape normalization and tool overrides.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
from report import command_shapes, effective_stage, report


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def ledger(path, rows, declared=True):
    path.mkdir(parents=True, exist_ok=True)
    if declared:
        write(path / 'interfaces.json', {'aos-observed': {'file': 'public.jsonl'}})
    (path / 'public.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


class ShellReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'PATH': str(HERE.parents[2] / 'cmd/aos-tools/bin') + os.pathsep + os.environ['PATH']})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def definition(self, name, metas):
        definition = self.root / name
        write(definition / 'interfaces.json', {'aos-agent': {'tools': 'cfg/tools.json'}})
        tools = {}
        for tool_name, meta in metas.items():
            target = self.root / ('tool_' + tool_name)
            write(target / '_tooldef.json', {'name': tool_name, 'description': 'Test tool', 'parameters': {'type': 'object'}})
            write(target / '_metainfo.json', meta)
            tools[tool_name] = {'path': str(target)}
        write(definition / 'cfg/tools.json', {'tools': tools})
        return definition

    def test_stages_and_effective_overlay(self):
        stack = self.root / 'stack'
        opened = self.definition('open', {'shell': {'arbitrary_exec': True}, 'safe': {}})
        boxed = self.definition('boxed', {'boxed': {'arbitrary_exec': True, 'sandbox': {}}})
        none = self.definition('none', {'safe': {}})
        self.assertEqual(effective_stage(opened, stack), ('open', ['shell']))
        self.assertEqual(effective_stage(boxed, stack), ('boxed', ['boxed']))
        self.assertEqual(effective_stage(none, stack), ('none', []))
        base = str(opened / 'cfg/tools.json')   # 11-10 aos-tools 改版：stack 那份＝"$override" 指回定義那份、拿掉的寫 null
        write(stack / 'cfg/tools.json', {'$override': base, 'tools': {'shell': None, 'boxed': {'path': str(self.root / 'tool_boxed')}}})
        self.assertEqual(effective_stage(opened, stack), ('boxed', ['boxed']))
        write(stack / 'cfg/tools.json', {'$override': base, 'tools': {'shell': None}})
        self.assertEqual(effective_stage(opened, stack), ('none', []))

    def test_shapes_pipeline_quotes_and_redirections(self):
        with patch('report.shutil.which', return_value=None):
            result = command_shapes('rg -n "two words" src 2>errors && jq -r . < input | missing x >> out; cd /tmp')
        self.assertEqual([r[0] for r in result], ['rg -n <arg> <arg> <redir>', 'jq -r <arg> <redir>', 'missing <arg> <redir>', 'cd <arg>'])
        self.assertTrue(all(binary is None for _, binary in result))
        self.assertEqual(command_shapes(''), [])
        self.assertEqual(command_shapes('missing x 2>&1')[0][0], 'missing <arg> <redir>')
        python_shape, python_binary = command_shapes(sys.executable + ' -c pass')[0]
        self.assertEqual(python_binary, str(Path(sys.executable).resolve()))
        self.assertTrue(python_shape.endswith(' -c <arg>'))
        with self.assertRaises(ValueError):
            command_shapes('rg "unfinished')

    def test_aggregate_children_and_undeclared_accounts(self):
        definition = self.definition('parent', {})
        child = self.definition('child', {})
        stacks = [self.root / 'run1/stack', self.root / 'run2/stack']
        for stack in stacks:
            ledger(stack, [{'kind': 'self', 'def': str(definition)},
                           {'kind': 'tool', 'stack': 'tools/shell', 'child': 'observed/kid'},
                           {'kind': 'tool', 'stack': 'tools/hidden'}])
            ledger(stack / 'tools/shell', [{'kind': 'self', 'def': '/wrong/tool'},
                                         {'kind': 'cmd', 'command': 'missing -n x', 'exit': 0}])
            ledger(stack / 'observed/kid', [{'kind': 'self', 'def': str(child)},
                                          {'kind': 'cmd', 'command': 'missing y', 'exit': 2}])
            ledger(stack / 'tools/hidden', [{'kind': 'cmd', 'command': 'secret x', 'exit': 0}], declared=False)
            # Unreferenced accounts are private implementation details.
            ledger(stack / 'private', [{'kind': 'cmd', 'command': 'secret x', 'exit': 0}])
        result = {row['agent']: row for row in report(stacks)['reports']}
        self.assertEqual(len(result), 2)
        self.assertEqual(result[str(definition)]['shapes'], [{'shape': 'missing -n <arg>', 'count': 2, 'exit_zero': 2, 'cases': list(map(str, stacks))}])
        self.assertEqual(result[str(child)]['shapes'][0]['exit_zero'], 0)
        self.assertEqual(result[str(child)]['shapes'][0]['count'], 2)
        # Duplicate stack references must not duplicate counts.
        self.assertEqual(report(stacks + stacks), report(stacks))

    def test_no_declaration_does_not_read_log_or_tools(self):
        stack = self.root / 'stack'
        ledger(stack, [], declared=False)
        (stack / 'public.jsonl').write_text('invalid JSON')
        write(stack / 'tools.json', 'also ignored')
        self.assertEqual(report([stack]), {'reports': []})

    def test_relative_definition_and_cli_errors(self):
        definition = self.definition('agent', {})
        stack = self.root / 'stack'
        ledger(stack, [{'kind': 'self', 'def': 'agent'}])
        self.assertEqual(report([stack], self.root)['reports'][0]['agent'], str(definition))
        with self.assertRaises(ValueError):
            report([stack])
        for payload in ('{}', '{"stacks":["relative"]}'):
            result = subprocess.run([str(HERE / '_entry')], input=payload, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, result.stderr)
        result = subprocess.run([str(HERE / '_entry'), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--stacks', result.stdout)


if __name__ == '__main__':
    unittest.main()
