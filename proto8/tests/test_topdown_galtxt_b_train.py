"""test_topdown_galtxt_b_train - galtxt-b 第 4 輪（plan/round4.md §8 第 1～3 項＋train/score、train/pick；10-25 使用者限縮成單一性格單一場景）：
範圍（宮澤柚葉精簡卡、一個固定場景兩個開關＝4 題、brief 的 style、語料錨只給在場女角、收尾句代入女角）、結構化分數（score.json 的 val／style／dims，
critic 的 dims 長成第 3 級、反差長在角色味底下、拆不出就不長）、train/score（rounds/<輪>.json、多樣性、delta、calibrated）、train/pick（§6b 的挑法）、
human/import（ratings.human、只動 ratings、calibration、單筆壞不擋整批）、human/ 的契約檔。全部假腦、不問腦。"""
import importlib.machinery, importlib.util, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
SET = GB / "train" / "set"
EX = GB / "examples"
A, B = "新書_宮澤_主角先_梅花章", "新書_宮澤_她先_集章冊"
Q01, Q08 = "q01_河鹿堂讓書", "q08_河鹿堂進新書日"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD", "AOS_CO",
         "GALTXT_FAKE_BAD_FIRST", "GALTXT_FAKE_LINT", "GALTXT_FAKE_BAD_PLAN", "GALTXT_FAKE_CRITIC_DIMS")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def src(q):
    """題目檔：train/set/ 的，或 examples/ 的（晴子兩題）。"""
    return SET / (q + ".json") if (SET / (q + ".json")).exists() else EX / (q + ".json")


def load_entry(path, name):
    """把沒有 .py 的 _entry 當模組載進來（只用它的純函數）；不寫 __pycache__ 進樹裡（不然那層沒有 _metainfo）。"""
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        loader = importlib.machinery.SourceFileLoader(name, str(path))
        spec = importlib.util.spec_from_loader(name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def galtxt(self, ws, q, env=None):
        """假腦把一題跑完：ws/new/<q>.json → ws/out/<q>/。"""
        (ws / "new").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src(q), ws / "new" / (q + ".json"))
        r = run(EXEC, "--ws", ws, GB, env=env, cwd=self.tmp, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return ws / "out" / q

    def brief(self, q, body=None):
        ws = self.tmp / ("b_" + q)
        (ws / "new").mkdir(parents=True)
        (ws / ".stack").mkdir()
        (ws / "new" / (q + ".json")).write_text(body if body is not None else src(q).read_text(encoding="utf-8"), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB / "brief", env={"AOS_STACK": str(ws / ".stack") + "/"}, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((ws / ".stack" / "brief.json").read_text(encoding="utf-8"))


class Scope(Base):
    def test_set_one_scene_two_switches(self):
        qs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SET.glob("*.json"))]
        self.assertEqual(len(qs), 4)
        fixed = lambda q: {k: v for k, v in q.items() if k not in ("event", "must_mention", "switches")}
        for q in qs:                                                    # 開關以外全固定
            self.assertEqual(fixed(q), fixed(qs[0]))
            self.assertEqual((q["style"], q["place"], q["cast"], q["relation_level"]), ("傲嬌", "河鹿堂", ["主角", "宮澤柚葉"], 1))
            self.assertNotIn("benchmark", q)
        self.assertEqual({(q["switches"]["first_speaker"], q["switches"]["prop"]) for q in qs},
                         {(a, b) for a in ("主角", "宮澤柚葉") for b in ("梅花章", "集章冊")})

    def test_brief_style_and_samples(self):
        b = self.brief(A)
        self.assertEqual(b["style"], "傲嬌")
        self.assertEqual([s["benchmark"] for s in b["samples"]], ["q16"])     # 只給在場女角的語氣錨
        self.assertEqual([c["display"] for c in b["cast"]], ["主角", "宮澤柚葉"])
        self.assertIn("宮澤柚葉：「嗯。……明天見。」", b["closer"])          # 鉤的收尾句代入在場女角
        b = self.brief(Q08)
        self.assertEqual([s["benchmark"] for s in b["samples"]], ["q01"])     # 晴子的、不漏自己那題
        self.assertIn("森下晴子：「嗯。……明天見。」", b["closer"])
        self.assertEqual(b["style"], "文靜")                                  # 沒寫 style＝女角卡 type 的第一個，去括號、取「／」前
        q = json.loads(src(A).read_text(encoding="utf-8"))
        del q["style"]
        self.assertEqual(self.brief("x", json.dumps(q, ensure_ascii=False))["style"], "傲嬌")

    def test_card(self):
        cast = json.loads((GB / "brief" / "tables" / "cast.json").read_text(encoding="utf-8"))
        c = self.brief(A)["cast"][1]                                            # 10-25 起表裡是 cells/1（一格一事實），看 brief 組回來的卡
        self.assertEqual(c["labels"], ["宮澤柚葉"])                              # 不放裸的「柚葉」
        self.assertEqual(c["type"], ["傲嬌（主軸）"])                            # 精簡、寫死：單一性格
        self.assertEqual(set(c) - {"address"}, set(cast["森下晴子"]))           # 照晴子那張的格
        self.assertLessEqual(len(c["catchphrases"]), 1)

    def test_set_fake_end_to_end(self):
        for p in sorted(SET.glob("*.json")):
            with self.subTest(q=p.stem):
                out = self.galtxt(self.tmp / p.stem, p.stem)
                s = json.loads((out / "score.json").read_text(encoding="utf-8"))
                self.assertTrue(s["tier0"]["pass"], (out / "check.json").read_text())
                self.assertEqual((s["style"], s["val"], s["total"]), ("傲嬌", "good", 5))


