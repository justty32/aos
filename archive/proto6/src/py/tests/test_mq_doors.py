"""訊息模組驗收（使用者 2026-10-02 第二十五批：多扇門、訂閱、環境變數、跨 daemon、重讀、socket 權限）。

真的開 bin/aos-daemon、bin/aos-mq、bin/aos-ctl。都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。
"""
import json
import os
import stat
import subprocess
import unittest

from _util import PY
from _ctl_util import CONTROL
from _daemon_util import CLEAN_ENV
from _mq_util import MQ, MqCase, task

DOORS = {"mq": {"S1": "./s1.sock", "ALERTS": "./alerts.sock"}}


class Doors(MqCase):

    def three(self, subs, modules=None, interval_ms=3600000):
        for n in ("a", "b", "c"):
            self.inst({"argv": ["true"]}, n + ".json")
        insts = {n + ".json": ({"mq": subs[n]} if n in subs else {}) for n in ("a", "b", "c")}
        p = self.up_mq(insts, interval_ms, modules or DOORS)
        self.s1, self.alerts = (os.path.join(self.d, f) for f in ("s1.sock", "alerts.sock"))
        return p

    def test_each_door_reaches_its_subscribers(self):
        self.three({"a": ["S1"], "b": ["S1", "ALERTS", "S1"], "c": []})   # 同一扇門寫兩次照一次算
        self.put('"one"', self.s1)
        self.put('"alert"', self.alerts)
        self.put('"two"', self.s1)
        self.assertEqual(self.take("a.json", sock=self.s1), ["one", "two"])
        self.assertEqual(self.take("b.json", sock=self.alerts), ["one", "alert", "two"])  # 哪扇門取都一樣
        self.assertEqual(self.take("c.json", sock=self.s1), [])

    def test_env_every_door_for_every_item(self):
        # 沒訂的項也拿到每一扇門；舊名 AOS_DAEMON_MQ_SOCKET、AOS_DAEMON_SOCKET 不再給
        self.inst(task('echo "$AOS_DAEMON_MQ_S1 $AOS_DAEMON_MQ_ALERTS ${AOS_DAEMON_INST-none} '
                       '${AOS_DAEMON_MQ_SOCKET-none} ${AOS_DAEMON_SOCKET-none} $AOS_DAEMON_CTL_SOCKET" > env.txt'),
                  "e.json")
        self.up_mq({"e.json": {}}, 3600000, dict(DOORS, **CONTROL))
        self.wait_for(lambda: self.exists("env.txt"))
        self.assertEqual(self.read("env.txt").split(),
                         [os.path.join(self.d, "s1.sock"), os.path.join(self.d, "alerts.sock"), "e.json",
                          "none", "none", self.sock])

    def test_sockets_666(self):
        # 控制與訊息 socket 一律 666（沒掛帳號模組也一樣）；誰能連看所在資料夾
        old = os.umask(0o077)
        try:
            self.inst({"argv": ["true"]}, "a.json")
            self.up_mq({"a.json": {}}, 3600000, dict(DOORS, **CONTROL))
            self.wait_for(lambda: self.is_sock())
        finally:
            os.umask(old)
        mode = lambda f: stat.S_IMODE(os.stat(os.path.join(self.d, f)).st_mode)
        for f in ("s1.sock", "alerts.sock", "aos.sock"):           # umask 077 下 bind 出來是 700，緊接著 chmod
            self.wait_for(lambda: mode(f) == 0o666)

    def test_reload(self):
        modules = dict(DOORS, reload={})
        p, out, err = self.three({"b": ["S1"]}, modules)
        self.put("1", self.s1)
        # b 改訂 ALERTS、c 訂 S1：照新設定
        self.config({"interval_ms": 3600000, "modules": modules,
                     "insts": {"a.json": {}, "b.json": {"mq": ["ALERTS"]}, "c.json": {"mq": ["S1"]}}})
        p.send_signal(1)
        self.wait_for(lambda: self.has(out, "reloaded"))
        self.put("2", self.s1)
        self.put("3", self.alerts)
        self.assertEqual(self.take("b.json", sock=self.s1), [1, 3])        # 還在的項信照留
        self.assertEqual(self.take("c.json", sock=self.s1), [2])
        # 寫了開起來時沒有的門：重讀出錯、整份不套用（就算新的 modules.mq 有那扇門）
        self.config({"interval_ms": 3600000, "modules": {"mq": {"S1": "./s1.sock", "NEW": "./n.sock"}, "reload": {}},
                     "insts": {"a.json": {"mq": ["NEW"]}, "b.json": {}, "c.json": {}}})
        p.send_signal(1)
        self.wait_for(lambda: any(l.startswith("aos-daemon: reload: ") for l in list(err)))
        self.put("4", self.s1)
        self.assertEqual(self.take("c.json", sock=self.s1), [4])           # 舊設定照跑
        # modules.mq 改了：不套用、警告；拿掉的項信箱一起丟、加回來從空的開始
        self.put("5", self.s1)
        self.config({"interval_ms": 3600000, "modules": {"mq": {"S1": "./other.sock"}, "reload": {}},
                     "insts": {"a.json": {}, "b.json": {}}})
        p.send_signal(1)
        self.wait_for(lambda: sum(self.has([l], "reloaded") for l in list(out)) == 2)
        self.assertTrue(self.has(out, "reload: need restart: modules"))
        self.assertFalse(self.exists("other.sock"))
        self.assertEqual(self.mq("take", self.s1, AOS_DAEMON_INST="c.json").stderr, "unknown_inst: c.json\n")
        self.config({"interval_ms": 3600000, "modules": modules,
                     "insts": {"a.json": {}, "b.json": {}, "c.json": {"mq": ["S1"]}}})
        p.send_signal(1)
        self.wait_for(lambda: sum(self.has([l], "reloaded") for l in list(out)) == 3)
        self.assertEqual(self.take("c.json", sock=self.s1), [])


