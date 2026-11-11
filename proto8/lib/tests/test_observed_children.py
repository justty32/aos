# Verify observed_children: a child's declared accounts are copied (and only those), take_child hands the mark over once.
import json
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from observed_children import clear_child, copy_child, take_child


class ChildrenTests(unittest.TestCase):
    def test_declared_tree_survives_source_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child, tool = root / 'kid', root / 'tool'
            for relative, filename in [('', 'ledger.jsonl'), ('tools/shell', 'commands.jsonl'),
                                       ('tools/subagent/observed/grandkid', 'observed.jsonl')]:
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
            self.assertTrue((root / 'parent/observed/tool/observed/kid/tools/subagent/observed/grandkid/observed.jsonl').exists())

    def test_missing_or_bad_interface_does_not_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'observed.jsonl').write_text('private')
            self.assertIsNone(copy_child(root / 'out', 'kid', root))
            (root / 'interfaces.json').write_text('[]')
            self.assertIsNone(copy_child(root / 'out', 'kid', root))
            clear_child(root)


if __name__ == "__main__":
    unittest.main()
