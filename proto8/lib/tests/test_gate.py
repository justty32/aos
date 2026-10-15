"""proto8/lib 的自動測試：LLM kernel（閘門 aos_gate ＋ 身體 aos_gate_kernel）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

排序類：直接用 aos_gate.post() 丟信、在本行程呼叫 aos_gate_kernel.tick()，看 log 的順序。
端到端：閘門起真的行程，kernel 在背景執行緒一拍一拍跑。
"""
import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time

from helpers import INST, LIB, Tmp
from test_agent import _Stub

import aos_gate
import aos_gate_kernel as K

GATE = os.path.join(LIB, "aos_gate.py")


class KernelOrderTest(Tmp):
    def setUp(self):
        super().setUp()
        self.box = aos_gate.mailbox(self.p("mb"))
        self.cfg = K.check({"mailbox": self.p("mb"), "state": self.p("k.state.json"), "log": self.p("log.jsonl")})

    def send(self, who, priority=None, meta=None, sh="cat"):
        doc = {"argv": ["sh", "-c", sh], "cwd": self.tmp,                     # 信＝那張 inst 本身＋私有 key
               "priority": aos_gate.normalize_priority(priority), "sent": time.time()}
        if meta is not None:
            doc["_metainfo"] = meta
        name = aos_gate.post(self.box, doc, who)
        time.sleep(0.002)               # 名字＝奈秒時間，保證先後
        return name

    def reply(self, name):
        with open(os.path.join(self.box["reply"], name)) as f:
            return json.load(f)

    def stdout(self, name):
        with open(aos_gate.side(os.path.join(self.box["reply"], name), "stdout")) as f:
            return f.read()

    def drain(self, n=20):
        order = []
        for _ in range(n):
            out = K.tick(self.cfg)
            order += [self.stdout(s["letter"]) for s in out["served"]]
            if not out["waiting"]:
                break
        return order

    def test_level_order(self):
        self.send("a", "low")
        self.send("b")
        self.send("c", {"level": "high", "class": "chat"})       # 不認得的 key 照帶
        self.send("d", 0)
        self.send("e", 5)                                        # 數字取正負號＝high
        self.assertEqual(self.drain(), ["c", "e", "b", "d", "a"])

    def test_deadline_jump_and_within_level(self):
        far = time.time() + 3600
        self.send("a", "high")
        self.send("b", {"level": "low", "deadline": time.time() + 10})      # 剩不到 near_ms＝插隊
        self.send("c", {"deadline": far + 10})
        self.send("d", {"deadline": datetime_iso(far)})                       # ISO 字串也收；同級 deadline 近的先
        self.send("e")
        self.assertEqual(self.drain(), ["b", "a", "d", "c", "e"])

    def test_deadline_passed_dropped(self):
        n = self.send("late", {"level": "high", "deadline": time.time() - 1})
        self.send("ok")
        out = K.tick(self.cfg)
        self.assertEqual(out["dropped"], [{"letter": n, "error": "DeadlineMissed"}])
        self.assertEqual(self.reply(n)["error"]["code"], "DeadlineMissed")
        self.assertEqual(len(out["served"]), 1)
        self.assertEqual(os.listdir(self.box["new"]) + os.listdir(self.box["cur"]), [])

    def test_aging(self):
        self.send("low", "low")
        order = []
        for i in range(14):                                       # 每拍來一封新的 normal、跑一封
            self.send("n%02d" % i)
            order += [self.stdout(s["letter"]) for s in K.tick(self.cfg)["served"]]
        # 沒 aging＝low 永遠輪不到；等滿 10 拍升成 normal，又是最早來的，第 11 拍輪到它
        self.assertEqual(order.index("low"), 10)

    def test_metainfo_cost_then_fifo(self):
        self.send("a", meta={"cost": 5})
        self.send("b", meta={"cost": 1})
        self.send("c")                                           # 沒寫 cost＝0
        self.send("d", meta={"other": 1})
        self.assertEqual(self.drain(), ["c", "d", "b", "a"])

    def test_budget_exhausted(self):
        cfg = dict(self.cfg, budget=10)
        self.send("x", sh='cat >/dev/null; echo \'{"role":"assistant","content":"x","usage":{"total_tokens":12}}\'')
        n2 = self.send("y")
        out = K.tick(dict(cfg, slots=1))
        self.assertEqual(out["budget"]["used"], 12)
        out = K.tick(cfg)
        self.assertEqual(out["dropped"], [{"letter": n2, "error": "BudgetExhausted"}])
        st = json.loads(self.read("k.state.json"))
        st["budget"]["day"] = "2000-01-01"                       # 換日＝歸零
        self.write("k.state.json", st)
        self.send("z")
        self.assertEqual(len(K.tick(cfg)["served"]), 1)

    def test_cur_letter_on_restart_is_error(self):
        n = self.send("half")
        os.rename(os.path.join(self.box["new"], n), os.path.join(self.box["cur"], n))   # 上一拍跑一半被殺
        out = K.tick(self.cfg)
        self.assertEqual(out["dropped"], [{"letter": n, "error": "KernelRestarted"}])
        self.assertEqual(self.reply(n)["error"]["code"], "KernelRestarted")
        self.assertEqual(os.listdir(self.box["cur"]), [])

    def test_slots(self):
        for w in "abc":
            self.send(w, sh="sleep 0.3; cat")
        t0 = time.monotonic()
        out = K.tick(dict(self.cfg, slots=2))
        self.assertEqual((len(out["served"]), out["waiting"]), (2, 1))
        self.assertLess(time.monotonic() - t0, 0.55)              # 兩封一起跑

    def test_letter_is_inst_and_reply_is_result(self):
        """信＝target 那張 inst（key 攤平）＋priority／reply／sent，stdin＝旁檔；回信＝aos_inst 的結果（N-30）。"""
        self.write("t.json", {"argv": ["sh", "-c", "cat; echo e >&2; exit 3"], "timeout_ms": 5000,
                              "_metainfo": {"cost": 2}})
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            box, doc = aos_gate.letter({"target": "t.json", "mailbox": self.p("mb"), "priority": "high"})
        finally:
            os.chdir(old)
        name = aos_gate.post(box, doc, "hi")
        with open(os.path.join(self.box["new"], name)) as f:
            lt = json.load(f)
        self.assertEqual((lt["argv"][0], lt["timeout_ms"], lt["_metainfo"], lt["priority"], lt["cwd"]),
                         ("sh", 5000, {"cost": 2}, {"level": "high"}, os.path.realpath(self.tmp)))
        self.assertEqual(lt["id"], os.path.realpath(self.p("t.json")))
        self.assertNotIn("kind", lt)
        self.assertEqual(lt["reply"], os.path.join(self.box["reply"], name))
        with open(lt["stdin"]) as f:
            self.assertEqual(f.read(), "hi")
        K.tick(self.cfg)
        rep = self.reply(name)
        self.assertEqual(set(rep), {"id", "code", "signal", "timed_out", "pid", "ms", "exit_file"})
        self.assertEqual((rep["code"], rep["id"]), (3, lt["id"]))
        self.assertEqual(aos_gate.outputs(self.box, name), ("hi", "e\n"))
        self.assertEqual(os.listdir(self.box["reply"]), [])                  # 回信與旁檔都收掉了

    def test_bad_config(self):
        with self.assertRaises(K.KernelError) as e:
            K.check({"mailbox": "m"})
        self.assertEqual(e.exception.code, "WindowMissing")


