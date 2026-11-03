"""test_human - 給人用的 aos-say／aos-listen（aos-chat 11-03 封存到 proto8/archive/aos-chat/，案例一起搬）（proto8/extras/human，2026-10-24）：對走 queue 的 agent 問答。

10-30 起照 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle A-7、A-8、第 4 步）：say＝aos-post send --ordered
<stack>/queue、listen 只看 stack（信還在 queue 就等、不見了就印 history 最新的回答）。
11-03 拿掉 aos-listen 的 --status／--trace／LetterUnclaimed、aos-chat 的 --trace／/trace／/status（trace.jsonl 整個拿掉，thinking 2026-11-03-trace）：
原本看快照的案例改看 stack 的 state.json 與 aos_human.runners（listen 提醒「沒人在跑」用的同一個判法）。
agent＝這裡臨時組的 eca 定義（aos-loop 包 bin/aos-eca-turn、CLI 是 test_cli_tools 的假 claude，回 `fake claude[<id>]: <題目>`；
11-03 前是 demo/agent-nia，它隨 round 那套 agent 刪了，案例改用 eca）；CLI 壞＝PATH 上沒有 claude（CliMissing，信留在 cur/）。
10-30 eca 第 7 步（去 hub 化）：External 段＝外部 coding agent 常駐（--on-empty idle）時 say／listen 照用、
runners 只靠 /proc 認得服務者（直接跑、掛 daemon〔11-03 起經 where 拿 stack〕兩種）；stack 的 server.txt 那招刪了。
設計：proto8/thinking/2026-10-24-say-listen.md。不連網。"""
import json, os, re, subprocess, tempfile, time, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

HUMAN = ROOT / "extras" / "human" / "bin"
SAY, LISTEN = (str(HUMAN / n) for n in ("aos-say", "aos-listen"))
DAN = str(ROOT / "demo" / "agent-eve")              # 舊協議（讀工作區 new/、不收 queue）：10-30 晚真腦實測發現 2；11-02 晚 agent-dan 刪除，改用它的複本 agent-eve
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_DAEMON_STACK",
         "TMUX", "CODEX_HOME", "FAKE_TRANSCRIPTS")
SIG = re.compile(r"^\d{12}\.\d{20}\.\d+\.\d+$")
TURN = ROOT / "bin" / "aos-eca-turn"                # 10-30 eca：外部 coding agent 的一輪（10-31 前是 lib/eca/turn 格）
FAKE = re.compile(r"^fake claude\[\w+\]: ")          # 假 claude 的回答開頭
from test_cli_tools import FAKE_CLAUDE, SYS_PATH  # noqa: E402  假 claude（不花額度）


def env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(str(ROOT / "bin") + os.pathsep + e.get("PATH", ""))
    e.update(kw)
    return e


def run(*args, cwd=None, input=None, timeout=60, **kw):
    return subprocess.run(args, capture_output=True, text=True, env=env(**kw), cwd=cwd, input=input, timeout=timeout)


