"""收屍／cgroup 模組驗收（plan m3m-daemon-modules.md 模組二）。真的開 bin/aos-daemon。

本檔：重讀、錯誤、沒委派（WithReload、Errors、NotDelegated）。

要有委派的 cgroup v2：daemon 一律用 `systemd-run --user --scope -p Delegate=yes` 包起來開（scope 就是它的子樹根）。
這台拿不到（沒有 systemd-run、使用者層 systemd 沒在跑、沒有 cgroup.kill……）整組跳過，不算失敗。
「沒委派好時回 1」那條直接開 daemon，只在測試自己所在的 cgroup 寫不進去時才跑（WSL 的 /init.scope 就是）。

都用暫存資料夾、短週期、假 inst；等條件一律用 monotonic 計時的 wait_for，時限寬鬆。
收尾時對 scope 的根寫 cgroup.kill，連 daemon 帶殘留一起清掉。
"""
import os
import subprocess
import unittest

import aos_daemon_cgroup
from _util import PY
from _daemon_util import CLEAN_ENV, DAEMON, sh
from test_daemon_reload import ReloadCase
from _cgroup_util import CG, CgCase, SCOPE, alive, cat


class WithReload(CgCase):

    def test_add_remove_and_limits(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        mods = dict(CG, reload={})
        p, out, _ = self.boot({"a.json": {"cgroup": {"pids.max": "50"}}}, 30000, modules=mods)
        self.wait_for(lambda: self.results(out, "a.json"), timeout=10)
        # 加 b、改 a 的上限
        self.rewrite(p, {"a.json": {"cgroup": {"pids.max": "40"}}, "b.json": {}}, 30000, modules=mods)
        self.wait_for(lambda: self.results(out, "b.json"), timeout=10)
        t = self.texts(out)
        self.assertLess(t.index("inst=b.json added"), t.index("inst=b.json cgroup=%s" % aos_daemon_cgroup.frame_name("b.json")))
        self.assertTrue(os.path.isdir(self.frame("b.json")))
        self.assertEqual(cat(os.path.join(self.frame("a.json"), "pids.max")), "40")
        self.assertEqual(sum(1 for x in t if x.startswith("inst=a.json cgroup=")), 1)   # 還在的項不再印
        # 拿掉 b：框刪掉
        self.rewrite(p, {"a.json": {"cgroup": {"pids.max": "40"}}}, 30000, modules=mods)
        self.wait_for(lambda: not os.path.exists(self.frame("b.json")), timeout=10)
        self.assertTrue(os.path.isdir(self.frame("a.json")))

    def test_remove_running_cleans_after(self):
        # 拿掉正在跑的項：那次照樣跑完、清完殘留，之後框刪掉
        self.inst(sh("sleep 1000 & echo $! >> bg; sleep 1"), "r.json")
        mods = dict(CG, reload={})
        p, out, _ = self.boot({"r.json": {}}, 30000, modules=mods)
        self.wait_for(lambda: self.bg(), timeout=10)
        self.rewrite(p, {}, 30000, modules=mods)
        self.wait_for(lambda: self.has(out, "inst=r.json removed"))
        self.wait_for(lambda: self.has(out, "inst=r.json reaped"), timeout=10)
        self.wait_for(lambda: not os.path.exists(self.frame("r.json")), timeout=10)
        (pid,) = self.bg()
        self.assertFalse(alive(pid))

    def test_bad_limit_on_reload(self):
        # 重讀時上限寫不進去（不存在的 cgroup 檔）：算重讀出錯，stderr 一行，舊的照跑
        self.inst({"argv": ["true"]}, "a.json")
        mods = dict(CG, reload={})
        p, out, err = self.boot({"a.json": {}}, 30000, modules=mods)
        self.wait_for(lambda: self.results(out, "a.json"), timeout=10)
        self.rewrite(p, {"a.json": {"cgroup": {"no.such.file": "1"}}}, 30000, modules=mods)
        self.wait_for(lambda: any(l.startswith("aos-daemon: reload: ") for l in list(err)), timeout=10)
        self.assertEqual(self.reloads(out), 0)
        self.assertIsNone(p.poll())


class Errors(CgCase):

    def test_bad_limit_at_start(self):
        # 開起來時上限寫不進去：自然丟錯、回 1
        self.inst({"argv": ["true"]}, "a.json")
        cfg = self.config({"interval_ms": 30000, "modules": CG,
                           "insts": {"a.json": {"cgroup": {"no.such.file": "1"}}}})
        r = subprocess.run(SCOPE + [PY, DAEMON, "--config", cfg], cwd=self.d, env=CLEAN_ENV,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Traceback", r.stderr)
        self.assertFalse(self.results(r.stdout.splitlines(), "a.json"))


def _own_writable():
    try:
        return os.access(aos_daemon_cgroup.own_cgroup(), os.W_OK)
    except (OSError, IndexError):
        return True


class NotDelegated(ReloadCase):         # 不包 systemd-run、不看 SKIP

    @unittest.skipIf(_own_writable(), "測試自己所在的 cgroup 寫得進去，模擬不了沒委派")
    def test_no_delegation_exits_1(self):
        # C1：掛了模組卻沒有委派好的 cgroup：自然丟錯、回 1，一次都沒跑
        self.inst({"argv": ["true"]}, "a.json")
        cfg = self.config({"interval_ms": 30000, "modules": CG, "insts": {"a.json": {}}})
        r = self.run_cfg(cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Traceback", r.stderr)
        self.assertIn("PermissionError", r.stderr)
        self.assertFalse(self.results(r.stdout.splitlines(), "a.json"))


if __name__ == "__main__":
    unittest.main()
