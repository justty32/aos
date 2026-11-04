# 真的開一個 daemon 進程來測。跑法：cd proto4-1 && python3 -m unittest discover -s test
import json, os, signal, subprocess, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aos_daemon as d

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx")
COUNTER = os.path.join(FX, "counter")
COUNT = os.path.join(COUNTER, "count.txt")


def count():
    try: return int(open(COUNT).read().strip())
    except (OSError, ValueError): return 0


def wait_until(pred, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred(): return True
        time.sleep(0.05)
    return False


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-proto4-1-daemon-")
        self.home = d.Home(self.tmp)
        if os.path.exists(COUNT): os.remove(COUNT)

    def tearDown(self):
        try:
            d.stop(self.home)
        finally:
            import shutil; shutil.rmtree(self.tmp, ignore_errors=True)
            if os.path.exists(COUNT): os.remove(COUNT)

    def test_whole_flow(self):
        h = self.home
        self.assertTrue(d.start(h, 0.1))
        self.assertTrue(h.alive())
        self.assertFalse(d.start(h, 0.1))                    # 第二次：已經在跑
        s0 = h.state()["steps"]
        self.assertTrue(wait_until(lambda: h.state()["steps"] > s0))   # 格數在長

        r = d.request(h, {"op": "register", "dir": COUNTER, "name": "cnt"})
        self.assertTrue(r["ok"]); self.assertEqual(r["result"]["dir"], COUNTER)
        self.assertTrue(wait_until(lambda: count() >= 2))          # count.txt 在長
        procs = json.load(open(h.procsf))
        self.assertEqual([p["name"] for p in procs], ["cnt"])       # 登記表落檔了

        d.request(h, {"op": "pause", "name": "cnt"})
        c = count(); time.sleep(0.4)
        self.assertEqual(count(), c)                                # 暫停就不長
        self.assertTrue(json.load(open(h.procsf))[0]["paused"])     # 暫停狀態也落檔
        d.request(h, {"op": "resume", "name": "cnt"})
        self.assertTrue(wait_until(lambda: count() > c))

        self.assertGreater(d.request(h, {"op": "steps"})["result"], 0)      # steps 請求回得出格數
        bad = d.request(h, {"op": "nope"})
        self.assertFalse(bad["ok"]); self.assertIn("KeyError", bad["result"])
        self.assertTrue(h.alive())                                  # 壞請求不會弄死 daemon

        # stop 之後：pid 檔不見、state 還在、登記表還在；再 start 會接回來繼續跑
        self.assertTrue(d.stop(h))
        self.assertFalse(os.path.exists(h.pidf))
        self.assertIsNotNone(h.state())
        r = d.request(h, {"op": "ls"})
        self.assertTrue(r.get("pending"))                           # daemon 沒跑，請求先放著
        c = count()
        self.assertTrue(d.start(h, 0.1))
        self.assertTrue(wait_until(lambda: count() > c))            # 登記接回來了
        self.assertTrue(wait_until(lambda: not os.listdir(h.requests) or os.listdir(h.requests) == ["done"]))  # 放著的請求被撿走

        # unregister 之後不再跑
        d.request(h, {"op": "unregister", "name": "cnt"})
        c = count(); time.sleep(0.4); self.assertEqual(count(), c)
        self.assertEqual(d.request(h, {"op": "ls"})["result"], [])

    def test_kill9_then_restart(self):
        h = self.home
        self.assertTrue(d.start(h, 0.1))
        pid = h.pid()
        os.kill(pid, signal.SIGKILL)
        self.assertTrue(wait_until(lambda: not h.alive()))
        self.assertTrue(d.start(h, 0.1))
        self.assertNotEqual(h.pid(), pid)

    def test_sigterm_finishes_cleanly(self):
        h = self.home
        self.assertTrue(d.start(h, 0.1))
        os.kill(h.pid(), signal.SIGTERM)
        self.assertTrue(wait_until(lambda: not os.path.exists(h.pidf)))   # 自己刪 pid 檔＝乾淨收工
        self.assertIn("收工", open(h.logf).read())

    def test_cli(self):
        env = dict(os.environ, AOS_DAEMON_DIR=self.tmp)
        cli = [sys.executable, os.path.join(os.path.dirname(FX), "..", "aos_daemon.py")]
        run = lambda *a: subprocess.run(cli + list(a), env=env, capture_output=True, text=True, timeout=10)
        self.assertIn("起來了", run("start", "--interval", "0.1").stdout)
        self.assertIn('"ok": true', run("register", COUNTER, "c").stdout)
        time.sleep(0.4)
        out = run("ls").stdout
        self.assertIn("alive", out); self.assertIn("c ", out)
        self.assertIn("收工", run("stop").stdout)


if __name__ == "__main__":
    unittest.main()
