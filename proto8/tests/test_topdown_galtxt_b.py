"""test_topdown_galtxt_b - 跑 proto8/topdown/galtxt-b 第 2 輪（plan/round2.md §3 驗收）＋第 3 輪收攏（plan/round3-collapse.md §4：
director／critic 縮成單發腦函數、plan_lint 搬回 draft/tools/）：端到端（假腦）、打回重寫、writer 自檢、
lib/lint 與 draft/tools/plan_lint 每條規則各一個會紅的輸入（恰中那條、好輸入全空＝雙向）、工具自己的錯、director 表壞兩次停住再接著做（P-20）、
brief 的錯、check／deliver 重跑、samples 不漏正解、_metainfo 形狀、捷徑、metainfo_table.py；真腦（localhost:4000 連不上就 skip）。"""
import json, os, re, shutil, subprocess, tempfile, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
Q01, Q08 = "q01_河鹿堂讓書", "q08_河鹿堂進新書日"
REAL_URL = "http://localhost:4000/v1"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD",
         "GALTXT_FAKE_BAD_FIRST", "GALTXT_FAKE_LINT", "GALTXT_FAKE_BAD_PLAN")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


GOOD = """【四月午後・河鹿堂】
（推開卡卡的木門，門鈴響了一聲。舊紙的味道裡，木百葉窗把書架的陰影拉得很長。）
（假腦寫的稿：照稿紙拼的，不是真的創作。）
主角：「啊，抱歉，妳先請。」
森下晴子：「不……是我沒注意到。咦，主角同學？」
主角：「森下？原來妳也會來這家店。」
森下晴子：「嗯，因為這裡很安靜。你也在找銀河鐵道之夜嗎？」
主角：「只是順路。剛好是四月。」
森下晴子：「……這本，就讓給主角同學吧。我下次再來，等爺爺蓋好梅花章的新書進來。」
主角：「這怎麼好意思。」
森下晴子：「沒什麼。……這句，很好。」
（沒有人再說話。百葉窗的光一點一點退回去，把這個午後輕輕收了起來。）""".split("\n")


def edit(replace=None, insert=None, keep=None):
    """從 GOOD 改出一份稿：replace {行號: 新行}、insert [(插在第幾行前, 新行)]、keep [只留哪幾行]。"""
    lines = list(GOOD)
    for i, s in (replace or {}).items():
        lines[i] = s
    for i, s in sorted(insert or [], reverse=True):
        lines.insert(i, s)
    if keep is not None:
        lines = [lines[i] for i in keep]
    return "\n".join(lines)


# 每條 lint 規則一個會紅的稿（round2 §3 驗收表）
LINT_RED = {
    "format": edit(insert=[(4, "主角 妳好")]),
    "speaker": edit(insert=[(4, "柏木秋穗：「妳們好。」")]),
    "line_count": edit(keep=[0, 1, 3, 6, 8]),
    "must_mention": edit(replace={6: "森下晴子：「嗯，因為這裡很安靜。你也在找這本書嗎？」"}),
    "banned_A": edit(replace={2: "（心跳漏了一拍。）"}),
    "banned_B": edit(replace={2: "（店外飄來星巴克的味道。）"}),
    "banned_C": edit(replace={9: "主角：「笑死，這怎麼好意思。」"}),
    "place_canon": edit(replace={5: "主角：「森下？原來妳也會來這家連鎖書店。」"}),
    "address": edit(replace={4: "森下晴子：「不……是我沒注意到。咦，悠？」"}),
    "line_length": edit(replace={9: "主角：「這怎麼好意思%s」" % ("啊" * 35)}),
    "exclaim": edit(replace={10: "森下晴子：「沒什麼！……這句，很好。」"}),
    "catchphrase": edit(insert=[(11, "森下晴子：「……這句，很好。」")]),
    "narration_max": edit(insert=[(11, "（門鈴又響了一聲。）"), (11, "（爺爺的算盤響了兩下。）")]),
}

