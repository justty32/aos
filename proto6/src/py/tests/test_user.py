"""proto6 新增：頂層 `user`——只讀原始字面值、不切換身分；跟目前身分不同就 125、不跑、不寫 exit。"""
import os
import pwd
import unittest

from _util import ExecCase, InstCase

ME_UID = os.geteuid()
ME_NAME = pwd.getpwuid(ME_UID).pw_name
OTHER_UID = 0 if ME_UID != 0 else 65534
OTHER_NAME = pwd.getpwuid(OTHER_UID).pw_name


class TestUserLoad(InstCase):

    def test_same_identity_runs(self):
        for user in (ME_NAME, ME_UID, ""):
            self.assertEqual(self.load({"user": user, "argv": ["true"]})["argv"], ["true"], user)

    def test_omitted(self):
        self.assertEqual(self.load({"argv": ["true"]})["argv"], ["true"])

    def test_other_identity_rejected(self):
        for user in (OTHER_NAME, OTHER_UID):
            self.bad({"user": user, "argv": ["true"]}, "UserNotGranted")

    def test_invalid(self):
        for user in (True, -1, 1.5, ["x"], {"$env": "USER"}, "aos-no-such-user-xyz"):
            self.bad({"user": user, "argv": ["true"]}, "UserInvalid")

    def test_checked_before_directives(self):
        """身分先看：user 不對時，別的欄位的指示詞錯誤不會先冒出來。"""
        self.bad({"user": OTHER_UID, "argv": [{"$ref": "nope.json"}]}, "UserNotGranted")


class TestUserCli(ExecCase):

    def test_mismatch_cli(self):
        self.inst({"user": OTHER_NAME, "argv": ["sh", "-c", "echo ran > ran.txt"], "exit": "exit.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-exec: UserNotGranted: "), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertFalse(self.exists("ran.txt"))
        self.assertFalse(self.exists("exit.txt"))

    def test_same_cli(self):
        self.inst({"user": ME_NAME, "argv": ["sh", "-c", "echo ran > ran.txt"], "exit": "exit.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("ran.txt"), "ran\n")
        self.assertEqual(self.read("exit.txt"), "0\n")


if __name__ == "__main__":
    unittest.main()