class Score(Base):
    def test_shape_deep(self):
        out = self.galtxt(self.tmp / "w", A)
        s = json.loads((out / "score.json").read_text(encoding="utf-8"))
        self.assertEqual(s["dims"], {"護欄": 1.0, "語域": 1.0, "語意": {"val": 0.67, "承接": 0.7, "含蓄": 0.6, "文筆": 0.8,
                                                                       "角色味": {"val": 0.7, "反差": 0.5}}})
        self.assertEqual((s["val"], s["max_total"], s["benchmark"]), ("good", 6, None))
        for k in ("tier0", "tier1", "tier2", "total", "register_agree", "attempt"):    # 舊讀者照讀
            self.assertIn(k, s)
        m = json.loads((out / "measure.json").read_text(encoding="utf-8"))
        self.assertEqual(m["score"]["val"], "good")

    def test_no_dims_stays_number(self):
        for mode in ("no", "bad"):
            with self.subTest(mode=mode):
                out = self.galtxt(self.tmp / mode, A, env={"GALTXT_FAKE_CRITIC_DIMS": mode})
                s = json.loads((out / "score.json").read_text(encoding="utf-8"))
                self.assertEqual(s["dims"]["語意"], 0.67)

    def test_val_ok(self):
        """第 1 稿寫壞、不給重寫（max_redrafts 0）＝定稿就是壞稿：護欄 0、語域 1（晴子的感嘆號）、語意 2 → total 3 → ok。"""
        q = json.loads(src(Q08).read_text(encoding="utf-8"))
        q["max_redrafts"] = 0
        ws = self.tmp / "w"
        (ws / "new").mkdir(parents=True)
        (ws / "new" / "壞.json").write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB, env={"GALTXT_FAKE_BAD_FIRST": "1"}, cwd=self.tmp, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads((ws / "out" / "壞" / "score.json").read_text(encoding="utf-8"))
        self.assertEqual((s["total"], s["val"], s["dims"]["護欄"], s["dims"]["語域"]), (3, "ok", 0.0, 0.5))


