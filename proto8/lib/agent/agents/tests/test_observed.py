# Verify agent account synchronization resolves only registered child stacks.
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / '_entry'


class ObservedTests(unittest.TestCase):
    def test_registered_child_stack_is_used(self):
        tree = ast.parse(SOURCE.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'preserve_child')
        ns = dict(load_json=Mock(return_value=[{'name': 'kid', 'stack': 'procs/kid'}]),
                  children_path='children.json', stack='tool', stack_abs=lambda value: '/daemon/' + value,
                  copy_child=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), ns)
        ns['preserve_child']('kid')
        ns['copy_child'].assert_called_once_with('tool', 'kid', '/daemon/procs/kid')
        ns['copy_child'].reset_mock()
        ns['preserve_child']('unknown')
        ns['copy_child'].assert_not_called()

    def test_ask_and_rm_sync_but_say_does_not(self):
        import io
        from types import SimpleNamespace
        tree = ast.parse(SOURCE.read_text())
        branches = [node for node in tree.body if isinstance(node, ast.If)
                    and ast.unparse(node.test) in ('op in ("say", "ask")', "op in ('say', 'ask')", "op == 'rm'", 'op == "rm"')]
        code = compile(ast.Module(body=branches, type_ignores=[]), str(SOURCE), 'exec')
        for op, expected in [('say', ['say']), ('ask', ['say', 'listen', 'copy']),
                             ('rm', ['copy', 'rm', 'write'])]:
            with self.subTest(op=op):
                events = []
                def must(argv, **kwargs):
                    events.append(argv[1] if argv[0] == 'ctl' else argv[0])
                    return 'answer'
                def exit(code):
                    raise SystemExit(code)
                ns = dict(op=op, args={'text': 'hello'}, my_child=lambda args: 'kid',
                          need_str=lambda args, key: args[key], must=must,
                          timeout_ticks=None, timeout_s=600, ctl_s=30, STEP_S=90,
                          preserve_child=lambda name: events.append('copy'),
                          write_children=lambda value: events.append('write'),
                          load_json=lambda *args: [], children_path='children.json',
                          sys=SimpleNamespace(stdout=io.StringIO(), exit=exit))
                with self.assertRaises(SystemExit) as result:
                    exec(code, ns)
                self.assertEqual(result.exception.code, 0)
                self.assertEqual(events, expected)



if __name__ == '__main__':
    unittest.main()
