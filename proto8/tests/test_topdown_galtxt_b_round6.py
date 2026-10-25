"""test_topdown_galtxt_b_round6 - galtxt-b 第 6 輪 §7 第 4、5 項（plan/round6.md §2、§3）：難例 → teach、結構化梯度、λ_gain。全部假腦。
訓練場：train/init 複製出 tree/ → 第 1 輪跑「prop 舊車票」題（表外：降級＋小格難例）→ train/score → train/record 收難例進 tree/ 複本
→ changes/1.json 一條 teach → train/apply（v0_agent 假腦回一張合法表）→ plans.json 多一列、難例 resolved → 第 2 輪同題 degraded 空
→ record 算 changes/1.json.gradient 與 gradient_share。定義資料夾（director、train 的格）hash 不變。
另：diff 三類（數值、非數值、集合）＋文字列 notes、只動一個工具時 share 全給它、有貢獻時按比例、pick 的 λ_gain、專名換回佔位。"""
import hashlib, importlib.machinery, importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
TRAIN = GB / "train"
Q = "新書_宮澤_主角先_舊車票"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD", "AOS_CO")
POLARITY = json.loads((TRAIN / "record" / "polarity.json").read_text(encoding="utf-8"))


def load_entry(path, name):
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        loader = importlib.machinery.SourceFileLoader(name, str(path))
        spec = importlib.util.spec_from_loader(name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


record = load_entry(TRAIN / "record" / "_entry", "galtxt_b_record")
apply_mod = load_entry(TRAIN / "apply" / "_entry", "galtxt_b_apply")
pick = load_entry(TRAIN / "pick" / "_entry", "galtxt_b_pick")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR and not k.startswith("GALTXT_")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def tree_hash(*roots):
    h = hashlib.sha256()
    for root in roots:
        for d, dirs, files in sorted(os.walk(root)):
            dirs.sort()
            for n in sorted(files):
                p = os.path.join(d, n)
                h.update(p.encode())
                if not os.path.islink(p):
                    h.update(Path(p).read_bytes())
    return h.hexdigest()


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class TeachLoop(unittest.TestCase):
    """端到端（假腦）：兩輪＋record＋apply teach。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.F = Path(self._t.name) / "field"
        self.stack = Path(self._t.name) / "stack"
        self.stack.mkdir()
        self.F.mkdir()

    def ex(self, cell, n):
        (self.stack / "round.json").write_text(json.dumps({"round": n}), encoding="utf-8")
        r = run(EXEC, "--ws", self.F, TRAIN / cell, env={"AOS_STACK": str(self.stack) + "/"}, cwd=self._t.name, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def round(self, n, q):
        ws = self.F / "runs" / str(n) / Q / "1"
        (ws / "new").mkdir(parents=True)
        (ws / "new" / (Q + ".json")).write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, self.F / "tree", cwd=self._t.name, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr)
        (ws / "run.json").write_text(json.dumps({"code": 0}), encoding="utf-8")
        self.ex("score", n)
        self.ex("record", n)
        return jload(ws / "out" / Q / "score.json")

    def test_hard_case_teach_gradient(self):
        watch = [GB / "draft" / "tools" / "director"] + [TRAIN / c for c in ("init", "record", "apply", "set", "pick")]
        before = tree_hash(*watch)
        self.ex("init", 0)
        self.assertTrue((self.F / "tree" / "draft" / "tools" / "director" / "versions" / "v1_script" / "tools" / "agent").is_symlink())
        self.assertFalse((self.F / "tree" / "train").exists())
        q = jload(TRAIN / "set" / "新書_宮澤_主角先_梅花章.json")
        q.update(switches={"first_speaker": "主角", "prop": "舊車票"}, must_mention=[["新書", "進新書日"], ["舊車票"]])
        (self.F / "set" / (Q + ".json")).write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        director = self.F / "tree" / "draft" / "tools" / "director"
        plans = director / "tools" / "plan_template" / "plans.json"

        s1 = self.round(1, q)                                                      # 第 1 輪：降級＋難例
        self.assertEqual(s1["degraded"], ["plan_template: 主角|舊車票 不在表上，用 default"])
        cases = [json.loads(l) for l in (director / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 1)
        self.assertEqual((cases[0]["status"], cases[0]["round"], cases[0]["input"]["switches"]["prop"]), ("open", 1, "舊車票"))
        self.assertEqual(cases[0]["brief"]["scene"]["switches"]["prop"], "舊車票")             # teach 要的稿紙一起收
        self.assertEqual(jload(director / "_metainfo")["hard_cases"]["counter_open"], 1)
        self.ex("record", 1)                                                       # 重跑不重收
        self.assertEqual(len((director / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(len(jload(plans)["plans"]), 4)

        (self.F / "changes").mkdir()
        (self.F / "changes" / "1.json").write_text(json.dumps({"round": 1, "moves": [{"kind": "teach"}, {"kind": "edit_prompt"}]}),
                                                   encoding="utf-8")
        self.ex("apply", 1)
        ch = jload(self.F / "changes" / "1.json")
        self.assertEqual([m["status"] for m in ch["moves"]], ["applied", "rejected"])
        self.assertEqual(ch["touched"], ["draft/tools/director/tools/plan_template", "draft/tools/director"])
        row = jload(plans)["plans"]["主角|舊車票"]
        self.assertEqual(len(jload(plans)["plans"]), 5)
        flat = json.dumps(row["beats"], ensure_ascii=False)
        self.assertIn("{heroine}", flat)
        self.assertIn("{prop}", flat)
        self.assertNotIn("宮澤柚葉", flat)
        self.assertNotIn("舊車票", flat)
        self.assertEqual(json.loads((director / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()[0])["status"], "resolved")

        s2 = self.round(2, q)                                                      # 第 2 輪：同題不再降級
        self.assertEqual(s2["degraded"], [])
        self.assertFalse((self.F / "runs" / "2" / Q / "1" / ".stack" / "director" / "hard_cases.jsonl").exists())
        g = jload(self.F / "changes" / "1.json")["gradient"]
        self.assertEqual(g["draft/tools/director"]["hard_cases.counter_open"], {"from": 1, "to": 0, "delta": -1})
        self.assertEqual(g["draft/tools/director/tools/plan_template"]["rollup.counter_rows"]["delta"], 1)
        self.assertEqual(g["."]["ratings.傲嬌.counter_degraded"]["delta"], -1)
        self.assertEqual(jload(director / "_metainfo")["hard_cases"]["counter_resolved"], 1)
        share = jload(director / "tools" / "plan_template" / "_metainfo")["gradient_share"]["1"]
        self.assertEqual(share["parts"]["draft/tools/director/tools/plan_template|rollup.counter_rows"], 1.0)
        self.assertGreater(share["gain"], 0)
        self.assertEqual(tree_hash(*watch), before)                                # 定義資料夾沒被寫（P-15）


class Gradient(unittest.TestCase):
    def test_three_kinds_and_notes(self):
        a = {"rollup": {"llm_tokens": {"val": 10082}}, "lifecycle": {"stage": "agent"}, "ratings": {"傲嬌": {"val": "ok", "rated_at": "x"},
             "human": {"tags": ["太長", "直球"], "notes": ["舊的"]}}, "round": 1}
        b = {"rollup": {"llm_tokens": {"val": 9700}}, "lifecycle": {"stage": "tools"}, "ratings": {"傲嬌": {"val": "good", "rated_at": "y"},
             "human": {"tags": ["直球", "嘴硬"], "notes": ["舊的", "這次她有洩底"]}}, "round": 2}
        d = record.diff_meta(a, b)
        self.assertEqual(d["rollup.llm_tokens.val"], {"from": 10082, "to": 9700, "delta": -382})
        self.assertEqual(d["lifecycle.stage"], {"from": "agent", "to": "tools"})
        self.assertEqual(d["ratings.human.tags"], {"added": ["嘴硬"], "removed": ["太長"]})
        self.assertEqual(d["ratings.human.notes"], {"notes": ["這次她有洩底"]})
        self.assertNotIn("ratings.傲嬌.rated_at", d)
        self.assertNotIn("round", d)
        self.assertEqual(record.good_of("rollup.llm_tokens.val", d["rollup.llm_tokens.val"], POLARITY), 382)
        self.assertEqual(record.good_of("ratings.傲嬌.val", d["ratings.傲嬌.val"], POLARITY), 1)

    def test_gradient_walks_up(self):
        before = {".": {"x": 1}, "draft": {"x": 1}, "draft/tools": {}, "draft/tools/writer": {"x": 1}, "draft/tools/writer/tools/trim": {"x": 1},
                  "judge": {"x": 1}}
        after = {".": {"x": 2}, "draft": {"x": 2}, "draft/tools": {}, "draft/tools/writer": {"x": 2}, "draft/tools/writer/tools/trim": {"x": 2},
                 "judge": {"x": 9}}
        g = record.gradient(before, after, ["draft/tools/writer/tools/trim"])
        self.assertEqual(sorted(g), [".", "draft", "draft/tools/writer", "draft/tools/writer/tools/trim"])   # 沒變的那層與旁枝不列

    def test_share_all_to_only_tool(self):
        grad = {"draft/tools/writer/tools/trim": {}, "draft/tools/writer": {"rollup.llm_tokens.val": {"from": 10082, "to": 9700, "delta": -382}},
                ".": {"ratings.傲嬌.反差": {"from": 0.7, "to": 0.75, "delta": 0.05}}}
        per, gain = record.shares(grad, ["draft/tools/writer/tools/trim"], {}, "galtxt-b", POLARITY, 2000)
        parts = per["draft/tools/writer/tools/trim"]["parts"]
        self.assertEqual(set(parts.values()), {1.0})
        self.assertEqual(len(parts), 2)
        self.assertAlmostEqual(gain, (382 + 0.05) / 2, places=3)

    def test_share_by_contribution(self):
        metas = {"draft/tools/writer/tools/trim": {"contribution": {"galtxt-b": {"dims": {"反差": -0.1, "承接": 0.0}}}},
                 "draft/tools/writer/tools/hand_over": {"contribution": {"galtxt-b": {"dims": {"反差": -0.3, "承接": -0.2}}}}}
        tools = sorted(metas)
        grad = {".": {"ratings.傲嬌.反差": {"from": 0.7, "to": 0.8, "delta": 0.1},
                      "ratings.傲嬌.承接": {"from": 0.7, "to": 0.8, "delta": 0.1},
                      "rollup.llm_tokens.val": {"from": 100, "to": 90, "delta": -10}}}
        per, _ = record.shares(grad, tools, metas, "galtxt-b", POLARITY, 0)
        h, t = per["draft/tools/writer/tools/hand_over"]["parts"], per["draft/tools/writer/tools/trim"]["parts"]
        self.assertEqual((h[".|ratings.傲嬌.反差"], t[".|ratings.傲嬌.反差"]), (0.75, 0.25))     # |−0.3| : |−0.1|
        self.assertEqual((h[".|ratings.傲嬌.承接"], t[".|ratings.傲嬌.承接"]), (1.0, 0.0))
        self.assertEqual((h[".|rollup.llm_tokens.val"], t[".|rollup.llm_tokens.val"]), (round(0.5 / 0.6, 4), round(0.1 / 0.6, 4)))   # 沒細項名＝Σ|dims|


class Pick(unittest.TestCase):
    def test_lambda_gain(self):
        rule = json.loads((TRAIN / "pick" / "pick_rule.json").read_text(encoding="utf-8"))
        ratings = {"反差": 0.5, "承接": 0.9}
        base = {"uses_llm": True, "responsible_for": ["反差"]}
        a = dict(base)
        b = dict(base, gradient_share={"1": {"gain": 0.5}, "2": {"gain": 3.0}})                  # 取最新一輪
        ranked = pick.pick_subtree({"a": a, "b": b, "lint": {"frozen": True}}, ratings, rule, "galtxt-b")
        self.assertEqual([p for _, p, _ in ranked], ["b", "a"])
        self.assertAlmostEqual(ranked[0][0] - ranked[1][0], rule["λ_gain"] * 0.75, places=4)
        off = dict(rule, λ_gain=0)                                                              # λ_gain 0＝兩棵同分
        self.assertEqual(pick.subtree_score(a, ratings, off, "galtxt-b")[0], pick.subtree_score(b, ratings, off, "galtxt-b")[0])


class Template(unittest.TestCase):
    def test_names_back_to_placeholders(self):
        brief = {"cast": [{"role": "hero", "display": "主角"}, {"role": "heroine", "display": "宮澤柚葉"}],
                 "scene": {"switches": {"first_speaker": "主角", "prop": "舊車票"}}, "must_mention": [["新書", "進新書日"], ["舊車票"]]}
        plan = {"beats": [{"beat": "B2", "who": "主角", "do": "主角調侃宮澤柚葉挑太多", "must": ["進新書日"]},
                          {"beat": "B4", "who": "宮澤柚葉", "do": "遞出舊車票", "must": ["舊車票"]}]}
        got = apply_mod.to_template(plan, brief)
        self.assertEqual(got["beats"][0], {"beat": "B2", "who": "{hero}", "do": "{hero}調侃{heroine}挑太多", "must": ["{m0}"]})
        self.assertEqual(got["beats"][1]["must"], ["{prop}"])


if __name__ == "__main__":
    unittest.main()