class TrainScore(Base):
    """train/score：訓練場 runs/<輪>/<題>/<次>/ → rounds/<輪>.json。"""

    def place(self, qs=(Q01, A), k=2, rounds=(0,)):
        p = self.tmp / "place"
        (p / "set").mkdir(parents=True, exist_ok=True)
        for q in qs:
            shutil.copyfile(src(q), p / "set" / (q + ".json"))
            for n in rounds:
                for i in range(1, k + 1):
                    w = p / "runs" / str(n) / q / str(i)
                    self.galtxt(w, q)
                    (w / "run.json").write_text('{"code": 0}')
        (p / ".stack").mkdir(exist_ok=True)
        return p

    def cell(self, p, name, round_json, root=GB / "train"):
        (p / ".stack" / "round.json").write_text(json.dumps(round_json))
        return run(EXEC, "--ws", p, root / name, env={"AOS_STACK": str(p / ".stack") + "/"}, cwd=self.tmp, timeout=30)

    def test_rounds_json(self):
        p = self.place(rounds=(0, 1))
        shutil.rmtree(p / "runs" / "1" / A / "2" / "out")                        # 一次沒交件＝failed
        r = self.cell(p, "score", {"round": 0, "k": 2})
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads((p / "rounds" / "0.json").read_text(encoding="utf-8"))
        self.assertEqual((d["round"], d["k"], len(d["runs"]), d["delta"]), (0, 2, 4, None))
        row = d["runs"][0]
        self.assertEqual((row["q"], row["k"], row["style"], row["produced_by"], row["code"]), (Q01, 1, "文靜", "draft/tools/writer", 0))
        self.assertEqual(row["answer"], "runs/0/%s/1/out/%s/answer.txt" % (Q01, Q01))
        self.assertEqual(row["scene"]["cast"], ["主角", "森下晴子"])
        self.assertEqual(d["by_q"][A]["多樣性"], 0.0)                              # 假腦兩稿一模一樣
        self.assertEqual(d["by_style"]["傲嬌"], {"val": "good", "語意": 0.67, "語域": 1.0, "護欄": 1.0, "total_mean": 5.0,
                                                "counter_samples": 2, "多樣性": 0.0, "weighted": 0.835})
        self.assertEqual((d["totals"]["counter_runs"], d["totals"]["counter_failed"]), (4, 0))
        self.assertEqual(self.cell(p, "score", {"round": 0, "k": 2}).returncode, 0)    # 算過了＝不動
        # 第 1 輪：一次失敗、有 delta；人評說傲嬌不準＝calibrated false
        (p / "human").mkdir()
        (p / "human" / "calibration.json").write_text(json.dumps({"agreement": {"by_style": {"傲嬌": 0.3, "文靜": 1.0}}}, ensure_ascii=False))
        r = self.cell(p, "score", {"round": 1, "k": 2})
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads((p / "rounds" / "1.json").read_text(encoding="utf-8"))
        self.assertEqual((d["totals"]["counter_failed"], d["by_q"][A]["counter_failed"]), (1, 1))
        self.assertTrue(d["runs"][-1]["failed"])
        self.assertNotIn("多樣性", d["by_q"][A])                                  # 只剩一稿
        self.assertNotIn("多樣性", d["by_style"]["傲嬌"])
        self.assertEqual(d["delta"]["total_mean"], 0.0)
        self.assertFalse(d["by_style"]["傲嬌"]["calibrated"])
        self.assertNotIn("calibrated", d["by_style"]["文靜"])

    def test_style_diversity_across_questions(self):
        """同一風格不同題的稿子也兩兩比：k＝1 也有風格的多樣性。"""
        p = self.place(qs=(A, B), k=1)
        self.assertEqual(self.cell(p, "score", {"round": 0, "k": 1}).returncode, 0)
        d = json.loads((p / "rounds" / "0.json").read_text(encoding="utf-8"))
        self.assertNotIn("多樣性", d["by_q"][A])
        self.assertTrue(0 < d["by_style"]["傲嬌"]["多樣性"] < 1)                    # 假腦稿只差必提詞＝很像但不一樣

    def test_errors(self):
        p = self.place(qs=(A,), k=1)
        (p / ".stack" / "round.json").unlink(missing_ok=True)
        r = run(EXEC, "--ws", p, GB / "train" / "score", env={"AOS_STACK": str(p / ".stack") + "/"}, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^score: RoundMissing \S")
        self.assertEqual(self.cell(p, "score", {"round": "0"}).returncode, 1)
        self.assertEqual(self.cell(p, "score", {"round": 5}).returncode, 0)          # 還沒跑＝退 0、不寫
        self.assertFalse((p / "rounds" / "5.json").exists())
        bad = self.tmp / "train_copy"
        shutil.copytree(GB / "train", bad)
        (bad / "score" / "weights.json").write_text('{"語意": 1}')
        r = self.cell(p, "score", {"round": 0}, root=bad)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^score: WeightsBad \S")


def fake_rounds():
    """12 筆假的每次成果：3 風格 × 2 題 × 2 次，各種分數。"""
    runs = []

    def add(q, k, style, total, sem, agree, lines):
        runs.append({"q": q, "k": k, "style": style, "scene": {"style": style}, "produced_by": "draft/tools/writer", "answer": None,
                     "counter_lines": lines,
                     "score": {"val": "good" if total >= 5 else "ok" if total >= 3 else "bad", "total": total, "max_total": 6,
                               "dims": {"護欄": 1.0}, "register_agree": agree, "tier1": {"score": 2},
                               "tier2": {"semantic": sem, "register_by_judge": 1}}})
    add("a_晴", 1, "文靜", 6, 3, True, 6)
    add("a_晴", 2, "文靜", 5, 3, True, 9)
    add("b_晴", 1, "文靜", 5, 3, True, 7)
    add("b_晴", 2, "文靜", 6, 3, True, 7)
    add("a_宮", 1, "傲嬌", 4, 1, False, 10)                # 不合（長）
    add("a_宮", 2, "傲嬌", 4, 1, False, 6)                 # 不合（短）
    add("b_宮", 1, "傲嬌", 3, 2, False, 7)                 # 不合
    add("b_宮", 2, "傲嬌", 2, 0, False, 5)                 # 不合（第 4 筆，超過 3 筆的上限）
    add("a_木", 1, "害羞", 5, 2, True, 8)
    add("a_木", 2, "害羞", 5, 2, True, 6)
    add("b_木", 1, "害羞", 1, 0, True, 6)
    add("b_木", 2, "害羞", 5, 3, True, 6)
    runs.append({"q": "c", "k": 1, "style": "文靜", "failed": True, "score": None})
    return {"round": 1, "runs": runs, "by_q": {"a_晴": {"style": "文靜", "多樣性": 0.1}, "b_晴": {"style": "文靜", "多樣性": 0.5},
                                              "a_宮": {"style": "傲嬌", "多樣性": 0.6}, "a_木": {"style": "害羞", "多樣性": 0.4}}}


class Pick(Base):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_entry(GB / "train" / "pick" / "_entry", "galtxt_pick")

    def test_order(self):
        got = [((r["q"], r["k"]), why.split("：")[0].split("（")[0]) for r, why in self.mod.pick(fake_rounds())]
        self.assertEqual(got, [
            (("b_宮", 2), "兩個評分器不合"), (("a_宮", 2), "兩個評分器不合"), (("b_宮", 1), "兩個評分器不合"),   # 短的先、最多 3
            (("a_宮", 1), "critic 給中間分"), (("a_木", 2), "critic 給中間分"),   # 每風格 1：文靜沒有中間分、傲嬌只剩長的那筆、害羞挑短的
            (("a_晴", 1), "校正錨")])                                            # 最高分兩筆同分取短的；滿 6 筆，最低那筆輪不到
        styles = {r["style"] for r, _ in self.mod.pick(fake_rounds())}
        self.assertEqual(styles, {"文靜", "傲嬌", "害羞"})

    def test_each_style_at_least_one(self):
        d = fake_rounds()
        for r in d["runs"]:                                    # 文靜全部變成最不起眼的：不合、中間分、錨都輪不到
            if r.get("style") == "文靜" and r.get("score"):
                r["score"]["total"] = 4
        chosen = self.mod.pick(d, 4)
        self.assertEqual(len(chosen), 4)
        self.assertIn("文靜", {r["style"] for r, _ in chosen})
        self.assertEqual(chosen[-1][1], "這個風格至少一筆")

    def test_cell(self):
        ws = self.tmp / "place"
        (ws / "rounds").mkdir(parents=True)
        (ws / ".stack").mkdir()
        (ws / "runs").mkdir()
        (ws / "rounds" / "1.json").write_text(json.dumps(fake_rounds(), ensure_ascii=False), encoding="utf-8")
        env = {"AOS_STACK": str(ws / ".stack") + "/"}
        (ws / ".stack" / "round.json").write_text('{"round": 1}')
        r = run(EXEC, "--ws", ws, GB / "train" / "pick", env=env, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((ws / "human" / "samples.json").exists())            # human 沒開＝不挑
        (ws / ".stack" / "round.json").write_text('{"round": 1, "human": true}')
        r = run(EXEC, "--ws", ws, GB / "train" / "pick", env=env, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads((ws / "human" / "samples.json").read_text(encoding="utf-8"))
        self.assertEqual(len(s), 6)
        self.assertEqual(s[0]["id"], "b-r1-b-宮-2")
        self.assertEqual(set(s[0]), {"id", "team", "round", "scene", "lines", "produced_by", "auto_scores", "why_picked"})
        self.assertEqual(s[0]["auto_scores"]["val"], "bad")
        self.assertEqual(s[5]["auto_scores"]["dims"]["多樣性"], 0.1)             # a_晴 的多樣性併進 dims


SAMPLES = [
    {"id": "s1", "scene": {"style": "傲嬌"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "good"}},
    {"id": "s2", "scene": {"style": "傲嬌"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "good"}},
    {"id": "s3", "scene": {"style": "傲嬌"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "ok"}},
    {"id": "s4", "scene": {"style": "文靜"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "good"}},
    {"id": "s5", "scene": {"style": "害羞"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "ok"}},
    {"id": "s6", "scene": {"style": "害羞"}, "produced_by": "draft/tools/writer", "auto_scores": {"val": "bad"}}]
RATINGS = [
    {"id": "s1", "overall": "bad", "tags": ["太直球", "稱呼不對階"], "dims": {"含蓄": 0.2}, "rated_at": "2026-10-26T01:00:00.000+00:00"},
    {"id": "s2", "overall": "bad", "tags": ["太直球"], "dims": {"含蓄": 0.4, "角色味": 0.5}, "rated_at": "2026-10-26T01:01:00.000+00:00"},
    {"id": "s3", "overall": "ok", "tags": [], "dims": {}, "rated_at": "2026-10-26T01:02:00.000+00:00"},
    {"id": "s4", "overall": "good", "tags": [], "rated_at": "2026-10-26T01:03:00.000+00:00"},
    {"id": "s5", "overall": "ok", "rated_at": "2026-10-26T01:04:00.000+00:00"},
    {"id": "s6", "overall": "ok", "tags": ["太短／沒戲"], "rated_at": "2026-10-26T01:05:00.000+00:00"},
    {"id": "沒這筆", "overall": "good"},
    {"id": "s4", "overall": "超讚"}]


class HumanImport(Base):
    def setUp(self):
        super().setUp()
        self.ws = self.tmp / "place"
        (self.ws / "human").mkdir(parents=True)
        shutil.copytree(GB, self.ws / "tree", symlinks=True, ignore=shutil.ignore_patterns("train", "plan", "human"))
        (self.ws / "human" / "samples.json").write_text(json.dumps(SAMPLES, ensure_ascii=False), encoding="utf-8")
        # 先把一個宣告 key 改壞（val > max）、排版也弄怪：import 之後原文一字不變
        top = self.ws / "tree" / "_metainfo"
        self.top_text = top.read_text(encoding="utf-8").replace('"time_ms": {"val": 26000, "max": 900000}',
                                                                '"time_ms" :  {"val": 999999999, "max": 1}')
        top.write_text(self.top_text, encoding="utf-8")

    def imp(self):
        return run(EXEC, "--ws", self.ws, GB / "human" / "import", cwd=self.tmp, timeout=30)

    def without_ratings(self, text):
        meta = json.loads(text)
        i = text.index('"ratings"')
        return text[:i], meta.get("ratings")

    def test_import(self):
        (self.ws / "human" / "ratings.json").write_text(json.dumps(RATINGS, ensure_ascii=False), encoding="utf-8")
        r = self.imp()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stderr, r"(?m)^import: SampleUnknown 沒這筆")
        self.assertRegex(r.stderr, r"(?m)^import: RatingBad s4 ")
        top = (self.ws / "tree" / "_metainfo").read_text(encoding="utf-8")
        before, ratings = self.without_ratings(top)
        self.assertEqual(before, self.without_ratings(self.top_text)[0])          # ratings 以外一字不變（含改壞的那個 key）
        self.assertTrue(top.endswith("}\n"))
        h = ratings["human"]
        self.assertEqual(h["傲嬌"], {"val": "bad", "tags": ["太直球", "稱呼不對階"], "含蓄": 0.3, "角色味": 0.5, "counter_samples": 3,
                                    "rated_at": "2026-10-26T01:02:00.000+00:00", "source": "human/import（人評：網頁勾選）"})
        self.assertEqual(h["文靜"]["val"], "good")
        self.assertEqual(h["害羞"]["val"], "ok")
        w = json.loads((self.ws / "tree" / "draft" / "tools" / "writer" / "_metainfo").read_text(encoding="utf-8"))
        self.assertEqual(w["ratings"]["human"], h)
        self.assertEqual(w["llm_model"], "chatgpt-gpt-6-luna-low")
        cal = json.loads((self.ws / "human" / "calibration.json").read_text(encoding="utf-8"))
        self.assertEqual(cal["counter_rated"], 6)
        self.assertEqual(cal["agreement"], {"overall": 0.5, "by_style": {"傲嬌": 0.333, "害羞": 0.5, "文靜": 1.0}})
        conf = {(c["auto"], c["human"]): c for c in cal["confusion"]}
        self.assertEqual(conf[("good", "bad")]["ids"], ["s1", "s2"])
        self.assertEqual(conf[("good", "bad")]["tags"], ["太直球", "稱呼不對階"])
        self.assertEqual(conf[("bad", "ok")]["ids"], ["s6"])
        self.assertTrue(any(s.startswith("傲嬌：") and "太鬆" in s for s in cal["suggest"]), cal["suggest"])
        self.assertTrue(any(s.startswith("害羞：") and "太嚴" in s for s in cal["suggest"]), cal["suggest"])
        c = json.loads((self.ws / "tree" / "judge" / "tools" / "critic" / "_metainfo").read_text(encoding="utf-8"))
        self.assertEqual((c["ratings"]["calibration"]["val"], c["ratings"]["calibration"]["counter_samples"]), (0.5, 6))
        # 重跑：除了 rated_at（沒帶時間的才用現在），結果一樣
        snap = (self.ws / "tree" / "draft" / "tools" / "writer" / "_metainfo").read_text(encoding="utf-8")
        self.assertEqual(self.imp().returncode, 0)
        self.assertEqual((self.ws / "tree" / "draft" / "tools" / "writer" / "_metainfo").read_text(encoding="utf-8"), snap)

    def test_other_style_kept(self):
        (self.ws / "human" / "ratings.json").write_text(json.dumps(RATINGS[:1], ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.imp().returncode, 0)
        (self.ws / "human" / "ratings.json").write_text(json.dumps(RATINGS[3:4], ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.imp().returncode, 0)
        h = json.loads((self.ws / "tree" / "_metainfo").read_text(encoding="utf-8"))["ratings"]["human"]
        self.assertEqual(set(h), {"傲嬌", "文靜"})                               # 別的風格不動

    def test_errors(self):
        r = self.imp()
        self.assertEqual((r.returncode, r.stderr), (0, ""))                         # 還沒人評＝什麼都不做
        self.assertFalse((self.ws / "human" / "calibration.json").exists())
        (self.ws / "human" / "ratings.json").write_text('{"id": "s1"}')
        r = self.imp()
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^import: RatingsBad \S")
        (self.ws / "human" / "ratings.json").write_text("[]")
        shutil.rmtree(self.ws / "tree")
        r = self.imp()
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^import: TreeMissing \S")


class HumanFiles(unittest.TestCase):
    def test_questions(self):
        q = json.loads((GB / "human" / "questions.json").read_text(encoding="utf-8"))
        self.assertEqual(q["overall"], ["good", "ok", "bad"])
        self.assertTrue(q["tags"] and q["dims"] and q["note"])

    def test_samples_contract(self):
        s = json.loads((GB / "human" / "samples.json").read_text(encoding="utf-8"))
        self.assertTrue(1 <= len(s) <= 6)
        self.assertEqual(len({x["id"] for x in s}), len(s))
        for x in s:
            with self.subTest(id=x["id"]):
                self.assertTrue(x["id"].startswith("b-"))
                self.assertEqual((x["team"], x["round"]), ("b", 0))
                self.assertTrue({"cast", "place", "event", "intent", "style"} <= set(x["scene"]))
                self.assertTrue(x["lines"] and all(isinstance(l, str) and l for l in x["lines"]))
                self.assertTrue((GB / x["produced_by"] / "_metainfo").exists())
                self.assertIn(x["auto_scores"]["val"], ("good", "ok", "bad"))
                self.assertTrue({"護欄", "語域", "語意"} <= set(x["auto_scores"]["dims"]))
        # 10-25 限縮：全是同一性格（傲嬌）× 同一場景（河鹿堂、主角＋宮澤柚葉、梅雨傍晚）
        self.assertEqual({(x["scene"]["style"], x["scene"]["place"], x["scene"]["season"], x["scene"]["time"], tuple(x["scene"]["cast"]))
                          for x in s}, {("傲嬌", "河鹿堂", "梅雨", "傍晚", ("主角", "宮澤柚葉"))})


if __name__ == "__main__":
    unittest.main()
