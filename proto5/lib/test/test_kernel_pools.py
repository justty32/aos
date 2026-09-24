"""proto5-2 kernel：info 第 2 版讀驗、成員公式、init --config、家與模板（不需要 daemon）。"""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_home
import aos_kernel_info as ki
import aos_kernel_pools
from _kernel_fake import FakeCase

CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-kernel"


def v2(**over):
    info = {"_metainfo": {"_type": "kernel", "_version": 2}, "daemon": "/abs/D",
            "pools": {"default": {"count": 2}}}
    info.update(over)
    return info


class Members(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(ki.members(3, [1]), [0, 2, 3])
        self.assertEqual(ki.members(0, [5]), [])
        self.assertEqual(ki.members(2, [0, 1, 9]), [2, 3])
        self.assertTrue(ki.is_member(3, 3, [1]))
        self.assertFalse(ki.is_member(1, 3, [1]))
        self.assertFalse(ki.is_member(4, 3, [1]))

    def test_encode_round_trip(self):
        rnd = random.Random(7)
        for _ in range(200):
            numbers = set(rnd.sample(range(40), rnd.randint(0, 20)))
            count, skip = ki.encode(numbers)
            self.assertEqual(set(ki.members(count, skip)), numbers)
            for i in range(45):
                self.assertEqual(ki.is_member(i, count, skip), i in numbers)

    def test_cpu_key(self):
        self.assertEqual(ki.split_key("default/3"), ("default", 3))
        for bad in ("default/01", "default/-1", "default/x", "/3", "a/b/3", "de fault/1"):
            self.assertIsNone(ki.split_key(bad), bad)


class InfoRead(unittest.TestCase):
    def parse(self, info):
        return ki._parse_info(Path("/abs/K"), info)

    def bad(self, info, code="FieldTypeMismatch"):
        with self.assertRaises(ki.KernelError) as cm:
            self.parse(info)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception

    def test_version(self):
        self.bad({"_metainfo": {"_type": "kernel", "_version": 1}, "cpus": {"k": {"pool": "kernel"}}}, "InfoVersion")
        self.bad({"_metainfo": {"_type": "kernel", "_version": 3}, "pools": {}}, "NotAHome")
        self.bad({"pools": {}}, "NotAHome")

    def test_defaults(self):
        info = self.parse(v2(pools={"default": {"count": 2}, "llm": {"count": 1, "envs": {"A": "b"}}}))
        self.assertNotIn("kernel", info["pools"])            # one-boot：不再補 kernel 池
        self.assertEqual(info["tick_timeout_ms"], 60000)
        self.assertEqual(info["pools"]["default"]["dpool"], "default")
        self.assertEqual(info["pools"]["llm"]["envs"], {"A": "b"})
        self.assertEqual(info["cpu"], {"poll_ms": 200, "timeout_ms": 0})
        self.assertEqual(info["sweep"], 32)
        self.assertEqual(info["tick_ms"], 1000)
        self.assertEqual(ki.pool_location(info, "llm"), ("/abs/D", "llm"))

    def test_legacy_kernel_pool_tolerated(self):
        """one-boot：舊 info 的 kernel 池讀得過（照一般池的形狀驗）、不算工作池；它寫的 daemon 當開 tick 的 daemon。"""
        for config in ({"count": 2}, {"count": 1, "skip": [0]}, {"count": 0}, {"count": 1, "dpool": "k1-kernel"}):
            info = self.parse(v2(pools={"kernel": config, "default": {"count": 1}}))
            self.assertEqual(ki.work_pools(info), ["default"])
            self.assertEqual(ki.ticker_daemon(info), "/abs/D")
        info = self.parse(v2(pools={"kernel": {"count": 1, "daemon": "/abs/DK"}}))
        self.assertEqual(ki.ticker_daemon(info), "/abs/DK")
        self.bad(v2(pools={"kernel": {"count": -1}}))
        self.bad(v2(tick_timeout_ms=-1))

    def test_dpool_clash(self):
        self.bad(v2(pools={"a": {"count": 1, "dpool": "x"}, "b": {"count": 1, "dpool": "x"}}))
        self.bad(v2(pools={"a": {"count": 1}, "b": {"count": 1, "dpool": "a"}}))
        # 不同 daemon 就不算撞
        self.parse(v2(pools={"a": {"count": 1, "dpool": "x"}, "b": {"count": 1, "dpool": "x", "daemon": "/abs/D2"}}))
        info = self.parse(v2(pools={"g": {"count": 1, "daemon": "/abs/D2"}}))
        self.assertEqual(ki.pool_location(info, "g"), ("/abs/D2", "g"))

    def test_boundaries(self):
        self.parse(v2(pools={"a" * 64: {"count": 0}}))
        for name in ("a" * 65, "a/b", ".", "..", "{x}", "a#b", "", "é"):
            self.bad(v2(pools={name: {"count": 1}}))
        self.bad(v2(pools={"a": {"count": 1, "dpool": "x/y"}}))
        self.bad(v2(pools={"a": {"count": True}}))
        self.bad(v2(pools={"a": {"count": -1}}))
        self.bad(v2(pools={"a": {"count": 1000001}}))
        self.parse(v2(pools={"a": {"count": 1000000}}))
        self.bad(v2(pools={"a": {}}))
        self.bad(v2(pools={"a": {"count": 1, "skip": [1, 1]}}))
        self.bad(v2(pools={"a": {"count": 1, "skip": [-1]}}))
        self.bad(v2(pools={"a": {"count": 1, "skip": [True]}}))
        self.bad(v2(pools={"a": {"count": 1, "envs": []}}))
        self.bad(v2(pools={"a": {"count": 1, "daemon": "rel/D"}}))
        self.bad(v2(daemon="rel"))
        self.bad(v2(cpu={"poll_ms": 0}))
        self.bad(v2(cpu={"timeout_ms": -1}))
        self.bad(v2(sweep=0))
        self.bad(v2(pools=[]))
        self.bad(["x"])

    def test_envs_not_resolved_but_rest_is(self):
        info = self.parse(v2(pools={"a": {"count": 1, "dpool": {"$fmt": {"$val": "k1-${p}", "p": "a"}}},
                                    "b": {"count": 1, "envs": {"X": {"$env": "HOME"}}}}))
        self.assertEqual(info["pools"]["a"]["dpool"], "k1-a")
        self.assertEqual(info["pools"]["b"]["envs"], {"X": {"$env": "HOME"}})

    def test_daemon_optional_until_boot(self):
        info = self.parse({"_metainfo": {"_type": "kernel", "_version": 2}, "pools": {"a": {"count": 1}}})
        self.assertEqual(ki.pool_location(info, "a"), (None, "a"))
        self.assertIsNone(ki.ticker_daemon(info))
        self.assertIsNone(ki.pool_location(info, "kernel"))


class Init(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-kfake-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.K = self.root / "K"

    def test_no_config(self):
        ki.init(self.K)
        info = aos_home.read_json(self.K / "info.json")
        self.assertEqual(info["_metainfo"], {"_type": "kernel", "_version": 2})
        self.assertEqual(info["pools"], {})                  # one-boot：init 不再補 kernel 池
        self.assertNotIn("tick_timeout_ms", info)            # 預設值不寫進 info
        for d in ("requests", "responses", "pools"):
            self.assertTrue((self.K / d).is_dir())
        self.assertEqual(list((self.K / "pools").iterdir()), [])
        with self.assertRaises(ki.KernelError) as cm:
            ki.init(self.K)
        self.assertEqual(cm.exception.code, "AlreadyExists")

    def test_config_empty_pools_and_zero(self):
        ki.init(self.K, {"pools": {}, "tick_ms": 50})
        info = aos_home.read_json(self.K / "info.json")
        self.assertEqual(info["pools"], {})
        self.assertEqual(info["tick_ms"], 50)
        K2 = self.root / "K2"
        ki.init(K2, {"pools": {"default": {"count": 0}}})
        self.assertEqual(ki.load_info(K2)["pools"]["default"]["count"], 0)

    def test_daemon_priority(self):
        ki.init(self.K, {"pools": {}, "daemon": "/abs/fromconfig"}, daemon=str(self.root / "D"))
        self.assertEqual(aos_home.read_json(self.K / "info.json")["daemon"], str(self.root / "D"))
        K2 = self.root / "K2"
        ki.init(K2, {"pools": {}, "daemon": "/abs/fromconfig"})
        self.assertEqual(aos_home.read_json(K2 / "info.json")["daemon"], "/abs/fromconfig")
        K3 = self.root / "K3"
        old = os.environ.get("AOS_DAEMON_HOME")
        os.environ["AOS_DAEMON_HOME"] = "rel-d"
        try:
            ki.init(K3)
        finally:
            if old is None:
                del os.environ["AOS_DAEMON_HOME"]
            else:
                os.environ["AOS_DAEMON_HOME"] = old
        self.assertEqual(aos_home.read_json(K3 / "info.json")["daemon"], os.path.abspath("rel-d"))

    def test_bad_config_builds_nothing(self):
        for config in ([], "x", {"$ref": "a.json"}, {"pools": {"$ref": "p.json"}},
                       {"pools": {"kernel": {"count": 2}}}, {"pools": {"kernel": {"count": 1}}},
                       {"pools": {"a": {"count": "1"}}}):
            with self.assertRaises(ki.KernelError):
                ki.init(self.K, config)
            self.assertFalse(self.K.exists())

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, timeout=20,
                              env={**os.environ, "AOS_DAEMON_HOME": ""})

    def test_cli_init(self):
        config = self.root / "c.json"
        aos_home.write_json(config, {"pools": {"default": {"count": 3}}})
        r = self.cli("init", "--target", self.K, "--config", config, "--daemon", self.root / "D")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "initialized %s" % self.K)
        info = ki.load_info(self.K)
        self.assertEqual(info["pools"]["default"]["count"], 3)
        self.assertEqual(info["daemon"], str(self.root / "D"))
        r = self.cli("init", "--target", self.K)
        self.assertEqual(r.returncode, 1)
        self.assertIn("AlreadyExists", r.stderr)
        K2 = self.root / "K2"
        r = self.cli("init", "--target", K2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("daemon", aos_home.read_json(K2 / "info.json"))
        for old in (["--cpu", "0"], ["--env", "0:A=b"]):
            r = self.cli("init", "--target", self.root / "K3", *old)
            self.assertEqual(r.returncode, 2, r.stderr)
        r = self.cli("init", "--target", self.root / "K4", "--config", config, "--daemon", "")
        self.assertEqual(r.returncode, 2)


class Homes(FakeCase):
    def test_boot_builds_homes_and_templates(self):
        self.init({"default": {"count": 2}, "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}},
                   "empty": {"count": 0}}, cpu={"poll_ms": 150})
        self.boot()
        pools = self.K / "pools"
        cpu_cli = str((Path(ki.__file__).resolve().parents[1] / "cli" / "aos-cpu").resolve())
        tmpl = {"argv": [cpu_cli, "."], "cwd": ".", "stderr": {"$opt": "append", "$val": "cpu.log"},
                "envs": {"$ref": "../../envs.json"}}
        self.assertFalse((pools / "kernel").exists())          # one-boot：沒有 kernel 池的家
        for pool, n in (("default", 2), ("llm", 1), ("empty", 0)):
            self.assertEqual(aos_home.read_json(pools / pool / "inst.json"), tmpl)
            self.assertEqual(sorted(p.name for p in (pools / pool / "cpus").iterdir()), [str(i) for i in range(n)])
            for i in range(n):
                home = pools / pool / "cpus" / str(i)
                self.assertEqual(aos_home.read_json(home / "inst.json"), tmpl)
                self.assertTrue((home / "requests").is_dir() and (home / "responses").is_dir())
        self.assertEqual(aos_home.read_json(pools / "llm" / "envs.json"), {"AOS_LLM_CONFIG": "/abs/llm.json"})
        self.assertEqual(aos_home.read_json(pools / "default" / "envs.json"), {})
        self.assertEqual(aos_home.read_json(pools / "default" / "cpus" / "1" / "info.json"),
                         {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 150, "timeout_ms": 0,
                          "notify": str(self.K / "requests")})

    def test_homes_fill_missing_never_overwrite_never_delete(self):
        self.init({"default": {"count": 2}})
        self.boot()
        home = self.K / "pools" / "default" / "cpus" / "1"
        aos_home.write_json(home / "inst.json", {"mine": True})
        (home / "info.json").unlink()
        self.edit_info(default={"count": 1})
        self.settle()
        self.assertTrue(home.is_dir())  # 縮小不刪家
        self.boot()
        self.assertEqual(aos_home.read_json(home / "inst.json"), {"mine": True})
        self.assertFalse((home / "info.json").exists())  # 1 號已不是成員：boot 只補 W 裡的
        self.edit_info(default={"count": 2})
        self.settle()
        self.assertTrue((home / "info.json").exists())  # 長回來時補齊
        self.assertEqual(aos_home.read_json(home / "inst.json"), {"mine": True})

    def test_envs_change_rewrites_without_scale(self):
        self.init({"default": {"count": 1}})
        self.boot()
        self.settle()
        sent = len(self.fake.seen)
        self.edit_info(default={"count": 1, "envs": {"X": "1"}})
        st = self.tick()
        self.assertEqual(aos_home.read_json(self.K / "pools" / "default" / "envs.json"), {"X": "1"})
        self.assertEqual(len(self.fake.seen), sent)
        self.assertEqual(st["pools"]["default"]["envs_digest"], aos_kernel_pools.envs_digest({"X": "1"}))


if __name__ == "__main__":
    unittest.main()
