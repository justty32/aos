"""proto8/lib 的自動測試：inst 樹工具（aos_tree）與判官回話的 schema。只用標準庫。

schema 驗證只在測試裡做（執行期不驗，C-48）；`validate()` 是手寫的最小驗證器，只支援 judge.schema.json 用到的關鍵字：
type、properties、required、items、additionalProperties（false）。
"""
import json
import os
import subprocess
import sys

from helpers import FSM, LIB, Tmp
import aos_tree  # noqa: E402

DEMO = os.path.join(os.path.dirname(LIB), "demo")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


TYPES = {"object": dict, "array": list, "string": str}


def validate(schema, v, at="$"):
    """回錯誤字串的 list（空＝通過）。"""
    errs = []
    t = schema.get("type")
    if t and not isinstance(v, TYPES[t]):
        return ["%s 要是 %s" % (at, t)]
    if isinstance(v, dict):
        errs += ["%s 缺 %s" % (at, k) for k in schema.get("required", []) if k not in v]
        props = schema.get("properties", {})
        for k, x in v.items():
            if k in props:
                errs += validate(props[k], x, at + "." + k)
            elif schema.get("additionalProperties") is False:
                errs.append("%s 多了 %s" % (at, k))
    if isinstance(v, list) and "items" in schema:
        for i, x in enumerate(v):
            errs += validate(schema["items"], x, "%s[%d]" % (at, i))
    return errs


