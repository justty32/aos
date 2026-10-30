"""test_round_queue - proto8/lib/agent 的 queue、history、compact 三格（agent-round § 7 第 2、3 步；queue 10-30 改 agent-lifecycle 第 1 步）。

每格照共通介面叫：aos-exec <格> <agent 資料夾> <子命令>；格靠 agent 資料夾的 parts.json（aos-parts which --json）找別的格。
queue（10-30 起＝$AOS_STACK/queue/，N-16 有順序的信箱，底下叫 aos-post）：push 之後 queue/new/ 有一封（body＝message、有序號）
→ claim（信在 cur/、current.txt、history 多一則）→ finish（信不見、--keep 進 done/）；pop 等信不見後印 history 最新 assistant；
沒有 queue/ 就建；push 壞 message；非有序的信與 body 壞＝壞信丟掉；withdraw 已認領報錯；claim 各步之間當掉重跑接得上（含 --more）；
claim --more（插話）；pop 逾時退 10。history：append 壞輸入 HistoryBad、compact 換上與 --expect-bytes。
compact：塞大 history 跑 compact，history_archive/ 多一份原文、新的 read 得到；沒超過 MAX_BYTES 什麼都不動。
問腦用測試自己寫的假 endpoint（一支 sh），不連真模型。設計：proto8/thinking/2026-10-28-agent-round.md § 4、§ 5、文末「實作時代定」；
queue 佈局：proto8/thinking/2026-10-30-agent-lifecycle.md 結論 A-1～A-9。"""
import json, os, re, subprocess, tempfile, time, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

EXEC = tool("aos-exec")
POST = tool("aos-post")
LIB = ROOT / "lib" / "agent"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "MAX_BYTES", "ENDPOINT")
FAKE_ENDPOINT = """#!/bin/sh
# 假 endpoint：吃一份請求、記一行到 calls.log、吐一則 assistant（不是 JSON 的 content＝compact 走退路）
cat > /dev/null
echo called >> "%s"
echo '{"role": "assistant", "content": "短摘要"}'
"""


