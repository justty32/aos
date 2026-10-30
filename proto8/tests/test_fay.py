"""test_fay - 跑 demo/agent-fay（claude／codex CLI 當工具、可接入）：用假的 claude／codex，不花額度。

驗：非互動模式續同一段對話（session.txt）、attach -d 開畫面後改從 tmux 送字、hook 把回答接進 turns.jsonl、
人用 attach 接進去打字再 Ctrl-\\ 跳出（pty 模擬）、有人接著時 agent 叫＝SessionBad、各種錯的代號、
小格的 transcripts/ symlink 與 freeze_transcripts（10-30 eca 第 3 步）。
設計：proto8/thinking/2026-10-24-cli-tools.md。需要 tmux（沒有就 skip 畫面那幾個）。"""
import json, os, pty, re, select, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
FAY = ROOT / "demo" / "agent-fay"
CLEAR = ("AOS_HUB", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")    # 後三個：CLI 自己的對話檔放哪，測試自己給
HAS_TMUX = shutil.which("tmux") is not None
SYS_PATH = "/usr/bin:/bin"          # 只留系統的：真的 claude（~/.local/bin）進不來；真的 codex（/usr/bin）被假的擋在前面

# 假 claude：-p＝印一份 JSON；沒 -p＝互動（逐行讀，每行跑 --settings 裡的 UserPromptSubmit、Stop hook）
FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, uuid
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"cli": "claude", "argv": a, "cwd": os.getcwd()}) + "\n")
def opt(name):
    return a[a.index(name) + 1] if name in a else None
sid = opt("--resume") or opt("--session-id") or str(uuid.uuid4())
if "-p" in a:
    prompt = sys.stdin.read()
    if os.environ.get("FAKE_TRANSCRIPTS"):        # 像真的 claude 一樣把對話存進自己的資料夾（測 transcripts symlink 用）
        d = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects", "fake")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, sid + ".jsonl"), "a") as f:
            f.write(json.dumps({"type": "user", "text": prompt}) + "\n")
    if "boom" in prompt:
        print(json.dumps({"is_error": True, "result": "壞了", "session_id": sid})); sys.exit(1)
    print(json.dumps({"is_error": False, "result": "fake claude[%s]: %s" % (sid[:8], prompt), "session_id": sid}))
    sys.exit(0)
hooks = json.loads(opt("--settings"))["hooks"]
def fire(event, extra):
    for h in hooks.get(event, []):
        for c in h["hooks"]:
            subprocess.run(c["command"], shell=True, input=json.dumps(dict(extra, hook_event_name=event, session_id=sid)), text=True)
sys.stdout.write("\x1b[?2004hfake claude ready (%s)\n> " % sid[:8]); sys.stdout.flush()
for line in sys.stdin:
    text = line.replace("\x1b[200~", "").replace("\x1b[201~", "").strip()
    if text == "/exit":
        break
    if not text:
        continue
    fire("UserPromptSubmit", {"prompt": text})
    reply = "fake live: " + text
    sys.stdout.write(reply + "\n> "); sys.stdout.flush()
    fire("Stop", {"last_assistant_message": reply, "stop_hook_active": False})
'''

# 假 codex：exec [resume ID] … -o 檔 -＝印 thread.started、答案寫 -o；沒 exec＝互動（每行叫 -c notify=[…]）
FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, uuid
a = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"cli": "codex", "argv": a, "cwd": os.getcwd()}) + "\n")
thread = a[a.index("resume") + 1] if "resume" in a else str(uuid.uuid4())
if a and a[0] == "exec":
    prompt = sys.stdin.read()
    if os.environ.get("FAKE_TRANSCRIPTS"):        # 像真的 codex：$CODEX_HOME/sessions/年/月/日/rollout-…-<thread>.jsonl
        d = os.path.join(os.environ["CODEX_HOME"], "sessions", "2026", "10", "30")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "rollout-2026-10-30T00-00-00-%s.jsonl" % thread), "a") as f:
            f.write(json.dumps({"type": "user", "text": prompt}) + "\n")
    print(json.dumps({"type": "thread.started", "thread_id": thread}))
    with open(a[a.index("-o") + 1], "w") as f:
        f.write("fake codex[%s]: %s" % (thread[:8], prompt))
    sys.exit(0)
notify = next(json.loads(x[len("notify="):]) for x in a if x.startswith("notify="))
sys.stdout.write("fake codex ready\n> "); sys.stdout.flush()
for line in sys.stdin:
    text = line.replace("\x1b[200~", "").replace("\x1b[201~", "").strip()
    if text == "/exit":
        break
    if text:
        reply = "fake live: " + text
        sys.stdout.write(reply + "\n> "); sys.stdout.flush()
        subprocess.run(notify + [json.dumps({"type": "agent-turn-complete", "thread-id": thread,
                                             "last-assistant-message": reply})])
'''


