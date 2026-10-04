#!/usr/bin/env python3
"""proto7-2 全套測試的統一入口（在 repo 根跑）：

    python3 proto7-2/tests/run_all.py [-v] [-k 樣式]... [資料夾...]

不給資料夾時收 `tests/core/`、`modules/*/tests/`、`modules/tests/` 底下所有 `test_*.py`；給了就只跑那些
（相對 proto7-2/ 或絕對路徑）。`-k` 同 unittest（可重複）。退出碼 0＝全綠、1＝有失敗。

各資料夾的測試檔名要唯一（每個資料夾各自 discover，同名模組會在 sys.modules 撞名）；共用工具 base／_matrix／_proc 在 tests/。
"""
import argparse
import glob
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def test_dirs():
    """預設要跑的測試資料夾：核心先，再各模組包。"""
    dirs = [os.path.join(HERE, "core")]
    dirs += sorted(d for d in glob.glob(os.path.join(TOP, "modules", "*", "tests")) if os.path.isdir(d))
    if os.path.isdir(os.path.join(TOP, "modules", "tests")):
        dirs.append(os.path.join(TOP, "modules", "tests"))
    return dirs


def main(argv=None):
    ap = argparse.ArgumentParser(description="proto7-2 全套測試")
    ap.add_argument("dirs", nargs="*", help="只跑這些資料夾（相對 proto7-2/）")
    ap.add_argument("-k", action="append", dest="patterns", default=None, help="只跑名字符合的測試（同 unittest -k）")
    ap.add_argument("-v", action="store_true", help="逐項列出")
    a = ap.parse_args(argv)
    dirs = [d if os.path.isabs(d) else os.path.join(TOP, d) for d in a.dirs] or test_dirs()
    suite = unittest.TestSuite()
    seen = {}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, "test_*.py"))):
            name = os.path.basename(p)
            if name in seen:
                print("run_all: 測試檔名重複：%s 與 %s" % (seen[name], p), file=sys.stderr)
                return 2
            seen[name] = p
        loader = unittest.TestLoader()
        if a.patterns:
            loader.testNamePatterns = ["*%s*" % k if "*" not in k else k for k in a.patterns]
        suite.addTests(loader.discover(d, pattern="test_*.py", top_level_dir=d))
    r = unittest.TextTestRunner(verbosity=2 if a.v else 1).run(suite)
    return 0 if r.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
