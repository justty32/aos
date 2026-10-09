"""動態掛載崩潰／失敗重試，以及讀檔與指示詞的 K4 回歸測試。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import errno
import unittest
from unittest import mock

from base import SLEEP
from _matrix import MatrixCase
import aos7_fs
from aos7_fs import read_json, write_json
from aos_directives import Context, DirectiveError, Document, resolve


class TestMountDyn(MatrixCase):
    """〔core〕動態掛載、fact 與指示詞的修復回歸。"""

    def running_mount_task(self):
        node = self.mknode("a", [{"name": "m", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "m")
        return node, self.slot(node, "m")

    def assert_mounted(self, node, sd, req):
        receipt = read_json(os.path.join(sd, "mount-done", "z.json"))
        self.assertIs(receipt["result"]["ok"], True)
        mount = self.birth(node, "m")["mounts"]["z"]
        self.assertIs(mount.get("dyn"), True)
        self.assertEqual(mount["to"], "z")
        self.assertEqual(mount["at"], os.path.join(sd, "mnt", "z"))
        self.assertNotIn("error", mount)
        self.assertTrue(os.path.islink(mount["at"]))
        self.assertEqual(os.path.realpath(mount["at"]), os.path.join(self.root, "z"))
        self.assertTrue(os.path.isdir(mount["at"]))
        self.assertFalse(os.path.exists(req))
        self.assertEqual(self.birth(node, "m")["run"], 1)

    def test_a8_07_mount_dyn_crash_after_symlink(self):
        """A8-07：建連結後、寫 birth 前被殺，收回合後重審同一請求成功。"""
        node, sd = self.running_mount_task()
        req = os.path.join(sd, "mount-req", "z.json")
        item = {"name": "z", "path": "z", "why": "崩潰後重試"}
        write_json(req, item)
        self.tock()
        self.crash("aos7-tick", "after-symlink")
        self.assertTrue(self.round_json(node)["open"])
        self.assertTrue(os.path.islink(os.path.join(sd, "mnt", "z")))
        self.assertNotIn("z", self.birth(node, "m")["mounts"])
        self.assertEqual(read_json(req), item)
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-done", "z.json")))
        self.tock(env={"AOS7_INCOMPLETE": "tick"})
        self.assertFalse(self.round_json(node)["open"])
        self.assertEqual(read_json(req), item)
        self.tick()
        self.assert_mounted(node, sd, req)

    def test_r8_09_mount_dyn_retry_failed_birth(self):
        """R8-09：同名同目標的失敗紀錄不算已掛，動態重試補建連結並換成 at＋dyn。"""
        node, sd = self.running_mount_task()
        birth = self.birth(node, "m")
        birth["mounts"]["z"] = {"to": "z", "error": "先前掛載失敗"}
        write_json(os.path.join(sd, "birth.json"), birth)
        self.assertFalse(os.path.lexists(os.path.join(sd, "mnt", "z")))
        req = os.path.join(sd, "mount-req", "z.json")
        write_json(req, {"name": "z", "path": "z", "why": "失敗後重試"})
        self.tock()
        self.tick()
        self.assert_mounted(node, sd, req)

    def test_r8_07_fact_fstat_eio_closes_fd(self):
        """R8-07：連續 50 次 fstat EIO 都回 U，開過的 fd 不洩漏。"""
        path = os.path.join(self.root, "fact.json")
        write_json(path, {"exists": True})
        self.assertEqual(aos7_fs.fact(path), (aos7_fs.OK, {"exists": True}))
        before = len(os.listdir("/proc/self/fd"))
        opened = set()

        def eio(fd):
            opened.add(fd)
            raise OSError(errno.EIO, os.strerror(errno.EIO))

        try:
            with mock.patch("aos7_fs.os.fstat", side_effect=eio) as fstat:
                for i in range(50):
                    with self.subTest(call=i):
                        state, detail = aos7_fs.fact(path)
                        self.assertEqual(state, aos7_fs.U)
                        self.assertIn("fact.json", detail)
                self.assertEqual(fstat.call_count, 50)
            self.assertEqual(len(os.listdir("/proc/self/fd")), before)
        finally:
            # 修正前的紅燈驗證也收掉洩漏的 fd，不污染後面的測試。
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_r8_28_ref_non_ascii_array_index(self):
        """R8-28：非 ASCII 數字索引一律是 ReferencePointerInvalid，不外洩 ValueError。"""
        doc = Document(None, {"array": ["zero", "one", "two"]})
        ctx = Context(doc)
        self.assertEqual(resolve({"$ref": "#/array/1"}, ctx, ["request"]), "one")
        for digit in ("²", "١"):
            for directive in ({"$ref": "#/array/" + digit},
                              {"$ref": "", "$at": "/array/" + digit}):
                with self.subTest(directive=directive):
                    with self.assertRaises(DirectiveError) as caught:
                        resolve(directive, ctx, ["request"])
                    self.assertEqual(caught.exception.code, "ReferencePointerInvalid")

    def test_r8_28_ref_at_null_is_type_mismatch(self):
        """R8-28：$at 明寫 null 必須拒絕，不能當成省略而取整份文件。"""
        doc = Document(None, {"value": "whole document"})
        ctx = Context(doc)
        self.assertEqual(resolve({"$ref": ""}, ctx, ["request"]), doc.root)
        with self.assertRaises(DirectiveError) as caught:
            resolve({"$ref": "", "$at": None}, ctx, ["request"])
        self.assertEqual(caught.exception.code, "DirectiveValueTypeMismatch")


if __name__ == "__main__":
    unittest.main()
