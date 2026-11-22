"""Verify reply files and legacy folders against a temporary zone without aos-post."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import zone as Z


class VerifyPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zone-verify-paths-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.zone = self.root / "user"
        Z.init(str(self.zone))
        self.body = {"zone": Z.ZONE_VER, "from": "user", "status": "DONE", "what": "yes", "reply_id": "r1"}
        self.letter = {"sender": str(self.zone), "in_reply_to": "original", "body": self.body}
        done = self.zone / "done" / "2026-11" / "original"
        done.mkdir(parents=True)
        Z.write_json(str(done / "reply.json"), dict(self.body, sent_as="reply", sent_to="test-mailbox"))
        Z.log(str(self.zone), "replied", letter="original", reply_id="r1")
        self.folder = self.root / "legacy-reply"
        self.folder.mkdir()
        self.old_file = self.folder / "letter.json"
        self.old_file.write_text(json.dumps(self.letter), encoding="utf-8")
        self.single_file = self.root / "single-reply"
        self.single_file.write_text(json.dumps(self.letter), encoding="utf-8")

    def cli(self, path):
        env = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
        env.update(AOS_USER_ZONE=str(self.zone), HOME=str(self.root), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "aos-user"), "verify", str(path)],
                              capture_output=True, text=True, env=env, timeout=30)

    def test_folder_and_both_file_paths_verify_identically(self):
        results = []
        for path in (self.folder, self.old_file, self.single_file):
            with self.subTest(path=path):
                results.append(Z.verify(str(self.zone), str(path)))
                result = self.cli(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.startswith("ok: matches "), result.stdout)
        self.assertTrue(results[0][0])
        self.assertEqual(results, [results[0]] * 3)

    def test_missing_path(self):
        path = self.root / "missing"
        with self.assertRaises(Z.Fail) as cm:
            Z.verify(str(self.zone), str(path))
        self.assertEqual(cm.exception.code, "VerifyBad")
        self.assertEqual(str(cm.exception), "%s is not a letter file or folder" % path)
        result = self.cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-user: error: VerifyBad ", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_directory_without_letter_json(self):
        path = self.root / "empty"
        path.mkdir()
        with self.assertRaises(Z.Fail) as cm:
            Z.verify(str(self.zone), str(path))
        self.assertEqual(cm.exception.code, "LetterBad")
        self.assertEqual(str(cm.exception), "cannot read %s" % (path / "letter.json"))
        result = self.cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-user: error: LetterBad ", result.stderr)

    def test_file_uses_existing_authentication_checks(self):
        for change, expected in (({"sender": "not-the-zone"}, "sender is"),
                                 ({"body": dict(self.body, what="changed")}, "reply differs"),
                                 ({"body": dict(self.body, zone="other")}, "not a user-zone reply")):
            with self.subTest(change=change):
                self.single_file.write_text(json.dumps(dict(self.letter, **change)), encoding="utf-8")
                ok, why = Z.verify(str(self.zone), str(self.single_file))
                self.assertFalse(ok)
                self.assertIn(expected, why)


if __name__ == "__main__":
    unittest.main()
