"""Test subagent against a fake aos-agent with a table: argv per op, the record and its reconciliation, quota, rm without purge, subagent account copies, and tools/llm/history/hook/system aimed at the subagent."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
LIB = Path(__file__).resolve().parents[4]
NAME = TOOL.parent.name

# 假 aos-agent：表存在 FAKE_TABLE（[{name, stack}]）；ctl add／rm 改表，ctl who 照 $AOS_STACK 找包住它的那列。
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.getcwd(), os.environ.get("AOS_STACK")] + argv) + "\n")
tp = os.environ["FAKE_TABLE"]
table = json.load(open(tp)) if os.path.exists(tp) else []
def save():
    json.dump(table, open(tp, "w"))
fail = os.environ.get("FAKE_FAIL", "")
if fail and fail in " ".join(argv):
    sys.stderr.write("aos-agent: error: PhaseBad kid is sleeping; use wake\n")
    sys.exit(1)
if argv[:2] == ["ctl", "ls"] and "-l" in argv:
    for r in table:
        print("\t".join([r["name"], "running", "-", "-", "-", "2", "0", "-", "-"]))
elif argv[:2] == ["ctl", "ls"]:
    print(json.dumps(table))
elif argv[:2] == ["ctl", "who"]:
    s = os.environ["AOS_STACK"]
    rows = sorted((r for r in table if s == r["stack"] or s.startswith(r["stack"] + "/")), key=lambda r: -len(r["stack"]))
    if not rows:
        sys.stderr.write("aos-agent: error: InstanceMissing no listed agent owns %s\n" % s)
        sys.exit(1)
    r = rows[0]
    print(json.dumps({"name": r["name"], "stack": r["stack"], "ws": None, "def": os.environ.get("FAKE_DEF"),
                      "daemon": os.environ["AOS_DAEMON"]}) if "--json" in argv else r["name"])
elif argv[:2] == ["ctl", "add"]:
    name = argv[argv.index("--name") + 1] if "--name" in argv else os.path.basename(argv[-1])
    if os.environ.get("FAKE_QUEUE"):
        print("queued %s at position 1 (letter L1; applied when a slot frees)" % name)
        sys.exit(0)
    if "--stack" in argv:
        stack = argv[argv.index("--stack") + 1]
    elif "--stack-json" in argv:                        # only the {"$env": "AOS_DAEMON", "$path": ...} directive the tool writes
        stack = os.path.join(os.environ["AOS_DAEMON"], json.loads(argv[argv.index("--stack-json") + 1])["$path"])
    else:
        stack = os.path.join(os.environ["AOS_DAEMON"], "procs", name)
    os.makedirs(stack, exist_ok=True)
    table.append({"name": name, "stack": stack})
    save()
    print(stack)
elif argv[:2] == ["ctl", "rm"]:
    table[:] = [r for r in table if r["name"] != argv[-1]]
    save()
    print("removed " + argv[-1])
elif argv[:1] == ["say"]:
    sys.stdin.read()
    print("letter-1")
elif argv[:1] == ["listen"]:
    print("the answer")
elif argv[:1] == ["ask"]:
    sys.stdin.read()
    print("the answer")
else:
    print("ok " + " ".join(argv))
'''


class Subagent(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="subagent-"))
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.daemon = self.tmp / "d"
        self.mom = self.daemon / "procs" / "mom"
        self.cell = self.mom / "tools" / NAME
        self.cell.mkdir(parents=True)
        self.defdir = self.tmp / "def"
        self.defdir.mkdir()
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        self.log, self.table = self.tmp / "log", self.tmp / "table.json"
        self.table.write_text(json.dumps([{"name": "mom", "stack": str(self.mom)}]))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH="%s:%s" % (bin_, os.environ["PATH"]), AOS_WS=str(self.ws), AOS_DAEMON=str(self.daemon),
                        AOS_STACK=str(self.cell), FAKE_LOG=str(self.log), FAKE_TABLE=str(self.table), FAKE_DEF=str(self.defdir),
                        PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, tool=TOOL, **env):
        return subprocess.run([str(tool)], input=json.dumps(args), capture_output=True, text=True, env=dict(self.env, **env), timeout=60)

    def ok(self, args, **env):
        r = self.run_tool(args, **env)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r.stdout

    def calls(self, first=None):
        rows = [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []
        return [c[2:] for c in rows if first is None or c[2] == first]

    def record(self):
        return json.loads((self.cell / "subagents.json").read_text())

    def test_broken_record_names_a_path_the_caller_can_open(self):
        """11-13 fx-2：帳壞掉的錯誤行印叫方照自己的 $AOS_STACK 找得到的路徑（aos-tools call 給 AOS_STACK_IN_CALLER），不印絕對路徑；
        直接被叫（沒給那個變數）＝從自己小格算。"""
        (self.cell / "subagents.json").write_text('{"not": "a list"}')
        r = self.run_tool({"op": "ls"}, AOS_STACK_IN_CALLER="tools/" + NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "%s: error: ReadFailed $AOS_STACK/tools/%s/subagents.json is not a JSON array of {name, stack}" % (NAME, NAME))
        self.assertTrue((self.mom / "tools" / NAME / "subagents.json").is_file())
        self.assertNotIn(str(self.tmp), r.stdout + r.stderr)
        r = self.run_tool({"op": "ls"})
        self.assertEqual(r.stdout.strip(), "%s: error: ReadFailed $AOS_STACK/subagents.json is not a JSON array of {name, stack}" % NAME)

    def test_add_records_and_argv(self):
        out = self.ok({"op": "add", "def": "defs/helper", "name": "kid", "ws": "kid", "limits": {"mem_mb": 64}, "timeout_s": 5})
        self.assertIn("added kid (stack %s); subagents 1/4" % (self.daemon / "procs" / "kid"), out)
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "add", "--stack-json", '{"$env": "AOS_DAEMON", "$path": "procs/%s"}' % "kid", "--name", "kid", "--ws", "kid", "--limits", '{"mem_mb": 64}',
                                                 "--envs", "AOS_NOTIFY_BOX=%s" % (self.mom / "mailbox"),
                                                 "--timeout-s", "5", "--", "defs/helper"])
        self.assertTrue((self.ws / "kid").is_dir())
        self.assertEqual(self.record(), [{"name": "kid", "stack": "procs/kid"}])   # relative to the daemon stack (ws-stack-1122-abs)
        self.ok({"op": "add", "def": "defs/kid2"})           # name defaults to the folder name, like ctl add
        self.assertEqual([k["name"] for k in self.record()], ["kid", "kid2"])
        self.assertEqual(self.ok({"op": "ls"}), "kid\t-\t-\t-\t-\nkid2\t-\t-\t-\t-\nsubagents 2/4\n")   # short lines, not mom
        listed = json.loads(self.ok({"op": "ls", "json": True}))
        self.assertEqual([r["name"] for r in listed["subagents"]], ["kid", "kid2"])   # not mom
        self.assertEqual(listed["max_subagents"], 4)
        self.assertEqual(self.ok({"op": "ls", "long": True}),        # long = ctl ls -l lines of mine, as text
                         "kid\trunning\t-\t-\t-\t2\t0\t-\t-\nkid2\trunning\t-\t-\t-\t2\t0\t-\t-\nsubagents 2/4\n")
        self.assertEqual(json.loads(self.ok({"op": "ls", "long": True, "json": True}))["max_subagents"], 4)   # json wins

    def test_record_follows_a_moved_tree(self):
        """ws-stack-1122-abs：帳上存相對 daemon stack 的寫法；整棵改名（換家目錄、換台）後表與環境都換成新位置，照樣認得、子的工具小格也在新位置。"""
        self.ok({"op": "add", "def": "d", "name": "kid"})
        moved = self.tmp / "moved"
        self.daemon.rename(moved)
        self.table.write_text(json.dumps([{"name": n, "stack": str(moved / "procs" / n)} for n in ("mom", "kid")]))
        cell = moved / "procs" / "mom" / "tools" / NAME
        env = dict(AOS_DAEMON=str(moved), AOS_STACK=str(cell))
        self.assertEqual(self.ok({"op": "ls"}, **env), "kid\t-\t-\t-\t-\nsubagents 1/4\n")
        self.assertEqual(json.loads((cell / "subagents.json").read_text()), [{"name": "kid", "stack": "procs/kid"}])
        if (TOOL.parents[1] / "self_hook" / "_entry").exists():   # the kid's tool cell is found in the moved tree too
            self.ok({"op": "hook", "name": "kid", "args": {"op": "ls"}}, **env)
            who = [json.loads(l) for l in self.log.read_text().splitlines()][-2]
            self.assertEqual(who[1:4], [str(moved / "procs" / "kid" / "tools" / "self_hook"), "ctl", "who"])

    def test_stack_outside_the_daemon_stays_absolute(self):
        far = self.tmp / "far" / "kid"
        self.ok({"op": "add", "def": "d", "name": "kid", "stack": str(far)})
        self.assertEqual(self.calls("ctl")[-1][:4], ["ctl", "add", "--name", "kid"])
        self.assertEqual(self.record(), [{"name": "kid", "stack": str(far)}])
        self.assertEqual(self.ok({"op": "ls"}), "kid\t-\t-\t-\t-\nsubagents 1/4\n")

    def test_add_keeps_explicit_notify_box(self):
        for i, box in enumerate(("/x", "")):
            with self.subTest(box=box):
                self.ok({"op": "add", "def": "d", "name": "kid%d" % i,
                         "envs": {"AOS_NOTIFY_BOX": box, "LANG": "C"}})
                self.assertEqual(self.calls("ctl")[-1],
                                 ["ctl", "add", "--stack-json", '{"$env": "AOS_DAEMON", "$path": "procs/%s"}' % ("kid%d" % i), "--name", "kid%d" % i,
                                  "--envs", "AOS_NOTIFY_BOX=" + box, "--envs", "LANG=C", "--", "d"])

    def test_add_defaults_notify_box_with_other_envs(self):
        self.ok({"op": "add", "def": "d", "name": "kid", "envs": {"LANG": "C"}})
        self.assertEqual(self.calls("ctl")[-1],
                         ["ctl", "add", "--stack-json", '{"$env": "AOS_DAEMON", "$path": "procs/%s"}' % "kid", "--name", "kid", "--envs", "AOS_NOTIFY_BOX=%s" % (self.mom / "mailbox"),
                          "--envs", "LANG=C", "--", "d"])

    def test_each_targeted_op(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        for args, want in (({"op": "state", "name": "kid"}, ["ctl", "state", "--target", "kid"]),
                           ({"op": "stop", "name": "kid", "timeout_s": 3}, ["ctl", "stop", "--target", "kid", "--timeout-s", "3"]),
                           ({"op": "start", "name": "kid", "on_queued": "ok"}, ["ctl", "start", "--target", "kid", "--on-queued", "ok"]),
                           ({"op": "sleep", "name": "kid"}, ["ctl", "sleep", "--target", "kid"]),
                           ({"op": "wake", "name": "kid"}, ["ctl", "wake", "--target", "kid"]),
                           ({"op": "pause", "name": "kid"}, ["ctl", "pause", "--target", "kid"]),
                           ({"op": "resume", "name": "kid"}, ["ctl", "resume", "--target", "kid"]),
                           ({"op": "say", "name": "kid", "text": "hi"}, ["say", "--target", "kid"]),
                           ({"op": "listen", "name": "kid"}, ["listen", "--target", "kid", "--timeout-s", "0"]),
                           ({"op": "listen", "name": "kid", "timeout_s": 0}, ["listen", "--target", "kid", "--timeout-s", "0"]),
                           ({"op": "ask", "name": "kid", "text": "hi", "timeout_s": 0}, ["ask", "--target", "kid", "--timeout-s", "0"]),
                           ({"op": "ask", "name": "kid", "text": "hi", "timeout_cycles": 5}, ["ask", "--target", "kid", "--timeout-cycles", "5"]),
                           ({"op": "listen", "name": "kid", "letter": "000000000003.q"}, ["listen", "--target", "kid", "--letter", "000000000003.q", "--timeout-s", "0"]),
                           ({"op": "listen", "name": "kid", "last": 3}, ["listen", "--target", "kid", "--last", "3"]),
                           ({"op": "listen", "name": "kid", "timeout_cycles": 7}, ["listen", "--target", "kid", "--timeout-cycles", "7"]),
                           ({"op": "ask", "name": "kid", "text": "hi", "timeout_s": 9}, ["ask", "--target", "kid", "--timeout-s", "9"])):
            out = self.ok(args)
            self.assertEqual(self.calls()[-1], want, args)
        self.assertEqual(out, "the answer\n")
        self.assertEqual(self.calls("say"), [["say", "--target", "kid"]])        # op ask is one aos-agent ask, no say before it (reply-match-1114)

    def test_rm_keeps_stack_unless_purge(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "rm", "name": "kid"})
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "rm", "--", "kid"])
        self.assertEqual(self.record(), [])
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "rm", "name": "kid", "purge": True})
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "rm", "--purge", "-y", "--", "kid"])

    def test_only_my_subagents(self):
        table = json.loads(self.table.read_text()) + [{"name": "other", "stack": str(self.daemon / "procs" / "other")}]
        self.table.write_text(json.dumps(table))
        for op in ({"op": "state"}, {"op": "rm"}, {"op": "say", "text": "x"}, {"op": "tools", "args": {"op": "ls"}}):
            r = self.run_tool(dict(op, name="other"))
            self.assertEqual(r.returncode, 1, op)
            self.assertIn(NAME + ": error: SubagentUnknown other", r.stdout)
        self.assertEqual([c for c in self.calls() if c[:2] not in (["ctl", "ls"], ["ctl", "who"])], [])   # who＝問 daemon 在哪（11-12）

    def test_removed_elsewhere_is_forgotten(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "add", "def": "d", "name": "kid2"})
        # someone else (agents_ctl rm, a human) takes both off the table
        self.table.write_text(json.dumps([{"name": "mom", "stack": str(self.mom)}]))
        r = self.run_tool({"op": "state", "name": "kid"})
        self.assertIn("error: SubagentMissing kid", r.stdout)
        r = self.run_tool({"op": "state", "name": "kid"})
        self.assertIn("error: SubagentUnknown kid", r.stdout)
        self.assertEqual(self.ok({"op": "ls"}), "subagents 0/4\n")     # kid2 forgotten by ls
        self.assertEqual(self.record(), [])
        self.assertIn("subagents 1/4", self.ok({"op": "add", "def": "d", "name": "kid3"}))   # quota freed

    def test_quota_full_sends_nothing(self):
        (self.defdir / "subagents.json").write_text('{"max_subagents": 3}')
        (self.mom / "subagents.json").write_text('{"max_subagents": 1}')          # the stack's copy wins
        self.ok({"op": "add", "def": "d", "name": "kid"})
        r = self.run_tool({"op": "add", "def": "d", "name": "kid2", "ws": "kid2"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: SubagentSlotMissing you already have 1 of max 1", r.stdout)
        self.assertEqual(len([c for c in self.calls("ctl") if c[1] == "add"]), 1)
        self.assertFalse((self.ws / "kid2").exists())
        (self.mom / "subagents.json").write_text('{"max_subagents": "two"}')
        self.assertIn("error: CfgBad", self.run_tool({"op": "add", "def": "d", "name": "kid2"}).stdout)

    def test_queued_subagent(self):
        out = self.ok({"op": "add", "def": "d", "name": "kid", "on_queued": "ok"}, FAKE_QUEUE="1")
        self.assertIn("letter L1", out)
        self.assertEqual(self.record(), [{"name": "kid", "queued_letter": "L1"}])
        self.assertEqual(json.loads(self.ok({"op": "ls", "json": True}))["subagents"], [{"name": "kid", "queued_letter": "L1"}])
        self.assertEqual(self.ok({"op": "ls"}), "kid\tqueued\t-\t-\tletter L1\nsubagents 1/4\n")
        self.assertEqual(self.ok({"op": "ls", "long": True}), "kid\tqueued\t-\t-\tletter L1\t-\t-\t-\t-\nsubagents 1/4\n")
        r = self.run_tool({"op": "tools", "name": "kid", "args": {"op": "ls"}})
        self.assertIn("error: SubagentQueued kid", r.stdout)

    def test_bad_arguments_send_nothing(self):
        for args, word in (({"op": "add", "def": "d", "name": "k", "llm": {}}, "unknown key llm"),
                           ({"op": "ls", "name": "k"}, "op ls does not take name"),
                           ({"op": "say", "name": "k"}, "text needs"),
                           ({"op": "ask", "name": "k", "text": "x", "timeout_s": 5, "timeout_cycles": 5}, "only one of"),
                           ({"op": "listen", "name": "k", "last": -1}, "last must be"),
                           ({"op": "listen", "name": "k", "letter": "x", "last": 1}, "does not go with last"),
                           ({"op": "listen", "name": "k", "letter": ""}, "letter must be"),
                           ({"op": "ask", "name": "k", "text": "x", "letter": "y"}, "op ask does not take letter"),
                           ({"op": "add", "def_json": {"$env": "X"}}, "needs name"),
                           ({"op": "tools", "name": "k", "args": "ls"}, "args must be object"),
                           ({"op": "where", "name": "k"}, "OpUnknown")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual(self.calls(), [])

    def test_lower_error_passed_up(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        r = self.run_tool({"op": "start", "name": "kid"}, FAKE_FAIL="ctl start")
        self.assertIn(NAME + ": error: PhaseBad kid is sleeping; use wake", r.stdout)

    def test_child_accounts_copied_on_ask_listen_rm_not_say(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        kid = self.daemon / "procs" / "kid"
        (kid / "interfaces.json").write_text('{"aos-observed": {"file": "observed.jsonl"}}')
        (kid / "observed.jsonl").write_text('{"kind": "self"}\n')
        copy = self.cell / "observed" / "kid" / "observed.jsonl"
        self.ok({"op": "say", "name": "kid", "text": "x"})
        self.assertFalse(copy.exists())
        for op in ({"op": "listen"}, {"op": "ask", "text": "x"}):
            self.ok(dict(op, name="kid"))
            self.assertTrue(copy.exists(), op)
            shutil.rmtree(self.cell / "observed")
        self.ok({"op": "rm", "name": "kid"})
        self.assertTrue(copy.exists())

    def test_forward_aims_at_the_subagent(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        kid_stack = str(self.daemon / "procs" / "kid")
        for op, sub, args, want in (("tools", "self_tools", {"op": "add", "path": "tools/math"}, ["tools", "--target", "kid", "add", "--", "tools/math"]),
                                    ("llm", "self_llm", {"op": "set", "settings": {"model": "fake"}}, ["llm", "--target", "kid", "set", "--", "model=fake"]),
                                    ("hook", "self_hook", {"op": "ls"}, ["hook", "--target", "kid", "ls"]),
                                    ("system", "self_system", {"op": "get"}, ["system", "--target", "kid", "get"])):
            if not (TOOL.parents[1] / sub / "_entry").exists():
                continue
            out = self.ok({"op": op, "name": "kid", "args": args})
            raw = [json.loads(l) for l in self.log.read_text().splitlines()]
            who, call = raw[-2], raw[-1]
            self.assertEqual(who[1:4], [os.path.join(kid_stack, "tools", sub), "ctl", "who"], op)   # it asks who it is with the kid's stack
            self.assertEqual(call[2:2 + len(want)], want, op)
            self.assertEqual(call[0], str(self.ws))
            self.assertNotIn("your next", out)
        r = self.run_tool({"op": "tools", "name": "kid", "args": {"op": "nope"}})
        self.assertIn(NAME + ": error: OpUnknown", r.stdout)                  # the self_* tool's own error, as ours

    def test_forward_tool_missing(self):
        lib = self.tmp / "lib"
        (lib / "tools" / "agent").mkdir(parents=True)
        for f in ("__init__.py", "tool_io.py", "observed_children.py", "observed.py", "process_group.py",
                  "agentlib/__init__.py", "agentlib/agents_cmd.py", "agentlib/cmd_call.py"):
            (lib / "aos" / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(LIB / "aos" / f, lib / "aos" / f)
        shutil.copytree(TOOL.parent, lib / "tools" / "agent" / NAME, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        self.ok({"op": "add", "def": "d", "name": "kid"})
        r = self.run_tool({"op": "hook", "name": "kid", "args": {"op": "ls"}}, tool=lib / "tools" / "agent" / NAME / "_entry")
        self.assertEqual(r.returncode, 1)
        self.assertIn(NAME + ": error: ToolMissing op hook needs the tool self_hook", r.stdout)


if __name__ == "__main__":
    unittest.main()
