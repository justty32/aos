"""test_eca_cmd - proto8/extras/eca（10-30 eca 第 6 步，取代 10-28 的 test_hub）：aos-eca 把外部 coding agent 掛到
信箱模式的 aos-daemon 底下（aos-daemon-ctl add --ws），三對指令 open／close、start／stop、add／rm（使用者 11-02 晚；11-03 remove 改 rm）與 ls／state，
以及 aos-say／aos-listen 帶 --stack $(aos-daemon-ctl where --stack 名字) 對它說話（11-03 起工作區沒有 .stack 捷徑）。
11-03 procs：daemon 的窗是 procs_ctl_mailbox／procs_state.json、一張表 procs；stack 一律拿表上那一列的；stop／start＝aos-daemon-ctl stop／start
（停著還在表上、where 找得到、信排在 queue）；自己結束的（CLI 出錯、直接寫 ctl 的 stop）下了表＝不在了，同名再 add 接著用；add --stack S。

eca 資料夾在測試裡臨時組（cli.json＋loop.json 叫 bin/aos-eca-turn --on-empty idle＋_entry 轉 aos-loop），add 的 XXX 就給它（11-03：沒有 --kind／--template）；CLI 用 test_cli_tools 的假 claude
（外面包一層：有 BROKEN 這個檔就退 1，測 CLI 出錯），不花額度。要 tmux 的只有 open -d 那案（沒有就 skip）。
設計：proto8/thinking/2026-10/30/eca/README.md C 結論 7～10。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_cli_tools import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
CTL = ROOT / "extras" / "eca" / "bin" / "aos-eca"
HUMAN = ROOT / "extras" / "human" / "bin"
TURN = ROOT / "bin" / "aos-eca-turn"
DAEMON = tool("aos-daemon")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "AOS_DAEMON_STACK", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")
WRAP = '#!/bin/sh\nif [ -e "$BROKEN" ]; then echo \'{"is_error": true, "result": "壞了"}\'; exit 1; fi\nexec "$(dirname "$0")/claude-real" "$@"\n'


class EcaCtl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-cmd-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, src in (("claude-real", FAKE_CLAUDE), ("claude", WRAP)):
            (self.bin / name).write_text(src)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.broken = self.tmp / "BROKEN"
        self.tpl = self.tmp / "eca-claude"                          # 定義：exec 直接寫 aos-eca-turn 與定義的絕對路徑（不靠 AOS_CD）
        self.tpl.mkdir()
        cfg = json.loads((ROOT / "lib" / "agent" / "claude" / "cli.json").read_text())
        (self.tpl / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        (self.tpl / "loop.json").write_text(json.dumps({"exec": [str(TURN), "--on-empty", "idle", str(self.tpl)], "interval_ms": 100,
                                                        "ctl": "ctl.json", "state": "state.json"}))
        (self.tpl / "_entry").write_text(json.dumps(["aos-loop", "loop.json"]))
        self.ds = self.tmp / "dstack"                                # daemon 的 $AOS_STACK＝AOS_DAEMON_STACK
        self.ds.mkdir()
        self.daemon = None
        self.socks = []
        self.names = {}                                              # 工作區名 → eca 名字（where 用）
        self.addCleanup(self.kill_all)

    def kill_all(self):
        for s in self.socks:
            subprocess.run(["tmux", "-S", str(s), "kill-server"], capture_output=True)
        if self.daemon and self.daemon.poll() is None:
            self.daemon.terminate()
            self.daemon.communicate(timeout=30)

    def env(self, extra=None, daemon=True):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + str(ROOT / "bin") + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log),
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"), FAKE_TRANSCRIPTS="1",
                 BROKEN=str(self.broken))
        if daemon:
            e["AOS_DAEMON_STACK"] = str(self.ds)
        e.update(extra or {})
        return e

    def start_daemon(self):
        (self.tmp / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                          "procs_ctl_mailbox": "procs_ctl_mailbox"}))
        self.daemon = subprocess.Popen([DAEMON, str(self.tmp / "daemon.json")], cwd=str(self.tmp), env=self.env({"AOS_STACK": str(self.ds)}),
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

    def run_(self, argv, cwd=None, env=None, timeout=60):
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=env or self.env(), cwd=cwd,
                              stdin=subprocess.DEVNULL, timeout=timeout)

    def ctl(self, *args, cwd=None, env=None):
        return self.run_([CTL, *args], cwd=cwd, env=env)

    def ls(self):
        r = self.ctl("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def daemon_rows(self):
        r = self.run_([ROOT / "bin" / "aos-daemon-ctl", "ls", "--json"])
        return json.loads(r.stdout)["procs"]

    def ws(self, name="proj"):
        w = self.tmp / name
        w.mkdir()
        self.socks.append(self.ds / "procs" / name / "claude" / "tty.sock")
        return w

    def add(self, w, name=None):
        """aos-eca add --name 名字 --ws w eca 資料夾（名字沒給＝工作區名，測試裡好認）。"""
        name = name or w.name
        r = self.ctl("add", "--name", name, "--ws", w, self.tpl)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: any(x["name"] == name for x in self.ls())), self.daemon_rows())
        self.names[w.name] = name
        return name

    def where(self, w):
        """這個工作區那隻的 stack：aos-daemon-ctl where --stack 名字（11-03 起工作區沒有 .stack 捷徑；只認 daemon 表上的）。"""
        r = self.run_([ROOT / "bin" / "aos-daemon-ctl", "where", "--stack", self.names.get(w.name, w.name)])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def say(self, w, text, stack=None):
        """aos-say --stack $(where) 話（下了表的給 stack＝它的資料夾）；cwd 在工作區。"""
        r = self.run_([HUMAN / "aos-say", "--stack", stack or self.where(w), text], cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, w):
        r = self.run_([HUMAN / "aos-listen", "--stack", self.where(w), "--timeout", "20"], cwd=w)   # 不帶信件名稱＝等最新那封（11-01 晚翻案）
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def say_listen(self, w, text):
        """aos-say 話 && aos-listen。"""
        self.say(w, text)
        return self.listen(w)

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def test_daemon_missing(self):
        """AOS_DAEMON_STACK 沒設＝DaemonMissing；資料夾在、daemon 沒在跑（沒有 procs_state、或它的 pid＋started_at_ticks 對不上；11-02 起沒有心跳）＝同。
        11-02 改名：只設舊的 AOS_DAEMON＝DaemonMissing、訊息提示 AOS_DAEMON_STACK；給舊旗標 --daemon＝FlagUnknown。"""
        self.assertEqual(self.code(self.ctl("ls", env=self.env(daemon=False))), (1, "DaemonMissing"))
        r = self.ctl("ls", env=self.env({"AOS_DAEMON": str(self.ds)}, daemon=False))
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertIn("AOS_DAEMON_STACK", r.stderr)
        self.assertEqual(self.code(self.ctl("--daemon", str(self.ds), "ls")), (1, "FlagUnknown"))
        self.assertEqual(self.code(self.ctl("ls")), (1, "DaemonMissing"))
        (self.ds / "procs_state.json").write_text(json.dumps({"procs": {}, "pid": 999999999,
                                                              "started_at_ticks": 1}))
        r = self.ctl("add", "--ws", self.ws(), self.tpl)
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertTrue(r.stderr.startswith("aos-eca: DaemonMissing "), r.stderr)
        self.assertEqual(self.code(self.ctl("frob")), (1, "CommandUnknown"))

    def test_add_ls_state_say_listen(self):
        """add 後 daemon 表上有它（11-03 起不再順手掛 eca_reap）、工作區不多東西（11-03 起沒有 .stack 捷徑）；ls 列得到、state 認得（資料夾或名字）；
        cd 到工作區 say／listen 經 daemon 底下的實例答得出（假 claude，第二句 --resume 同一段）；
        XXX 沒有 cli.json＝EcaBad、不在＝PathMissing、沒給＝ArgumentsBad、--ws 不在＝PathMissing、舊旗標 --template／--kind＝FlagUnknown。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.assertIn(name, self.daemon_rows())
        self.add(self.ws("second"))
        self.assertEqual(sorted(self.daemon_rows()), [name, "second"])
        self.assertFalse(os.path.lexists(w / ".stack"))
        it = next(x for x in self.ls() if x["name"] == name)
        self.assertEqual((it["name"], it["kind"], it["ws"], it["state"], it["screen"], it["phase"]),
                         (name, "claude", str(w), "running", "closed", "running"))
        for arg in ((), ("proj",)):
            r = self.ctl("state", *arg, cwd=w)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("工作區 %s" % w, r.stdout)
            self.assertEqual(self.ctl("status", *arg, cwd=w).stdout, r.stdout)    # 11-03：status＝state 的別名
        self.assertEqual(self.code(self.ctl("state", cwd=self.tmp)), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ctl("status", cwd=self.tmp)), (1, "InstanceMissing"))
        a1 = self.say_listen(w, "你好")
        self.assertTrue(a1.startswith("fake claude[") and a1.rstrip().endswith(": 你好"), a1)
        sid = (self.ds / "procs" / name / "claude" / "session.txt").read_text().strip()
        self.assertTrue(self.say_listen(w, "再一句").startswith("fake claude[%s]" % sid[:8]))
        r = self.ctl("ls")
        self.assertIn("session %s" % sid[:8], r.stdout)
        line = next(x for x in r.stdout.splitlines() if x.startswith(name + " "))     # 11-03：名字 狀態 畫面 種類 工作區 session id
        self.assertEqual(line.split(), [name, "running", "closed", "claude", str(w), "session", sid[:8]])
        other = self.ws("other")
        self.assertEqual(self.code(self.ctl("add", "--ws", other, self.tmp)), (1, "EcaBad"))
        self.assertEqual(self.code(self.ctl("add", "--ws", other, self.tmp / "nope")), (1, "PathMissing"))
        self.assertEqual(self.code(self.ctl("add", cwd=other)), (1, "ArgumentsBad"))
        self.assertEqual(self.code(self.ctl("add", "--ws", self.tmp / "nope", self.tpl)), (1, "PathMissing"))
        for old in ("--template", "--kind"):
            self.assertEqual(self.code(self.ctl("add", old, "claude", self.tpl, cwd=other)), (1, "FlagUnknown"))
        for empty in (("--stack", ""), ("--stack=",)):
            self.assertEqual(self.code(self.ctl("add", *empty, self.tpl, cwd=other)), (1, "ArgumentsBad"))
        self.assertNotIn("other", self.daemon_rows())

    def test_close_stop_start(self):
        """close（畫面沒開）＝本來就沒畫面、再 say 照答；stop＝aos-daemon-ctl stop（11-03 procs）：daemon 表上留成 stopped、小格原樣留、
        ls 的狀態 stopped、where 照找得到，這期間 say 的信排在 queue、沒人答；start＝aos-daemon-ctl start，同一個 stack 起來、接著答那封（同一段對話）。
        已在跑再 start、已停再 stop＝說一句、退 0；aos-daemon-ctl pause＝ls、state 的狀態 paused，resume 回 running（11-03 英文名詞）。沒有 eca_archive（11-02 晚：不封存）。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "第一句")
        r = self.ctl("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "本來就沒畫面（已收起）"), r.stderr)
        self.assertIn("第二句", self.say_listen(w, "第二句"))
        cell = self.ds / "procs" / name
        sid = (cell / "claude" / "session.txt").read_text().strip()
        pid = self.daemon_rows()[name]["pid"]
        r = self.ctl("stop", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stack 留著", r.stdout)
        row = self.daemon_rows()[name]                               # 11-03：停著還在表上
        self.assertEqual((row["phase"], row["pid"], row["stack"]), ("stopped", None, str(cell)))
        self.assertEqual(self.where(w), str(cell))
        self.assertEqual([x["state"] for x in self.ls()], ["stopped"])
        self.assertEqual(self.ctl("stop", name).stdout.strip(), "本來就停著（stopped）")
        sig = self.say(w, "停著時的一句")                              # where 照找得到
        time.sleep(0.5)                                              # 子 loop 在的話 100 ms 就會認領
        self.assertEqual(os.listdir(cell / "queue" / "new"), [sig])
        self.assertEqual(len((cell / "history.jsonl").read_text().splitlines()), 4)
        r = self.ctl("start", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("起來了（同一個 stack），queue 裡 1 封", r.stdout)
        a = self.listen(w)
        self.assertTrue(a.startswith("fake claude[%s]" % sid[:8]) and "停著時的一句" in a, a)
        self.assertEqual(self.ls()[0]["state"], "running")
        self.assertNotEqual(self.daemon_rows()[name]["pid"], pid)
        self.assertEqual(self.ctl("start", name).stdout.strip(), "本來就在跑（running）")
        dctl = ROOT / "bin" / "aos-daemon-ctl"                       # 11-03：paused＝表上 running、子 loop 的 state.json 是 paused
        self.assertEqual(self.run_([dctl, "pause", name]).returncode, 0)
        self.assertTrue(self.until(lambda: self.ls()[0]["state"] == "paused"), self.ls())
        self.assertEqual(self.daemon_rows()[name]["phase"], "running")
        self.assertIn("狀態   paused（daemon phase running）\n畫面   closed\n", self.ctl("state", name).stdout)
        self.assertEqual(self.run_([dctl, "resume", name]).returncode, 0)
        self.assertTrue(self.until(lambda: self.ls()[0]["state"] == "running"), self.ls())
        self.assertFalse((self.ds / "eca_archive").exists())

    def test_rm(self):
        """rm＝從 daemon 拿掉、小格刪掉（不封存）；之後 ls 空、state＝InstanceMissing；
        停了的也 rm 得掉；rm 後再 add 同一資料夾＝從頭來（新的小格）。舊名 remove＝CommandUnknown（11-03 不留別名）。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "第一句")
        self.assertEqual(self.code(self.ctl("remove", name)), (1, "CommandUnknown"))
        r = self.ctl("rm", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(name, self.daemon_rows())
        self.assertFalse((self.ds / "procs" / name).exists())
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.assertFalse((self.ds / "eca_archive").exists())
        self.assertEqual(self.ls(), [])
        self.assertEqual(self.daemon_rows(), {})
        self.assertEqual(self.code(self.ctl("state", cwd=w)), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ctl("rm", cwd=w)), (1, "InstanceMissing"))
        name = self.add(w)
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.assertEqual(len((self.ds / "procs" / name / "history.jsonl").read_text().splitlines()), 0) \
            if (self.ds / "procs" / name / "history.jsonl").exists() else None
        self.say_listen(w, "第二輪")
        self.assertEqual(self.ctl("stop", cwd=w).returncode, 0)
        r = self.ctl("rm", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.ds / "procs" / name).exists())
        self.assertNotIn(name, self.daemon_rows())
        self.assertFalse(os.path.lexists(w / ".stack"))

    def test_add_name_taken(self):
        """11-03 撞名＝InstanceExists、退 1、不送信（使用者「撞名的話就報錯，也就是add的時候就會檢查了」）：daemon 表上的同名都算——
        掛著的、停了的（還在表上；訊息指 start）、daemon 上別的子項；換 --name 就掛得上。名字沒給＝eca 資料夾名。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        r = self.ctl("add", "--name", name, "--ws", w, self.tpl)
        self.assertEqual(self.code(r), (1, "InstanceExists"))
        self.assertIn("--name", r.stderr)
        self.say_listen(w, "第一輪")
        sid = (self.ds / "procs" / name / "claude" / "session.txt").read_text().strip()
        self.assertEqual(self.ctl("stop", name).returncode, 0)
        r = self.ctl("add", "--name", name, "--ws", w, self.tpl)
        self.assertEqual(self.code(r), (1, "InstanceExists"))
        self.assertIn("aos-eca start %s" % name, r.stderr)
        self.assertEqual([x["state"] for x in self.ls()], ["stopped"])
        self.assertEqual(self.ctl("start", name).returncode, 0)
        self.assertTrue(self.say_listen(w, "第二輪").startswith("fake claude[%s]" % sid[:8]))
        r = self.run_([ROOT / "bin" / "aos-daemon-ctl", "add", "--name", "nap", "/bin/sleep", "--", "30"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: "nap" in self.run_([ROOT / "bin" / "aos-daemon-ctl", "ls"]).stdout))
        self.assertEqual(self.code(self.ctl("add", "--name", "nap", "--ws", w, self.tpl)), (1, "InstanceExists"))
        d = self.ws("third")                                        # 預設名字＝eca 資料夾名（self.tpl 叫 eca-claude），不是工作區名
        r = self.ctl("add", "--ws", d, self.tpl)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("eca-claude", self.daemon_rows())

    def test_add_leaves_ws_stack(self):
        """11-03 起 add 不碰工作區的 .stack：工作區已有真的 .stack/（例如直接 aos-exec 跑過）＝add 照樣成功、不說話、原樣留；rm 也不動它。"""
        self.start_daemon()
        d = self.ws("direct")
        (d / ".stack").mkdir()
        self.add(d)
        self.assertIn("說到", self.say_listen(d, "說到"))
        self.assertEqual(self.ctl("rm", "direct").returncode, 0)
        self.assertTrue((d / ".stack").is_dir() and not (d / ".stack").is_symlink())
        self.assertEqual(os.listdir(d / ".stack"), [])

    def test_failed_gone_readd(self):
        """CLI 失敗＝子 loop 停（P-20）、自己結束＝daemon 照 11-02 從表上拿掉（procs 衝突 2「照舊拿掉」）：ls 不列、state／start／stop／rm＝InstanceMissing；
        11-03 起交給 CLI 就收信（使用者「中途掛掉就是邊緣狀況，不要讓邊緣狀況影響他的原本意思」，eca 20）：那封不在 queue 了、
        history 最後一則是它的 user、沒有回答，不自動重答。修好後同名再 add（名字不在表上＝不算撞名）＝用回同一個 stack、同一段對話，
        要重答由人再 say。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "先一句")
        cell = self.ds / "procs" / name
        sid = (cell / "claude" / "session.txt").read_text().strip()
        self.broken.write_text("")
        self.say(w, "會壞的一句")
        self.assertTrue(self.until(lambda: name not in self.daemon_rows()), self.daemon_rows())
        self.assertEqual(self.ls(), [])
        for cmd in ("state", "start", "stop", "rm"):
            self.assertEqual(self.code(self.ctl(cmd, name)), (1, "InstanceMissing"), cmd)
        self.assertEqual((os.listdir(cell / "queue" / "new"), os.listdir(cell / "queue" / "cur")), ([], []))
        self.assertEqual(json.loads((cell / "history.jsonl").read_text().splitlines()[-1]), {"role": "user", "content": "會壞的一句"})
        self.broken.unlink()
        self.add(w, name)
        a = self.say_listen(w, "再說一次")
        self.assertTrue(a.startswith("fake claude[%s]" % sid[:8]) and a.rstrip().endswith(": 再說一次"), a)

    def test_ctl_stop_bypass_gone_readd(self):
        """繞過 daemon 直接寫它 ctl.json 的 {"cmd": "stop"}：子 loop 退 0、daemon 從表上拿掉＝不在了（不是 stop；procs 衝突 2）：
        ls 空、stop／rm＝InstanceMissing；同名再 add＝同一個 stack 接著用，殘留的 stop 指令不清（11-03 基準線）、答得出。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "一")
        cell = self.ds / "procs" / name
        (cell / "ctl.json").write_text(json.dumps({"cmd": "stop", "seq": 4}))
        self.assertTrue(self.until(lambda: name not in self.daemon_rows()), self.daemon_rows())
        self.assertEqual(self.ls(), [])
        self.assertEqual(self.code(self.ctl("stop", name)), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ctl("rm", cwd=w)), (1, "InstanceMissing"))
        self.add(w, name)
        self.assertEqual(json.loads((cell / "ctl.json").read_text()), {"cmd": "stop", "seq": 4})
        self.assertIn("第二輪", self.say_listen(w, "第二輪"))
        self.assertEqual(self.ls()[0]["state"], "running")

    def test_add_stack(self):
        """11-03 使用者「aos-eca add沒辦法指定stack嗎？」：add --stack S（相對的從呼叫的 cwd 算、不在就由 daemon 建）＝照傳 aos-daemon-ctl add --stack；
        add 印的、ls／state 的 stack、where 都是 S，eca.json、對話都在 S，預設小格不建；stop／start 同一個 S；rm 刪 S。
        已有的再 open 帶 --stack＝ArgumentsBad。"""
        self.start_daemon()
        w = self.ws()
        r = self.ctl("add", "--name", "s1", "--ws", w, "--stack", "mine/s1", self.tpl, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.tmp / "mine" / "s1"
        self.assertEqual(r.stdout.strip(), str(st))
        self.names[w.name] = "s1"
        self.assertTrue(self.until(lambda: self.ls()), self.daemon_rows())
        self.assertEqual((self.ls()[0]["cell"], self.where(w)), (str(st), str(st)))
        self.assertIn("stack  %s" % st, self.ctl("state", "s1").stdout)
        self.assertIn("你好", self.say_listen(w, "你好"))
        self.assertTrue((st / "eca.json").is_file() and (st / "claude" / "session.txt").is_file())
        self.assertFalse((self.ds / "procs" / "s1").exists())
        self.assertEqual(self.code(self.ctl("open", "-d", "--stack", "x", "s1")), (1, "ArgumentsBad"))
        self.assertEqual(self.ctl("stop", "s1").returncode, 0)
        self.assertEqual(self.daemon_rows()["s1"]["phase"], "stopped")
        self.assertEqual(self.ctl("start", "s1").returncode, 0)
        self.assertIn("再一句", self.say_listen(w, "再一句"))
        r = self.ctl("rm", "s1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(st.exists())
        self.assertEqual(self.daemon_rows(), {})

    def test_add_tools(self):
        """11-03 eca-tools：add 先驗 cli.json 與登記檔——tools 指的不在＝ToolsMissing、cli.json 壞＝CfgBad，都不送信（表上沒有）；
        state 印「工具箱」（沒有＝（沒有））；放了 tools.json 的 eca 答一題後，CLI 小格 claude/mcp.json 的 --stack＝where 印的、--ws＝工作區。"""
        self.start_daemon()
        w = self.ws()
        bad = self.tmp / "eca-bad"
        shutil.copytree(self.tpl, bad)
        cfg = json.loads((bad / "cli.json").read_text())
        (bad / "cli.json").write_text(json.dumps(dict(cfg, tools="nope.json")))
        r = self.ctl("add", "--name", "bad", "--ws", w, bad)
        self.assertEqual(self.code(r), (1, "ToolsMissing"))
        self.assertTrue(r.stderr.startswith("aos-eca: ToolsMissing "), r.stderr)
        (bad / "cli.json").write_text(json.dumps(dict(cfg, tools_flags="--enable-logs")))
        self.assertEqual(self.code(self.ctl("add", "--name", "bad", "--ws", w, bad)), (1, "CfgBad"))
        self.assertEqual(self.daemon_rows(), {})
        name = self.add(w)
        self.assertIn("工具箱 （沒有）", self.ctl("state", name).stdout)
        self.assertEqual(self.ctl("rm", name).returncode, 0)
        reg = self.tpl / "tools.json"
        reg.write_text(json.dumps({"tools": {"clock": {"path": str(ROOT / "lib" / "base" / "clock")}}}))
        name = self.add(w)
        self.assertIn("答一題", self.say_listen(w, "答一題"))
        st = self.where(w)
        args = json.loads((Path(st) / "claude" / "mcp.json").read_text())["mcpServers"]["aos"]["args"]
        self.assertEqual(args, ["--ws", str(w), "--stack", st, str(reg)])
        self.assertIn("工具箱 %s" % reg, self.ctl("state", name).stdout)

    def test_add_prompt(self):
        """11-04 翻案：開場白是 aos-eca-turn 的 --prompt（寫在 XXX 的 loop.json 裡）。add／open 新建先驗：指的不是檔（相對路徑從
        aos-eca-turn 的定義資料夾算：寫死的絕對路徑、或 {"$env": "AOS_CD"}＝XXX）＝PromptMissing、不送信（表上沒有）；
        cli.json 寫了 prompt 不看；指得到的照常 add。"""
        self.start_daemon()
        w = self.ws()
        bad = self.tmp / "eca-bad"
        shutil.copytree(self.tpl, bad)
        cfg = json.loads((bad / "cli.json").read_text())
        (bad / "cli.json").write_text(json.dumps(dict(cfg, prompt="nope.txt")))       # 沒認的鍵：不是 PromptMissing
        loop = json.loads((bad / "loop.json").read_text())
        for ex in ([str(TURN), "--on-empty", "idle", "--prompt", "nope.txt", str(bad)],
                   {"argv": [str(TURN), "--prompt=nope.txt", {"$env": "AOS_CD"}]}):
            (bad / "loop.json").write_text(json.dumps(dict(loop, exec=ex)))
            r = self.ctl("add", "--name", "bad", "--ws", w, bad)
            self.assertEqual(self.code(r), (1, "PromptMissing"))
            self.assertTrue(r.stderr.startswith("aos-eca: PromptMissing "), r.stderr)
            self.assertEqual(self.code(self.ctl("open", "-d", "--name", "bad", "--ws", w, bad)), (1, "PromptMissing"))
        self.assertEqual(self.daemon_rows(), {})
        (bad / "open.txt").write_text("開場白\n")
        (bad / "loop.json").write_text(json.dumps(dict(loop, exec=[str(TURN), "--on-empty", "idle", "--prompt", "open.txt", str(bad)])))
        r = self.ctl("add", "--name", "good", "--ws", w, bad)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: any(x["name"] == "good" for x in self.ls())), self.daemon_rows())

    def test_add_demo(self):
        """add 給 proto8/demo/eca-claude（11-03 起沒有預設，要明給 XXX）：掛 daemon 時 aos-daemon-ctl 把 {"$env": "AOS_CD"} 換成 eca 資料夾路徑，
        aos-eca-turn 拿得到 cli.json；say／listen 答得出、ls 的 template 是 demo/eca-claude、名字＝eca-claude。"""
        self.start_daemon()
        w = self.ws()
        r = self.ctl("add", ROOT / "demo" / "eca-claude", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: self.ls()), self.daemon_rows())
        self.assertEqual((self.ls()[0]["name"], self.ls()[0]["template"], self.ls()[0]["ws"]),
                         ("eca-claude", str(ROOT / "demo" / "eca-claude"), str(w)))
        self.names[w.name] = "eca-claude"
        a = self.say_listen(w, "預設範本")
        self.assertTrue(a.rstrip().endswith(": 預設範本"), a)

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_close(self):
        """open -d XXX：認不出、是 eca 資料夾＝先 add（--name、--ws 照 add）、開畫面（tty.sock、ls 的 screen open、Ctrl-] 只跳出）；畫面開著時 say＝打進畫面；
        已有的再 open（名字）＝本來就開著，帶 --name＝ArgumentsBad；不是名字、工作區、eca 資料夾＝InstanceMissing；
        close 後 tty.sock 那個 tmux 不在、再 say 照答（--resume）；close --idle 拿掉了（11-03）＝FlagUnknown。"""
        self.start_daemon()
        w = self.ws()
        self.assertEqual(self.code(self.ctl("open", "-d", cwd=w)), (1, "InstanceMissing"))
        r = self.ctl("open", "-d", "--name", "proj", self.tpl, cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        cell = self.ds / "procs" / "proj" / "claude"
        self.assertTrue((cell / "tty.sock").exists())
        self.assertEqual((self.ls()[0]["state"], self.ls()[0]["screen"]), ("running", "open"))
        keys = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "list-keys", "-T", "root"],
                              capture_output=True, text=True).stdout
        self.assertIn("C-]", keys)
        r = self.ctl("open", "-d", "proj")
        self.assertEqual((r.returncode, r.stdout.split("：")[0]), (0, "畫面本來就開著"), r.stderr)
        self.assertEqual(self.code(self.ctl("open", "-d", "--name", "x", "proj")), (1, "ArgumentsBad"))
        self.assertEqual(self.say_listen(w, "畫面上的一句"), "fake live: 畫面上的一句\n")
        self.assertEqual(self.code(self.ctl("close", "--idle", "60")), (1, "FlagUnknown"))
        r = self.ctl("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        alive = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "has-session"], capture_output=True).returncode == 0
        self.assertFalse(alive)
        self.assertEqual((self.ls()[0]["state"], self.ls()[0]["screen"]), ("running", "closed"))
        self.assertIn("又一句", self.say_listen(w, "又一句"))


if __name__ == "__main__":
    unittest.main()