PLAN = {"beats": [
    {"beat": "B0", "who": "旁白", "do": "門鈴＋百葉窗的光，建立涼、靜、舊", "must": []},
    {"beat": "B1", "who": "旁白", "do": "兩人的手同時搭上同一本《銀河鐵道之夜》", "must": ["銀河鐵道之夜"]},
    {"beat": "B2", "who": "主角", "do": "先讓：妳先請", "must": []},
    {"beat": "B3", "who": "森下晴子", "do": "為什麼來這裡：安靜；你也喜歡宮澤賢治嗎", "must": []},
    {"beat": "B3", "who": "主角", "do": "只是想重溫、剛好是春天", "must": []},
    {"beat": "B4", "who": "森下晴子", "do": "讓書：這本讓給主角同學，下次再來", "must": ["讓給"]},
    {"beat": "B5", "who": "森下晴子", "do": "表面：沒關係的；洩底：想知道你讀完的想法", "must": []},
    {"beat": "B6", "who": "旁白", "do": "爺爺蓋梅花章", "must": []},
    {"beat": "B7", "who": "旁白", "do": "T9 定格：百葉窗的光退回去", "must": []}]}


def plan_edit(fn):
    p = json.loads(json.dumps(PLAN))
    fn(p["beats"])
    return p


PLAN_RED = {
    "grammar_no_b0": ("grammar", plan_edit(lambda b: b.pop(0))),
    "grammar_b5_before_b3": ("grammar", plan_edit(lambda b: b.insert(3, b.pop(6)))),
    "beat_unknown": ("beat_unknown", plan_edit(lambda b: b[7].update(beat="B9"))),
    "who_unknown": ("who_unknown", plan_edit(lambda b: b[3].update(who="柏木秋穗"))),
    "must_assigned": ("must_assigned", plan_edit(lambda b: b[5].update(must=[]))),
    "b6_needs_pickup": ("b6_needs_pickup", plan_edit(lambda b: b[5].update(do="讓出去：這本讓給主角同學，下次再來"))),
    "beats_count": ("beats_count", plan_edit(lambda b: b.__setitem__(slice(4, 4), [dict(b[3]), dict(b[4]), dict(b[3])]))),
}


