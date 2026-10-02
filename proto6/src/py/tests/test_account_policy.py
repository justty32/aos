"""帳號模組驗收（plan m3m-daemon-modules.md 模組五）。

本檔：一般帳號就能跑的名單比對、設定錯、沒用 root（Names、Policies、NotRoot）。

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


if __name__ == "__main__":
    unittest.main()
