"""Consistency test: the hook_points.json declarations say the same as the event tables the programs use today and as the hand copies (docs, knowledge, self_hook, help texts, gdb); a hand copy that misses a point or a field fails."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
ROOT = PY.parent
sys.path.insert(0, str(PY))
from aos import hook_flags, hook_point
from aos.agentlib import hooks

P = hook_point.PROVIDERS
KERNEL_DIR = PY / "tools" / "aos" / "kernel"
FSM = hook_point.read([P["aos-loop"], P["agent-fsm"]])
ECA = hook_point.read([P["aos-loop"], P["eca"], P["mcp"]])
KERNEL = hook_point.read([str(KERNEL_DIR / "hook_points.json")])


def fired(points):
    """Points something fires today (a point marked not_fired_yet is declared ahead of its code; none is since cut 5)."""
    return {n: p for n, p in points.items() if "not_fired_yet" not in p}


AGENT = dict(fired(ECA), **fired(FSM))   # the eleven shared names plus eca's two compact points; fields of both for the doc checks
ECA_ONLY = {"before_compact", "after_compact"}   # 11-21 top-1121-ecaeffort: eca-claude's compact_hook fires them; agent-fsm has none yet
LOOP = hook_point.read([P["aos-loop"]])     # the four points aos-loop fires through loop.json
FIELDS = {n: set(fired(FSM).get(n, {}).get("fields", {})) | set(fired(ECA).get(n, {}).get("fields", {})) for n in AGENT}

# Gaps between the declarations (= what the code does) and hand copies that are allowed for now: "where: point.field".
# The 17 found on 11-20 (line aos-hook-k1-1120) were filled by line aos-hook-drift-1120; keep this empty.
KNOWN_GAPS = frozenset()


def assigned(path, name):
    """The literal value of a top-level NAME = ... in a Python source file."""
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no %s in %s" % (name, path))


def rows(path, name):
    """Lines of the markdown tables in PATH whose first cell names `name`; a row that says "the fields above"
    (上面、上述) brings the row before it along."""
    out, last = [], ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = line.split("|")
        if line.startswith("|") and len(cells) > 2 and "`%s`" % name in cells[1]:
            out += [last, line] if ("上面" in line or "上述" in line) else [line]
        last = line
    return "\n".join(out)


def gaps():
    """Every hand copy that misses a point or a field: ["where: point", "where: point.field"]."""
    out = []
    doc = PY / "aos" / "apps" / "agent" / "docs" / "06-hook.md"
    for n in AGENT:
        text = rows(doc, n)
        out += ["06-hook.md: %s" % n] if not text else ["06-hook.md: %s.%s" % (n, f) for f in sorted(FIELDS[n]) if "`%s`" % f not in text]
    readme = KERNEL_DIR / "README.md"
    for n, p in KERNEL.items():
        text = rows(readme, n)
        out += ["kernel/README.md: %s" % n] if not text else ["kernel/README.md: %s.%s" % (n, f) for f in sorted(p["fields"]) if "`%s`" % f not in text]
    desc = json.loads((PY / "tools" / "agent" / "self_hook" / "_tooldef.json").read_text(encoding="utf-8"))["description"]
    for n in AGENT:
        text = "\n".join(l for l in desc.splitlines() if l.startswith("- ") and re.search(r"\b%s\b" % n, l))
        out += ["self_hook/_tooldef.json: %s" % n] if not text else ["self_hook/_tooldef.json: %s.%s" % (n, f) for f in sorted(FIELDS[n]) if not re.search(r"\b%s\b" % f, text)]
    know = json.loads((ROOT / "knowledge" / "aos" / "me" / "self_hook.json").read_text(encoding="utf-8"))
    lines = (know["events"] + "\n" + know["clock"]).splitlines()
    for n in AGENT:
        text = "\n".join(l for l in lines if "`%s`" % n in l)
        out += ["knowledge me/self_hook.json: %s" % n] if not text else ["knowledge me/self_hook.json: %s.%s" % (n, f) for f in sorted(FIELDS[n]) if "`%s`" % f not in text]
    help_text = (PY / "aos" / "apps" / "agent" / "hook.py").read_text(encoding="utf-8")
    out += ["aos-agent hook --help: %s" % n for n in AGENT if not re.search(r"\b%s\b" % n, help_text)]
    for tpl, points in (("agent-fsm", FSM), ("start-api/agents/ann", FSM), ("eca-claude", ECA), ("eca-pi", ECA), ("start-eca/agents/ann", ECA)):
        text = json.loads((ROOT / "templates" / tpl / "hooks.json").read_text(encoding="utf-8")).get("description", "")
        out += ["templates/%s/hooks.json: %s" % (tpl, n) for n in fired(points) if not re.search(r"\b%s\b" % n, text)]
    return out


class Tables(unittest.TestCase):
    """What the programs use at run time today."""

    def test_agent_events_per_body(self):
        """EVENTS = every shipped agent point; eca has them all, agent-fsm all but eca's two compact points."""
        self.assertEqual(hook_point.engine_table(fired(ECA)), hooks.EVENTS)
        self.assertEqual(set(hooks.EVENTS) - set(fired(FSM)), ECA_ONLY)
        self.assertEqual(hook_point.engine_table(fired(FSM)), {n: e for n, e in hooks.EVENTS.items() if n not in ECA_ONLY})

    def test_definitions_declare_their_points(self):
        """Cut 3: every shipped definition with hooks lists its hook_points; what they fire = the nine agent events."""
        for tpl in ("agent-fsm", "agent-python", "start-api/agents/ann", "eca-claude", "eca-pi", "start-eca/agents/ann"):
            with self.subTest(tpl=tpl):
                points = hook_point.for_definition(str(ROOT / "templates" / tpl))
                want = hooks.EVENTS if tpl.startswith(("eca-", "start-eca")) else {n: e for n, e in hooks.EVENTS.items() if n not in ECA_ONLY}
                self.assertEqual(hook_point.engine_table(fired(points)), want)
                self.assertEqual(hooks.table(str(ROOT / "templates" / tpl)), hook_point.engine_table(points))

    def test_kernel_events(self):
        spec = importlib.util.spec_from_file_location("kernel_hooks_for_match", KERNEL_DIR / "hooks.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(hook_point.engine_table(KERNEL), mod.EVENTS)

    def test_on_clock_keys(self):
        for points in (FSM, ECA):
            self.assertEqual(points[hooks.CLOCK_EVENT]["phase"], "on")
            self.assertEqual(points[hooks.CLOCK_EVENT]["entry_keys"], list(hooks.CLOCK_KEYS))
        others = {n for points in (FSM, ECA, KERNEL) for n, p in points.items() if "entry_keys" in p}
        self.assertEqual(others, {hooks.CLOCK_EVENT})

    def test_templates_wire_start_stop(self):
        """on_start / on_stop of the templates fire after_start / after_stop through aos-hook fire (the agents with --agent);
        after_stop's fields come from the declaration's env (the variables aos-loop sets for on_stop)."""
        loop = hook_point.read_file(P["aos-loop"])[1]
        self.assertEqual({f: about["env"] for f, about in loop["after_stop"]["fields"].items()},
                         {"code": "AOS_LOOP_CODE", "signal": "AOS_LOOP_SIGNAL", "cause": "AOS_LOOP_CAUSE"})
        agents = ("agent-fsm", "agent-python", "start-api/agents/ann", "eca-claude", "eca-pi", "start-eca/agents/ann")
        for tpl in agents + ("kernel/procs-kernel", "start-api/perm"):
            wired = json.loads((ROOT / "templates" / tpl / "loop.json").read_text(encoding="utf-8"))
            for key, event in (("on_start", "after_start"), ("on_stop", "after_stop")):
                with self.subTest(tpl=tpl, key=key):
                    argv = wired[key]["argv"]
                    self.assertEqual((argv[:3], argv[-1]), (["aos-hook", "fire", "-q"], event))
                    if tpl in agents:
                        self.assertEqual(argv[3:-1], ["--agent", {"$env": "AOS_CD"}])

    def test_gdb(self):
        trigger = PY / "aos" / "gdb" / "trigger.py"
        # gdb's hold list covers the body points; the loop's before_run is a pause breakpoint until cut 6 reads the declarations;
        # eca's before_compact runs inside Claude Code's PreCompact hook (60 s timeout), so gdb pauses on it instead of holding it
        before = {n for n, p in AGENT.items() if p["phase"] == "before" and n not in LOOP and n not in ECA_ONLY}
        self.assertEqual(set(assigned(trigger, "HOLD_EVENTS")), before)
        for n in before:   # key_of: before_tool looks at id, the rest at letter
            self.assertEqual(AGENT[n].get("key"), "id" if n == "before_tool" else "letter", n)
        for n, p in AGENT.items():   # SUBJECT: points with a name condition; brain_failed = code, the rest = tool
            if p.get("condition") == "name":
                self.assertEqual(p.get("subject"), "code" if n == "brain_failed" else "tool", n)

    def test_templates_wire_the_loop_points(self):
        """A24: the templates whose definitions take hooks wire before_run / after_run in loop.json, each behind its flag file."""
        flag = {p: {"$env": "AOS_STACK", "$path": "/" + n} for p, n in hook_flags.FLAGS.items()}
        agents = ("agent-fsm", "agent-python", "start-api/agents/ann", "eca-claude", "eca-pi", "start-eca/agents/ann")
        for tpl in agents + ("kernel/procs-kernel", "start-api/perm"):
            loop = json.loads((ROOT / "templates" / tpl / "loop.json").read_text(encoding="utf-8"))
            for point in ("before_run", "after_run"):
                with self.subTest(tpl=tpl, point=point):
                    argv = loop["on_" + point]["argv"]
                    self.assertEqual((argv[:3], argv[-1]), (["aos-hook", "fire", "-q"], point))
                    self.assertEqual(loop["on_%s_if" % point], flag[point])
                    self.assertIn("--agent" if tpl in agents else "--list", argv)
            fields = [a for a in loop["on_before_run"]["argv"] if isinstance(a, dict) and "$prefix" in a]
            with self.subTest(tpl=tpl, stage=True):
                fsm = (ROOT / "templates" / tpl / "fsm.json").exists()
                self.assertEqual([a["$prefix"] for a in fields], ["stage=", "stage="] if fsm else [])

    def test_self_hook_event_enum(self):
        tooldef = json.loads((PY / "tools" / "agent" / "self_hook" / "_tooldef.json").read_text(encoding="utf-8"))
        self.assertEqual(set(tooldef["parameters"]["properties"]["event"]["enum"]), set(AGENT))


class HandCopies(unittest.TestCase):
    """Docs and help texts written by hand: points and field names."""

    def test_no_new_gaps(self):
        self.assertEqual(sorted(set(gaps()) - KNOWN_GAPS), [])

    def test_known_gaps_are_still_there(self):
        self.assertEqual(sorted(KNOWN_GAPS - set(gaps())), [], "fixed: take these out of KNOWN_GAPS")

    def test_hand_copies_match_fully(self):
        self.assertEqual(gaps(), [])


if __name__ == "__main__":
    unittest.main()
