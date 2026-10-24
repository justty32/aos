"""test_talk - 跑 demo/talk（多隻 agent 互相寄信）：一個 daemon 同時跑 ann、bob、cat 三隻 member，假 server 依「你是誰」照劇本回。

設計：proto8/thinking/2026-10-24-agent-talk.md。驗：寄信工具（名冊、群組、上限、送不到、同時寫）、自動回信、
三隻分工交換五封信、互相回信被手數上限擋住、member 失敗時團隊停下。"""
import http.server, json, os, re, shutil, subprocess, tempfile, threading, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
TALK = ROOT / "demo" / "talk"
SEND = str(TALK / "member" / "tools" / "send_message")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_ROSTER")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def call(name, arguments):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_%s" % name, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}}]}


def answer(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def body_of(text):
    return text.split("\n---\n", 1)[1] if "\n---\n" in text else text


def study_group(req):
    """讀書會劇本：ann 統籌（問 bob 算、請 cat 寫、交給 user），bob 用 math 算，cat 寫公告。"""
    msgs = req["messages"]
    me = re.search(r"你是 (\w+)。", msgs[0]["content"]).group(1)
    last = msgs[-1]
    if last["role"] == "tool":
        if me == "bob":
            return answer("總餐費 = 17 × 3 × 235 = %s 元。" % last["content"].strip())
        return answer("已寄出，等回信。")
    text = last["content"]
    if me == "ann":
        if "寄件人：user" in text:
            return call("send_message", {"to": "bob", "subject": "算餐費", "expect_reply": True,
                                         "body": "請算讀書會總餐費：17 人 × 3 天 × 每人每天 235 元，回我總額與算式。"})
        if "寄件人：bob" in text:
            return call("send_message", {"to": "cat", "subject": "寫公告", "expect_reply": True,
                                         "body": "請寫一段讀書會公告（17 人、3 天），提到：" + body_of(text).strip()})
        if "寄件人：cat" in text:
            return call("send_message", {"to": "user", "subject": "讀書會公告", "expect_reply": False,
                                         "body": body_of(text).strip()})
    if me == "bob":
        return call("math", {"expr": "17*3*235"})
    if me == "cat":
        n = re.search(r"(\d{4,}) 元", text)
        return answer("【讀書會公告】三天共 17 人，總餐費 %s 元，請大家準時出席。" % (n.group(1) if n else "?"))
    return answer("不知道要做什麼")


def ping_pong(req):
    """互相回信劇本：每封信都寄回給對方、要對方回答；被擋下（錯誤：…）就收手。"""
    msgs = req["messages"]
    me = re.search(r"你是 (\w+)。", msgs[0]["content"]).group(1)
    last = msgs[-1]
    if last["role"] == "tool":
        return answer("停了：" + last["content"][:40]) if last["content"].startswith("錯誤") else answer("寄了")
    other = "bob" if me == "ann" else "ann"
    return call("send_message", {"to": other, "body": "再來一次", "expect_reply": True})


class RoleBrain:
    """假的 OpenAI 相容 server：照 decide(request) 回；三隻同時打也行。"""

    def __init__(self, decide):
        self.requests, lock = [], threading.Lock()
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                with lock:
                    brain.requests.append(req)
                data = json.dumps(decide(req), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def letters(d):
    d = Path(d)
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.is_dir() else []


class TalkCase(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.ws = Path(self._t.name)
        self.roster = json.loads((TALK / "team" / "roster.json").read_text())
        for n in ("ann", "bob", "cat", "user"):
            (self.ws / n).mkdir()
        self.write_roster()
        self.team = self.ws / "team"                  # 複製一份 team/、member/，測試可以改 daemon.json
        shutil.copytree(TALK / "team", self.team)
        shutil.copytree(TALK / "member", self.ws / "member")

    def tearDown(self):
        self._t.cleanup()

    def write_roster(self):
        (self.ws / "roster.json").write_text(json.dumps(self.roster, ensure_ascii=False))

    def send(self, who, args, raw=None):
        return run(EXEC, "--ws", str(self.ws / who), SEND, input=raw if raw is not None else json.dumps(args, ensure_ascii=False),
                   env={"AOS_ROSTER": str(self.ws / "roster.json")})

    def run_team(self, url=None, timeout=60):
        env = {"AOS_WS": str(self.ws)}
        if url:
            env["AOS_BRAIN_URL"] = url
        return run(EXEC, str(self.team), env=env, cwd=str(self.ws), timeout=timeout)


class SendMessage(TalkCase):
    def test_deliver_and_sent_copy(self):
        r = self.send("user", {"to": "ann", "subject": "hi", "body": "你好", "expect_reply": True})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("已寄出 1 封", r.stdout)
        [l] = letters(self.ws / "ann" / "new")
        self.assertEqual((l["from"], l["to"], l["hops"], l["reply_to"], l["thread"]), ("user", "ann", 1, None, l["id"]))
        self.assertTrue(l["expect_reply"])
        self.assertEqual(letters(self.ws / "user" / "sent"), [l])
        self.assertEqual(list((self.ws / "ann" / "tmp").iterdir()), [])

    def test_group_excludes_self(self):
        r = self.send("ann", {"to": "all", "body": "大家好"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(letters(self.ws / "ann" / "new"), [])
        b, c = letters(self.ws / "bob" / "new"), letters(self.ws / "cat" / "new")
        self.assertEqual((len(b), len(c), b[0]["group"], b[0]["thread"]), (1, 1, "all", c[0]["thread"]))

    def test_model_errors_exit_0(self):
        for args, want in (({"to": "zed", "body": "x"}, "不認得「zed」"),
                           ({"to": "ann", "body": "x"}, "沒有收件人"),
                           ({"to": "bob", "body": ""}, "body 要是非空字串"),
                           ({"to": "bob", "body": "長" * 9000}, "信太大")):
            r = self.send("ann", args)
            self.assertEqual((r.returncode, r.stdout.startswith("錯誤：")), (0, True), (args, r.stdout))
            self.assertIn(want, r.stdout)
        self.assertEqual(letters(self.ws / "bob" / "new"), [])

    def test_mailbox_missing(self):
        shutil.rmtree(self.ws / "cat")
        r = self.send("ann", {"to": ["bob", "cat"], "body": "x"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("已寄出 1 封", r.stdout)
        self.assertIn("錯誤：送不到 cat", r.stdout)

    def test_env_errors_exit_1(self):
        r = run(EXEC, "--ws", str(self.ws / "ann"), SEND, input="{}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("send_message: RosterMissing", r.stderr)
        (self.ws / "stranger").mkdir()
        r = self.send("stranger", {"to": "ann", "body": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("send_message: SelfUnknown", r.stderr)

    def test_thread_follows_letter_in_cur_and_limits(self):
        self.roster.update(max_hops=3, max_sends=2)
        self.write_roster()
        self.send("user", {"to": "ann", "body": "題目", "expect_reply": True})
        (self.ws / "ann" / "cur").mkdir()
        [p] = (self.ws / "ann" / "new").iterdir()
        p.rename(self.ws / "ann" / "cur" / p.name)     # 假裝 ann 認領了
        r = self.send("ann", {"to": ["bob", "cat"], "body": "幫忙"})
        self.assertIn("第 2 手", r.stdout)
        b = letters(self.ws / "bob" / "new")[0]
        self.assertEqual((b["hops"], b["reply_to"], b["thread"]), (2, p.stem, json.loads((self.ws / "ann" / "cur" / p.name).read_text())["thread"]))
        r = self.send("ann", {"to": "bob", "body": "再一封"})            # 這一層已寄 2 封＝上限
        self.assertTrue(r.stdout.startswith("錯誤：處理這一封時已經寄了 2 封"), r.stdout)
        letter = json.loads((self.ws / "ann" / "cur" / p.name).read_text())
        letter["hops"] = 3
        (self.ws / "ann" / "cur" / p.name).write_text(json.dumps(letter))
        r = self.send("ann", {"to": "bob", "body": "超過"})
        self.assertTrue(r.stdout.startswith("錯誤：這個對話串已經傳了 3 手"), r.stdout)

    def test_many_senders_at_once(self):
        with ThreadPoolExecutor(10) as ex:
            rs = list(ex.map(lambda i: self.send(("bob", "cat")[i % 2], {"to": "ann", "body": "第 %d 封" % i}), range(20)))
        self.assertTrue(all(r.returncode == 0 for r in rs), [r.stderr for r in rs])
        got = letters(self.ws / "ann" / "new")
        self.assertEqual(sorted(l["body"] for l in got), sorted("第 %d 封" % i for i in range(20)))
        self.assertEqual(list((self.ws / "ann" / "tmp").iterdir()), [])


class Team(TalkCase):
    def test_fake_brain_auto_reply(self):
        self.send("user", {"to": "ann", "subject": "問", "body": "1+1？", "expect_reply": True})
        r = self.run_team()
        self.assertEqual(r.returncode, 0, r.stderr)
        [l] = letters(self.ws / "user" / "new")
        self.assertEqual((l["from"], l["subject"], l["hops"], l["expect_reply"]), ("ann", "Re: 問", 2, False))
        self.assertIn("FAKE ANSWER to: 1+1？", l["body"])
        self.assertEqual(json.loads((self.ws / ".stack" / "state.json").read_text())["phase"], "done")

    def test_three_agents_study_group(self):
        brain = RoleBrain(study_group)
        try:
            self.send("user", {"to": "ann", "subject": "讀書會", "expect_reply": False,
                               "body": "幫我準備讀書會公告：17 人、3 天、每人每天餐費 235 元。"})
            r = self.run_team(brain.url)
        finally:
            brain.close()
        self.assertEqual(r.returncode, 0, r.stderr)
        [final] = letters(self.ws / "user" / "new")
        self.assertEqual(final["from"], "ann")
        self.assertIn("總餐費 11985 元", final["body"])
        sent = sorted((l for n in ("user", "ann", "bob", "cat") for l in letters(self.ws / n / "sent")), key=lambda l: l["hops"])
        self.assertEqual([(l["from"], l["to"], l["hops"]) for l in sent],
                         [("user", "ann", 1), ("ann", "bob", 2), ("bob", "ann", 3), ("ann", "cat", 4), ("cat", "ann", 5), ("ann", "user", 6)])
        self.assertEqual(len({l["thread"] for l in sent}), 1)
        for n in ("ann", "bob", "cat"):
            for d in ("new", "cur", "tmp"):
                p = self.ws / n / d
                self.assertEqual(list(p.iterdir()) if p.is_dir() else [], [], (n, d))

    def test_ping_pong_stops_at_max_hops(self):
        self.roster["max_hops"] = 5
        self.write_roster()
        brain = RoleBrain(ping_pong)
        try:
            self.send("user", {"to": "ann", "body": "開始", "expect_reply": False})
            r = self.run_team(brain.url)
        finally:
            brain.close()
        self.assertEqual(r.returncode, 0, r.stderr)
        sent = [l for n in ("ann", "bob") for l in letters(self.ws / n / "sent")]
        self.assertEqual(sorted(l["hops"] for l in sent), [2, 3, 4, 5])      # 第 1 手是 user 寄的；第 6 手被擋
        outs = [p.read_text() for n in ("ann", "bob") for p in (self.ws / n / "out").glob("*.txt")]
        self.assertTrue(any("停了：錯誤：這個對話串已經傳了 5 手" in o for o in outs), outs)

    def test_member_failed_stops_team(self):
        self.send("user", {"to": "ann", "body": "x", "expect_reply": True})
        r = self.run_team("http://127.0.0.1:9/v1")          # 連不上：ann 的腦 BrainFailed、她的 loop 退 1
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("talk-member: BrainFailed", r.stderr + (self.ws / ".stack" / "ann" / "stderr.txt").read_text())
        self.assertIn("team: MemberFailed ann", r.stderr)
        self.assertEqual(len(letters(self.ws / "ann" / "cur")), 1)                 # 信留在 cur/，修好再跑會接著做


if __name__ == "__main__":
    unittest.main()
