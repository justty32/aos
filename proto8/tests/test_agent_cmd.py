"""test_agent_cmd - proto8/extras/agent/bin/aos-agent（11-04 aos-agent 步 4、5；thinking 2026-11/04/aos-agent 05/01 的測試清單 15 案，加第 16 案：測試自己造的 llm／screen 入口）：
一支指令管掛在信箱模式 aos-daemon 上的一隻 agent（eca 與 loop／fsm agent 同一套子命令）；對象 --target ＞ $AOS_AGENT、daemon --daemon ＞ $AOS_DAEMON。

兩種 agent 都在暫存資料夾臨時組、自己寫 interfaces.json 宣告遵守 aos-agent：
- fsm：demo/agent-fsm 複製一份（tools.json 的 clock 改絕對路徑）；沒設 AOS_BRAIN_URL＝範本的假腦，要看 request 的案起本機假端點（test_agent_fsm.FakeBrain）。
- eca：照 test_eca_cmd 組（cli.json＋loop.json 叫 bin/aos-eca-turn）＋假 claude（test_cli_tools）；demo/eca-claude 有 screen/、llm/ 就一起複製進來。
靠別的步驟（步 1～3：screen／llm 入口、身體讀 stack 副本）的子案，那些檔還不在就 skip。不碰網路、不花額度。"""
import fcntl, json, os, shutil, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_cli_tools import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
from test_agent_fsm import FakeBrain  # noqa: E402

AGENT = ROOT / "extras" / "agent" / "bin" / "aos-agent"
SH = ROOT / "extras" / "agent" / "using-aos-agent.sh"
DCTL = ROOT / "bin" / "aos-daemon-ctl"
TOOLS = ROOT / "bin" / "aos-tools"
TURN = ROOT / "bin" / "aos-eca-turn"
FSM_TPL = ROOT / "demo" / "agent-fsm"
ECA_TPL = ROOT / "demo" / "eca-claude"
CLOCK = ROOT / "lib" / "base" / "clock"
DAEMON = tool("aos-daemon")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "AOS_DAEMON_STACK", "AOS_AGENT", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS", "AOS_BRAIN_URL", "AOS_BRAIN_KEY", "AOS_KERNEL_REPORT")
WRAP = '#!/bin/sh\nif [ -e "$BROKEN" ]; then echo \'{"is_error": true, "result": "壞了"}\'; exit 1; fi\nexec "$(dirname "$0")/claude-real" "$@"\n'
HAS_SCREEN = (ROOT / "bin" / "aos-eca-screen").exists() and (ECA_TPL / "screen").is_dir()
HAS_ECA_LLM = (ROOT / "bin" / "aos-eca-llm").exists() and (ECA_TPL / "llm").is_dir()
HAS_FSM_LLM = (FSM_TPL / "llm").is_dir()
FSM_COPIES = (FSM_TPL / "interfaces.json").exists()        # 步 2 落地＝身體會讀 $AOS_STACK/tools.json、llm.json


def daemon_has_exec():
    """daemon 表每列有 exec 欄（步 0）：看 daemon.cpp 原始碼。"""
    try:
        return "c.exec" in (ROOT / "impls" / "aos-daemon" / "src" / "daemon" / "daemon.cpp").read_text()
    except OSError:
        return False


