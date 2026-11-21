"""Test aos-agent ctl state (11-10 self-family self_state): the overview (one line per part), picked parts, all, --json, and parts that are not available."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"
PARTS = ["who", "state", "tools", "llm", "system", "hooks", "history", "mailbox", "subagents", "resources", "time"]


def clean_env(**extra):
    return env_helper.clean_env(**extra)


class State(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-state-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json", "history": "history.jsonl"}}))
        (self.defn / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(REPO / "proto8" / "py" / "tools" / "base" / "peek_now_time")}}}))
        (self.defn / "llm.json").write_text(json.dumps({"model": "m1"}))
        (self.defn / "subagents.json").write_text(json.dumps({"max_subagents": 2}))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {
            "bob": {"phase": "paused", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn), "limits": {"memory_max": "1G"}},
            "kid": {"phase": "running", "stack": "procs/kid", "ws": "../ws"}}}))
        (self.stack / "llm.json").write_text(json.dumps({"model": "m2"}))
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m) + "\n" for m in (
            {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "bye"})))
        book = self.stack / "tools" / "subagent"
        book.mkdir(parents=True)
        (book / "subagents.json").write_text(json.dumps([{"name": "kid", "stack": "procs/kid"}]))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self, *args, ok=True):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "state", "--target", "bob", *args],
                           env=clean_env(), capture_output=True, text=True, timeout=120, cwd=self.tmp, stdin=subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_overview_one_line_per_part(self):
        out = self.state().stdout.splitlines()
        self.assertEqual([l.split()[0] for l in out], PARTS)
        row = {l.split()[0]: l.split(None, 1)[1] for l in out}
        self.assertTrue(row["who"].startswith("bob (def %s" % self.defn))
        self.assertIn("1 tools (clock)", row["tools"])
        self.assertIn("model=m2", row["llm"])
        self.assertIn("changed by it: model", row["llm"])
        self.assertIn("3 messages", row["history"])
        self.assertIn("assistant 1, user 2", row["history"])
        self.assertNotIn(" 0 bytes", row["history"])
        self.assertEqual(row["subagents"], "1/2 subagents (kid running)")
        self.assertIn("limits memory_max=1G; no running process", row["resources"])
        self.assertIn("not running", row["time"])
        self.assertTrue(row["hooks"].startswith("not available ("), row["hooks"])   # 沒宣告 hooks
        self.assertTrue(row["system"].startswith("not available ("), row["system"])   # 沒宣告 system
        self.assertIn("0 letters waiting", row["mailbox"])

    def test_picked_parts_and_all(self):
        out = self.state("history", "llm").stdout
        self.assertEqual([l for l in out.splitlines() if l.startswith("== ")], ["== history", "== llm"])
        self.assertIn("3\tuser\tbye", out)
        out = self.state("all").stdout
        self.assertEqual([l[3:] for l in out.splitlines() if l.startswith("== ")], PARTS)

    def test_json(self):
        j = json.loads(self.state("-j").stdout)
        self.assertEqual(list(j), PARTS)
        self.assertEqual(j["history"]["messages"], 3)
        self.assertEqual(j["llm"]["settings"], {"model": "m2"})
        self.assertEqual(j["subagents"]["max_subagents"], 2)
        self.assertEqual(j["hooks"]["available"], False)
        j = json.loads(self.state("--json", "tools").stdout)
        self.assertEqual(list(j), ["tools"])
        self.assertEqual(j["tools"]["names"], ["clock"])

    def run_as(self, env, *args):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "state", "--target", "bob", *args],
                           env=clean_env(**env), capture_output=True, text=True, timeout=120, cwd=self.tmp, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_who_notify_box_only_for_itself(self):   # wf/advices「子 agent 不知道是誰生了它」who 那段（ok-limits 11-14）
        box = str(self.tmp / "mom" / "mailbox")
        j = json.loads(self.run_as({"AOS_STACK": str(self.stack / "tools" / "self_state"), "AOS_NOTIFY_BOX": " %s\n" % box}, "-j", "who"))
        self.assertEqual(j["who"]["notify_box"], box)
        out = self.run_as({"AOS_STACK": str(self.stack), "AOS_NOTIFY_BOX": box}, "who")
        self.assertIn("notify_box " + box, out)
        self.assertIn("not proof of who started you", out)
        for env in ({"AOS_NOTIFY_BOX": box},                                           # 沒有 AOS_STACK：不是它自己在問
                    {"AOS_STACK": str(self.d / "procs" / "kid"), "AOS_NOTIFY_BOX": box},   # 別隻在問 bob
                    {"AOS_STACK": str(self.stack), "AOS_NOTIFY_BOX": "  "}):              # 空白＝沒有
            self.assertIsNone(json.loads(self.run_as(env, "-j", "who"))["who"]["notify_box"], env)
        self.assertIsNone(json.loads(self.state("-j", "who").stdout)["who"]["notify_box"])

    def test_ctl_who_json_notify_box(self):
        box = str(self.tmp / "mom" / "mailbox")
        def who(env, *args):
            p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "who", "--json", *args], env=clean_env(**env),
                               capture_output=True, text=True, timeout=120, cwd=self.tmp, stdin=subprocess.DEVNULL)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        me = {"AOS_STACK": str(self.stack / "tools" / "x"), "AOS_NOTIFY_BOX": box}
        self.assertEqual((who(me)["name"], who(me)["notify_box"]), ("bob", box))
        self.assertIsNone(who(me, "--stack", str(self.d / "procs" / "kid"))["notify_box"])   # 問別隻＝null

    def test_registered_read_from_row_then_launch_envs(self):   # ok-devt-1114 05 定稿 1.3：列 ＞ launch 的 envs ＞ 自己的環境
        box, parent = str(self.tmp / "mom" / "mailbox"), str(self.stack)
        table = json.loads((self.d / "procs_state.json").read_text())
        cell = self.d / "procs" / "kid"                                    # 真的 daemon 記法：launch 指到小格，envs 在小格檔（ok-limits 探測 probe2）
        cell.mkdir(parents=True, exist_ok=True)
        single = {"argv": ["aos-exec", "--", "x"], "envs": {
            "AOS_PARENT_STACK": parent, "AOS_NOTIFY_BOX": " %s " % box, "FAKE_TOKEN": "secret-value-1114"}}
        (cell / "exec.json").write_text(json.dumps({"exec": single}))
        table["procs"]["kid"]["launch"] = {"exec": ["procs/kid/exec.json#/exec"]}
        (self.d / "procs_state.json").write_text(json.dumps(table))
        def run(env, *args):
            p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", *args], env=clean_env(**env),
                               capture_output=True, text=True, timeout=120, cwd=self.tmp, stdin=subprocess.DEVNULL)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("secret-value-1114", p.stdout + p.stderr)   # 別的 envs 一個字都不印
            return p.stdout
        kid = str(self.d / "procs" / "kid")
        j = json.loads(run({}, "who", "--json", "--stack", kid))        # 問別隻也查得到（讀表）
        self.assertEqual((j["name"], j["parent"], j["notify_box"]), ("kid", parent, box))
        out = run({}, "state", "--target", "kid", "who")
        self.assertIn("parent     %s (bob)" % parent, out)               # 文字版附名字
        self.assertIn("(parent and notify_box are what the requester wrote at add time, not proof of who started you)", out)
        j = json.loads(run({}, "state", "--target", "kid", "-j", "who"))["who"]
        self.assertEqual((j["parent"], j["notify_box"]), (parent, box))  # JSON 不附名字
        single["envs"]["AOS_NOTIFY_BOX"] = ""                                   # 明確的空字串＝沒有，不再看自己的環境
        (cell / "loop.json").write_text(json.dumps({"exec": single, "_entry": ["aos-loop", {"$env": "AOS_CF"}]}))
        table["procs"]["kid"]["launch"] = {"exec": ["procs/kid/loop.json#/_entry"]}   # loop 型：指 /_entry，單子在 /exec
        table["procs"]["kid"]["parent"] = None                                  # 列上的欄（第 2 期）優先
        (self.d / "procs_state.json").write_text(json.dumps(table))
        j = json.loads(run({"AOS_STACK": kid, "AOS_NOTIFY_BOX": box, "AOS_PARENT_STACK": parent}, "who", "--json"))
        self.assertEqual((j["name"], j["parent"], j["notify_box"]), ("kid", None, None))
        table["procs"]["kid"]["launch"] = {"exec": ["../def-x"]}                # 沒帶 envs 的列：launch 是定義路徑
        del table["procs"]["kid"]["parent"]
        (self.d / "procs_state.json").write_text(json.dumps(table))
        self.assertEqual(json.loads(run({}, "who", "--json", "--stack", kid))["notify_box"], None)
        j = json.loads(run({"AOS_STACK": kid, "AOS_NOTIFY_BOX": box}, "who", "--json"))   # 自己的環境兜底
        self.assertEqual((j["parent"], j["notify_box"]), (None, box))
        table["procs"]["kid"]["launch"] = {"exec": ["procs/kid/gone.json#/exec"]}   # 指標指到讀不到的檔＝null
        (self.d / "procs_state.json").write_text(json.dumps(table))
        self.assertEqual(json.loads(run({}, "who", "--json", "--stack", kid))["notify_box"], None)

    def test_hooks_with_one_hook(self):   # 11-10 最後一輪：hook 鍵改名 event 後 part_hooks 還讀 "on"，有 hook 就 KeyError
        iface = json.loads((self.defn / "interfaces.json").read_text())
        iface["hookeds"] = "hookeds.json"
        (self.defn / "interfaces.json").write_text(json.dumps(iface))
        (self.defn / "hookeds.json").write_text(json.dumps({"logger": {"event": "after_tool", "handler": "/bin/true"}}))
        row = {l.split()[0]: l.split(None, 1)[1] for l in self.state().stdout.splitlines()}
        self.assertEqual(row["hooks"], "1 hooks (logger on after_tool)")
        j = json.loads(self.state("-j", "hooks").stdout)
        self.assertEqual(j["hooks"]["hooks"][0]["event"], "after_tool")

    def test_hooks_with_new_events(self):   # 11-11 clock-hook：新事件與 on_clock 的鍵，part_hooks 不崩
        iface = json.loads((self.defn / "interfaces.json").read_text())
        iface["hookeds"] = "hookeds.json"
        (self.defn / "interfaces.json").write_text(json.dumps(iface))
        (self.defn / "hookeds.json").write_text(json.dumps({"description": "test",
            "timer": {"event": "on_clock", "every_ms": 300000, "handler": "/bin/true"},
            "up": {"event": "after_start", "handler": "/bin/true"}}))
        row = {l.split()[0]: l.split(None, 1)[1] for l in self.state().stdout.splitlines()}
        self.assertEqual(row["hooks"], "2 hooks (timer on on_clock, up on after_start)")
        j = json.loads(self.state("-j", "hooks").stdout)
        self.assertEqual([h["event"] for h in j["hooks"]["hooks"]], ["on_clock", "after_start"])

    def test_unknown_part(self):
        p = self.state("bogus", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("aos-agent: error: ArgumentsBad unknown part bogus", p.stderr)


if __name__ == "__main__":
    unittest.main()
