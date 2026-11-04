"""test_agent_fsm - aos 體系自己的 loop／fsm agent 範本 demo/agent-fsm（11-04；thinking 2026-11/04/loop-fsm-agent 03 的測試清單 13 案）：
_entry＝aos-loop loop.json、每次一格 fsm.json（idle 收信→think 問腦→act 跑工具），走 queue 協議（P-42）；
aos-say 寄進 $AOS_STACK/queue/、aos-listen 讀 history.jsonl；掛 daemon 用 aos-daemon-ctl add。

腦一律不碰外網：沒設 AOS_BRAIN_URL＝範本的假腦（有工具先叫第一個、再答一句）；要看送出的 request 的案起一個本機假端點（FakeBrain）。
範本原處就跑（tools.json 的 clock 相對路徑從範本算）；要改表、改旗標的案複製一份，tools.json 改寫成絕對路徑。"""
import http.server, json, os, shutil, subprocess, tempfile, threading, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, tool, path_with  # noqa: E402
from dead_brain import DEAD  # noqa: E402
TEMPLATE = ROOT / "demo" / "agent-fsm"
HUMAN = ROOT / "extras" / "human" / "bin"
CTL = ROOT / "bin" / "aos-daemon-ctl"
POST = tool("aos-post")
CLOCK = ROOT / "lib" / "base" / "clock"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "AOS_DAEMON_STACK",
         "AOS_BRAIN_URL", "AOS_BRAIN_KEY", "AOS_KERNEL_REPORT")


class FakeBrain:
    """本機的 OpenAI 相容假端點：記下每個 request；最後一則是 user 而且有工具＝叫第一個工具，否則答 "real: <最後一則 user>"。"""

    def __init__(self, test):
        self.requests = []
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                brain.requests.append(dict(body, path=self.path))
                msgs, tools = body["messages"], body.get("tools") or []
                if msgs[-1]["role"] == "user" and tools:
                    msg = {"role": "assistant", "content": None, "tool_calls": [
                        {"id": "c%d" % len(brain.requests), "type": "function",
                         "function": {"name": tools[0]["function"]["name"], "arguments": "{}"}}]}
                else:
                    msg = {"role": "assistant", "content": "real: " + [m for m in msgs if m["role"] == "user"][-1]["content"],
                           "reasoning": "不該被收進 history"}
                out = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        test.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]


