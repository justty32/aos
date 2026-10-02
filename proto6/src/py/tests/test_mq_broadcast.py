"""訊息模組驗收（plan m3m-daemon-modules.md 模組四「驗收草稿」）。真的開 bin/aos-daemon 與 bin/aos-mq。

本檔：跨 daemon、廣播與頻道、重讀（CrossDaemon、Broadcast、WithReload）。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。任務裡叫 aos-mq 用 `"$PY" "$MQ"`
（兩個變數由 inst 的 envs 給），不靠 PATH。
"""
import json
import os
import subprocess
import unittest

from _util import PY
from _daemon_util import CLEAN_ENV
from _mq_util import MQ, MQMOD, MqCase, task


class CrossDaemon(MqCase):
    """第二十一批：跨 daemon＝收件地址前綴是對方 daemon 的 socket 路徑（aos-mq send --socket、aos-ctl --socket）。
    兩個 daemon 各用自己的設定檔（A.json、B.json）與起點資料夾（A/、B/）。"""

    def two(self):
        for name in ("A", "B"):
            self.config({"cwd": name, "interval_ms": 3600000,
                         "modules": {"mq": {"socket": "./mq.sock"}, "control": {"socket": "./aos.sock"}},
                         "insts": {name.lower() + ".json": {}}}, rel=name + ".json")
        self.a_mq, self.b_mq = (os.path.join(self.d, n, "mq.sock") for n in "AB")
        self.b_ctl = os.path.join(self.d, "B", "aos.sock")

    def up(self, name):
        p, out, err = self.start(os.path.join(self.d, name + ".json"))
        self.wait_for(lambda: self.is_sock(name + "/mq.sock") and self.is_sock(name + "/aos.sock"))
        return p, out, err

    def test_send_to_other_daemon_and_reply(self):
        self.two()
        self.inst(task('"$PY" "$MQ" send --socket "$BSOCK" b.json \'{"hi":1}\''), "A/a.json")
        self.inst(task("echo x >> runs"), "B/b.json")
        # a 的任務要拿得到 BSOCK：加進 inst 的 envs
        inst = json.loads(self.read("A/a.json"))
        inst["envs"]["BSOCK"] = self.b_mq
        self.inst(inst, "A/a.json")
        self.up("B")
        _, out_a, _ = self.up("A")
        self.wait_for(lambda: self.results(out_a, "a.json") == [0])
        r = self.mq("take", AOS_DAEMON_MQ_SOCKET=self.b_mq, AOS_DAEMON_INST="b.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = [json.loads(l) for l in r.stdout.splitlines()]
        self.assertEqual(got, [{"from": "a.json", "from_socket": self.a_mq, "to": "b.json", "msg": {"hi": 1}}])
        # 照 from_socket 回信回得去
        r = self.mq("send", "--socket", got[0]["from_socket"], got[0]["from"], '"pong"',
                    AOS_DAEMON_MQ_SOCKET=self.b_mq, AOS_DAEMON_INST="b.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.mq("take", AOS_DAEMON_MQ_SOCKET=self.a_mq, AOS_DAEMON_INST="a.json")
        self.assertEqual([json.loads(l) for l in r.stdout.splitlines()],
                         [{"from": "b.json", "from_socket": self.b_mq, "to": "a.json", "msg": "pong"}])

    def test_relative_socket_from_cwd(self):
        # --socket 的相對路徑以呼叫者的 cwd 為準；沒有自己的 daemon 時 from_socket 是 null
        self.two()
        self.inst({"argv": ["true"]}, "B/b.json")
        self.up("B")
        e = dict(CLEAN_ENV)
        r = subprocess.run([PY, MQ, "send", "--socket", "B/mq.sock", "b.json", "1"], cwd=self.d, env=e,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.mq("peek", AOS_DAEMON_MQ_SOCKET=self.b_mq, AOS_DAEMON_INST="b.json")
        self.assertEqual(json.loads(r.stdout), {"from": None, "from_socket": None, "to": "b.json", "msg": 1})

    def test_ctl_socket_other_daemon(self):
        self.two()
        self.inst(task("echo x >> runs"), "B/b.json")
        self.up("B")
        self.wait_for(lambda: self.exists("B/runs"))
        r = self.ctl("--socket", self.b_ctl, "status", "b.json", AOS_DAEMON_SOCKET=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inst"], "b.json")
        r = self.ctl("wake", "--socket", self.b_ctl, "b.json", AOS_DAEMON_SOCKET=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.wait_for(lambda: len(self.read("B/runs").split()) == 2)
        # 給了 --socket 就要明寫 inst（AOS_DAEMON_INST 是自己 daemon 的名字）
        for args in (("--socket", self.b_ctl, "status"), ("--socket",), ("status", "--socket")):
            r = self.ctl(*args, AOS_DAEMON_INST="b.json")
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: "), (args, r.stderr))
        r = self.ctl("--socket", os.path.join(self.d, "none.sock"), "status", "b.json")
        self.assertTrue(r.stderr.startswith("connect: "), r.stderr)


class Broadcast(MqCase):
    """第二十二批：--all 全體廣播、--channel 頻道（每項設定 mq.subscribe），都不寄給寄件人自己；信多 to；--to 篩選。"""

    def three(self, subs=None, modules=None, interval_ms=3600000):
        subs = subs or {}
        for n in ("a", "b", "c"):
            self.inst({"argv": ["true"]}, n + ".json")
        insts = {n + ".json": ({"mq": {"subscribe": subs[n]}} if n in subs else {}) for n in ("a", "b", "c")}
        return self.up_mq(insts, interval_ms, modules)

    def box(self, inst):
        return self.take(inst)

    def test_all_excludes_sender(self):
        self.three()
        r = self.mq("send", "--all", '{"hi":1}', AOS_DAEMON_INST="a.json")
        self.assertEqual((r.returncode, r.stdout), (0, "2\n"), r.stderr)
        for n in ("b.json", "c.json"):
            self.assertEqual(self.box(n), [self.letter("a.json", {"hi": 1}, to="*")])
        self.assertEqual(self.box("a.json"), [])

    def test_all_from_null_reaches_everyone(self):
        self.three()
        r = self.mq("send", "--all", "1")
        self.assertEqual(r.stdout, "3\n")
        self.assertEqual([len(self.box(n)) for n in ("a.json", "b.json", "c.json")], [1, 1, 1])

    def test_all_from_other_daemon_not_excluded(self):
        # 寄件人的 from_socket 不是這個 daemon 的 socket（跨 daemon 來的）：同名的項不算自己
        self.three()
        other = os.path.join(self.d, "other", "mq.sock")
        r = self.mq("send", "--socket", self.mq_sock, "--all", "1",
                    AOS_DAEMON_MQ_SOCKET=other, AOS_DAEMON_INST="a.json")
        self.assertEqual(r.stdout, "3\n", r.stderr)
        self.assertEqual(self.box("a.json"), [self.letter("a.json", 1, sock=other, to="*")])

    def test_channel_subscribers_only(self):
        self.three({"a": ["deploy"], "b": ["deploy", "alerts"], "c": []})
        r = self.mq("send", "--channel", "deploy", '"v2"', AOS_DAEMON_INST="c.json")
        self.assertEqual(r.stdout, "2\n", r.stderr)
        r = self.mq("send", "--channel", "deploy", '"v3"', AOS_DAEMON_INST="a.json")     # 自己訂了也不收
        self.assertEqual(r.stdout, "1\n")
        r = self.mq("send", "--channel", "nobody", '"x"')                                # 沒人訂：回 0、丟掉
        self.assertEqual((r.returncode, r.stdout), (0, "0\n"))
        self.assertEqual(self.box("a.json"), [self.letter("c.json", "v2", to="#deploy")])
        self.assertEqual(self.box("b.json"), [self.letter("c.json", "v2", to="#deploy"),
                                              self.letter("a.json", "v3", to="#deploy")])
        self.assertEqual(self.box("c.json"), [])

    def test_single_send_prints_nothing(self):
        self.three()
        r = self.mq("send", "b.json", "1")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_urgent_wakes_many(self):
        for n in ("b", "c"):
            self.inst(task("echo x >> %s.runs" % n), n + ".json")
        self.up_mq({"b.json": {}, "c.json": {}}, 3600000)
        self.wait_for(lambda: self.exists("b.runs") and self.exists("c.runs"))
        self.assertEqual(self.mq("send", "--all", "--urgent", "1").stdout, "2\n")
        self.wait_for(lambda: all(len(self.read(n + ".runs").split()) == 2 for n in ("b", "c")), timeout=2)

    def test_reload_changes_subscription(self):
        modules = dict(MQMOD, reload={})
        p, out, _ = self.three({"b": []}, modules)
        self.assertEqual(self.mq("send", "--channel", "x", "1").stdout, "0\n")
        self.config({"interval_ms": 3600000, "modules": modules,
                     "insts": {"a.json": {}, "b.json": {"mq": {"subscribe": ["x"]}}, "c.json": {}}})
        p.send_signal(1)
        self.wait_for(lambda: self.has(out, "reloaded"))
        self.assertEqual(self.mq("send", "--channel", "x", "2").stdout, "1\n")
        self.assertEqual(self.box("b.json"), [self.letter(None, 2, to="#x")])

    def test_to_filter(self):
        self.three({"b": ["deploy"]})
        self.mq("send", "b.json", "1", AOS_DAEMON_INST="a.json")
        self.mq("send", "--all", "2", AOS_DAEMON_INST="a.json")
        self.mq("send", "--channel", "deploy", "3", AOS_DAEMON_INST="a.json")
        msgs = lambda got: [m["msg"] for m in got]
        self.assertEqual(msgs(self.peek("b.json", "--to", "*")), [2])
        self.assertEqual(msgs(self.peek("b.json", "--to", "#deploy", "b.json")), [1, 3])
        self.assertEqual(msgs(self.peek("b.json", "--to")), [])                     # to 不會是 null
        self.assertEqual(msgs(self.take("b.json", "--to", "*", "--from", "a.json")), [2])
        self.assertEqual(msgs(self.take("b.json")), [1, 3])

    def test_usage_three_way(self):
        self.three()
        for args in (("send", "--all", "b.json", "1"), ("send", "--all", "--channel", "x", "1"),
                     ("send", "1"), ("send", "--channel"), ("send", "--channel", "x", "b.json", "1"),
                     ("send", "--channel", "x", "--channel", "y", "1")):
            r = self.mq(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("usage: "), (args, r.stderr))
        for cmd in ("take", "peek"):
            for flag in ("--all", "--channel"):
                r = self.mq(cmd, flag, AOS_DAEMON_INST="b.json")
                self.assertTrue(r.stderr.startswith("usage: "), (cmd, flag, r.stderr))

    def test_bad_requests(self):
        self.three()
        for bad in (b'{"broadcast":1,"msg":1}\n', b'{"broadcast":false,"msg":1}\n', b'{"channel":"","msg":1}\n',
                    b'{"channel":3,"msg":1}\n', b'{"broadcast":true}\n', b'{"broadcast":true,"send":"b.json","msg":1}\n',
                    b'{"take":"b.json","to":[]}\n', b'{"peek":"b.json","to":"*"}\n'):
            self.assertEqual(self.send(bad, self.mq_sock)["error"], "bad_request", bad)
        self.assertEqual(self.send({"broadcast": True, "msg": 1}, self.mq_sock), {"ok": True, "delivered": 3})
        self.assertEqual(self.send({"channel": "x", "msg": 1}, self.mq_sock), {"ok": True, "delivered": 0})

    def test_subscribe_config(self):
        # 掛了模組時 mq.subscribe 格式不對＝設定錯；沒掛時 "mq" 照不認得的鍵忽略
        self.inst({"argv": ["true"]}, "b.json")
        for bad in ({"mq": 5}, {"mq": {"subscribe": "x"}}, {"mq": {"subscribe": [""]}}, {"mq": {"subscribe": [3]}}):
            r = self.run_cfg(self.config({"interval_ms": 5, "modules": MQMOD, "insts": {"b.json": bad}}))
            self.assertEqual(r.returncode, 1, bad)
        _, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"b.json": {"mq": 5}}}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])


class WithReload(MqCase):

    def test_kept_item_keeps_mail_removed_drops(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        modules = dict(MQMOD, reload={})
        cfg = {"interval_ms": 10000, "modules": modules, "insts": {"a.json": {}, "b.json": {}}}
        p, out, _ = self.up_mq(cfg["insts"], 10000, modules)
        self.mq("send", "a.json", "1")
        self.mq("send", "b.json", "2")
        self.config(dict(cfg, insts={"a.json": {}, "c.json": {}}))
        self.inst({"argv": ["true"]}, "c.json")
        p.send_signal(1)
        self.wait_for(lambda: self.has(out, "reloaded"))
        self.assertEqual(self.take("a.json"), [self.letter(None, 1, to="a.json")])
        self.assertEqual(self.mq("send", "b.json", "3").stderr, "unknown_inst: b.json\n")
        self.config(dict(cfg, insts={"a.json": {}, "b.json": {}}))
        p.send_signal(1)
        self.wait_for(lambda: sum(self.has([l], "reloaded") for l in list(out)) == 2)
        self.assertEqual(self.take("b.json"), [])                  # 加回來＝新的一項，信箱從空的開始


if __name__ == "__main__":
    unittest.main()
