"""訊息模組驗收（plan m3m 模組四；使用者 2026-10-02 第二十五批改成多扇門）。真的開 bin/aos-daemon 與 bin/aos-mq。

本檔：一扇門的寄、取、看、叫醒、錯誤（Send、Wake、Errors）。多扇門、跨 daemon、重讀、權限在 test_mq_doors.py。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。任務裡叫 aos-mq 用 `"$PY" "$MQ"`
（兩個變數由 inst 的 envs 給），不靠 PATH。
"""
import json
import os
import time
import unittest

from _ctl_util import CONTROL
from _mq_util import MQMOD, SUB, MqCase, task


class Send(MqCase):

    def test_task_sends_other_takes(self):
        # a 寄到 S1；b 訂了 S1，每次跑都取信寫進 got；信＝寄的 JSON 原樣
        self.inst(task('"$PY" "$MQ" send "$AOS_DAEMON_MQ_S1" \'{"hi":1}\''), "a.json")
        self.inst(task('"$PY" "$MQ" take "$AOS_DAEMON_MQ_S1" >> got'), "b.json")
        _, out, _ = self.up_mq({"a.json": {}, "b.json": SUB}, 3600000)
        self.wait_for(lambda: self.exists("got") and self.read("got").strip())
        self.assertEqual(self.read("got"), '{"hi":1}\n')
        self.wait_for(lambda: self.results(out, "a.json") == [0])
        self.assertEqual(self.take("b.json"), [])                  # 取過就空了

    def test_fifo_stdin_negative(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": SUB}, 10000)
        for i in range(3):
            self.put(str(i))
        r = self.mq("send", self.mq_sock, "-", stdin='"x"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.put("-5")                                             # 負數不是旗標
        self.put('{"from":"spoof","to":1}')                        # daemon 不看信的內容
        self.assertEqual(self.take("b.json"), [0, 1, 2, "x", -5, {"from": "spoof", "to": 1}])

    def test_take_prints_one_per_line(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": SUB}, 10000)
        self.put("[1]")
        self.put("null")
        r = self.mq("take", self.mq_sock, AOS_DAEMON_INST="b.json")
        self.assertEqual((r.returncode, r.stdout), (0, "[1]\nnull\n"))
        r = self.mq("take", self.mq_sock, AOS_DAEMON_INST="b.json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_peek_does_not_take(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": SUB}, 10000)
        for m in ("1", "2"):
            self.put(m)
        self.assertEqual(self.peek("b.json"), [1, 2])
        self.assertEqual(self.take("b.json"), [1, 2])
        self.assertEqual(self.peek("b.json"), [])

    def test_no_identity_check(self):
        # 能連就能做：報別項的名字也照給（aos-mq 只看 AOS_DAEMON_INST，直接連 socket 也行）
        for n in ("a", "b"):
            self.inst({"argv": ["true"]}, n + ".json")
        self.up_mq({"a.json": {}, "b.json": SUB}, 10000)
        self.put("1")
        self.put("2")
        self.assertEqual(self.send({"peek": "b.json"}, self.mq_sock), {"ok": True, "messages": [1, 2]})
        self.assertEqual(self.take("b.json"), [1, 2])              # 以 b 的名字取，誰都行
        self.assertEqual(self.take("a.json"), [])                  # a 沒訂，沒收到

    def test_nobody_subscribed(self):
        self.inst({"argv": ["true"]}, "b.json")
        self.up_mq({"b.json": {}}, 10000)
        self.put("1")                                              # 沒人訂：照回 0，信丟掉
        self.assertEqual(self.send({"send": 2}, self.mq_sock), {"ok": True})
        self.assertEqual(self.take("b.json"), [])

    def test_relative_to_start_and_removed_on_quit(self):
        self.inst({"argv": ["true"]}, "sub/x.json")
        p, _, _ = self.start(self.config({"cwd": "sub", "interval_ms": 10000,
                                          "modules": {"mq": {"M": "./m", "N": "n"}}, "insts": {"x.json": {}}}))
        self.wait_for(lambda: self.is_sock("sub/m") and self.is_sock("sub/n"))
        p.terminate()
        p.wait()
        self.assertFalse(self.exists("sub/m") or self.exists("sub/n"))

    def test_restart_loses_mail(self):
        self.inst({"argv": ["true"]}, "b.json")
        p, _, _ = self.up_mq({"b.json": SUB}, 10000)
        self.put("1")
        p.terminate()
        p.wait()
        self.up_mq({"b.json": SUB}, 10000)
        self.assertEqual(self.take("b.json"), [])


class Wake(MqCase):
    """每封信都觸發（合併後的）叫醒，照現有急件規則；不訂的不叫。"""

    def test_send_wakes_subscriber_only(self):
        self.inst(task("echo x >> b.runs"), "b.json")
        self.inst(task("echo x >> c.runs"), "c.json")
        self.up_mq({"b.json": SUB, "c.json": {}}, 3600000)
        self.wait_for(lambda: self.exists("b.runs") and self.exists("c.runs"))
        self.put("1")
        self.wait_for(lambda: len(self.read("b.runs").split()) == 2, timeout=1)
        time.sleep(0.3)
        self.assertEqual(len(self.read("c.runs").split()), 1)

    def test_many_while_running_runs_once_more(self):
        self.inst(task('echo s >> log; sleep 0.5; "$PY" "$MQ" take "$AOS_DAEMON_MQ_S1" >> got; echo e >> log'),
                  "b.json")
        self.up_mq({"b.json": SUB}, 3600000)
        self.wait_for(lambda: self.exists("log"))
        for i in range(3):
            self.put(str(i))
        time.sleep(1.6)
        self.assertEqual(self.read("log").split(), ["s", "e", "s", "e"])  # 只補一次
        self.assertEqual([json.loads(l) for l in self.read("got").splitlines()], [0, 1, 2])

    def test_stopped_not_run_paused_runs(self):
        # 已停的項：信收下、不跑；暫停的項：跑一次、照樣暫停（照控制模組 wake）
        self.inst(task("echo x >> s.runs; exit 3"), "s.json")
        self.inst(task("echo x >> p.runs"), "p.json")
        modules = dict(MQMOD, **CONTROL)
        _, out, _ = self.up_mq({"s.json": {"stop_on_nonzero": True, "mq": ["S1"]}, "p.json": SUB}, 3600000, modules)
        self.wait_for(lambda: self.has(out, "inst=s.json stopped") and self.exists("p.runs"))
        self.assertEqual(self.send({"pause": "p.json"}), {"ok": True})
        self.put("1")
        self.wait_for(lambda: len(self.read("p.runs").split()) == 2, timeout=1)
        time.sleep(0.3)
        self.assertEqual(len(self.read("s.runs").split()), 1)
        self.assertEqual(self.take("s.json"), [1])
        self.assertTrue(self.send({"status": "p.json"})["paused"])

    def test_sender_subscribed_wakes_itself(self):
        # 不排除寄件人：自己訂了那扇門，自己也收到、也被叫醒
        self.inst(task('echo x >> runs; [ -e sent ] || { touch sent; "$PY" "$MQ" send "$AOS_DAEMON_MQ_S1" 7; }; '
                       '"$PY" "$MQ" take "$AOS_DAEMON_MQ_S1" >> got'), "a.json")
        self.up_mq({"a.json": SUB}, 3600000)
        self.wait_for(lambda: self.exists("runs") and len(self.read("runs").split()) == 2)
        self.wait_for(lambda: self.read("got") == "7\n")


class WakeMerge(unittest.TestCase):
    """開跑前連來多封只叫一次：直接叫伺服器端的 handle()，那一項的執行緒不開，「開跑前」的窗口就一直開著。"""

    def test_many_before_start_runs_once(self):
        import aos_daemon
        import aos_daemon_mq
        item = aos_daemon.Item(0, "b.json", 3600000, False, None)
        item.doors = ["S1"]
        item.due = time.monotonic() + 3600                       # 照週期還早
        items = {"b.json": item}
        for i in range(3):
            self.assertEqual(aos_daemon_mq.handle(("send", i), items, "S1"), {"ok": True})
        self.assertEqual(item.mailbox, [0, 1, 2])
        with item.cond:
            self.assertIs(aos_daemon._next_run(item), False)        # 跑一次（不帶 keep_schedule）
            self.assertFalse(item.pending)                          # 三封只記了一次，跑掉就沒了
            self.assertGreater(item.due, time.monotonic())          # 下一次要等週期，不會再補跑


class Errors(MqCase):

    def setUp(self):
        super().setUp()
        self.inst({"argv": ["true"]}, "b.json")

    def test_unknown_inst(self):
        self.up_mq({"b.json": SUB}, 10000)
        for cmd in ("take", "peek"):
            r = self.mq(cmd, self.mq_sock, AOS_DAEMON_INST="nope")
            self.assertEqual((r.returncode, r.stderr), (1, "unknown_inst: nope\n"))

    def test_client_errors(self):
        self.up_mq({"b.json": SUB}, 10000)
        s, none = self.mq_sock, os.path.join(self.d, "none.sock")
        me = {"AOS_DAEMON_INST": "b.json"}
        cases = [
            ((), {}, "usage"),
            (("get", s), {}, "usage"),
            (("send", s), {}, "usage"),
            (("send", s, "{bad"), {}, "usage"),
            (("send", s, "1", "2"), {}, "usage"),
            (("send", "--urgent", s, "1"), {}, "usage"),
            (("send", "--socket", s, "b.json", "1"), {}, "usage"),
            (("send", "--all", "1"), {}, "usage"),
            (("take",), me, "usage"),
            (("take", s, "b.json"), me, "usage"),
            (("take", s, "--from", "a"), me, "usage"),
            (("peek", s, "--to"), me, "usage"),
            (("take", s), {}, "no_inst"),
            (("peek", s), {}, "no_inst"),
            (("send", none, "1"), {}, "connect"),
            (("take", none), me, "connect"),
        ]
        for args, env, code in cases:
            r = self.mq(*args, **env)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith(code + ": "), (args, r.stderr))
        self.assertEqual(self.take("b.json"), [])                  # 上面沒有一封寄成功

    def test_bad_request_only_that_connection(self):
        self.up_mq({"b.json": SUB}, 10000)
        for bad in (b"nope\n", b"[]\n", b"{}\n", b'{"msg":1}\n', b'{"send":1,"take":"b.json"}\n',
                    b'{"take":3}\n', b'{"peek":null}\n', b'{"peek":"b.json","take":"b.json"}\n', b'{"send":1'):
            self.assertEqual(self.send(bad, self.mq_sock)["error"], "bad_request", bad)
        self.assertEqual(self.send({"send": None}, self.mq_sock), {"ok": True})     # null 也是一封信
        self.assertEqual(self.send({"send": 1, "from": "x", "urgent": 3}, self.mq_sock), {"ok": True})  # 其餘欄位忽略
        self.assertEqual(self.send({"take": "b.json", "from": [1]}, self.mq_sock),
                         {"ok": True, "messages": [None, 1]})

    def test_config_errors(self):
        # 掛了模組：modules.mq 與每項 mq 不合＝設定錯、回 1
        mods = [{"mq": {}}, {"mq": "./x"}, {"mq": {"a-b": "./x"}}, {"mq": {"A": ""}}, {"mq": {"A": 5}},
                {"mq": {"A": "./x", "B": "x"}}, {"mq": {"A": "./aos.sock"}, "control": {"socket": "aos.sock"}}]
        for m in mods:
            r = self.run_cfg(self.config({"interval_ms": 5, "modules": m, "insts": {"b.json": {}}}))
            self.assertEqual(r.returncode, 1, m)
            self.assertTrue(r.stderr.startswith("aos-daemon: config: "), (m, r.stderr))
        for bad in ({"mq": 5}, {"mq": "S1"}, {"mq": {"subscribe": ["S1"]}}, {"mq": ["NOPE"]}, {"mq": [3]}):
            r = self.run_cfg(self.config({"interval_ms": 5, "modules": MQMOD, "insts": {"b.json": bad}}))
            self.assertEqual(r.returncode, 1, bad)
        # 沒掛模組：每項的 mq 照不認得的鍵忽略
        _, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"b.json": {"mq": 5}}}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])


if __name__ == "__main__":
    unittest.main()