class AgentFsm(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-fsm-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
        self.procs = []
        self.seq = 0
        self.addCleanup(self.kill_all)

    def kill_all(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with()
        e.update(extra or {})
        return e

    def run_(self, argv, env=None, timeout=60, cwd=None):
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=env or self.env(),
                              stdin=subprocess.DEVNULL, timeout=timeout, cwd=cwd)

    def copy(self, name="tpl", fsm=None, loop=None):
        """範本複製一份：tools.json 的 clock 改絕對路徑（相對的從範本原處算，搬家會斷）；fsm／loop 給了就照改（f(dict)）。"""
        d = self.tmp / name
        shutil.copytree(TEMPLATE, d)
        (d / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(CLOCK)}}}))
        for fname, f in (("fsm.json", fsm), ("loop.json", loop)):
            if f:
                cfg = json.loads((d / fname).read_text())
                f(cfg)
                (d / fname).write_text(json.dumps(cfg))
        return d

    def once(self, cfg):
        """射後不理：idle 的 next 改成字串 "think"（queue 空的 10 到 loop＝收工）。"""
        cfg["states"]["idle"]["next"] = "think"

    def start(self, tpl=TEMPLATE, env=None):
        p = subprocess.Popen([str(EXEC), "--ws", str(self.ws), str(tpl)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             text=True, env=env or self.env())
        self.procs.append(p)
        return p

    def ctl(self, cmd, stack=None):
        self.seq += 1
        (stack or self.stack).mkdir(parents=True, exist_ok=True)
        ((stack or self.stack) / "ctl.json").write_text(json.dumps({"cmd": cmd, "seq": self.seq}))

    def stop(self, p):
        self.ctl("stop")
        code = p.wait(timeout=30)
        err = p.stderr.read()
        return code, err

    def say(self, text, stack=None):
        where = ["--stack", stack] if stack else ["--ws", self.ws]
        r = self.run_([HUMAN / "aos-say", *where, text])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, stack=None, secs=30):
        where = ["--stack", stack] if stack else ["--ws", self.ws]
        r = self.run_([HUMAN / "aos-listen", *where, "--timeout", str(secs)], timeout=secs + 10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def post(self, body, ordered=True, stack=None):
        box = (stack or self.stack) / "queue"
        if not (box / "new").is_dir():
            self.assertEqual(self.run_([POST, "init", box]).returncode, 0)
        r = subprocess.run([str(POST), "send"] + (["--ordered"] if ordered else []) + [str(box)],
                           input=body if isinstance(body, str) else json.dumps(body, ensure_ascii=False),
                           capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def history(self, stack=None):
        try:
            text = ((stack or self.stack) / "history.jsonl").read_text()
        except FileNotFoundError:
            return []
        return [json.loads(l) for l in text.splitlines() if l.strip()]

    def answers(self, stack=None):
        return [m for m in self.history(stack) if m["role"] == "assistant" and not m.get("tool_calls")]

    def until(self, f, secs=30):
        end = time.time() + secs
        while time.time() < end:
            try:
                v = f()
                if v:
                    return v
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.05)
        return None

    def state_txt(self, stack=None):
        return ((stack or self.stack) / "state.txt").read_text().strip()

    def phase(self, stack=None):
        return json.loads(((stack or self.stack) / "state.json").read_text() or "{}").get("phase")

    def queue(self, stage, stack=None):
        try:
            return sorted(n for n in os.listdir((stack or self.stack) / "queue" / stage) if not n.startswith("."))
        except FileNotFoundError:
            return []

    def cell(self, script, *args, cd=TEMPLATE, env=None):
        """直接叫一支格（不經 fsm）：AOS_STACK＝self.stack、AOS_CD＝cd、cwd＝cd。"""
        self.stack.mkdir(parents=True, exist_ok=True)
        e = self.env(dict(AOS_STACK=str(self.stack) + "/", AOS_CD=str(cd), AOS_WS=str(self.ws), **(env or {})))
        return self.run_(["python3", cd / script, *args], env=e, cwd=cd)

    # ---- 1 範本形狀 ----

    def test_01_shape(self):
        """五個固定檔、_entry＝aos-loop loop.json（JSON、沒 +x）、loop.json 開 ctl／state、fsm.json 三格與 next 的形狀（N-36）、
        tools.json 只有 clock；沒有 parts.json／prompt.txt／cli.json。"""
        for f in ("_entry", "loop.json", "fsm.json", "tools.json", "system.txt", ".env", "idle.py", "brain.py", "act.py"):
            self.assertTrue((TEMPLATE / f).is_file(), f)
        self.assertEqual(json.loads((TEMPLATE / "_entry").read_text()), ["aos-loop", "loop.json"])
        self.assertFalse(os.stat(TEMPLATE / "_entry").st_mode & 0o111)
        self.assertEqual(json.loads((TEMPLATE / "loop.json").read_text()),
                         {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"})
        fsm = json.loads((TEMPLATE / "fsm.json").read_text())
        self.assertEqual((fsm["_entry"], fsm["start"], sorted(fsm["states"])),
                         (["aos-fsm", {"$env": "AOS_CF"}], "idle", ["act", "idle", "think"]))
        nexts = {k: v["next"] for k, v in fsm["states"].items()}
        self.assertEqual(nexts, {"idle": {"0": "think", "10": "idle"}, "think": {"0": "act", "10": "idle"}, "act": "think"})
        self.assertEqual(fsm["states"]["think"]["exec"]["argv"], ["python3", "brain.py", "--system", "system.txt"])
        r = self.run_([ROOT / "bin" / "aos-tools", "--file", TEMPLATE / "tools.json", "ls"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([l.split("\t")[:3] for l in r.stdout.splitlines()], [["clock", "dir", str(CLOCK)]])
        for f in ("parts.json", "prompt.txt", "cli.json", "hook"):
            self.assertFalse((TEMPLATE / f).exists(), f)

    # ---- 2 一問一答、13 不碰工作區 ----

    def test_02_one_exchange(self):
        """假腦一問一答：aos-say → history 四則（user、assistant 帶 clock、tool、assistant）、aos-listen 拿到答案；
        tools/clock/ 在、信已收掉、state.txt 回 idle、沒有 mailbox_warning；工作區只有 .stack（13）；stop 後 loop 退 0、stderr 空。"""
        self.say("現在幾點")
        p = self.start()
        out = self.listen()
        self.assertTrue(out.startswith("FAKE ANSWER to: 現在幾點（tool said: "), out)
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(h[0], {"role": "user", "content": "現在幾點"})
        self.assertEqual(h[1]["tool_calls"][0]["function"]["name"], "clock")
        self.assertRegex(h[2]["content"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n$")
        self.assertTrue((self.stack / "tools" / "clock").is_dir())
        self.assertTrue(self.until(lambda: self.state_txt() == "idle"))
        self.assertEqual((self.queue("new"), self.queue("cur")), ([], []))
        self.assertFalse((self.stack / "mailbox_warning.txt").exists())
        self.assertIn(self.phase(), ("running", "waiting"))
        code, err = self.stop(p)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.phase(), "stopped")
        self.assertEqual(sorted(os.listdir(self.ws)), [".stack"])            # 13：P-42 三樣以外不碰工作區（clock 不寫檔）

    # ---- 3 整批 ----

    def test_03_batch(self):
        """先連寄三封再起：history 前三則都是 user（照寄的順序），腦只問一次（一則帶 tool_calls 的 assistant）。"""
        for t in ("一", "二", "三"):
            self.say(t)
        p = self.start()
        self.assertTrue(self.until(self.answers))
        h = self.history()
        self.assertEqual([m.get("content") for m in h[:3]], ["一", "二", "三"])
        self.assertEqual([m["role"] for m in h], ["user"] * 3 + ["assistant", "tool", "assistant"])
        self.assertEqual(self.stop(p)[0], 0)

    # ---- 4 壞信 ----

    def test_04_bad_letters(self):
        """壞信三種（assistant、空 content、不是物件）夾一封好信：壞的 done 丟掉、mailbox_warning.txt 一行（最後一封）、好信照答。"""
        self.post({"role": "assistant", "content": "x"})
        self.post({"role": "user", "content": ""})
        good = self.post({"role": "user", "content": "好信"})
        last_bad = self.post('"不是物件"')
        p = self.start()
        self.assertTrue(self.until(self.answers))
        self.assertEqual([m["content"] for m in self.history() if m["role"] == "user"], ["好信"])
        warn = (self.stack / "mailbox_warning.txt").read_text()
        self.assertEqual(len(warn.splitlines()), 1)
        self.assertTrue(warn.startswith("信 %s 不採用：" % last_bad), warn)
        self.assertNotIn(good, warn)
        self.assertEqual((self.queue("new"), self.queue("cur"), self.queue("archive")), ([], [], []))
        self.assertEqual(self.stop(p)[0], 0)

    # ---- 5 無序信排後面 ----

    def test_05_unordered_last(self):
        """無序（aos-post send 沒 --ordered）先寄、有序後寄：history 裡有序那則在前。"""
        self.post({"role": "user", "content": "無序"}, ordered=False)
        self.post({"role": "user", "content": "有序"})
        p = self.start()
        self.assertTrue(self.until(self.answers))
        self.assertEqual([m["content"] for m in self.history()[:2]], ["有序", "無序"])
        self.assertEqual(self.stop(p)[0], 0)

    # ---- 6 開場白 ----

    def test_06_prompt(self):
        """idle 加 --prompt prompt.txt（相對範本）＋射後不理：不 say 也答、答完收工；再跑一次（history 非空）不重投；
        --prompt 指不到＝PromptMissing 退 1、不碰 queue；沒給旗標時同層的 prompt.txt 不投。"""
        def fsm(cfg):
            self.once(cfg)
            cfg["states"]["idle"]["exec"]["argv"] += ["--prompt", "prompt.txt"]
        d = self.copy(fsm=fsm, loop=lambda c: c.pop("interval_ms"))
        (d / "prompt.txt").write_text("開場白\n")
        r = self.run_([EXEC, "--ws", self.ws, d])
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        h = self.history()
        self.assertEqual(h[0], {"role": "user", "content": "開場白"})
        self.assertTrue(h[-1]["content"].startswith("FAKE ANSWER to: 開場白（tool said: "), h[-1])
        self.assertEqual(self.phase(), "done")
        r = self.run_([EXEC, "--ws", self.ws, d])
        self.assertEqual((r.returncode, len(self.history())), (0, len(h)))
        shutil.rmtree(self.stack)
        r = self.cell("idle.py", "--prompt", "nope.txt", cd=d)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("agent-fsm: PromptMissing "), r.stderr)
        self.assertFalse((self.stack / "queue").exists())
        r = self.cell("idle.py", cd=d)                                        # 沒給 --prompt：有 prompt.txt 也不投
        self.assertEqual((r.returncode, self.queue("new"), self.history()), (10, [], []))

    # ---- 7 停著等 vs 收工 ----

    def test_07_wait_vs_once(self):
        """範本（表接住 idle 的 10）queue 空時不退、phase 在 running／waiting，寄一封就答；射後不理那份 queue 空＝退 0。"""
        p = self.start()
        self.assertTrue(self.until(lambda: self.phase() in ("running", "waiting")))
        time.sleep(1.5)
        self.assertIsNone(p.poll())
        self.assertIn(self.phase(), ("running", "waiting"))
        self.say("在嗎")
        self.assertTrue(self.listen().startswith("FAKE ANSWER to: 在嗎"))
        self.assertEqual(self.stop(p)[0], 0)
        shutil.rmtree(self.stack)
        d = self.copy(fsm=self.once, loop=lambda c: c.pop("interval_ms"))
        r = self.run_([EXEC, "--ws", self.ws, d], timeout=30)
        self.assertEqual((r.returncode, r.stderr, self.history()), (0, "", []))

    # ---- 8 腦失敗停下等人 ----

    def test_08_brain_fails(self):
        """AOS_BRAIN_URL 指到馬上被拒的埠：brain 退 1 BrainFailed、loop 退 1、state.txt＝think、history 尾巴是 user；
        拿掉 URL 用同一個 stack 再起＝從 think 接著答、user 不重複。"""
        self.say("問")
        r = self.run_([EXEC, "--ws", self.ws, TEMPLATE], env=self.env({"AOS_BRAIN_URL": DEAD}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("agent-fsm: BrainFailed ", r.stderr)
        self.assertEqual((self.state_txt(), self.history()), ("think", [{"role": "user", "content": "問"}]))
        p = self.start()
        self.assertTrue(self.until(self.answers))
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(self.stop(p)[0], 0)

    # ---- 9 工具錯回給腦 ----

    def test_09_tool_error_back_to_brain(self):
        """登記一個會退 1 的工具、假腦先叫它：tool 訊息尾巴有結束碼、agent 不停、最後有答案。"""
        d = self.copy()
        bad = self.tmp / "bad"
        bad.mkdir()
        (bad / "_tooldef.json").write_text(json.dumps({"description": "壞掉的工具"}))
        (bad / "_entry").write_text("#!/bin/sh\necho 壞了\nexit 1\n")
        (bad / "_entry").chmod(0o755)
        (d / "tools.json").write_text(json.dumps({"tools": {"bad": {"path": str(bad)}}}))
        self.say("叫壞工具")
        p = self.start(d)
        self.assertTrue(self.until(self.answers))
        h = self.history()
        self.assertEqual(h[2], {"role": "tool", "tool_call_id": h[1]["tool_calls"][0]["id"], "content": "壞了\n(工具 bad 結束碼 1)\n"})
        self.assertIn("結束碼 1", h[3]["content"])
        code, err = self.stop(p)
        self.assertEqual(code, 0)
        self.assertIn("agent-fsm: ToolFailed bad 結束碼 1（回給腦）", err)

    # ---- 10 --system／--tools ----

    def test_10_system_and_tools(self):
        """真端點（本機假的）：--system 的內容在 request 最前面、不進 history；tools 是登記名；--tools 指別的登記檔就用那份；
        回覆只留 role／content／tool_calls；指不到＝SystemMissing／ToolsMissing；沒 tools.json 也沒 --tools＝不給工具、照答。"""
        brain = FakeBrain(self)
        self.say("幾點")
        p = self.start(env=self.env({"AOS_BRAIN_URL": brain.url}))
        self.assertTrue(self.until(self.answers))
        self.assertEqual(self.stop(p)[0], 0)
        first = brain.requests[0]
        self.assertEqual(first["path"], "/v1/chat/completions")
        self.assertEqual(first["model"], "chatgpt-gpt-6-luna-low")                       # 範本 .env
        self.assertEqual(first["messages"][0], {"role": "system", "content": (TEMPLATE / "system.txt").read_text()})
        self.assertEqual([t["function"]["name"] for t in first["tools"]], ["clock"])
        self.assertEqual(len(brain.requests), 2)
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(h[3], {"role": "assistant", "content": "real: 幾點"})

        shutil.rmtree(self.stack)                                             # --tools 指別的登記檔
        d = self.copy("tpl-tools", fsm=lambda c: (c["states"]["think"]["exec"]["argv"].extend(["--tools", "other.json"]),
                                                  c["states"]["act"]["exec"]["argv"].extend(["--tools", "other.json"])))
        (d / "other.json").write_text(json.dumps({"tools": {"tick": {"path": str(CLOCK)}}}))
        brain.requests.clear()
        self.say("幾點")
        p = self.start(d, env=self.env({"AOS_BRAIN_URL": brain.url}))
        self.assertTrue(self.until(self.answers))
        self.assertEqual(self.stop(p)[0], 0)
        self.assertEqual([t["function"]["name"] for t in brain.requests[0]["tools"]], ["tick"])
        self.assertTrue((self.stack / "tools" / "tick").is_dir())

        for script, flag, code in (("brain.py", "--system", "SystemMissing"), ("brain.py", "--tools", "ToolsMissing"),
                                   ("act.py", "--tools", "ToolsMissing")):
            r = self.cell(script, flag, "nope.txt")
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("agent-fsm: %s " % code), r.stderr)

        shutil.rmtree(self.stack)                                             # 沒有 tools.json＝不給工具
        d = self.copy("tpl-notools")
        (d / "tools.json").unlink()
        brain.requests.clear()
        self.say("沒工具")
        p = self.start(d, env=self.env({"AOS_BRAIN_URL": brain.url}))
        self.assertTrue(self.until(self.answers))
        self.assertEqual(self.stop(p)[0], 0)
        self.assertNotIn("tools", brain.requests[0])
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])

    # ---- 11 人改 history 再跑 ----

    def test_11_edit_history(self):
        """暫停時刪掉最後一則 assistant、state.txt 寫 think 再 resume＝brain 重問（用剩下的 history）；
        停下後把 state.txt 寫 think（最後一則已是答案）再起＝brain 退 10 回 idle、不多答；act 遇到沒 tool_calls＝HistoryBad。"""
        self.say("改我")
        p = self.start()
        self.assertTrue(self.until(self.answers))
        self.assertTrue(self.until(lambda: self.state_txt() == "idle"))
        self.ctl("pause")
        self.assertTrue(self.until(lambda: self.phase() == "paused"))
        lines = (self.stack / "history.jsonl").read_text().splitlines()
        (self.stack / "history.jsonl").write_text("\n".join(lines[:-1]) + "\n")   # 刪掉答案；最後一則是 tool
        (self.stack / "state.txt").write_text("think\n")
        self.ctl("resume")
        self.assertTrue(self.until(lambda: len(self.history()) == 4 and self.answers()))
        self.assertTrue(self.until(lambda: self.state_txt() == "idle"))
        self.assertEqual(self.stop(p)[0], 0)
        (self.stack / "state.txt").write_text("think\n")
        p = self.start()
        self.assertTrue(self.until(lambda: self.state_txt() == "idle"))
        time.sleep(0.8)
        self.assertEqual(len(self.history()), 4)
        self.assertEqual(self.stop(p)[0], 0)
        r = self.cell("act.py")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("agent-fsm: HistoryBad "), r.stderr)

    # ---- 12 掛 daemon ----

    def test_12_daemon(self):
        """aos-daemon-ctl add --ws W --name fsm1 範本＝loop 型、表上 running；aos-say／aos-listen 帶 --stack $(where --stack fsm1) 對話；
        pause→phase paused、新信留 new/；resume 答；stop→stopped、start 接著答（同一段 history）；rm 下表。"""
        ds = self.tmp / "dstack"
        ds.mkdir()
        (self.tmp / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                          "procs_ctl_mailbox": "procs_ctl_mailbox"}))
        denv = self.env({"AOS_DAEMON_STACK": str(ds)})
        d = subprocess.Popen([tool("aos-daemon"), str(self.tmp / "daemon.json")], cwd=str(self.tmp),
                             env=dict(denv, AOS_STACK=str(ds)), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.procs.append(d)
        self.assertTrue(self.until(lambda: (ds / "procs_ctl_mailbox" / "new").is_dir() and (ds / "procs_state.json").is_file()))

        def dctl(*args):
            r = self.run_([CTL, *args], env=denv)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()

        def row():
            return json.loads(dctl("ls", "--json"))["procs"].get("fsm1")
        dctl("add", "--ws", self.ws, "--name", "fsm1", TEMPLATE)
        self.assertTrue(self.until(lambda: (row() or {}).get("phase") == "running"))
        st = Path(dctl("where", "--stack", "fsm1"))
        self.assertEqual(st, ds / "procs" / "fsm1")
        self.say("第一句", stack=st)
        self.assertTrue(self.listen(stack=st).startswith("FAKE ANSWER to: 第一句"))
        dctl("pause", "fsm1")
        self.assertTrue(self.until(lambda: self.phase(st) == "paused"))
        sig = self.say("第二句", stack=st)
        time.sleep(1)
        self.assertEqual(self.queue("new", st), [sig])
        dctl("resume", "fsm1")
        self.assertTrue(self.listen(stack=st).startswith("FAKE ANSWER to: 第二句"))
        dctl("stop", "fsm1")
        self.assertTrue(self.until(lambda: (row() or {}).get("phase") == "stopped"))
        self.say("第三句", stack=st)
        dctl("start", "fsm1")
        self.assertTrue(self.until(lambda: (row() or {}).get("phase") == "running"))
        self.assertTrue(self.listen(stack=st).startswith("FAKE ANSWER to: 第三句"))
        self.assertEqual([m["content"] for m in self.history(st) if m["role"] == "user"], ["第一句", "第二句", "第三句"])
        dctl("rm", "fsm1")
        self.assertTrue(self.until(lambda: row() is None))
        self.assertEqual(sorted(os.listdir(self.ws)), [])                     # 掛 daemon 的 stack 在 daemon 的小格，工作區不長東西
        d.terminate()
        d.communicate(timeout=30)


if __name__ == "__main__":
    unittest.main()
