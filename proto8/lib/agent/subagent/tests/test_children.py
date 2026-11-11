"""Test subagent against a fake aos-agent with a table: argv per op, the record and its reconciliation, quota, rm without purge, child account copies, and tools/llm/history/hook/system aimed at the child."""
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
LIB = Path(__file__).resolve().parents[3]
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
    print(json.dumps({"name": r["name"], "stack": r["stack"], "ws": None, "def": os.environ.get("FAKE_DEF")}) if "--json" in argv else r["name"])
elif argv[:2] == ["ctl", "add"]:
    name = argv[argv.index("--name") + 1] if "--name" in argv else os.path.basename(argv[-1])
    if os.environ.get("FAKE_QUEUE"):
        print("queued %s at position 1 (letter L1; applied when a slot frees)" % name)
        sys.exit(0)
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
else:
    print("ok " + " ".join(argv))
'''


class Children(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agents-children-"))
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
        return json.loads((self.cell / "children.json").read_text())

    def test_add_records_and_argv(self):
        out = self.ok({"op": "add", "def": "defs/helper", "name": "kid", "ws": "kid", "limits": {"mem_mb": 64}, "timeout_s": 5})
        self.assertIn("added kid (stack %s); children 1/4" % (self.daemon / "procs" / "kid"), out)
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "add", "--name", "kid", "--ws", "kid", "--limits", '{"mem_mb": 64}',
                                                 "--timeout-s", "5", "defs/helper"])
        self.assertTrue((self.ws / "kid").is_dir())
        self.assertEqual(self.record(), [{"name": "kid", "stack": "procs/kid"}])
        self.ok({"op": "add", "def": "defs/kid2"})           # name defaults to the folder name, like ctl add
        self.assertEqual([k["name"] for k in self.record()], ["kid", "kid2"])
        self.assertEqual(self.ok({"op": "ls"}), "kid\t-\t-\t-\t-\nkid2\t-\t-\t-\t-\nchildren 2/4\n")   # short lines, not mom
        listed = json.loads(self.ok({"op": "ls", "json": True}))
        self.assertEqual([r["name"] for r in listed["children"]], ["kid", "kid2"])   # not mom
        self.assertEqual(listed["max_children"], 4)
        self.assertEqual(self.ok({"op": "ls", "long": True}),        # long = ctl ls -l lines of mine, as text
                         "kid\trunning\t-\t-\t-\t2\t0\t-\t-\nkid2\trunning\t-\t-\t-\t2\t0\t-\t-\nchildren 2/4\n")
        self.assertEqual(json.loads(self.ok({"op": "ls", "long": True, "json": True}))["max_children"], 4)   # json wins

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
                           ({"op": "listen", "name": "kid"}, ["listen", "--target", "kid", "--timeout-s", "600"]),
                           ({"op": "listen", "name": "kid", "last": 3}, ["listen", "--target", "kid", "--last", "3"]),
                           ({"op": "listen", "name": "kid", "timeout_cycles": 7}, ["listen", "--target", "kid", "--timeout-cycles", "7"]),
                           ({"op": "ask", "name": "kid", "text": "hi", "timeout_s": 9}, ["listen", "--target", "kid", "--timeout-s", "9"])):
            out = self.ok(args)
            self.assertEqual(self.calls()[-1], want, args)
        self.assertEqual(out, "the answer\n")
        self.assertEqual(self.calls("say")[-1], ["say", "--target", "kid"])

    def test_rm_keeps_stack_unless_purge(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "rm", "name": "kid"})
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "rm", "kid"])
        self.assertEqual(self.record(), [])
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "rm", "name": "kid", "purge": True})
        self.assertEqual(self.calls("ctl")[-1], ["ctl", "rm", "--purge", "-y", "kid"])

    def test_only_my_children(self):
        table = json.loads(self.table.read_text()) + [{"name": "other", "stack": str(self.daemon / "procs" / "other")}]
        self.table.write_text(json.dumps(table))
        for op in ({"op": "state"}, {"op": "rm"}, {"op": "say", "text": "x"}, {"op": "tools", "args": {"op": "ls"}}):
            r = self.run_tool(dict(op, name="other"))
            self.assertEqual(r.returncode, 1, op)
            self.assertIn(NAME + ": error: ChildUnknown other", r.stdout)
        self.assertEqual([c for c in self.calls() if c[:2] != ["ctl", "ls"]], [])

    def test_removed_elsewhere_is_forgotten(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        self.ok({"op": "add", "def": "d", "name": "kid2"})
        # someone else (agents_ctl rm, a human) takes both off the table
        self.table.write_text(json.dumps([{"name": "mom", "stack": str(self.mom)}]))
        r = self.run_tool({"op": "state", "name": "kid"})
        self.assertIn("error: ChildMissing kid", r.stdout)
        r = self.run_tool({"op": "state", "name": "kid"})
        self.assertIn("error: ChildUnknown kid", r.stdout)
        self.assertEqual(self.ok({"op": "ls"}), "children 0/4\n")     # kid2 forgotten by ls
        self.assertEqual(self.record(), [])
        self.assertIn("children 1/4", self.ok({"op": "add", "def": "d", "name": "kid3"}))   # quota freed

    def test_quota_full_sends_nothing(self):
        (self.defdir / "children.json").write_text('{"max_children": 3}')
        (self.mom / "children.json").write_text('{"max_children": 1}')          # the stack's copy wins
        self.ok({"op": "add", "def": "d", "name": "kid"})
        r = self.run_tool({"op": "add", "def": "d", "name": "kid2", "ws": "kid2"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: ChildSlotMissing you already have 1 of max 1", r.stdout)
        self.assertEqual(len([c for c in self.calls("ctl") if c[1] == "add"]), 1)
        self.assertFalse((self.ws / "kid2").exists())
        (self.mom / "children.json").write_text('{"max_children": "two"}')
        self.assertIn("error: CfgBad", self.run_tool({"op": "add", "def": "d", "name": "kid2"}).stdout)

    def test_queued_child(self):
        out = self.ok({"op": "add", "def": "d", "name": "kid", "on_queued": "ok"}, FAKE_QUEUE="1")
        self.assertIn("letter L1", out)
        self.assertEqual(self.record(), [{"name": "kid", "queued_letter": "L1"}])
        self.assertEqual(json.loads(self.ok({"op": "ls", "json": True}))["children"], [{"name": "kid", "queued_letter": "L1"}])
        self.assertEqual(self.ok({"op": "ls"}), "kid\tqueued\t-\t-\tletter L1\nchildren 1/4\n")
        self.assertEqual(self.ok({"op": "ls", "long": True}), "kid\tqueued\t-\t-\tletter L1\t-\t-\t-\t-\nchildren 1/4\n")
        r = self.run_tool({"op": "tools", "name": "kid", "args": {"op": "ls"}})
        self.assertIn("error: ChildQueued kid", r.stdout)

    def test_bad_arguments_send_nothing(self):
        for args, word in (({"op": "add", "def": "d", "name": "k", "llm": {}}, "unknown key llm"),
                           ({"op": "ls", "name": "k"}, "op ls does not take name"),
                           ({"op": "say", "name": "k"}, "text needs"),
                           ({"op": "ask", "name": "k", "text": "x", "timeout_s": 5, "timeout_cycles": 5}, "only one of"),
                           ({"op": "listen", "name": "k", "last": -1}, "last must be"),
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

    def test_forward_aims_at_the_child(self):
        self.ok({"op": "add", "def": "d", "name": "kid"})
        kid_stack = str(self.daemon / "procs" / "kid")
        for op, sub, args, want in (("tools", "self_tools", {"op": "add", "path": "tools/math"}, ["tools", "--target", "kid", "add", "tools/math"]),
                                    ("llm", "self_llm", {"op": "set", "settings": {"model": "fake"}}, ["llm", "--target", "kid", "set", "model=fake"]),
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
        (lib / "agent").mkdir(parents=True)
        for f in ("tool_io.py", "observed_children.py", "observed.py"):
            shutil.copy(LIB / f, lib / f)
        shutil.copy(TOOL.parents[1] / "agents_cmd.py", lib / "agent")
        shutil.copytree(TOOL.parent, lib / "agent" / NAME, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        self.ok({"op": "add", "def": "d", "name": "kid"})
        r = self.run_tool({"op": "hook", "name": "kid", "args": {"op": "ls"}}, tool=lib / "agent" / NAME / "_entry")
        self.assertEqual(r.returncode, 1)
        self.assertIn(NAME + ": error: ToolMissing op hook needs the tool self_hook", r.stdout)


if __name__ == "__main__":
    unittest.main()
