"""訊息模組驗收（plan m3m-daemon-modules.md 模組四「驗收草稿」）。真的開 bin/aos-daemon 與 bin/aos-mq。

本檔：單一 daemon 內的送收、急件、錯誤（Send、Urgent、Errors）。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。任務裡叫 aos-mq 用 `"$PY" "$MQ"`
（兩個變數由 inst 的 envs 給），不靠 PATH。
"""
import json
import os
import time
import unittest

from _ctl_util import CONTROL
from _mq_util import MQMOD, MqCase, task


class Send(MqCase):

    def test_task_sends_other_takes(self):
        # a 寄給 b；b 每次跑都取信寫進 got；from 自動填 a
        self.inst(task('"$PY" "$MQ" send b.json \'{"hi":1}\''), "a.json")
        self.inst(task('"$PY" "$MQ" take >> got'), "b.json")
        _, out, _ = self.up_mq({"a.json": {}, "b.json": {"interval_ms": 300}}, 10000)
        self.wait_for(lambda: self.exists("got") and self.read("got").strip())
        self.assertEqual(json.loads(self.read("got").splitlines()[0]), self.letter("a.json", {"hi": 1}))
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
        self.assertEqual(self.take("b.json"), [self.letter(None, m) for m in (0, 1, 2, "x", -5)])

    def test_take_own_mailbox_only(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        self.mq("send", "b.json", "[1]")
        r = self.mq("take", AOS_DAEMON_INST="b.json")
        self.assertEqual(r.stdout, '{"from":null,"from_socket":%s,"to":"b.json","msg":[1]}\n' % json.dumps(self.mq_sock))
        r = self.mq("take", "b.json", AOS_DAEMON_INST="b.json")     # 不收 <inst>
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("usage: "))

    def test_take_from_filter(self):
        # a、c 寄給 b、手打寄一封；只取 a 的，其他照順序留著
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        for sender, m in (("a.json", 1), ("c.json", 2), (None, 3), ("a.json", 4)):
            self.mq("send", "b.json", str(m), AOS_DAEMON_INST=sender)
        self.assertEqual(self.take("b.json", "--from", "a.json"),
                         [self.letter("a.json", 1), self.letter("a.json", 4)])
        self.assertEqual(self.take("b.json", "--from", "nobody.json"), [])
        self.assertEqual(self.take("b.json"), [self.letter("c.json", 2), self.letter(None, 3)])

    def mail(self):
        """b 的信箱：a、c、d、null、a 各寄一封（msg 1～5）。"""
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        for sender, m in (("a.json", 1), ("c.json", 2), ("d.json", 3), (None, 4), ("a.json", 5)):
            self.mq("send", "b.json", str(m), AOS_DAEMON_INST=sender)

    @staticmethod
    def msgs(got):
        return [m["msg"] for m in got]

    def test_from_many(self):
        # 第十五批：--from a c 取兩個寄件人的，其他照順序留著
        self.mail()
        self.assertEqual(self.msgs(self.take("b.json", "--from", "a.json", "c.json")), [1, 2, 5])
        self.assertEqual(self.msgs(self.take("b.json")), [3, 4])

    def test_from_nothing_is_null(self):
        # --from 後面不接＝寄件人是 null 的信
        self.mail()
        self.assertEqual(self.take("b.json", "--from"), [self.letter(None, 4)])
        self.assertEqual(self.msgs(self.take("b.json")), [1, 2, 3, 5])

    def test_from_repeated_adds_up(self):
        # --from 可以重複寫、疊加：--from（null）加 --from d
        self.mail()
        self.assertEqual(self.msgs(self.take("b.json", "--from", "--from", "d.json")), [3, 4])
        self.assertEqual(self.msgs(self.take("b.json")), [1, 2, 5])

    def test_peek_does_not_take(self):
        self.mail()
        self.assertEqual(self.msgs(self.peek("b.json")), [1, 2, 3, 4, 5])
        self.assertEqual(self.msgs(self.peek("b.json", "--from", "a.json", "--from")), [1, 4, 5])
        self.assertEqual(self.msgs(self.take("b.json")), [1, 2, 3, 4, 5])  # peek 沒取走
        self.assertEqual(self.peek("b.json"), [])

    def test_flag_after_from(self):
        # --from 收到下一個 -- 開頭的參數為止；take／peek 不認得 --urgent
        self.mail()
        for cmd in ("take", "peek"):
            r = self.mq(cmd, "--from", "a.json", "--urgent", AOS_DAEMON_INST="b.json")
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("usage: "), r.stderr)
        self.assertEqual(self.msgs(self.take("b.json", "--from", "-x")), [])    # -x 不是旗標，是寄件人
        self.assertEqual(self.msgs(self.take("b.json")), [1, 2, 3, 4, 5])

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
        self.assertEqual(self.take("s.json"), [self.letter(None, 1, to="s.json")])
        self.assertTrue(self.send({"status": "p.json"})["paused"])


class Errors(MqCase):

    def setUp(self):
        super().setUp()
        self.inst({"argv": ["true"]}, "b.json")

    def test_unknown_inst(self):
        self.up_mq({"b.json": {}}, 10000)
        for args, env in ((("send", "nope", "1"), {}), (("take",), {"AOS_DAEMON_INST": "nope"}),
                          (("peek",), {"AOS_DAEMON_INST": "nope"})):
            r = self.mq(*args, **env)
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
            (("take", "a"), {"AOS_DAEMON_INST": "b.json"}, "usage"),
            (("peek", "a"), {"AOS_DAEMON_INST": "b.json"}, "usage"),
            (("peek",), {}, "no_inst"),
            (("send", "--from", "b.json", "1"), {}, "usage"),
            (("send", "--socket"), {}, "usage"),
            (("take", "--socket", self.mq_sock), {"AOS_DAEMON_INST": "b.json"}, "usage"),
            (("peek", "--socket", self.mq_sock), {"AOS_DAEMON_INST": "b.json"}, "usage"),
            (("send", "--socket", os.path.join(self.d, "none.sock"), "b.json", "1"), {}, "connect"),
            (("send", "--socket", os.path.join(self.d, "none.sock"), "b.json", "1"), {"AOS_DAEMON_MQ_SOCKET": None}, "connect"),
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
                    b'{"send":"b.json","msg":1,"from":3}\n', b'{"send":"b.json","msg":1,"from_socket":3}\n', b'{"take":"b.json","from":3}\n', b'{"take":"b.json","from":"a.json"}\n', b'{"take":"b.json","from":[]}\n',
                    b'{"peek":"b.json","from":[1]}\n', b'{"peek":"b.json","take":"b.json"}\n', b'{"send":"b.json"'):
            self.assertEqual(self.send(bad, self.mq_sock)["error"], "bad_request", bad)
        self.assertEqual(self.send({"send": "b.json", "msg": None}, self.mq_sock), {"ok": True, "delivered": 1})
        self.assertEqual(self.send({"peek": "b.json", "from": [None, "x"]}, self.mq_sock),
                         {"ok": True, "messages": [self.letter(None, None, None)]})
        self.assertEqual(self.send({"take": "b.json", "msg": 1}, self.mq_sock),
                         {"ok": True, "messages": [self.letter(None, None, None)]})

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


if __name__ == "__main__":
    unittest.main()
