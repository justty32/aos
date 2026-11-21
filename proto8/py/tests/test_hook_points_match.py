"""Consistency test: the hook point declarations (only for reading) say the same as the rules the firing programs keep in code (the agent family, the kernel), the templates wire the loop points the new way, and the hand copies (docs, knowledge, self_hook, help texts, gdb) name every point and field."""
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
from aos import hook_point
from aos.agentlib import hooks

KERNEL_DIR = PY / "tools" / "aos" / "kernel"
LOOP = hook_point.read([str(PY / "aos" / "apps" / "hook" / "loop_hooks.json")])
FSM = hook_point.read([str(ROOT / "templates" / "agent-fsm" / "hooks.json")])
ECA = hook_point.read([str(PY / "aos" / "apps" / "eca" / "hooks.json"), str(PY / "aos" / "apps" / "mcp" / "hooks.json")])
KERNEL = hook_point.read([str(KERNEL_DIR / "kernel_hooks.json")])
ECA_ONLY = {"before_compact", "after_compact"}   # eca-claude's compact_hook fires them through aos-hook fire
AGENT = dict(ECA, **FSM)
COMMON = {"event", "hook", "stack"}             # every handler gets these


def fields(point):
    return set(point["input"].get("properties", {})) - COMMON


def kernel_module():
    spec = importlib.util.spec_from_file_location("kernel_hooks_for_match", KERNEL_DIR / "hooks.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(KERNEL_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(KERNEL_DIR))
    return mod


def assigned(path, name):
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no %s in %s" % (name, path))


class Rules(unittest.TestCase):
    """A declaration only tells; these make sure it does not tell something else than the code does."""

    def check(self, points, rules):
        for n, rule in rules.items():
            with self.subTest(point=n):
                p = points[n]
                self.assertEqual(bool(p.get("block")), rule.get("block", True), n)
                self.assertEqual(p.get("condition"), rule["field"], n)
                change = rule["change"] if isinstance(rule["change"], tuple) else tuple(rule["change"])
                self.assertEqual(set(p.get("output", {}).get("properties", {})), set(change), n)

    def test_agent_family(self):
        self.assertEqual(set(hooks.POINTS), set(FSM))
        self.assertEqual(set(hooks.POINTS) | ECA_ONLY, set(ECA))
        self.check(FSM, hooks.POINTS)
        self.check(ECA, hooks.POINTS)

    def test_kernel(self):
        rules = kernel_module().POINTS
        self.assertEqual(set(rules), set(KERNEL))
        self.check(KERNEL, rules)

    def test_on_clock_keys(self):
        for points in (FSM, ECA):
            self.assertEqual(points[hooks.CLOCK_EVENT]["entry_keys"], list(hooks.CLOCK_KEYS))


class Wiring(unittest.TestCase):
    AGENTS = ("agent-fsm", "agent-python", "start-api/agents/ann", "eca-claude", "eca-pi", "start-eca/agents/ann")
    KERNELS = ("kernel/procs-kernel", "kernel/kernel-python", "start-api/perm")

    def test_templates_wire_start_stop(self):
        """on_start / on_stop fire after_start / after_stop through aos-hook fire --stop-on-nonzero --def $AOS_CD."""
        for tpl in self.AGENTS + self.KERNELS:
            wired = json.loads((ROOT / "templates" / tpl / "loop.json").read_text(encoding="utf-8"))
            for key, event in (("on_start", "after_start"), ("on_stop", "after_stop")):
                with self.subTest(tpl=tpl, key=key):
                    self.assertEqual(wired[key]["argv"], ["aos-hook", "fire", "-q", "--stop-on-nonzero", "--def", {"$env": "AOS_CD"}, event])

    def test_no_flag_files_and_no_run_points_without_hooks(self):
        """No flag files any more; a template that hooks nothing on before_run / after_run does not wire them."""
        for path in sorted(ROOT.glob("templates/**/loop.json")):
            loop = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path=str(path)):
                self.assertFalse({"on_before_run_if", "on_after_run_if"} & set(loop))
                self.assertFalse({"on_before_run", "on_after_run"} & set(loop))
                self.assertNotIn("--points", json.dumps(loop))
                self.assertNotIn("loop_hooks.json", json.dumps(loop))      # the old list file of the loop points is gone

    def test_kernel_json_has_no_hooks(self):
        """kernel 甲案: what is hooked moved to kernel_hookeds.json; a hooks key left in kernel.json would be silently ignored."""
        for path in sorted(ROOT.glob("templates/**/kernel.json")):
            with self.subTest(path=str(path)):
                self.assertNotIn("hooks", json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(ROOT.glob("templates/**/kernel.json")):
            face = json.loads((path.parent / "interfaces.json").read_text(encoding="utf-8"))
            with self.subTest(face=str(path.parent)):
                self.assertEqual(face["hookeds"], "kernel_hookeds.json")
                self.assertEqual(face["kernel"], {})
                hooks_value = face["hooks"] if isinstance(face["hooks"], list) else [face["hooks"]]
                self.assertEqual(hooks_value[0], "kernel_hooks.json")

    def test_nothing_reads_hooks_as_a_list(self):
        """The trap of the swap: the code that reads hookeds lists asks for "hookeds"; only aos.hook_point names both keys."""
        offenders = []
        for path in list(PY.rglob("*.py")) + list(PY.rglob("_entry")) + list((ROOT / "templates").rglob("*.py")):
            if "tests" in path.parts or path.name == "hook_point.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"""(items|files|layers)\([^)]*["']hooks["']""", text) or re.search(r"""declared_files\([^)]*\)\.get\(["']hooks""", text):
                offenders.append(str(path))
        self.assertEqual(offenders, [])

    def test_gdb(self):
        trigger = PY / "aos" / "gdb" / "trigger.py"
        before = {n for n, p in AGENT.items() if p.get("phase") == "before" and n not in ECA_ONLY}
        self.assertEqual(set(assigned(trigger, "HOLD_EVENTS")), before)
        for n in before:   # key_of: before_tool looks at id, the rest at letter
            self.assertEqual(AGENT[n].get("key"), "id" if n == "before_tool" else "letter", n)
        for n, p in AGENT.items():
            if p.get("condition") == "name":
                self.assertEqual(p.get("subject"), "code" if n == "brain_failed" else "tool", n)

    def test_self_hook_event_enum(self):
        tooldef = json.loads((PY / "tools" / "agent" / "self_hook" / "_tooldef.json").read_text(encoding="utf-8"))
        self.assertEqual(set(tooldef["parameters"]["properties"]["event"]["enum"]), set(AGENT) | set(LOOP))


def rows(path, name):
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
    for n, p in AGENT.items():
        text = rows(doc, n)
        out += ["06-hook.md: %s" % n] if not text else ["06-hook.md: %s.%s" % (n, f) for f in sorted(fields(p)) if "`%s`" % f not in text]
    readme = KERNEL_DIR / "README.md"
    for n, p in KERNEL.items():
        text = rows(readme, n)
        out += ["kernel/README.md: %s" % n] if not text else ["kernel/README.md: %s.%s" % (n, f) for f in sorted(fields(p)) if "`%s`" % f not in text]
    desc = json.loads((PY / "tools" / "agent" / "self_hook" / "_tooldef.json").read_text(encoding="utf-8"))["description"]
    for n, p in AGENT.items():
        text = "\n".join(l for l in desc.splitlines() if l.startswith("- ") and re.search(r"\b%s\b" % n, l))
        out += ["self_hook/_tooldef.json: %s" % n] if not text else ["self_hook/_tooldef.json: %s.%s" % (n, f) for f in sorted(fields(p)) if not re.search(r"\b%s\b" % f, text)]
    know = json.loads((ROOT / "knowledge" / "aos" / "me" / "self_hook.json").read_text(encoding="utf-8"))
    lines = (know["events"] + "\n" + know["clock"]).splitlines()
    for n, p in AGENT.items():
        text = "\n".join(l for l in lines if "`%s`" % n in l)
        out += ["knowledge me/self_hook.json: %s" % n] if not text else ["knowledge me/self_hook.json: %s.%s" % (n, f) for f in sorted(fields(p)) if "`%s`" % f not in text]
    help_text = (PY / "aos" / "apps" / "agent" / "hook.py").read_text(encoding="utf-8")
    out += ["aos-agent hook --help: %s" % n for n in list(AGENT) + list(LOOP) if not re.search(r"\b%s\b" % n, help_text)]
    return out


class HandCopies(unittest.TestCase):
    def test_hand_copies_match_fully(self):
        self.assertEqual(gaps(), [])


if __name__ == "__main__":
    unittest.main()
