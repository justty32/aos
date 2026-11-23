"""test_daemon_sub - daemon-sub stays daemon-root without the clock: same files, the same _entry argv and sweeper row, no _clock row, and a .env that sets only AOS_HOME."""
# 使用者 11-23（eca_main 轉來）「做一個『普通 daemon』範本，也就是掛在別的 daemon 底下、本身不帶時鐘的子 daemon」：
# daemon-root 改了 _entry 的 argv、_sweeper 那列或 procs_requests 沒同步到 daemon-sub 就紅。說明句、README 本來就不同，不比。只讀檔、不起行程。
import json
import os
from pathlib import Path
import unittest

TEMPLATES = Path(__file__).resolve().parents[1]
ROOT, SUB = TEMPLATES / "daemon-root", TEMPLATES / "daemon-sub"


def files(folder):
    """Relative paths of every file under folder (no __pycache__)."""
    out = set()
    for dirpath, dirnames, names in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for n in names:
            out.add(os.path.relpath(os.path.join(dirpath, n), folder))
    return out


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def settings(path):
    """The NAME=VALUE lines of a .env file (comments and blank lines left out)."""
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]


class DaemonSubTest(unittest.TestCase):
    def test_same_files_as_daemon_root(self):
        self.assertEqual(files(SUB), files(ROOT), "daemon-sub has other files than daemon-root")

    def test_entry_runs_the_same(self):
        root, sub = load(ROOT / "_entry"), load(SUB / "_entry")
        self.assertEqual(sub["argv"], root["argv"], "daemon-sub/_entry argv differs from daemon-root's: copy it again")
        self.assertEqual(sorted(sub), sorted(root))
        self.assertNotIn("root", sub["description"].lower())

    def test_daemon_json_is_root_without_the_clock(self):
        root, sub = load(ROOT / "daemon.json"), load(SUB / "daemon.json")
        self.assertIn("_clock", root["procs"])
        self.assertEqual(sorted(sub["procs"]), ["_sweeper"], "daemon-sub must carry only its own _sweeper (the clock is only in the root)")
        want = dict(root, procs={k: v for k, v in root["procs"].items() if k != "_clock"})
        del want["description"]
        got = dict(sub)
        del got["description"]
        self.assertEqual(got, want, "daemon-sub/daemon.json differs from daemon-root's beyond the _clock row: copy it again")
        self.assertNotIn("Root", sub["description"])

    def test_env_sets_only_aos_home(self):
        self.assertEqual(settings(SUB / ".env"), ["AOS_HOME=${AOS_HOME}"],
                         "daemon-sub/.env sets only AOS_HOME: AOS_CLOCK and AOS_LLM_KERNEL come from the daemon above")
        self.assertEqual(settings(ROOT / ".env")[-1], settings(SUB / ".env")[-1])
        self.assertTrue((SUB / ".env").read_text(encoding="utf-8").startswith("# .env - "))


if __name__ == "__main__":
    unittest.main()
