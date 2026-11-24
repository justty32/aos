"""回答配對（thinking/2026-11/14/reply-match-1114/03）的 agent-fsm 寫的一方：idle 記 aos.letter／pending／dropped，wait 記 aos.answer_to、清 pending，brain／stale_request 剝 aos 鍵。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

PROTO = Path(__file__).resolve().parents[3]
CELLS = PROTO / "py" / "aos" / "apps" / "agent_fsm"   # 格的程式（11-24 起搬出範本，裝好在 lib/aos/apps/agent_fsm）
TEMPLATE = PROTO / "templates" / "agents" / "agent-fsm"   # 範本本身（給人抄的定義）
sys.path.insert(0, str(PROTO / "py"))
from aos.agentlib import cooldown  # noqa: E402
CALL = {"id": "c1", "type": "function", "function": {"name": "echo", "arguments": "{}"}}
FAKE_LLM = """import json, os, sys
if sys.argv[1] == 'send':
    with open(os.environ['FAKE_SENT'], 'w') as f:
        f.write(sys.stdin.read())
    print('letter-1'); sys.exit(0)
code = int(os.environ.get('FAKE_RECV', '0'))
if code == 0:
    print(json.dumps({'message': json.loads(os.environ['FAKE_MESSAGE'])}))
else:
    print('aos-llm: error: EndpointFailed fake', file=sys.stderr)