def runners(ws):
    """誰在跑這個工作區的 agent（aos_human.runners，listen 提醒「沒人在跑」用的同一套；11-03 起取代 --status 那行）：[(pid, 程式名)]。"""
    import sys
    sys.path.insert(0, str(HUMAN))
    import aos_human
    return aos_human.runners(aos_human.Where(str(ws), None))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        t = Path(self._tmp.name)
        self.ws = t / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
        self.bin = t / "fakebin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE_CLAUDE)
        (self.bin / "claude").chmod(0o755)
        self.xenv = dict(PATH=path_with(str(self.bin) + os.pathsep + str(ROOT / "bin") + os.pathsep + SYS_PATH),
                         FAKE_LOG=str(t / "cli.log"), CLAUDE_CONFIG_DIR=str(t / "claude-home"))
        self.agent = self.eca_def(t / "eca-stop")                      # 射後不理：queue 空 aos-eca-turn 退 10、loop 收工
        self.eca = self.eca_def(t / "eca-claude", idle=True)            # 常駐：queue 空隔 interval_ms 再來

    def eca_def(self, where, idle=False):
        """eca 定義：cli.json（lib/agent/claude 的）＋loop.json（叫 aos-eca-turn）＋_entry 轉 aos-loop。"""
        where.mkdir()
        cfg = json.loads((ROOT / "lib" / "agent" / "claude" / "cli.json").read_text())
        (where / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        loop = {"exec": [str(TURN), "--on-empty", "idle" if idle else "stop", str(where)], "ctl": "ctl.json", "state": "state.json"}
        loop.update({"interval_ms": 100} if idle else {"max": 40})
        (where / "loop.json").write_text(json.dumps(loop))
        (where / "_entry").write_text(json.dumps(["aos-loop", "loop.json"]))
        return where

    def say(self, *words, **kw):
        r = run(SAY, "--ws", str(self.ws), *words, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def go(self, agent=None, **kw):
        return run("aos-exec", "--ws", str(self.ws), str(agent or self.agent), **dict(self.xenv, **kw))

    def queue(self, stage):
        d = self.stack / "queue" / stage
        return sorted(os.listdir(d)) if d.is_dir() else []

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class SayTest(Base):
    def test_say_sends_one_ordered_letter(self):
        sig = self.say("現在", "幾點")
        self.assertRegex(sig, SIG)
        self.assertTrue(sig.startswith("000000000001."))
        self.assertEqual(self.queue("new"), [sig])
        letter = json.loads((self.stack / "queue" / "new" / sig / "letter.json").read_text())
        self.assertEqual(letter["body"], {"role": "user", "content": "現在 幾點"})
        self.assertEqual(sorted(os.listdir(self.ws)), [".stack"])        # 工作區不長 new/、暫存檔

    def test_stdin_cwd_and_stack_flag(self):
        r = run(SAY, cwd=str(self.ws), input="第一行\n第二行\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = json.loads((self.stack / "queue" / "new" / r.stdout.strip() / "letter.json").read_text())["body"]
        self.assertEqual(body["content"], "第一行\n第二行")              # 結尾換行去掉
        self.assertIn("目前沒有程式在跑這隻 agent", r.stderr)            # 沒人跑：提醒、不算錯
        self.assertIn("--stack $(aos-daemon-ctl where --stack 名字)", r.stderr)   # 11-03：掛在 daemon 上的怎麼指
        other = self.ws / "elsewhere"
        r = run(SAY, "--ws", str(self.ws), "--stack", str(other), "到別的 stack")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(other / "queue" / "new"), [r.stdout.strip()])
        r = run(SAY, "--ws", str(self.ws), "環境變數的 stack", AOS_STACK=str(other))
        self.assertEqual(len(os.listdir(other / "queue" / "new")), 2)

    def test_stopped_on_daemon_hint(self):
        """11-03 procs：stack 是 daemon 表上 stopped 的那一列＝提醒 aos-daemon-ctl start 名字（eca＝aos-eca start）、不說另開終端機。"""
        d = self.ws / "dstack"
        cell, other = d / "procs" / "bob", self.ws / "custom"
        def table(**rows):
            d.mkdir(exist_ok=True)
            (d / "procs_state.json").write_text(json.dumps({"procs": rows}))
        table(bob={"phase": "stopped", "pid": None, "stack": str(cell)})
        r = run(SAY, "--ws", str(self.ws), "--stack", str(cell), "x")       # 預設小格：不用 AOS_DAEMON_STACK 也認得
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bob 是 stopped", r.stderr)
        self.assertIn("aos-daemon-ctl start bob", r.stderr)
        self.assertNotIn("另開一個終端機", r.stderr)
        self.assertNotIn("where --stack", r.stderr)
        (cell / "eca.json").write_text(json.dumps({"kind": "claude"}))
        r = run(SAY, "--ws", str(self.ws), "--stack", str(cell), "x")
        self.assertIn("aos-eca start bob", r.stderr)
        table(c2={"phase": "stopped", "pid": None, "stack": str(other) + "/"})   # 別處的 stack：看 AOS_DAEMON_STACK
        r = run(SAY, "--ws", str(self.ws), "--stack", str(other), "x")
        self.assertIn("另開一個終端機", r.stderr)                            # 沒設：認不出，照舊提醒
        r = run(SAY, "--ws", str(self.ws), "--stack", str(other), "x", AOS_DAEMON_STACK=str(d))
        self.assertIn("aos-daemon-ctl start c2", r.stderr)
        table(c2={"phase": "running", "pid": 1, "stack": str(other)})           # 表上不是 stopped：照舊
        r = run(SAY, "--ws", str(self.ws), "--stack", str(other), "x", AOS_DAEMON_STACK=str(d))
        self.assertIn("另開一個終端機", r.stderr)
        self.assertIn("where --stack", r.stderr)

    def test_order(self):
        sigs = [self.say("q%d" % i) for i in range(5)]
        self.assertEqual(sigs, sorted(sigs))
        self.assertEqual([s[:12] for s in sigs], ["%012d" % i for i in range(1, 6)])

    def test_errors(self):
        r = run(SAY, "--ws", str(self.ws / "nope"), "x")
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "WsMissing"))
        r = run(SAY, "--ws", str(self.ws), input="  \n")
        self.assertRegex(r.stderr, r"^aos-say: ArgumentsBad usage: ")
        r = run(SAY, "--bogus", "x")
        self.assertRegex(r.stderr, r"^aos-say: FlagUnknown usage: ")
        r = run(SAY, "--ws", str(self.ws), "--name", "q1.txt", "x")       # --name 拿掉了（信件名稱由 aos-post 給）
        self.assertRegex(r.stderr, r"^aos-say: FlagUnknown usage: ")


