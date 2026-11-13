# 用真的 aos-post、aos-exec 與框架站驗證 kernel_gate 工具與它的 tick／hold 兩支 hook；aos-agent 用暫存的假指令頂替（只答 who、記下 hook 指令）。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

GATE = Path(__file__).resolve().parents[1]
PROTO8 = GATE.parents[2]
BINS = [PROTO8 / "impls" / name / "bin" for name in ("aos-post", "aos-exec", "aos-directive")]
FAKE_AGENT = """#!%s
# 暫存的假 aos-agent：ctl who 回測試的 agent，hook 指令只記下來。
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["ctl", "who"]:
    print(json.dumps({"name": "kay", "def": None, "ws": os.environ["AOS_WS"], "stack": os.environ["TEST_AGENT_STACK"]})
          if "--json" in args else "kay")
elif args[:1] == ["hook"]:
    with open(os.environ["TEST_HOOK_LOG"], "a") as stream:
        stream.write(json.dumps(args) + "\\n")
else:
    sys.exit("fake aos-agent: unexpected %%r" %% args)
""" % sys.executable


class KernelGateTest(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get("KERNEL_TEST_TMP", "/tmp")
        self.root = Path(subprocess.check_output(
            ["mktemp", "-d", str(Path(scratch) / "kernel-gate-test.XXXXXX")], text=True).strip())
        self.addCleanup(shutil.rmtree, self.root)
        self.stack = self.root / "kay"
        self.cell = self.stack / "hooks" / "kernel_gate"
        self.requests = self.cell / "requests"
        self.daemon = self.root / "daemon"
        self.ctl = self.daemon / "procs_requests"
        self.sender = self.root / "sender"
        self.queue = self.stack / "queue"
        for folder in (self.stack, self.daemon, self.root / "ws", self.root / "bin"):
            folder.mkdir()
        fake = self.root / "bin" / "aos-agent"
        fake.write_text(FAKE_AGENT)
        fake.chmod(0o755)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
        self.env.update(AOS_DAEMON=str(self.daemon), AOS_WS=str(self.root / "ws"), PYTHONDONTWRITEBYTECODE="1",
                        TEST_AGENT_STACK=str(self.stack), TEST_HOOK_LOG=str(self.root / "hooks.log"),
                        PATH=os.pathsep.join([str(self.root / "bin")] + [str(b) for b in BINS] + [os.environ["PATH"]]))
        for box in (self.ctl, self.sender, self.queue):
            self.post("init", box)

    def post(self, *args, body=None):
        result = subprocess.run(["aos-post", *map(str, args)], input="" if body is None else json.dumps(body),
                                text=True, capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def tool(self, **arguments):
        return subprocess.run([sys.executable, str(GATE / "_entry")], input=json.dumps(arguments), text=True,
                              capture_output=True, env=dict(self.env, AOS_STACK=str(self.stack / "tools" / "kernel_gate")))

    def ok(self, **arguments):
        result = self.tool(**arguments)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def tick(self):
        event = {"event": "on_clock", "hook": "kernel_gate", "stack": str(self.stack), "first": False}
        return subprocess.run([str(GATE / "tick")], input=json.dumps(event), text=True, capture_output=True,
                              env=dict(self.env, AOS_STACK=str(self.cell)))

    def send(self, name, **body):
        return self.post("send", "--reply-to", self.sender, self.requests, name, body=body)

    def names(self, box, slot="new"):
        return sorted(path.name for path in (box / slot).iterdir() if not path.name.startswith("."))

    def notices(self):
        return [json.loads((self.queue / "new" / name / "letter.json").read_text())["body"]
                for name in self.names(self.queue)]

    def answers(self):
        found = {}
        for name in self.names(self.sender):
            letter = json.loads((self.sender / "new" / name / "letter.json").read_text())
            found[letter["in_reply_to"]] = letter["body"]
        return found

    def test_01_on_makes_the_station_and_hooks_it(self):
        out = self.ok(op="on")
        self.assertIn("Requests go to this mailbox: %s" % self.requests, out)
        self.assertIn("the ctl mailbox of your daemon", out)
        cfg = json.loads((self.cell / "kernel.json").read_text())
        self.assertEqual(cfg, {"hooks": {"hold": {"event": "after_verdict", "condition": "pass",
                                                  "handler": str(GATE / "hold")}}})
        self.assertTrue((self.requests / "new").is_dir())
        hook = json.loads((self.root / "hooks.log").read_text().splitlines()[0])
        self.assertEqual(hook[:6], ["hook", "--target", "kay", "add", "--event", "on_clock"])
        self.assertEqual(json.loads(hook[hook.index("--path-json") + 1]), str(GATE / "tick"))
        (self.cell / "kernel.json").write_text(json.dumps(dict(cfg, allowed=["a"])))
        self.assertIn("kept as you left them", self.ok(op="on"))
        self.assertEqual(json.loads((self.cell / "kernel.json").read_text())["allowed"], ["a"])

    def test_02_tick_does_nothing_before_on(self):
        result = self.tick()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.cell.exists())
        self.assertEqual(self.notices(), [])

    def test_03_tick_holds_and_tells_once_with_extra_keys_as_written(self):
        self.ok(op="on")
        self.send("a", procs_added={"logwatch": {"def": "/defs/x"}}, desc="我想看 log，拜託", why={"k": [1, 2]})
        self.send("b", procs_added={"quiet": {}}, queue_wait_ms=600000)
        self.assertEqual(self.tick().returncode, 0)
        notices = self.notices()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["role"], "user")
        text = notices[0]["content"]
        self.assertTrue(text.startswith("[aos] kernel_hold: 2 requests held at your kernel station"), text)
        self.assertIn('- letter a\n    from: ', text)
        self.assertIn('    request: {"procs_added": {"logwatch": {"def": "/defs/x"}}}\n', text)
        self.assertIn('    other keys the sender wrote (nobody checked them): {"desc": "我想看 log，拜託", "why": {"k": [1, 2]}}', text)
        self.assertIn('    other keys the sender wrote (nobody checked them): (none)', text)
        self.assertRegex(text, r"deadline: the sender waits \d+ more seconds")
        self.assertIn("deadline: none", text)
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(len(self.notices()), 1)  # 通知過的不再通知。
        self.send("c", ping=True)
        self.tick()
        self.assertEqual(len(self.notices()), 2)
        self.assertIn("1 request held", self.notices()[1]["content"])
        self.assertIn("- letter a\n", self.ok(op="ls"))
        self.assertEqual(self.names(self.ctl), [])

    def test_04_pass_and_refuse_are_applied_by_the_station_at_once(self):
        self.ok(op="on")
        body = {"procs_added": {"logwatch": {}}, "desc": "x", "more": [1]}
        self.send("a", **body)
        self.send("b", procs_added={"quiet": {}})
        self.tick()
        self.assertIn("passed a: the station forwarded it", self.ok(op="pass", letter="a"))
        self.assertEqual(self.names(self.ctl), ["a"])
        forwarded = json.loads((self.ctl / "new" / "a" / "letter.json").read_text())
        self.assertEqual(forwarded["body"], body)
        self.assertEqual(os.path.realpath(self.ctl / forwarded["reply_to"]), str(self.sender))
        out = self.ok(op="refuse", letter="b", reason="  沒寫用途  ")
        self.assertIn("refused b; the sender got: HoldRefused 沒寫用途", out)
        self.assertEqual(self.answers(), {"b": {"applied": False, "error": {"code": "HoldRefused", "msg": "沒寫用途"}}})
        self.assertIn("no requests held", self.ok(op="ls"))
        result = self.tool(op="pass", letter="a")
        self.assertEqual(result.returncode, 1)
        self.assertIn("kernel_gate: error: LetterMissing no held request a", result.stdout)
        self.assertEqual(self.tool(op="refuse", letter="b").returncode, 1)

    def test_05_pass_after_the_sender_deadline_is_refused_by_the_station(self):
        self.ok(op="on")
        self.send("late", procs_added={"x": {}}, queue_wait_ms=600000)
        self.tick()
        path = self.requests / "cur" / "late" / "letter.json"
        letter = json.loads(path.read_text())
        letter["sent_at"] = "2000-01-01T00:00:00.000Z"
        path.write_text(json.dumps(letter))
        result = self.tool(op="pass", letter="late")
        self.assertEqual(result.returncode, 1)
        self.assertIn("kernel_gate: error: LetterRefused late was not passed on: the station refused it after your pass: SlotMissing held", result.stdout)
        self.assertEqual(self.names(self.ctl), [])
        self.assertEqual(self.answers()["late"]["error"]["code"], "SlotMissing")

    def test_06_rules_in_kernel_json_refuse_without_asking(self):
        self.ok(op="on")
        cfg = json.loads((self.cell / "kernel.json").read_text())
        (self.cell / "kernel.json").write_text(json.dumps(dict(cfg, allowed=["good"])))
        self.send("bad", procs_added={"evil": {}})
        self.send("fine", procs_added={"good": {}})
        self.tick()
        self.assertEqual(self.answers()["bad"]["error"]["code"], "NameUnknown")
        self.assertIn("1 request held", self.notices()[0]["content"])
        self.assertNotIn("letter bad", self.notices()[0]["content"])

    def test_07_off_refuses_what_is_held_and_removes_the_hook(self):
        self.ok(op="on")
        self.send("a", ping=True)
        self.tick()
        self.send("b", ping=True)  # 還沒被站看到的也一起收。
        out = self.ok(op="off")
        self.assertIn("2 held requests were refused", out)
        self.assertEqual({name: body["error"]["code"] for name, body in self.answers().items()},
                         {"a": "HoldRefused", "b": "HoldRefused"})
        self.assertEqual(json.loads((self.root / "hooks.log").read_text().splitlines()[-1]),
                         ["hook", "--target", "kay", "rm", "kernel_gate"])
        self.assertTrue((self.cell / "kernel.json").is_file())

    def test_08_bad_arguments(self):
        for arguments, code in (({}, "ArgumentsBad"), ({"op": "open"}, "OpUnknown"),
                                ({"op": "ls", "letter": "a"}, "ArgumentsBad"), ({"op": "pass"}, "ArgumentsBad")):
            with self.subTest(arguments=arguments):
                result = self.tool(**arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn("kernel_gate: error: %s " % code, result.stdout)

    def test_09_by_hand_without_the_tool(self):
        # 知識庫 aos/kernel.json#/write_your_own 第 3 種：只用 self_hook 掛一支 run、手寫 kernel.json 與一支 hook、表態＝寫一個檔。
        gate = self.root / "ws" / "gate"
        gate.mkdir()
        (gate / "kernel.json").write_text(json.dumps(
            {"hooks": {"ask": {"event": "after_verdict", "condition": "pass", "handler": "ask"}}}))
        (gate / "run").write_text('#!/bin/sh\nexec aos-exec --stack "$AOS_STACK" "$AOS_HOME/lib/aos/kernel" "$(dirname "$0")/kernel.json"\n')
        (gate / "ask").write_text(
            "#!%s\n"
            "# 暫存的測試 hook：留下這封信，並往 agent 的 queue 寄一則通知。\n"
            "import json, os, subprocess, sys\n"
            "event = json.load(sys.stdin)\n"
            "queue = os.path.join(event['stack'], '..', '..', 'queue')\n"
            "note = {'role': 'user', 'content': 'request %%s waits: %%s' %% (event['letter'], json.dumps(event['body']))}\n"
            "subprocess.run(['aos-post', 'send', queue], input=json.dumps(note), text=True, check=True, stdout=subprocess.DEVNULL)\n"
            "print(json.dumps({'verdict': 'hold'}))\n" % sys.executable)
        for name in ("run", "ask"):
            (gate / name).chmod(0o755)
        cell = self.stack / "hooks" / "gate"
        cell.mkdir(parents=True)
        env = dict(self.env, AOS_STACK=str(cell), AOS_HOME=str(PROTO8))

        def round_by_hook():
            result = subprocess.run([str(gate / "run")], text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)

        round_by_hook()
        body = {"procs_added": {"x": {}}, "desc": "please"}
        self.post("send", "--reply-to", self.sender, cell / "requests", "a", body=body)
        round_by_hook()
        round_by_hook()
        self.assertEqual([note["content"] for note in self.notices()], ["request a waits: " + json.dumps(body)])
        self.assertEqual(self.names(self.ctl), [])
        (cell / "decisions").mkdir()
        (cell / "decisions" / "a.json").write_text('{"verdict": "pass"}')
        round_by_hook()
        self.assertEqual(json.loads((self.ctl / "new" / "a" / "letter.json").read_text())["body"], body)


if __name__ == "__main__":
    unittest.main()