class TreeTest(Tmp):
    def fsm_tree(self):
        self.write("a.json", {"argv": ["sh", "-c", "cat >/dev/null; echo '{\"next\": \"b\", \"data\": {\"x\": 1}}'"]})
        self.write("sub/b.json", {"argv": ["true"]})
        self.write("f.json", {"start": "a", "state": "f.state.json", "states": {
            "a": {"target": "a.json", "next": "b"},
            "b": "sub/b.json",
            "c": {"argv": ["true"]}}})
        return self.p("f.json")

    def test_print_and_ids(self):
        path = self.fsm_tree()
        node, _ = aos_tree.build(path)
        text = aos_tree.render(node)
        real = os.path.realpath(path)
        self.assertEqual(node["kind"], "fsm")
        self.assertIn("fsm " + real, text)
        self.assertIn("states/c: inst %s#/states/c" % real, text)        # 內嵌＝外層 id 接位置
        self.assertIn("states/a: inst " + os.path.realpath(self.p("a.json")), text)
        self.assertIn("states/b: inst " + os.path.realpath(self.p("sub/b.json")), text)
        self.assertEqual([k["label"] for k in node["kids"]], ["states/a", "states/b", "states/c"])

    def test_ids_never_null_and_dict_root(self):
        node, doc = aos_tree.build({"start": "a", "states": {"a": {"argv": ["true"]}, "b": {"target": {"argv": ["true"]}}}})

        def ids(n):
            return [n["id"]] + [i for k in n["kids"] for i in ids(k)]
        all_ids = ids(node)
        self.assertEqual(len(all_ids), 3)
        self.assertTrue(all(isinstance(i, str) and i for i in all_ids))
        self.assertTrue(node["id"].startswith("sha256:"))
        self.assertEqual(node["kids"][1]["id"], node["id"] + "#/states/b/target")

    def test_demo_agent_tree(self):
        r = subprocess.run([sys.executable, os.path.join(LIB, "aos_tree.py"), "print", "agent.json"], cwd=os.path.join(DEMO, "fsm"),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("fsm+agent "))
        for lab in ("states/thinking", "brain", "tools/clerk"):
            self.assertTrue(any(l.startswith("  " + lab + ": inst /") for l in lines), lab)

    def test_inline_runs_same(self):
        path = self.fsm_tree()
        _, doc = aos_tree.build(path)

        def walk(d):        # 攤完不該再剩字串槽位
            for p, _ in aos_tree.slots(d):
                v = d
                for k in p:
                    v = v[k]
                self.assertIsInstance(v, dict)
                walk(v)
        walk(doc)
        inl = self.p("inl.json")
        doc["state"] = "inl.state.json"
        with open(inl, "w") as f:
            json.dump(doc, f)
        for p in ("f.json", "inl.json"):
            r = subprocess.run([sys.executable, FSM, p], capture_output=True, text=True, cwd=self.tmp, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
        a, b = (load(self.p(n)) for n in ("f.state.json", "inl.state.json"))
        for k in ("phase", "data", "step", "last_error"):
            self.assertEqual((k, a[k]), (k, b[k]))
        self.assertEqual((a["phase"], a["data"]), ("b", {"x": 1}))

    def test_cli_inline_cycle_and_depth(self):
        self.write("x.json", {"start": "a", "states": {"a": "y.json"}})
        self.write("y.json", {"start": "a", "states": {"a": "x.json", "b": {"argv": ["true"]}}})
        tool = os.path.join(LIB, "aos_tree.py")
        r = subprocess.run([sys.executable, tool, "inline", "x.json"], capture_output=True, text=True, cwd=self.tmp, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        w = json.loads(r.stderr.splitlines()[0])["warning"]
        self.assertEqual(w["code"], "TreeCycle")
        out = json.loads(r.stdout)
        self.assertEqual(out["states"]["a"]["states"]["a"], "x.json")      # 循環處留名字
        self.assertIn("b", out["states"]["a"]["states"])
        r = subprocess.run([sys.executable, tool, "inline", "x.json", "--depth", "0"], capture_output=True, text=True,
                           cwd=self.tmp, timeout=10)
        self.assertEqual(json.loads(r.stderr.splitlines()[0])["warning"]["code"], "TreeDepth")
        self.assertEqual(json.loads(r.stdout)["states"]["a"], "y.json")

    def test_missing_target_is_error(self):
        self.write("x.json", {"start": "a", "states": {"a": "nope.json"}})
        r = subprocess.run([sys.executable, os.path.join(LIB, "aos_tree.py"), "print", "x.json"], capture_output=True, text=True,
                           cwd=self.tmp, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("error", json.loads(r.stderr.splitlines()[0]))


class JudgeSchemaTest(Tmp):
    def schema(self):
        d = os.path.join(DEMO, "kernel2")
        inst = load(os.path.join(d, "judge-rules.json"))
        return load(os.path.join(d, inst["_schema"]))        # 私有 key，普通路徑

    def run_judge(self, snap):
        r = subprocess.run([sys.executable, os.path.join(LIB, "judge_rules.py")], input=json.dumps(snap), capture_output=True,
                           text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_judge_rules_output_matches_schema(self):
        sc = self.schema()["stdout"]
        snap = {"queue": {"a": {"priority": {"level": "low"}, "_metainfo": {"resource": "llm"}},
                          "b": {"priority": {"level": "high"}, "_metainfo": {"resource": "llm"}},
                          "c": {"_metainfo": {"resource": "human"}}},
                "slots": {"llm": {"total": 1, "used": 0}, "human": {"total": 1, "used": 0}}}
        out = self.run_judge(snap)
        self.assertEqual(validate(sc, out), [])
        self.assertEqual(validate(sc, self.run_judge({"queue": {}, "slots": {}})), [])
        self.assertTrue(validate(self.schema()["stdin"], snap) == [])

    def test_validator_rejects_bad(self):
        sc = self.schema()["stdout"]
        self.assertTrue(validate(sc, {"run": "a"}))
        self.assertTrue(validate(sc, {"run": [1]}))
        self.assertTrue(validate(sc, {"extra": []}))
        self.assertTrue(validate(sc, {"reject": [{"id": "a"}]}))
        self.assertTrue(validate(sc, {"reject": [{"id": "a", "error": {"msg": "x"}}]}))
        self.assertEqual(validate(sc, {"reject": [{"id": "a", "error": {"code": "X", "msg": "y"}}]}), [])