class CrossDaemon(MqCase):
    """跨 daemon：send 的路徑寫對方的門即可；aos-ctl --socket 照留。兩個 daemon 各用自己的設定檔與起點資料夾。"""

    def two(self):
        for name in ("A", "B"):
            self.config({"cwd": name, "interval_ms": 3600000,
                         "modules": {"mq": {"IN": "./mq.sock"}, "control": {"socket": "./aos.sock"}},
                         "insts": {name.lower() + ".json": {"mq": ["IN"]}}}, rel=name + ".json")
        self.a_mq, self.b_mq = (os.path.join(self.d, n, "mq.sock") for n in "AB")
        self.b_ctl = os.path.join(self.d, "B", "aos.sock")

    def up(self, name):
        p, out, err = self.start(os.path.join(self.d, name + ".json"))
        self.wait_for(lambda: self.is_sock(name + "/mq.sock") and self.is_sock(name + "/aos.sock"))
        return p, out, err

    def test_send_to_other_daemon_wakes(self):
        self.two()
        inst = task('"$PY" "$MQ" send "$BSOCK" \'{"hi":1}\'')
        inst["envs"]["BSOCK"] = self.b_mq
        self.inst(inst, "A/a.json")
        self.inst(task("echo x >> runs"), "B/b.json")
        self.up("B")
        self.wait_for(lambda: self.exists("B/runs"))
        _, out_a, _ = self.up("A")
        self.wait_for(lambda: self.results(out_a, "a.json") == [0])
        self.wait_for(lambda: len(self.read("B/runs").split()) == 2)      # 跨 daemon 來的信也叫醒
        self.assertEqual(self.take("b.json", sock=self.b_mq), [{"hi": 1}])
        self.assertEqual(self.take("a.json", sock=self.a_mq), [])

    def test_relative_path_from_cwd(self):
        self.two()
        self.inst({"argv": ["true"]}, "B/b.json")
        self.up("B")
        r = subprocess.run([PY, MQ, "send", "B/mq.sock", "1"], cwd=self.d, env=dict(CLEAN_ENV),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.peek("b.json", sock=self.b_mq), [1])

    def test_ctl_socket_other_daemon(self):
        self.two()
        self.inst(task("echo x >> runs"), "B/b.json")
        self.up("B")
        self.wait_for(lambda: self.exists("B/runs"))
        r = self.ctl("--socket", self.b_ctl, "status", "b.json", AOS_DAEMON_CTL_SOCKET=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inst"], "b.json")
        r = self.ctl("wake", "--socket", self.b_ctl, "b.json", AOS_DAEMON_CTL_SOCKET=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.wait_for(lambda: len(self.read("B/runs").split()) == 2)
        # 給了 --socket 就要明寫 inst（AOS_DAEMON_INST 是自己 daemon 的名字）
        for args in (("--socket", self.b_ctl, "status"), ("--socket",), ("status", "--socket")):
            r = self.ctl(*args, AOS_DAEMON_INST="b.json")
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: "), (args, r.stderr))
        r = self.ctl("--socket", os.path.join(self.d, "none.sock"), "status", "b.json")
        self.assertTrue(r.stderr.startswith("connect: "), r.stderr)
        # 舊名 AOS_DAEMON_SOCKET 不再認
        r = self.ctl("status", "b.json", AOS_DAEMON_CTL_SOCKET=None, AOS_DAEMON_SOCKET=self.b_ctl)
        self.assertTrue(r.stderr.startswith("no_daemon: "), r.stderr)


if __name__ == "__main__":
    unittest.main()
