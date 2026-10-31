"""test_eca_hub - proto8/extras/eca_hub（10-30 eca 第 6 步，取代 10-28 的 test_hub）：aos-eca-hub 把外部 coding agent 掛到
信箱模式的 aos-daemon 底下（aos-daemon-ctl add --ws），add／ls／state／open／close／stop，以及 aos-say／aos-listen 經工作區的
.stack 捷徑對它說話。

定義在測試裡臨時組（cli.json＋loop.json 叫 bin/aos-eca-turn --on-empty idle＋_entry 轉 aos-loop），用 --template 指；CLI 用 test_fay 的假 claude
（外面包一層：有 BROKEN 這個檔就退 1，測「出錯停了」），不花額度。要 tmux 的只有 open -d 那案（沒有就 skip）。
設計：proto8/thinking/2026-10-30-eca.md C 結論 7～10。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
HUB = ROOT / "extras" / "eca_hub" / "bin" / "aos-eca-hub"
HUMAN = ROOT / "extras" / "human" / "bin"
TURN = ROOT / "bin" / "aos-eca-turn"
DAEMON = tool("aos-daemon")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")
WRAP = '#!/bin/sh\nif [ -e "$BROKEN" ]; then echo \'{"is_error": true, "result": "壞了"}\'; exit 1; fi\nexec "$(dirname "$0")/claude-real" "$@"\n'


class EcaHub(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-hub-"))
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
        self.ds = self.tmp / "dstack"                                # daemon 的 $AOS_STACK＝AOS_DAEMON
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
            e["AOS_DAEMON"] = str(self.ds)
        e.update(extra or {})
        return e

    def start_daemon(self):
        (self.tmp / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                          "loops_mailbox": "loops_mailbox"}))
        self.daemon = subprocess.Popen([DAEMON, str(self.tmp / "daemon.json")], cwd=str(self.tmp), env=self.env({"AOS_STACK": str(self.ds)}),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.until(lambda: (self.ds / "loops_mailbox" / "new").is_dir() and (self.ds / "loops_state.json").is_file()))

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

    def hub(self, *args, cwd=None, env=None):
        return self.run_([HUB, *args], cwd=cwd, env=env)

    def ls(self):
        r = self.hub("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def daemon_rows(self):
        r = self.run_([ROOT / "bin" / "aos-daemon-ctl", "ls", "--json"])
        return json.loads(r.stdout)["loops"]

    def ws(self, name="proj"):
        w = self.tmp / name
        w.mkdir()
        self.socks.append(self.ds / name / "claude" / "tty.sock")
        return w

    def add(self, w, *more):
        r = self.hub("add", "--template", self.tpl, *more, w)
        self.assertEqual(r.returncode, 0, r.stderr)
        name = more[more.index("--name") + 1] if "--name" in more else w.name
        self.assertTrue(self.until(lambda: any(x["name"] == name for x in self.ls())), self.daemon_rows())
        return name

    def say(self, w, text):
        r = self.run_([HUMAN / "aos-say", text], cwd=w)                 # cd 到工作區、不給 --ws：經 .stack 捷徑
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, w, sig):
        r = self.run_([HUMAN / "aos-listen", "--timeout", "20", sig], cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def test_daemon_missing(self):
        """AOS_DAEMON 沒設＝DaemonMissing；資料夾在、daemon 沒在跑（沒有 loops_state、或心跳的行程不在）＝同。"""
        self.assertEqual(self.code(self.hub("ls", env=self.env(daemon=False))), (1, "DaemonMissing"))
        self.assertEqual(self.code(self.hub("ls")), (1, "DaemonMissing"))
        (self.ds / "loops_state.json").write_text(json.dumps({"kind": "state", "loops": {}, "pid": 999999999,
                                                              "started_at_ticks": 1}))
        r = self.hub("add", "--template", self.tpl, self.ws())
        self.assertEqual(self.code(r), (1, "DaemonMissing"))
        self.assertTrue(r.stderr.startswith("aos-eca-hub: DaemonMissing "), r.stderr)
        self.assertEqual(self.code(self.hub("frob")), (1, "CommandUnknown"))

    def test_add_ls_state_say_listen(self):
        """add 後 daemon 表上有它、工作區多一個 .stack 捷徑指到小格；ls 列得到、state 認得（資料夾或名字）；
        cd 到工作區 say／listen 經 daemon 底下的實例答得出（假 claude，第二句 --resume 同一段）；定義不對＝TemplateUnknown。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.assertIn(name, self.daemon_rows())
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / name))
        it = self.ls()[0]
        self.assertEqual((it["name"], it["kind"], it["ws"], it["state"], it["phase"]), (name, "claude", str(w), "收起了", "running"))
        for arg in ((), ("proj",)):
            r = self.hub("state", *arg, cwd=w)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("工作區 %s" % w, r.stdout)
        self.assertEqual(self.code(self.hub("state", cwd=self.tmp)), (1, "InstanceMissing"))
        a1 = self.listen(w, self.say(w, "你好"))
        self.assertTrue(a1.startswith("fake claude[") and a1.rstrip().endswith(": 你好"), a1)
        sid = (self.ds / name / "claude" / "session.txt").read_text().strip()
        self.assertTrue(self.listen(w, self.say(w, "再一句")).startswith("fake claude[%s]" % sid[:8]))
        r = self.hub("ls")
        self.assertIn("對話 %s" % sid[:8], r.stdout)
        self.assertEqual(self.code(self.hub("add", "--template", self.tmp, self.ws("other"))), (1, "TemplateUnknown"))

    def test_close_and_stop_archive(self):
        """close（畫面沒開）＝本來就沒畫面、再 say 照答；stop 後 daemon 表上沒它、.stack 捷徑拿掉、
        小格搬到 <daemon>/eca_archive/<名字>-<UTC>/（10-30 使用者「A」），transcripts/ 是真檔、工作區不留真的 .stack/；
        之後 state＝InstanceMissing。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.listen(w, self.say(w, "第一句"))
        r = self.hub("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "本來就沒畫面（已收起）"), r.stderr)
        self.assertIn("第二句", self.listen(w, self.say(w, "第二句")))
        sid = (self.ds / name / "claude" / "session.txt").read_text().strip()
        r = self.hub("stop", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(name, self.daemon_rows())
        self.assertFalse((self.ds / name).exists())
        self.assertFalse(os.path.lexists(w / ".stack"))
        arch = list((self.ds / "eca_archive").iterdir())
        self.assertEqual(len(arch), 1)
        self.assertTrue(arch[0].name.startswith(name + "-"), arch)
        self.assertEqual((arch[0] / "claude" / "session.txt").read_text().strip(), sid)
        t = arch[0] / "claude" / "transcripts" / ("claude-%s.jsonl" % sid)
        self.assertTrue(t.is_file() and not t.is_symlink(), list((arch[0] / "claude").iterdir()))
        self.assertEqual(len((arch[0] / "history.jsonl").read_text().splitlines()), 4)
        self.assertEqual(self.ls(), [])
        self.assertEqual(self.code(self.hub("state", cwd=w)), (1, "InstanceMissing"))

    def test_stop_then_add_again(self):
        """stop 後再 add 同一工作區：.stack 又是捷徑指到新小格、say／listen 答得出；歸檔留在 daemon 那邊不受影響。
        工作區已有真的 .stack/（例如直接 aos-exec 跑過）＝add 照樣成功、stderr 一句「工作區已有 .stack…請先搬開」、不建捷徑。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.listen(w, self.say(w, "第一輪"))
        r = self.hub("stop", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.lexists(w / ".stack"))
        name = self.add(w)
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / name))
        self.assertIn("第二輪", self.listen(w, self.say(w, "第二輪")))
        self.assertEqual(len(list((self.ds / "eca_archive").iterdir())), 1)
        d = self.ws("direct")
        (d / ".stack").mkdir()
        r = self.hub("add", "--template", self.tpl, d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("工作區已有 .stack", r.stderr)
        self.assertIn("請先搬開", r.stderr)
        self.assertTrue((d / ".stack").is_dir() and not (d / ".stack").is_symlink())

    def test_failed_close_readds(self):
        """CLI 失敗＝子 loop 停（P-20）、ls 標「出錯停了」、信留 cur/；修好後 close 一次＝拿掉再掛回去，接著答那封。"""
        self.start_daemon()
        w = self.ws()
        name = self.add(w)
        self.broken.write_text("")
        sig = self.say(w, "會壞的一句")
        self.assertTrue(self.until(lambda: self.ls()[0]["state"] == "出錯停了"), self.ls())
        self.assertEqual(os.listdir(self.ds / name / "queue" / "cur"), [sig])
        self.broken.unlink()
        r = self.hub("close", name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("重新掛上", r.stdout)
        self.assertIn("會壞的一句", self.listen(w, sig))
        self.assertEqual(os.readlink(w / ".stack"), str(self.ds / name))

    def test_default_template(self):
        """不給 --template＝proto8/demo/eca-claude（方向題 3）：掛 daemon 時 aos-daemon-ctl 把 {"$env": "AOS_CD"} 換成定義路徑，
        aos-eca-turn 拿得到 cli.json；say／listen 答得出、ls 的 template 是 demo/eca-claude。"""
        self.start_daemon()
        w = self.ws()
        r = self.hub("add", w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: self.ls()), (self.ds / "proj" / "stderr.txt").read_text()
                        if (self.ds / "proj" / "stderr.txt").exists() else self.daemon_rows())
        self.assertEqual(self.ls()[0]["template"], str(ROOT / "demo" / "eca-claude"))
        a = self.listen(w, self.say(w, "預設範本"))
        self.assertTrue(a.rstrip().endswith(": 預設範本"), a)

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_close(self):
        """open -d：還沒掛就先 add、開畫面（tty.sock、ls 畫面開著、Ctrl-] 只跳出）；畫面開著時 say＝打進畫面；
        close 後 tty.sock 那個 tmux 不在、再 say 照答（--resume）；close --idle 60 不收還沒閒的。"""
        self.start_daemon()
        w = self.ws()
        r = self.hub("open", "-d", "--template", self.tpl, cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        cell = self.ds / "proj" / "claude"
        self.assertTrue((cell / "tty.sock").exists())
        self.assertEqual(self.ls()[0]["state"], "畫面開著")
        keys = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "list-keys", "-T", "root"],
                              capture_output=True, text=True).stdout
        self.assertIn("C-]", keys)
        self.assertEqual(self.listen(w, self.say(w, "畫面上的一句")), "fake live: 畫面上的一句\n")
        r = self.hub("close", "--idle", "60")
        self.assertEqual((r.returncode, r.stdout, self.ls()[0]["state"]), (0, "", "畫面開著"), r.stderr)
        r = self.hub("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        alive = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "has-session"], capture_output=True).returncode == 0
        self.assertFalse(alive)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn("又一句", self.listen(w, self.say(w, "又一句")))


if __name__ == "__main__":
    unittest.main()
