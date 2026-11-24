# 驗延後關畫面的到期單、假 tmux 排程、token 與本機身分、小格鎖及 hook 事件入口。
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.agentlib import cli_cell, cli_linger as linger, hooks

FAKE = '''#!/usr/bin/env python3
# 記錄 tmux 參數並模擬畫面身分與關閉，絕不連真 server。
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["TMUX_LOG"], "a") as out:
    out.write(json.dumps(args) + "\\n")
if "has-session" in args:
    sys.exit(0 if os.environ.get("SCREEN_ALIVE", "1") == "1" else 1)
if "list-sessions" in args:
    print("cli " + os.environ.get("SCREEN_ID", "123 456"))
if "run-shell" in args:
    sys.exit(int(os.environ.get("SCHEDULE_RC", "0")))
if "kill-server" in args:
    order = pathlib.Path(os.environ["ORDER"])
    pathlib.Path(os.environ["CLOSE_CHECK"]).write_text(str(order.exists()))
'''


class Linger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / "stack"
        self.cell = cli_cell.Cell(str(self.stack / "claude"))
        self.definition = self.root / "definition"
        self.definition.mkdir()
        (self.definition / "cli.json").write_text('{"screen_close_after_s": 600}')
        self.cell.write("tool.txt", os.path.relpath(self.definition, self.cell.path))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "tmux").write_text(FAKE)
        (self.bin / "tmux").chmod(0o755)
        self.log = self.root / "tmux.log"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(PATH=str(self.bin) + ":" + env["PATH"], XDG_RUNTIME_DIR=str(self.root), TMUX_LOG=str(self.log),
                   ORDER=self.cell.file(linger.ORDER), CLOSE_CHECK=str(self.root / "closed"))
        self.scope = contextlib.ExitStack()
        self.addCleanup(self.scope.close)
        self.scope.enter_context(patch.dict(os.environ, env, clear=True))
        self.sock = Path(self.cell.sock(make=True))
        self.sock.touch()
        self.scope.enter_context(patch.object(signal, "signal"))

    def calls(self, command):
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [json.loads(line)[2:] for line in lines if command in json.loads(line)[2:]]

    def order(self, cell=None):
        return linger.read((cell or self.cell).file(linger.ORDER))

    def arm(self, delay=600):
        (self.definition / "cli.json").write_text(json.dumps({"screen_close_after_s": delay}))
        linger.arm(str(self.stack))
        return self.order()

    def reap(self, doc=None):
        linger.reap(str(self.stack), "claude", (doc or self.order())["token"])

    def identity(self):
        text = Path("/proc/self/stat").read_text()
        return {"pid": os.getpid(), "started_at_ticks": int(text[text.rindex(")") + 1:].split()[19]),
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}

    def state(self, value):
        (self.stack / "state.json").write_text(json.dumps(value))

    def test_arm_fields_and_background_command(self):
        doc = self.arm()
        self.assertEqual(set(doc), {"token", "by", "down_at", "due_at", "delay_s", "loop", "screen", "retries"})
        self.assertEqual(doc["due_at"] - doc["down_at"], 600)
        self.assertEqual(doc["screen"], {"pid": 123, "created": 456})
        call = self.calls("run-shell")[0]
        self.assertEqual(call[:4], ["run-shell", "-b", "-d", "600"])
        self.assertTrue(call[4].endswith(" </dev/null >/dev/null 2>&1 &"))
        words = shlex.split(call[4])
        self.assertEqual(words[:6], [sys.executable, linger.ENTRY, "reap", str(self.stack), "claude", doc["token"]])

    def test_no_screen_clears_stale_order(self):
        linger.put(self.cell, {"token": "stale"})
        os.environ["SCREEN_ALIVE"] = "0"
        linger.arm(str(self.stack))
        self.assertFalse(self.order())
        self.assertEqual(self.calls("run-shell"), [])

    def test_zero_uses_reap_and_closes_before_deleting_order(self):
        self.arm(0)
        self.assertFalse(self.order())
        self.assertEqual(self.calls("run-shell"), [])
        self.assertEqual(len(self.calls("kill-server")), 1)
        self.assertEqual((self.root / "closed").read_text(), "True")
        self.assertFalse(self.sock.exists())

    def test_zero_busy_lock_retries(self):
        lock, ok = self.cell.lock()
        self.assertTrue(ok)
        with lock:
            self.arm(0)
        self.assertEqual(self.order()["retries"], 1)
        self.assertEqual(self.calls("run-shell")[0][3], "30")
        self.assertEqual(self.calls("kill-server"), [])

    def test_delay_and_fallback_values(self):
        self.arm(90)
        self.assertEqual(self.calls("run-shell")[-1][3], "90")
        for value in (-1, 1.5, "600", True):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()) as err:
                self.arm(value)
                self.assertIn("using 600 s", err.getvalue())
                self.assertEqual(self.order()["delay_s"], 600)
        for mode in ("bad-json", "missing-tool", "missing-cfg"):
            if mode == "bad-json":
                (self.definition / "cli.json").write_text("not json")
            elif mode == "missing-tool":
                self.cell.write("tool.txt", "")
            else:
                self.cell.write("tool.txt", "missing")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                linger.arm(str(self.stack))
            self.assertIn("using 600 s", err.getvalue())

    def test_rearm_replaces_token_cancel_both_kinds(self):
        first = self.arm()
        second = self.arm()
        self.assertNotEqual(first["token"], second["token"])
        codex = cli_cell.Cell(str(self.stack / "codex"))
        linger.put(codex, first)
        linger.cancel(str(self.stack))
        linger.cancel(str(self.stack))
        self.assertFalse(self.order())
        self.assertFalse(self.order(codex))

    def test_missing_or_wrong_token_does_nothing(self):
        linger.reap(str(self.stack), "claude", "absent")
        doc = self.arm()
        linger.reap(str(self.stack), "claude", "wrong")
        self.assertEqual(self.order(), doc)
        self.assertEqual(self.calls("kill-server"), [])

    def test_reopened_screen_obsoletes_order(self):
        doc = self.arm()
        os.environ["SCREEN_ID"] = "789 999"
        self.reap(doc)
        self.assertFalse(self.order())
        self.assertEqual(self.calls("kill-server"), [])

    def test_new_live_loop_cancels_even_when_locked(self):
        doc = self.arm()
        self.state(self.identity())
        lock, _ = self.cell.lock()
        with lock:
            self.reap(doc)
        self.assertEqual(self.order(), doc)
        self.assertEqual(len(self.calls("run-shell")), 1)
        self.reap(doc)
        self.assertFalse(self.order())
        self.assertEqual(self.calls("kill-server"), [])

    def test_same_live_stopping_loop_can_close(self):
        self.state(self.identity())
        self.reap(self.arm())
        self.assertEqual(len(self.calls("kill-server")), 1)

    def test_dead_or_mismatched_loop_can_close(self):
        for key, value in (("pid", 2147483647), ("started_at_ticks", -1), ("boot_id", "another-boot")):
            with self.subTest(key=key):
                self.sock.touch()
                doc = self.arm()
                identity = self.identity()
                identity[key] = value
                self.state(identity)
                self.reap(doc)
                self.assertFalse(self.order())
        self.sock.touch()
        self.state({})
        self.reap(self.arm())
        self.assertFalse(self.order())

    def test_unverifiable_live_pid_keeps_order_and_warns(self):
        for key in ("started_at_ticks", "boot_id"):
            doc = self.arm()
            identity = self.identity()
            identity.pop(key)
            self.state(identity)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.reap(doc)
            self.assertIn("cannot be verified", err.getvalue())
            self.assertEqual(self.order(), doc)
        self.assertEqual(self.calls("kill-server"), [])

    def test_busy_lock_retries_ten_times_then_stops(self):
        doc = self.arm()
        lock, _ = self.cell.lock()
        with lock:
            for _ in range(11):
                self.reap(doc)
        self.assertEqual(self.order()["retries"], 10)
        self.assertEqual(len(self.calls("run-shell")), 11)
        self.assertEqual(self.calls("kill-server"), [])

    def test_busy_lock_does_not_recreate_missing_or_replace_new_order(self):
        lock, _ = self.cell.lock()
        with lock:
            linger.reap(str(self.stack), "claude", "absent")
            doc = self.arm()
            linger.reap(str(self.stack), "claude", "wrong")
        self.assertEqual(self.order(), doc)
        self.assertEqual(len(self.calls("run-shell")), 1)

    def test_reap_twice_only_closes_once(self):
        doc = self.arm()
        self.reap(doc)
        self.reap(doc)
        self.assertEqual(len(self.calls("kill-server")), 1)

    def test_close_does_not_delete_new_token(self):
        doc = self.arm()
        with patch.object(cli_cell, "close", side_effect=lambda cell: linger.put(cell, dict(doc, token="new"))):
            self.reap(doc)
        self.assertEqual(self.order()["token"], "new")

    def test_codex_arm_reap(self):
        self.cell = cli_cell.Cell(str(self.stack / "codex"))
        self.cell.write("tool.txt", os.path.relpath(self.definition, self.cell.path))
        Path(self.cell.sock(make=True)).touch()
        linger.arm(str(self.stack))
        doc = self.order()
        self.assertIn("codex", self.calls("run-shell")[-1][-1])
        linger.reap(str(self.stack), "codex", doc["token"])
        self.assertFalse(self.order())

    def test_schedule_failure_warns_and_keeps_order(self):
        os.environ["SCHEDULE_RC"] = "1"
        with contextlib.redirect_stderr(io.StringIO()) as err:
            doc = self.arm()
        self.assertIn("cannot schedule", err.getvalue())
        self.assertEqual(self.order(), doc)

    def test_hook_entry_uses_event_stack_and_null_disables_stop(self):
        proto = LIB.parent
        env = dict(os.environ, AOS_STACK=str(self.root / "handler-cell"))
        event = {"event": "after_start", "stack": str(self.stack)}
        self.arm()
        result = subprocess.run([sys.executable, linger.ENTRY], input=json.dumps(event), env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.order())
        event["event"] = "after_stop"
        result = subprocess.run([sys.executable, linger.ENTRY], input=json.dumps(event), env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.order())
        linger.cancel(str(self.stack))
        (self.stack / "hookeds.json").write_text(json.dumps({"screen_linger_stop": None}))   # the stack copy: null turns it off
        defn = str(proto / "templates/agents/eca-claude")
        entries = hooks.load(defn, str(self.stack))
        self.assertNotIn("screen_linger_stop", entries)
        hooks.fire("after_stop", {}, entries, str(self.stack))
        self.assertFalse(self.order())
        result = subprocess.run([sys.executable, linger.ENTRY], input="not JSON", env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)          # as a hook a bad event only warns: the loop goes on
        self.assertTrue(result.stderr.startswith("screen_linger: warning: "), result.stderr)


if __name__ == "__main__":
    unittest.main()
