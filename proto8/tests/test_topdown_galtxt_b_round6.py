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
optimize = load_entry(TRAIN / "optimize" / "_entry", "galtxt_b_optimize")
rollup_mod = load_entry(TRAIN / "record" / "rollup.py", "galtxt_b_rollup_t")
Q4 = "新書_宮澤_主角先_梅花章"


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


class StructuredScene(unittest.TestCase):
    """10-25 結構化（plan/runs/round6/structured.md）：tables 一格一事實、brief 照 _layout 組回舊形狀。
    brief.json（拿掉 cells_used）跟改前逐字相同（四題＋examples 兩題＋關 samples）、格 id 唯一、cells_used 指得到表裡的格與稿紙的位置、
    改一格只動引用它的欄位、lint 違規帶 cell（不改分數）、事件 {ref} 由格組出跟題目散文相同。"""
    TABLES = GB / "brief" / "tables"
    BEFORE = GB / "plan" / "runs" / "round6" / "structured" / "before"
    QS = sorted((GB / "train" / "set").glob("*.json")) + sorted((GB / "examples").glob("*.json"))

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.k = 0

    def brief(self, q, brief_dir=GB / "brief", env=None):
        self.k += 1
        ws = self.tmp / ("b%d" % self.k)
        (ws / "new").mkdir(parents=True)
        (ws / ".stack").mkdir()
        name, q = (q.stem, q.read_text(encoding="utf-8")) if isinstance(q, Path) else ("x", q)      # 題名進 brief.name
        (ws / "new" / (name + ".json")).write_text(q if isinstance(q, str) else json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, brief_dir, env=dict({"AOS_STACK": str(ws / ".stack") + "/"}, **(env or {})), cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return jload(ws / ".stack" / "brief.json")

    @staticmethod
    def text(b):
        return json.dumps({k: v for k, v in b.items() if k != "cells_used"}, ensure_ascii=False, indent=1)

    @staticmethod
    def at(doc, pointer):                                # JSON 指標 → 值
        for part in pointer.split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            doc = doc[int(part)] if isinstance(doc, list) else doc[part]
        return doc

    def cell(self, cid):                                 # 格 id → 表裡那一格（陣列裡的格以 id／beat／benchmark 或字串本身當段）
        table, *path = cid.split("/")
        doc = jload(self.TABLES / (table + ".json"))
        for seg in path:
            seg = seg.replace("~1", "/").replace("~0", "~")
            if isinstance(doc, dict):
                doc = doc[seg]
            else:
                doc = next(x for x in doc if x == seg or (isinstance(x, dict) and seg in (x.get("id"), x.get("beat"), x.get("benchmark"))))
        return doc

    @staticmethod
    def flat(doc, at=""):                                # 稿紙攤平成 {指標: 純量}
        if isinstance(doc, dict):
            return {k: v for key, x in doc.items() for k, v in StructuredScene.flat(x, at + "/" + key.replace("~", "~0").replace("/", "~1")).items()}
        if isinstance(doc, list):
            return {k: v for i, x in enumerate(doc) for k, v in StructuredScene.flat(x, "%s/%d" % (at, i)).items()}
        return {at: doc}

    def test_brief_verbatim(self):
        self.assertEqual(len(self.QS), 6)
        for p in self.QS:
            with self.subTest(q=p.stem):
                b = self.brief(p)
                self.assertEqual(self.text(b), (self.BEFORE / (p.stem + ".json")).read_text(encoding="utf-8").rstrip("\n"))
                self.assertTrue(b["cells_used"])
        b = self.brief(self.QS[0], env={"GALTXT_OFF_SAMPLES": "1"})
        self.assertEqual(self.text(b), (self.BEFORE / (self.QS[0].stem + ".off_samples.json")).read_text(encoding="utf-8").rstrip("\n"))
        self.assertFalse([c for c in b["cells_used"] if c.startswith("samples/")])

    def test_ids_unique(self):
        def no_dup(pairs):
            keys = [k for k, _ in pairs]
            self.assertEqual(len(keys), len(set(keys)), keys)
            return dict(pairs)
        cards = 0
        for p in self.TABLES.glob("*.json"):
            t = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=no_dup)     # 同一層重複的鍵＝格 id 撞號
            for name, c in t.items():
                if isinstance(c, dict) and c.get("_format") == "cells/1":
                    cards += 1
                    self.assertIn("_layout", c)
            for side in ("openers", "closers"):
                ids = [x["id"] for x in t.get(side, [])] if p.stem == "openers" else []
                self.assertEqual(len(ids), len(set(ids)))
            for tier in ("A", "B", "C") if p.stem == "banned" else ():
                self.assertEqual(len(t[tier]), len(set(t[tier])))                     # 禁詞一詞一格：詞本身是鍵
        self.assertEqual(cards, 4)                                                    # 主角、宮澤柚葉、河鹿堂、進新書日
        cast = jload(self.TABLES / "cast.json")
        self.assertNotIn("_format", cast["森下晴子"])                                   # 停用的卡不動
        self.assertNotIn("_format", cast["木下柚葉"])

    def test_cells_used_point_to_cells(self):
        for p in self.QS:
            b = self.brief(p.read_text(encoding="utf-8"))
            with self.subTest(q=p.stem):
                ids = list(b["cells_used"])
                self.assertEqual(len(ids), len(set(ids)))
                for cid, ats in b["cells_used"].items():
                    c = self.cell(cid)                                                   # 表裡指得到
                    v = c.get("text", c.get("value")) if isinstance(c, dict) and ("text" in c or "value" in c) else c
                    for a in ats:
                        got = self.at(b, a)                                              # 稿紙裡指得到
                        if isinstance(v, (str, int)) and not isinstance(got, (dict, list)):
                            if isinstance(v, int) or "{" not in str(v):
                                self.assertIn(str(v), str(got), (cid, a))               # 單格＝相等；模板格＝是那段文字的一部分
                if "宮澤" in p.stem:
                    self.assertIn("events/進新書日/beats/shove", ids)                    # 事件散文對得上事件卡
                    self.assertIn("events/進新書日/props/%s" % ("集章冊" if "集章冊" in p.stem else "梅花章"), ids)
                    self.assertIn("cast/宮澤柚葉/catchphrases/not_for_you", ids)
                else:
                    self.assertIn("cast/森下晴子", ids)                                  # 舊卡整張一格
                    self.assertFalse([c for c in ids if c.startswith("events/")])

    def test_one_cell_change_is_local(self):
        q = self.QS[0].read_text(encoding="utf-8")
        before = self.brief(q)
        import shutil                                    # 只這個 class 用（本檔上方的 import 別人在動，不改）
        bd = self.tmp / "brief"
        shutil.copytree(GB / "brief", bd)
        cast = json.loads((bd / "tables" / "cast.json").read_text(encoding="utf-8"))
        cast["宮澤柚葉"]["catchphrases"]["not_for_you"]["text"] = "哼，又不是特地等你"          # 只動口癖那一格
        (bd / "tables" / "cast.json").write_text(json.dumps(cast, ensure_ascii=False), encoding="utf-8")
        after = self.brief(q, bd)
        fb, fa = self.flat({k: v for k, v in before.items() if k != "cells_used"}), self.flat({k: v for k, v in after.items() if k != "cells_used"})
        changed = {k for k in fb.keys() | fa.keys() if fb.get(k) != fa.get(k)}
        self.assertEqual(changed, set(before["cells_used"]["cast/宮澤柚葉/catchphrases/not_for_you"]))
        self.assertEqual(changed, {"/cast/1/catchphrases/0"})
        # 事件的一拍同理：只動 /scene/event？題目散文不變＝對不上事件卡，那些格就不記（表示法跟題目脫鉤會被看見）
        ev = json.loads((bd / "tables" / "events.json").read_text(encoding="utf-8"))
        ev["進新書日"]["beats"]["accept"] = "主角嘆了口氣答應"
        (bd / "tables" / "events.json").write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
        b = self.brief(q, bd)
        self.assertEqual(b["scene"], before["scene"])
        self.assertFalse([c for c in b["cells_used"] if c.startswith("events/")])

    def test_event_ref(self):
        for p in self.QS[:4]:
            q = json.loads(p.read_text(encoding="utf-8"))
            prose = q["event"]
            q["event"] = {"ref": "進新書日"}
            b = self.brief(q)
            with self.subTest(q=p.stem):
                self.assertEqual(b["scene"]["event"], prose)
        q["event"] = {"ref": "沒有這個事件"}
        ws = self.tmp / "bad"
        (ws / "new").mkdir(parents=True)
        (ws / ".stack").mkdir()
        (ws / "new" / "x.json").write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB / "brief", env={"AOS_STACK": str(ws / ".stack") + "/"}, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^brief: SceneBad \S")

    def lint(self, text, brief):
        r = run(EXEC, GB / "lib" / "lint", input=json.dumps({"text": text, "brief": brief}, ensure_ascii=False), cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_lint_cells(self):
        b = self.brief(self.QS[0].read_text(encoding="utf-8"))
        text = "\n".join(["（推開門，是連鎖書店的味道。）",
                          "主角：「宮澤，挑這麼多？」",
                          "宮澤柚葉：「佐伯，才不是為了你！才不是為了你！別誤會了！」",
                          "主角：「笑死，進新書日、河鹿堂都一樣。」",
                          "宮澤柚葉：「哼。」", "主角：「好。」", "宮澤柚葉：「嗯。」"])
        got = self.lint(text, b)
        cells = {(v["rule"], v.get("cell"), v.get("limit_cell")) for v in got["violations"]}
        self.assertIn(("banned_C", "banned/C/笑死", None), cells)
        self.assertIn(("place_canon", "places/河鹿堂/wrong_names/chain_store", None), cells)
        self.assertIn(("address", "address/heroine_to_hero/1/forbidden/surname_bare", None), cells)
        self.assertIn(("exclaim", "cast/宮澤柚葉/budget/exclaim_max", None), cells)
        self.assertIn(("catchphrase", "cast/宮澤柚葉/catchphrases/not_for_you", "cast/宮澤柚葉/budget/catchphrase_max"), cells)
        old = self.lint(text, {k: v for k, v in b.items() if k != "cells_used"})                # 舊稿紙：不帶 cell、違規其餘一模一樣
        self.assertFalse([v for v in old["violations"] if "cell" in v or "limit_cell" in v])
        strip = [{k: v for k, v in x.items() if k not in ("cell", "limit_cell")} for x in got["violations"]]
        self.assertEqual(strip, old["violations"])
        q01 = self.brief((GB / "examples" / "q01_河鹿堂讓書.json").read_text(encoding="utf-8"))
        v = self.lint("森下晴子：「！」\n" * 5 + "主角：「好。」", q01)["violations"]
        self.assertIn("cast/森下晴子", {x.get("cell") for x in v if x["rule"] == "exclaim"})      # 停用的舊卡：指到整張


class ArbiterOptimize(unittest.TestCase):
    """round6 §7-6：判斷器（假腦固定選 a、規則表）、optimize 一步兩條→判斷器→apply 被選的、record 記 judgments（accuracy、≥ 8 次固化）；
    §7-7 漂移假腦全 0；freeze_order／patch_act 在 writer 上真的生效（假腦）。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.T = Path(self._t.name)
        self.F = self.T / "field"
        self.stack = self.T / "stack"
        self.F.mkdir()
        self.stack.mkdir()

    def ex(self, cell, n, env=None):
        (self.stack / "round.json").write_text(json.dumps({"round": n}), encoding="utf-8")
        r = run(EXEC, "--ws", self.F, TRAIN / cell, env=dict(env or {}, AOS_STACK=str(self.stack) + "/"), cwd=self._t.name, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def round(self, n, env=None, qs=None):
        qs = qs or sorted(p.stem for p in (self.F / "set").glob("*.json"))
        for q in qs:
            ws = self.F / "runs" / str(n) / q / "1"
            (ws / "new").mkdir(parents=True)
            (ws / "new" / (q + ".json")).write_text((self.F / "set" / (q + ".json")).read_text(encoding="utf-8"), encoding="utf-8")
            r = run(EXEC, "--ws", ws, self.F / "tree", env=env, cwd=self._t.name, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr)
            (ws / "run.json").write_text(json.dumps({"code": 0}), encoding="utf-8")
        self.ex("score", n)
        self.ex("record", n)

    def ask(self, adir, question, env=None):
        ws = self.T / ("aws%d" % len(list(self.T.glob("aws*"))))
        (ws / "new").mkdir(parents=True)
        (ws / "new" / "1.json").write_text(json.dumps(question, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, adir, env=dict(env or {}, AOS_STACK=str(ws) + "/.s/"), cwd=self._t.name, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return jload(ws / "out" / "1.txt")

    QUESTION = {"node": "draft/tools/writer",
                "a": {"move": {"kind": "freeze_order"}, "expected": {".": {"rollup.measured.llm_tokens": {"from": 20000, "to": 19200, "delta": -800}}}},
                "b": {"move": {"kind": "patch_act"}, "expected": {".": {"rollup.measured.llm_tokens": {"from": 20000, "to": 19900, "delta": -100}}}}}

    def test_arbiter_fake_and_rules(self):
        v = self.ask(TRAIN / "arbiter", self.QUESTION)
        self.assertEqual((v["better"], v["by"]), ("a", "fake"))
        self.assertTrue(v["why"])
        self.assertIn("llm_tokens", v["weights_used"])
        self.assertEqual(self.ask(TRAIN / "arbiter", self.QUESTION, env={"GALTXT_FAKE_ARBITER": "b"})["better"], "b")
        adir = self.T / "arb"                                                          # 固化後：規則表分得出就不問腦
        import shutil
        shutil.copytree(TRAIN / "arbiter", adir)
        (adir / "priority_rules.json").write_text(json.dumps({"weights": {"llm_tokens": 1.0}, "polarity": POLARITY, "tie": 0.05}), encoding="utf-8")
        v = self.ask(adir, self.QUESTION, env={"GALTXT_FAKE_ARBITER": "b"})
        self.assertEqual((v["better"], v["by"]), ("a", "rules"))
        tie = json.loads(json.dumps(self.QUESTION))
        tie["b"]["expected"]["."]["rollup.measured.llm_tokens"]["delta"] = -800
        self.assertEqual(self.ask(adir, tie, env={"GALTXT_FAKE_ARBITER": "b"})["by"], "fake")   # 平手才問腦

    def judgment_ws(self, m, chosen, ga, gb=None):
        """手組一步：changes/<m>.json（arbiter 選 chosen、實測 gradient＝被選的）＋可選的 side/<m>-<另一條>/。"""
        (self.F / "changes").mkdir(exist_ok=True)
        other = "b" if chosen == "a" else "a"
        exp = {".": {"rollup.measured.llm_tokens": {"from": 20000, "to": 19000, "delta": -1000}}}
        (self.F / "changes" / ("%d.json" % m)).write_text(json.dumps({
            "round": m, "moves": [{"kind": "x"}], "candidates": [{"label": "a", "expected": exp}, {"label": "b", "expected": exp}],
            "arbiter": {"better": chosen, "why": ["t"], "weights_used": {"llm_tokens": 0.6, "total_mean": 0.4}}, "gradient": ga}), encoding="utf-8")
        if gb is not None:
            p = self.F / "side" / ("%d-%s" % (m, other)) / "changes"
            p.mkdir(parents=True)
            (p / ("%d.json" % m)).write_text(json.dumps({"gradient": gb}), encoding="utf-8")

    @staticmethod
    def g(tokens_delta, total_delta=0.0):
        return {".": {"rollup.measured.llm_tokens": {"from": 20000, "to": 20000 + tokens_delta, "delta": tokens_delta},
                      "ratings.傲嬌.total_mean": {"from": 5, "to": 5 + total_delta, "delta": total_delta}}}

    def test_judgments_accuracy_and_solidify(self):
        import shutil
        shutil.copytree(TRAIN / "arbiter", self.F / "arbiter")
        self.judgment_ws(0, "a", self.g(-2000), self.g(-100))                          # 對：a 省得多（差 ≥ 改前的 5%）
        self.assertTrue(record.write_judgment(str(self.F), 1))
        self.assertFalse(record.write_judgment(str(self.F), 1))                        # 同一步不重記
        self.judgment_ws(1, "a", self.g(-100), self.g(-100, total_delta=1.0))          # 錯：b 分數高 1
        record.write_judgment(str(self.F), 2)
        self.judgment_ws(2, "b", self.g(500))                                          # 只測被選的：partial，預期省、實際多花＝沒中
        record.write_judgment(str(self.F), 3)
        j = jload(self.F / "arbiter" / "_metainfo")["ratings"]["judgments"]
        self.assertEqual([x["verdict"] for x in j["items"]], ["correct", "wrong", "partial"])
        self.assertEqual((j["counter_full"], j["counter_correct"], j["accuracy"]), (2, 1, 0.5))
        self.assertEqual((j["counter_partial"], j["expectation_held"]), (1, 0.0))
        self.assertIsNone(j["human_agreement"])
        self.assertFalse((self.F / "arbiter" / "priority_rules.json").exists())
        for m in range(3, 8):                                                          # 第 8 次 → 規則表、stage script
            self.judgment_ws(m, "a", self.g(-1000))
            record.write_judgment(str(self.F), m + 1)
        rules = jload(self.F / "arbiter" / "priority_rules.json")
        self.assertEqual(rules["weights"], {"llm_tokens": 0.6, "total_mean": 0.4})
        self.assertEqual(rules["order"], ["llm_tokens", "total_mean"])
        meta = jload(self.F / "arbiter" / "_metainfo")
        self.assertEqual(meta["lifecycle"]["stage"], "script")
        self.assertEqual(meta["ratings"]["judgments"]["counter_judgments"], 8)

    def test_optimize_two_candidates_arbiter_apply_drift(self):
        nopath = {"GALTXT_FAKE_LINT": "nopath"}
        self.ex("init", 0)
        for d in ("arbiter", "critic_v0", "tree_v0", "v0_drafts"):
            self.assertTrue((self.F / d).is_dir(), d)
        self.round(1, nopath)                                                          # 假腦漏給 brief_path → lint ArgumentsBad
        wpath = self.F / "tree" / "draft" / "tools" / "writer" / "_metainfo"
        tools = jload(wpath)["rollup"]["measured"]["tools"]
        self.assertEqual((tools["lint"]["counter_runs"], tools["lint"]["counter_argbad"]), (4, 4))
        w = jload(wpath)                                                               # 手補 trim 的觀測（假腦這輪沒叫 trim）：4/4 次都叫
        w["rollup"]["measured"]["tools"]["trim"] = {"counter_runs": 4, "counter_runs_called": 4, "counter_calls": 4, "counter_noop": 4}
        wpath.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
        cands = optimize.propose(str(self.F / "tree"), optimize.all_metas(str(self.F / "tree")))
        self.assertEqual([(c["move"]["kind"], c["move"]["tool"]) for c in cands], [("patch_act", "lint"), ("freeze_order", "trim")])
        self.ex("optimize", 1)                                                         # 假腦判斷器固定選 a＝patch_act
        ch = jload(self.F / "changes" / "1.json")
        self.assertEqual(ch["arbiter"]["better"], "a")
        self.assertEqual([c["label"] for c in ch["candidates"]], ["a", "b"])
        self.assertLess(ch["candidates"][0]["expected"]["draft/tools/writer"]["rollup.measured.tools.lint.counter_argbad"]["delta"], 0)
        self.assertEqual([m["kind"] for m in ch["moves"]], ["patch_act"])
        self.ex("apply", 1)
        ch = jload(self.F / "changes" / "1.json")
        self.assertEqual(ch["moves"][0]["status"], "applied")
        self.assertEqual(jload(self.F / "tree" / "draft" / "tools" / "writer" / "act_rules.json"),
                         {"default_args": {"lint": {"brief_path": "cur/{name}.json#/brief"}}})
        self.round(2, nopath)                                                          # act 補上 brief_path：不再 ArgumentsBad
        h = (self.F / "runs" / "2" / Q4 / "1" / ".stack" / "writer" / "history.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("ArgumentsBad", h)
        g = jload(self.F / "changes" / "1.json")["gradient"]
        self.assertEqual(g["draft/tools/writer"]["rollup.measured.tools.lint.counter_argbad"], {"from": 4, "to": 0, "delta": -4})
        j = jload(self.F / "arbiter" / "_metainfo")["ratings"]["judgments"]         # 預期 5 條 delta 中 4 條同號（假腦不會因 ArgumentsBad 多問一次，llm_calls 沒降）
        self.assertEqual((j["counter_judgments"], j["items"][0]["verdict"], j["items"][0]["expectation_held"]), (1, "partial", 0.8))
        drift = jload(self.F / "rounds" / "2.json")["drift"]                             # 假腦：漂移全 0
        self.assertEqual(drift["critic_drift"]["val"], 0)
        self.assertEqual(drift["critic_drift"]["counter_tokens"], 0)
        self.assertEqual(drift["progress"]["val"], 0)
        self.assertEqual(drift["progress"]["counter_drafts"], 2)
        self.assertEqual(drift["progress"]["critic_gap"]["val"], 0)
        self.assertEqual((drift["anchor"]["lint_delta"], drift["anchor"]["critic_delta"], drift["anchor"]["suspicious"]), (0, 0, False))
        self.assertEqual(drift["counter_tokens"], 0)
        roll = jload(self.F / "tree" / "_metainfo")["rollup"]                          # record 也寫了子樹彙總
        self.assertEqual(roll["stage_min"], "agent")
        self.assertTrue(roll["uses_llm"])

    def test_freeze_order_trims_and_guards(self):
        self.ex("init", 0)
        tree = self.F / "tree"
        (self.F / "changes").mkdir()
        moves = [{"kind": "freeze_order", "node": "draft/tools/writer", "tool": "lint", "evidence": {"counter_runs": 4, "counter_runs_called": 4}},
                 {"kind": "freeze_order", "node": "judge/tools/critic", "tool": "x"},
                 {"kind": "freeze_order", "node": "draft/tools/writer", "tool": "trim", "evidence": {"counter_runs": 10, "counter_runs_called": 8}},
                 {"kind": "patch_act", "node": "draft/tools/writer", "tool": "lint", "patch": "default_args", "args": {"nope": "x"}},
                 {"kind": "freeze_order", "node": "draft/tools/writer", "tool": "trim", "evidence": {"counter_runs": 6, "counter_runs_called": 6}}]
        (self.F / "changes" / "1.json").write_text(json.dumps({"round": 1, "moves": moves}), encoding="utf-8")
        self.ex("apply", 1)
        got = jload(self.F / "changes" / "1.json")["moves"]
        self.assertEqual([m["status"] for m in got], ["rejected", "rejected", "rejected", "rejected", "applied"])
        self.assertIn("returns: text", got[0]["why"])                                  # lint 回的是意見、不是稿
        self.assertIn("凍結", got[1]["why"])
        self.assertIn("90%", got[2]["why"])
        self.assertNotIn("工具 trim", (tree / "draft" / "tools" / "writer" / "system.txt").read_text(encoding="utf-8"))
        self.assertEqual(jload(tree / "draft" / "tools" / "writer" / "act_rules.json")["after_answer"], ["trim"])
        q = Q4
        ws = self.T / "w"
        (ws / "new").mkdir(parents=True)
        (ws / "new" / (q + ".json")).write_text((self.F / "set" / (q + ".json")).read_text(encoding="utf-8"), encoding="utf-8")
        r = run(EXEC, "--ws", ws, tree, env={"GALTXT_FAKE_TRIM": "noisy"}, cwd=self._t.name, timeout=300)    # 髒稿直接交、act 交稿前修
        self.assertEqual(r.returncode, 0, r.stderr)
        h = [json.loads(l) for l in (ws / ".stack" / "writer" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([m["role"] for m in h], ["user", "assistant"])               # 腦沒叫工具（trim 也不給它了）
        acts = [json.loads(l) for l in (ws / ".stack" / "writer" / "act.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual((acts[0]["tool"], acts[0]["after_answer"], acts[0]["code"]), ("trim", True, 0))
        self.assertGreater(acts[0]["counter_changes"], 0)
        check = jload(ws / "out" / q / "check.json")
        self.assertFalse([v for v in check["violations"] if v["rule"] in ("narration_max", "exclaim")])


class Rollup(unittest.TestCase):
    """子樹彙總：由下往上；純程式子樹 tokens 0、stage pure；捷徑照抄目標；印出模式不寫。"""

    def test_bottom_up(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "tree"

            def node(rel, meta, files=()):
                d = root / rel if rel else root
                d.mkdir(parents=True, exist_ok=True)
                (d / "_metainfo").write_text(json.dumps(dict({"summary": rel or "根"}, **meta), ensure_ascii=False), encoding="utf-8")
                for f in files:
                    (d / f).write_text("", encoding="utf-8")

            node("", {"uses_llm": True})
            node("a", {"uses_llm": False, "lifecycle": {"stage": "pure"}})
            node("a/tools", {"kind": "dir"})
            node("a/tools/x", {"uses_llm": False, "lifecycle": {"stage": "pure"}, "hard_cases": {"counter_open": 1, "counter_resolved": 2}})
            node("b", {"uses_llm": True, "llm_tokens": {"val": 900, "max": 2000}, "lifecycle": {"stage": "tools"},
                       "rollup": {"measured": {"llm_tokens": 120.0, "deterministic_score": {"score": 0.8}}}}, files=["brain.py"])
            node("b/tools", {"kind": "dir"})
            os.symlink("../../a/tools/x", root / "b" / "tools" / "x")
            node("c", {"uses_llm": True, "llm_tokens": {"val": 300, "max": 900}}, files=["ask.py"])
            node("plan", {"summary": "不算"})
            before = tree_hash(root)
            got = rollup_mod.rollup(str(root))
            self.assertEqual(tree_hash(root), before)                                   # 印出模式不寫
            by = {lab.split("  ")[0]: r for _, lab, r in got["lines"]}
            self.assertEqual((by["a"]["llm_tokens"]["val"], by["a"]["stage"], by["a"]["stage_min"], by["a"]["uses_llm"], by["a"]["deterministic_score"]),
                             (0, "pure", "pure", False, 1.0))
            self.assertEqual(by["a"]["hard_cases"], {"counter_open": 1, "counter_resolved": 2})
            self.assertEqual((by["b"]["llm_tokens"], by["b"]["stage_min"], by["b"]["deterministic_score"]),
                             ({"val": 120.0, "self": 120.0, "source": "measured"}, "tools", 0.8))
            self.assertEqual(by["c"]["llm_tokens"]["source"], "declared")
            self.assertIsNone(by["c"]["deterministic_score"])
            r = got["root"]
            self.assertEqual((r["llm_tokens"]["val"], r["llm_tokens"]["self"], r["stage_min"], r["uses_llm"]), (420.0, 0, "agent", True))
            self.assertEqual(r["hard_cases"]["counter_open"], 2)                       # a 那份＋b 底下捷徑照抄的那份
            self.assertNotIn("plan", by)
            self.assertIn("捷徑", rollup_mod.render(got["lines"]))
            rollup_mod.rollup(str(root), write=True)
            m = jload(root / "b" / "_metainfo")
            self.assertEqual(m["rollup"]["measured"]["llm_tokens"], 120.0)               # 原有的 key 保留
            self.assertEqual(m["rollup"]["stage_min"], "tools")
            self.assertEqual(jload(root / "a" / "tools" / "x" / "_metainfo")["rollup"]["stage"], "pure")
            self.assertEqual(jload(root / "b" / "tools" / "_metainfo")["rollup"]["links"], ["x → ../../a/tools/x"])


if __name__ == "__main__":
    unittest.main()
