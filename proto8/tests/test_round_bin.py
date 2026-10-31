"""test_round_bin - agent-round 一輪：bin/aos-round（10-31 自 test_round.py 拆出，行為不變）。

一輪（10-30 起 aos-round：lib/agent/round 的 fsm 表＋五格；舊骨架 round/_entry 與它的 Round 類、--step、hook/pause 第 6 步刪了）：
  題目經 queue push 進 $AOS_STACK/queue/，答案看 history 最新那則 assistant。
AosRound（第 3 步）：bin/aos-round 單次叫、loop.json 用它整隻跑（stop、idle＋ctl paused／stopped、單子逾時殺在 think）、自己的錯。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。"""
import json, os, subprocess, time, unittest

from aos_bins import ROOT, tool  # noqa: E402
from round_common import AgentCase, ROUND, EXEC, err_code  # noqa: E402


class AosRound(AgentCase):
    """bin/aos-round（10-30 aos-round 第 3 步）：挑表（AOS_ROUND_ON_EMPTY）、設 AOS_ROUND_AGENT、cd lib/agent/round、換成 aos-fsm；
    agent 的 loop.json 用 aos-round、aos-exec <agent> 整隻跑；驗 fsm trace 的 state／next 序列。"""

    def loop(self, **cfg):
        cfg = dict({"exec": {"argv": ["aos-round", {"$env": "AOS_CD"}]}}, **cfg)
        (self.agent / "loop.json").write_text(json.dumps(cfg))
        (self.agent / "_entry").write_text('["aos-loop", "loop.json"]')

    def whole(self):
        return subprocess.run([EXEC, str(self.agent)], capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=120)

    def aos_round(self, *args, env=None):
        return subprocess.run([tool("aos-round")] + list(args), capture_output=True, text=True, env=self.env(env),
                              cwd=self.tmp, timeout=120)

    def states(self):
        return [(t["state"], t["code"], t["next"]) for t in self.lines((self.stack / "trace.jsonl").read_text())]

    def state(self):
        return (self.stack / "state.txt").read_text().strip()

    def test_one_step(self):
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual((self.state(), self.states()), ("think", [("idle", 0, "think")]))
        self.assertEqual(self.ls("cur"), [self.q1])

    def test_relative_stack(self):
        r = self.aos_round(str(self.agent), env={"AOS_STACK": "ws/.stack/", "AOS_WS": "ws"})   # 從 cwd（tmp）算，不是從 round 資料夾
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
        """AOS_ROUND_ON_EMPTY=idle（round 槽的 env）＋interval_ms：答完後 idle 一行一行（next 都是 idle）；paused 時新信留在 new/，放行後答出；stopped 收工。"""
        self.parts["round"] = {"path": ROUND, "env": {"AOS_ROUND_ON_EMPTY": "idle"}}
        self.save()
        self.loop(interval_ms=100, ctl="ctl.json", state="state.json")
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
                if x != ("idle", 10, "idle"):
                    break
                n += 1
            return n

        until("第一題答完、idle 空轉兩次", lambda: self.answer() is not None and idles() >= 2)
        (self.stack / "ctl.json").write_text('{"paused": true}')
        until("loop 暫停", lambda: phase() == "paused")
        q2 = self.put("第二題")
        time.sleep(1)
        self.assertEqual(self.ls("new"), [q2])                                                   # 暫停：兩格之間不再起
        (self.stack / "ctl.json").write_text('{"paused": false}')
        until("第二題答完", lambda: (self.answer() or "").startswith("FAKE ANSWER to: 第二題") and not self.ls("cur") and not self.ls("new"))
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=30), 0)
        self.assertEqual(self.state(), "idle")

    def test_loop_timeout_kills_think(self):
        self.parts["endpoint/default"] = {"path": self.script("slow", "cat > /dev/null; sleep 30\n")}
        self.save()
        self.loop(exec={"argv": ["aos-round", {"$env": "AOS_CD"}], "timeout_ms": 2000}, max=10)
        t0 = time.time()
        r = self.whole()
        self.assertLess(time.time() - t0, 20)
        self.assertEqual(self.state(), "think")
        self.assertEqual(r.returncode, 143, r.stderr)                                           # 單子逾時：整群收，fsm 那格 143、表沒接
        self.assertEqual(self.states()[-1], ("think", 143, None))
        self.assertEqual([m["role"] for m in self.history()], ["user"])

    def test_own_errors(self):
        r = self.aos_round()
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "ArgumentsBad"))
        r = self.aos_round(str(self.agent), "x")
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "ArgumentsBad"))
        r = self.aos_round("agent")
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "AgentBad"))
        self.parts["round"] = {"path": ROUND, "env": {"AOS_ROUND_ON_EMPTY": "wait"}}
        self.save()
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "SettingBad"))
        self.parts["round"] = {"path": str(self.tmp / "nope")}
        self.save()
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "PartsBad"))
        self.assertFalse((self.stack / "state.txt").exists())

    def test_fsm_not_on_path(self):
        """PATH 上沒有 aos-fsm：CommandMissing、說「PATH 上找不到」，不印 PATH 最後一格的路徑（10-30 晚真腦實測發現 1）。"""
        path = os.pathsep.join([str(ROOT / "bin"), "/usr/bin", "/bin"])        # 有 aos-parts、沒有 aos-fsm
        r = self.aos_round(str(self.agent), env={"PATH": path})
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "CommandMissing"))
        self.assertIn("PATH 上找不到可執行的 aos-fsm", r.stderr)
        self.assertNotIn("/bin/aos-fsm", r.stderr)


if __name__ == "__main__":
    unittest.main()
