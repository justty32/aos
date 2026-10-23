"""10-20 指示詞改版（proto8/thinking/2026-10-20-ideas.md D9～D15）：$path 取代 path、加 $prefix；
錯分兩類——真的解不開（變數沒設、讀不到、指不到、繞圈）照舊是錯，寫法（格式）寬容、不報錯。
10-23 Python 版刪了（使用者「python版本可以刪掉了」）：原本直接叫 Python 庫 aos_inst.resolve 的逐條案例拿掉，
同樣的案例 C++ 版在 proto8/impls/aos-directive/tests/test_cli.py；這裡只留經 aos-exec 的命令列案例。"""
import tempfile, unittest
from pathlib import Path

from test_directive_argv import put, run  # noqa: E402
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name).resolve()
        self.addCleanup(self._t.cleanup)

    # ───── 命令列：argv 陣列與單子 ─────

    def test_cli_argv_array_and_inst(self):
        ws = self.t / "ws"; ws.mkdir()
        q = self.t / "q"
        put(q / "_entry.json", ["echo", {"$env": "AOS_WS", "$path": "a.txt", "$prefix": "--file="}])
        rc, out, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual((rc, out), (0, "--file=%s/a.txt\n" % ws), err)
        # 寫法不合＝物件原封不動 → argv 陣列解完不是字串＝入口壞（aos-exec 的規則，不是指示詞的錯）
        put(q / "_entry.json", ["echo", {"$env": 3}])
        rc, _, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("aos-exec: 入口壞"), err)
        put(q / "_entry.json", {"argv": ["echo", {"$env": "AOS_WS", "$fmt": "%s", "$prefix": "w="}]})
        rc, out, err = run("aos-exec", "--ws", ws, q)
        self.assertEqual((rc, out), (0, "w=%s\n" % ws), err)


if __name__ == "__main__":
    unittest.main()
