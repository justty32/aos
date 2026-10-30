"""test_dan_q - 跑 demo/agent-dan-q（agent-dan 搬到 queue 的版本，10-30 eca 第 8 步）：aos-say 投信、aos-exec 跑到 queue 空收工、
aos-listen 拿回答；壞信丟掉；loop 的 ctl 窗在 think 與 act 之間暫停、改 system.txt、放行後照改過的走（場景二）。

fsm agent（aos-loop 一次跑一格 fsm），只做射後不理（queue 空 idle 退 10、loop 收工）；停著等的 fsm agent 等方向題 1。
舊協議的 agent-dan 不動（它的測試在 test_dan.py）。設計：proto8/thinking/2026-10-30-eca.md、2026-10-30-agent-lifecycle.md。"""
import json, os, re, shutil, subprocess, tempfile, threading, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, path_with  # noqa: E402
from test_dan import FakeBrain, call, tool_reply, answer  # noqa: E402
DANQ = ROOT / "demo" / "agent-dan-q"
HUMAN = ROOT / "extras" / "human" / "bin"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CD", "AOS_CF", "AOS_CO")


class HookList(list):
    """FakeBrain 的劇本：每被拿走一項就叫 hook（回答送出去之前）。"""

    def __init__(self, items, hook):
        super().__init__(items)
        self.hook = hook

    def pop(self, i=-1):
        item = super().pop(i)
        self.hook(len(self))
        return item


class DanQ(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dan-q-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with(e.get("PATH", ""))
        e.update(extra or {})
        return e

    def copy(self):
        """改得動的複本（場景二要改 system.txt）：tools.json 手寫 ../../lib/base/…，所以複本放在 <tmp>/demo/ 底下、<tmp>/lib 指回 lib。"""
        os.symlink(ROOT / "lib", self.tmp / "lib")
        d = self.tmp / "demo" / "agent-dan-q"
        shutil.copytree(DANQ, d, ignore=shutil.ignore_patterns("__pycache__"))
        return d

    def say(self, text):
        r = subprocess.run([str(HUMAN / "aos-say"), "--ws", str(self.ws), text], capture_output=True, text=True,
                           env=self.env(), stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, *args):
        return subprocess.run([str(HUMAN / "aos-listen"), "--ws", str(self.ws)] + list(args), capture_output=True,
                              text=True, env=self.env(), stdin=subprocess.DEVNULL, timeout=60)

    def dan(self, agent=DANQ, url=None):
        return subprocess.run([EXEC, "--ws", str(self.ws), str(agent)], capture_output=True, text=True,
                              env=self.env({"AOS_BRAIN_URL": url} if url else {}), stdin=subprocess.DEVNULL, timeout=60)

    def history(self):
        return [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines() if l.strip()]

    def states(self):
        return [json.loads(l)["state"] for l in (self.stack / "trace.jsonl").read_text().splitlines()]

    def stage(self, s):
        d = self.stack / "queue" / s
        return sorted(n for n in os.listdir(d) if not n.startswith(".")) if d.exists() else []

    def test_template_shape(self):
        """_entry、loop.json 是 JSON（不給 +x，複製時不用管執行位元）；loop.json 開 ctl／state 窗；tools.json 指 lib/base。"""
        self.assertEqual(json.loads((DANQ / "_entry").read_text()), ["aos-loop", "loop.json"])
        self.assertFalse(os.stat(DANQ / "_entry").st_mode & 0o111)
        loop = json.loads((DANQ / "loop.json").read_text())
        self.assertEqual((loop["exec"], loop["ctl"], loop["state"]), ("fsm.json", "ctl.json", "state.json"))
        tools = json.loads((DANQ / "tools.json").read_text())["tools"]
        for name, t in tools.items():
            self.assertEqual((DANQ / t["path"]).resolve(), (ROOT / "lib" / "base" / name).resolve())

    def test_say_run_listen(self):
        """假腦：say 一句 → aos-exec 跑到 queue 空收工（退 0）→ listen 拿到「FAKE ANSWER …（clock said …）」；
        history 四則、信收掉、current.txt 清掉、工作區只長 .stack、state 窗 done、trace 照 fsm 一格一行。"""
        sig = self.say("現在幾點？")
        r = self.dan()
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.listen("--timeout", "10", sig)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ）\n$")
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertFalse((self.stack / "current.txt").exists())
        self.assertEqual(sorted(os.listdir(self.ws)), [".stack"])
        self.assertEqual(json.loads((self.stack / "state.json").read_text())["phase"], "done")
        self.assertEqual(self.states(), ["idle", "think", "act", "idle", "think", "act", "idle"])

    def test_two_letters_and_bad_letter(self):
        """排著的信一次答完（照序號）；壞信（body 不是 user 的非空字串）丟掉、不問腦。"""
        post = shutil.which("aos-post", path=self.env()["PATH"])
        first = self.say("第一句")
        subprocess.run([post, "send", "--ordered", str(self.stack / "queue")], input='{"text": "壞信"}',
                       capture_output=True, text=True, env=self.env(), check=True)
        second = self.say("第二句")
        r = self.dan()
        self.assertEqual(r.returncode, 0, r.stderr)
        users = [m["content"] for m in self.history() if m["role"] == "user"]
        self.assertEqual(users, ["第一句", "第二句"])
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertIn("第二句", self.listen("--timeout", "10", second).stdout)
        self.assertEqual(self.listen("--timeout", "10", first).returncode, 0)

    def test_pause_between_think_and_act(self):
        """場景二：think 問完腦（送回答之前就寫 paused）→ loop 停在 think 與 act 之間、信還在 cur/ →
        改 system.txt → 放行 → act 跑工具、下一次 think 帶的是改過的 system。"""
        agent = self.copy()
        sig = self.say("17*23 是多少？")

        def hook(left):
            if left == 1:                                        # 第一次問腦（回 tool_calls）
                (self.stack / "ctl.json").write_text('{"paused": true}')

        b = FakeBrain([])
        self.addCleanup(b.close)
        b.script = HookList([tool_reply(call("c1", "math", {"expr": "17*23"})), answer("391")], hook)
        p = subprocess.Popen([EXEC, "--ws", str(self.ws), str(agent)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             text=True, env=self.env({"AOS_BRAIN_URL": b.url}))
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        end = time.time() + 20
        while time.time() < end:
            try:
                if json.loads((self.stack / "state.json").read_text() or "{}").get("phase") == "paused":
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        else:
            self.fail("loop 沒停在 paused")
        self.assertEqual(self.states(), ["idle", "think"])                # 停在 think 之後、act 之前
        self.assertEqual(self.stage("cur"), [sig])
        self.assertIn("phase paused", self.listen("--status").stdout)
        (agent / "system.txt").write_text("改過的 system：答案只給數字。\n")
        (self.stack / "ctl.json").write_text('{"paused": false}')
        self.assertEqual(p.wait(timeout=30), 0, p.stderr.read())
        self.assertEqual(self.listen("--timeout", "10", sig).stdout, "391\n")
        first, second = b.requests
        self.assertEqual(first["messages"][0]["content"], (DANQ / "system.txt").read_text())
        self.assertEqual(second["messages"][0]["content"], "改過的 system：答案只給數字。\n")
        self.assertEqual(self.states(), ["idle", "think", "act", "idle", "think", "act", "idle"])


if __name__ == "__main__":
    unittest.main()
