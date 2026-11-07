# Verify one-time metadata migration, preservation, exclusions, and idempotence.
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('migration', Path(__file__).parents[1] / 'metainfo_migrate.py')
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def test_shapes_and_preservation(self):
        for legacy, expected in [(50, {'cost': {'time_ms': 50}}),
                                 ({'val': 50, 'max': 100}, {'cost': {'time_ms': 50}, 'timeout_ms': 100}),
                                 ({'max': 100}, {'timeout_ms': 100})]:
            with self.subTest(legacy=legacy):
                meta = {'summary': 'demo', 'time_ms': legacy, 'extra': [1], 'cost': {'token': 2}}
                migration.migrate(meta)
                self.assertEqual(meta['summary'], 'demo')
                self.assertEqual(meta['extra'], [1])
                self.assertEqual(meta['cost']['token'], 2)
                for key, value in expected.items():
                    if key == 'cost':
                        self.assertEqual(meta[key]['time_ms'], value['time_ms'])
                    else:
                        self.assertEqual(meta[key], value)
                self.assertEqual(list(meta)[:2], ['summary', 'extra'])
                self.assertNotIn('time_ms', meta)
                self.assertFalse(migration.migrate(meta))

    def test_tree_embedded_and_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, obj in [('_metainfo.json', {'time_ms': 3}),
                                  ('tool.json', {'description': 'tool', '_metainfo': {'time_ms': {'val': 4, 'max': 5}}}),
                                  ('data.json', {'time_ms': 6}),
                                  ('thinking/_metainfo.json', {'time_ms': 7}),
                                  ('archive/_metainfo.json', {'time_ms': 8}),
                                  ('.git/_metainfo.json', {'time_ms': 9}),
                                  ('user-advice/_metainfo.json', {'time_ms': 10})]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj))
            (root / 'alias.json').symlink_to(root / '_metainfo.json')
            self.assertEqual(len(migration.migrate_tree(root)), 2)
            before = {p: p.read_bytes() for p in root.rglob('*.json')}
            self.assertEqual(migration.migrate_tree(root), [])
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*.json')})
            self.assertEqual(json.loads((root / 'tool.json').read_text())['_metainfo'],
                             {'cost': {'time_ms': 4}, 'timeout_ms': 5})
            self.assertEqual(json.loads((root / 'thinking/_metainfo.json').read_text()), {'time_ms': 7})

    def test_conflicts_are_reported(self):
        for meta in [{'time_ms': 4, 'cost': {'time_ms': 5}},
                     {'time_ms': {'max': 4}, 'timeout_ms': 5},
                     {'time_ms': 'bad'}]:
            with self.assertRaises(ValueError):
                migration.migrate(meta)


if __name__ == '__main__':
    unittest.main()
