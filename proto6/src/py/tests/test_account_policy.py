"""帳號模組驗收（plan m3m-daemon-modules.md 模組五）。

本檔：一般帳號就能跑的名單比對、設定錯、沒用 root、重讀不換帳號、root 端的框檢查與 exec 前整理（Names、Policies、NotRoot、ReloadKeepsAccount、RootSide）。

兩組：
- `Names`、`Policies`、`NotRoot`：一般帳號就能跑（名單比對、設定錯、沒用 root 開回 1）。
- 其餘：用 `unshare --user --map-root-user --map-auto` 當假 root——namespace 裡自己是 root，
  UID 1～65536 對到 /etc/subuid 的子 UID，所以 `/etc/passwd` 裡的系統帳號（預設帳號、daemon、nobody）
  切得過去。拿不到（沒有 subuid、沒有那幾個帳號）就整組跳過，要等真 root 手動驗。
  別的 UID 進不了 /home/lorkhan（700），所以整份 src/py 先複製到 /tmp 底下 755 的資料夾再跑；
  測試資料夾 chmod 777。預設帳號用 http（Arch）；沒有就依序試 www-data（Debian／Ubuntu）、bin、sys。
  別的帳號用 daemon 與 nobody；補充群組照系統查（Arch 的 daemon 有 adm、bin，Ubuntu 沒有）。
  `Policies` 也要這三個帳號存在，找不到就跳過。
"""
import os
import unittest

from _daemon_util import DaemonCase
from _account_util import DEFAULT, OTHER, THIRD, _have

import aos_daemon_account as acc


USERS_SKIP = (None if all(_have(n) for n in (DEFAULT, OTHER, THIRD))
              else "系統沒有測試要的帳號（%s、%s、%s）" % (DEFAULT, OTHER, THIRD))


class Item:
    def __init__(self, inst, user=None):
        self.inst, self.user = inst, user


class Names(unittest.TestCase):

    def test_match(self):
        self.assertTrue(acc.match("agent-*", "agent-1"))
        self.assertTrue(acc.match("agent-*", "agent-"))
        self.assertFalse(acc.match("agent-*", "agen"))
        self.assertTrue(acc.match("*", "anyone"))
        self.assertTrue(acc.match("bob", "bob"))
        self.assertFalse(acc.match("bob", "bobby"))


@unittest.skipIf(USERS_SKIP is not None, USERS_SKIP or "")
class Policies(unittest.TestCase):
    """名單與預設帳號（不用 root：只查 /etc/passwd）。"""

    def pol(self, conf, env=None):
        return acc.Policy(conf, env or {})

    def bad(self, conf, env=None, text=None):
        with self.assertRaises(acc.AccountError) as cm:
            self.pol(conf, env)
        if text:
            self.assertIn(text, str(cm.exception))

    def test_default_user(self):
        self.assertEqual(self.pol({"user": DEFAULT}).default, DEFAULT)
        self.assertEqual(self.pol({}, {"SUDO_USER": DEFAULT}).default, DEFAULT)
        self.assertEqual(self.pol({"user": DEFAULT}, {"SUDO_USER": OTHER}).default, DEFAULT)
        self.bad({}, text="沒有預設帳號")
        self.bad({}, {"SUDO_USER": ""}, text="沒有預設帳號")
        self.bad({"user": "root"}, text="root")
        self.bad({"user": "aos-no-such-user"}, text="no such user")
        self.bad({"user": 3})
        self.bad([])

    def test_patterns(self):
        self.bad({"user": DEFAULT, "allow": "x"})
        self.bad({"user": DEFAULT, "allow": [""]})
        self.bad({"user": DEFAULT, "allow": ["a*b"]}, text="結尾")
        self.bad({"user": DEFAULT, "deny": ["**"]}, text="結尾")
        self.pol({"user": DEFAULT, "allow": ["*", "agent-*"]})

    def test_deny_default(self):
        # allow 不寫（第十三批）與有寫（A7）都算設定錯；前綴、單獨 * 也算比到
        for conf in ({"deny": [DEFAULT]}, {"deny": [DEFAULT[:2] + "*"]}, {"deny": ["*"]},
                     {"allow": ["*"], "deny": [DEFAULT]}):
            self.bad(dict(conf, user=DEFAULT), text="deny 比得到預設帳號")

    def test_allowed(self):
        p = self.pol({"user": DEFAULT, "allow": [THIRD[:2] + "*", OTHER], "deny": [THIRD]})
        self.assertTrue(p.allowed(DEFAULT))             # 預設帳號不受名單管
        self.assertTrue(p.allowed(OTHER))
        self.assertFalse(p.allowed(THIRD))              # 黑名單優先
        self.assertFalse(p.allowed("root"))             # root 一律不准
        self.assertFalse(self.pol({"user": DEFAULT, "allow": ["*"]}).allowed("root"))
        self.assertFalse(self.pol({"user": DEFAULT}).allowed(OTHER))   # allow 不寫＝空
        with self.assertRaises(acc.AccountError):
            p.allowed("aos-no-such-user")

    def test_check_items(self):
        p = self.pol({"user": DEFAULT, "allow": [OTHER]})
        p.check_items([Item("a"), Item("b", OTHER), Item("c", DEFAULT)])
        for user in (THIRD, "root", "aos-no-such-user"):
            with self.assertRaises(acc.AccountError):
                p.check_items([Item("a"), Item("x", user)])

    def test_item_user(self):
        self.assertIsNone(acc.item_user({}))
        self.assertEqual(acc.item_user({"account": {"user": "bob"}}), "bob")
        self.assertIsNone(acc.item_user({"account": {}}))
        with self.assertRaises(acc.AccountError):
            acc.item_user({"account": "bob"})