def datetime_iso(t):
    import datetime
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat()


class GateEndToEndTest(Tmp):
    """閘門真的起行程；kernel 在背景執行緒每 50 ms 拍一次。"""

    def setUp(self):
        super().setUp()
        self.cfg = K.check({"mailbox": self.p("mb"), "state": self.p("k.state.json")})
        self.box = aos_gate.mailbox(self.p("mb"))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.stop = threading.Event()
        self.running = threading.Event()

    def kernel(self):
        def beat():
            while not self.stop.is_set():
                if self.running.is_set():
                    K.tick(self.cfg)
                time.sleep(0.05)
        t = threading.Thread(target=beat, daemon=True)
        t.start()
        self.addCleanup(t.join)
        self.addCleanup(self.stop.set)
        self.running.set()

    def gate(self, target, **keys):
        self.write("gate.json", dict({"target": target, "mailbox": self.p("mb")}, **keys))
        return [sys.executable, GATE, self.p("gate.json")]

    def test_identical_to_direct_call(self):
        self.kernel()
        sh = 'read x; echo "{\\"got\\": \\"$x\\"}"; echo \'{"error":{"code":"E","msg":"m"}}\' >&2; exit 4'
        self.write("t.json", {"argv": ["sh", "-c", sh], "_metainfo": {"cost": 1}})
        self.write("in.txt", "hello\n")
        res = {}
        for name, inst in (("direct", self.p("t.json")),
                           ("gated", {"argv": self.gate("t.json"), "cwd": self.tmp})):
            if isinstance(inst, str):
                inst = json.loads(self.read("t.json"))
                inst.pop("_metainfo")
            doc = dict(inst, stdin=self.p("in.txt"), stdout=self.p(name + ".out"), stderr=self.p(name + ".err"),
                       cwd=self.tmp)
            r = subprocess.run([sys.executable, INST, "-"], input=json.dumps(doc), capture_output=True, text=True,
                               env=self.env, cwd=self.tmp, timeout=20)
            res[name] = json.loads(r.stdout)
        self.assertEqual(res["direct"]["code"], 4)
        self.assertEqual(res["gated"]["code"], 4)
        self.assertEqual(self.read("direct.out"), self.read("gated.out"))
        self.assertEqual(self.read("direct.err"), self.read("gated.err"))
        self.assertEqual(os.listdir(self.box["reply"]), [])                  # 閘門讀完旁檔就刪

    def test_env_priority_and_plain_stdin(self):
        self.kernel()
        r = subprocess.run(self.gate({"argv": ["cat"]}), input="abc", capture_output=True, text=True,
                           env=dict(self.env, AOS_PRIORITY="high"), cwd=self.tmp, timeout=20)
        self.assertEqual((r.returncode, r.stdout), (0, "abc"))

    def test_queue_timeout_withdraws(self):
        r = subprocess.run(self.gate({"argv": ["cat"]}, wait_ms=200), input="x", capture_output=True, text=True,
                           env=self.env, cwd=self.tmp, timeout=20)          # kernel 沒在拍
        self.assertEqual(r.returncode, 125)
        self.assertEqual(json.loads(r.stderr)["error"]["code"], "QueueTimeout")
        self.assertEqual(os.listdir(self.box["new"]) + os.listdir(self.box["reply"]), [])     # 撤信連 stdin 旁檔

    def test_sigterm_withdraws(self):
        p = subprocess.Popen(self.gate({"argv": ["cat"]}), stdin=subprocess.PIPE, env=self.env, cwd=self.tmp)
        p.stdin.write(b"x")
        p.stdin.close()
        self.until(lambda: os.listdir(self.box["new"]))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 128 + signal.SIGTERM)
        self.assertEqual(os.listdir(self.box["new"]), [])

    def test_kernel_error_and_inst_error_codes(self):
        self.kernel()
        r = subprocess.run(self.gate({"argv": ["no-such-prog-xyz"]}), input="", capture_output=True, text=True,
                           env=self.env, cwd=self.tmp, timeout=20)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (127, "CommandNotFound"))
        r = subprocess.run([sys.executable, GATE, "-"], input="{}", capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (125, "Usage"))

    def test_real_brain_usage_counts_budget(self):
        """真的腦（假伺服器回 usage）經閘門：kernel 額度照 usage.total_tokens 加；think 接進 history 的沒有 usage。"""
        _Stub.seen, _Stub.status = [], 200
        _Stub.reply = {"choices": [{"message": {"role": "assistant", "content": "好"}}], "usage": {"total_tokens": 9}}
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.cfg["budget"] = 1000
        self.kernel()
        brain = os.path.join(LIB, "aos_brain_openai.py")
        self.write("brain.json", {"argv": [sys.executable, brain, "--base-url",
                                           "http://127.0.0.1:%d/v1" % srv.server_port, "--model", "m"]})
        self.write("gated.json", {"argv": self.gate("brain.json"), "cwd": self.tmp})
        self.write("h.json", [{"role": "user", "content": "hi"}])
        cfg = {"brain": "gated.json", "history": "h.json", "work": "work"}
        for _ in range(2):
            r = subprocess.run([sys.executable, os.path.join(LIB, "aos_agent_lib.py"), "think"], cwd=self.tmp,
                               input=json.dumps(cfg), capture_output=True, text=True, env=self.env, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.write("h.json", json.loads(self.read("h.json")) + [{"role": "user", "content": "再一次"}])
        self.until(lambda: json.loads(self.read("k.state.json"))["budget"]["used"] == 18)   # state 在回信之後才寫
        self.assertNotIn("usage", json.dumps(json.loads(self.read("h.json"))))

    def test_kernel_cli_under_loop(self):
        """kernel 的身體照 N-12 當 inst 被 aos-loop 拍（stdout 一份摘要）。"""
        kernel = os.path.join(LIB, "aos_gate_kernel.py")
        r = subprocess.run([sys.executable, kernel, "--mailbox", self.p("mb"), "--state", self.p("k.json")],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["runs"], 1)
        st = json.loads(self.read("k.json"))                     # state 窗用 loop 骨架的名字
        self.assertEqual((st["state"], st["runs"], st["last_error"]), ("waiting", 1, None))
        self.assertIn("beat", st)
        r = subprocess.run([sys.executable, kernel, "--mailbox", self.p("mb")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 125)


if __name__ == "__main__":
    import unittest
    unittest.main()
