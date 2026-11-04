"""測試共用底座。只准標準庫。

LandCase：每支測試自己的暫存 AOS_HOME + 一塊地，tearDown 還原環境變數並清目錄。
write_source：把步驟陣列寫成一份原稿（<name>.aos.json）。
run_cli：用 subprocess 跑 python3 proto/aos.py <argv...>，回傳 (returncode, stdout, stderr)。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, layout  # noqa: E402

AOS_PY = os.path.join(PROTO, "aos.py")


class LandCase(unittest.TestCase):
    """setUp 建暫存目錄、把 $AOS_HOME 指過去、開一塊地；tearDown 全部收回去。"""

    def setUp(self):
        self._old_home = os.environ.get("AOS_HOME")
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        home_dir = os.path.join(self.tmp, "home")
        fsutil.ensure_dir(home_dir)
        os.environ["AOS_HOME"] = home_dir
        self.land_root = os.path.join(self.tmp, "land")
        self.land, _created = layout.init(self.land_root)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("AOS_HOME", None)
        else:
            os.environ["AOS_HOME"] = self._old_home
        shutil.rmtree(self.tmp, ignore_errors=True)


def write_source(land, steps, name="main"):
    """把步驟陣列寫成一份原稿 <name>.aos.json（land 的根目錄下）。"""
    fsutil.write_json(land.source(name), {
        "format_version": 1,
        "name": name,
        "steps": steps,
    })


def run_cli(*argv, cwd=None, env=None, timeout=15):
    """跑真的子行程：python3 proto/aos.py <argv...>。回傳 (returncode, stdout, stderr)。"""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    p = subprocess.run(
        [sys.executable, AOS_PY] + list(argv),
        cwd=cwd, env=full_env, capture_output=True, text=True, timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr
