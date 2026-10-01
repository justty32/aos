"""訊息模組驗收（plan m3m-daemon-modules.md 模組四「驗收草稿」）。真的開 bin/aos-daemon 與 bin/aos-mq。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。任務裡叫 aos-mq 用 `"$PY" "$MQ"`
（兩個變數由 inst 的 envs 給），不靠 PATH。
"""
import json
import os
import subprocess
import time

from _util import PY
from test_ctl import CONTROL, CtlCase
from test_daemon import BIN, CLEAN_ENV, sh

MQ = os.path.join(BIN, "aos-mq")
MQMOD = {"mq": {"socket": "./mq.sock"}}


def task(script):
    """inst：sh -c script，環境多帶 PY、MQ。"""
    return sh(script, envs={"PY": PY, "MQ": MQ})


class MqCase(CtlCase):

    @property
    def mq_sock(self):
        return os.path.join(self.d, "mq.sock")

    def up_mq(self, insts, interval_ms, modules=None, **top):
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": modules or MQMOD, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        self.wait_for(lambda: self.exists("mq.sock"))
        return p, out, err

    def mq(self, *args, stdin=None, **env):
        """跑 aos-mq；env 給的變數加在乾淨環境上（給 None＝拿掉）。"""
        e = dict(CLEAN_ENV, AOS_DAEMON_MQ_SOCKET=self.mq_sock)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return subprocess.run([PY, MQ] + list(args), env=e, input=stdin, capture_output=True,
                              text=True, timeout=10)

    def take(self, inst):
        r = self.mq("take", inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in r.stdout.splitlines()]


class Send(MqCase):

    def test_task_sends_other_takes(self):
        # a 寄給 b；b 每次跑都取信寫進 got；from 自動填 a
        self.inst(task('"$PY" "$MQ" send b.json \'{"hi":1}\''), "a.json")
        self.inst(task('"$PY" "$MQ" take >> got'), "b.json")
        _, out, _ = self.up_mq({"a.json": {}, "b.json": {"interval_ms": 300}}, 10000)
        self.wait_for(lambda: self.exists("got") and self.read("got").strip())
        self.assertEqual(json.loads(self.read("got").splitlines()[0]), {"from": "a.json", "msg": {"hi": 1}})
        self.wait_for(lambda: self.results(out, "a.json") == [0])  # b 可能比 a 的那一行先取到信
        self.assertEqual(self.take("b.json"), [])                  # 取過就空了

    def test_fifo_and_from_null(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        for i in range(3):
            self.assertEqual(self.mq("send", "b.json", str(i)).returncode, 0)
        r = self.mq("send", "b.json", "-", stdin='"x"')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.mq("send", "b.json", "-5")                        # 負數不是旗標
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.take("b.json"), [{"from": None, "msg": m} for m in (0, 1, 2, "x", -5)])

    def test_take_defaults_to_own_inst(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        self.mq("send", "b.json", "[1]")
        r = self.mq("take", AOS_DAEMON_INST="b.json")
        self.assertEqual(r.stdout, '{"from":null,"msg":[1]}\n')

    def test_env_given_to_tasks(self):
        self.inst(task('echo "$AOS_DAEMON_MQ_SOCKET ${AOS_DAEMON_INST-none} ${AOS_DAEMON_SOCKET-none}" > env.txt'),
                  "e.json")
        self.up_mq({"e.json": {}}, 10000)
        self.wait_for(lambda: self.exists("env.txt"))
        self.assertEqual(self.read("env.txt").split(), [self.mq_sock, "e.json", "none"])

    def test_relative_to_start_and_removed_on_quit(self):
        self.inst({"argv": ["true"]}, "sub/x.json")
        p, _, _ = self.start(self.config({"cwd": "sub", "interval_ms": 10000,
                                          "modules": {"mq": {"socket": "./m"}}, "insts": {"x.json": {}}}))
        self.wait_for(lambda: self.is_sock("sub/m"))
        p.terminate()
        p.wait()
        self.assertFalse(self.exists("sub/m"))


class Urgent(MqCase):

    def test_urgent_wakes(self):
        self.inst(task("echo x >> runs"), "b.json")
        self.up_mq({"b.json": {}}, 3600000)
        self.wait_for(lambda: self.read("runs").split() == ["x"] if self.exists("runs") else False)
        self.assertEqual(self.mq("send", "b.json", "1").returncode, 0)     # 普通信不叫醒
        time.sleep(0.5)
        self.assertEqual(self.read("runs").split(), ["x"])
        self.assertEqual(self.mq("send", "--urgent", "b.json", "2").returncode, 0)
        self.wait_for(lambda: len(self.read("runs").split()) == 2, timeout=1)

    def test_urgent_while_running_runs_once_more(self):
        self.inst(task('echo s >> log; sleep 0.5; "$PY" "$MQ" take >> got; echo e >> log'), "b.json")
        self.up_mq({"b.json": {}}, 3600000)
        self.wait_for(lambda: self.exists("log"))
        for i in range(3):
            self.assertEqual(self.mq("send", "--urgent", "b.json", str(i)).returncode, 0)
        time.sleep(1.6)
        self.assertEqual(self.read("log").split(), ["s", "e", "s", "e"])  # 只補一次
        self.assertEqual([json.loads(l)["msg"] for l in self.read("got").splitlines()], [0, 1, 2])

    def test_urgent_stopped_not_run_paused_runs(self):
        # 已停的項：信收下、不跑；暫停的項：跑一次（照控制模組 wake）
        self.inst(task("echo x >> s.runs; exit 3"), "s.json")
        self.inst(task("echo x >> p.runs"), "p.json")
        modules = dict(MQMOD, **CONTROL)
        _, out, _ = self.up_mq({"s.json": {"stop_on_nonzero": True}, "p.json": {}}, 3600000, modules)
        self.wait_for(lambda: self.has(out, "inst=s.json stopped") and self.exists("p.runs"))
        self.assertEqual(self.send({"pause": "p.json"}), {"ok": True})
        self.assertEqual(self.mq("send", "--urgent", "s.json", "1").returncode, 0)
        self.assertEqual(self.mq("send", "--urgent", "p.json", "1").returncode, 0)
        self.wait_for(lambda: len(self.read("p.runs").split()) == 2, timeout=1)
        time.sleep(0.3)
        self.assertEqual(len(self.read("s.runs").split()), 1)
        self.assertEqual(self.take("s.json"), [{"from": None, "msg": 1}])
        self.assertTrue(self.send({"status": "p.json"})["paused"])


class Errors(MqCase):

    def setUp(self):
        super().setUp()
        self.inst({"argv": ["true"]}, "b.json")

    def test_unknown_inst(self):
        self.up_mq({"b.json": {}}, 10000)
        for args in (("send", "nope", "1"), ("take", "nope")):
            r = self.mq(*args)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stderr, "unknown_inst: nope\n")

    def test_client_errors(self):
        cases = [
            ((), {}, "usage"),
            (("get",), {}, "usage"),
            (("send", "b.json"), {}, "usage"),
            (("send", "b.json", "{bad"), {}, "usage"),
            (("take", "--urgent"), {}, "usage"),
            (("send", "--loud", "b.json", "1"), {}, "usage"),
            (("take", "a", "b"), {}, "usage"),
            (("take",), {}, "no_inst"),
            (("send", "b.json", "1"), {"AOS_DAEMON_MQ_SOCKET": None}, "no_daemon"),
            (("send", "b.json", "1"), {"AOS_DAEMON_MQ_SOCKET": os.path.join(self.d, "none.sock")}, "connect"),
        ]
        for args, env, code in cases:
            r = self.mq(*args, **env)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith(code + ": "), (args, r.stderr))

    def test_bad_request_only_that_connection(self):
        self.up_mq({"b.json": {}}, 10000)
        for bad in (b"nope\n", b"[]\n", b'{"send":"b.json"}\n', b'{"send":"b.json","take":"b.json"}\n',
                    b'{"send":1,"msg":1}\n', b'{"send":"b.json","msg":1,"urgent":"y"}\n',
                    b'{"send":"b.json","msg":1,"from":3}\n', b'{"send":"b.json"'):
            self.assertEqual(self.send(bad, self.mq_sock)["error"], "bad_request", bad)
        self.assertEqual(self.send({"send": "b.json", "msg": None}, self.mq_sock), {"ok": True})
        self.assertEqual(self.send({"take": "b.json", "msg": 1}, self.mq_sock),
                         {"ok": True, "messages": [{"from": None, "msg": None}]})

    def test_no_socket_key(self):
        r = self.run_cfg(self.config({"interval_ms": 5, "insts": {}, "modules": {"mq": {}}}))
        self.assertEqual(r.returncode, 1)

    def test_restart_loses_mail(self):
        p, _, _ = self.up_mq({"b.json": {}}, 10000)
        self.mq("send", "b.json", "1")
        p.terminate()
        p.wait()
        self.up_mq({"b.json": {}}, 10000)
        self.assertEqual(self.take("b.json"), [])


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
        self.assertEqual(self.take("a.json"), [{"from": None, "msg": 1}])
        self.assertEqual(self.mq("send", "b.json", "3").stderr, "unknown_inst: b.json\n")
        self.config(dict(cfg, insts={"a.json": {}, "b.json": {}}))
        p.send_signal(1)
        self.wait_for(lambda: sum(self.has([l], "reloaded") for l in list(out)) == 2)
        self.assertEqual(self.take("b.json"), [])                  # 加回來＝新的一項，信箱從空的開始


if __name__ == "__main__":
    import unittest
    unittest.main()