class ListenTest(Base):
    def test_answer_already_there(self):
        """答案先到、再 listen：不漏（信不見了＝印 history 最新的回答）。"""
        sig = self.say("現在幾點")
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.queue("new") + self.queue("cur"), [])
        r = run(LISTEN, "--ws", str(self.ws))                    # 不帶信件名稱：new/ cur/ 空＝印最新那則回答
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, FAKE)
        self.assertTrue(r.stdout.endswith(": 現在幾點\n"), r.stdout)
        self.assertEqual(r.stdout.count("\n"), 1)

    def test_waits_while_agent_runs_later(self):
        sig = self.say("等我")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(1.5)                                       # listen 先開：這時沒人在跑，會提醒一次
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(FAKE.match(out) and out.endswith(": 等我\n"), out)
        self.assertIn("還在 queue 的 new/，但目前沒有程式在跑", err)

    def test_old_protocol_agent_waits(self):
        """say 之後拿舊協議的 agent（agent-eve；11-02 晚前是 agent-dan）跑：退 0、信原封留在 new/；listen 照等到逾時（11-03 起沒有
        LetterUnclaimed：那是靠 trace.jsonl 的時間判的）；之後換走 queue 的 agent 跑就答得出。"""
        sig = self.say("舊協議")
        self.assertEqual(self.go(DAN).returncode, 0)
        self.assertEqual(self.queue("new"), [sig])
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒")
        self.assertIn("還在 queue 的 new/，但目前沒有程式在跑", r.stderr)
        self.assertEqual(self.go().returncode, 0)                # 換走 queue 的 agent（eca）：答得出
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "5")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_handed_waits_for_answer(self):
        """11-03 外部 coding agent（aos-eca-turn）交給 CLI 就收信：queue 空、history 最後一則是 user＝還在答——listen 等新回答出來、
        不印上一則舊回答；沒有程式在跑它＝AnswerMissing（中途掛掉的那批不會自動重答）。"""
        self.stack.mkdir()
        rows = [{"role": "user", "content": "舊的"}, {"role": "assistant", "content": "舊回答"}, {"role": "user", "content": "交出去了"}]
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in rows))
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "5")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 最新那封 已經交出去了")
        self.assertEqual(r.stdout, "")
        fake = subprocess.Popen(["aos-loop", "30"], executable="/bin/sleep", env=env(AOS_STACK=str(self.stack) + "/"))   # 假裝有人在跑
        self.addCleanup(lambda: (fake.kill(), fake.wait()))
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "20"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(1.5)
        self.assertIsNone(p.poll())                                     # 還在等，沒印舊回答
        with open(self.stack / "history.jsonl", "a") as f:
            f.write(json.dumps({"role": "assistant", "content": "新回答"}, ensure_ascii=False) + "\n")
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "新回答\n"), err)

    def test_waits_while_letter_in_cur(self):
        """信在 cur/（認領了、還沒交出去：CLI 不在 PATH 上〔CliMissing〕停住）：listen 照等、說信在 cur/ 沒人在跑；修好再跑就答出。"""
        sig = self.say("壞腦")
        r = self.go(PATH=path_with(str(ROOT / "bin") + os.pathsep + SYS_PATH))     # PATH 上沒有 claude
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CliMissing", r.stderr)
        self.assertEqual(self.queue("cur"), [sig])
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("在 queue 的 cur/（認領了、還沒答完），但目前沒有程式在跑", r.stderr)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒.*（信在 queue 的 cur/）")
        self.assertFalse((self.stack / "trace.jsonl").exists())               # 11-03：不寫 trace
        self.assertEqual(json.loads((self.stack / "state.json").read_text())["phase"], "done")   # aos-loop 的 state 窗（失敗也是 done）
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(0.5)
        self.assertEqual(self.go().returncode, 0)                        # CLI 回來了：cur/ 那封照問
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(FAKE.match(out) and out.endswith(": 壞腦\n"), out)

    def test_paused_letter_waits(self):
        """常駐（idle）的 aos-loop 被 ctl 暫停：state.json 的 phase paused、runners 認得有人在跑；寄的信留在 new/。"""
        agent = self.eca
        self.stack.mkdir()
        (self.stack / "ctl.json").write_text('{"cmd": "pause"}')
        p = subprocess.Popen(["aos-exec", "--ws", str(self.ws), str(agent)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, env=env(**self.xenv))
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        end = time.time() + 20
        while time.time() < end:
            st = self.stack / "state.json"
            if st.exists() and json.loads(st.read_text() or "{}").get("phase") == "paused":
                break
            time.sleep(0.05)
        sig = self.say("暫停中")
        self.assertIn("aos-loop", [n for _, n in runners(self.ws)])
        self.assertEqual(self.queue("new"), [sig])
        (self.stack / "ctl.json").write_text('{"cmd": "resume"}')
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "20")
        self.assertTrue(FAKE.match(r.stdout) and r.stdout.endswith(": 暫停中\n"), r.stdout + r.stderr)
        (self.stack / "ctl.json").write_text('{"cmd": "stop"}')
        self.assertEqual(p.wait(timeout=20), 0)

    def test_unknown_and_usage(self):
        r = run(LISTEN, "--ws", str(self.ws))                           # 沒寄過、也沒回答
        self.assertRegex(r.stderr, r"^aos-listen: QuestionUnknown ")
        r = run(LISTEN, "--ws", str(self.ws), "000000000001.nope")     # 11-01 晚翻案：信件名稱參數拿掉
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: .*不收位置參數")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "2", "x")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "abc")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1", "--follow")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        for gone in ("--status", "--trace"):                            # 11-03 拿掉
            r = run(LISTEN, "--ws", str(self.ws), gone)
            self.assertRegex(r.stderr, r"^aos-listen: FlagUnknown ")

    def test_waits_for_latest_letter(self):
        """aos-say 話 && aos-listen：連寄兩封，listen 等的是最新那封；答完印最新的回答（aos-eca-turn 兩封一批、一則回答）。"""
        self.say("第一封")
        self.say("第二封")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(0.5)
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(FAKE.match(out) and out.endswith(": 第一封\n\n第二封\n"), out)

    def test_latest_is_last_in_processing_order(self):
        """11-03 aos-post 改版：有序、無序同箱，處理順序＝有序先（照名字）、無序後（照名字）；「最新那封」＝處理順序最後那封
        （aos_ws.letter_key 取 max）——無序那封的名字照字面比還比有序的小（"0-…" 對 "00…"）時，照樣等無序那封。"""
        self.say("有序的")
        box = str(self.stack / "queue")
        r = run("aos-post", "send", box, "0-unordered", input="{}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.say("又一封有序的")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "0.5")
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 0.5 秒，0-unordered 還沒答")

    def test_letter_key_order(self):
        """aos_ws.letter_key／names：有序（^[0-9]{12}\\.）在前照名字、無序在後照名字；不靠 sorted() 碰巧。"""
        import sys
        sys.path.insert(0, str(ROOT / "lib" / "aos"))
        import aos_ws
        new = self.stack / "queue" / "new"
        new.mkdir(parents=True)
        for n in ("000000000002.b", "000.x", "000000000001.a", ".hidden", "0a"):
            (new / n).mkdir()
        self.assertEqual(aos_ws.names(str(self.stack), "new"),
                         ["000000000001.a", "000000000002.b", "000.x", "0a"])
        self.assertEqual(max(aos_ws.names(str(self.stack), "new"), key=aos_ws.letter_key), "0a")
        self.assertEqual(aos_ws.STAGES, ("new", "cur", "archive"))

    def test_last_prints_question_and_answer(self):
        self.say("一")
        self.assertEqual(self.go().returncode, 0)                        # 一封一輪（同一批會合成一則回答）
        self.say("二")
        self.assertEqual(self.go().returncode, 0)
        r = run(LISTEN, "--ws", str(self.ws), "--last", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?s)^== #1\n> 一\nfake claude\[\w+\]: 一\n== #2\n> 二\nfake claude\[\w+\]: 二")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "1")
        self.assertTrue(r.stdout.startswith("== #2\n> 二\n"), r.stdout)

    def test_follow_prints_new_answers(self):
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--follow"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env())
        time.sleep(0.5)
        self.say("跟著看")
        self.assertEqual(self.go().returncode, 0)
        time.sleep(1)
        p.terminate()
        out, _ = p.communicate(timeout=10)
        self.assertRegex(out, r"== #1\n> 跟著看\nfake claude\[\w+\]: 跟著看")



class External(Base):
    """10-30 eca 第 7 步（C 結論 9、F 結論 18；衝突 6 刪 server.txt）：外部 coding agent＝aos-loop 包著 aos-eca-turn 的定義（P-43 草稿），
    常駐（--on-empty idle）時 say／listen 不用改；服務者（aos_human.runners）只靠 /proc。定義是 Base 的 self.eca。"""

    def xrun(self, *args, **kw):
        return run(*args, **dict(self.xenv, **kw))

    def popen(self, argv, **kw):
        e = env(**dict(self.xenv, **kw))
        for k in ("TMUX", "CODEX_HOME", "FAKE_TRANSCRIPTS"):
            e.pop(k, None)
        p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=e)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        return p

    def phase(self, stack, want):
        end = time.time() + 20
        while time.time() < end:
            try:
                if json.loads((stack / "state.json").read_text() or "{}").get("phase") in want:
                    return True
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        return False

    def test_external_runner_and_phase(self):
        """aos-exec 直接跑外部範本（idle）：say／listen 答得出；runners 認得服務者（aos-loop）；暫停時 phase paused；
        stack 裡沒有 server.txt、trace.jsonl（11-03）。"""
        p = self.popen(["aos-exec", "--ws", str(self.ws), str(self.eca)])
        self.assertTrue(self.phase(self.stack, ("waiting", "running")))
        sig = self.say("你好", **self.xenv)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--timeout", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("fake claude[") and r.stdout.rstrip().endswith(": 你好"), r.stdout)
        self.assertIn((p.pid, "aos-loop"), runners(self.ws))
        self.assertFalse((self.stack / "server.txt").exists())
        self.assertFalse((self.stack / "trace.jsonl").exists())
        (self.stack / "ctl.json").write_text('{"cmd": "pause"}')
        self.assertTrue(self.phase(self.stack, ("paused",)))
        self.assertIn("aos-loop", [n for _, n in runners(self.ws)])
        (self.stack / "ctl.json").write_text('{"cmd": "stop"}')
        self.assertEqual(p.wait(timeout=20), 0)
        self.assertEqual(runners(self.ws), [])

    def test_status_sees_runner_under_daemon(self):
        """掛在 daemon 底下（aos-daemon-ctl add --ws）：子 loop 的 AOS_STACK 是 daemon 的小格；11-03 起工作區不建 .stack 捷徑，
        stack 用 aos-daemon-ctl where --stack 名字 拿；runners 照樣認得服務者；say／listen 帶 --stack 答得出。"""
        ds = Path(self._tmp.name) / "dstack"
        ds.mkdir()
        dj = Path(self._tmp.name) / "daemon.json"
        dj.write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                  "procs_ctl_mailbox": "procs_ctl_mailbox"}))
        d = self.popen(["aos-daemon", str(dj)], AOS_STACK=str(ds))
        end = time.time() + 20
        while not (ds / "procs_ctl_mailbox" / "new").is_dir():
            self.assertLess(time.time(), end)
            time.sleep(0.05)
        ctl = str(ROOT / "bin" / "aos-daemon-ctl")
        r = self.xrun(ctl, "--daemon-stack", str(ds), "add", "--ws", str(self.ws), "--name", "bob", str(self.eca))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(os.path.lexists(self.stack))
        self.assertTrue(self.phase(ds / "procs" / "bob", ("waiting", "running")))
        r = self.xrun(ctl, "--daemon-stack", str(ds), "where", "--stack", "bob")
        self.assertEqual((r.returncode, r.stdout), (0, str(ds / "procs" / "bob") + "\n"), r.stderr)
        stack = r.stdout.strip()
        r = self.xrun(SAY, "--stack", stack, "在 daemon 底下")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.xrun(LISTEN, "--stack", stack, "--timeout", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.rstrip().endswith(": 在 daemon 底下"), r.stdout)
        import sys
        sys.path.insert(0, str(HUMAN))
        import aos_human
        self.assertIn("aos-loop", [n for _, n in aos_human.runners(aos_human.Where(str(self.ws), stack))])
        (ds / "ctl.json").write_text('{"cmd": "stop"}')
        self.assertEqual(d.wait(timeout=30), 0)


if __name__ == "__main__":
    unittest.main()
