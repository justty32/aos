"""test_eca_ctl - proto8/extras/eca_ctl（10-30 eca 第 6 步，取代 10-28 的 test_hub）：aos-eca-ctl 把外部 coding agent 掛到
信箱模式的 aos-daemon 底下（aos-daemon-ctl add --ws），三對指令 open／close、start／stop、add／remove（使用者 11-02 晚）與 ls／state，
以及 aos-say／aos-listen 經工作區的 .stack 捷徑對它說話。

定義在測試裡臨時組（cli.json＋loop.json 叫 bin/aos-eca-turn --on-empty idle＋_entry 轉 aos-loop），用 --template 指；CLI 用 test_fay 的假 claude
（外面包一層：有 BROKEN 這個檔就退 1，測「出錯停了」），不花額度。要 tmux 的只有 open -d 那案（沒有就 skip）。
設計：proto8/thinking/2026-10-30-eca.md C 結論 7～10。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
CTL = ROOT / "extras" / "eca_ctl" / "bin" / "aos-eca-ctl"
HUMAN = ROOT / "extras" / "human" / "bin"
TURN = ROOT / "bin" / "aos-eca-turn"
DAEMON = tool("aos-daemon")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "AOS_DAEMON_STACK", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")
WRAP = '#!/bin/sh\nif [ -e "$BROKEN" ]; then echo \'{"is_error": true, "result": "壞了"}\'; exit 1; fi\nexec "$(dirname "$0")/claude-real" "$@"\n'


class EcaCtl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-ctl-"))
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
                                                          "loops_ctl_mailbox": "loops_ctl_mailbox"}))
        self.daemon = subprocess.Popen([DAEMON, str(self.tmp / "daemon.json")], cwd=str(self.tmp), env=self.env({"AOS_STACK": str(self.ds)}),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.until(lambda: (self.ds / "loops_ctl_mailbox" / "new").is_dir() and (self.ds / "loops_state.json").is_file()))

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
        return json.loads(r.stdout)["loops"]

    def ws(self, name="proj"):
        w = self.tmp / name
        w.mkdir()
        self.socks.append(self.ds / "loops" / name / "claude" / "tty.sock")
        return w

    def add(self, w, *more):
        r = self.ctl("add", "--template", self.tpl, *more, w)
        self.assertEqual(r.returncode, 0, r.stderr)
        name = more[more.index("--name") + 1] if "--name" in more else w.name
        self.assertTrue(self.until(lambda: any(x["name"] == name for x in self.ls())), self.daemon_rows())
        return name

    def say(self, w, text):
        r = self.run_([HUMAN / "aos-say", text], cwd=w)                 # cd 到工作區、不給 --ws：經 .stack 捷徑
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, w):
        r = self.run_([HUMAN / "aos-listen", "--timeout", "20"], cwd=w)   # 不帶信號＝等最新那封（11-01 晚翻案）
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def say_listen(self, w, text):
        """aos-say 話 && aos-listen。"""
        self.say(w, text)
        return self.listen(w)

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def test_daemon_missing(self):
        """AOS_DAEMON_STACK 沒設＝DaemonMissing；資料夾在、daemon 沒在跑（沒有 loops_state、或它的 pid＋started_at_ticks 對不上；11-02 起沒有心跳）＝同。
        11-02 改名：只設舊的 AOS_DAEMON＝DaemonMissing、訊息提示 AOS_DAEMON_STACK；給舊旗標 --daemon＝FlagUnknown。"""
        self.assertEqual(self.code(self.ctl("ls", env=self.env(daemon=False))), (1, "DaemonMissing"))
        r = self.ctl("ls", env=self.env({"AOS_DAEMON": str(self.ds)}, daemon=False))
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertIn("AOS_DAEMON_STACK", r.stderr)
        self.assertEqual(self.code(self.ctl("--daemon", str(self.ds), "ls")), (1, "FlagUnknown"))
        self.assertEqual(self.code(self.ctl("ls")), (1, "DaemonMissing"))
        (self.ds / "loops_state.json").write_text(json.dumps({"loops": {}, "pid": 999999999,
                                                              "started_at_ticks": 1}))
        r = self.ctl("add", "--template", self.tpl, self.ws())
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertTrue(r.stderr.startswith("aos-eca-ctl: DaemonMissing "), r.stderr)
        self.assertEqual(self.code(self.ctl("frob")), (1, "CommandUnknown"))

    def test_add_ls_state_say_listen(self):
        """add 後 daemon 表上有它、也有 eca_reap（只掛一次）、工作區多一個 .stack 捷徑指到小格；ls 列得到、state 認得（資料夾或名字）；
        cd 到工作區 say／listen 經 daemon 底下的實例答得出（假 claude，第二句 --resume 同一段）；定義不對＝TemplateUnknown。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.assertIn(name, self.daemon_rows())
        self.assertTrue(self.until(lambda: "eca_reap" in self.daemon_rows()), self.daemon_rows())   # 11-02 晚：add 順手掛上自動收畫面
        self.add(self.ws("second"))
        self.assertEqual(sorted(self.daemon_rows()), ["eca_reap", name, "second"])                 # 已掛著就不再掛
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / "loops" / name))
        it = next(x for x in self.ls() if x["name"] == name)
        self.assertEqual((it["name"], it["kind"], it["ws"], it["state"], it["phase"]), (name, "claude", str(w), "收起了", "running"))
        for arg in ((), ("proj",)):
            r = self.ctl("state", *arg, cwd=w)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("工作區 %s" % w, r.stdout)
            self.assertEqual(self.ctl("status", *arg, cwd=w).stdout, r.stdout)    # 11-03：status＝state 的別名
        self.assertEqual(self.code(self.ctl("state", cwd=self.tmp)), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ctl("status", cwd=self.tmp)), (1, "InstanceMissing"))
        a1 = self.say_listen(w, "你好")
        self.assertTrue(a1.startswith("fake claude[") and a1.rstrip().endswith(": 你好"), a1)
        sid = (self.ds / "loops" / name / "claude" / "session.txt").read_text().strip()
        self.assertTrue(self.say_listen(w, "再一句").startswith("fake claude[%s]" % sid[:8]))
        r = self.ctl("ls")
        self.assertIn("對話 %s" % sid[:8], r.stdout)
        self.assertEqual(self.code(self.ctl("add", "--template", self.tmp, self.ws("other"))), (1, "TemplateUnknown"))

    def test_close_stop_start(self):
        """close（畫面沒開）＝本來就沒畫面、再 say 照答；stop＝daemon 表上沒它、小格與 .stack 捷徑原樣留、ls「停了」，
        這期間 say 的信排在 queue、沒人答；start＝同名掛回、接著答那封（同一段對話）。已掛著再 start、已停再 stop＝說一句、退 0。
        沒有 eca_archive（11-02 晚：不封存）。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "第一句")
        r = self.ctl("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "本來就沒畫面（已收起）"), r.stderr)
        self.assertIn("第二句", self.say_listen(w, "第二句"))
        cell = self.ds / "loops" / name
        sid = (cell / "claude" / "session.txt").read_text().strip()
        r = self.ctl("stop", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("小格留著", r.stdout)
        self.assertNotIn(name, self.daemon_rows())
        self.assertEqual(os.readlink(w / ".stack"), str(cell))
        self.assertEqual([x["state"] for x in self.ls()], ["停了"])
        self.assertEqual(self.ctl("stop", name).stdout.strip(), "本來就沒掛在 daemon 上（停了）")
        sig = self.say(w, "停著時的一句")
        time.sleep(0.5)                                              # 子 loop 在的話 100 ms 就會認領
        self.assertEqual(os.listdir(cell / "queue" / "new"), [sig])
        self.assertEqual(len((cell / "history.jsonl").read_text().splitlines()), 4)
        r = self.ctl("start", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("掛回 daemon 了（上次停了），queue 裡 1 封", r.stdout)
        a = self.listen(w)
        self.assertTrue(a.startswith("fake claude[%s]" % sid[:8]) and "停著時的一句" in a, a)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertEqual(self.ctl("start", name).stdout.strip(), "本來就掛著（收起了）")
        self.assertFalse((self.ds / "eca_archive").exists())

    def test_remove(self):
        """remove＝從 daemon 拿掉、.stack 捷徑拆掉、小格刪掉（不封存）；之後 ls 空、state＝InstanceMissing；
        停了的也 remove 得掉；remove 後再 add 同一資料夾＝從頭來（新的小格、捷徑又建得起來）。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "第一句")
        r = self.ctl("remove", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(name, self.daemon_rows())
        self.assertFalse((self.ds / "loops" / name).exists())
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.assertFalse((self.ds / "eca_archive").exists())
        self.assertEqual(self.ls(), [])
        self.assertIn("eca_reap", self.daemon_rows())                # 最後一隻 remove 了 eca_reap 照樣留（代定）
        self.assertEqual(self.code(self.ctl("state", cwd=w)), (1, "InstanceMissing"))
        self.assertEqual(self.code(self.ctl("remove", cwd=w)), (1, "InstanceMissing"))
        name = self.add(w)
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / "loops" / name))
        self.assertEqual(len((self.ds / "loops" / name / "history.jsonl").read_text().splitlines()), 0) \
            if (self.ds / "loops" / name / "history.jsonl").exists() else None
        self.say_listen(w, "第二輪")
        self.assertEqual(self.ctl("stop", cwd=w).returncode, 0)
        r = self.ctl("remove", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.ds / "loops" / name).exists())
        self.assertFalse(os.path.lexists(w / ".stack"))

    def test_add_again(self):
        """停了的同名再 add＝daemon 用回小格（前文、queue 照舊）、stderr 一句「小格還在…要從頭來先 remove」、捷徑已指著小格不警告。
        工作區已有真的 .stack/（例如直接 aos-exec 跑過）＝add 照樣成功、stderr 一句「工作區已有 .stack…請先搬開」、不建捷徑。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.say_listen(w, "第一輪")
        sid = (self.ds / "loops" / name / "claude" / "session.txt").read_text().strip()
        self.assertEqual(self.ctl("stop", name).returncode, 0)
        r = self.ctl("add", "--template", self.tpl, w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("小格還在（停了）", r.stderr)
        self.assertNotIn("工作區已有 .stack", r.stderr)
        self.assertTrue(self.until(lambda: [x["state"] for x in self.ls()] == ["收起了"]), self.ls())
        self.assertTrue(self.say_listen(w, "第二輪").startswith("fake claude[%s]" % sid[:8]))
        d = self.ws("direct")
        (d / ".stack").mkdir()
        r = self.ctl("add", "--template", self.tpl, d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("工作區已有 .stack", r.stderr)
        self.assertIn("請先搬開", r.stderr)
        self.assertTrue((d / ".stack").is_dir() and not (d / ".stack").is_symlink())

    def test_failed_start_readds(self):
        """CLI 失敗＝子 loop 停（P-20）、ls 標「出錯停了」、信留 cur/；close 只管畫面（說一句要用 start）；
        修好後 start＝掛回去，接著答那封。11-02 起停了的子項不在 daemon 的表上：ctl 看小格的 state.json（done＋結束碼非 0）認它。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.broken.write_text("")
        sig = self.say(w, "會壞的一句")
        self.assertTrue(self.until(lambda: self.ls()[0]["state"] == "出錯停了"), self.ls())
        self.assertNotIn(name, self.daemon_rows())
        self.assertEqual(os.listdir(self.ds / "loops" / name / "queue" / "cur"), [sig])
        self.broken.unlink()
        r = self.ctl("close", name)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "本來就沒畫面（已收起）"), r.stderr)
        self.assertIn("aos-eca-ctl start", r.stderr)
        self.assertNotIn(name, self.daemon_rows())
        r = self.ctl("start", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("上次出錯停了", r.stdout)
        self.assertIn("會壞的一句", self.listen(w))
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / "loops" / name))

    def stopped_by_ctl(self, w, name, ctl=None):
        """外部寫小格 ctl.json 的 stopped 收工：子 loop 以 0 結束、daemon 表上不留它；ctl 列「收工了」。"""
        self.say_listen(w, "一")
        (self.ds / "loops" / name / "ctl.json").write_text(json.dumps(ctl or {"stopped": True}))
        self.assertTrue(self.until(lambda: [x["state"] for x in self.ls()] == ["收工了"]), (self.ls(), self.daemon_rows()))
        self.assertNotIn(name, self.daemon_rows())

    def test_finished_listed_and_remove(self):
        """11-02 晚：ctl.json stopped 收工的（下了表、退 0）ls／state 照列「收工了」；stop＝本來就沒掛；remove 拆 .stack 捷徑、刪小格。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.stopped_by_ctl(w, name)
        r = self.ctl("state", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("收工了", r.stdout)
        self.assertEqual(self.ctl("stop", name).stdout.strip(), "本來就沒掛在 daemon 上（收工了）")
        r = self.ctl("remove", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.assertFalse((self.ds / "loops" / name).exists())
        self.assertEqual(self.ls(), [])

    def test_finished_add_again_clears_stopped(self):
        """收工了的再 add 同一資料夾：殘留的 stopped 拿掉（其他 key 照留）、.stack 已指著這個小格＝不警告，子 loop 重新收、答得出。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.stopped_by_ctl(w, name, {"stopped": True, "paused": False})
        r = self.ctl("add", "--template", self.tpl, w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("小格還在（收工了）", r.stderr)
        self.assertNotIn("工作區已有 .stack", r.stderr)
        self.assertEqual(json.loads((self.ds / "loops" / name / "ctl.json").read_text()), {"paused": False})
        self.assertTrue(self.until(lambda: [x["state"] for x in self.ls()] == ["收起了"]), self.ls())
        self.assertIn("第二輪", self.say_listen(w, "第二輪"))

    def test_finished_start_readds(self):
        """收工了的 start＝跟出錯停了一樣掛回；ctl.json 只有 stopped＝整個檔拿掉。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.stopped_by_ctl(w, name)
        r = self.ctl("start", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("掛回 daemon 了（上次收工了）", r.stdout)
        self.assertFalse((self.ds / "loops" / name / "ctl.json").exists())
        self.assertIn("再來", self.say_listen(w, "再來"))
        self.assertEqual(self.ls()[0]["state"], "收起了")

    def test_default_template(self):
        """不給 --template＝proto8/demo/eca-claude（方向題 3）：掛 daemon 時 aos-daemon-ctl 把 {"$env": "AOS_CD"} 換成定義路徑，
        aos-eca-turn 拿得到 cli.json；say／listen 答得出、ls 的 template 是 demo/eca-claude。"""
        self.start_daemon()
        w = self.ws()
        r = self.ctl("add", w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: self.ls()), (self.ds / "loops" / "proj" / "stderr.txt").read_text()
                        if (self.ds / "loops" / "proj" / "stderr.txt").exists() else self.daemon_rows())
        self.assertEqual(self.ls()[0]["template"], str(ROOT / "demo" / "eca-claude"))
        a = self.say_listen(w, "預設範本")
        self.assertTrue(a.rstrip().endswith(": 預設範本"), a)

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_close(self):
        """open -d：還沒掛就先 add、開畫面（tty.sock、ls 畫面開著、Ctrl-] 只跳出）；畫面開著時 say＝打進畫面；
        close 後 tty.sock 那個 tmux 不在、再 say 照答（--resume）；close --idle 60 不收還沒閒的。"""
        self.start_daemon()
        w = self.ws()
        r = self.ctl("open", "-d", "--template", self.tpl, cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        cell = self.ds / "loops" / "proj" / "claude"
        self.assertTrue((cell / "tty.sock").exists())
        self.assertEqual(self.ls()[0]["state"], "畫面開著")
        keys = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "list-keys", "-T", "root"],
                              capture_output=True, text=True).stdout
        self.assertIn("C-]", keys)
        self.assertEqual(self.say_listen(w, "畫面上的一句"), "fake live: 畫面上的一句\n")
        r = self.ctl("close", "--idle", "60")
        self.assertEqual((r.returncode, r.stdout, self.ls()[0]["state"]), (0, "", "畫面開著"), r.stderr)
        r = self.ctl("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        alive = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "has-session"], capture_output=True).returncode == 0
        self.assertFalse(alive)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn("又一句", self.say_listen(w, "又一句"))


if __name__ == "__main__":
    unittest.main()