sys.exit(code)
"""


class ReplyMatch(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-reply-match-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.defn, self.stack, self.bin = self.root / "def", self.root / "st", self.root / "bin"
        for d in (self.defn, self.stack, self.bin):
            d.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json"}}))
        (self.defn / "tools.json").write_text("{}")
        (self.defn / "llm.json").write_text('{"model":"local"}')
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") or k == "AOS_HOME"}
        self.env = dict(env, AOS_STACK=str(self.stack), AOS_CD=str(self.defn), AOS_LLM_KERNEL=str(self.root / "missing-kernel"),
                        FAKE_SENT=str(self.root / "sent.json"), FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "ok"}),
                        PATH=os.pathsep.join([str(self.bin), str(PROTO / "bin")] + [env["PATH"]]))
        self.command("aos-llm", FAKE_LLM)
        self.command("aos-tools", "import json, sys\nif 'ls' in sys.argv: print('[]')\n")

    # ---- 小工具
    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)

    def run_cell(self, name, code=0, **env):
        r = subprocess.run([sys.executable, str(CELLS / (name + ".py"))], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def send(self, body):
        """寄一封進 queue（body 照給，不檢查）；回信名。"""
        box = self.stack / "queue"
        subprocess.run(["aos-post", "init", str(box)], env=self.env, check=True, capture_output=True)
        return subprocess.run(["aos-post", "send", "--ordered", str(box)], env=self.env, check=True, capture_output=True,
                              input=json.dumps(body), text=True).stdout.strip()

    def letter(self, content, **more):
        return self.send(dict({"role": "user", "content": content}, **more))

    def history(self, rows=None):
        path = self.stack / "history.jsonl"
        if rows is not None:
            path.write_text("".join(json.dumps(m) + "\n" for m in rows))
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def letters(self):
        path = self.stack / "letters.json"
        return json.loads(path.read_text()) if path.exists() else None

    def think(self, message=None, **env):
        """brain 組請求 → wait 寄出（退 10）→ wait 收回信（退 0）；回寄出的 request.messages。"""
        if message is not None:
            env["FAKE_MESSAGE"] = json.dumps(message)
        self.run_cell("brain")
        self.run_cell("wait", 10, **env)
        sent = json.loads((self.root / "sent.json").read_text())["request"]["messages"]
        self.run_cell("wait", 0, **env)
        return sent

    # ---- 寫的一方
    def test_batch_of_letters_gets_one_answer_in_order(self):
        names = [self.letter(t) for t in ("one", "two", "three")]
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": t, "aos": {"letter": n}}
                                          for t, n in zip(("one", "two", "three"), names)])
        self.assertEqual(self.letters(), {"pending": names, "dropped": []})
        self.think()
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "ok", "aos": {"answer_to": names}})
        self.assertEqual(self.letters()["pending"], [])

    def test_tool_call_is_not_an_answer(self):
        name = self.letter("go")
        self.run_cell("idle")
        self.think({"role": "assistant", "content": None, "tool_calls": [CALL], "aos": {"answer_to": ["forged"]}})
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": None, "tool_calls": [CALL]})   # 端點的 aos 拿掉、不配
        self.assertEqual(self.letters()["pending"], [name])                                                 # 還沒答

    def test_bad_and_blocked_letters_are_dropped(self):
        bad = self.send({"role": "user", "content": "   "})
        good = self.letter("fine")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "fine", "aos": {"letter": good}}])
        d = self.letters()
        self.assertEqual(d["pending"], [good])
        self.assertEqual([(x["letter"], x["reason"]) for x in d["dropped"]], [(bad, "bad")])
        self.assertRegex(d["dropped"][0]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
        # 被 before_queue 擋的
        hook = self.defn / "drop.py"
        hook.write_text("#!" + sys.executable + "\nimport sys\nsys.stdin.read()\nsys.exit(10)\n")
        hook.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps(
            {"aos-agent": {"tools": "tools.json", "llm": "llm.json"}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"d": {"event": "before_queue", "handler": "drop.py"}}))
        spam = self.letter("spam")
        self.run_cell("idle", 10)
        d = self.letters()
        self.assertEqual(d["pending"], [good])
        self.assertEqual([(x["letter"], x["reason"]) for x in d["dropped"]], [(bad, "bad"), (spam, "blocked")])
        self.assertEqual(len(self.history()), 1)

    def test_forged_aos_keys_are_overwritten(self):
        name = self.letter("hi", aos={"answer_to": ["someone-else"]})
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "hi", "aos": {"letter": name}}])
        self.think({"role": "assistant", "content": "ok", "aos": {"answer_to": ["forged"], "letter": "x"}})
        self.assertEqual(self.history()[-1]["aos"], {"answer_to": [name]})

    def test_no_letter_no_aos_key(self):
        self.history([{"role": "user", "content": "[aos] goal: do it"}])                  # 不經 queue 的 user 列
        self.think()
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "ok"})
        self.assertIsNone(self.letters())

    # ---- 送端點
    def test_endpoint_never_sees_aos_and_request_is_not_stale(self):
        name = self.letter("hi")
        self.run_cell("idle")
        self.history(self.history() + [{"role": "assistant", "tool_calls": [CALL], "extra": 4, "aos": {"x": 1}},
                                       {"role": "tool", "tool_call_id": "c1", "content": "r"}])
        self.run_cell("brain")
        messages = json.loads((self.stack / "think/request.json").read_text())["request"]["messages"]
        self.assertEqual(messages, [{"role": "user", "content": "hi"},
                                    {"role": "assistant", "tool_calls": [CALL], "extra": 4},
                                    {"role": "tool", "tool_call_id": "c1", "content": "r"}])   # 只少 aos，其他鍵照留
        self.assertEqual(self.history()[0]["aos"], {"letter": name})                             # history 本身不動
        # stale_request：history 最後一則帶 aos、request 裡那則沒帶，剝了再比＝不算過期（退 10 寄出，不是 11 重組）
        self.history([{"role": "user", "content": "hi", "aos": {"letter": name}}])
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.assertTrue((self.stack / "think/pending.txt").is_file())
        sent = json.loads((self.root / "sent.json").read_text())["request"]["messages"]
        self.assertEqual(sent, [{"role": "user", "content": "hi"}])
        # 真的換了內容的還是判過期
        (self.stack / "think/pending.txt").unlink()
        self.history([{"role": "user", "content": "other", "aos": {"letter": name}}])
        os.utime(self.stack / "think/request.json")
        self.run_cell("wait", 11)

    # ---- 腦失敗、摺疊
    def test_brain_failure_carries_letters_to_next_answer(self):
        first = self.letter("first")
        self.run_cell("idle")
        self.run_cell("brain")
        self.run_cell("wait", 10)
        r = self.run_cell("wait", 1, FAKE_RECV="1")
        self.assertIn("BrainFailed", r.stderr)
        self.assertEqual(self.letters()["pending"], [first])                               # 失敗：pending 留著
        rec = json.loads((self.stack / cooldown.NAME).read_text())                         # 冷卻到了（同 test_cooldown.past）
        rec["until"] = cooldown.iso(time.time() - 5)
        (self.stack / cooldown.NAME).write_text(json.dumps(rec))
        second = self.letter("second")
        self.run_cell("idle")
        self.think()
        self.assertEqual(self.history()[-1]["aos"], {"answer_to": [first, second]})        # 模型看得到兩封，一起算
        self.assertEqual(self.letters()["pending"], [])

    def test_answer_matches_after_this_turn_user_rows_are_folded(self):
        name = self.letter("long question")
        self.run_cell("idle")
        self.history([{"role": "user", "content": "[aos] summary: lines 1-1, 1 message."}])   # summarize／do_task 把本輪 user 列摺掉
        self.think()
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "ok", "aos": {"answer_to": [name]}})
        self.assertEqual(self.letters()["pending"], [])

    def test_answered_letters_are_not_answered_again(self):
        a = self.letter("a")
        self.run_cell("idle")
        self.think()
        b = self.letter("b")
        self.run_cell("idle")
        self.think({"role": "assistant", "content": "second"})
        answers = [m.get("aos") for m in self.history() if m["role"] == "assistant"]
        self.assertEqual(answers, [{"answer_to": [a]}, {"answer_to": [b]}])


if __name__ == "__main__":
    unittest.main()