class NotRoot(DaemonCase):

    def test_not_root_exits_1(self):
        if os.geteuid() == 0:
            self.skipTest("測試本身是 root")
        self.inst({"argv": ["true"]}, "a.json")
        r = self.run_cfg(self.config({"interval_ms": 1000, "modules": {"account": {"user": DEFAULT}},
                                      "insts": {"a.json": {}}}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-daemon: account: 掛了 modules.account 要用 root 開", r.stderr)

    def test_unmounted_ignores_account_key(self):
        # 模組沒掛：每項的 account 照不認得的鍵忽略（寫壞了也不管）
        self.inst({"argv": ["true"]}, "a.json")
        _, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"a.json": {"account": "x"}}}))
        self.wait_for(lambda: self.results(out, "a.json") == [0])


class ReloadKeepsAccount(DaemonCase):
    """重讀設定照開起來時有沒有掛帳號模組決定讀不讀每項的 account（拿掉 modules.account 不偷換帳號）。"""

    def test_account_flag(self):
        import aos_daemon
        cfg = self.config({"interval_ms": 1000, "insts": {"a": {"account": {"user": "bob"}}, "b": {}}})
        self.assertEqual([i.user for i in aos_daemon.load_full(cfg).items], [None, None])
        self.assertEqual([i.user for i in aos_daemon.load_full(cfg, account=True).items], ["bob", None])
        cfg = self.config({"interval_ms": 1000, "modules": {"account": {}},
                           "insts": {"a": {"account": {"user": "bob"}}}})
        self.assertEqual([i.user for i in aos_daemon.load_full(cfg, account=False).items], [None])


class RootSide(DaemonCase):
    """root 端不用 root 就能驗的部分：框只認自己子樹底下的 i-<h>；exec 前訊號恢復預設、多的 fd 關掉。"""

    def test_frame_ok(self):
        import aos_daemon_root as r
        root = "/sys/fs/cgroup/user.slice/x.scope"
        good = root + "/i-0123456789abcdef"
        self.assertTrue(r.frame_ok(root, None))
        self.assertTrue(r.frame_ok(root, good))
        for bad in ("/etc", root + "/i-0123456789abcdef/..", root + "/../i-0123456789abcdef",
                    root + "/daemon", root + "/i-0123456789ABCDEF", root + "/x/i-0123456789abcdef",
                    "i-0123456789abcdef", 5):
            self.assertFalse(r.frame_ok(root, bad), bad)
        self.assertFalse(r.frame_ok(None, good))                     # cgroup 模組沒掛：有框一律不收

    def test_stdio_signals_and_fds(self):
        # 子程序裡先把 SIGINT／SIGHUP 設成忽略（像 root 端那樣），stdio() 之後 exec sh：
        # 三個訊號都不再被忽略、收到的兩個 fd 只剩 1／2
        code = r"""
import os, signal, sys
sys.path.insert(0, %r)
import aos_daemon_root
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
r, w = os.pipe()
a, b = os.dup(w), os.dup(w)
os.set_inheritable(a, True); os.set_inheritable(b, True)
pid = os.fork()
if pid == 0:
    aos_daemon_root.stdio(a, b)
    os.execv("/bin/sh", ["sh", "-c",
        'grep SigIgn /proc/$$/status; for f in %%d %%d; do [ -e /proc/$$/fd/$f ] && echo open$f; done' %% (a, b)])
os.close(w); os.close(a); os.close(b)
print(os.read(r, 4096).decode(), end="")
os.waitpid(pid, 0)
""" % os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
        import subprocess
        from _util import PY
        out = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=10).stdout
        lines = out.splitlines()
        self.assertEqual(len(lines), 1, out)                          # 沒有 open<fd>
        mask = int(lines[0].split()[1], 16)
        for sig in (1, 2, 13):                                         # HUP、INT、PIPE
            self.assertFalse(mask & (1 << (sig - 1)), out)


if __name__ == "__main__":
    unittest.main()