class AgentCmd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-cmd-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, src in (("claude-real", FAKE_CLAUDE), ("claude", WRAP)):
            (self.bin / name).write_text(src)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.broken = self.tmp / "BROKEN"
        self.ds = self.tmp / "dstack"
        self.ds.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.daemon = None
        self.held = []
        self.addCleanup(self.kill_all)

    def kill_all(self):
        for f in self.held:
            f.close()
        for s in self.ds.glob("procs/*/claude/tty.sock"):
            subprocess.run(["tmux", "-S", str(s), "kill-server"], capture_output=True)
        if self.daemon and self.daemon.poll() is None:
            self.daemon.terminate()
            self.daemon.communicate(timeout=30)

    # ---- 組定義 ----

    def fsm_def(self, name="fsm-def", decl=None):
        d = self.tmp / name
        shutil.copytree(FSM_TPL, d)
        (d / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(CLOCK)}}}))
        if decl is None:
            decl = {"tools": "tools.json"}
            if HAS_FSM_LLM:
                decl["llm"] = "llm"
        (d / "interfaces.json").write_text(json.dumps({"aos-agent": decl}))
        return d

    def eca_def(self, name="eca-def", decl=None):
        d = self.tmp / name
        d.mkdir()
        cfg = json.loads((ROOT / "lib" / "agent" / "claude" / "cli.json").read_text())
        (d / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        # exec 照 demo/eca-claude 寫內嵌單子：daemon-ctl 換成 <d>/loop.json#/exec，表的 exec 欄才指得回定義
        (d / "loop.json").write_text(json.dumps({"exec": {"argv": [str(TURN), "--on-empty", "idle", {"$env": "AOS_CD"}]}, "interval_ms": 100,
                                                 "ctl": "ctl.json", "state": "state.json"}))
        (d / "_entry").write_text(json.dumps(["aos-loop", "loop.json"]))
        auto = {}
        for sub, ok in (("screen", HAS_SCREEN), ("llm", HAS_ECA_LLM)):
            if ok:
                shutil.copytree(ECA_TPL / sub, d / sub)
                auto[sub] = sub
        (d / "interfaces.json").write_text(json.dumps({"aos-agent": auto if decl is None else decl}))
        return d

    # ---- 跑 ----

    def env(self, extra=None, daemon=True):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log),
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"), FAKE_TRANSCRIPTS="1", BROKEN=str(self.broken))
        if daemon:
            e["AOS_DAEMON"] = str(self.ds)
        e.update(extra or {})
        return {k: v for k, v in e.items() if v is not None}

    def start_daemon(self, extra=None):
        (self.tmp / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                          "procs_ctl_mailbox": "procs_ctl_mailbox"}))
        self.daemon = subprocess.Popen([DAEMON, str(self.tmp / "daemon.json")], cwd=str(self.tmp),
                                       env=self.env(dict(extra or {}, AOS_STACK=str(self.ds))),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.until(lambda: (self.ds / "procs_ctl_mailbox" / "new").is_dir() and (self.ds / "procs_state.json").is_file()))

    def until(self, f, secs=20):
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

    def ag(self, *args, env=None, cwd=None, stdin=None, timeout=90):
        return subprocess.run([str(AGENT)] + [str(a) for a in args], capture_output=True, text=True, env=env or self.env(),
                              cwd=cwd or str(self.ws), input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
                              timeout=timeout)

    def ok(self, *args, **kw):
        r = self.ag(*args, **kw)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def add(self, name, d):
        return self.ok("add", "--name", name, d).stdout.strip()

    def rows(self):
        r = subprocess.run([str(DCTL), "ls", "--json"], capture_output=True, text=True, env=self.env())
        return json.loads(r.stdout)["procs"]

    def say_listen(self, name, text):
        self.ok("say", "--target", name, text)
        return self.ok("listen", "--target", name, "--timeout-s", "30").stdout

    def ls(self):
        return {x["name"]: x for x in json.loads(self.ok("ls", "--json").stdout)}

    # ---- 1、2 宣告與 add ----

    def tool_names(self, name):
        return sorted(l.split("\t")[0] for l in self.ok("tools", "--target", name).stdout.splitlines() if l.strip())

    def test_01_declare(self):
        """有 interfaces.json＋aos-agent key 的 add 過；沒檔、沒 key＝InterfaceMissing 不送信；壞 JSON＝InterfaceBad；
        fsm.json 弄壞 add 照過（不看它，第一圈才下表）。"""
        self.start_daemon()
        good = self.fsm_def()
        self.add("fsm1", good)
        bad = self.fsm_def("nodecl")
        (bad / "interfaces.json").unlink()
        self.assertEqual(self.code(self.ag("add", bad)), (1, "InterfaceMissing"))
        (bad / "interfaces.json").write_text(json.dumps({"other": {}}))
        self.assertEqual(self.code(self.ag("add", bad)), (1, "InterfaceMissing"))
        for text in ("{壞", "[1]", json.dumps({"aos-agent": "x"})):
            (bad / "interfaces.json").write_text(text)
            self.assertEqual(self.code(self.ag("add", bad)), (1, "InterfaceBad"), text)
        self.assertEqual(sorted(self.rows()), ["fsm1"])
        self.assertEqual(self.code(self.ag("add", self.tmp / "nope")), (1, "PathMissing"))
        self.assertEqual(self.code(self.ag("add")), (1, "ArgumentsBad"))
        broken = self.fsm_def("broken")
        (broken / "fsm.json").write_text("{壞")
        r = self.ag("add", "--name", "br", broken)
        self.assertIn(self.code(r), ((0, ""), (1, "WaitFailed")), r.stderr)   # 不驗內容：不會是 InterfaceBad／CfgBad
        self.assertTrue(self.until(lambda: "br" not in self.rows()))

    def test_02_add_wait(self):
        """兩種 add --name 回來時表上有、印的 stack＝where；撞名 InstanceExists 不送信。"""
        self.start_daemon()
        s1 = self.add("fsm1", self.fsm_def())
        s2 = self.add("e1", self.eca_def())
        self.assertEqual(sorted(self.rows()), ["e1", "fsm1"])
        self.assertEqual(self.ok("where", "--target", "fsm1").stdout.strip(), s1)
        self.assertEqual(self.ok("where", "--target", "e1").stdout.strip(), s2)
        r = self.ag("add", "--name", "fsm1", self.fsm_def("other"))
        self.assertEqual(self.code(r), (1, "InstanceExists"))
        self.assertEqual(len(os.listdir(self.ds / "procs_ctl_mailbox" / "new")), 0)

    # ---- 3 找 target ----

    def test_03_target(self):
        """--target 對；沒給看 AOS_AGENT；都沒有＝TargetMissing；表上沒有＝InstanceMissing；給 --stack＝FlagUnknown。"""
        self.start_daemon()
        s = self.add("fsm1", self.fsm_def())
        self.assertEqual(self.ok("where", "--target", "fsm1").stdout.strip(), s)
        self.assertEqual(self.ok("where", env=self.env({"AOS_AGENT": "fsm1"})).stdout.strip(), s)
        r = self.ag("where")
        self.assertEqual(self.code(r), (1, "TargetMissing"))
        self.assertIn("AOS_AGENT", r.stderr)
        for cmd in ("state", "where", "say", "listen"):
            self.assertEqual(self.code(self.ag(cmd, "--target", "nobody", *(["話"] if cmd == "say" else []))), (1, "InstanceMissing"), cmd)
            self.assertEqual(self.code(self.ag(cmd, "--stack", s)), (1, "FlagUnknown"), cmd)

    # ---- 4 ls／state／status ----

    def test_04_ls_state(self):
        """兩隻一行一列、狀態、工作區、queue 數；status＝state；pause 後 paused。"""
        self.start_daemon()
        self.add("fsm1", self.fsm_def())
        self.add("e1", self.eca_def())
        rows = self.ls()
        self.assertEqual(sorted(rows), ["e1", "fsm1"])
        for n in rows:
            self.assertEqual((rows[n]["state"], rows[n]["ws"]), ("running", str(self.ws)))
        lines = self.ok("ls").stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].split()[1:3], ["running", str(self.ws)])
        st = self.ok("state", "--target", "fsm1").stdout
        self.assertIn("工作區 %s" % self.ws, st)
        self.assertIn("stack  %s" % rows["fsm1"]["stack"], st)
        self.assertEqual(self.ok("status", "--target", "fsm1").stdout, st)
        self.ok("pause", "--target", "fsm1")
        self.assertTrue(self.until(lambda: self.ls()["fsm1"]["state"] == "paused"))
        self.ok("say", "--target", "fsm1", "排著")
        self.assertEqual(self.ls()["fsm1"]["queued"], 1)
        self.assertIn("queue  1 封", self.ok("state", "--target", "fsm1").stdout)

    # ---- 5 start／stop／pause／resume ----

    def test_05_start_stop_pause(self):
        """stop→stopped、where 照找得到、say 照寄；start 接著答；pause→新信留 new/；resume 答。"""
        self.start_daemon()
        s = self.add("fsm1", self.fsm_def())
        self.assertIn("停了", self.ok("stop", "--target", "fsm1").stdout)
        self.assertEqual(self.ls()["fsm1"]["state"], "stopped")
        self.assertIn("本來就停著", self.ok("stop", "--target", "fsm1").stdout)
        self.assertEqual(self.ok("where", "--target", "fsm1").stdout.strip(), s)
        r = self.ok("say", "--target", "fsm1", "停著時寄的")
        self.assertIn("aos-agent start --target fsm1", r.stderr)
        self.assertIn("接著答", self.ok("start", "--target", "fsm1").stdout)
        self.assertIn("本來就在跑", self.ok("start", "--target", "fsm1").stdout)
        self.assertIn("停著時寄的", self.ok("listen", "--target", "fsm1", "--timeout-s", "30").stdout)
        self.ok("pause", "--target", "fsm1")
        self.assertTrue(self.until(lambda: self.ls()["fsm1"]["state"] == "paused"))
        sig = self.ok("say", "--target", "fsm1", "暫停時寄的").stdout.strip()
        time.sleep(1)
        self.assertTrue((Path(s) / "queue" / "new" / sig).exists())
        self.ok("resume", "--target", "fsm1")
        self.assertIn("暫停時寄的", self.ok("listen", "--target", "fsm1", "--timeout-s", "30").stdout)

    # ---- 6 rm ----

    def test_06_rm(self):
        """rm 名字 下表、stack 不在（含副本）；再 state＝InstanceMissing；只設 AOS_AGENT 不給名字＝ArgumentsBad。"""
        self.start_daemon()
        s = Path(self.add("fsm1", self.fsm_def()))
        if daemon_has_exec():
            self.ok("tools", "--target", "fsm1", "add", "x", CLOCK)
            self.assertTrue((s / "tools.json").is_file())
        self.assertEqual(self.code(self.ag("rm", env=self.env({"AOS_AGENT": "fsm1"}))), (1, "ArgumentsBad"))
        self.assertIn("刪了 fsm1", self.ok("rm", "fsm1").stdout)
        self.assertNotIn("fsm1", self.rows())
        self.assertFalse(s.exists())
        self.assertEqual(self.code(self.ag("state", "--target", "fsm1")), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ag("rm", "fsm1")), (1, "InstanceMissing"))

    # ---- 7 say／listen ----

    def test_07_say_listen(self):
        """AOS_AGENT=… say 話 && listen 兩種都答；listen --last／--follow 照舊；--timeout 舊名＝FlagUnknown。"""
        self.start_daemon()
        self.add("fsm1", self.fsm_def())
        self.add("e1", self.eca_def())
        for name, want in (("fsm1", "FAKE ANSWER to: 現在幾點"), ("e1", ": 現在幾點")):
            env = self.env({"AOS_AGENT": name})
            sig = self.ok("say", "現在幾點", env=env).stdout.strip()
            self.assertRegex(sig, r"^[0-9]{12}\.")
            out = self.ok("listen", "--timeout-s", "30", env=env).stdout
            self.assertIn(want, out)
        self.ok("say", "--target", "fsm1", stdin="又一句\n")                       # 話沒給＝讀 stdin
        self.assertIn("又一句", self.ok("listen", "--target", "fsm1", "--timeout-s", "30").stdout)
        r = self.ok("listen", "--target", "fsm1", "--last", "1")
        self.assertTrue(r.stdout.startswith("== #2\n> 又一句\n"), r.stdout)
        self.assertEqual(self.code(self.ag("listen", "--target", "fsm1", "--timeout", "3")), (1, "FlagUnknown"))
        self.assertEqual(self.code(self.ag("listen", "--target", "fsm1", "--last", "1", "--timeout-s", "3")), (1, "ArgumentsBad"))
        p = subprocess.Popen([str(AGENT), "listen", "--target", "fsm1", "--follow"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=self.env(), stdin=subprocess.DEVNULL)
        time.sleep(0.5)
        self.ok("say", "--target", "fsm1", "跟著看")
        self.assertTrue(self.until(lambda: "跟著看" in self.ok("listen", "--target", "fsm1", "--last", "1").stdout, 30))
        time.sleep(0.6)
        p.send_signal(signal.SIGINT)
        out, _ = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0)
        self.assertIn("== #3\n> 跟著看\n", out)

    # ---- 8 chat ----

    def test_08_chat(self):
        """stdin 餵兩行→stdout 兩個回答、不含信件名稱；等答案時送 SIGINT→退 130、stderr 含「已寄出」、agent 照答、之後 listen 印得到。"""
        self.start_daemon()
        s = Path(self.add("fsm1", self.fsm_def()))
        r = self.ok("chat", "--target", "fsm1", stdin="第一句\n\n第二句\n")
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 2, r.stdout)
        self.assertTrue(lines[0].startswith("FAKE ANSWER to: 第一句") and lines[1].startswith("FAKE ANSWER to: 第二句"), r.stdout)
        self.assertNotRegex(r.stdout, r"[0-9]{12}\.")
        self.assertIn("Ctrl-C", r.stderr)
        self.ok("pause", "--target", "fsm1")
        self.assertTrue(self.until(lambda: self.ls()["fsm1"]["state"] == "paused"))
        p = subprocess.Popen([str(AGENT), "chat", "--target", "fsm1"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=self.env())
        p.stdin.write("按掉前寄的\n")
        p.stdin.flush()
        self.assertTrue(self.until(lambda: os.listdir(s / "queue" / "new")))
        time.sleep(0.3)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 130, err)
        self.assertIn("已寄出", err)
        self.ok("resume", "--target", "fsm1")
        self.assertIn("按掉前寄的", self.ok("listen", "--target", "fsm1", "--timeout-s", "30").stdout)

    # ---- 9 tools 副本 ----

    @unittest.skipUnless(daemon_has_exec(), "daemon 表還沒有 exec 欄（步 0）")
    def test_09_tools_copy(self):
        """tools 印 clock、stderr 說用的是定義；tools add x→<stack>/tools.json、path 絕對；定義沒動；改定義後副本不跟；reset 後跟；
        沒宣告＝ToolsMissing。下一題假腦叫得到 x（步 2 落地才驗）。"""
        brain = FakeBrain(self)
        self.start_daemon({"AOS_BRAIN_URL": brain.url} if FSM_COPIES else None)
        d = self.fsm_def()
        s = Path(self.add("fsm1", d))
        r = self.ok("tools", "--target", "fsm1")
        self.assertIn("clock", r.stdout)
        self.assertIn("定義", r.stderr)
        before = (d / "tools.json").read_text()
        self.ok("tools", "--target", "fsm1", "add", "x", os.path.relpath(CLOCK, self.ws))
        reg = json.loads((s / "tools.json").read_text())
        self.assertEqual(sorted(reg["tools"]), ["clock", "x"])
        self.assertTrue(all(os.path.isabs(t["path"]) for t in reg["tools"].values()))
        self.assertEqual((d / "tools.json").read_text(), before)
        r = self.ok("tools", "--target", "fsm1", "ls")
        self.assertIn("副本", r.stderr)
        self.assertEqual(sorted(l.split("\t")[0] for l in r.stdout.splitlines()), ["clock", "x"])
        if FSM_COPIES:
            brain.requests.clear()
            self.say_listen("fsm1", "用工具")
            self.assertIn("x", [t["function"]["name"] for t in brain.requests[0]["tools"]])
        subprocess.run([str(TOOLS), "--file", str(d / "tools.json"), "add", "--name", "y", str(CLOCK)], check=True,
                       capture_output=True, env=self.env())
        self.assertEqual(self.tool_names("fsm1"), ["clock", "x"])                 # 副本不跟定義
        self.ok("tools", "--target", "fsm1", "rm", "x")
        self.assertEqual(self.tool_names("fsm1"), ["clock"])
        self.assertIn("刪了副本", self.ok("tools", "--target", "fsm1", "reset").stdout)
        self.assertFalse((s / "tools.json").exists())
        self.assertEqual(self.tool_names("fsm1"), ["clock", "y"])
        self.add("e0", self.eca_def("eca-notools", decl={}))
        self.assertEqual(self.code(self.ag("tools", "--target", "e0")), (1, "ToolsMissing"))

    # ---- 10 llm 副本 ----

    @unittest.skipUnless(daemon_has_exec() and HAS_FSM_LLM, "步 0（exec 欄）或步 2（agent-fsm/llm）還沒落地")
    def test_10_llm_copy(self):
        """llm show 有 model=；set model=x→<stack>/llm.json、下一題假端點收到 model=x、定義 .env 沒動；reset 刪檔；set zzz=1＝KeyUnknown；
        沒宣告＝LlmMissing；llm/ 沒宣告 aos-agent/llm＝LlmBad；eca 的 set model=haiku→假 CLI 收到 --model haiku（步 1 落地才驗）。"""
        brain = FakeBrain(self)
        self.start_daemon({"AOS_BRAIN_URL": brain.url})
        d = self.fsm_def()
        s = Path(self.add("fsm1", d))
        env_before = (d / ".env").read_text()
        self.assertIn("model=", self.ok("llm", "--target", "fsm1").stdout)
        r = self.ok("llm", "--target", "fsm1", "set", "model=x")
        self.assertIn("model=x", r.stdout)
        self.assertEqual(json.loads((s / "llm.json").read_text()).get("model"), "x")
        self.assertEqual((d / ".env").read_text(), env_before)
        brain.requests.clear()
        self.say_listen("fsm1", "換腦了")
        self.assertEqual(brain.requests[-1]["model"], "x")
        r = self.ag("llm", "--target", "fsm1", "set", "zzz=1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("KeyUnknown", r.stderr)
        self.ok("llm", "--target", "fsm1", "reset")
        self.assertFalse((s / "llm.json").exists())
        self.add("e0", self.eca_def("eca-nollm", decl={}))
        self.assertEqual(self.code(self.ag("llm", "--target", "e0")), (1, "LlmMissing"))
        d2 = self.fsm_def("fsm-badllm")
        (d2 / "llm" / "interfaces.json").write_text("{}")
        self.add("fsm2", d2)
        self.assertEqual(self.code(self.ag("llm", "--target", "fsm2")), (1, "LlmBad"))
        if HAS_ECA_LLM:
            self.add("e1", self.eca_def())
            self.ok("llm", "--target", "e1", "set", "model=haiku")
            self.say_listen("e1", "換模型")
            last = [json.loads(l) for l in self.log.read_text().splitlines() if l.strip()][-1]
            self.assertIn("haiku", json.dumps(last))

    # ---- 11 同定義提醒 ----

    @unittest.skipUnless(daemon_has_exec(), "daemon 表還沒有 exec 欄（步 0）")
    def test_11_shared_def(self):
        """bob、ann 都從同一資料夾 add，tools add／llm set --target bob 的 stderr 含「ann 也用這份定義」；ann 的 stack 沒副本。"""
        self.start_daemon()
        d = self.fsm_def()
        self.add("bob", d)
        ann = Path(self.add("ann", d))
        r = self.ok("tools", "--target", "bob", "add", "x", CLOCK)
        self.assertIn("ann 也用這份定義", r.stderr)
        self.assertFalse((ann / "tools.json").exists())
        if HAS_FSM_LLM:
            self.assertIn("ann 也用這份定義", self.ok("llm", "--target", "bob", "set", "model=x").stderr)
        self.add("solo", self.fsm_def("other"))
        self.assertNotIn("也用這份定義", self.ok("tools", "--target", "solo", "add", "x", CLOCK).stderr)

    # ---- 12 screen ----

    @unittest.skipUnless(daemon_has_exec(), "daemon 表還沒有 exec 欄（步 0）")
    def test_12_screen(self):
        """fsm 的 open／close／watch＝ScreenMissing、訊息含 listen --follow；eca 的 screen/interfaces.json 拿掉＝ScreenBad；
        eca open -d 開得了；rm 時正在答（格的 lock 被拿著）＝SessionBad、不拔。後三個要步 1 的 aos-eca-screen。"""
        self.start_daemon()
        self.add("fsm1", self.fsm_def())
        for act in ("open", "close", "watch"):
            r = self.ag(act, "--target", "fsm1")
            self.assertEqual(self.code(r), (1, "ScreenMissing"), act)
            self.assertIn("listen --follow", r.stderr)
        if not HAS_SCREEN:
            self.skipTest("步 1 的 bin/aos-eca-screen、demo/eca-claude/screen 還不在")
        bad = self.eca_def("eca-badscreen")
        (bad / "screen" / "interfaces.json").unlink()
        self.add("eb", bad)
        self.assertEqual(self.code(self.ag("open", "-d", "--target", "eb")), (1, "ScreenBad"))
        s = Path(self.add("e1", self.eca_def()))
        if HAS_TMUX:
            r = self.ok("open", "-d", "--target", "e1")
            self.assertTrue((s / "claude" / "tty.sock").exists(), r.stdout)
            self.ok("close", "--target", "e1")
        (s / "claude").mkdir(exist_ok=True)
        f = open(s / "claude" / "lock", "w")
        self.held.append(f)
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(self.code(self.ag("rm", "e1")), (1, "SessionBad"))
        self.assertIn("e1", self.rows())

    # ---- 13 自己結束的 ----

    def test_13_self_exit(self):
        """fsm 腦失敗退 1 下表後 ls 不列、state＝InstanceMissing；修好同名再 add（同一個 stack）接著答。"""
        self.start_daemon()
        d = self.fsm_def()
        (d / "system.txt").rename(d / "system.bak")              # brain.py --system 找不到＝SystemMissing、退 1
        s = self.add("fsm1", d)
        self.ok("say", "--target", "fsm1", "會壞的一句")
        self.assertTrue(self.until(lambda: "fsm1" not in self.rows(), 30))
        self.assertNotIn("fsm1", self.ls())
        self.assertEqual(self.code(self.ag("state", "--target", "fsm1")), (1, "InstanceMissing"))
        (d / "system.bak").rename(d / "system.txt")
        self.assertEqual(self.add("fsm1", d), s)                   # 同一個 stack：history 停在那句 user，接著答它
        self.assertTrue(self.until(lambda: "會壞的一句" in self.ok("listen", "--target", "fsm1", "--last", "1").stdout, 30))
        self.assertIn("又一句", self.say_listen("fsm1", "又一句"))

    # ---- 14 daemon ----

    def test_14_daemon(self):
        """沒設 AOS_DAEMON＝DaemonMissing；只設舊名＝DaemonMissing 提示新名；--daemon 給了照用；
        daemon 沒在跑 ls 照表印＋stderr 注意、add＝DaemonMissing；不認得的子命令＝CommandUnknown。"""
        self.assertEqual(self.code(self.ag("ls", env=self.env(daemon=False))), (1, "DaemonMissing"))
        r = self.ag("ls", env=self.env({"AOS_DAEMON_STACK": str(self.ds)}, daemon=False))
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertIn("AOS_DAEMON", r.stderr.replace("AOS_DAEMON_STACK", ""))
        self.assertEqual(self.code(self.ag("frob")), (1, "CommandUnknown"))
        (self.ds / "procs_state.json").write_text(json.dumps({"procs": {"old": {"phase": "running", "pid": 999999999, "stack": str(self.tmp)}},
                                                              "pid": 999999999, "started_at_ticks": 1}))
        r = self.ag("--daemon", self.ds, "ls", env=self.env(daemon=False))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("old "), r.stdout)
        self.assertIn("沒在跑", r.stderr)
        self.assertEqual(self.code(self.ag("add", self.fsm_def())), (1, "DaemonMissing"))

    # ---- 16 子介面的接法（測試自己造的 llm／screen 入口，不等步 1、2） ----

    @unittest.skipUnless(daemon_has_exec(), "daemon 表還沒有 exec 欄（步 0）")
    def test_16_fake_entries(self):
        """llm 入口收到 `stack 動作…`、AOS_STACK＝那隻的 stack、stdout 透傳；入口自己的錯（KeyUnknown）原樣轉、退 1；
        screen 入口收到 open -d／close／watch；rm 時 close 報 SessionBad＝不拔；入口退 0 才往下拔。"""
        LLM = ('import json, os, sys\nf = os.path.join(os.environ["AOS_STACK"], "llm.json")\na = sys.argv[1:]\n'
               'cur = json.load(open(f)) if os.path.exists(f) else {}\n'
               'if a[:2] == ["stack", "set"]:\n    for kv in a[2:]:\n        k, _, v = kv.partition("=")\n'
               '        if k != "model":\n            print("llm: KeyUnknown " + k, file=sys.stderr); sys.exit(1)\n        cur[k] = v\n'
               '    json.dump(cur, open(f, "w"))\nelif a[:2] == ["stack", "reset"] and os.path.exists(f):\n    os.unlink(f)\n'
               'print("model=" + cur.get("model", "def") if a[1] != "reset" else "model=def")\n')
        SCREEN = ('import os, sys\nif os.path.exists(os.path.join(os.environ["AOS_STACK"], "BUSY")):\n'
                  '    print("screen: SessionBad 正在答", file=sys.stderr); sys.exit(1)\n'
                  'print("screen " + " ".join(sys.argv[1:]) + " " + os.environ["AOS_WS"])\n')
        self.start_daemon()
        d = self.fsm_def(decl={"llm": "llm", "screen": "screen"})
        for sub, src in (("llm", LLM), ("screen", SCREEN)):
            (d / sub).mkdir(exist_ok=True)
            (d / sub / "_entry").write_text(json.dumps(["python3", "main.py"]))
            (d / sub / "main.py").write_text(src)
            (d / sub / "interfaces.json").write_text(json.dumps({"aos-agent/" + sub: {}}))
        s = Path(self.add("f1", d))
        self.assertEqual(self.ok("llm", "--target", "f1").stdout, "model=def\n")
        self.assertEqual(self.ok("llm", "--target", "f1", "set", "model=x").stdout, "model=x\n")
        self.assertEqual(json.loads((s / "llm.json").read_text()), {"model": "x"})
        r = self.ag("llm", "--target", "f1", "set", "zzz=1")
        self.assertEqual(self.code(r), (1, "KeyUnknown"))
        self.ok("llm", "--target", "f1", "reset")
        self.assertFalse((s / "llm.json").exists())
        self.assertEqual(self.code(self.ag("llm", "--target", "f1", "frob")), (1, "CommandUnknown"))
        self.assertEqual(self.ok("open", "-d", "--target", "f1").stdout, "screen open -d %s\n" % self.ws)
        self.assertEqual(self.ok("watch", "--target", "f1").stdout, "screen watch %s\n" % self.ws)
        (s / "BUSY").write_text("")
        self.assertEqual(self.code(self.ag("rm", "f1")), (1, "SessionBad"))
        self.assertEqual(self.code(self.ag("stop", "--target", "f1")), (1, "SessionBad"))
        self.assertIn("f1", self.rows())
        (s / "BUSY").unlink()
        self.ok("rm", "f1")
        self.assertNotIn("f1", self.rows())

    # ---- 15 using-aos-agent.sh ----

    def test_15_using_sh(self):
        """source using-aos-agent.sh bob：四個函數在、AOS_AGENT=bob；rm 沒被定義；不帶名字只定義函數。"""
        r = subprocess.run(["bash", "-c", 'source "$0" bob; declare -f say listen chat status >/dev/null && echo "ok $AOS_AGENT"; '
                            'declare -f rm >/dev/null && echo has-rm; true', str(SH)], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.stdout.strip(), "ok bob", r.stderr)
        r = subprocess.run(["bash", "-c", 'unset AOS_AGENT; source "$0"; declare -f say >/dev/null && echo "ok [${AOS_AGENT-}]"', str(SH)],
                           capture_output=True, text=True, env=self.env())
        self.assertEqual(r.stdout.strip(), "ok []", r.stderr)
        r = subprocess.run(["bash", "-c", 'source "$0" bob; say', str(SH)], capture_output=True, text=True, env=self.env(daemon=False))
        self.assertTrue(r.stderr.startswith("aos-agent: "), r.stderr)          # 函數真的叫到 aos-agent


if __name__ == "__main__":
    unittest.main()
