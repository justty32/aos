"""驗畫面 hook 跟上 CLI 的對話（11-12 eca-slash）：id 換了就改記 session.txt；claude 的 /clear（SessionStart source clear）連 aos 的 history 一起清、原文搬到旁邊；codex 取標題的旁支 thread 不記。"""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent import cli_session  # noqa: E402


class HookFollow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-hook-"))
        self.stack = self.tmp / "stack"
        self.cell = self.stack / "claude"
        self.cell.mkdir(parents=True)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.cell / "ws.txt").write_text("../../ws\n")
        (self.cell / "stack.txt").write_text("..\n")
        (self.cell / "session.txt").write_text("old\n")
        (self.cell / ".history_sum").write_text("abc\n")
        self.hist = self.stack / "history.jsonl"
        self.hist.write_text('{"role": "user", "content": "PLUM-7"}\n{"role": "assistant", "content": "ok"}\nnot json\n')
        self.env = patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp / "claude-home"),
                                           "CODEX_HOME": str(self.tmp / "codex-home")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def claude(self, payload, cell=None):
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
            cli_session.hook_main("claude", str(cell or self.cell))

    def read(self, name):
        return (self.cell / name).read_text().strip() if (self.cell / name).exists() else None

    def test_clear_follows_new_id_and_clears_history(self):
        self.claude({"hook_event_name": "SessionStart", "source": "clear", "session_id": "new"})
        self.assertEqual(self.read("session.txt"), "new")
        self.assertEqual(json.loads(self.read(".session_home"))["session"], "new")
        self.assertEqual(self.hist.read_text(), "")
        removed = [json.loads(l) for l in (self.stack / "history_removed.jsonl").read_text().splitlines()]
        self.assertEqual([r["line"] for r in removed], [1, 2, 3])
        self.assertEqual({r["op"] for r in removed}, {"clear"})
        self.assertEqual(removed[0]["message"], {"role": "user", "content": "PLUM-7"})
        self.assertEqual(removed[2]["raw"], "not json")
        self.assertIsNone(self.read(".history_sum"))          # 不然下一輪當成 history 被改過、又丟掉新對話
        self.assertFalse((self.cell / "turns.jsonl").exists())

    def test_startup_does_not_write_the_id(self):
        (self.cell / "session.txt").unlink()
        self.claude({"hook_event_name": "SessionStart", "source": "startup", "session_id": "fresh"})
        self.assertIsNone(self.read("session.txt"))           # 第一輪才記：ask 看它空著才接 reseed
        self.assertIn("PLUM-7", self.hist.read_text())

    def test_compact_and_resume_keep_history(self):
        for source in ("compact", "resume"):
            self.claude({"hook_event_name": "SessionStart", "source": source, "session_id": "old"})
        self.assertEqual(self.read("session.txt"), "old")
        self.assertIn("PLUM-7", self.hist.read_text())
        self.assertFalse((self.stack / "history_removed.jsonl").exists())

    def test_prompt_and_stop_follow_a_changed_id(self):
        self.claude({"hook_event_name": "UserPromptSubmit", "session_id": "other"})
        self.assertEqual(self.read("session.txt"), "other")
        self.assertTrue((self.cell / "busy.txt").exists())
        (self.cell / "session.txt").write_text("old\n")
        self.claude({"hook_event_name": "Stop", "session_id": "other2", "last_assistant_message": "hi"})
        self.assertEqual(self.read("session.txt"), "other2")
        self.assertEqual(json.loads(self.read("turns.jsonl"))["text"], "hi")
        self.assertFalse((self.cell / "busy.txt").exists())

    def test_tool_cell_clear_leaves_history(self):
        (self.cell / "stack.txt").write_text(".\n")             # 工具形：stack＝小格本身，沒有 aos history
        self.claude({"hook_event_name": "SessionStart", "source": "clear", "session_id": "new"})
        self.assertEqual(self.read("session.txt"), "new")
        self.assertIn("PLUM-7", self.hist.read_text())

    def test_compact_replaces_history_with_the_summary(self):
        t = self.tmp / "t.jsonl"
        t.write_text(json.dumps({"type": "system", "subtype": "compact_boundary"}) + "\n"
                     + json.dumps({"type": "user", "isCompactSummary": True, "message": {"role": "user", "content": "SUM: PLUM-7"}}) + "\n")
        self.claude({"hook_event_name": "SessionStart", "source": "compact", "session_id": "old", "transcript_path": str(t)})
        rows = [json.loads(l) for l in self.hist.read_text().splitlines()]
        self.assertEqual(rows, [{"role": "user", "content": "[aos] summary: lines 1-3, 3 messages. SUM: PLUM-7"}])
        removed = [json.loads(l) for l in (self.stack / "history_removed.jsonl").read_text().splitlines()]
        self.assertEqual({r["op"] for r in removed}, {"compact"})
        self.assertIsNone(self.read(".history_sum"))
        self.assertEqual(self.read("session.txt"), "old")

    def test_compact_without_summary_leaves_history(self):
        t = self.tmp / "t.jsonl"
        t.write_text("{}\n")
        self.claude({"hook_event_name": "SessionStart", "source": "compact", "session_id": "old", "transcript_path": str(t)})
        self.assertIn("PLUM-7", self.hist.read_text())

    def codex_cell(self, threads):
        cell = self.stack / "codex"
        cell.mkdir()
        (cell / "ws.txt").write_text("../../ws\n")
        (cell / "stack.txt").write_text("..\n")
        (cell / "session.txt").write_text("old\n")
        d = self.tmp / "codex-home" / "sessions" / "2026" / "11" / "12"
        d.mkdir(parents=True)
        for tid, turns in threads.items():
            (d / ("rollout-x-%s.jsonl" % tid)).write_text('{"type": "event_msg", "payload": {"type": "task_complete"}}\n' * turns)
        return cell

    def test_codex_new_thread_clears_history_but_keeps_the_question(self):
        cell = self.codex_cell({"fresh": 1})
        with open(self.hist, "a") as f:
            f.write(json.dumps({"role": "user", "content": "just asked"}) + "\n")
        cli_session.hook_main("codex", str(cell), json.dumps({"type": "agent-turn-complete", "thread-id": "fresh", "last-assistant-message": "NONE"}))
        self.assertEqual((cell / "session.txt").read_text().strip(), "fresh")
        self.assertEqual([json.loads(l) for l in self.hist.read_text().splitlines()], [{"role": "user", "content": "just asked"}])
        self.assertEqual(len((self.stack / "history_removed.jsonl").read_text().splitlines()), 3)

    COMPACTED = {"type": "compacted", "payload": {"message": "", "replacement_history": [
        {"type": "additional_tools", "role": "developer", "tools": []},
        {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "You are Codex"}]},
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context> <cwd>/x</cwd>"}]},
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Remember LIME-4"}]},
        {"type": "function_call", "name": "exec", "arguments": "{}"},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
        {"type": "compaction", "encrypted_content": "xxx"}]}}

    def rollout(self, tid):
        return self.tmp / "codex-home" / "sessions" / "2026" / "11" / "12" / ("rollout-x-%s.jsonl" % tid)

    def notify(self, cell, tid, text="hi"):
        cli_session.hook_main("codex", str(cell), json.dumps({"type": "agent-turn-complete", "thread-id": tid, "last-assistant-message": text}))

    def test_codex_compact_rows_keep_only_the_talk(self):
        self.assertEqual(cli_session.codex_compact_rows(self.COMPACTED["payload"]),
                         [{"role": "user", "content": "Remember LIME-4"}, {"role": "assistant", "content": "ok"}])
        self.assertIsNone(cli_session.codex_compact_rows({"message": ""}))
        self.assertIsNone(cli_session.codex_compact_rows({"replacement_history": [{"type": "compaction"}]}))

    def test_codex_compaction_on_the_same_thread_replaces_history(self):
        cell = self.codex_cell({"old": 3})
        (cell / ".compact_seen").write_text(json.dumps({"thread": "old", "compacted": 0}))
        with open(self.rollout("old"), "a") as f:
            f.write(json.dumps(self.COMPACTED) + "\n")
        with open(self.hist, "a") as f:
            f.write(json.dumps({"role": "user", "content": "just asked"}) + "\n")
        self.notify(cell, "old")
        rows = [json.loads(l) for l in self.hist.read_text().splitlines()]
        self.assertTrue(rows[0]["content"].startswith("[aos] summary: lines 1-3, 3 messages. codex compacted"))
        self.assertEqual(rows[1:], [{"role": "user", "content": "Remember LIME-4"}, {"role": "assistant", "content": "ok"},
                                    {"role": "user", "content": "just asked"}])
        removed = [json.loads(l) for l in (self.stack / "history_removed.jsonl").read_text().splitlines()]
        self.assertEqual({r["op"] for r in removed}, {"compact"})
        self.assertEqual(json.loads((cell / ".compact_seen").read_text()), {"thread": "old", "compacted": 1})
        self.notify(cell, "old")                                 # same count again: nothing more
        self.assertEqual(len(self.hist.read_text().splitlines()), 4)

    def test_codex_compaction_without_baseline_or_unreadable_leaves_history(self):
        cell = self.codex_cell({"old": 3})
        with open(self.rollout("old"), "a") as f:
            f.write(json.dumps(self.COMPACTED) + "\n")
        self.notify(cell, "old")                                 # no .compact_seen yet: only the baseline
        self.assertIn("PLUM-7", self.hist.read_text())
        with open(self.rollout("old"), "a") as f:
            f.write(json.dumps({"type": "compacted", "payload": {"message": ""}}) + "\n")
        self.notify(cell, "old")                                 # compacted again but nothing to read
        self.assertIn("PLUM-7", self.hist.read_text())
        self.assertFalse((self.stack / "history_removed.jsonl").exists())

    def test_codex_resume_to_an_older_thread_keeps_history(self):
        cell = self.codex_cell({"older": 4})
        cli_session.hook_main("codex", str(cell), json.dumps({"type": "agent-turn-complete", "thread-id": "older", "last-assistant-message": "hi"}))
        self.assertEqual((cell / "session.txt").read_text().strip(), "older")
        self.assertIn("PLUM-7", self.hist.read_text())
        self.assertFalse((self.stack / "history_removed.jsonl").exists())

    def test_codex_side_thread_is_ignored(self):
        cell = self.stack / "codex"
        cell.mkdir()
        (cell / "ws.txt").write_text("../../ws\n")
        rollout = self.tmp / "codex-home" / "sessions" / "2026" / "11" / "12"
        rollout.mkdir(parents=True)
        (rollout / "rollout-2026-11-12T13-37-19-real.jsonl").write_text("{}\n")
        note = lambda tid, text: json.dumps({"type": "agent-turn-complete", "thread-id": tid, "last-assistant-message": text})
        cli_session.hook_main("codex", str(cell), note("title", '{"title": "x"}'))   # 旁支：沒存檔
        self.assertFalse((cell / "turns.jsonl").exists())
        self.assertFalse((cell / "session.txt").exists())
        cli_session.hook_main("codex", str(cell), note("real", "ok"))
        self.assertEqual((cell / "session.txt").read_text().strip(), "real")
        self.assertEqual(json.loads((cell / "turns.jsonl").read_text())["text"], "ok")
        self.assertTrue((cell / "transcripts" / "codex-real.jsonl").is_symlink())


if __name__ == "__main__":
    unittest.main()
