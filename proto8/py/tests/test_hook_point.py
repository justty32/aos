"""Test aos.hook_point: the shipped hook_points.json files read and check fine, every check rule rejects a bad example, merging, engine_table and for_definition."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY))
from aos import hook_point
from aos.hook_point import PointsBad

KERNEL = PY / "tools" / "aos" / "kernel" / "hook_points.json"
SHIPPED = dict(hook_point.PROVIDERS, kernel=str(KERNEL))


def point(**kw):
    p = {"when": "w", "phase": "after", "fields": {"name": "n", "id": "i"}}
    p.update(kw)
    return p


class Shipped(unittest.TestCase):
    def test_each_file_reads_and_names_its_provider(self):
        for provider, path in SHIPPED.items():
            with self.subTest(provider=provider):
                got, points = hook_point.read_file(path)
                self.assertEqual(got, provider)
                self.assertTrue(points)

    def test_fired_in_files_exist_and_name_the_point(self):
        for provider, path in SHIPPED.items():
            _, points = hook_point.read_file(path)
            for name, p in points.items():
                for rel in p.get("fired_in", []):
                    with self.subTest(provider=provider, point=name, file=rel):
                        src = Path(path).parent / rel
                        self.assertTrue(src.is_file(), src)
                        self.assertRegex(src.read_text(encoding="utf-8"), r"\b%s\b" % re.escape(name))

    def test_nothing_shipped_is_not_fired_yet(self):
        """Cut 5, second half: the templates wire before_run / after_run, so every shipped point is fired."""
        found = {(prov, n) for prov, path in SHIPPED.items()
                 for n, p in hook_point.read_file(path)[1].items() if "not_fired_yet" in p}
        self.assertEqual(found, set())

    def test_start_api_ann_links_the_shipped_file(self):
        """11-21: start-api's ann carries no hook_points.json of its own; it names the provider, so it reads agent-fsm's declaration."""
        ann = str(PY.parent / "templates" / "start-api" / "agents" / "ann")
        points = hook_point.for_definition(ann)
        self.assertEqual(points, hook_point.read([hook_point.provider_path("aos-loop"), hook_point.provider_path("agent-fsm")]))
        self.assertEqual({s["path"] for p in points.values() for s in p["said"]},
                         {hook_point.provider_path("aos-loop"), hook_point.provider_path("agent-fsm")})

    def test_unknown_provider(self):
        with self.assertRaisesRegex(PointsBad, "unknown hook point provider"):
            hook_point.provider_path("nope")


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hook-point-")
        self.addCleanup(self.tmp.cleanup)
        self.n = 0

    def write(self, doc, raw=None):
        self.n += 1
        path = os.path.join(self.tmp.name, "p%d.json" % self.n)
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(doc))
        return path

    def bad(self, doc, pattern, raw=None):
        with self.assertRaisesRegex(PointsBad, pattern):
            hook_point.read([self.write(doc, raw)])

    def doc(self, **points):
        return {"provider": "x", "points": points}

    def test_good_minimal(self):
        got = hook_point.read([self.write(self.doc(a_1=point()))])
        self.assertEqual(list(got), ["a_1"])
        self.assertEqual(got["a_1"]["said"], [{"provider": "x", "path": os.path.join(self.tmp.name, "p1.json"), "when": "w"}])

    def test_rule1_file_shape_and_types(self):
        self.bad(None, "cannot read", raw="{")
        self.bad([], "must be a JSON object")
        self.bad({"points": {}}, "provider must be")
        self.bad({"provider": "x", "points": []}, "points must be")
        self.bad(self.doc(**{"Bad-Name": point()}), "may only have")
        self.bad(self.doc(a=[]), "point a must be a JSON object")
        self.bad(self.doc(a=point(when="")), "when must be")
        self.bad(self.doc(a=point(fields=[])), "fields must be")
        self.bad(self.doc(a=point(fields={"f": 1})), "field f must be")
        self.bad(self.doc(a=point(fields={"f": {"env": "E"}})), "needs about")
        self.bad(self.doc(a=point(fields={"f": {"about": "a", "env": ""}})), "needs env")
        self.bad(self.doc(a=point(fields={"f": {"about": "a", "env": "E", "type": "float"}})), "type must be")
        self.bad(self.doc(a=point(condition=3)), "condition must be")
        self.bad(self.doc(a=point(subject="")), "subject must be")
        self.bad(self.doc(a=point(block="yes")), "block must be")
        self.bad(self.doc(a=point(change=["name"])), "change must be")
        self.bad(self.doc(a=point(entry_keys="every_ms")), "entry_keys must be")
        self.bad(self.doc(a=point(fired_in=[""])), "fired_in must be")
        self.bad(self.doc(a=point(not_fired_yet=True)), "not_fired_yet must be")

    def test_rule2_phase_and_block(self):
        self.bad(self.doc(a=point(phase="during")), "phase must be")
        self.bad(self.doc(a=point(phase="on", block=True, if_blocked="b")), "does not go with phase on")
        self.bad(self.doc(a=point(phase="before", block=True)), "needs if_blocked")
        hook_point.read([self.write(self.doc(a=point(phase="after", block=True, if_blocked="b")))])   # after + block is allowed (kernel after_verdict)

    def test_rule3_keys_are_fields(self):
        self.bad(self.doc(a=point(condition="nope")), "condition nope is not one of its fields")
        self.bad(self.doc(a=point(key="nope")), "key nope is not one of its fields")
        self.bad(self.doc(a=point(change={"nope": "any"})), "change nope is not one of its fields")

    def test_rule4_change_types(self):
        self.bad(self.doc(a=point(change={"name": "int"})), "change name must be")
        for t in hook_point.CHANGE_TYPES:
            hook_point.read([self.write(self.doc(a=point(change={"name": t})))])

    def test_rule5_merge(self):
        one = self.write({"provider": "p1", "points": {"a": point(fields={"name": "first"}, condition="name")}})
        two = self.write({"provider": "p2", "points": {"a": point(when="w2", fields={"name": "second", "extra": "e"},
                                                                  condition="name", if_failed="stops")}})
        got = hook_point.read([one, two])["a"]
        self.assertEqual(got["fields"], {"name": "first", "extra": "e"})
        self.assertEqual([(s["provider"], s["when"]) for s in got["said"]], [("p1", "w"), ("p2", "w2")])
        self.assertEqual(got["said"][1]["if_failed"], "stops")
        for k, v in (("phase", "before"), ("condition", "id"), ("subject", "tool"), ("change", {"name": "any"}),
                     ("block", True), ("key", "id"), ("entry_keys", ["every_ms"])):
            with self.subTest(key=k):
                p = point(fields={"name": "n", "id": "i"}, condition="name")
                p[k] = v
                if k == "block":
                    p["if_blocked"] = "b"
                other = self.write({"provider": "p3", "points": {"a": p}})
                with self.assertRaisesRegex(PointsBad, "point a: %s differs" % k):
                    hook_point.read([one, other])

    def test_engine_table(self):
        path = self.write(self.doc(a=point(phase="before", condition="name", change={"id": "string", "name": "any"},
                                           block=True, if_blocked="b"), b=point()))
        self.assertEqual(hook_point.engine_table(hook_point.read([path])),
                         {"a": {"condition": "name", "intercept": ("id", "name"), "block": True},
                          "b": {"condition": None, "intercept": (), "block": False}})


class ForDefinition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hook-point-def-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def interfaces(self, doc, raw=None):
        with open(os.path.join(self.dir, "interfaces.json"), "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(doc))

    def test_nothing_declared(self):
        self.assertEqual(hook_point.for_definition(self.dir), {})
        self.interfaces({"other": 1})
        self.assertEqual(hook_point.for_definition(self.dir), {})
        self.interfaces({"aos-agent": {"hooks": "hooks.json"}})
        self.assertEqual(hook_point.for_definition(self.dir), {})

    def test_providers_and_paths(self):
        with open(os.path.join(self.dir, "mine.json"), "w", encoding="utf-8") as f:
            json.dump({"provider": "me", "points": {"before_save": point(phase="before")}}, f)
        self.interfaces({"aos-agent": {"hook_points": [{"provider": "aos-loop"}, {"provider": "agent-fsm"}, "mine.json"]}})
        got = hook_point.for_definition(self.dir)
        self.assertIn("after_start", got)
        self.assertIn("before_tool", got)
        self.assertEqual(got["before_save"]["said"][0]["path"], os.path.join(self.dir, "mine.json"))

    def test_bad(self):
        for doc, pattern in (([], "must be a JSON object"), ({"aos-agent": []}, "aos-agent must be"),
                             ({"aos-agent": {"hook_points": "x.json"}}, "must be an array"),
                             ({"aos-agent": {"hook_points": [{"provider": "eca", "x": 1}]}}, "each item"),
                             ({"aos-agent": {"hook_points": [{"$env": "AOS_HOME"}]}}, "each item"),
                             ({"aos-agent": {"hook_points": [{"provider": "nope"}]}}, "unknown hook point provider"),
                             ({"aos-agent": {"hook_points": ["missing.json"]}}, "cannot read")):
            with self.subTest(doc=doc):
                self.interfaces(doc)
                with self.assertRaisesRegex(PointsBad, pattern):
                    hook_point.for_definition(self.dir)
        self.interfaces(None, raw="{")
        with self.assertRaisesRegex(PointsBad, "cannot read"):
            hook_point.for_definition(self.dir)


if __name__ == "__main__":
    unittest.main()
