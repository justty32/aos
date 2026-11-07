# Verify child account preservation and thought cleanup ordering.
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(LIB))
from observed_children import clear_child, copy_child, take_child


class ChildrenTests(unittest.TestCase):
    def test_declared_tree_survives_source_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child, tool = root / 'kid', root / 'tool'
            for relative, filename in [('', 'ledger.jsonl'), ('tools/bash', 'commands.jsonl'),
                                       ('tools/thought/observed/grandkid', 'observed.jsonl')]:
                folder = child / relative
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'interfaces.json').write_text(json.dumps({'other': {}, 'aos-observed': {'file': filename}}))
                (folder / filename).write_text('{"kind":"cmd"}\n')
            (child / 'secret').write_text('private')
            undeclared = child / 'undeclared'
            undeclared.mkdir()
            (undeclared / 'observed.jsonl').write_text('private')
            self.assertEqual(copy_child(tool, 'kid', child), 'observed/kid')
            self.assertEqual(take_child(tool), 'observed/kid')
            self.assertIsNone(take_child(tool))
            saved = tool / 'observed/kid'
            self.assertFalse((saved / 'secret').exists())
            self.assertFalse((saved / 'undeclared').exists())
            self.assertEqual(copy_child(root / 'parent', 'tool', tool), 'observed/tool')
            self.assertTrue((root / 'parent/observed/tool/observed/kid/tools/thought/observed/grandkid/observed.jsonl').exists())

    def test_missing_or_bad_interface_does_not_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'observed.jsonl').write_text('private')
            self.assertIsNone(copy_child(root / 'out', 'kid', root))
            (root / 'interfaces.json').write_text('[]')
            self.assertIsNone(copy_child(root / 'out', 'kid', root))
            clear_child(root)

    def test_gc_resolves_daemon_relative_stack(self):
        source = (LIB / 'agent/thought/_entry').read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'reconcile')
        from unittest.mock import Mock
        import os
        import time
        copied = Mock()
        namespace = dict(os=os, time=time, kids_dir='/unused', mtime=lambda name: 0,
                         lease_active=lambda value: False, STEP_S=90, FAILED_KEEP=1,
                         child_stacks={'old': 'procs/old'}, daemon='/daemon', stack='/tool',
                         copy_child=copied, forget=Mock(), mark=Mock(),
                         agent=Mock(return_value=('', None)), tool_io=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(LIB), 'exec'), namespace)
        from unittest.mock import patch, mock_open
        with patch('os.listdir', return_value=['old']), patch('builtins.open', mock_open(read_data='failed')):
            namespace['reconcile']({'old': 'stopped'})
        copied.assert_called_once_with('/tool', 'old', '/daemon/procs/old', publish=False)

    def test_thought_copies_before_keep_and_remove(self):
        import io
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = (LIB / 'agent/thought/_entry').read_text()
        ending = source[source.index('# ---- 問、收 ----'):]
        for keep in (False, True):
            with self.subTest(keep=keep):
                events = []
                def agent(argv, **kwargs):
                    events.append(argv[1] if argv[0] == 'ctl' else argv[0])
                    return 'answer', None
                def exit(code):
                    raise SystemExit(code)
                ns = dict(OPENING='{goal}', max_chars=600, goal='task', context=[], kid='kid',
                          stack='tool', kid_stack='/daemon/kid', keep=keep,
                          timeout_ticks=None, timeout_s=600, agent=agent,
                          copy_child=lambda *args: events.append('copy'),
                          mark=Mock(), forget=Mock(), tool_io=Mock(), rel=lambda value: value,
                          sys=SimpleNamespace(stdout=io.StringIO(), exit=exit))
                with self.assertRaises(SystemExit) as result:
                    exec(compile(ending, str(LIB / 'agent/thought/_entry'), 'exec'), ns)
                self.assertEqual(result.exception.code, 0)
                self.assertEqual(events, ['say', 'listen', 'copy', 'stop' if keep else 'rm'])
                if keep:
                    ns['mark'].assert_called_once_with('kid', 'kept')
                    ns['forget'].assert_not_called()
                else:
                    ns['forget'].assert_called_once_with('kid')



if __name__ == '__main__':
    unittest.main()