def user(text):
    return json.dumps({"role": "user", "content": text}, ensure_ascii=False)


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        t = self.t = Path(self._t.name)
        self.agent, self.ws = t / "agent", t / "ws"
        self.agent.mkdir()
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
        self.box = self.stack / "queue"
        self.calls = t / "calls.log"
        ep = t / "fake_endpoint"
        ep.write_text(FAKE_ENDPOINT % self.calls)
        ep.chmod(0o755)
        self.parts = {"queue": {"path": str(LIB / "queue")}, "history": {"path": str(LIB / "history")},
                      "compact": {"path": str(LIB / "compact"), "env": {"MAX_BYTES": "4096"}},
                      "endpoint/default": {"path": str(ep)}}
        self.write_parts()
        self.env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        self.env.update({"PATH": path_with(self.env.get("PATH", "")), "AOS_WS": str(self.ws),
                         "AOS_STACK": str(self.stack) + "/"})
        self.stack.mkdir()

    def write_parts(self):
        (self.agent / "parts.json").write_text(json.dumps({"parts": self.parts}))

    def part(self, slot, *args, stdin="", env=None):
        p = self.parts[slot]
        env = dict(env or self.env, **p.get("env", {}))
        return subprocess.run([EXEC, p["path"], str(self.agent)] + list(args), input=stdin,
                              capture_output=True, text=True, env=env, timeout=60)

    def ok(self, slot, *args, stdin=""):
        r = self.part(slot, *args, stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def fails(self, code, slot, *args, stdin="", env=None):
        r = self.part(slot, *args, stdin=stdin, env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.startswith("%s: %s " % (slot, code)), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        return r

    def ls(self, stage):
        d = self.box / stage
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def history(self):
        return json.loads(self.ok("history", "read"))

    def post(self, *args, stdin=""):
        r = subprocess.run([POST] + list(args), input=stdin, capture_output=True, text=True, env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def say(self, text):
        return self.ok("queue", "push", stdin=user(text)).strip()


class Queue(Base):
    def test_push_peek_claim_finish(self):
        self.assertFalse(self.box.exists())
        sig = self.say("你好")
        self.assertRegex(sig, r"^000000000001\.[0-9]{20}\.")               # 有序：序號 1
        self.assertEqual(self.ls("new"), [sig])                              # queue 沒有就建
        letter = json.loads((self.box / "new" / sig / "letter.json").read_text())
        self.assertEqual((letter["kind"], letter["body"]), ("letter", {"role": "user", "content": "你好"}))
        self.assertEqual(self.ok("queue", "peek").split(), [sig])
        self.assertEqual(self.ok("queue", "claim").strip(), sig)
        self.assertEqual(self.ls("cur"), [sig])
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ok("queue", "current").split(), [sig])
        self.assertEqual((self.stack / "current.txt").read_text(), sig + "\n")
        self.assertEqual(self.history(), [{"role": "user", "content": "你好"}])   # body 原樣接進 history
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": "答案"}))
        self.ok("queue", "finish", stdin="stdin 不看")
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.ls("done"), [])                                # 預設刪
        self.assertFalse((self.stack / "current.txt").exists())
        self.assertFalse((self.ws / "out").exists() or (self.ws / "new").exists())   # 工作區不長東西
        self.assertEqual(self.ok("queue", "pop", sig), "答案\n")
        self.assertEqual(self.part("queue", "claim").returncode, 10)       # 沒信退 10

    def test_finish_keep_goes_to_done(self):
        sig = self.say("一")
        self.ok("queue", "claim")
        self.ok("queue", "finish", "--keep")
        self.assertEqual(self.ls("done"), [sig])
        self.assertEqual(self.ok("queue", "done").split(), [sig])
        self.assertEqual(self.ls("cur"), [])

    def test_order_follows_push(self):
        sigs = [self.say(str(i)) for i in range(3)]
        self.assertEqual([s[:12] for s in sigs], ["%012d" % i for i in (1, 2, 3)])
        self.assertEqual(self.ok("queue", "peek").split(), sigs)
        self.assertEqual(self.ok("queue", "claim").strip(), sigs[0])

    def test_push_bad_message(self):
        for bad in ("你好", "", "[1]", '"字串"', '{"content": "沒有 role"}', '{"role": 1}'):
            with self.subTest(stdin=bad):
                self.fails("MessageBad", "queue", "push", stdin=bad)
        self.assertFalse(self.box.exists())
        self.fails("ArgumentsBad", "queue", "push", "q.txt", stdin=user("一"))   # 信號由 aos-post 給，不收名字

    def test_push_creates_stack(self):
        """可以先說再跑 agent：stack 還沒有也建得出 queue/。"""
        env = dict(self.env, AOS_STACK=str(self.t / "later" / ".stack"))
        r = self.part("queue", "push", stdin=user("一"), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(self.t / "later" / ".stack" / "queue" / "new")), [r.stdout.strip()])

    def test_bad_letters_are_dropped(self):
        """非有序的信（aos-post send 沒帶 --ordered）與 body 不是 message 的信＝壞信：丟掉、認領下一封、不寫 stderr。"""
        self.post("init", str(self.box))
        plain = self.post("send", str(self.box), stdin=user("沒序號"))
        self.post("send", "--ordered", str(self.box), stdin='"純字串"')
        good = self.say("好的")
        r = self.part("queue", "claim")                                      # 照名字排：bad（序號 1）→ good（2）→ plain
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (0, good, ""))
        self.assertEqual(self.ls("cur"), [good])
        self.assertEqual(self.ls("new"), [plain])
        self.assertEqual(self.history(), [{"role": "user", "content": "好的"}])
        self.ok("queue", "finish", "--keep")
        r = self.part("queue", "claim")                                      # 剩下非有序的那封：丟掉＝沒信
        self.assertEqual((r.returncode, r.stderr), (10, ""))
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("done"), [good])                            # 壞信不進 done/
        self.assertEqual(os.listdir(self.box / "tmp"), [])
        self.assertEqual(len(self.history()), 1)

    def test_only_bad_letters_is_empty(self):
        self.post("init", str(self.box))
        self.post("send", str(self.box), stdin=user("沒序號"))
        r = self.part("queue", "claim")
        self.assertEqual((r.returncode, r.stderr), (10, ""))
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.history(), [])

    def test_withdraw_only_new(self):
        a = self.say("一")
        b = self.say("二")
        self.assertEqual(self.ok("queue", "claim").strip(), a)
        self.fails("LetterClaimed", "queue", "withdraw", a)
        self.assertEqual(self.ls("cur"), [a])
        self.ok("queue", "withdraw", b)
        self.assertEqual(self.ls("new"), [])
        self.fails("LetterUnknown", "queue", "withdraw", "000000000009.nope")
        self.fails("ArgumentsBad", "queue", "withdraw", "../x")

    def crash_state(self, step):
        """模擬 claim 在第 step 步之後當掉：① aos-post claim 進 cur/ ② history 接了 user ③ current.txt 寫了。"""
        sig = self.say("題目")
        if step >= 1:
            self.assertEqual(self.post("claim", str(self.box)), sig)
        if step >= 2:
            self.ok("history", "append", stdin=user("題目"))
        if step >= 3:
            (self.stack / "current.txt").write_text(sig + "\n")
        return sig

    def test_claim_resumes_after_each_step(self):
        for step in (0, 1, 2, 3):
            with self.subTest(step=step):
                self.setUp()
                sig = self.crash_state(step)
                self.assertEqual(self.ok("queue", "claim").strip(), sig)
                self.assertEqual(self.history(), [{"role": "user", "content": "題目"}])   # 不接兩次、也不漏
                self.assertEqual(self.ls("cur"), [sig])
                self.assertEqual(self.ls("new"), [])
                self.assertEqual((self.stack / "current.txt").read_text(), sig + "\n")

    def test_claim_ignores_stale_current(self):
        """上次 finish 死在清 current.txt 之前：舊信號不在 cur/，不算。"""
        (self.stack / "current.txt").write_text("000000000001.old\n")
        sig = self.say("新")
        self.assertEqual(self.ok("queue", "claim").strip(), sig)
        self.assertEqual((self.stack / "current.txt").read_text(), sig + "\n")

    def test_claim_does_not_reuse_previous_answer(self):
        """上一題答完（最後一則是 assistant）才認領新信：新信要接一則 user；當掉在 ① 之後重跑也一樣。"""
        self.ok("history", "append", stdin=user("舊題"))
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": "舊答"}))
        sig = self.say("新題")
        self.post("claim", str(self.box))                                    # 死在 ① 之後
        self.assertEqual(self.ok("queue", "claim").strip(), sig)
        self.assertEqual(self.history()[-1], {"role": "user", "content": "新題"})
        self.assertEqual(len(self.history()), 3)

    def test_claim_more_takes_interrupting_message(self):
        a = self.say("一")
        self.ok("queue", "claim")
        self.ok("history", "append", stdin=json.dumps({"role": "tool", "tool_call_id": "c1", "content": "被打斷"}))
        b = self.say("二")
        self.assertEqual(self.ok("queue", "claim", "--more").strip(), b)
        self.assertEqual(self.history()[-1], {"role": "user", "content": "二"})
        self.assertEqual((self.stack / "current.txt").read_text(), a + "\n" + b + "\n")
        self.assertEqual(self.ls("cur"), [a, b])
        self.assertEqual(self.part("queue", "claim", "--more").returncode, 10)
        self.ok("queue", "finish", "--keep")
        self.assertEqual(self.ls("done"), [a, b])
        self.assertEqual(self.ls("cur"), [])

    def test_claim_more_resumes(self):
        """--more 死在 ① 之後（b 進了 cur/、還沒接）：之後一般的 claim 照 --more 的規則補接 b（最後一則是 tool 也要接）。"""
        a = self.say("一")
        self.ok("queue", "claim")
        self.ok("history", "append", stdin=json.dumps({"role": "tool", "tool_call_id": "c1", "content": "被打斷"}))
        b = self.say("二")
        self.post("claim", str(self.box))
        self.assertEqual(self.ok("queue", "claim").split(), [a, b])
        self.assertEqual(self.history()[-1], {"role": "user", "content": "二"})
        self.assertEqual(len(self.history()), 3)
        self.assertEqual((self.stack / "current.txt").read_text(), a + "\n" + b + "\n")

    def test_claim_without_history_part(self):
        del self.parts["history"]
        self.write_parts()
        sig = self.say("一")
        self.fails("PartMissing", "queue", "claim")
        self.assertEqual(self.ls("new"), [sig])                               # 先找 history 格、找不到就不搬

    def test_claim_without_queue(self):
        self.assertEqual(self.part("queue", "claim").returncode, 10)
        self.assertEqual(self.ok("queue", "peek"), "")

    def test_pop_waits_then_answers(self):
        sig = self.say("一")
        r = self.part("queue", "pop", "--timeout-s", "0.3", sig)              # 還在 new/：等到逾時退 10
        self.assertEqual((r.returncode, r.stdout), (10, ""), r.stderr)
        self.ok("queue", "claim")
        r = self.part("queue", "pop", "--timeout-s", "0.3", sig)              # 在 cur/：照樣等
        self.assertEqual(r.returncode, 10, r.stderr)
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}))
        self.ok("history", "append", stdin=json.dumps({"role": "tool", "tool_call_id": "c1", "content": "12:00"}))
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": "十二點"}))
        p = subprocess.Popen([EXEC, self.parts["queue"]["path"], str(self.agent), "pop", "--timeout-s", "20", sig],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        self.ok("queue", "finish")
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "十二點\n"), err)            # 跳過帶 tool_calls 的那則

    def test_pop_unknown_and_missing(self):
        self.fails("LetterUnknown", "queue", "pop", "--timeout-s", "0.3", "000000000001.nope")
        sig = self.say("一")
        self.ok("queue", "withdraw", sig)
        self.fails("LetterUnknown", "queue", "pop", sig)                      # 沒看到過、history 也沒 assistant
        sig = self.say("二")
        self.ok("queue", "claim")
        p = subprocess.Popen([EXEC, self.parts["queue"]["path"], str(self.agent), "pop", "--timeout-s", "20", sig],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        time.sleep(0.5)                                                       # 讓 pop 先看到信在 cur/
        self.ok("queue", "finish")                                            # 沒答就收掉
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 1, out + err)
        self.assertTrue(re.search(r"^queue: AnswerMissing ", err, re.M), err)

    def test_push_wait(self):
        p = subprocess.Popen([EXEC, self.parts["queue"]["path"], str(self.agent), "push", "--wait", "--timeout-s", "20"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        p.stdin.write(user("一"))
        p.stdin.close()
        sig = p.stdout.readline().strip()
        self.assertRegex(sig, r"^000000000001\.")
        self.ok("queue", "claim")
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": "答"}))
        self.ok("queue", "finish")
        self.assertEqual(p.stdout.read(), "答\n")
        self.assertEqual(p.wait(timeout=30), 0, p.stderr.read())
        p.stdout.close()
        p.stderr.close()

    def test_emit_appends_live(self):
        self.ok("queue", "emit", stdin='{"role": "assistant", "content": "a"}')
        self.ok("queue", "emit", stdin='{"role": "assistant", "content": "b"}')
        lines = (self.stack / "live.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(l)["content"] for l in lines], ["a", "b"])
        self.fails("MessageBad", "queue", "emit", stdin="not json")

    def test_finish_without_claim(self):
        self.fails("LetterMissing", "queue", "finish")
        self.say("一")
        self.fails("LetterMissing", "queue", "finish")


class History(Base):
    def test_append_bad_is_history_bad(self):
        for bad in ("not json", "[1, 2]", '"字串"', ""):
            with self.subTest(stdin=bad):
                self.fails("HistoryBad", "history", "append", stdin=bad)
        self.assertEqual(self.history(), [])
        self.ok("history", "append", stdin='{"role": "user",\n "content": "多行也行"}')
        self.assertEqual(self.history(), [{"role": "user", "content": "多行也行"}])
        self.assertEqual(len((self.stack / "history.jsonl").read_text().splitlines()), 1)

    def test_read_bad_line(self):
        (self.stack / "history.jsonl").write_text('{"role": "user"}\nnope\n')
        self.fails("HistoryBad", "history", "read")

    def test_compact_swaps_and_archives(self):
        old = '{"role": "user", "content": "一"}\n{"role": "assistant", "content": "二"}\n'
        (self.stack / "history.jsonl").write_text(old)
        self.fails("HistoryBad", "history", "compact", stdin='{"role": "user"}\n[1]\n')
        self.fails("HistoryChanged", "history", "compact", "--expect-bytes", "1", stdin='{"role": "user"}\n')
        self.assertEqual((self.stack / "history.jsonl").read_text(), old)
        self.assertFalse((self.stack / "history_archive").exists() and any((self.stack / "history_archive").iterdir()))
        out = self.ok("history", "compact", "--expect-bytes", str(len(old.encode())), stdin='{"role": "user", "content": "短"}\n')
        arch = self.stack / out.strip()
        self.assertEqual(arch.parent.name, "history_archive")
        self.assertEqual(arch.read_text(), old)
        self.assertEqual(self.history(), [{"role": "user", "content": "短"}])


def big_history(turns, pad):
    rows = []
    for i in range(turns):
        rows.append({"role": "user", "content": "第 %d 題：請算 %d+1" % (i, i)})
        rows.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "c%d" % i, "type": "function", "function": {"name": "math", "arguments": '{"expr": "%d+1"}' % i}}]})
        rows.append({"role": "tool", "tool_call_id": "c%d" % i, "content": str(i + 1) + " " + "x" * pad})
        rows.append({"role": "assistant", "content": "答案是 %d" % (i + 1)})
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


