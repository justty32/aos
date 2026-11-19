"""入口 aos.py 的把手與 aos.gdb 斷點（a.bp、a.look）對真的 aos 樹（start-api 抄一份、假腦）實跑：a.bp 的增刪改查；控制 resume／step／stop 都等到停下才回、回停在哪（沒停著時 resume 只等、step 走一格、閒著或行程不在就回「沒停」、Ctrl-C 只是不等了且不留殘局、timeout_s）；工具要跑之前扣住→看→續＝工具真的跑了；扣著時別人 pause、sleep 再 wake、shell ctl resume；跑完才停、連錯兩次才停、條件壞了不停不掛、舊字條；觀察者（丙）停住目標、字條 by watch、壞了不影響目標、一個看兩隻、拿掉後行程沒了。"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "lib"))          # 跟 agent 用的 handler（lib/tools/agent/gdb_trigger）同一份裝好的庫
from aos.py import agent, Failed, Timeout  # noqa: E402
from aos.gdb import trigger, watcher  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")


def until(cond, timeout=30, every=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="gdb-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "start-api", cls.tree, symlinks=True)
        kj = cls.tree / "llms" / "def" / "kernel.json"
        k = json.loads(kj.read_text())
        k["endpoints"]["fake-math"] = dict(k["endpoints"]["fake"], tool="math", summary="fake brain that calls math with {} (an error)")
        kj.write_text(json.dumps(k))
        cls.logs = [open(cls.tmp / n, "w") for n in ("root.log", "llm.log")]
        cls.procs = [subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                      stdout=cls.logs[0], stderr=subprocess.STDOUT, start_new_session=True)]
        until(lambda: (cls.tree / ".stack" / "state.json").exists())
        cls.procs.append(subprocess.Popen(["aos-exec", "--stack", "stacks/llm", "def"], cwd=cls.tree / "llms", env=ENV,
                                          stdin=subprocess.DEVNULL, stdout=cls.logs[1], stderr=subprocess.STDOUT, start_new_session=True))
        until(lambda: (cls.tree / "llms" / "stacks" / "llm" / "state.json").exists())
        cls.sh("aos-agent -d .stack ctl add --auto-restart -w . agents/ann")
        os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])   # 庫在這個行程裡叫 aos-agent
        cls.daemon = str(cls.tree / ".stack")
        cls.a = agent.attach("ann", daemon=cls.daemon)
        cls.a.bp.timeout_s = 60                                     # 測試不會卡死：等過頭＝Timeout

    @classmethod
    def tearDownClass(cls):
        try:
            cls.sh("aos-daemon-ctl -d .stack shutdown", check=False)
            cls.sh("aos-daemon-ctl -d llms/stacks/llm shutdown", check=False)
            for p in cls.procs:
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)          # 只收這個測試自己起的那一群
                    p.wait()
        finally:
            for f in cls.logs:
                f.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def sh(cls, cmd, check=True):
        r = subprocess.run(cmd, shell=True, cwd=cls.tree, env=ENV, capture_output=True, text=True, timeout=60)
        if check and r.returncode:
            raise AssertionError("%s: %s" % (cmd, r.stderr))
        return r.stdout

    def setUp(self):
        a = self.a
        for w in watcher.ls(self.daemon):
            watcher.rm(self.daemon, w["name"], echo=False)
        a.bp.clear()
        a.bp.idle_s = 1.0
        if a.bp.stopped():
            a.bp.resume()                                           # 斷點都拿掉了：放行後跑到閒著才回
        a.llm.set("model=fake")

    def watchers(self):
        return watcher.ls(self.daemon)

    def row(self, name="ann"):
        return json.loads(self.sh("aos-daemon-ctl -d .stack ls -j"))["procs"].get(name)

    def tool_messages(self, call_id):
        return [m for m in self.a.look.history(0) if m.get("role") == "tool" and m.get("tool_call_id") == call_id]

    # ---- (一) before_tool 斷點：工具還沒跑就停，續了照原樣跑 ----
    def test_01_before_tool_holds_then_runs(self):
        a = self.a
        name = a.bp.add.before_tool("peek_now_time")
        self.assertIs(type(name), str)
        self.assertEqual(name, "before_tool_1")
        one = a.say("one")
        r = a.bp.resume()                                          # 沒停著：不送東西，等到停在斷點
        self.assertEqual((r.outcome, r.head), ("stopped", "stopped at before_tool_1 (peek_now_time)"))
        self.assertTrue(repr(r).startswith("stopped at before_tool_1 (peek_now_time)\nann is held at breakpoint before_tool_1"))
        h = a.bp.held()
        self.assertEqual((h["event"], h["detail"]["name"]), ("before_tool", "peek_now_time"))
        call = h["detail"]["id"]
        self.assertEqual(self.tool_messages(call), [])             # 工具還沒跑
        last = a.look.history(1)[0]
        self.assertEqual(last["tool_calls"][0]["id"], call)        # 腦已決定叫它，停在那一刻
        self.assertEqual(a.look.where(), "act")
        why = a.bp.why()
        self.assertTrue(why.paused and why.current and why.held)
        self.assertEqual(why.breakpoint, name)
        self.assertTrue(a.bp.get(name)["here"])
        self.assertIn("has not run yet", repr(why))
        self.assertEqual(self.row()["phase"], "running")           # 表上照寫 running（卡在那一格裡）
        two = a.say("one b")                                       # 扣著時信照收進信箱
        until(lambda: a.look.queue())
        a.bp.rm(name)                                             # 拿掉觸發器不影響正扣著的這一次
        self.assertIsNotNone(a.bp.held())
        r = a.bp.resume()                                          # 放行；斷點拿掉了，兩封信都答完、閒著才回
        self.assertEqual(r.outcome, "idle")
        self.assertIn("did not stop: it is idle", repr(r))
        msgs = until(lambda: self.tool_messages(call))
        self.assertEqual(len(msgs), 1)
        self.assertRegex(msgs[0]["content"], r"^\d{4}-\d\d-\d\dT")  # 真的跑了：peek_now_time 的時間
        self.assertIn("FAKE ANSWER to: one", a.listen(timeout_s=30, letter=one))
        self.assertIn("FAKE ANSWER to: one b", a.listen(timeout_s=30, letter=two))
        self.assertFalse(a.bp.why().paused)
        self.assertEqual(a.bp.why().notes, [])

    def test_02_step_from_a_hold_runs_the_tool_and_stops_after_that_step(self):
        a = self.a
        a.bp.add.before_tool("peek_now_time", once=True)
        two = a.say("two")
        self.assertEqual(a.bp.resume().outcome, "stopped")
        call = a.bp.held()["detail"]["id"]
        r = a.bp.step()                                            # 放行（工具照跑），act 這一格做完就停
        self.assertEqual((r.outcome, r.head), ("stopped", "stopped after one step, before think"))
        self.assertIsNone(a.bp.held())
        self.assertEqual(len(self.tool_messages(call)), 1)         # 工具跑了
        self.assertEqual(a.look.where(), "think")
        self.assertIn("ann is paused by a.bp.step()", repr(a.bp.why()))
        self.assertIsNone(a.bp.why().breakpoint)
        r = a.bp.step()                                            # 從暫停走一格：think 做完，停在 wait 前
        self.assertEqual(r.head, "stopped after one step, before wait")
        self.assertEqual(a.look.history(1)[0]["role"], "tool")     # 腦還沒回
        self.assertTrue(a.bp.ls()[0]["spent"])
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: two", a.listen(timeout_s=30, letter=two))
        self.assertFalse(a.bp.stopped())
        r = a.bp.step()                                            # 沒停著（閒著）：跑完這一格（idle）就停
        self.assertEqual(r.head, "stopped after one step, before idle")
        self.assertEqual(a.bp.resume().outcome, "idle")

    def test_03_paused_by_someone_else_while_held(self):
        a = self.a
        a.bp.add.before_tool("peek_now_time", once=True)
        three = a.say("three")
        a.bp.resume()
        call = a.bp.held()["detail"]["id"]
        self.sh("aos-agent -d .stack ctl pause --no-wait ann")      # 扣著時別人在 shell 下 pause
        why = a.bp.why()
        self.assertEqual(why.pending[1], "pause")
        self.assertIn("then it pauses", repr(why))
        r = a.bp.resume()                                             # 放行：工具照跑，這一格做完 loop 套用那個 pause
        self.assertEqual((r.outcome, r.head), ("stopped", "stopped before think (paused, not by a breakpoint)"))
        self.assertEqual(len(self.tool_messages(call)), 1)
        self.assertTrue(json.loads((Path(a.stack) / "state.json").read_text()).get("paused"))
        self.assertIsNone(a.bp.held())
        self.assertIn("no note", repr(r))                             # 這次停是別人的 pause，不是觸發器
        self.sh("aos-agent -d .stack ctl resume ann")
        self.assertIn("FAKE ANSWER to: three", a.listen(timeout_s=30, letter=three))

    def test_04_sleep_while_held_then_wake_holds_again(self):
        a = self.a
        a.bp.add.before_tool("peek_now_time", once=True)
        four = a.say("four")
        a.bp.resume()
        h = a.bp.held()
        call = h["detail"]["id"]
        self.sh("aos-agent -d .stack ctl sleep ann")               # 現在就停（TERM）：那一格被收掉
        until(lambda: self.row()["phase"] == "sleeping")
        self.assertIsNone(a.bp.held())
        self.assertFalse(alive(h["pid"]))
        self.assertEqual(self.tool_messages(call), [])             # 工具沒跑
        self.assertEqual(a.bp.why().notes[-1]["kind"], "hold_ended")
        self.sh("aos-agent -d .stack ctl wake ann")                # 醒來重跑同一個呼叫：once 也照扣
        self.assertEqual(a.bp.resume().head, "stopped at before_tool_1 (peek_now_time)")
        h2 = a.bp.held()
        self.assertEqual((h2["detail"]["id"], h2["again"]), (call, True))
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: four", a.listen(timeout_s=30, letter=four))
        self.assertEqual(len(self.tool_messages(call)), 1)         # 只跑了一次

    def test_05_shell_ctl_resume_releases_the_hold(self):
        a = self.a
        a.bp.add.before_tool("peek_now_time", once=True)
        five = a.say("five")
        a.bp.resume()
        call = a.bp.held()["detail"]["id"]
        self.sh("aos-agent -d .stack ctl resume ann")              # 在 shell 續（不經 aos.gdb）
        self.assertIn("FAKE ANSWER to: five", a.listen(timeout_s=30, letter=five))
        self.assertEqual(len(self.tool_messages(call)), 1)
        self.assertEqual(a.bp.notes()[-1]["by"], "ctl")
        self.assertFalse(a.bp.why().paused)

    # ---- 已經發生的事件：那一格做完才停 ----
    def test_06_after_tool_stops_before_the_brain_sees_it(self):
        a = self.a
        a.bp.add.after_tool("peek_now_time", once=True)
        six = a.say("six")
        r = a.bp.resume()
        self.assertEqual(r.head, "stopped at after_tool_1 (peek_now_time), before think")
        self.assertIsNone(a.bp.held())
        self.assertEqual(a.look.where(), "think")
        self.assertEqual(a.look.history(1)[0]["role"], "tool")
        self.assertIn("paused by breakpoint after_tool_1 (a trigger)", repr(a.bp.why()))
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: six", a.listen(timeout_s=30, letter=six))

    def test_07_tool_error_twice_in_a_row(self):
        a = self.a
        a.llm.set("model=fake-math")
        a.bp.add.tool_error(times=2)
        first = a.say("seven a")
        self.assertIn("FAKE ANSWER to: seven a", a.listen(timeout_s=30, letter=first))   # 第一次錯：還不算
        self.assertFalse(a.bp.stopped())
        second = a.say("seven b")
        self.assertEqual(a.bp.resume().head, "stopped at tool_error_1 (math), before think")
        note = a.bp.why().notes[-1]
        self.assertEqual((note["detail"]["name"], note["detail"]["code"]), ("math", 1))
        a.bp.resume()
        self.assertIn("FAKE ANSWER to: seven b", a.listen(timeout_s=30, letter=second))

    def test_08_broken_condition_does_not_stop_or_kill(self):
        a = self.a
        a.bp.add.before_tool(py=lambda ev: ev["no such key"])
        a.bp.add.before_tool(sh="exit 3")
        eight = a.say("eight")
        self.assertIn("FAKE ANSWER to: eight", a.listen(timeout_s=30, letter=eight))
        self.assertFalse(a.bp.stopped())
        errors = [t["last_error"] for t in a.bp.ls()]
        self.assertTrue(all(errors), errors)
        row = self.row()
        self.assertEqual((row["phase"], row["reason"]), ("running", None))

    def test_09_shell_resume_then_pause_makes_the_note_old(self):
        a = self.a
        a.bp.add.after_tool(sh="grep -q peek_now_time", once=True)
        nine = a.say("nine")
        a.bp.resume()
        self.assertTrue(a.bp.why().current)
        self.sh("aos-agent -d .stack ctl resume ann")
        self.assertIn("FAKE ANSWER to: nine", a.listen(timeout_s=30, letter=nine))
        self.sh("aos-agent -d .stack ctl pause ann")
        why = a.bp.why()
        self.assertTrue(why.paused)
        self.assertFalse(why.current)                              # 字條是上一次的
        self.assertIn("may be old", repr(why))

    # ---- (三) a.bp 的增刪改查、stop／resume（線 aosgdb-api-1119；aosgdb-verbs-1119 改成都等到停下）----
    def test_10_bp_crud_and_stop_resume(self):
        a = self.a
        self.assertTrue(a.ctl.where().strip())                         # a.ctl.where()＝aos-agent ctl where
        r = a.bp.stop()                                                # 現在停：等到真的停下才回
        self.assertEqual((r.outcome, r.head), ("stopped", "stopped before idle (a.bp.stop())"))
        self.assertTrue(a.bp.stopped())
        self.assertIn("is paused by a.bp.stop()", repr(a.bp.why()))
        self.assertIsNone(a.bp.why().breakpoint)                       # 不是停在斷點上
        self.assertEqual(a.bp.stop().head, "already stopped before idle (a.bp.stop())")   # 停著再 stop：什麼都不送
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertFalse(a.bp.stopped())
        for gone in ("skip", "wait_stopped"):
            self.assertFalse(hasattr(a.bp, gone))
        b1 = a.bp.add.before_tool("peek_now_time")
        b2 = a.bp.add.after_tool(sh="exit 10", times=2, id="mine")
        w = a.bp.add.watch(sh="exit 10", every_ms=200)
        self.assertEqual((b1, b2, w), ("before_tool_1", "mine", "watch_1"))
        self.assertTrue(all(type(x) is str for x in (b1, b2, w)))
        rows = {r["id"]: r for r in a.bp.ls()}
        self.assertEqual(set(rows), {b1, b2, w})
        self.assertIn("mine", repr(a.bp))                              # REPL 裡直接打 a.bp：一個斷點一行
        self.assertEqual((rows[b1]["kind"], rows[b1]["how"], rows[b1]["enabled"]), ("trigger", "hold", True))
        self.assertEqual((rows[w]["kind"], rows[w]["on"]), ("watch", "watch"))
        got = a.bp.get(b2)
        self.assertEqual((got["on"], got["times"], got["condition"]), ("after_tool", 2, {"sh": "exit 10"}))
        with self.assertRaises(Failed):
            a.bp.add.after_tool(id="mine")                        # 同 id 不換（沒給 replace）
        with self.assertRaises(Failed):
            a.bp.get("no_such")
        # 改：停用＝hook 拿下、設定留著；停用時不停
        self.assertFalse(a.bp.set(b1, enabled=False)["enabled"])
        self.assertNotIn("gdb_" + b1, a.hook.ls() or "")
        x = a.say("ten")
        self.assertIn("FAKE ANSWER to: ten", a.listen(timeout_s=30, letter=x))
        self.assertFalse(a.bp.stopped())
        on = a.bp.set(b1, enabled=True, once=True)
        self.assertEqual((on["enabled"], on["once"]), (True, True))
        self.assertIn("once", on["about"])
        self.assertEqual(a.bp.set(b2, times=3)["times"], 3)
        self.assertEqual(a.bp.set(w, times=4)["times"], 4)
        self.assertFalse(a.bp.set(w, enabled=False)["enabled"])
        until(lambda: self.row("gdbw_" + w)["phase"] == "stopped")
        self.assertTrue(a.bp.set(w, enabled=True)["enabled"])
        y = a.say("ten b")                                             # 啟用回來：照停
        self.assertEqual(a.bp.resume().head, "stopped at before_tool_1 (peek_now_time)")
        self.assertTrue(a.bp.get(b1)["here"])
        self.assertIn("a.bp.step()", repr(a.bp.why()))
        self.assertEqual(a.bp.stop().head, "already stopped at before_tool_1 (peek_now_time)")   # 扣著時 stop 不再送 pause
        self.assertIsNone(trigger.ctl_unapplied(a.stack))
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: ten b", a.listen(timeout_s=30, letter=y))
        # 刪：以 id 刪；刪了就查不到
        a.bp.rm(b2)
        a.bp.rm(w)
        self.assertEqual([r["id"] for r in a.bp.ls()], [b1])
        with self.assertRaises(Failed):
            a.bp.get(b2)
        self.assertIsNone(self.row("gdbw_" + w))
        a.bp.clear()
        self.assertEqual(a.bp.ls(), [])
        from aos.py import breakpoint as bp                            # bp.attach 回的跟 a.bp 同一種
        b3 = bp.attach("ann", daemon=self.daemon).add.before_queue(id="via_bp")
        self.assertEqual([r["id"] for r in a.bp.ls()], [b3])
        a.bp.rm(b3)

    # ---- (四) 控制動作：等到停下、它不停、Ctrl-C（線 aosgdb-verbs-1119）----
    def test_11_resume_when_running_sends_nothing_and_waits(self):
        a = self.a
        a.bp.add.after_tool("peek_now_time", once=True)
        before = trigger.ctl_doc(a.stack)[0]
        x = a.say("eleven")
        r = a.bp.resume()                                          # 剛 a.say 完、還在跑：只等
        self.assertEqual(r.head, "stopped at after_tool_1 (peek_now_time), before think")
        self.assertEqual(trigger.ctl_doc(a.stack)[0], (before or 0) + 1)   # 這期間只有觸發器自己的那一個 pause
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: eleven", a.listen(timeout_s=30, letter=x))

    def test_12_it_never_stops_idle_gone_timeout(self):
        a = self.a
        x = a.say("twelve")                                        # 沒有斷點：答完就閒著
        t0 = time.monotonic()
        r = a.bp.resume()
        self.assertEqual(r.outcome, "idle")
        self.assertLess(time.monotonic() - t0, 20)
        self.assertTrue(any("FAKE ANSWER to: twelve" in (m.get("content") or "") for m in a.look.history(2)))
        self.assertFalse(a.bp.stopped())
        a.bp.idle_s, a.bp.timeout_s = 60, 1.5                     # 閒著也不回：只能等到逾時
        with self.assertRaises(Timeout) as e:
            a.bp.resume()
        self.assertIn("it goes on as it was", str(e.exception))
        a.bp.idle_s, a.bp.timeout_s = 1.0, 60
        self.sh("aos-agent -d .stack ctl sleep ann")               # 行程不在：回「沒停：not running」
        until(lambda: self.row()["phase"] == "sleeping")
        r = a.bp.resume()
        self.assertEqual(r.outcome, "gone")
        self.assertIn("did not stop: it is not running", repr(r))
        self.sh("aos-agent -d .stack ctl wake ann")
        until(lambda: self.row()["phase"] == "running")
        self.assertIn("FAKE ANSWER to: twelve", a.listen(timeout_s=30, letter=x))

    def child(self, body, before="pass"):
        """另起一支 python 跑 a.bp 的一個控制動作，印 READY 後（再跑完 before）才開始；給 SIGINT 模擬在 REPL 裡按 Ctrl-C。"""
        code = textwrap.dedent("""
            import sys, time
            sys.path.insert(0, %r)
            from aos.py import agent
            a = agent.attach("ann", daemon=%r)
            a.bp.idle_s, a.bp.report_s = 60, 0
            print("READY", flush=True)
            %s
            r = %s
            print("OUTCOME", r.outcome, flush=True)
            print(repr(r), flush=True)
        """) % (str(PROTO / "lib"), self.daemon, before, body)
        p = subprocess.Popen([sys.executable, "-c", code], cwd=self.tree, env=dict(ENV), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and (p.kill(), p.wait()))
        self.assertEqual(p.stdout.readline().strip(), "READY")
        return p

    def test_13_ctrl_c_stops_waiting_and_leaves_nothing(self):
        a = self.a
        p = self.child("a.bp.resume()")                            # 閒著、idle_s 60：一直等
        time.sleep(1.0)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, err)
        self.assertIn("OUTCOME interrupted", out)
        self.assertIn("stopped waiting (Ctrl-C); ann goes on as it was", out)
        self.assertFalse(a.bp.stopped())
        self.assertIsNone(trigger.ctl_unapplied(a.stack))         # 什麼都沒留
        x = a.say("thirteen")
        self.assertIn("FAKE ANSWER to: thirteen", a.listen(timeout_s=30, letter=x))

    def test_14_ctrl_c_during_a_step_takes_its_pause_back(self):
        a = self.a
        a.bp.add.after_tool(sh="sleep 6; exit 10")                 # act 這一格拖 6 秒（條件判 6 秒、永遠不算）
        # act 開始 1 秒後（正在判那 6 秒的條件）step：送 pause --no-wait，等這一格做完
        p = self.child("a.bp.step()", before="while a.look.where() != 'act': time.sleep(0.02)\ntime.sleep(1)")
        x = a.say("fourteen")
        until(lambda: trigger.ctl_unapplied(a.stack), timeout=10)
        time.sleep(0.3)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, err)
        self.assertIn("OUTCOME interrupted", out)
        self.assertIn("the pause a.bp.step() sent is taken back", out)
        self.assertIn("FAKE ANSWER to: fourteen", a.listen(timeout_s=30, letter=x))   # 沒停：照跑到答完
        self.assertFalse(a.bp.stopped())
        self.assertIsNone(trigger.ctl_unapplied(a.stack))
        self.assertNotIn("step", [n.get("by") for n in a.bp.notes()][-3:])

    def test_15_step_goes_one_cell_at_a_time(self):
        a = self.a
        a.bp.add.after_queue(once=True)                            # 收了信之後停（idle 那一格做完）
        x = a.say("fifteen")
        r = a.bp.resume()
        self.assertTrue(r.head.startswith("stopped at after_queue_1 (") and r.head.endswith("), before think"), r.head)
        seen = []
        for _ in range(12):                                        # 一格一格走完這一輪：think、wait（等腦時一格接一格）、act、think...
            r = a.bp.step()
            self.assertEqual(r.outcome, "stopped")
            seen.append(r.head.rsplit(" ", 1)[-1])
            if seen[-1] == "idle":
                break
        self.assertEqual(seen[0], "wait")                          # think 走一格＝停在 wait 前
        self.assertIn("act", seen)
        self.assertEqual(seen[-1], "idle")
        for a_, b_ in zip(["think"] + seen, seen):                 # 每一步都只往 fsm 的下一格（或 wait 自己再一格）
            self.assertIn((a_, b_), {("think", "wait"), ("wait", "wait"), ("wait", "act"), ("act", "think"), ("act", "idle"),
                                     ("wait", "idle"), ("idle", "idle"), ("idle", "think")})
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertIn("FAKE ANSWER to: fifteen", a.listen(timeout_s=30, letter=x))

    # ---- (二) 觀察者 ----
    def test_20_watcher_pauses_target_with_a_note(self):
        a = self.a

        def new_tool_result(t):                                    # 跨圈：t.mem 記上次看到幾則，只看新的
            h = t.history(0)
            seen = t.mem.get("n", len(h))
            t.mem["n"] = len(h)
            return any(m.get("role") == "tool" for m in h[seen:])
        w = a.bp.add.watch(py=new_tool_result, every_ms=200)
        rows = self.watchers()
        self.assertEqual([r["name"] for r in rows], [w])
        until(lambda: self.watchers()[0]["per_target"]["ann"].get("seen", 0) >= 2)   # 基準記好了
        a.say("twenty")
        self.assertTrue(a.bp.resume().head.startswith("stopped at %s (ann), before " % w))
        why = a.bp.why()
        self.assertTrue(why.current)
        note = why.notes[-1]
        self.assertEqual((note["by"], note["trigger"], note["detail"]["target"]), ("watch", "gdbw_" + w, "ann"))
        self.assertIn("paused by breakpoint %s (a watcher)" % w, repr(why))
        self.assertEqual(why.breakpoint, w)
        self.assertRegex(self.sh("aos-agent -d .stack ctl ls"), r"(?m)^ann\s+paused")   # aos-agent 的表看得到 paused
        a.bp.rm(w)
        self.assertEqual(a.bp.resume().outcome, "idle")
        self.assertTrue(any("FAKE ANSWER to: twenty" in (m.get("content") or "") for m in a.look.history(3)))

    def test_21_broken_watcher_does_not_touch_the_target_and_rm_ends_it(self):
        a = self.a
        w = a.bp.add.watch(py=lambda t: t.no_such_thing(), every_ms=200)
        until(lambda: self.watchers()[0]["per_target"]["ann"].get("last_error"))
        x = a.say("twenty one")
        self.assertIn("FAKE ANSWER to: twenty one", a.listen(timeout_s=30, letter=x))
        self.assertFalse(a.bp.stopped())
        row = self.watchers()[0]
        self.assertEqual(row["phase"], "running")                  # 條件壞了：觀察者照跑、只記 last_error
        pid = row["pid"]
        os.kill(pid, signal.SIGKILL)                               # 觀察者行程整個死掉（這是測試自己起的那一支）
        until(lambda: self.watchers()[0]["phase"] != "running" or self.watchers()[0]["pid"] != pid)
        y = a.say("twenty one b")
        self.assertIn("FAKE ANSWER to: twenty one b", a.listen(timeout_s=30, letter=y))
        self.assertEqual(self.row()["phase"], "running")
        w2 = a.bp.add.watch(sh="exit 10", every_ms=200)                   # 另一支好的：拿掉後行程沒了、表上沒了
        until(lambda: [r for r in self.watchers() if r["name"] == w2 and r["pid"]])
        pid2 = [r for r in self.watchers() if r["name"] == w2][0]["pid"]
        a.bp.rm(w2)
        a.bp.rm(w)
        self.assertFalse(alive(pid2))
        self.assertIsNone(self.row("gdbw_" + w2))
        self.assertEqual(self.watchers(), [])
        self.assertEqual(a.bp.ls(), [])

    def test_22_one_watcher_two_agents_times_and_rearm(self):
        a = self.a
        self.sh("aos-agent -d .stack ctl add -n bob --auto-restart -w . agents/ann")
        b = agent.attach("bob", daemon=self.daemon)
        flag = "test -f gdb_flag || exit 10"                       # cwd＝目標的 stack；不成立要退 10（退 1＝條件壞了）
        w = a.bp.add.watch(also=["bob"], sh=flag, times=3, every_ms=200)
        self.assertEqual([r["id"] for r in b.bp.ls()], [w])        # bob 那邊也看得到同一個 id
        b.bp.timeout_s, b.bp.idle_s = 30, 15                        # bob 閒著；要等的是觀察者來停它，閒著不算數
        (Path(b.stack) / "gdb_flag").write_text("x")
        t0 = time.monotonic()
        self.assertEqual(b.bp.resume().outcome, "stopped")
        self.assertGreater(time.monotonic() - t0, 0.4)             # 連續 3 圈才算（約 0.6 秒）
        self.assertFalse(a.bp.stopped())
        note = b.bp.why().notes[-1]
        self.assertEqual((note["by"], note["times"], note["detail"]["target"]), ("watch", 3, "bob"))
        b.bp.idle_s = 1.0
        self.assertEqual(b.bp.resume().outcome, "idle")               # 條件還成立：先要看到一次不成立才會再停
        time.sleep(1.5)
        self.assertFalse(b.bp.stopped())
        self.assertFalse(self.watchers()[0]["per_target"]["bob"]["armed"])
        os.remove(Path(b.stack) / "gdb_flag")
        until(lambda: self.watchers()[0]["per_target"]["bob"]["armed"])   # 看到一次不成立
        b.bp.idle_s = 15
        (Path(b.stack) / "gdb_flag").write_text("x")
        self.assertEqual(b.bp.resume().outcome, "stopped")
        self.assertEqual(self.watchers()[0]["per_target"]["bob"]["fired"], 2)
        b.bp.rm(w)
        b.bp.idle_s = 1.0
        b.bp.resume()
        self.sh("aos-agent -d .stack ctl rm bob")


if __name__ == "__main__":
    unittest.main()
