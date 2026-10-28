"""test_round_queue - proto8/lib/agent 的 queue、history、compact 三格（agent-round § 7 第 2、3 步）。

每格照共通介面叫：aos-exec <格> <agent 資料夾> <子命令>；格靠 agent 資料夾的 parts.json（aos-parts which --json）找別的格。
queue：push → peek → claim（cur/、current.txt、history 有 user）→ finish（out/、done/）；withdraw 已認領報錯；claim 各步之間當掉
重跑接得上；claim --more（插話）；pop 逾時退 10。history：append 壞輸入 HistoryBad、compact 換上與 --expect-bytes。
compact：塞大 history 跑 compact，history_archive/ 多一份原文、新的 read 得到；沒超過 MAX_BYTES 什麼都不動。
問腦用測試自己寫的假 endpoint（一支 sh），不連真模型。設計：proto8/thinking/2026-10-28-agent-round.md § 4、§ 5、文末「實作時代定」。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

EXEC = tool("aos-exec")
LIB = ROOT / "lib" / "agent"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "MAX_BYTES", "ENDPOINT")
FAKE_ENDPOINT = """#!/bin/sh
# 假 endpoint：吃一份請求、記一行到 calls.log、吐一則 assistant（不是 JSON 的 content＝compact 走退路）
cat > /dev/null
echo called >> "%s"
echo '{"role": "assistant", "content": "短摘要"}'
"""


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        t = self.t = Path(self._t.name)
        self.agent, self.ws = t / "agent", t / "ws"
        self.agent.mkdir()
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
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

    def part(self, slot, *args, stdin=""):
        p = self.parts[slot]
        env = dict(self.env, **p.get("env", {}))
        return subprocess.run([EXEC, p["path"], str(self.agent)] + list(args), input=stdin,
                              capture_output=True, text=True, env=env, timeout=60)

    def ok(self, slot, *args, stdin=""):
        r = self.part(slot, *args, stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def fails(self, code, slot, *args, stdin=""):
        r = self.part(slot, *args, stdin=stdin)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.startswith("%s: %s " % (slot, code)), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        return r

    def ls(self, stage):
        d = self.ws / stage
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def history(self):
        return json.loads(self.ok("history", "read"))


class Queue(Base):
    def test_push_peek_claim_finish(self):
        name = self.ok("queue", "push", stdin="你好").strip()
        self.assertEqual(self.ok("queue", "peek").split(), [name])
        self.assertEqual(self.ok("queue", "claim").strip(), name)
        self.assertEqual(self.ls("cur"), [name])
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ok("queue", "current").split(), [name])
        self.assertEqual((self.stack / "current.txt").read_text(), name + "\n")
        self.assertEqual(self.history(), [{"role": "user", "content": "你好\n"}])
        self.ok("queue", "finish", stdin="答案")
        self.assertEqual((self.ws / "out" / name).read_text(), "答案\n")
        self.assertEqual(self.ls("done"), [name])
        self.assertEqual(self.ok("queue", "done").split(), [name])
        self.assertEqual(self.ls("cur"), [])
        self.assertFalse((self.stack / "current.txt").exists())
        self.assertEqual(self.ok("queue", "pop", name), "答案\n")
        self.assertEqual(self.part("queue", "claim").returncode, 10)       # 沒題退 10

    def test_push_name_taken_and_empty(self):
        self.ok("queue", "push", "q.txt", stdin="一")
        self.fails("NameBad", "queue", "push", "q.txt", stdin="二")
        self.fails("TextMissing", "queue", "push", stdin="  \n")
        self.assertEqual((self.ws / "new" / "q.txt").read_text(), "一\n")

    def test_withdraw_only_new(self):
        self.ok("queue", "push", "a.txt", stdin="一")
        self.ok("queue", "push", "b.txt", stdin="二")
        self.assertEqual(self.ok("queue", "claim").strip(), "a.txt")
        self.fails("QuestionClaimed", "queue", "withdraw", "a.txt")
        self.assertEqual(self.ls("cur"), ["a.txt"])
        self.ok("queue", "withdraw", "b.txt")
        self.assertEqual(self.ls("new"), [])
        self.fails("QuestionUnknown", "queue", "withdraw", "c.txt")

    def crash_state(self, step):
        """模擬 claim 在第 step 步之後當掉：① history 接了 user ② current.txt 寫了 ③ 搬進 cur/。"""
        self.ok("queue", "push", "q.txt", stdin="題目")
        if step >= 1:
            self.ok("history", "append", stdin=json.dumps({"role": "user", "content": "題目\n"}))
        if step >= 2:
            (self.stack / "current.txt").write_text("q.txt\n")
        if step >= 3:
            (self.ws / "cur").mkdir()
            os.replace(self.ws / "new" / "q.txt", self.ws / "cur" / "q.txt")

    def test_claim_resumes_after_each_step(self):
        for step in (1, 2, 3):
            with self.subTest(step=step):
                self.setUp()
                self.crash_state(step)
                self.assertEqual(self.ok("queue", "claim").strip(), "q.txt")
                self.assertEqual(self.history(), [{"role": "user", "content": "題目\n"}])   # 不接兩次
                self.assertEqual(self.ls("cur"), ["q.txt"])
                self.assertEqual(self.ls("new"), [])
                self.assertEqual((self.stack / "current.txt").read_text(), "q.txt\n")

    def test_claim_does_not_reuse_previous_answer(self):
        """上一題答完（最後一則是 assistant）才認領新題：新題要接一則 user。"""
        self.ok("history", "append", stdin=json.dumps({"role": "user", "content": "舊題\n"}))
        self.ok("history", "append", stdin=json.dumps({"role": "assistant", "content": "舊答"}))
        self.ok("queue", "push", "q.txt", stdin="新題")
        self.ok("queue", "claim")
        self.assertEqual(self.history()[-1], {"role": "user", "content": "新題\n"})

    def test_claim_more_takes_interrupting_question(self):
        self.ok("queue", "push", "a.txt", stdin="一")
        self.ok("queue", "claim")
        self.ok("history", "append", stdin=json.dumps({"role": "tool", "tool_call_id": "c1", "content": "被打斷"}))
        self.ok("queue", "push", "b.txt", stdin="二")
        self.assertEqual(self.ok("queue", "claim", "--more").strip(), "b.txt")
        self.assertEqual(self.history()[-1], {"role": "user", "content": "二\n"})
        self.assertEqual((self.stack / "current.txt").read_text(), "a.txt\nb.txt\n")
        self.assertEqual(self.ls("cur"), ["a.txt", "b.txt"])
        self.assertEqual(self.part("queue", "claim", "--more").returncode, 10)
        self.ok("queue", "finish", stdin="一起答")
        self.assertEqual(self.ls("out"), ["a.txt", "b.txt"])
        self.assertEqual((self.ws / "out" / "b.txt").read_text(), "一起答\n")
        self.assertEqual(self.ls("done"), ["a.txt", "b.txt"])

    def test_claim_without_history_part(self):
        del self.parts["history"]
        self.write_parts()
        self.ok("queue", "push", stdin="一")
        self.fails("PartMissing", "queue", "claim")
        self.assertEqual(self.ls("cur"), [])

    def test_pop_timeout_and_unknown(self):
        name = self.ok("queue", "push", stdin="一").strip()
        r = self.part("queue", "pop", "--timeout-s", "0.3", name)
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertEqual(r.stdout, "")
        self.fails("QuestionUnknown", "queue", "pop", "--timeout-s", "0.3", "nope.txt")

    def test_emit_appends_live(self):
        self.ok("queue", "emit", stdin='{"role": "assistant", "content": "a"}')
        self.ok("queue", "emit", stdin='{"role": "assistant", "content": "b"}')
        lines = (self.stack / "live.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(l)["content"] for l in lines], ["a", "b"])
        self.fails("MessageBad", "queue", "emit", stdin="not json")

    def test_finish_without_claim(self):
        self.fails("QuestionMissing", "queue", "finish", stdin="答")


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