class Compact(Base):
    def test_big_history_is_compacted(self):
        old = big_history(6, 1500)
        (self.stack / "history.jsonl").write_text(old)
        self.assertGreater(len(old.encode()), 4096)
        self.assertEqual(self.ok("compact"), "")
        archives = list((self.stack / "history_archive").iterdir())
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_text(), old)                       # 原文整份收著
        new = self.history()
        self.assertLess(len((self.stack / "history.jsonl").read_bytes()), len(old.encode()))
        self.assertTrue(new[0]["content"].startswith("【compact】"), new[0])
        self.assertIn("短摘要", new[0]["content"])
        self.assertEqual(new[1]["role"], "assistant")
        self.assertEqual([m["content"] for m in new if m["role"] == "user"][1:], ["第 4 題：請算 4+1", "第 5 題：請算 5+1"])
        self.assertEqual(new[-1], {"role": "assistant", "content": "答案是 6"})   # 最近 2 題原樣
        self.assertGreater(len(self.calls.read_text().splitlines()), 0)            # 有問 endpoint
        runs = [p for p in (self.stack / "compact").iterdir() if p.is_dir()]
        self.assertEqual(len(runs), 1)
        report = json.loads((runs[0] / "report.json").read_text())
        self.assertEqual(report["archive"], "history_archive/" + archives[0].name)

    def test_under_max_bytes_does_nothing(self):
        old = big_history(6, 1500)
        (self.stack / "history.jsonl").write_text(old)
        self.parts["compact"]["env"]["MAX_BYTES"] = str(len(old.encode()))
        self.write_parts()
        self.assertEqual(self.ok("compact"), "")
        self.assertEqual((self.stack / "history.jsonl").read_text(), old)
        self.assertFalse((self.stack / "history_archive").exists())
        self.assertFalse((self.stack / "compact").exists())
        self.assertFalse(self.calls.exists())

    def test_endpoint_failure_leaves_history(self):
        old = big_history(6, 1500)
        (self.stack / "history.jsonl").write_text(old)
        bad = self.t / "bad_endpoint"
        bad.write_text("#!/bin/sh\ncat >/dev/null\necho 'endpoint: BrainFailed 連不上' >&2\nexit 1\n")
        bad.chmod(0o755)
        self.parts["endpoint/default"] = {"path": str(bad)}
        self.write_parts()
        r = self.part("compact")
        self.assertEqual(r.returncode, 1)
        self.assertIn("compact: EndpointFailed ", r.stderr)
        self.assertEqual((self.stack / "history.jsonl").read_text(), old)
        self.assertFalse((self.stack / "history_archive").exists())


if __name__ == "__main__":
    unittest.main()
