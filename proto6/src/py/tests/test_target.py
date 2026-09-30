"""找 inst（inst.md〈inst 目標：檔案或資料夾〉）。"""
import os

from aos_inst import InstError, find_inst, node_dir
from tests.util import TmpCase


class FindInst(TmpCase):
    def test_dir_prefers_dot_aos(self):
        a = self.write(".aos/inst.json", {"argv": ["a"]})
        self.write("inst.json", {"argv": ["b"]})
        src = find_inst(self.dir)
        self.assertEqual((src.path, src.base, src.is_dir), (a, self.dir, True))

    def test_dir_falls_back_to_inst_json(self):
        b = self.write("inst.json", {"argv": ["b"]})
        self.assertEqual(find_inst(self.dir).path, b)

    def test_base_is_dir_not_dot_aos(self):
        self.write(".aos/inst.json", {"argv": ["a"]})
        self.assertEqual(find_inst(self.dir).base, self.dir)

    def test_file_target(self):
        f = self.write("sub/job.json", {"argv": ["a"]})
        src = find_inst(f)
        self.assertEqual((src.path, src.base, src.is_dir), (f, self.path("sub"), False))

    def test_empty_dir_is_usage(self):
        with self.assertRaises(InstError) as cm:
            find_inst(self.dir)
        self.assertEqual((cm.exception.code, cm.exception.exit_code), ("Usage", 2))

    def test_missing_target_is_usage(self):
        with self.assertRaises(InstError) as cm:
            find_inst(self.path("nope.json"))
        self.assertEqual(cm.exception.exit_code, 2)


class NodeDir(TmpCase):
    def test_normalize(self):
        a = self.write(".aos/inst.json", {"argv": ["a"]})
        self.assertEqual(node_dir(a), self.dir)
        self.assertEqual(node_dir(self.dir), self.dir)

    def test_inst_json_is_node_when_no_dot_aos(self):
        b = self.write("inst.json", {"argv": ["b"]})
        self.assertEqual(node_dir(b), self.dir)

    def test_inst_json_shadowed_by_dot_aos(self):
        self.write(".aos/inst.json", {"argv": ["a"]})
        b = self.write("inst.json", {"argv": ["b"]})
        self.assertIsNone(node_dir(b))

    def test_single_file_not_node(self):
        f = self.write("once.json", {"argv": ["a"]})
        self.assertIsNone(node_dir(f))
        os.makedirs(self.path("empty"))
        self.assertIsNone(node_dir(self.path("empty")))
