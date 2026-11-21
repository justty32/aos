"""Every _entry under py/tools and templates that is a program (starts with #! or is an ELF file, or is not JSON) has its execute bit; a JSON _entry ({"description", "argv"} and the like) needs none (user 11-21: "補測試")."""
import json
import os
from pathlib import Path
import stat
import sys
import unittest

sys.dont_write_bytecode = True
P8 = Path(__file__).resolve().parents[2]
ROOTS = ("py/tools", "templates")


def program_like(path):
    """Same split as aos-exec picks the kind of an entry: #! or ELF = a program; else JSON is read (and not being JSON is an error there)."""
    data = path.read_bytes()
    if data.startswith(b"#!") or data.startswith(b"\x7fELF"):
        return True
    try:
        json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return True
    return False


def entries():
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(P8 / root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "_entry" in filenames:
                yield Path(dirpath) / "_entry"


class ToolEntryExec(unittest.TestCase):
    def test_program_entries_are_executable(self):
        found = [p for p in entries() if program_like(p)]
        tools = [p for p in found if p.is_relative_to(P8 / "py/tools")]
        self.assertGreater(len(tools), 80)                  # the walk really reached the tools
        missing = [str(p.relative_to(P8)) for p in found if not os.stat(p).st_mode & stat.S_IXUSR]
        self.assertEqual(missing, [], "chmod +x these entries: aos-exec reads an _entry without +x as JSON and fails")

    def test_json_entries_are_not_counted(self):
        """The JSON ones (agent, kernel, start-api rows...) are there and are left out, whatever their mode."""
        json_ones = [p for p in entries() if not program_like(p)]
        self.assertGreater(len(json_ones), 10)


if __name__ == "__main__":
    unittest.main()
