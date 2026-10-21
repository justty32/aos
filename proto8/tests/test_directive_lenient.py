"""10-20 指示詞改版（proto8/thinking/2026-10-20-ideas.md D9～D15）：$path 取代 path、加 $prefix；
錯分兩類——真的解不開（變數沒設、讀不到、指不到、繞圈）照舊是錯，寫法（格式）寬容、不報錯。"""
import json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import aos_inst  # noqa: E402
from test_directive_argv import put, run  # noqa: E402


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name).resolve()
        self.addCleanup(self._t.cleanup)
        put(self.t / "d.json", {"s": "/base", "n": 3, "o": {"k": 1}})
        self._env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._env)))
        os.environ["AOS_WS"] = "/ws"
        os.environ.pop("AOS_NOPE_XYZ", None)

    def r(self, x):
        return aos_inst.resolve(x, str(self.t))

    # ───── D9、D10：$path、$prefix ─────

    def test_env_path_prefix(self):
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "a.txt"}), "/ws/a.txt")
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "a.txt", "$prefix": "--file="}), "--file=/ws/a.txt")
        self.assertEqual(self.r({"$env": "AOS_WS", "$prefix": "-C"}), "-C/ws")
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "/abs"}), "/ws/abs")   # 10-21 傍晚：絕對路徑也是接上去
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": None, "$prefix": None}), "/ws")

    def test_path_is_string_concat(self):
        # 10-21 傍晚 ideas § 9：$path＝字串拼接——# 開頭直接接；其他中間剛好一個 /；空字串＝不接
        os.environ["AOS_CF"] = "/x/big.json"
        self.assertEqual(self.r({"$env": "AOS_CF", "$path": "#/loops/a"}), "/x/big.json#/loops/a")
        self.assertEqual(self.r({"$env": "AOS_CF", "$path": "#/loops/a", "$prefix": "--cfg="}),
                         "--cfg=/x/big.json#/loops/a")
        self.assertEqual(self.r({"$env": "AOS_CF", "$path": "#"}), "/x/big.json#")
        for sub in ("a.txt", "/a.txt", "//a.txt"):
            self.assertEqual(self.r({"$env": "AOS_WS", "$path": sub}), "/ws/a.txt", sub)
        os.environ["AOS_WS"] = "/ws//"
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "/a/b/"}), "/ws/a/b/")
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": ""}), "/ws//")
        os.environ["AOS_WS"] = ""
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "a"}), "/a")
        os.environ["AOS_WS"] = "/"
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "a"}), "/a")

    def test_ref_string_path_prefix(self):
        self.assertEqual(self.r({"$ref": "d.json#/s", "$path": "x", "$prefix": "--f="}), "--f=/base/x")

    def test_ref_non_string_silently_ignores(self):
        self.assertEqual(self.r({"$ref": "d.json#/n", "$path": "x", "$prefix": "p"}), 3)
        self.assertEqual(self.r({"$ref": "d.json", "at": "/o", "$prefix": "p"}), {"k": 1})

    def test_old_path_key_ignored(self):
        self.assertEqual(self.r({"$env": "AOS_WS", "path": "a.txt"}), "/ws")

    # ───── D12～D15：寫法寬容 ─────

    def test_unknown_dollar_keys_ignored(self):
        self.assertEqual(self.r({"$env": "AOS_WS", "$fmt": "x", "$nope": 1}), "/ws")
        self.assertEqual(self.r({"$ref": "d.json#/s", "$fmt": "x"}), "/base")
        # 沒有 $ref／$env 的物件不是指示詞，照常往下解
        self.assertEqual(self.r({"$fmt": "x", "a": {"$env": "AOS_WS"}}), {"$fmt": "x", "a": "/ws"})

    def test_bad_path_prefix_type_treated_as_absent(self):
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": 3, "$prefix": ["x"]}), "/ws")
        self.assertEqual(self.r({"$env": "AOS_WS", "$path": "a", "$prefix": 1}), "/ws/a")

    def test_bad_at_treated_as_absent(self):
        self.assertEqual(self.r({"$ref": "d.json#/s", "at": "a"}), "/base")
        self.assertEqual(self.r({"$ref": "d.json#/s", "at": 3}), "/base")

    def test_malformed_left_untouched(self):
        for x in ({"$ref": 3}, {"$ref": ""}, {"$ref": "#/s"}, {"$ref": "d.json#s"},
                  {"$env": 3}, {"$env": ""}, {"$env": None, "$path": "a"},
                  {"$ref": 3, "$env": "AOS_WS"},                         # 有 $ref 就只看 $ref
                  {"$ref": 3, "a": {"$env": "AOS_WS"}}):                  # 物件裡其餘東西不管
            self.assertEqual(self.r(x), x)
        self.assertEqual(self.r(["a", {"$env": 3}]), ["a", {"$env": 3}])

    # ───── 真的解不開＝照舊報錯 ─────

    def test_real_failures_still_errors(self):
        put(self.t / "bad.json", "{nope")
        put(self.t / "l1.json", {"$ref": "l2.json"})
        put(self.t / "l2.json", {"$ref": "l1.json"})
        for x, msg in (({"$env": "AOS_NOPE_XYZ", "$path": "a"}, "AOS_NOPE_XYZ"),
                       ({"$ref": "nope.json"}, "讀不到"),
                       ({"$ref": "bad.json"}, "不是 JSON"),
                       ({"$ref": "d.json#/zz"}, "指不到"),
                       ({"$ref": "l1.json"}, "繞圈")):
            with self.assertRaises(aos_inst.InstError) as c:
                self.r(x)
            self.assertIn(msg, str(c.exception))

    def test_ref_to_folder_is_error(self):
        # 10-21 傍晚 ideas § 9：$ref 指到資料夾＝讀不到、算錯（不走進去找入口、不把資料夾組成物件；使用者「維持報錯」）
        (self.t / "dir").mkdir()
        put(self.t / "dir" / "_exec.json", {"k": 1})
        for x in ({"$ref": "dir"}, {"$ref": "dir#/k"}, {"$ref": "dir", "at": "/k"}):
            with self.assertRaises(aos_inst.InstError) as c:
                self.r(x)
            self.assertIn("讀不到", str(c.exception))

    # ───── 命令列：argv 陣列與單子 ─────

    def test_cli_argv_array_and_inst(self):
        ws = self.t / "ws"; ws.mkdir()
        q = self.t / "q"
        put(q / "_exec.json", ["echo", {"$env": "AOS_WS", "$path": "a.txt", "$prefix": "--file="}])
        rc, out, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual((rc, out), (0, "--file=%s/a.txt\n" % ws), err)
        # 寫法不合＝物件原封不動 → argv 陣列解完不是字串＝入口壞（aos-exec 的規則，不是指示詞的錯）
        put(q / "_exec.json", ["echo", {"$env": 3}])
        rc, _, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("aos-exec: 入口壞"), err)
        put(q / "_exec.json", {"argv": ["echo", {"$env": "AOS_WS", "$fmt": "%s", "$prefix": "w="}]})
        rc, out, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual((rc, out), (0, "w=%s\n" % ws), err)


if __name__ == "__main__":
    unittest.main()
