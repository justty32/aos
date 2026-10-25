"""LLM kernel 整合（10-24，thinking 2026-10-24-llm-kernel）：aos-gate 寄信、aos-kernel-llm 被 aos-loop／aos-daemon 一次次拍、回信原樣交回。

單元（排序、slots、回信的錯、收拾、鎖）在 impls/aos-kernel-llm、impls/aos-gate 各自的 tests/test_cli.py；這裡只測兩支接起來、
跟 loop／fsm／daemon 一起跑的樣子：端到端、包它那格的 timeout_ms 收掉閘門（撤信）、kernel 不在時信堆著、kernel 死掉後重起、demo/kernel-llm。"""
import http.server, json, os, signal, subprocess, tempfile, threading, time, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

GATE = tool("aos-gate")
KERNEL = tool("aos-kernel-llm")
LOOP = tool("aos-loop")


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


def until(f, secs=15):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        try:
            v = f()
            if v:
                return v
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.02)
    return None


class KernelCase(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.t = Path(self.td.name)
        self.mb = self.t / "mb"
        self.mb.mkdir()
        (self.t / "kst").mkdir()
        (self.t / "kernel.json").write_text(json.dumps({"mailbox": str(self.mb), "slots": 1}))
        (self.t / "loop.json").write_text(json.dumps({"exec": {"argv": ["aos-kernel-llm", "kernel.json"]},
                                                       "interval_ms": 50}))
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            for f in (p.stdout, p.stderr):
                if f:
                    f.close()
        self.td.cleanup()

    def kernel_loop(self):
        p = subprocess.Popen([LOOP, "loop.json"], cwd=self.t, env=env_of({"AOS_STACK": str(self.t / "kst")}),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def gate(self, inst, name="q.json", extra=None):
        (self.t / name).write_text(json.dumps(inst))
        p = subprocess.Popen([GATE, name], cwd=self.t, env=env_of(dict({"AOS_KERNEL": str(self.mb)}, **(extra or {}))),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def test_end_to_end_under_loop(self):
        self.kernel_loop()
        g = self.gate({"argv": ["sh", "-c", 'echo "hi $WHO from $(basename "$PWD")"; echo warn >&2; exit 4'],
                       "priority": "high"}, extra={"WHO": "eve"})
        out, err = g.communicate(timeout=20)
        self.assertEqual((g.returncode, out, err), (4, "hi eve from %s\n" % self.t.name, "warn\n"))
        served = until(lambda: (self.t / "kst" / "served.jsonl").read_text())
        line = json.loads(served.splitlines()[0])
        self.assertEqual((line["level"], line["code"], line["error"]), ("high", 4, None))
        until(lambda: not os.listdir(self.mb / "done"))
        self.assertEqual(os.listdir(self.mb / "done"), [])   # 閘門讀完就刪

    def test_cell_timeout_withdraws(self):
        """包閘門的那格逾時（這裡沒有 kernel，信一直排著）：閘門被 SIGTERM、撤信、那格非 0。"""
        (self.t / "q.json").write_text(json.dumps({"argv": ["true"]}))
        (self.t / "cell.json").write_text(json.dumps({"exec": {"argv": ["aos-gate", "q.json"], "timeout_ms": 400},
                                                       "max": 1}))
        t0 = time.monotonic()
        r = subprocess.run([LOOP, "cell.json"], cwd=self.t, env=env_of({"AOS_KERNEL": str(self.mb)}),
                           capture_output=True, text=True, timeout=30)
        self.assertLess(time.monotonic() - t0, 10)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(os.listdir(self.mb / "new"), [])
        self.assertEqual(os.listdir(self.mb / "tmp"), [])

    def test_kernel_absent_then_started(self):
        g = self.gate({"argv": ["echo", "late"]})
        until(lambda: os.listdir(self.mb / "new"))
        time.sleep(0.3)
        self.assertIsNone(g.poll())   # kernel 不在：信堆著
        self.kernel_loop()
        out, _ = g.communicate(timeout=20)
        self.assertEqual((g.returncode, out), (0, "late\n"))

    def test_high_first_and_slots(self):
        """kernel 還沒起時三封排好，起來後 high 先；slots 2 時兩封一起跑。"""
        gs = [self.gate({"argv": ["sh", "-c", "sleep 0.5; echo %s" % n], "priority": p}, name="%s.json" % n)
              for n, p in (("a", "low"), ("b", "normal"), ("c", "high"))]
        until(lambda: len(os.listdir(self.mb / "new")) == 3)
        self.kernel_loop()
        for g in gs:
            g.communicate(timeout=20)
        served = [json.loads(l) for l in (self.t / "kst" / "served.jsonl").read_text().splitlines()]
        self.assertEqual([s["level"] for s in served], ["high", "normal", "low"])

        (self.t / "kernel.json").write_text(json.dumps({"mailbox": str(self.mb), "slots": 2}))
        gs = [self.gate({"argv": ["sleep", "1"]}, name="s%d.json" % i) for i in range(2)]
        until(lambda: len(os.listdir(self.mb / "new")) == 2)
        t0 = time.monotonic()
        for g in gs:
            g.communicate(timeout=20)
            self.assertEqual(g.returncode, 0)
        self.assertLess(time.monotonic() - t0, 1.9)

    def test_kernel_killed_then_restarted(self):
        """kernel 整群被 SIGKILL（跑信的子行程也死了）→ 重起後那封回 RunFailed、不重跑；閘門退 1。"""
        g = self.gate({"argv": ["sh", "-c", 'echo run >> "%s"; sleep 2' % (self.t / "runs")]})
        until(lambda: os.listdir(self.mb / "new"))
        k = subprocess.Popen([KERNEL, "kernel.json"], cwd=self.t, env=env_of({"AOS_STACK": str(self.t / "kst")}),
                             start_new_session=True)
        until(lambda: (self.t / "runs").exists())
        os.killpg(k.pid, signal.SIGKILL)
        k.wait()
        self.kernel_loop()
        out, err = g.communicate(timeout=20)
        self.assertEqual(g.returncode, 1)
        self.assertTrue(err.startswith("aos-gate: RunFailed "), err)
        self.assertEqual((self.t / "runs").read_text(), "run\n")

    def test_kernel_parent_killed_runner_finishes(self):
        """只殺 kernel 本體、跑信的子行程還活著 → 重起的 kernel 不搶，等它寫好回信再交出去；閘門拿到真結果。"""
        g = self.gate({"argv": ["sh", "-c", "sleep 1; echo done"]})
        until(lambda: os.listdir(self.mb / "new"))
        k = subprocess.Popen([KERNEL, "kernel.json"], cwd=self.t, env=env_of({"AOS_STACK": str(self.t / "kst")}))
        until(lambda: list((self.mb / "cur").glob("*/runner.json")))
        k.kill()
        k.wait()
        self.kernel_loop()
        out, err = g.communicate(timeout=20)
        self.assertEqual((g.returncode, out), (0, "done\n"), err)


class UsageServer:
    """假的 OpenAI 相容 server：每次都回同一個答案，帶 usage（10-24 token 回報）。"""
    def __init__(self, usage):
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": "4"}}], "usage": usage}).encode()

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ReportCase(unittest.TestCase):
    """10-24 token 回報與額度：agent-dan 的 brain.py 經閘門、kernel 跑，把假 server 回的 usage 寫進 AOS_KERNEL_REPORT。"""
    DAN = ROOT / "demo" / "agent-dan"
    setUp, tearDown, kernel_loop = KernelCase.setUp, KernelCase.tearDown, KernelCase.kernel_loop   # 借 KernelCase 的架子，不重跑它的案例

    def dan_brain(self, n, url):
        ws, st = self.t / ("ws%d" % n), self.t / ("st%d" % n)
        (ws / "new").mkdir(parents=True)
        st.mkdir()
        (ws / "new" / "q1.txt").write_text("2+2？\n")
        (self.t / ("b%d.json" % n)).write_text(json.dumps({"argv": ["python3", "brain.py"], "cwd": str(self.DAN)}))
        return self.gate(None, name="b%d.json" % n, extra={"AOS_STACK": str(st), "AOS_WS": str(ws),
                                                            "AOS_BRAIN_URL": url}), st

    def gate(self, inst, name="q.json", extra=None):
        if inst is not None:
            return KernelCase.gate(self, inst, name, extra)
        p = subprocess.Popen([GATE, name], cwd=self.t, env=env_of(dict({"AOS_KERNEL": str(self.mb)}, **(extra or {}))),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def test_dan_brain_reports_usage(self):
        srv = UsageServer({"prompt_tokens": 20, "completion_tokens": 3, "total_tokens": 23})
        self.addCleanup(srv.close)
        self.kernel_loop()
        g, st = self.dan_brain(1, srv.url)
        out, err = g.communicate(timeout=30)
        self.assertEqual(g.returncode, 0, err)
        h = [json.loads(l) for l in (st / "history.jsonl").read_text().splitlines()]
        self.assertEqual(h[-1], {"role": "assistant", "content": "4"})   # usage 不進 history
        served = until(lambda: (self.t / "kst" / "served.jsonl").read_text())
        line = json.loads(served.splitlines()[0])
        self.assertEqual((line["code"], line["counter_tokens"], line["report_bad"]), (0, 23, False))
        used = json.loads((self.t / "kst" / "used.json").read_text())
        self.assertEqual((used["counter_calls"], used["counter_tokens"]), (1, 23))

    def test_dan_brain_without_kernel_writes_nothing(self):
        srv = UsageServer({"total_tokens": 5})
        self.addCleanup(srv.close)
        ws, st = self.t / "ws", self.t / "st"
        (ws / "new").mkdir(parents=True)
        st.mkdir()
        (ws / "new" / "q1.txt").write_text("hi\n")
        r = subprocess.run(["python3", "brain.py"], cwd=self.DAN, capture_output=True, text=True, timeout=30,
                           env=env_of({"AOS_STACK": str(st), "AOS_WS": str(ws), "AOS_BRAIN_URL": srv.url}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(st)), ["current.txt", "history.jsonl"])

    def test_budget_refused_through_gate(self):
        (self.t / "kernel.json").write_text(json.dumps({"mailbox": str(self.mb), "budget": {"max_calls": 1}}))
        self.kernel_loop()
        g = self.gate({"argv": ["echo", "one"]}, name="1.json")
        self.assertEqual(g.communicate(timeout=20)[0], "one\n")
        g = self.gate({"argv": ["echo", "two"]}, name="2.json")
        out, err = g.communicate(timeout=20)
        self.assertEqual((g.returncode, out), (1, ""))
        self.assertTrue(err.startswith("aos-gate: BudgetMissing "), err)


class DemoCase(unittest.TestCase):
    def test_demo_kernel_llm(self):
        with tempfile.TemporaryDirectory() as ws:
            for a in "abc":
                Path(ws, a, "new").mkdir(parents=True)
                Path(ws, a, "new", "q1.txt").write_text("%s 問：2+2？\n" % a)
            r = subprocess.run([tool("aos-exec"), str(ROOT / "demo" / "kernel-llm")], cwd=ws, env=env_of(),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            for a in "abc":
                self.assertEqual(Path(ws, a, "out", "q1.txt").read_text(), "FAKE ANSWER to: %s 問：2+2？\n" % a)
            served = [json.loads(l) for l in Path(ws, ".stack", "kernel", "served.jsonl").read_text().splitlines()]
            self.assertEqual([s["level"] for s in served], ["high", "normal", "normal"])
            self.assertEqual([s["time_ms"] for s in served], [5000, 800, None])   # 同級：宣告短的（b）先、沒寫的（a）最後
            self.assertEqual([s["code"] for s in served], [0, 0, 0])
            self.assertEqual([s["counter_tokens"] for s in served], [33, 33, 33])   # 假腦編的 usage（字數）經 AOS_KERNEL_REPORT 交回
            used = json.loads(Path(ws, ".stack", "kernel", "used.json").read_text())
            self.assertEqual((used["window"], used["counter_calls"], used["counter_tokens"]), ("day", 3, 99))


if __name__ == "__main__":
    unittest.main()
