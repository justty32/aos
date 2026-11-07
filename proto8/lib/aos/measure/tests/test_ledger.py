# Verify public ledger traversal, local token accounting, and call aggregation.
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('ledger', Path(__file__).parents[1] / 'ledger.py')
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'stack'
        self.defs = self.root / 'defs'

    def account(self, path, records, public=True):
        path.mkdir(parents=True, exist_ok=True)
        (path / 'book.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
        if public:
            (path / 'interfaces.json').write_text(json.dumps({'aos-observed': {'file': 'book.jsonl'}}))

    def think(self, count=10, usage=True):
        return {'kind': 'think', 'endpoint': 'fake', 'elapsed_ms': 7,
                'usage': {'prompt_tokens': count, 'completion_tokens': 2,
                          'prompt_tokens_details': {'cached_tokens': 3}} if usage else None}

    def tool(self, name='worker', **extra):
        return {'kind': 'tool', 'name': name, 'def': str(self.defs / name),
                'stack': 'tools/' + name, 'elapsed_ms': 20, **extra}

    def test_two_levels_child_copy_and_no_double_count(self):
        self.account(self.stack, [self.tool(child='tools/worker/observed/kid')])
        worker = self.stack / 'tools/worker'
        self.account(worker, [{'kind': 'tool', 'name': 'kid', 'def': str(self.defs / 'kid'),
                               'stack': 'observed/kid', 'elapsed_ms': 12}])
        self.account(worker / 'observed/kid', [self.think(11), self.tool('leaf', elapsed_ms=4)])
        tree, total = ledger.fold(self.stack, self.defs, self.defs / 'root', 100)
        self.assertEqual(total['token']['in'], 11)
        self.assertEqual(total['counter_calls'], 1)
        self.assertEqual(tree['cost']['token']['in'], 0)
        self.assertEqual(tree['cost']['time_ms'], 20)
        self.assertEqual(total['time_ms'], 20)
        self.assertEqual(len(tree['children'][0]['children']), 1)

    def test_repeated_calls_read_shared_account_once(self):
        self.account(self.stack, [self.tool(), self.tool()])
        self.account(self.stack / 'tools/worker', [self.think(5), self.think(9), self.think(usage=False)])
        tree, cost = ledger.fold(self.stack, self.defs, 'root')
        child = tree['children'][0]
        self.assertEqual(child['counter_calls'], 2)
        self.assertEqual(child['cost']['counter_calls'], 3)
        self.assertEqual(cost['token'], {'in': 14, 'out': 4, 'cached': 6})
        self.assertEqual(cost['counter_usage_missing'], 1)
        self.assertEqual(child['kind'], 'agent')
        self.assertEqual(child['endpoint'], 'fake')
        self.assertEqual(cost['time_ms'], 40)

    def test_private_account_is_leaf(self):
        self.account(self.stack, [self.think()], public=False)
        tree, cost = ledger.fold(self.stack, self.defs, 'root', 19)
        self.assertEqual(cost['token']['in'], 0)
        self.assertEqual(cost['time_ms'], 19)
        self.assertEqual(tree['kind'], 'script')

    def test_root_time_is_sum_and_definition_paths(self):
        self.account(self.stack, [self.tool('a', elapsed_ms=8), self.tool('b', elapsed_ms=13)])
        tree, cost = ledger.fold(self.stack, self.defs, self.defs / 'root', 100)
        self.assertEqual(tree['def'], 'root')
        self.assertEqual(cost['time_ms'], 21)
        self.assertEqual(cost['time_ms'], sum(c['cost']['time_ms'] for c in tree['children']))
        outside, _ = ledger.fold(self.stack, self.defs, self.root / 'outside')
        self.assertEqual(outside['def'], str(self.root / 'outside'))

    def test_nested_script_preserves_parent_time_and_input_bytes(self):
        self.account(self.stack, [self.tool(in_bytes=3), self.tool(in_bytes=5)])
        self.account(self.stack / 'tools/worker', [self.tool('leaf', elapsed_ms=4)])
        tree, cost = ledger.fold(self.stack, self.defs, 'root', 100)
        child = tree['children'][0]
        self.assertEqual(child['cost']['time_ms'], 40)
        self.assertEqual(child['children'][0]['cost']['time_ms'], 4)
        self.assertEqual(child['in_bytes'], 8)
        self.assertEqual(cost['time_ms'], 40)

    def test_command_leaf_without_outer_timer(self):
        self.account(self.stack, [{'kind': 'cmd', 'elapsed_ms': 9}])
        tree, cost = ledger.fold(self.stack, self.defs, 'bash')
        self.assertEqual(cost['time_ms'], 9)
        self.assertEqual(tree['kind'], 'script')

    def test_invalid_public_objects_raise_value_error(self):
        self.stack.mkdir()
        (self.stack / 'interfaces.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'interfaces.json must be an object'):
            ledger.fold(self.stack, self.defs)
        self.account(self.stack, [17])
        with self.assertRaisesRegex(ValueError, 'observation records must be objects'):
            ledger.fold(self.stack, self.defs)

    def test_child_path_is_relative_to_parent_stack(self):
        self.account(self.stack, [self.tool(child='copies/kid')])
        self.account(self.stack / 'copies/kid', [self.think(23)])
        tree, total = ledger.fold(self.stack, self.defs, 'root')
        self.assertEqual(tree['children'][0]['children'][0]['kind'], 'agent')
        self.assertEqual(total['token']['in'], 23)
        self.assertEqual(total['time_ms'], 20)


if __name__ == '__main__':
    unittest.main()
