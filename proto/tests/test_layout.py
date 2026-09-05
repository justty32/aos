"""aosp/layout.py：一塊地的版面、Land.resolve()、Home()。"""
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, layout  # noqa: E402
from .helpers import LandCase  # noqa: E402


class TestInit(LandCase):
    def test_init_creates_layout_json(self):
        self.assertTrue(os.path.isfile(self.land.layout),
                         msg=".aos/layout.json 應該被 aos init 建出來：%s" % self.land.layout)
        obj = fsutil.read_json(self.land.layout)
        self.assertEqual(obj.get("format_version"), 1,
                          msg="layout.json 的 format_version 應該是 1，實際 %r" % obj)
        self.assertEqual(obj.get("layout_version"), 1,
                          msg="layout.json 的 layout_version 應該是 1，實際 %r" % obj)

    def test_init_creates_config_json(self):
        self.assertTrue(os.path.isfile(self.land.config),
                         msg=".aos/config.json 應該被 aos init 建出來：%s" % self.land.config)

    def test_is_land_true_after_init(self):
        self.assertTrue(self.land.is_land(),
                         msg="init 過的地，is_land() 應該是 True")

    def test_is_land_false_for_plain_dir(self):
        plain = os.path.join(self.tmp, "not-a-land")
        fsutil.ensure_dir(plain)
        self.assertFalse(layout.Land(plain).is_land(),
                          msg="沒 init 過的目錄，is_land() 應該是 False")

    def test_init_second_time_without_force_keeps_existing(self):
        fsutil.write_json(self.land.config, {"format_version": 1, "marker": "keep-me"})
        land2, created = layout.init(self.land_root, force=False)
        self.assertFalse(created,
                          msg="已經是一塊地時，再 init（不帶 force）應該回報沒有重建")
        cfg = fsutil.read_json(land2.config)
        self.assertEqual(cfg.get("marker"), "keep-me",
                          msg="不帶 force 的重複 init 不該蓋掉既有 config.json，實際 %r" % cfg)


class TestResolve(LandCase):
    def test_relative_path_based_on_land_root(self):
        got = self.land.resolve(os.path.join("foo", "bar.txt"))
        want = os.path.join(self.land.root, "foo", "bar.txt")
        self.assertEqual(got, want,
                          msg="相對路徑應該以這塊地的根為基準，實際 %r 想要 %r" % (got, want))

    def test_absolute_path_passthrough(self):
        abs_path = os.path.join(self.tmp, "elsewhere", "x.txt")
        got = self.land.resolve(abs_path)
        self.assertEqual(got, abs_path,
                          msg="絕對路徑應該照用，不該被地的根前綴，實際 %r" % got)


class TestHome(LandCase):
    def test_home_reads_env(self):
        got = layout.home()
        want = os.path.abspath(os.environ["AOS_HOME"])
        self.assertEqual(got, want,
                          msg="home() 應該讀 $AOS_HOME，實際 %r 想要 %r" % (got, want))

    def test_home_registry_and_ledger_paths(self):
        h = layout.Home()
        self.assertEqual(h.registry, os.path.join(h.aos, "registry.json"),
                          msg=".registry 路徑不對：%r" % h.registry)
        self.assertEqual(h.registry_lock, os.path.join(h.aos, "registry.lock"),
                          msg=".registry_lock 路徑不對：%r" % h.registry_lock)
        self.assertEqual(h.ledger, os.path.join(h.aos, "ledger.jsonl"),
                          msg=".ledger 路徑不對：%r" % h.ledger)
        self.assertEqual(h.daemon_pid, os.path.join(h.aos, "daemon.pid"),
                          msg=".daemon_pid 路徑不對：%r" % h.daemon_pid)

    def test_llm_world_default(self):
        h = layout.Home()
        self.assertEqual(h.llm_world, os.path.join(h.aos, "llm"),
                          msg="沒設定 config 的 llm_world 時，應該預設 .aos/llm，實際 %r" % h.llm_world)

    def test_llm_world_config_override(self):
        h = layout.Home()
        custom = os.path.join(self.tmp, "custom-llm-world")
        fsutil.write_json(h.config, {"format_version": 1, "llm_world": custom})
        h2 = layout.Home()
        self.assertEqual(h2.llm_world, os.path.abspath(custom),
                          msg="config.json 設了 llm_world 就該用那個路徑，實際 %r 想要 %r"
                          % (h2.llm_world, os.path.abspath(custom)))
