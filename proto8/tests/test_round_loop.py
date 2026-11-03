"""test_round_loop - agent-round 一輪：agent 的 loop.json 直接叫 aos-fsm 跑 lib/agent/round 的表（11-01 起；前身 test_round_bin.py 測 bin/aos-round）。

一輪（lib/agent/round 的 fsm 表＋五格）：題目經 queue push 進 $AOS_STACK/queue/，答案看 history 最新那則 assistant。
11-01 使用者「aos round這東西還沒刪掉嗎」「刪掉」：bin/aos-round 刪了，loop.json 寫
  {"exec": {"argv": ["aos-fsm", "fsm-stop.json"], "cwd": "<lib/agent/round>"}}——cwd 讓表裡的格名從 round 資料夾找，
  表的 {"$env": "AOS_CD"} 是 loop 跑那張單子時的 AOS_CD＝loop.json 的資料夾＝agent；queue 空的停法＝指哪張表（stop／idle）。
RoundLoop：aos-exec <agent>/loop.json#/exec 單次走一格（ask_round 的叫法）、相對的 AOS_STACK／AOS_WS 從呼叫的 cwd 算、
  舊的 AOS_ROUND_AGENT 不再有作用；aos-exec <agent> 整隻跑（stop 表收工、idle 表＋ctl paused／stopped、單子逾時殺在 think）。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。"""
import json, shutil, subprocess, time, unittest

from round_common import AgentCase, EXEC, ROUND  # noqa: E402
from aos_bins import fsm_steps  # noqa: E402


class RoundLoop(AgentCase):
    """agent 的 loop.json → aos-fsm 表：驗 fsm 每格的 state／next 序列（11-03 起看 tests/spy_bin 的旁觀者）。"""

    def loop(self, table="fsm-stop.json", **cfg):
        cfg = dict({"exec": {"argv": ["aos-fsm", table], "cwd": ROUND}}, **cfg)
        (self.agent / "loop.json").write_text(json.dumps(cfg))
        (self.agent / "_entry").write_text('["aos-loop", "loop.json"]')

    def whole(self):
        return subprocess.run([EXEC, str(self.agent)], capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=120)

    def one(self, env=None):
        """aos-exec <agent>/loop.json#/exec：照 loop.json 走一格（ask_round 這樣叫）。"""
        return subprocess.run([EXEC, str(self.agent / "loop.json") + "#/exec"], capture_output=True, text=True,
                              env=self.env(env), cwd=self.tmp, timeout=120)

    def states(self):
        return [(t["state"], t["code"], t["next"]) for t in fsm_steps(self.stack)]  # 11-03：fsm 不寫 trace.jsonl，跑了哪幾格看 tests/spy_bin 的旁觀者（code＝aos-fsm 的結束碼，分岔接住＝0）

    def state(self):
        return (self.stack / "state.txt").read_text().strip()

    def test_one_step(self):
        self.loop()
        r = self.one(env={"AOS_ROUND_AGENT": str(self.tmp / "nowhere")})     # 舊的傳話筒不再有作用
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual((self.state(), self.states()), ("think", [("idle", 0, "think")]))
        self.assertEqual(self.ls("cur"), [self.q1])

    def test_relative_stack(self):
        self.loop()
        r = self.one(env={"AOS_STACK": "ws/.stack/", "AOS_WS": "ws"})         # 從呼叫的 cwd（tmp）算，不是從 round 資料夾
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.state(), "think")

    def test_stop_under_loop(self):
        self.loop(max=50)
        r = self.whole()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x for x, _, _ in self.states()], ["idle", "think", "act", "think", "finish", "idle"])
        self.assertEqual(self.states()[-1], ("idle", 10, None))
        self.assertTrue(self.answer().startswith("FAKE ANSWER to: 幾點？（clock said:"))
        self.assertEqual((self.ls("new"), self.ls("cur")), ([], []))

    def test_idle_under_loop_with_ctl(self):
        """fsm-idle.json＋interval_ms：答完後 idle 一行一行（next 都是 idle）；paused 時新信留在 new/，放行後答出；stopped 收工。"""
        self.loop("fsm-idle.json", interval_ms=100, ctl="ctl.json", state="state.json")
        p = subprocess.Popen([EXEC, str(self.agent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env=self.env(), cwd=self.tmp)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))

        def until(what, cond, secs=30):
            end = time.time() + secs
            while time.time() < end:
                if cond():
                    return
                time.sleep(0.05)
            self.fail("等不到：" + what)

        def phase():
            try:
                return json.loads((self.stack / "state.json").read_text()).get("phase")
            except (OSError, ValueError):
                return None

        def idles():
            n = 0
            for x in reversed(self.states()):
                if x != ("idle", 0, "idle"):                 # 11-03：旁觀者記 fsm 的碼，idle 表接住 10＝0
                    break
                n += 1
            return n

        until("第一題答完、idle 空轉兩次", lambda: self.answer() is not None and idles() >= 2)
        (self.stack / "ctl.json").write_text('{"cmd": "pause"}')
        until("loop 暫停", lambda: phase() == "paused")
        q2 = self.put("第二題")
        time.sleep(1)
        self.assertEqual(self.ls("new"), [q2])                                                   # 暫停：兩格之間不再起
        (self.stack / "ctl.json").write_text('{"cmd": "resume"}')
        until("第二題答完", lambda: (self.answer() or "").startswith("FAKE ANSWER to: 第二題") and not self.ls("cur") and not self.ls("new"))
        (self.stack / "ctl.json").write_text('{"cmd": "stop"}')
        self.assertEqual(p.wait(timeout=30), 0)
        self.assertEqual(self.state(), "idle")

    def test_loop_timeout_kills_think(self):
        self.parts["endpoint/default"] = {"path": self.script("slow", "cat > /dev/null; sleep 30\n")}
        self.save()
        self.loop(exec={"argv": ["aos-fsm", "fsm-stop.json"], "cwd": ROUND, "timeout_ms": 2000}, max=10)
        t0 = time.time()
        r = self.whole()
        self.assertLess(time.time() - t0, 20)
        self.assertEqual(self.state(), "think")
        self.assertEqual(r.returncode, 143, r.stderr)                                           # 單子逾時：整群收，fsm 那格 143、表沒接
        self.assertEqual(self.states()[-1], ("think", 143, None))
        self.assertEqual([m["role"] for m in self.history()], ["user"])


if __name__ == "__main__":
    unittest.main()