class Fay(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fay-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.agent = self.tmp / "agent-fay"                     # 複製一份，測試可以改 cli.json
        shutil.copytree(FAY, self.agent, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("claude", "codex"):                                 # 等回答最多 15 秒（原 600 秒），壞了快點紅
            cfg_path = self.agent / "tools" / name / "cli.json"
            cfg_path.write_text(json.dumps(dict(json.loads(cfg_path.read_text()), timeout_ms=15000)))
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, src in (("claude", FAKE_CLAUDE), ("codex", FAKE_CODEX)):
            (self.bin / name).write_text(src)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with(str(self.bin) + os.pathsep + SYS_PATH)
        e["FAKE_LOG"] = str(self.log)
        e.update(extra or {})
        return e

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def tool(self, name, args, extra=None):
        """像 act 那樣叫工具：AOS_STACK＝<stack>/<名>/、arguments 從 stdin 進。"""
        env = self.env(dict(AOS_WS=str(self.ws), AOS_STACK=str(self.stack / name) + "/", **(extra or {})))
        return subprocess.run([EXEC, "tools/" + name], input=json.dumps(args), capture_output=True, text=True,
                              env=env, cwd=self.agent, timeout=60)

    def attach(self, *args):
        return subprocess.run([str(self.agent / "attach"), "--ws", str(self.ws), *args],
                              capture_output=True, text=True, env=self.env(), timeout=60)

    def kill_tmux(self, name):
        sock = self.stack / name / "tty.sock"
        subprocess.run(["tmux", "-S", str(sock), "kill-server"], capture_output=True)

    def codes(self, stderr):
        return re.findall(r"^(?:cli_session|claude|codex): ([A-Z][A-Za-z]+) ", stderr, re.M)   # 工具叫的錯開頭是工具名（10-24 遷移進 lib/agent）

    # ------------------------------------------------------------ 非互動

    def test_agent_asks_claude_twice_same_session(self):
        """整隻 agent（假腦）：題目交給 claude 工具；第二題續同一段對話（--resume 同一個 id）。"""
        (self.ws / "new" / "q1.txt").write_text("列出檔案")
        r = subprocess.run([EXEC, "--ws", str(self.ws), str(self.agent)], capture_output=True, text=True,
                           env=self.env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        sid = (self.stack / "claude" / "session.txt").read_text().strip()
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(),
                         "FAKE ANSWER to: 列出檔案（claude said: fake claude[%s]: 列出檔案）\n" % sid[:8])
        (self.ws / "new" / "q2.txt").write_text("再一次")
        r = subprocess.run([EXEC, "--ws", str(self.ws), str(self.agent)], capture_output=True, text=True,
                           env=self.env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        first, second = self.calls()
        self.assertIn("--session-id", first["argv"])
        self.assertEqual(second["argv"][second["argv"].index("--resume") + 1], sid)
        self.assertEqual(first["cwd"], str(self.ws))                     # CLI 在工作區裡跑
        for c in (first, second):                                          # 保守旗標都有帶
            self.assertIn("--tools", c["argv"])
            self.assertIn("dontAsk", c["argv"])

    def test_codex_exec_then_resume(self):
        r = self.tool("codex", {"prompt": "第一句"})
        self.assertEqual(r.returncode, 0, r.stderr)
        thread = (self.stack / "codex" / "session.txt").read_text().strip()
        self.assertEqual(r.stdout, "fake codex[%s]: 第一句\n" % thread[:8])
        r = self.tool("codex", {"prompt": "第二句"})
        self.assertEqual(r.returncode, 0, r.stderr)
        first, second = self.calls()
        self.assertNotIn("resume", first["argv"])
        self.assertEqual(second["argv"][:3], ["exec", "resume", thread])
        self.assertIn('sandbox_mode="read-only"', second["argv"])

    def test_errors(self):
        r = self.tool("claude", {"text": "沒有 prompt"})
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["ArgumentsBad"]))   # 10-24 遷移前叫 PromptBad
        self.assertEqual(r.stdout.strip(), r.stderr.strip())                            # lib 契約：stdout 也有同一行
        self.assertTrue(r.stderr.startswith("claude: ArgumentsBad "), r.stderr)
        r = self.tool("claude", {"prompt": "boom"})
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["CliFailed"]))
        self.assertFalse((self.stack / "claude" / "session.txt").exists())   # 失敗不記 id，下次重開
        if not shutil.which("claude", path=SYS_PATH):                     # 系統裡也沒有 claude 才測得到「找不到」
            (self.bin / "claude").unlink()
            r = self.tool("claude", {"prompt": "hi"})
            self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["CliMissing"]))
        (self.agent / "tools" / "codex" / "cli.json").write_text('{"kind": "gemini"}')
        r = self.tool("codex", {"prompt": "hi"})
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["CfgBad"]))
        r = self.attach("nope")
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["ToolUnknown"]))

    # ------------------------------------------------------------ CLI 自己的對話檔（transcripts/，10-30）

    def transcript_env(self):
        return dict(FAKE_TRANSCRIPTS="1", CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"),
                    CODEX_HOME=str(self.tmp / "codex-home"))

    def cli_session(self):
        """在測試程序裡 import lib 的 cli_session（freeze_transcripts 是給 aos-eca-hub 叫的函式，沒有命令列）。"""
        sys.path.insert(0, str(ROOT / "lib" / "agent"))
        self.addCleanup(sys.path.remove, str(ROOT / "lib" / "agent"))
        import cli_session
        return cli_session

    def test_transcripts_link_then_freeze(self):
        """工具形叫一次＝小格有 transcripts/<kind>-<id>.jsonl symlink 指到 CLI 自己的檔；freeze 後是真檔、內容一樣；
        再叫一次 symlink 不重建（已有就不動）。claude、codex 各一次。"""
        cs = self.cli_session()
        for kind in ("claude", "codex"):
            r = self.tool(kind, {"prompt": "第一句"}, self.transcript_env())
            self.assertEqual(r.returncode, 0, r.stderr)
            cell = self.stack / kind
            sid = (cell / "session.txt").read_text().strip()
            link = cell / "transcripts" / ("%s-%s.jsonl" % (kind, sid))
            self.assertTrue(link.is_symlink(), sorted(os.listdir(cell)))
            target = Path(os.readlink(link))
            home = self.tmp / ("claude-home" if kind == "claude" else "codex-home")
            self.assertTrue(target.is_absolute() and home in target.parents, target)
            self.assertTrue(target.name.endswith(sid + ".jsonl"))
            self.assertEqual(sorted(os.listdir(cell / "transcripts")), [link.name])   # 沒有殘留的暫存檔
            r = self.tool(kind, {"prompt": "第二句"}, self.transcript_env())
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(os.readlink(link)), target)
            self.assertEqual(len(link.read_text().splitlines()), 2)           # 指到的是 CLI 正在接的那份
            copied = cs.freeze_transcripts(cs.Cell(cell), kind)
            self.assertEqual(copied, [str(target)])
            self.assertFalse(link.is_symlink())
            self.assertEqual(link.read_text(), target.read_text())
            self.assertEqual(cs.freeze_transcripts(cs.Cell(cell), kind), [])  # 已經是真檔：不再拷

    def test_transcripts_freeze_target_gone(self):
        """CLI 自己把對話檔清掉了：freeze 不報錯、不拷，symlink 留著（看得出原本指哪）；沒有 transcripts/ 的格也不報錯。"""
        cs = self.cli_session()
        r = self.tool("claude", {"prompt": "講完就清"}, self.transcript_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        cell = self.stack / "claude"
        sid = (cell / "session.txt").read_text().strip()
        link = cell / "transcripts" / ("claude-%s.jsonl" % sid)
        os.remove(os.readlink(link))
        self.assertEqual(cs.freeze_transcripts(cs.Cell(cell), "claude"), [])
        self.assertTrue(link.is_symlink() and not link.exists())
        empty = self.tmp / "empty-cell"
        self.assertEqual(cs.freeze_transcripts(cs.Cell(empty), "claude"), [])  # 還沒有對話的格
        self.assertFalse((empty / "transcripts").exists())

    def test_no_transcript_no_link(self):
        """CLI 沒存對話檔（找不到）：照答、不建 symlink，也不建空的 transcripts/。"""
        r = self.tool("claude", {"prompt": "不存檔"}, dict(CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.stack / "claude" / "transcripts").exists())

    # ------------------------------------------------------------ 畫面（tmux）

    def wait_for(self, cond, secs=10):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.1)
        return False

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_live_claude_after_print(self):
        """先非互動講一句（有了 session id）→ attach -d 開畫面（--resume 同一個 id）→ 工具改從畫面送字、回答從 hook 拿。"""
        self.addCleanup(self.kill_tmux, "claude")
        self.assertEqual(self.tool("claude", {"prompt": "先講一句"}).returncode, 0)
        sid = (self.stack / "claude" / "session.txt").read_text().strip()
        r = self.attach("-d", "claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("開好了", r.stdout)
        tui = self.calls()[-1]["argv"]
        self.assertEqual(tui[tui.index("--resume") + 1], sid)
        self.assertNotIn("-p", tui)
        r = self.tool("claude", {"prompt": "畫面上的一句"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "fake live: 畫面上的一句\n")
        turns = [json.loads(l) for l in (self.stack / "claude" / "turns.jsonl").read_text().splitlines()]
        self.assertEqual([t["text"] for t in turns], ["fake live: 畫面上的一句"])
        self.assertEqual(set(turns[0]), {"answered_at", "text"})          # 講完的時間（10-25 前叫 at）
        self.assertFalse((self.stack / "claude" / "busy.txt").exists())
        self.assertEqual(len(self.calls()), 2)                             # 第二句沒有再起一次 claude
        self.assertIn("本來就開著", self.attach("-d", "claude").stdout)

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_live_codex_new_session_from_notify(self):
        """codex 沒講過話就開畫面：thread id 由 notify 補進 session.txt；關掉畫面後改走 exec resume 同一個 id。"""
        self.addCleanup(self.kill_tmux, "codex")
        self.assertEqual(self.attach("-d", "codex").returncode, 0)
        r = self.tool("codex", {"prompt": "你好"})
        self.assertEqual((r.returncode, r.stdout), (0, "fake live: 你好\n"), r.stderr)
        thread = (self.stack / "codex" / "session.txt").read_text().strip()
        self.assertTrue(thread)
        self.kill_tmux("codex")
        r = self.tool("codex", {"prompt": "畫面關了"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls()[-1]["argv"][:3], ["exec", "resume", thread])

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_human_attach_type_detach(self):
        """人：attach claude（pty 模擬終端）→ 打一句 → Ctrl-\\ 跳出；接著的時候 agent 叫＝SessionBad；跳出後畫面還活著、agent 照用。"""
        self.addCleanup(self.kill_tmux, "claude")
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(str(self.agent / "attach"), [str(self.agent / "attach"), "--ws", str(self.ws), "claude"],
                      self.env(dict(TERM="xterm")))
        screen = b""

        def read_until(pat, secs=10):
            nonlocal screen
            end = time.time() + secs
            while time.time() < end:
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        screen += os.read(fd, 4096)
                    except OSError:
                        break
                if pat in screen:
                    return True
            return False

        self.assertTrue(read_until(b"fake claude ready"), screen[-500:])
        os.write(fd, "人打的一句\r".encode())
        self.assertTrue(read_until("fake live: 人打的一句".encode()), screen[-500:])
        r = self.tool("claude", {"prompt": "agent 插話"})                   # 人還接著
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["SessionBad"]))
        os.write(fd, b"\x1c")                                             # Ctrl-\ 跳出
        _, status = os.waitpid(pid, 0)
        os.close(fd)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        self.assertTrue(self.wait_for(lambda: "畫面開著" in self.attach().stdout and
                                      "有人接著" not in self.attach().stdout))
        r = self.tool("claude", {"prompt": "跳出後"})
        self.assertEqual((r.returncode, r.stdout), (0, "fake live: 跳出後\n"), r.stderr)
        texts = [json.loads(l)["text"] for l in (self.stack / "claude" / "turns.jsonl").read_text().splitlines()]
        self.assertEqual(texts, ["fake live: 人打的一句", "fake live: 跳出後"])

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_live_no_reply_times_out(self):
        """畫面開著但 hook 不回（CLI 卡住）：等到 timeout_ms＝ReplyMissing；畫面關掉＝CliFailed。"""
        self.addCleanup(self.kill_tmux, "claude")
        cfg = json.loads((self.agent / "tools" / "claude" / "cli.json").read_text())
        (self.agent / "tools" / "claude" / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=1500)))
        (self.bin / "claude").write_text("#!/bin/sh\necho stuck; cat > /dev/null\n")
        self.assertEqual(self.attach("-d", "claude").returncode, 0)
        r = self.tool("claude", {"prompt": "沒人回"})
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["ReplyMissing"]))
        (self.stack / "claude" / "busy.txt").write_text("x\n")
        r = self.tool("claude", {"prompt": "正在跑"})
        self.assertEqual((r.returncode, self.codes(r.stderr)), (1, ["SessionBad"]))


if __name__ == "__main__":
    unittest.main()
