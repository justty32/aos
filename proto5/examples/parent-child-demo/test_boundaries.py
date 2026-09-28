"""Offline boundary tests; never starts a daemon or contacts a model."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bridge
import install


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('parent', 'project', 'reference', 'K'):
            (self.root / folder).mkdir()
        for filename in ('parent/info.json', 'K/info.json'):
            (self.root / filename).write_text('{}')
        self.cfg = {'root': str(self.root), 'cli': '/unused/aos-agent'}

    def test_arguments_rejected_before_cli(self):
        with patch('bridge.Path.cwd', return_value=self.root / 'parent'), patch('bridge.cli') as cli:
            for arg in ({'task': ''}, {'task': 'ok', 'path': '/tmp/other'},
                        {'task': 3}, {'task': 'x' * 12001}, {'task': 'x\0y'}, []):
                with self.assertRaises(ValueError):
                    bridge.invoke(self.cfg, 'parent', 'spawn_child', arg)
            cli.assert_not_called()

    def test_existing_child_is_not_adopted(self):
        (self.root / 'child').mkdir()
        with self.assertRaises(ValueError):
            install.install(self.root)
        self.assertFalse((self.root / 'parent-child-demo').exists())

    def test_symlink_path_rejected(self):
        (self.root / 'child').symlink_to(self.root / 'parent')
        with self.assertRaises(ValueError):
            bridge.check_paths(self.cfg)

    def test_repeat_install_preserves_parent(self):
        memory = self.root / 'parent/history.json'
        memory.write_text('private history')
        with patch('install.cli') as cli:
            install.install(self.root)
            before = {p: p.read_bytes() for p in (self.root / 'parent').iterdir()}
            install.install(self.root)
            self.assertEqual(cli.call_count, 1)
            self.assertEqual(before, {p: p.read_bytes() for p in (self.root / 'parent').iterdir()})

    def test_incomplete_install_does_not_report_success(self):
        with patch('install.cli', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                install.install(self.root)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            install.install(self.root)

    def test_child_cannot_spawn(self):
        with patch('bridge.Path.cwd', return_value=self.root / 'child'):
            with self.assertRaises(ValueError):
                bridge.invoke(self.cfg, 'child', 'spawn_child', {'task': 'hi'})


if __name__ == '__main__':
    unittest.main()