def brain_up():
    try:
        with urllib.request.urlopen(REAL_URL + "/models", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def put(self, name=Q01, as_name=None, body=None):
        dst = self.ws / "new" / ((as_name or name) + ".json")
        if body is None:
            shutil.copyfile(GB / "examples" / (name + ".json"), dst)
        else:
            dst.write_text(body, encoding="utf-8")

    def galtxt(self, env=None, timeout=120):
        return run(EXEC, "--ws", self.ws, GB, env=env, cwd=self.tmp, timeout=timeout)

    def cell(self, name, env=None):
        """單跑一格（跟 fsm 叫它時一樣：cwd＝那一格、stack＝頂層 .stack/）。"""
        self.stack.mkdir(exist_ok=True)
        e = {"AOS_STACK": str(self.stack) + "/"}
        e.update(env or {})
        return run(EXEC, "--ws", self.ws, GB / name, env=e, cwd=self.tmp, timeout=60)

    def out(self, name, f):
        return self.ws / "out" / name / f


class EndToEnd(Base):
    def test_q01(self):
        self.put()
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("answer.txt", "score.json", "check.json", "measure.json"):
            self.assertTrue(self.out(Q01, f).exists(), f)
        score = json.loads(self.out(Q01, "score.json").read_text())
        self.assertTrue(score["tier0"]["pass"])
        self.assertFalse((self.stack / "plan.json").exists())          # deliver 一起刪了
        trace = jsonl(self.stack / "trace.jsonl")
        self.assertEqual([t["state"] for t in trace], ["idle", "brief", "draft", "check", "judge", "deliver", "idle"])
        self.assertEqual(trace[-1]["code"], 10)
        m = json.loads(self.out(Q01, "measure.json").read_text())
        self.assertEqual((m["name"], m["benchmark"], m["counter_cycles"], m["counter_drafts"], m["counter_plans"],
                          m["counter_lint_calls"], m["counter_llm_calls"]), (Q01, "q01", 1, 1, 1, 0, 3))
        self.assertEqual(set(m["cells"]), {"brief", "draft", "check", "judge", "deliver"})
        self.assertEqual({k: v["counter_llm_calls"] for k, v in m["agents"].items()}, {"director": 1, "writer": 1, "critic": 1})
        for who in ("director", "writer", "critic"):                      # 假腦也寫一行量測，形狀一致
            lines = jsonl(self.stack / who / "llm.jsonl")
            self.assertEqual(len(lines), 1)
            self.assertEqual(set(lines[0]), {"asked_at", "model", "elapsed_ms", "counter_tokens_prompt",
                                             "counter_tokens_completion", "counter_tokens", "usage"})
            self.assertEqual((lines[0]["model"], lines[0]["counter_tokens"]), ("fake", 0))
        for who in ("director", "critic"):                                 # round3：單發腦函數，小格只剩 history／current／llm／ws
            self.assertEqual([m["role"] for m in jsonl(self.stack / who / "history.jsonl")], ["user", "assistant"])
            self.assertFalse((self.stack / who / "trace.jsonl").exists() or (self.stack / who / "state.txt").exists(), who)
        # writer 拿到的題目帶 beat 表，第一則訊息有節拍表與題目檔路徑
        first = jsonl(self.stack / "writer" / "history.jsonl")[0]["content"]
        self.assertIn("【節拍表】", first)
        self.assertIn("cur/1.json#/brief", first)

    def test_q08_redraft(self):
        self.put(Q08)
        r = self.galtxt(env={"GALTXT_FAKE_BAD_FIRST": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        h = json.loads(self.out(Q08, "check.json").read_text())["history"]
        self.assertEqual([x["attempt"] for x in h], [1, 2])
        rules = {v["rule"] for v in h[0]["violations"]}
        self.assertTrue({"must_mention", "banned_A", "exclaim"} <= rules, rules)
        self.assertEqual(h[1]["violations"], [])
        self.assertEqual(len(jsonl(self.stack / "writer" / "history.jsonl")), 4)
        self.assertEqual(len(jsonl(self.stack / "director" / "history.jsonl")), 2)   # director 只問過一次：重寫沿用 plan.json
        self.assertEqual(len(jsonl(self.stack / "director" / "llm.jsonl")), 1)
        m = json.loads(self.out(Q08, "measure.json").read_text())
        self.assertEqual((m["counter_cycles"], m["counter_drafts"], m["counter_plans"], m["counter_llm_calls"]), (2, 2, 1, 4))

    def test_self_lint(self):
        self.put()
        r = self.galtxt(env={"GALTXT_FAKE_LINT": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        h = jsonl(self.stack / "writer" / "history.jsonl")
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(h[1]["tool_calls"][0]["function"]["name"], "lint")
        self.assertEqual(json.loads(h[2]["content"])["violations"], [])    # 經 brief_path 讀 cur/1.json#/brief
        self.assertTrue(h[3]["content"].startswith("【四月午後"))
        self.assertTrue((self.stack / "writer" / "lint").is_dir())
        m = json.loads(self.out(Q01, "measure.json").read_text())
        self.assertEqual((m["counter_lint_calls"], m["agents"]["writer"]["counter_llm_calls"]), (1, 2))

    def test_plan_bad_twice_then_resume(self):
        """director 的表兩次都壞＝PlanBad 停在 draft；開關關掉再跑，從 draft 接著做（P-20）。"""
        self.put()
        r = self.galtxt(env={"GALTXT_FAKE_BAD_PLAN": "2"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("draft: PlanBad ", r.stderr)
        self.assertEqual((self.stack / "state.txt").read_text().strip(), "draft")
        self.assertEqual(len(jsonl(self.stack / "director" / "history.jsonl")), 4)   # 第 2 次帶理由續聊
        self.assertIn("B0", jsonl(self.stack / "director" / "history.jsonl")[2]["content"])   # plan_lint 的理由
        self.assertFalse((self.stack / "plan.json").exists())
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.out(Q01, "answer.txt").exists())
        states = [t["state"] for t in jsonl(self.stack / "trace.jsonl")]
        self.assertEqual(states.count("brief"), 1)                        # 第二次沒有重新認領
        self.assertEqual(states[-5:], ["draft", "check", "judge", "deliver", "idle"])

    def test_plan_bad_once_recovers(self):
        """壞一次：plan_lint 的理由回給 director、第 2 張過了就往下。"""
        self.put()
        r = self.galtxt(env={"GALTXT_FAKE_BAD_PLAN": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        h = jsonl(self.stack / "director" / "history.jsonl")
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "user", "assistant"])
        self.assertIn("B0", h[2]["content"])
        self.assertEqual(json.loads(self.out(Q01, "measure.json").read_text())["counter_plans"], 2)

    def test_brief_errors(self):
        scene = json.loads((GB / "examples" / (Q01 + ".json")).read_text())
        for code, body in (("CastUnknown", dict(scene, cast=["主角", "柏木秋穗"])),
                           ("PlaceUnknown", dict(scene, place="陽溜亭")),
                           ("SceneBad", None)):
            with self.subTest(code=code):
                shutil.rmtree(self.ws)
                (self.ws / "new").mkdir(parents=True)
                self.put(body="{不是 JSON" if body is None else json.dumps(body, ensure_ascii=False))
                r = self.galtxt()
                self.assertNotEqual(r.returncode, 0)
                self.assertRegex(r.stderr, r"(?m)^brief: %s \S" % code)
                self.assertEqual(os.listdir(self.ws / "cur"), [Q01 + ".json"])   # 題目還在 cur/，修好再跑接著做

    def test_check_noop(self):
        self.put()
        for c in ("brief", "draft", "check"):
            r = self.cell(c)
            self.assertEqual(r.returncode, 0, (c, r.stderr))
        p = self.stack / "check.json"
        before, mtime = p.read_bytes(), p.stat().st_mtime_ns
        r = self.cell("check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), (before, mtime))
        c = json.loads(before)
        self.assertEqual((c["pass"], c["counter_violations_tier0"], c["counter_violations_tier1"]), (True, 0, 0))
        self.assertTrue((self.stack / "lint").is_dir())

    def test_deliver_rerun(self):
        self.put()
        for c in ("brief", "draft", "check", "judge"):
            r = self.cell(c)
            self.assertEqual(r.returncode, 0, (c, r.stderr))
        self.assertTrue((self.stack / "score.json").exists())
        r = self.cell("deliver")
        self.assertEqual(r.returncode, 0, r.stderr)
        snap = {f: self.out(Q01, f).read_bytes() for f in ("answer.txt", "score.json", "check.json", "measure.json")}
        r = self.cell("deliver")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({f: self.out(Q01, f).read_bytes() for f in snap}, snap)
        self.assertEqual(os.listdir(self.ws / "done"), [Q01 + ".json"])
        for f in ("brief.json", "plan.json", "draft.json", "check.json", "score.json", "current.txt"):
            self.assertFalse((self.stack / f).exists(), f)

    def test_brief_samples_no_leak(self):
        self.put()
        r = self.cell("brief")
        self.assertEqual(r.returncode, 0, r.stderr)
        b = json.loads((self.stack / "brief.json").read_text())
        self.assertEqual([s["benchmark"] for s in b["samples"]], ["q08"])
        self.assertNotIn("讓給主角同學", json.dumps(b["samples"], ensure_ascii=False))
        self.assertEqual(b["lines"]["narration_max"], 4)
        self.assertEqual(b["beats"]["grammar"], "B0 B1 B2 B3+ (B4) B5 (B6) B7")


class Lint(Base):
    @classmethod
    def setUpClass(cls):
        """稿紙：跑一次 q01 的 brief 格拿到的 brief.json。"""
        with tempfile.TemporaryDirectory() as t:
            ws = Path(t) / "ws"
            (ws / "new").mkdir(parents=True)
            (ws / ".stack").mkdir()
            shutil.copyfile(GB / "examples" / (Q01 + ".json"), ws / "new" / (Q01 + ".json"))
            r = run(EXEC, "--ws", ws, GB / "brief", env={"AOS_STACK": str(ws / ".stack") + "/"}, cwd=t)
            assert r.returncode == 0, r.stderr
            cls.brief = json.loads((ws / ".stack" / "brief.json").read_text())

    def tool(self, name, args, root=None):
        root = root or (GB / "draft" / "tools" if name == "plan_lint" else GB / "lib")   # round3：plan_lint 搬回 draft/tools/
        stdin = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        return run(EXEC, "--ws", self.ws, Path(root) / name, input=stdin, cwd=self.tmp, timeout=30)

    def violations(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)["violations"]

    def test_lint_rules_red(self):
        for rule, text in LINT_RED.items():
            with self.subTest(rule=rule):
                got = {v["rule"] for v in self.violations(self.tool("lint", {"text": text, "brief": self.brief}))}
                self.assertEqual(got, {rule})
        # 主角叫她名字也是 address
        text = edit(replace={5: "主角：「晴子，原來妳也會來這家店。」"})
        self.assertEqual({v["rule"] for v in self.violations(self.tool("lint", {"text": text, "brief": self.brief}))}, {"address"})

    def test_lint_good_green(self):
        r = self.tool("lint", {"text": "\n".join(GOOD), "brief": self.brief})
        out = json.loads(r.stdout)
        self.assertEqual((self.violations(r), out["counter_dialogue_lines"], out["counter_narration_lines"]), ([], 8, 3))

    def test_lint_brief_path(self):
        (self.ws / "cur").mkdir()
        (self.ws / "cur" / "1.json").write_text(json.dumps({"attempt": 1, "brief": self.brief}, ensure_ascii=False))
        self.assertEqual(self.violations(self.tool("lint", {"text": "\n".join(GOOD), "brief_path": "cur/1.json#/brief"})), [])
        got = self.violations(self.tool("lint", {"text": LINT_RED["exclaim"], "brief_path": "cur/1.json#/brief"}))
        self.assertEqual({v["rule"] for v in got}, {"exclaim"})

    def test_lint_rule_removed_goes_unnoticed(self):
        """證明紅案例真的靠那條規則：拿掉 narration_max，同一份稿就不再中（測試會紅）。"""
        lib = self.tmp / "lib"
        shutil.copytree(GB / "lib" / "lint", lib / "lint")
        p = lib / "lint" / "_entry"
        src = p.read_text(encoding="utf-8")
        cut = src.replace(', ("narration_max", 1, r_narration_max)', "")
        self.assertNotEqual(cut, src)
        p.write_text(cut, encoding="utf-8")
        got = self.violations(self.tool("lint", {"text": LINT_RED["narration_max"], "brief": self.brief}, root=lib))
        self.assertEqual(got, [])

    def assert_tool_error(self, r, name, code):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        line = r.stdout.strip()
        self.assertRegex(line, r"^%s: %s \S" % (name, code))
        self.assertIn(line, r.stderr.splitlines())                       # stderr 與 stdout 同一行

    def test_lint_errors(self):
        (self.ws / "cur").mkdir()
        (self.ws / "cur" / "1.json").write_text(json.dumps({"brief": self.brief}, ensure_ascii=False))
        (self.tmp / "x.json").write_text(json.dumps({"brief": self.brief}, ensure_ascii=False))
        for code, args in (("ArgumentsBad", "{不是 JSON"),
                           ("ArgumentsBad", {"brief": self.brief}),
                           ("ArgumentsBad", {"text": "x"}),
                           ("PathBad", {"text": "x", "brief_path": "../x.json#/brief"}),
                           ("BriefMissing", {"text": "x", "brief_path": "cur/9.json#/brief"}),
                           ("PointerMissing", {"text": "x", "brief_path": "cur/1.json#/nope"})):
            with self.subTest(code=code, args=str(args)[:40]):
                self.assert_tool_error(self.tool("lint", args), "lint", code)

    def test_plan_lint_rules_red(self):
        for case, (rule, plan) in PLAN_RED.items():
            with self.subTest(case=case):
                got = {v["rule"] for v in self.violations(self.tool("plan_lint", {"plan": plan, "brief": self.brief}))}
                self.assertEqual(got, {rule})
        three = {"beats": PLAN["beats"][:3]}
        got = {v["rule"] for v in self.violations(self.tool("plan_lint", {"plan": three, "brief": self.brief}))}
        self.assertIn("beats_count", got)

    def test_plan_lint_good_green(self):
        r = self.tool("plan_lint", {"plan": PLAN, "brief": self.brief})
        self.assertEqual((self.violations(r), json.loads(r.stdout)["counter_beats"]), ([], 9))
        # 連著同名的幾拍算一拍；c3：B6 跟 B5 對調也合法
        swapped = plan_edit(lambda b: b.insert(6, b.pop(7)))
        self.assertEqual(self.violations(self.tool("plan_lint", {"plan": swapped, "brief": self.brief})), [])

    def test_plan_lint_errors(self):
        self.assert_tool_error(self.tool("plan_lint", {"brief": self.brief}), "plan_lint", "ArgumentsBad")
        self.assert_tool_error(self.tool("plan_lint", {"plan": PLAN, "brief_path": "../x.json#/brief"}), "plan_lint", "PathBad")


META_NUM = ("time_ms", "llm_calls", "llm_tokens", "mem_mb", "cost")


def meta_problems(meta, is_fn):
    """round2 §3「_metainfo 形狀」：回問題清單（空＝合格）。"""
    bad = []
    if not isinstance(meta, dict):
        return ["不是 JSON 物件"]
    if not isinstance(meta.get("summary"), str) or not meta["summary"]:
        bad.append("沒有 summary")
    if is_fn and "time_ms" not in meta:
        bad.append("函數沒有 time_ms")
    res = meta.get("resource")
    if "llm" in (res if isinstance(res, list) else [res]):
        bad += ["resource 有 llm 卻沒有 %s" % k for k in ("llm_calls", "llm_tokens", "llm_endpoint", "llm_model") if k not in meta]
    for k in META_NUM:
        if k not in meta:
            continue
        v = meta[k]
        if isinstance(v, dict):
            if not all(isinstance(v.get(x), (int, float)) for x in ("val", "max")) or v["val"] > v["max"]:
                bad.append("%s 要 {val, max} 且 val ≤ max：%r" % (k, v))
        elif not isinstance(v, (int, float)) or isinstance(v, bool):
            bad.append("%s 不是數字：%r" % (k, v))
    return bad


class Shape(unittest.TestCase):
    def test_metainfo_everywhere(self):
        seen = 0
        for d, dirs, files in os.walk(GB):
            rel = os.path.relpath(d, GB)
            dirs[:] = [x for x in dirs if not x.startswith(".") and not (rel == "." and x == "plan")]
            with self.subTest(dir=rel):
                self.assertIn("_metainfo", files)
                meta = json.loads(Path(d, "_metainfo").read_text(encoding="utf-8"))
                self.assertEqual(meta_problems(meta, "_entry" in files), [])
                seen += 1
            for n in files:
                if n.endswith(".json") and n != "_metainfo.json":
                    js = json.loads(Path(d, n).read_text(encoding="utf-8"))
                    for st in (js.get("states") or {}).values() if isinstance(js, dict) else []:
                        ex = st.get("exec")
                        if isinstance(ex, dict) and "_metainfo" in ex:
                            with self.subTest(file=os.path.join(rel, n)):
                                self.assertEqual(meta_problems(ex["_metainfo"], True), [])
        self.assertGreater(seen, 20)

    def test_metainfo_checker_goes_red(self):
        self.assertEqual(meta_problems({"summary": "x", "time_ms": {"val": 1, "max": 2}}, True), [])
        self.assertTrue(meta_problems({"time_ms": 1}, True))                                   # 沒 summary
        self.assertTrue(meta_problems({"summary": "x"}, True))                                 # 函數沒 time_ms
        self.assertTrue(meta_problems({"summary": "x", "time_ms": {"val": 3, "max": 2}}, True))
        self.assertTrue(meta_problems({"summary": "x", "time_ms": 1, "resource": ["llm"], "llm_calls": 1}, True))

    def test_links(self):
        links = {"check/tools/lint": "lib/lint", "draft/tools/writer/tools/lint": "lib/lint"}
        p = GB / "draft" / "tools" / "plan_lint"                           # round3：只有一個呼叫者，搬回來當真資料夾
        self.assertTrue(p.is_dir() and not p.is_symlink())
        self.assertTrue((p / "tool.json").exists() and os.access(p / "_entry", os.X_OK))
        self.assertFalse((GB / "lib" / "plan_lint").exists())
        for at, real in links.items():
            with self.subTest(link=at):
                p = GB / at
                self.assertTrue(p.is_symlink())
                self.assertFalse(os.path.isabs(os.readlink(p)))
                self.assertEqual(p.resolve(), (GB / real).resolve())
                self.assertTrue((p / "tool.json").exists() and os.access(p / "_entry", os.X_OK))


class MetainfoTable(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def table(self, *args):
        return run("python3", GB / "plan" / "metainfo_table.py", *args, cwd=self.tmp, timeout=30)

    def test_small_tree(self):
        root = self.tmp / "tree"
        (root / "a").mkdir(parents=True)
        (root / "plan").mkdir()
        (root / "lib" / "f").mkdir(parents=True)
        (root / "_metainfo").write_text(json.dumps({"summary": "根", "time_ms": {"val": 100, "max": 1000},
                                                    "llm_calls": {"val": 1, "max": 2}, "grow_level": 5}))
        (root / "_entry").write_text("#!/bin/sh\n")
        (root / "a" / "_metainfo.json").write_text(json.dumps({"summary": "a", "kind": "data"}))
        (root / "a" / "fsm.json").write_text(json.dumps({"states": {"think": {"exec": {"argv": ["x"], "_metainfo": {"summary": "問腦", "llm_calls": 1}}}}}))
        (root / "plan" / "_metainfo").write_text(json.dumps({"summary": "不該出現"}))
        (root / "lib" / "f" / "_metainfo").write_text(json.dumps({"summary": "f"}))
        os.symlink("../lib/f", root / "a" / "f")
        m = self.tmp / "m.json"
        m.write_text(json.dumps({"name": "q99", "elapsed_ms": 2000, "counter_llm_calls": 3, "counter_tokens": 50,
                                 "cells": {"a": {"elapsed_ms": 7}}, "agents": {}}))
        out = self.tmp / "out"
        r = self.table("--root", root, "--out", out, "--measure", m)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads((out / "metainfo_table.json").read_text())
        rows = {x["path"]: x for x in doc["rows"]}
        self.assertEqual(set(rows), {".", "a", "a/fsm.json#/states/think/exec", "a/f", "lib", "lib/f"})
        self.assertEqual((rows["."]["kind"], rows["a"]["kind"], rows["a/f"]["kind"], rows["a/fsm.json#/states/think/exec"]["kind"]),
                         ("fn", "data", "link", "單子"))
        self.assertEqual(rows["."]["other"], {"grow_level": 5})
        self.assertEqual(rows["."]["measured"], {"q99": {"time_ms": 2000, "llm_calls": 3, "llm_tokens": 50}})
        self.assertEqual(rows["."]["over_max"], ["q99 time_ms 2000>1000", "q99 llm_calls 3>2"])
        self.assertEqual(rows["a"]["measured"], {"q99": {"time_ms": 7}})
        self.assertNotIn("measured", rows["lib"])                         # 對不上的列空著
        md = (out / "metainfo_table.md").read_text()
        self.assertIn("| 實測 time_ms |", md)
        self.assertIn("q99:2000", md)
        self.assertIn("差最多", md)
        # 壞的 measure＝MeasureBad 退 1
        m.write_text("{壞")
        r = self.table("--root", root, "--out", out, "--measure", m)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^metainfo_table: MeasureBad \S")

    def test_entry_single(self):
        """round3：沒 +x 的 JSON _entry 單子收成一列；_metainfo 寫 {"$ref": "_metainfo"} 照指的讀；實測拿 agent 的「每問一次」平均對。"""
        root = self.tmp / "tree"
        (root / "draft" / "tools" / "director").mkdir(parents=True)
        d = root / "draft" / "tools" / "director"
        (root / "_metainfo").write_text(json.dumps({"summary": "根"}))
        (d / "_metainfo").write_text(json.dumps({"summary": "單發", "time_ms": {"val": 10, "max": 100}, "llm_calls": {"val": 1, "max": 1}}))
        (d / "_entry").write_text(json.dumps({"argv": ["python3", "ask.py"], "_metainfo": {"$ref": "_metainfo"}}))
        (root / "x").mkdir()
        (root / "x" / "_entry").write_text("#!/bin/sh\n")                         # sh 入口不是單子
        os.chmod(root / "x" / "_entry", 0o755)
        m = self.tmp / "m.json"
        m.write_text(json.dumps({"name": "q99", "agents": {"director": {"counter_llm_calls": 2, "counter_tokens": 300,
                                                                         "llm_elapsed_ms": 400, "elapsed_ms": 500}}}))
        out = self.tmp / "out"
        r = self.table("--root", root, "--out", out, "--measure", m)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {x["path"]: x for x in json.loads((out / "metainfo_table.json").read_text())["rows"]}
        self.assertEqual(set(rows), {".", "draft", "draft/tools", "draft/tools/director", "draft/tools/director/_entry", "x"})
        e = rows["draft/tools/director/_entry"]
        self.assertEqual((e["kind"], e["summary"], e["source"]), ("單子", "單發", "draft/tools/director/_metainfo"))
        self.assertEqual(e["measured"], {"q99": {"time_ms": 200, "llm_calls": 1, "llm_tokens": 150}})
        self.assertEqual(e["over_max"], ["q99 time_ms 200>100"])

    def test_real_tree_runs(self):
        r = self.table("--out", self.tmp / "out")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {x["path"] for x in json.loads((self.tmp / "out" / "metainfo_table.json").read_text())["rows"]}
        self.assertTrue({".", "lib/lint", "draft/tools/director", "draft/tools/writer/fsm.json#/states/think/exec",
                         "draft/tools/director/_entry", "judge/tools/critic/_entry", "draft/tools/plan_lint"} <= rows)
        self.assertFalse(any("director/fsm.json" in p or "critic/fsm.json" in p for p in rows))   # round3：5→4，沒有 fsm 了
        self.assertFalse(any(p.startswith("plan") for p in rows))


@unittest.skipUnless(brain_up(), "localhost:4000 連不上，真腦案例跳過")
class RealBrain(Base):
    def test_q01_real(self):
        self.put()
        r = self.galtxt(env={"AOS_BRAIN_URL": REAL_URL}, timeout=900)
        self.assertEqual(r.returncode, 0, r.stderr)
        score = json.loads(self.out(Q01, "score.json").read_text())
        self.assertGreaterEqual(score["total"], 4, score)
        m = json.loads(self.out(Q01, "measure.json").read_text())
        self.assertTrue(3 <= m["counter_llm_calls"] <= 11, m)
        for who in ("director", "writer", "critic"):
            for line in jsonl(self.stack / who / "llm.jsonl"):
                self.assertIsInstance(line["counter_tokens"], int)
                self.assertNotEqual(line["model"], "fake")
                self.assertNotRegex(line["model"], r"(?i)claude")          # 只准 gpt 系列當腦


if __name__ == "__main__":
    unittest.main()
