"""範本預設的 mail_notify hook 實跑（真 root daemon＋時鐘、假腦）：寄一封＝間隔內收到一則 [aos] new_mail；連寄三封只多一則；self_hook 改間隔照新間隔；self_hook rm＝不再收到。"""
# 11-11 mail-notify（使用者「用on_clock」「預設開」「合成一句」）。用這份 clone 的 impls／cmd（PATH 最前）、py／lib（PYTHONPATH）。
# 跑法：python3 test_mail_notify_daemon.py [-v]；KEEP=1 留下試驗資料夾。約一分鐘（範本間隔 10 秒、根的時鐘 1 秒一格）。
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[3]
NOTE = "[aos] new_mail: "


class MailNotifyDaemon(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="aos-mailnotify-")))
        if not os.environ.get("KEEP"):
            self.addCleanup(shutil.rmtree, self.root, True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(p) for p in sorted(PROTO.glob("impls/*/bin"))] + [str(p) for p in sorted(PROTO.glob("cmd/*/bin"))]
        kernel = self.root / "kernel"
        kernel.mkdir()
        self.env = dict(env, AOS_HOME=str(PROTO), PATH=os.pathsep.join(bins + [env["PATH"]]), AOS_LLM_KERNEL=str(kernel),
                        PYTHONPATH=os.pathsep.join([str(PROTO / "py"), str(PROTO / "lib")]), PYTHONDONTWRITEBYTECODE="1")
        (self.root / "kernel.json").write_text(json.dumps({"exec": str(PROTO / "lib/base/llm_fake"), "endpoint": "fake",
                                                           "endpoints": {"fake": {}}}))
        (self.root / "kernel_daemon.json").write_text(json.dumps({"interval_ms": 10, "exec": {"argv": [
            str(PROTO / "impls/aos-llm-kernel/bin/aos-llm-kernel"), str(self.root / "kernel.json")]}}))
        shutil.copytree(PROTO / "templates" / "daemon-root", self.root / "defs")
        bob = self.root / "defs" / "bob"
        shutil.copytree(PROTO / "templates" / "agent-fsm", bob, ignore=shutil.ignore_patterns("__pycache__"))
        (bob / "llm.json").write_text(json.dumps({"model": "fake"}))
        (bob / "tools.json").write_text(json.dumps({"tools": {}}))   # 假腦看到工具會先叫一支；這裡只看 history 裡的提醒
        self.err = open(self.root / "root.err", "w")
        self.addCleanup(self.err.close)
        self.kernel = subprocess.Popen(["aos-daemon", str(self.root / "kernel_daemon.json")], cwd=self.root,
                                       env=dict(self.env, AOS_STACK=str(kernel)), stdout=self.err, stderr=self.err,
                                       start_new_session=True)
        self.daemon = subprocess.Popen(["aos-exec", "--stack", "stacks/root", "defs"], cwd=self.root, env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=self.err, start_new_session=True)
        self.addCleanup(self.close)
        self.until(lambda: (self.root / "stacks" / "root" / "clock").exists(), 20)

    def close(self):
        if self.daemon.poll() is None:
            subprocess.run(["aos-daemon-ctl", "-d", "stacks/root", "shutdown"], cwd=self.root, env=self.env,
                           capture_output=True, timeout=60)
            try:
                self.daemon.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.daemon.pid, signal.SIGKILL)
        for p in (self.daemon, self.kernel):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)

    def until(self, fn, secs=30):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            got = fn()
            if got:
                return got
            time.sleep(.2)
        raise AssertionError("timed out; notes %s; root.err: %s" % (self.notes(), (self.root / "root.err").read_text()[-2000:]))

    def run_ok(self, argv, stdin=None, env=None):
        r = subprocess.run(argv, cwd=self.root, env=env or self.env, input=stdin, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def notes(self):
        h = self.root / "stacks" / "root" / "procs" / "bob" / "history.jsonl"
        rows = [json.loads(l) for l in h.read_text().splitlines()] if h.exists() else []
        return [m["content"] for m in rows if m.get("role") == "user" and str(m.get("content", "")).startswith(NOTE)]

    def send(self, sender):
        self.run_ok(["aos-mailbox", "send", "--to", "bob", "-d", "stacks/root", "--from", sender, "--status", "REQUEST",
                     "--title", "hello from %s" % sender, "Please read me."])

    def self_hook(self, args):
        """bob 自己的 self_hook 工具（同腦叫：aos-exec 起、$AOS_STACK＝它的工具小格、$AOS_DAEMON＝根）。"""
        cell = self.root / "stacks" / "root" / "procs" / "bob" / "tools" / "self_hook"
        env = dict(self.env, AOS_DAEMON=str(self.root / "stacks" / "root"), AOS_WS=str(self.root))
        return self.run_ok(["aos-exec", "--stack", str(cell) + "/", str(PROTO / "lib/agent/self_hook")], json.dumps(args), env)

    def test_notify_batch_interval_and_off(self):
        self.run_ok(["aos-agent", "-d", "stacks/root", "ctl", "add", "-w", ".", "defs/bob"])
        stack = self.root / "stacks" / "root" / "procs" / "bob"
        self.until(lambda: (stack / "hooks" / "mail_notify" / "on_clock.json").exists())   # 起來第一次已看過（空信箱：安靜）
        self.assertEqual(self.notes(), [])
        self.send("amy")
        t0 = time.monotonic()
        self.until(lambda: len(self.notes()) == 1, 25)
        self.assertLess(time.monotonic() - t0, 16)                                           # 10 秒間隔（＋一格餘裕）內
        self.assertTrue(self.notes()[0].startswith("[aos] new_mail: 1 new letter from amy."), self.notes())
        for _ in range(3):
            self.send("cody")
        self.until(lambda: len(self.notes()) == 2, 25)
        time.sleep(12)                                                                       # 再一個間隔：不重複
        self.assertEqual(len(self.notes()), 2, self.notes())
        self.assertTrue(self.notes()[1].startswith("[aos] new_mail: 3 new letters from cody."), self.notes())
        # 改間隔（免打擾的反面：改快）：self_hook add replace 同名
        self.self_hook({"op": "add", "name": "mail_notify", "event": "on_clock", "every_ms": 2000, "replace": True,
                        "path_json": {"$env": "AOS_HOME", "$path": "/lib/agent/mail_notify"}, "on_error": "continue",
                        "timeout_ms": 10000})
        time.sleep(3)
        self.send("dan")
        t0 = time.monotonic()
        self.until(lambda: len(self.notes()) == 3, 15)
        self.assertLess(time.monotonic() - t0, 6)
        # 免打擾：self_hook rm
        self.self_hook({"op": "rm", "name": "mail_notify"})
        time.sleep(2)
        self.send("eve")
        time.sleep(13)
        self.assertEqual(len(self.notes()), 3, self.notes())
        self.assertNotIn("Please read me", " ".join(self.notes()))


if __name__ == "__main__":
    unittest.main()
