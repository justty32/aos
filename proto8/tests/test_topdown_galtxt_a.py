"""test_topdown_galtxt_a - 跑 topdown/galtxt-a（由上而下拆的 galgame 台詞管線：brief → write（寫手 agent）→ check（lint）→ judge（評審 agent）→ pick）。

規劃：proto8/topdown/galtxt-a/plan/round1.md § 6.3；第二輪收攏（round2-collapse.md § 4 第 8 步）只改路徑與讀法、斷言不改，另加 collapse 與 metatable --suggest 的測試；
第三輪（round3.md § 11 的 1～11）加 Round3T：傲嬌與 Q16、選路、writer-sol、假腦技能表、rate、optimize、整條訓練、回滾、預算、M7（會寫樹的都在拷貝上跑）。全部離線（假腦）；連真模型的那個（test_real_model）localhost:4000 連不上就 skip。"""
import json, os, shutil, statistics, subprocess, sys, tempfile, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
G = ROOT / "topdown" / "galtxt-a"
EXAMPLES = G / "plan" / "examples"
LINT = str(G / "tools" / "lint")
REAL_URL = "http://localhost:4000/v1"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
BRIEF = str(G / "fsm.json") + "#/states/brief/exec"   # 收攏後 brief 是 fsm.json 裡的內嵌單子（N-62；cwd＝galtxt-a 根）
ANSWER = json.loads((G / "data" / "bench" / "Q01.json").read_text(encoding="utf-8"))["answer"]


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def jl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def is_line(l):
    return (l.startswith("（") and l.endswith("）")) or ("：「" in l and l.endswith("」"))


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def put(self, example):
        (self.ws / "new" / example).write_text((EXAMPLES / example).read_text(encoding="utf-8"), encoding="utf-8")

    def galtxt(self, url=None, timeout=120):
        env = {"AOS_BRAIN_URL": url} if url else {}
        return run(EXEC, "--ws", "ws", str(G), env=env, cwd=self.tmp, timeout=timeout)

    def ls(self, d):
        p = self.ws / d
        return sorted(os.listdir(p)) if p.exists() else []

    # 1. 樹的形狀
    def test_tree_shape(self):
        for d, subs, files in os.walk(G):
            here = Path(d)
            subs[:] = [s for s in subs if not (here / s).is_symlink()]     # 捷徑不算（真身另外驗）
            if here.name == "tools":                                         # P-33 的容器，不是節點；裡面每個工具才是
                continue
            meta_p = here / "_metainfo"
            self.assertTrue(meta_p.is_file(), "%s 沒有 _metainfo" % here)
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            self.assertIn("summary", meta, here)
            self.assertIn("kind", meta, here)
            if meta["kind"] == "agent":
                res = meta["resource"] if isinstance(meta["resource"], list) else [meta["resource"]]
                self.assertIn("llm", res, here)
                self.assertIn("llm_calls", meta, here)
            if here.parent.name == "tools" and meta["kind"] != "agent":   # 腦可以叫的工具（P-41）：要有 tool.json
                spec = json.loads((here / "tool.json").read_text(encoding="utf-8"))
                self.assertTrue({"description", "parameters"} <= set(spec), here)
            if (here / "_entry").exists():
                e = here / "_entry"
                self.assertTrue(os.access(e, os.X_OK), "%s 不是 +x" % e)
                self.assertTrue(e.read_text(encoding="utf-8").startswith("#!"), "%s 沒有 shebang" % e)
        link = G / "writer" / "tools" / "lint"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../../tools/lint")
        self.assertEqual(link.resolve(), (G / "tools" / "lint").resolve())
        for a in ("writer", "grader"):                                       # 收攏：idle 只留一份真身（B-4）
            self.assertTrue((G / a / "idle").is_symlink(), a)
            self.assertEqual(os.readlink(G / a / "idle"), "../idle")
        second = (G / "tools" / "lint" / "_entry").read_text(encoding="utf-8").splitlines()[1]
        self.assertTrue(second.startswith("# lint - "), second)              # lib/README 契約：第二行 NAME
        for p in (G / "data").rglob("*.json"):
            js = json.loads(p.read_text(encoding="utf-8"))
            self.assertTrue("source" in js or "source" in (js.get("_metainfo") or {}), p)   # 每張表標出處（格檔放在檔內 _metainfo）

    # 2. 場景模式
    def test_scene(self):
        self.put("scene.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        lines = (self.ws / "out" / "scene" / "answer.txt").read_text(encoding="utf-8").splitlines()
        self.assertTrue(5 <= len(lines) <= 10, lines)
        for l in lines:
            self.assertTrue(is_line(l), l)
            if "：「" in l:
                self.assertIn(l.split("：「")[0], ("主角", "森下晴子"))
        score = json.loads((self.ws / "out" / "scene" / "score.json").read_text(encoding="utf-8"))
        self.assertIn("picked", score)
        self.assertEqual(len(score["drafts"]), 3)
        for d in score["drafts"]:
            self.assertTrue({"tier0", "tier1", "total"} <= set(d), d)
        self.assertEqual((self.ls("cur"), self.ls("done")), ([], ["scene.json"]))
        trace = jl(self.stack / "trace.jsonl")
        for s in ("idle", "brief", "write", "check", "judge", "pick"):
            self.assertIn(s, [t["state"] for t in trace])
        self.assertEqual((trace[-1]["state"], trace[-1]["code"]), ("idle", 10))
        for f in ("brief.json", "rules.json", "drafts/1.txt", "drafts/2.txt", "drafts/3.txt", "checks.json", "judge.json"):
            self.assertTrue((self.stack / f).is_file(), f)
        h = jl(self.stack / "writer" / "runs" / "001" / "stack" / "history.jsonl")
        self.assertTrue(any(c["function"]["name"] == "lint" for m in h for c in m.get("tool_calls") or []), h)
        self.assertTrue((self.stack / "writer" / "runs" / "001" / "stack" / "lint").is_dir())
        passed = sum(1 for c in json.loads((self.stack / "checks.json").read_text()).values() if c["pass"])
        self.assertEqual(len(os.listdir(self.stack / "judge" / "runs")), passed)
        self.assertIn(passed, (2, 3))
        drafts = {(self.stack / "drafts" / ("%d.txt" % i)).read_text() for i in (1, 2, 3)}
        self.assertEqual(len(drafts), 3)                                     # 三份字面不同

    # 3. 挖空模式 Q01
    def test_fill_q01(self):
        self.put("Q01.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (self.ws / "out" / "Q01" / "answer.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("森下晴子：「"), lines)
        for group in (["銀河鐵道之夜", "宮澤賢治"], ["讓給", "先看"]):
            self.assertTrue(any(w in lines[0] for w in group), (group, lines[0]))
        score = json.loads((self.ws / "out" / "Q01" / "score.json").read_text(encoding="utf-8"))
        self.assertIn("bigram_overlap", score["bench"])
        self.assertTrue(score["bench"]["guard_hit"])
        third = score["drafts"][2]
        self.assertIn("KeywordMissing", third["tier0"])
        self.assertEqual(third["total"], 0)
        self.assertEqual(score["picked"], 1)                                 # 1、2 同分，平手編號小的贏
        self.assertEqual([d["total"] for d in score["drafts"][:2]], [4, 4])
        self.assertEqual(len(os.listdir(self.stack / "judge" / "runs")), 2)  # 第 3 份沒過護欄，不評
        # 隔離：寫手、評審的小格裡找不到正解
        quote = ANSWER.split("：「", 1)[1]
        for sub in ("writer", "judge"):
            for p in (self.stack / sub / "runs").rglob("*"):
                if p.is_file():
                    self.assertNotIn(quote, p.read_text(encoding="utf-8"), p)
        for p in ("brief.json", "rules.json"):
            self.assertNotIn(quote, (self.stack / p).read_text(encoding="utf-8"))

    # 4. lint 單元
    def lint(self, text, rules=True, stdin=None):
        d = self.tmp / "lintws"
        d.mkdir(exist_ok=True)
        if rules:
            (d / "rules.json").write_text(json.dumps(self.rules, ensure_ascii=False), encoding="utf-8")
        return run(EXEC, "--ws", str(d), LINT, input=json.dumps({"text": text}) if stdin is None else stdin,
                   env={"AOS_STACK": str(self.tmp / "lintstack") + "/"})

    def make_rules(self, example):
        self.put(example)
        env = {"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"}
        self.stack.mkdir()
        r = run(EXEC, BRIEF, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.rules = json.loads((self.stack / "rules.json").read_text(encoding="utf-8"))

    def out(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_lint(self):
        self.make_rules("Q01.json")
        ok = "森下晴子：「既然這樣，這本《銀河鐵道之夜》就讓給主角同學吧。我下次再來呢。」"
        o = self.out(self.lint(ok))
        self.assertEqual((o["pass"], o["tier0"], o["tier1"], o["counter_lines"]), (True, [], 2, 1))
        o = self.out(self.lint("森下晴子：「既然這樣，《銀河鐵道之夜》就讓給主角同學吧。我心跳漏了一拍呢。」"))
        self.assertFalse(o["pass"])
        self.assertEqual([t["code"] for t in o["tier0"]], ["ForbiddenWord"])
        self.assertEqual(o["tier0"][0]["hit"], "心跳漏了一拍")
        o = self.out(self.lint("森下晴子：「既然這樣，《銀河鐵道之夜》就讓給悠吧。我下次再來呢。」"))
        self.assertTrue(o["pass"])                                           # 稱呼是 Tier 1：不砍只扣
        self.assertIn("AddressBad", o["tier1_notes"])
        self.assertEqual(o["tier1"], 1)
        o = self.out(self.lint("柏木秋穗：「《銀河鐵道之夜》就讓給主角同學吧呢。」"))
        self.assertIn("SpeakerUnknown", [t["code"] for t in o["tier0"]])
        o = self.out(self.lint(ok + "\n" + ok))
        self.assertIn("FormatBad", [t["code"] for t in o["tier0"]])
        o = self.out(self.lint("主角：「《銀河鐵道之夜》就讓給你吧。」"))
        self.assertIn("SpeakerWrong", [t["code"] for t in o["tier0"]])
        o = self.out(self.lint("森下晴子：「這本就讓給主角同學吧，下次去連鎖書店找呢。」"))
        self.assertEqual(sorted(t["code"] for t in o["tier0"]), ["KeywordMissing", "SettingBad"])
        for stdin, code in (("nope", "ArgumentsBad"), ("{}", "ArgumentsBad")):
            r = self.lint("", stdin=stdin)
            self.assertEqual(r.returncode, 1)
            self.assertRegex(r.stderr, r"^lint: %s \S" % code)
            self.assertEqual(r.stdout, r.stderr)                             # stdout 也印同一行（給腦看）
        (self.tmp / "lintws" / "rules.json").unlink()
        r = self.lint(ok, rules=False)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^lint: RulesMissing \S")

    def test_lint_scene(self):
        self.make_rules("scene.json")
        text = "（河鹿堂。）\n主角：「啊，抱歉。」\n森下晴子：「是嗎……主角同學。」\n主角：「森下。」\n（安靜。）"
        o = self.out(self.lint(text))
        self.assertEqual((o["pass"], o["tier1"], o["counter_lines"]), (True, 2, 5))
        o = self.out(self.lint("主角：「啊。」\n森下晴子：「是嗎。」"))
        self.assertEqual([t["code"] for t in o["tier0"]], ["FormatBad"])     # 行數不到 5
        o = self.out(self.lint(text.replace("是嗎……", "")))
        self.assertIn("VoiceMissing", o["tier1_notes"])
        self.assertEqual(o["tier1"], 1)

    # 5. 壞了停、修好接著做
    def test_stop_then_resume(self):
        self.put("Q01.json")
        r = self.galtxt("http://127.0.0.1:9/v1")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("writer: BrainFailed", r.stderr)
        self.assertIn("galtxt-a write: AgentFailed", r.stderr)
        self.assertEqual((self.stack / "state.txt").read_text(), "write\n")
        self.assertTrue((self.stack / "brief.json").is_file())
        self.assertEqual(os.listdir(self.stack / "drafts"), [])
        mtime = (self.stack / "brief.json").stat().st_mtime_ns
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.stack / "brief.json").stat().st_mtime_ns, mtime)   # brief 沒重跑
        self.assertTrue((self.ws / "out" / "Q01" / "answer.txt").is_file())
        self.assertEqual(self.ls("done"), ["Q01.json"])

    def test_write_skips_existing_drafts(self):
        self.put("Q01.json")
        env = {"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"}
        self.stack.mkdir()
        self.assertEqual(run(EXEC, BRIEF, env=env).returncode, 0)
        (self.stack / "drafts").mkdir()
        (self.stack / "drafts" / "1.txt").write_text("手寫的第一份\n", encoding="utf-8")
        r = run(EXEC, str(G / "fsm.json") + "#/states/write/exec", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(os.listdir(self.stack / "writer" / "runs")), 2)
        self.assertEqual((self.stack / "drafts" / "1.txt").read_text(encoding="utf-8"), "手寫的第一份\n")
        self.assertEqual(sorted(os.listdir(self.stack / "drafts")), ["1.txt", "2.txt", "3.txt"])

    def test_next_question_clears_old_drafts(self):
        """一次放兩題：第二題不會撿第一題的草稿（brief 換題時清 drafts／checks／judge）。"""
        self.put("Q01.json")
        self.put("scene.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ls("done"), ["Q01.json", "scene.json"])
        self.assertEqual(len((self.ws / "out" / "Q01" / "answer.txt").read_text().splitlines()), 1)
        self.assertGreaterEqual(len((self.ws / "out" / "scene" / "answer.txt").read_text().splitlines()), 5)
        self.assertEqual(len(os.listdir(self.stack / "writer" / "runs")), 6)

    # 6. _metainfo 自我一致
    def meta(self, rel):
        return json.loads((G / rel / "_metainfo").read_text(encoding="utf-8"))

    def cell_meta(self, state):
        """收攏後五格是內嵌單子：_metainfo 在 fsm.json#/states/<名>/exec/_metainfo（M1 第三處）"""
        return json.loads((G / "fsm.json").read_text(encoding="utf-8"))["states"][state]["exec"]["_metainfo"]

    def test_metainfo_consistent(self):
        top, w, j = self.meta("."), self.cell_meta("write"), self.cell_meta("judge")
        self.assertGreaterEqual(top["llm_calls"]["max"], w["llm_calls"]["max"] + j["llm_calls"]["max"])
        writer = self.meta("writer")
        loop = json.loads((G / "writer/loop.json").read_text())
        self.assertGreaterEqual(writer["llm_calls"]["max"], loop["max"] // 3)
        judge = self.meta("grader")
        loop = json.loads((G / "grader/loop.json").read_text())
        self.assertGreaterEqual(judge["llm_calls"]["max"], loop["max"] // 3)
        for d, subs, files in os.walk(G):
            here = Path(d)
            subs[:] = [s for s in subs if not (here / s).is_symlink()]
            if here.name == "tools":
                continue
            m = json.loads((here / "_metainfo").read_text(encoding="utf-8"))
            if m["kind"] in ("glue", "program") and not m.get("fs_needs"):
                self.assertEqual(sorted(os.listdir(here)), ["_entry", "_metainfo"], here)
        # 外層逾時 ≥ 內層（P-36）：fsm 格的 timeout_ms ≥ 那格 _metainfo 的 time_ms.max
        fsm = json.loads((G / "fsm.json").read_text())
        for s, cell in fsm["states"].items():
            if isinstance(cell["exec"], dict):
                self.assertGreaterEqual(cell["exec"]["timeout_ms"], self.cell_meta(s)["time_ms"]["max"], s)
        self.assertGreaterEqual(w["time_ms"]["max"], 3 * writer["time_ms"]["max"])
        self.assertGreaterEqual(j["time_ms"]["max"], 3 * judge["time_ms"]["max"])

    # 7. 真腦
    def test_real_model(self):
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=2).read()
        except OSError as e:
            self.skipTest("LiteLLM 連不上：%s" % e)
        self.put("Q01.json")
        r = self.galtxt(REAL_URL, timeout=1800)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (self.ws / "out" / "Q01" / "answer.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(json.loads((self.ws / "out" / "Q01" / "score.json").read_text())["bench"]["guard_hit"])


METATABLE = str(G / "meta" / "metatable" / "_entry")


class MetatableT(unittest.TestCase):
    """meta/metatable：把整棵樹的 _metainfo 收成一張表"""

    def test_galtxt_a_table(self):
        r = run(METATABLE, "--json", str(G))
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertGreater(len(d["nodes"]), 10)
        self.assertEqual(d["summary"]["counter_nodes"], len(d["nodes"]))
        self.assertIn("max_depth", d["summary"])
        self.assertTrue(any(n.get("kind") == "捷徑" for n in d["nodes"]))
        md = run(METATABLE, str(G))
        self.assertIn("| 節點數 |", md.stdout)

    def test_bad_json_marked_and_root_missing(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "a").mkdir()
            (Path(t) / "a" / "_metainfo").write_text("{不是 json", encoding="utf-8")
            r = run(METATABLE, "--json", t)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("metatable: MetainfoBad", r.stderr)
            nodes = json.loads(r.stdout)["nodes"]
            self.assertEqual([n["kind"] for n in nodes if n["path"] == "a"], ["壞"])
            self.assertIn("壞", run(METATABLE, t).stdout)
        r = run(METATABLE, "/不存在/的/路徑")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("metatable: RootMissing"), r.stderr)


COLLAPSE = str(G / "meta" / "collapse" / "_entry")
BEFORE_COMMIT = "2967009e"          # galtxt-a 收攏前那一版（round2-collapse.md § 3 的「前」）


def snapshot(root):
    """整棵樹：檔＝內容、捷徑＝目標字串、資料夾＝存在"""
    out = {}
    for here, subs, files in os.walk(root):
        for n in subs + files:
            p = Path(here) / n
            out[str(p.relative_to(root))] = ("L", os.readlink(p)) if p.is_symlink() else \
                (p.read_bytes(), os.access(p, os.X_OK)) if p.is_file() else "dir"
    return out


def mini_before(t):
    """收攏前長相的小樹：fsm 一格叫資料夾 a/（B-2）、box/tools/agent/（A-1 容器）、d/t/ 資料表（B-3）、兩份一樣的 idle（B-4）。"""
    t = Path(t)
    (t / "fsm.json").write_text(json.dumps({"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "a", "states": {
        "a": {"exec": {"argv": ["aos-exec", "a"], "timeout_ms": 5000}, "next": "a"}}}), encoding="utf-8")
    (t / "data.txt").write_text("資料\n", encoding="utf-8")
    (t / "a").mkdir()
    (t / "a" / "_entry").write_text(
        "#!/usr/bin/env python3\n# a - 讀 ../data.txt，寫 $AOS_WS/out.txt\nimport os\n"
        "DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), \"data.txt\")\n"
        "open(os.path.join(os.environ[\"AOS_WS\"], \"out.txt\"), \"w\").write(open(DATA).read() + os.environ.get(\"AOS_BRAIN_URL\", \"-\"))\n",
        encoding="utf-8")
    (t / "a" / "_entry").chmod(0o755)
    (t / "a" / "_metainfo").write_text(json.dumps({"summary": "寫 out.txt", "kind": "program", "grow_level": 3,
                                                   "fs_needs": [], "callers": 1, "reads": ["d:t/*"]}), encoding="utf-8")
    ag = t / "box" / "tools" / "agent"
    ag.mkdir(parents=True)
    (ag / "_metainfo").write_text(json.dumps({"summary": "agent", "kind": "agent", "fs_needs": ["own_stack"], "callers": 1}),
                                  encoding="utf-8")
    (t / "d" / "t").mkdir(parents=True)
    (t / "d" / "_metainfo").write_text(json.dumps({"summary": "表", "kind": "data", "fs_needs": ["git_tracked"],
                                                   "children": {"t": "一筆一檔"}}), encoding="utf-8")
    (t / "d" / "t" / "_metainfo").write_text(json.dumps({"summary": "一筆一檔", "kind": "data", "fs_needs": ["git_tracked"]}),
                                             encoding="utf-8")
    for n in ("x", "y"):
        (t / "d" / "t" / (n + ".json")).write_text(json.dumps({"source": "手寫", "v": n}), encoding="utf-8")
    for p in (t / "idle", ag / "idle"):
        p.mkdir()
        (p / "_entry").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (p / "_entry").chmod(0o755)
        (p / "_metainfo").write_text(json.dumps({"summary": "idle", "kind": "program", "fs_needs": [], "callers": 1}),
                                     encoding="utf-8")
    return t


class CollapseT(unittest.TestCase):
    """meta/collapse：inline／unwrap／table／dedupe 四個子命令"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.t = Path(self._t.name) / "t"
        self.t.mkdir()
        mini_before(self.t)

    def collapse(self, *args):
        return run(COLLAPSE, *args, cwd=self.t)

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.t)
        for args in (["inline", "fsm.json#/states/a/exec"], ["unwrap", "box/tools"], ["table", "d/t"],
                     ["dedupe", "idle", "box/tools/agent/idle"]):
            r = self.collapse("--dry-run", *args)
            self.assertEqual(r.returncode, 0, (args, r.stderr))
            self.assertTrue(r.stdout.strip(), args)
            self.assertEqual(snapshot(self.t), before, args)
        r = self.collapse("--dry-run", "inline", "fsm.json#/states/a/exec")
        self.assertIn("搬 a/_entry → a.py", r.stdout)
        self.assertIn("__file__", r.stdout)                                   # 手改清單：往上找的層數

    def fsm_once(self, ws):
        ws.mkdir()
        return run(EXEC, "--ws", str(ws), str(self.t / "fsm.json"), cwd=self.t)

    def test_inline_same_result(self):
        r1 = self.fsm_once(self.t.parent / "ws1")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r = self.collapse("inline", "fsm.json#/states/a/exec")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.t / "a").exists())
        cell = json.loads((self.t / "fsm.json").read_text(encoding="utf-8"))["states"]["a"]["exec"]
        self.assertEqual((cell["argv"], cell["timeout_ms"]), (["python3", "a.py"], 5000))
        self.assertEqual((cell["_metainfo"]["grow_level"], cell["_metainfo"]["summary"]), (0, "寫 out.txt"))
        p = self.t / "a.py"                                                   # 照手改清單改 __file__ 那行（工具不改腳本）
        p.write_text(p.read_text(encoding="utf-8").replace("os.path.dirname(os.path.dirname(os.path.realpath(__file__)))",
                                                           "os.path.dirname(os.path.realpath(__file__))"), encoding="utf-8")
        r2 = self.fsm_once(self.t.parent / "ws2")
        self.assertEqual((r2.returncode, r2.stderr), (r1.returncode, r1.stderr))
        for f in ("out.txt", ".stack/state.txt"):
            self.assertEqual((self.t.parent / "ws2" / f).read_text(), (self.t.parent / "ws1" / f).read_text(), f)
        strip = lambda p: [(t["state"], t["code"], t["signal"]) for t in jl(p)]   # noqa: E731
        self.assertEqual(strip(self.t.parent / "ws2" / ".stack" / "trace.jsonl"), strip(self.t.parent / "ws1" / ".stack" / "trace.jsonl"))

    def test_unwrap_table_dedupe(self):
        r = self.collapse("unwrap", "box/tools")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.t / "box" / "agent" / "_metainfo").is_file())
        self.assertFalse((self.t / "box" / "tools").exists())
        r = self.collapse("dedupe", "idle", "box/agent/idle")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.readlink(self.t / "box" / "agent" / "idle"), "../../idle")
        self.assertEqual(json.loads((self.t / "idle" / "_metainfo").read_text())["callers"], 2)
        r = self.collapse("unwrap", "box")                                    # 捷徑本身被搬，目標跟著改
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.readlink(self.t / "agent" / "idle"), "../idle")
        r = self.collapse("table", "d/t", "--source", "手寫兩筆")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.t / "d" / "t.json").read_text()),
                         {"source": "手寫兩筆", "x": {"source": "手寫", "v": "x"}, "y": {"source": "手寫", "v": "y"}})
        self.assertEqual(json.loads((self.t / "d" / "_metainfo").read_text())["children"], {"t.json": "一筆一檔"})
        self.assertEqual(json.loads((self.t / "a" / "_metainfo").read_text())["reads"], ["d:t.json"])   # 讀者的 reads 跟著改

    def test_refuses_and_writes_nothing(self):
        (self.t / "box" / "tools" / "agent" / "tool.json").write_text("{}", encoding="utf-8")
        before = snapshot(self.t)
        for args, code in ((["unwrap", "box/tools"], "TargetBad"),           # tools/ 底下有 tool.json＝A-1 例外（P-41）
                           (["inline", "fsm.json#/states/nope/exec"], "CfgMissing"),
                           (["dedupe", "idle", "a"], "TargetBad"),            # 內容不一樣
                           (["table", "a"], "TargetBad"),                     # kind 不是 data
                           (["--bogus", "inline", "x"], "FlagUnknown")):
            r = self.collapse(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertRegex(r.stderr, r"^collapse: %s \S" % code)
            self.assertEqual(snapshot(self.t), before, args)


class SuggestT(unittest.TestCase):
    """meta/metatable --suggest：收攏前的樹列出候選，收攏後的樹列不出來"""

    def suggest(self, root):
        r = run(METATABLE, "--json", "--suggest", str(root))
        self.assertEqual(r.returncode, 0, r.stderr)
        return {s["path"]: s["rule"] for s in json.loads(r.stdout)["summary"]["suggest"]}

    def test_before_tree_lists_candidates(self):
        with tempfile.TemporaryDirectory() as t:
            tar = Path(t) / "before.tar"
            r = subprocess.run(["git", "-C", str(ROOT), "archive", "-o", str(tar), BEFORE_COMMIT, "topdown/galtxt-a"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest("拿不到收攏前那一版（%s）：%s" % (BEFORE_COMMIT, r.stderr.strip()))
            subprocess.run(["tar", "xf", str(tar), "-C", t], check=True)
            got = self.suggest(Path(t) / "topdown" / "galtxt-a")
        self.assertEqual({k: got.get(k) for k in ("brief", "pick", "write", "check", "judge")}, dict.fromkeys(
            ("brief", "pick", "write", "check", "judge"), "B-2"))
        self.assertEqual({k: got.get(k) for k in ("data/cast", "data/places", "data/samples")},
                         dict.fromkeys(("data/cast", "data/places", "data/samples"), "B-3"))
        self.assertEqual((got.get("write/tools"), got.get("judge/tools")), ("A-1", "A-1"))
        self.assertEqual((got.get("write/tools/writer/idle"), got.get("judge/tools/judge/idle")), ("B-4", "B-4"))
        for keep in ("idle", "data", "data/bench", "check/tools", "check/tools/lint", "write/tools/writer"):
            self.assertNotIn(keep, got)                                        # N-1／N-3、A-1 例外

    def test_mini_before_tree(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "t").mkdir()
            got = self.suggest(mini_before(Path(t) / "t"))
        self.assertEqual(got, {"a": "B-2", "box": "A-1", "box/tools": "A-1", "d/t": "B-3", "box/tools/agent/idle": "B-4"})

    def test_after_tree_lists_nothing(self):
        self.assertEqual(self.suggest(G), {})
        md = run(METATABLE, "--suggest", str(G)).stdout
        self.assertIn("候選 0 個", md)


STYLE_VALS = {"good", "ok", "bad", "none"}
TRAIN = G / "train"


def tree_copy(t):
    """整棵 galtxt-a 拷到 t/proto8/topdown/galtxt-a（捷徑照留），t/proto8/lib 指回真的 lib（write.py、judge.py 從 ../../lib 找 agent_tool）；回拷貝的根。
    訓練、rate、optimize 會寫樹（tree:），所以一律在拷貝上跑。"""
    g = Path(t) / "proto8" / "topdown" / "galtxt-a"
    shutil.copytree(G, g, symlinks=True)
    os.symlink(ROOT / "lib", Path(t) / "proto8" / "lib")
    return g


def jread(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def yuzu_total(dims):
    """round4 § 1.4：5 × Σ(weight×值)/Σweight，null 不進分母（照 data/dims.json 的傲嬌 profile）。"""
    got = [(spec.get("weight", 1), dims[k]) for k, spec in YUZU.items() if dims[k] is not None]
    return 5 * sum(w * v for w, v in got) / sum(w for w, _ in got)


YUZU = json.loads((G / "data" / "dims.json").read_text(encoding="utf-8"))["profiles"]["傲嬌"]


def jwrite(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class Round3T(unittest.TestCase):
    """第三輪（plan/round3.md § 11 的 1～11）：傲嬌與 Q16、選路、writer-sol、假腦技能表、rate、optimize、整條訓練、回滾、預算、M7。全部假腦。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def put(self, example, **extra):
        task = jread(EXAMPLES / example)
        task.update(extra)
        jwrite(self.ws / "new" / example, task)

    def galtxt(self, g=G, env=None):
        return run(EXEC, "--ws", str(self.ws), str(g), env=env, cwd=self.tmp, timeout=300)

    def score(self, name):
        return jread(self.ws / "out" / name / "score.json")

    # 1. 樹
    def test_tree(self):
        sol, w = G / "writer-sol", G / "writer"
        self.assertTrue(os.access(sol / "_entry", os.X_OK))
        model = lambda d: [l for l in (d / ".env").read_text().splitlines() if l.startswith("AOS_BRAIN_MODEL=")]   # noqa: E731
        self.assertNotEqual(model(sol), model(w))
        self.assertIn("sol", model(sol)[0])
        for f in ("brain.py", "act.py", "loop.json", "system.txt"):
            self.assertTrue((sol / f).is_symlink(), f)
            self.assertEqual(os.readlink(sol / f), "../writer/" + f)
        self.assertFalse((sol / "fsm.json").is_symlink())               # aos-fsm 的 cwd 是 fsm.json 的實際資料夾：捷徑會跑在 writer/ 裡
        self.assertEqual((sol / "fsm.json").read_bytes(), (w / "fsm.json").read_bytes())
        self.assertEqual(os.readlink(sol / "idle"), "../idle")
        self.assertEqual(os.readlink(sol / "tools" / "lint"), "../../tools/lint")
        for d in (w, sol):
            m = jread(d / "_metainfo")
            self.assertEqual((m["ratings"], m["human_ratings"]), ({"$ref": "ratings.json"}, {"$ref": "human.json"}))
            for f in ("ratings.json", "human.json"):
                r = jread(d / f)
                self.assertIsInstance(r, dict)
                self.assertIn("source", r)
                for k, cell in r.items():
                    if k.startswith("style:"):
                        self.assertIn(cell["val"], STYLE_VALS)
                        for v in cell.get("dims", {}).values():
                            self.assertTrue(v is None or 0 <= v <= 1, (d, k, v))
        st = jread(w / "stage.json")                                      # round4 步驟 3：寫手的固化階與兩套實作都在
        self.assertIn(st["stage"], ("agent", "semi", "program"))
        self.assertTrue(set(st["tools"]) <= set(os.listdir(w / "tools")), st["tools"])
        self.assertTrue((w / "compose.py").is_file())
        self.assertEqual(jread(w / "_metainfo")["brain"], {"$ref": "stage.json"})
        m = jread(TRAIN / "optimize" / "_metainfo")
        for k in ("ratings", "policy"):
            self.assertTrue((TRAIN / "optimize" / m[k]["$ref"]).is_file(), k)
        route = jread(G / "data" / "route.json")
        for v in [route["default"], *route["by_style"].values()]:
            self.assertTrue((G / v / "_entry").is_file(), v)
        q = jread(G / "human" / "questions.json")
        self.assertTrue(q["tags"] and q["dims"])
        fsm = jread(TRAIN / "fsm.json")                                   # P-36：格的 timeout_ms ≥ 那格 _metainfo 的 time_ms.max
        for s, cell in fsm["states"].items():
            if isinstance(cell["exec"], dict):
                self.assertGreaterEqual(cell["exec"]["timeout_ms"], cell["exec"]["_metainfo"]["time_ms"]["max"], s)
        self.assertEqual(jread(TRAIN / "loop.json")["max"], 4 * jread(TRAIN / "budget.json")["max_epochs"] + 1)

    # 2、3. 選路、換題清狀態
    def test_route(self):
        self.put("scene-yuzuha.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(self.stack / "brief.json")["style"], "傲嬌")
        self.assertEqual(jread(self.stack / "route.json"), {"writer": "writer", "style": "傲嬌", "by": "default"})
        self.assertEqual(self.score("scene-yuzuha")["writer"], "writer")
        g = tree_copy(self.tmp / "t")
        rt = jread(g / "data" / "route.json")
        rt["by_style"] = {"傲嬌": "writer-sol"}
        jwrite(g / "data" / "route.json", rt)
        shutil.rmtree(self.ws)
        (self.ws / "new").mkdir(parents=True)
        self.put("scene.json")
        self.put("scene-yuzuha.json")                                   # 兩題連放（scene-yuzuha 排前面）：第二題換寫手、route.json 重選
        r = self.galtxt(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(self.stack / "route.json"), {"writer": "writer", "style": "文靜／書卷", "by": "default"})
        self.assertEqual((self.score("scene")["writer"], self.score("scene-yuzuha")["writer"]), ("writer", "writer-sol"))
        self.assertEqual(len(os.listdir(self.stack / "writer" / "runs")), 3)
        self.assertEqual(len(os.listdir(self.stack / "writer-sol" / "runs")), 3)
        shutil.rmtree(self.ws)
        (self.ws / "new").mkdir(parents=True)
        self.put("scene-yuzuha.json")
        r = self.galtxt(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(self.stack / "route.json"), {"writer": "writer-sol", "style": "傲嬌", "by": "by_style"})
        self.assertTrue((self.stack / "writer-sol" / "runs" / "001").is_dir())
        shutil.rmtree(self.ws)
        (self.ws / "new").mkdir(parents=True)
        self.put("scene-yuzuha.json", writer="writer")                   # 題目級覆寫贏過表
        r = self.galtxt(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(self.stack / "route.json")["by"], "question")
        self.assertEqual(self.score("scene-yuzuha")["writer"], "writer")
        shutil.rmtree(self.ws)
        (self.ws / "new").mkdir(parents=True)
        self.put("scene-yuzuha.json", writer="nope")
        r = self.galtxt(g)
        self.assertEqual(r.returncode, 1)
        self.assertIn("galtxt-a write: RouteBad", r.stderr)
        self.assertEqual((self.stack / "state.txt").read_text(), "write\n")
        self.assertFalse((self.stack / "route.json").exists())

    # 4. Q16 離線
    def test_fill_q16(self):
        self.put("Q16.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (self.ws / "out" / "Q16" / "answer.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("宮澤柚葉：「"), lines)
        s = self.score("Q16")
        self.assertTrue(s["bench"]["guard_hit"])
        self.assertEqual((s["writer"], s["style"]), ("writer", "傲嬌"))
        self.assertIn("KeywordMissing", s["drafts"][2]["tier0"])          # 第 3 份（留白）沒過護欄：護欄 0、total 0、沒評＝評審量的維度 null
        d3 = s["drafts"][2]
        self.assertEqual(set(d3["dims"]), set(YUZU) | {"護欄"})            # round4：維度照 dims.json 的傲嬌 profile（＋護欄）
        self.assertEqual((d3["dims"]["護欄"], d3["total"]), (0.0, 0))
        for k, spec in YUZU.items():
            if spec["by"] == "grader" or "fill" not in spec.get("modes", ["fill"]):   # 沒評、或 fill 沒這維（洩底）＝null
                self.assertIsNone(d3["dims"][k], k)
        for d in s["drafts"][:2]:                                         # 前兩份過護欄：fill 的洩底 null、total＝加權
            self.assertEqual(d["dims"]["護欄"], 1.0)
            self.assertIsNone(d["dims"]["洩底"])
            self.assertAlmostEqual(d["total"], yuzu_total(d["dims"]), places=2)
        self.assertIn("bigram_overlap", s["bench"])
        quote = jread(G / "data" / "bench" / "Q16.json")["answer"].split("：「", 1)[1]
        for p in self.stack.rglob("*"):
            if p.is_file():
                self.assertNotIn(quote, p.read_text(encoding="utf-8"), p)

    # 5. 假腦技能表、結構分
    def test_fake_skill_table(self):
        self.put("scene-yuzuha.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.score("scene-yuzuha")
        self.assertEqual([d["tier1"] for d in s["drafts"]], [1, 1, 1])
        for d in s["drafts"]:
            self.assertIn("NgMark", d["tier1_notes"])
            self.assertEqual(set(d["dims"]), set(YUZU) | {"護欄"})         # round4：維度照 profile；NgMark＝語域半分、假腦有反差節拍
            self.assertEqual((d["dims"]["護欄"], d["dims"]["語域"], d["dims"]["反差"]), (1.0, 0.5, 1.0))
            self.assertTrue(all(v is not None and 0 <= v <= 1 for v in d["dims"].values()), d["dims"])   # scene 每維都有值
            self.assertAlmostEqual(d["total"], yuzu_total(d["dims"]), places=2)
        self.assertTrue(0 <= s["dims"]["多樣性"] <= 1)
        shutil.rmtree(self.ws)
        (self.ws / "new").mkdir(parents=True)
        self.put("scene-yuzuha.json", writer="writer-sol")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([d["tier1"] for d in self.score("scene-yuzuha")["drafts"]], [2, 2, 2])
        shutil.rmtree(self.ws)                                           # 技能表反過來：sol 寫傲嬌砸、luna 不砸
        (self.ws / "new").mkdir(parents=True)
        self.put("scene-yuzuha.json", writer="writer-sol")
        r = self.galtxt(env={"GALTXT_FAKE_WEAK": "sol:傲嬌"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([d["tier1"] for d in self.score("scene-yuzuha")["drafts"]], [1, 1, 1])

    # 6. rate 單元
    def rate(self, g, st):
        return run("python3", str(g / "train" / "rate.py"), env={"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws)},
                   cwd=g / "train")

    def test_rate(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "human" / "samples.json", [])                         # 在就不動：這個單元不挑樣本
        r0 = jread(g / "writer" / "ratings.json")
        r0["style:舊的"] = {"val": "good", "score_avg": 5}
        jwrite(g / "writer" / "ratings.json", r0)
        st = self.tmp / "st"

        def dims_of(t):                                                  # round4：傲嬌 profile 的維度（像柚葉跟著 total 動、其餘固定）
            return {"反差": 1.0, "像柚葉": round((t - 2) / 3, 3), "承接": 0.5, "文筆": 0.5, "語域": 1.0, "洩底": 0.5, "護欄": 1.0}

        def score(where, name, writer, totals, fail=0, div=0.5, style="傲嬌", reason="承接自然", top=st):
            drafts = [{"n": i + 1, "tier0": [], "tier1": 2, "total": t, "dims": dims_of(t), "reason": reason}
                      for i, t in enumerate(totals)]
            drafts += [{"n": len(totals) + i + 1, "tier0": ["FormatBad"], "tier1": 0, "total": 0,
                        "dims": {"反差": 0.0, "像柚葉": None, "承接": None, "文筆": None, "語域": 0.0, "洩底": None, "護欄": 0.0}}
                       for i in range(fail)]
            jwrite(top / "epochs" / "001" / where / name / "ws" / "out" / name / "score.json",
                   {"name": name, "writer": writer, "style": style, "drafts": drafts, "dims": {"多樣性": div}})

        score("runs", "a", "writer", [4, 4, 4], fail=1, div=0.4)
        score("runs", "b", "writer", [5, 3], div=0.6, reason="太直白")
        score("runs", "d", "writer-sol", [2, 2, 2])
        score("verify", "v", "writer", [0, 0, 0], style="文靜／書卷")      # 驗證題：rate 不收、也不守門
        run_d = st / "epochs" / "001" / "runs" / "a" / "stack" / "writer" / "runs" / "001" / "stack"   # 寫手小格一次：cost 照它算
        run_d.mkdir(parents=True)
        (run_d / "history.jsonl").write_text('{"role": "user"}\n{"role": "assistant"}\n{"role": "assistant"}\n', encoding="utf-8")
        (run_d / "usage.jsonl").write_text('{"total_tokens": 1000}\n', encoding="utf-8")
        (run_d / "trace.jsonl").write_text('{"elapsed_ms": 300}\n{"elapsed_ms": 200}\n', encoding="utf-8")
        r = self.rate(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        w, sol = jread(g / "writer" / "ratings.json"), jread(g / "writer-sol" / "ratings.json")
        t = w["style:傲嬌"]
        self.assertEqual((t["val"], t["score_avg"], t["score_min"], t["counter_samples"], t["counter_runs"]), ("good", 4.0, 3, 5, 2))
        self.assertEqual(set(t["dims"]), set(YUZU) | {"護欄", "多樣性"})   # 維度照 score.json 裡有的走（不寫死）
        self.assertEqual(t["dims"]["護欄"], round(5 / 6, 3))
        self.assertEqual(t["dims"]["多樣性"], 0.5)
        self.assertEqual(t["dims"]["像柚葉"], round(sum(round((x - 2) / 3, 3) for x in [4, 4, 4, 5, 3]) / 5, 3))
        self.assertEqual((t["dims"]["反差"], t["dims"]["洩底"]), (1.0, 0.5))   # 沒過護欄那份的 0 不算進維度
        self.assertIsNone(t["determinism"])                              # 這個 epoch 沒 verify.json＝沒量
        self.assertEqual(t["cost"], {"llm_calls": 2, "llm_tokens": 1000, "time_ms": 500, "counter_runs": 1})
        self.assertEqual(t["tags"], {"太直白": 2, "承接自然": 3})
        self.assertEqual(w["scope"], jread(g / "train" / "set.json")["scope"])
        self.assertNotIn("style:文靜／書卷", w)                            # 驗證題不算
        self.assertEqual(w["style:舊的"], {"val": "good", "score_avg": 5})   # 這次沒跑到的風格留舊格
        self.assertEqual((sol["style:傲嬌"]["val"], sol["style:傲嬌"]["score_avg"]), ("bad", 2.0))
        self.assertRegex(t["rated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        gr = jread(g / "grader" / "ratings.json")["role:grader"]       # 分辨力＝每題（承接、像柚葉）標準差 ÷ 0.5 的平均
        sds = [statistics.pstdev([round((x - 2) / 3, 3) for x in xs]) / 0.5 for xs in ([4, 4, 4], [5, 3], [2, 2, 2])] + [0.0] * 3
        self.assertEqual(gr["dims"]["分辨力"], round(sum(sds) / len(sds), 3))
        self.assertEqual(gr["counter_samples"], 6)
        strip = lambda d: {k: {k2: v2 for k2, v2 in v.items() if k2 != "rated_at"} if isinstance(v, dict) else v for k, v in d.items()}   # noqa: E731
        r = self.rate(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(strip(jread(g / "writer" / "ratings.json")), strip(w))
        self.assertEqual(jread(g / "human" / "samples.json"), [])
        st2 = self.tmp / "st2"                                           # 2 份＜3＝none
        score("runs", "e", "writer-sol", [5, 5], top=st2)
        r = self.rate(g, st2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(g / "writer-sol" / "ratings.json")["style:傲嬌"]["val"], "none")
        st3 = self.tmp / "st3"                                           # 收窄守門：訓練題混進別的風格＝StateBad、評級不寫
        score("runs", "a", "writer", [4, 4, 4], top=st3)
        score("runs", "c", "writer", [3, 3, 3], style="文靜／書卷", top=st3)
        before = (g / "writer" / "ratings.json").read_bytes()
        r = self.rate(g, st3)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^train: StateBad .*文靜／書卷.*scope\.style")
        self.assertEqual((g / "writer" / "ratings.json").read_bytes(), before)

    # 7. optimize 單元：第三輪的選路優化器（route.json）在 6b 換成照樹走的優化器（selfopt／stage／extract），單元移到 Round4OptT.test_optimize_tree（§ 10 測試 13）

    # 8、11. 整條訓練＋M7
    def test_train_whole(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "train" / "budget.json", dict(jread(g / "train" / "budget.json"), max_epochs=1))
        (g / "human" / "samples.json").unlink(missing_ok=True)
        sets = jread(g / "train" / "set.json")
        before = snapshot(g)
        r = run(EXEC, "--ws", str(self.ws), str(g / "train"), cwd=self.tmp, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        e0, e1 = (jread(self.stack / "epochs" / n / "verify.json") for n in ("000", "001"))
        # round4：writers 只剩 writer、route 沒得換（optimize 步驟 6 才重寫）＝分數不會往下掉；假腦同輸入同分，不再斷言進步
        self.assertGreaterEqual(e1["score_mean"], e0["score_mean"])
        self.assertEqual(e1["delta"], round(e1["score_mean"] - e0["score_mean"], 3))
        for e in (e0, e1):
            self.assertEqual(set(e["by_question"]), {q[:-5] for q in sets["verify"]})   # 驗證題分題記（round4 § 7.2 (c)）
            self.assertEqual(e["measure"]["question"], sets["measure"][:-5])
            self.assertTrue(0 <= e["measure"]["一致"] <= 1)
            nodes = e["brain"]["nodes"]                                  # round4 步驟 4：節點改讀根的 rollup（整棵樹的直接子樹＋攤平的「子樹/孫」）
            self.assertEqual({k: nodes.get(k) for k in ("writer", "grader", "tools/lint", "train/weigh")},
                             {"writer": "agent" if e is e0 else "semi", "grader": "agent", "tools/lint": "program", "train/weigh": "agent"})   # 6b：epoch 0 的 selfopt 抽了 close → semi
            self.assertNotIn("writer-sol", nodes)                        # 步驟 5 隊長裁定：只算每題會被叫到的；writer-sol 凍結、route 沒選它
            self.assertEqual(e["brain"]["excluded"].get("writer-sol"), "agent")
            self.assertTrue({"idle", "train", "train/optimize"} <= set(e["brain"]["excluded"]))
            self.assertEqual(e["brain"]["counter_on_brain"], sum(1 for v in nodes.values() if v in ("agent", "semi")))
        self.assertNotIn("writer/tools/beat", e0["brain"]["nodes"])          # epoch 0 的 verify 在 rate 之前：writer 還沒 rollup、孫子看不到
        self.assertEqual(e1["brain"]["nodes"]["writer/tools/beat"], "program")   # rate 跑過 rollup --up writer 之後才攤平得到
        self.assertEqual(e1["brain"]["nodes"], jread(g / "rollup.json")["brain"]["nodes"])
        w = jread(g / "writer" / "ratings.json")
        t = w["style:傲嬌"]
        self.assertEqual(t["val"], "good" if t["score_avg"] >= 4 else "ok" if t["score_avg"] >= 3 else "bad")
        self.assertEqual(set(t["dims"]), set(YUZU) | {"護欄", "多樣性"})
        self.assertEqual(w["scope"], sets["scope"])
        root = jread(g / "ratings.json")["style:傲嬌"]                    # 根評級＝最後一次 verify 的數
        self.assertEqual((root["score_avg"], root["determinism"], root["brain"]), (e1["score_mean"], e1["measure"]["一致"], e1["brain"]))
        self.assertTrue(0 <= jread(g / "grader" / "ratings.json")["role:grader"]["dims"]["分辨力"] <= 1)
        samples = jread(g / "human" / "samples.json")
        self.assertTrue(1 <= len(samples) <= 6)
        for s in samples:
            self.assertTrue({"id", "team", "scene", "lines", "produced_by", "auto_scores", "round", "why_picked"} <= set(s), s)
            self.assertTrue(s["id"].startswith("a4-"))                  # 步驟 7：新 id，不跟第三輪 a-q01-writer-* 撞
            self.assertEqual(s["team"], "a")
            self.assertTrue(1 <= len(s["lines"]) <= 8)
            self.assertTrue((g / s["produced_by"] / "_entry").is_file())
            self.assertTrue({"cast", "place", "event", "style", "intent", "epoch", "stage", "pair_id"} <= set(s["scene"]))
            self.assertEqual((s["scene"]["style"], s["scene"]["place"]), (sets["scope"]["style"], sets["scope"]["place"]))   # 全在收窄範圍
        self.assertEqual(len({s["id"] for s in samples}), len(samples))
        # round4 § 8.1：第一個 epoch 後只有 agent 階的產出——兩個驗證題的 pair-stage 前半（epoch 0、agent）＋disagree；program 半邊與難例之後的 rate 補
        pairs = sorted((s["scene"]["pair_id"], s["scene"]["stage"], s["scene"]["epoch"]) for s in samples if s["why_picked"] == "pair-stage")
        self.assertEqual(pairs, sorted(("a4-%s" % q[:-5].lower(), "agent", 0) for q in sets["verify"]))
        self.assertEqual({s["why_picked"] for s in samples} - {"pair-stage"}, {"disagree"})
        self.assertEqual(len(jl(self.stack / "verify.jsonl")), 2)
        self.assertEqual([t["state"] for t in jl(self.stack / "trace.jsonl")], ["verify", "train", "rate", "optimize", "verify"])
        after = snapshot(g)                                               # M7：只有量出來的旁檔變（route 沒換＝route.json、optimize 評級不動）
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"writer/ratings.json", "grader/ratings.json", "ratings.json", "human/samples.json",
                                   "rollup.json", "writer/rollup.json", "grader/rollup.json",   # round4 步驟 4：rate／verify 叫 rollup --up
                                   "train/rollup.json", "train/weigh/rollup.json",              # 步驟 5：verify 先 rollup --up train/weigh
                                   "writer/stage.json",                                          # 步驟 5：verify 每個 epoch 寫 stage.json.history
                                   "writer/opt_log.jsonl", "train/optimize/selfopt.json",        # 6b：epoch 0 的 optimize 派 selfopt（抽 close）、accept 搬回
                                   "writer/tools/close", "writer/tools/close/_entry", "writer/tools/close/_metainfo", "writer/tools/close/tool.json",
                                   "writer/grad.json", "writer/tools/close/grad.json", "writer/tools/close/rollup.json",   # epoch 1 的 verify 判 A、梯度分給 close
                                   "train/optimize/ratings.json", "train/weigh/ratings.json", "train/weigh/log.jsonl"})
        self.assertEqual([h["epoch"] for h in jread(g / "writer" / "stage.json")["history"]], [0, 1])
        r = run(EXEC, "--ws", str(self.ws), str(g / "train"), cwd=self.tmp, timeout=600)   # 收工後再叫：verify 照舊退 10、不重跑
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(jl(self.stack / "verify.jsonl")), 2)

    # 9. 回滾
    def test_regressed_rolls_back(self):
        g = tree_copy(self.tmp / "t")
        st = self.tmp / "st"
        (st / "epochs" / "001" / "params").mkdir(parents=True)
        (st / "epoch.txt").write_text("1\n")
        jwrite(st / "epochs" / "000" / "verify.json", {"epoch": 0, "score_mean": 4.0})
        old = jread(g / "data" / "route.json")
        jwrite(st / "epochs" / "001" / "params" / "route.json", old)
        jwrite(st / "epochs" / "001" / "params" / "optimize.json", {"changed": True})
        jwrite(g / "data" / "route.json", dict(old, by_style={"傲嬌": "writer-sol"}))
        r = run(EXEC, str(g / "train" / "fsm.json") + "#/states/verify/exec",
                env={"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws), "GALTXT_FAKE_WEAK": "sol:傲嬌"}, timeout=300)
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertIn("train: Regressed epoch 1", r.stderr)
        self.assertEqual(jread(g / "data" / "route.json"), old)
        a = jread(g / "train" / "optimize" / "ratings.json")["action:route"]
        self.assertEqual((a["counter_regressed"], a["counter_applied"], a["val"]), (1, 1, "bad"))
        self.assertEqual((st / "epoch.txt").read_text(), "1\n")

    # 10. 預算
    def test_budget_spent(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "train" / "budget.json", dict(jread(g / "train" / "budget.json"), max_calls=3))
        route = (g / "data" / "route.json").read_bytes()
        r = run(EXEC, "--ws", str(self.ws), str(g / "train"), cwd=self.tmp, timeout=300)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("train: BudgetSpent max_calls", r.stderr)
        self.assertEqual((self.stack / "state.txt").read_text(), "train\n")
        self.assertEqual((g / "data" / "route.json").read_bytes(), route)


class Round4T(unittest.TestCase):
    """第四輪（plan/round4.md § 10）：收窄到宮澤柚葉×教室・文化祭收攤之後的測試。全部假腦；會寫樹的都在拷貝上跑。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)

    # 4. scope 守門：set.json scope.style 暫改文靜 → rate 讀到傲嬌的 score.json＝StateBad、評級不寫
    def test_scope_guard(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "human" / "samples.json", [])
        st = self.tmp / "st"
        dims = {"反差": 1.0, "像柚葉": 0.667, "承接": 0.667, "文筆": 0.667, "語域": 0.5, "洩底": 0.5, "護欄": 1.0}
        jwrite(st / "epochs" / "001" / "runs" / "a" / "ws" / "out" / "a" / "score.json",
               {"name": "a", "writer": "writer", "style": "傲嬌", "dims": {"多樣性": 0.3},
                "drafts": [{"n": i, "tier0": [], "tier1": 1, "total": 3.5, "dims": dims} for i in (1, 2, 3)]})
        rate = lambda: run("python3", str(g / "train" / "rate.py"), env={"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws)},   # noqa: E731
                           cwd=g / "train")
        r = rate()                                                       # 對照：範圍對＝過
        self.assertEqual(r.returncode, 0, r.stderr)
        sets = jread(g / "train" / "set.json")
        jwrite(g / "train" / "set.json", dict(sets, scope=dict(sets["scope"], style="文靜")))
        before = {p: (g / p).read_bytes() for p in ("writer/ratings.json", "grader/ratings.json")}
        r = rate()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.count("\n"), 1, r.stderr)
        self.assertRegex(r.stderr, r"^train: StateBad .*'傲嬌' 不在收窄範圍.*'文靜'")
        self.assertEqual({p: (g / p).read_bytes() for p in before}, before)

    # ---- 共用 ----
    def put(self, example, ws=None):
        jwrite((ws or self.ws) / "new" / example, jread(EXAMPLES / example))

    def galtxt(self, g=G, env=None, ws=None):
        return run(EXEC, "--ws", str(ws or self.ws), str(g), env=env, cwd=self.tmp, timeout=300)

    def fresh(self, name):
        ws = self.tmp / name
        (ws / "new").mkdir(parents=True)
        return ws

    def staged(self, stage, tools=None):
        """樹的拷貝，writer/stage.json 改成這階（tools 有給也換）"""
        g = tree_copy(self.tmp / ("t-" + stage + "-" + "-".join(tools or [])))
        st = jread(g / "writer" / "stage.json")
        st["stage"] = stage
        if tools is not None:
            st["tools"] = tools
        jwrite(g / "writer" / "stage.json", st)
        return g

    def histories(self, ws, agent="writer"):
        return [jl(p) for p in sorted((ws / ".stack" / agent / "runs").glob("*/stack/history.jsonl"))]

    # 1. 評分結構：dims.json 的 by 都是真的子樹（或 pick）；柚葉 fill 三份 dims 齊、洩底 null、total＝加權手算
    def test_dims_table(self):
        d = jread(G / "data" / "dims.json")
        for name, spec in [*d["profiles"]["傲嬌"].items(), *d["question_dims"].items()]:
            by = spec["by"]
            self.assertTrue(by == "pick" or (G / by / "_metainfo").is_file(), (name, by))
            for sub in spec["moved_by"]:
                self.assertTrue((G / sub / "_metainfo").is_file(), (name, sub))
        self.put("Q16.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        s = jread(self.ws / "out" / "Q16" / "score.json")
        for x in s["drafts"]:
            self.assertEqual(set(x["dims"]), set(YUZU) | {"護欄"})
            self.assertIsNone(x["dims"]["洩底"])                          # fill 沒有洩底
            if x["dims"]["護欄"]:
                self.assertAlmostEqual(x["total"], yuzu_total(x["dims"]), places=2)
            else:
                self.assertEqual(x["total"], 0)
        self.assertEqual(set(s["dims"]), {"多樣性"})                       # 不是 hints_fixed 的題：沒有「一致」

    # 2. lint 細項：反差的順序、洩底、OocMark、開關
    def lint_rules(self, example):
        ws = self.fresh("b-" + example)
        self.put(example, ws)
        st = ws / ".stack"
        st.mkdir()
        r = run(EXEC, BRIEF, env={"AOS_WS": str(ws), "AOS_STACK": str(st) + "/"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return jread(st / "rules.json")

    def lint_dims(self, rules, text):
        d = self.tmp / "lintws"
        jwrite(d / "rules.json", rules)
        r = run(EXEC, "--ws", str(d), LINT, input=json.dumps({"text": text}, ensure_ascii=False),
                env={"AOS_STACK": str(self.tmp / "lintstack") + "/"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_lint_contrast(self):
        fill = self.lint_rules("Q16.json")
        y = "宮澤柚葉：「%s」"
        o = self.lint_dims(fill, y % "哼，才沒有。不過……也不是不能接受。")
        self.assertEqual((o["dims"]["反差"], o["dims"]["洩底"]), (1.0, None))   # fill 沒有洩底
        self.assertEqual(self.lint_dims(fill, y % "才沒有。")["dims"]["反差"], 0.5)
        self.assertEqual(self.lint_dims(fill, y % "也不是不能接受。才沒有。")["dims"]["反差"], 0.5)   # 順序反
        self.assertEqual(self.lint_dims(fill, y % "嗯，好啊。")["dims"]["反差"], 0.0)
        o = self.lint_dims(fill, y % "哼，才沒有，臉紅冒煙了。")
        self.assertIn("OocMark", o["tier1_notes"])
        self.assertIn("冒煙", o["tier1_notes"])
        off = dict(fill, switches=dict(fill["switches"], contrast_order=False))
        self.assertIsNone(self.lint_dims(off, y % "哼，才沒有。不過……也不是不能接受。")["dims"]["反差"])
        scene = self.lint_rules("cls-ribbon.json")
        body = ["主角：「宮澤，那個要丟嗎？」", y % "哼，才沒有。不過……也不是不能接受。", "主角：「好。」", y % "真是的。"]
        o = self.lint_dims(scene, "\n".join(["（宮澤柚葉別過臉，耳根有點紅。）"] + body))
        self.assertEqual(o["dims"]["洩底"], 1.0)
        self.assertEqual(self.lint_dims(scene, "\n".join(["（夕陽斜斜照進來。）"] + body))["dims"]["洩底"], 0.5)
        self.assertEqual(self.lint_dims(scene, "\n".join(body + ["主角：「走吧。」"]))["dims"]["洩底"], 0.0)

    # 3. judge 四行：三個 dims；少「文筆：」＝null 不停；沒「承接：」＝ReplyBad
    def test_judge_four_lines(self):
        self.put("Q16.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        j = jread(self.ws / ".stack" / "judge.json")
        self.assertTrue(j)
        for v in j.values():
            self.assertEqual((v["scores"], v["tier2"], v["reason"]), ({"承接": 2, "像柚葉": 2, "文筆": 2}, 2, "假腦"))
        ws = self.fresh("ws2")
        self.put("Q16.json", ws)
        r = self.galtxt(ws=ws, env={"GALTXT_FAKE_GRADE": "承接：3\\n像柚葉：1\\n理由：太直白"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for v in jread(ws / ".stack" / "judge.json").values():
            self.assertEqual((v["scores"], v["reason"]), ({"承接": 3, "像柚葉": 1, "文筆": None}, "太直白"))
        for x in jread(ws / "out" / "Q16" / "score.json")["drafts"]:
            if x["dims"]["護欄"]:
                self.assertIsNone(x["dims"]["文筆"])
                self.assertEqual((x["dims"]["承接"], x["dims"]["像柚葉"]), (1.0, 0.333))
        ws = self.fresh("ws3")
        self.put("Q16.json", ws)
        r = self.galtxt(ws=ws, env={"GALTXT_FAKE_GRADE": "像柚葉：3\\n文筆：3\\n理由：沒承接"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("galtxt-a judge: ReplyBad", r.stderr)
        self.assertFalse((ws / "out" / "Q16").exists())

    # 5. 寫手三階同介面：agent／semi／program 跑 Q16 都交一行、must 中；program 沒有腦的痕跡；semi 腦叫了 beat
    def test_writer_stages(self):
        runs = {}
        for stage, tools in (("agent", None), ("semi", ["lint", "beat"]), ("semi", ["lint"]), ("program", None)):
            g = self.staged(stage, tools)
            key = "-".join([stage] + (tools or []))
            ws = self.fresh("ws-" + key)
            self.put("Q16.json", ws)
            r = self.galtxt(g, ws=ws)
            self.assertEqual(r.returncode, 0, (key, r.stderr))
            lines = (ws / "out" / "Q16" / "answer.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1, (key, lines))
            self.assertTrue(lines[0].startswith("宮澤柚葉：「"), (key, lines))
            self.assertTrue(jread(ws / "out" / "Q16" / "score.json")["bench"]["guard_hit"], key)
            runs[key] = ws
        called = lambda h: {c["function"]["name"] for m in h for c in m.get("tool_calls") or []}   # noqa: E731
        for key in ("agent", "semi-lint"):
            hs = self.histories(runs[key])
            self.assertEqual(len(hs), 3)
            for h in hs:
                self.assertEqual(called(h), {"lint"}, key)                 # tools ["lint"]：腦看不到 beat（semi 也一樣）
        hs = self.histories(runs["semi-lint-beat"])
        self.assertEqual(len(hs), 3)
        for h in hs:
            self.assertEqual(called(h), {"lint", "beat"})
            self.assertTrue(any(m.get("role") == "tool" and "不過……" in m["content"] for m in h), h)   # beat 真的跑了
        cells = sorted((runs["program"] / ".stack" / "writer" / "runs").iterdir())
        self.assertEqual(len(cells), 3)                                    # write.py 一字不改：小格照開
        for c in cells:
            for f in ("history.jsonl", "usage.jsonl", "trace.jsonl"):
                self.assertEqual(list(c.rglob(f)), [], (c, f))             # 程式階：沒有腦、沒有 loop 的痕跡
        self.assertEqual(self.histories(runs["program"]), [])               # counter_calls 0
        self.assertEqual(len(self.histories(runs["program"], "judge")), 3)  # 評審照評
        ws = self.fresh("ws-env")                                           # GALTXT_STAGE 蓋過 stage.json
        self.put("Q16.json", ws)
        r = self.galtxt(ws=ws, env={"GALTXT_STAGE": "program"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.histories(ws), [])
        ws = self.fresh("ws-bad")
        self.put("Q16.json", ws)
        r = self.galtxt(ws=ws, env={"GALTXT_STAGE": "nope"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("writer: StateBad", r.stderr)

    # 6. 工具契約：beat、voice
    def tool(self, name, args):
        return run(EXEC, str(G / "writer" / "tools" / name), input=args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
                   env={"AOS_STACK": str(self.tmp / "toolstack" / name) + "/"})

    def test_tool_contract(self):
        for name in ("beat", "voice"):
            d = G / "writer" / "tools" / name
            self.assertTrue(os.access(d / "_entry", os.X_OK), name)
            self.assertTrue({"description", "parameters"} <= set(jread(d / "tool.json")), name)
            m = jread(d / "_metainfo")
            self.assertEqual((m["kind"], m["deterministic"]), ("program", True), name)
        r = self.tool("beat", {"deny": "才沒有", "yield": "也不是不能接受", "cover": "真是的"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.count("\n"), 1, r.stdout)
        out = r.stdout.strip()
        self.assertTrue(0 <= out.index("才沒有") < out.index("也不是不能接受") < out.index("真是的"), out)
        self.assertEqual(self.tool("beat", {"deny": "才沒有", "yield": "也不是不能接受", "cover": "真是的"}).stdout, r.stdout)   # 確定性
        r = self.tool("beat", {"deny": "才沒有"})                           # 槽缺：通用句補、stderr 一行、退 0
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("\n"), 1)
        self.assertTrue(r.stdout.startswith("才沒有"), r.stdout)
        self.assertRegex(r.stderr, r"^beat: SlotMissing yield")
        self.assertEqual(r.stderr.count("SlotMissing"), 2)                 # yield、cover 各一行
        r = self.tool("voice", {"text": "才沒有。不過……也不是不能接受，真是的。", "who": "宮澤柚葉", "ending": "啦"})
        self.assertEqual((r.returncode, r.stdout), (0, "宮澤柚葉：「才沒有。不過……也不是不能接受，真是的啦。」\n"))
        r = self.tool("voice", {"text": "{calls}拿著。", "calls": "你"})       # 稱呼換上、沒口癖就補第一個
        self.assertEqual(r.stdout, "哼，你拿著。\n")
        r = self.tool("voice", {})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.count("\n"), 1)
        self.assertEqual(r.stderr.count("\n"), 1)
        self.assertRegex(r.stderr, r"^voice: SlotMissing text")
        for name in ("beat", "voice"):
            r = self.tool(name, "nope")
            self.assertEqual(r.returncode, 1)
            self.assertRegex(r.stderr, r"^%s: ArgumentsBad \S" % name)

    # 7. 確定性：Q16-fixed 三份同 hint；program 的「一致」1.0；假腦 agent 預設 < 1（6b）、JITTER=0 是 1.0、JITTER=1 更低；＝1 − 多樣性
    def test_determinism(self):
        def one(g, env=None, tag="x"):
            ws = self.fresh("ws-" + tag)
            self.put("Q16-fixed.json", ws)
            r = self.galtxt(g, env=env, ws=ws)
            self.assertEqual(r.returncode, 0, r.stderr)
            hints = [jread(p)["hint"] for p in sorted((ws / ".stack" / "writer" / "runs").glob("*/ws/done/Q16-fixed.json"))]
            self.assertEqual(hints, ["借景"] * 3)
            return jread(ws / "out" / "Q16-fixed" / "score.json")["dims"]
        self.assertEqual(one(self.staged("program"), tag="p")["一致"], 1.0)
        a = one(G, tag="a")                                                  # 6b：假腦 agent 階預設有抽樣差（口氣照第幾次抽挑）＝同輸入同角度三份不一樣
        self.assertLess(a["一致"], 1.0)
        self.assertAlmostEqual(a["一致"], 1 - a["多樣性"], places=3)
        self.assertEqual(one(G, env={"GALTXT_FAKE_JITTER": "0"}, tag="z")["一致"], 1.0)   # 關掉＝同輸入同輸出
        d = one(G, env={"GALTXT_FAKE_JITTER": "1"}, tag="j")                  # 再加句尾記號＝更不一致
        self.assertLess(d["一致"], a["一致"])
        self.assertAlmostEqual(d["一致"], 1 - d["多樣性"], places=3)

    # 8. 難例：templates.json 沒 poster → program 照產、hard.jsonl 一行 TemplateMissing；再跑不重複；ribbon 不記
    def test_hard_cases(self):
        self.assertNotIn("poster", jread(G / "data" / "templates.json")["by_detail"])
        self.assertNotIn("lights", jread(G / "data" / "templates.json")["by_detail"])   # held-out
        g = self.staged("program")
        hard = g / "writer" / "hard.jsonl"
        for i in (1, 2):
            ws = self.fresh("ws-poster-%d" % i)
            self.put("cls-poster.json", ws)
            r = self.galtxt(g, ws=ws)
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = (ws / "out" / "cls-poster" / "answer.txt").read_text(encoding="utf-8").splitlines()
            self.assertTrue(5 <= len(lines) <= 10, lines)
            rows = jl(hard)
            self.assertEqual(len(rows), 1, rows)                            # 三份草稿、跑兩次：同題同 why 只記一次
            self.assertEqual((rows[0]["question"], rows[0]["why"], rows[0]["brief_key"]),
                             ("cls-poster", "TemplateMissing", {"mode": "scene", "detail": "poster"}))
            self.assertIn("宮澤柚葉：「", rows[0]["output"])
            self.assertEqual(rows[0]["cells"], ["scene.closeup.detail.poster"])          # 步驟 3b：缺的那格
        ws = self.fresh("ws-ribbon")
        self.put("cls-ribbon.json", ws)
        r = self.galtxt(g, ws=ws)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("彩帶", (ws / "out" / "cls-ribbon" / "answer.txt").read_text(encoding="utf-8"))   # 用了 by_detail.ribbon
        self.assertEqual(len(jl(hard)), 1)
        self.assertFalse((G / "writer" / "hard.jsonl").exists())            # 真樹沒被弄髒

    # ---- 步驟 4：rollup ----
    def rollup(self, root, *args):
        return run(ROLLUP, *args, cwd=root)

    def mini_tree(self):
        """暫存三層樹：根 → mid（semi、有評級）→ mid/tools/gc（program、有評級與梯度）、mid/helper（agent）；根 → uncle（program）"""
        r = self.tmp / "forest"
        jwrite(r / "_metainfo", {"summary": "根", "kind": "agent", "resource": ["llm"], "rollup": {"$ref": "rollup.json"}})
        jwrite(r / "rollup.json", {"source": "只有 source"})
        jwrite(r / "mid" / "_metainfo", {"summary": "中層", "kind": "agent", "resource": ["llm"], "llm_tokens": {"val": 1000, "max": 9000},
                                         "ratings": {"$ref": "ratings.json"}, "brain": {"$ref": "stage.json"}})
        jwrite(r / "mid" / "ratings.json", {"source": "s", "scope": {"style": "傲嬌"},
                                            "style:傲嬌": {"val": "ok", "score_avg": 3.5, "cost": {"llm_calls": 2, "llm_tokens": 5000, "time_ms": 10}},
                                            "style:文靜": {"val": "bad"}})
        jwrite(r / "mid" / "stage.json", {"source": "s", "stage": "semi", "tools": ["gc"]})
        jwrite(r / "mid" / "tools" / "gc" / "_metainfo", {"summary": "孫", "kind": "program"})
        jwrite(r / "mid" / "tools" / "gc" / "ratings.json", {"style:傲嬌": {"val": "good"}})
        jwrite(r / "mid" / "tools" / "gc" / "grad.json", {"source": "s", "context": {"tree": "forest"}, "sum": {"determinism": 0.25}})
        jwrite(r / "mid" / "helper" / "_metainfo", {"summary": "另一個孫", "kind": "agent", "resource": ["llm"]})
        jwrite(r / "uncle" / "_metainfo", {"summary": "叔叔", "kind": "program", "resource": "cpu"})
        jwrite(r / "notes" / "_metainfo", {"summary": "資料", "kind": "data"})
        return r

    @staticmethod
    def no_at(p):
        d = jread(p)
        d.pop("rolled_at", None)
        return d

    # 12. rollup 單元
    def test_rollup(self):
        r = self.mini_tree()
        metas = {p: p.read_bytes() for p in r.rglob("_metainfo")}
        gc, mid, top, uncle = r / "mid/tools/gc/rollup.json", r / "mid/rollup.json", r / "rollup.json", r / "uncle/rollup.json"
        x = self.rollup(r, "uncle")
        self.assertEqual(x.returncode, 0, x.stderr)
        x = self.rollup(r, "--up", "mid/tools/gc")
        self.assertEqual(x.returncode, 0, x.stderr)
        self.assertEqual([l.split()[1] for l in x.stdout.splitlines() if l.startswith("rollup: ") and " val " in l], ["mid/tools/gc", "mid", "."])
        self.assertIn("rollup: DeclaredOff mid llm_tokens 1000 vs 5000", x.stdout)           # 宣告與實測差兩倍以上：只印
        m = jread(mid)
        self.assertEqual(m["children"], {"tools/gc": {"kind": "program", "val": "good", "stage": "program", "grad_total": {"determinism": 0.25}},
                                         "helper": {"kind": "agent", "stage": "agent"}})          # 中層 children 兩行（穿過 tools/ 容器）
        self.assertEqual((m["val"], m["stage"], m["cost"]["per_run"]["llm_tokens"], m["cost"]["declared"]["llm_tokens"]), ("ok", "semi", 5000, 1000))
        t = jread(top)
        self.assertEqual(t["brain"]["nodes"], {"mid": "semi", "mid/helper": "agent", "mid/tools/gc": "program", "uncle": "program"})   # 子樹/孫
        self.assertEqual((t["brain"]["counter_on_brain"], t["brain"]["counter_program"]), (2, 2))
        self.assertEqual(t["children"]["notes"], {"kind": "data"})                            # data 不算腦用量的節點
        self.assertNotIn("tools/gc", t["children"])                                          # 根不打開孫子
        # 孫子的評級與固化階改了、只重算根 → 根除 rolled_at 不變（根只讀 mid 的 rollup.json）
        before = self.no_at(top)
        jwrite(r / "mid" / "tools" / "gc" / "ratings.json", {"style:傲嬌": {"val": "bad"}})
        jwrite(r / "mid" / "tools" / "gc" / "stage.json", {"stage": "semi"})
        self.assertEqual(self.rollup(r, ".").returncode, 0)
        self.assertEqual(self.no_at(top), before)
        # --up 孫子 → 孫、中、根三份變；叔叔 bytes 不變
        snap = {p: p.read_bytes() for p in (gc, mid, top, uncle)}
        self.assertEqual(self.rollup(r, "--up", "mid/tools/gc").returncode, 0)
        self.assertEqual({p for p in snap if p.read_bytes() != snap[p]}, {gc, mid, top})
        self.assertEqual(jread(mid)["children"]["tools/gc"]["val"], "bad")
        self.assertEqual(jread(top)["brain"]["nodes"]["mid/tools/gc"], "semi")
        # 兩次除 rolled_at 全同
        once = {p: self.no_at(p) for p in (gc, mid, top)}
        self.assertEqual(self.rollup(r, "--up", "mid/tools/gc").returncode, 0)
        self.assertEqual({p: self.no_at(p) for p in once}, once)
        # --dry-run 不寫（--json 每層一行）
        snap = {p: p.read_bytes() for p in (gc, mid, top, uncle)}
        x = self.rollup(r, "--up", "--dry-run", "--json", "mid/tools/gc")
        self.assertEqual(x.returncode, 0, x.stderr)
        self.assertEqual([json.loads(l)["path"] for l in x.stdout.splitlines()], ["mid/tools/gc", "mid", "."])
        self.assertEqual({p: p.read_bytes() for p in snap}, snap)
        # 懸空 $ref → RefBad、退 1、一份都不寫（下面幾層也不寫）
        jwrite(r / "_metainfo", dict(jread(r / "_metainfo"), grad={"$ref": "nope.json"}))
        metas[r / "_metainfo"] = (r / "_metainfo").read_bytes()
        x = self.rollup(r, "--up", "mid/tools/gc")
        self.assertEqual(x.returncode, 1)
        self.assertRegex(x.stderr, r"^rollup: RefBad .*nope\.json")
        self.assertEqual({p: p.read_bytes() for p in snap}, snap)
        self.assertEqual(self.rollup(r, "nowhere").returncode, 1)
        self.assertTrue(self.rollup(r, "nowhere").stderr.startswith("rollup: RootMissing"))
        x = self.rollup(r, "mid/tools")                                                       # 純容器不是子樹
        self.assertEqual(x.returncode, 1)
        self.assertTrue(x.stderr.startswith("rollup: MetainfoBad"), x.stderr)
        self.assertEqual({p: p.read_bytes() for p in r.rglob("_metainfo")}, metas)          # _metainfo 一字不碰

    # 20. 搬得走：cp -r writer/ 到別棵樹 → rollup 不炸、梯度當 foreign、評級與固化階照列
    def test_rollup_portable(self):
        other = self.tmp / "other"
        jwrite(other / "_metainfo", {"summary": "別棵樹", "kind": "agent", "resource": ["llm"]})
        shutil.copytree(G / "writer", other / "writer", symlinks=True)       # 捷徑（../idle、../../tools/lint）在別棵樹裡懸空
        jwrite(other / "writer" / "grad.json", {"source": "s", "context": {"tree": "galtxt-a"}, "sum": {"determinism": 0.25}})
        jwrite(other / "writer" / "ratings.json", {"source": "s", "scope": {"style": "傲嬌"}, "style:傲嬌": {"val": "ok", "score_avg": 3.5}})
        x = self.rollup(other, "--up", "writer")
        self.assertEqual(x.returncode, 0, x.stderr)
        self.assertIn("foreign grad（context.tree galtxt-a）", x.stdout)
        w = jread(other / "rollup.json")["children"]["writer"]
        self.assertIsNone(w["grad_total"])
        self.assertEqual((w["grad_foreign"], w["val"], w["stage"]), ("galtxt-a", "ok", jread(G / "writer" / "stage.json")["stage"]))
        own = jread(other / "writer" / "rollup.json")
        self.assertEqual(own["children"]["tools/lint"], {"kind": "捷徑", "to": "../../tools/lint"})
        self.assertEqual((own["children"]["tools/beat"]["stage"], own["score_avg"]), ("program", 3.5))
        x = self.rollup(G, "--dry-run", "writer")                                            # 在原樹裡＝自己的梯度，不是 foreign
        self.assertEqual(x.returncode, 0, x.stderr)
        self.assertNotIn("foreign", x.stdout)

    # 17. M7：訓練前後 _metainfo、fsm.json、dims.json bytes 一樣；變的只有旁檔與該變的表
    #     （§ 10 的清單照步驟 4 已存在的檔走：weigh/rules.json、log.jsonl 步驟 5 才有，先不列）
    def test_m7(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "train" / "budget.json", dict(jread(g / "train" / "budget.json"), max_epochs=1))
        before = snapshot(g)
        r = run(EXEC, "--ws", str(self.ws), str(g / "train"), cwd=self.tmp, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = snapshot(g)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        frozen = {k for k in before if os.path.basename(k) in ("_metainfo", "fsm.json", "loop.json", "dims.json")} | {"train/weigh/rules.json"}
        self.assertIn("train/weigh/rules.json", before)                                       # 步驟 5：判斷器的規則表只有人改
        self.assertTrue(frozen and not (frozen & changed), frozen & changed)
        allowed = {"ratings.json", "stage.json", "grad.json", "rollup.json", "human.json", "hard.jsonl", "log.jsonl",
                   "templates.json", "templates.distilled.json", "samples.json", "route.json", "policy.json",
                   "opt_log.jsonl", "selfopt.json"}                                          # 6b：selfopt 的紀錄（節點自己的、優化器自己的）
        top = lambda k: "/".join(k.split("/")[:3])                                            # noqa: E731
        born = {k for k in changed if k.startswith("writer/tools/") and top(k) not in before}  # so-12：selfopt 新建的工具資料夾（有 author 的 _metainfo）
        self.assertTrue(born and all(jread(g / k)["author"].startswith("writer@selfopt") for k in born if k.endswith("/_metainfo")), born)
        self.assertEqual({k for k in changed if os.path.basename(k) not in allowed} - born, set())
        self.assertTrue({"rollup.json", "writer/rollup.json", "grader/rollup.json"} <= changed)    # rate／verify 叫了 rollup --up
        authored = {k for k in before if k.startswith(("data/cast/", "data/place/", "data/scene/", "data/style/")) or k == "data/templates.json"}
        self.assertTrue(len(authored) >= 5 and not (authored & changed), authored & changed)       # 3b-8：人寫的格檔訓練前後 bytes 不變
        for k in ("writer/tools/beat/rollup.json", "tools/lint/rollup.json", "train/optimize/rollup.json"):
            self.assertNotIn(k, changed)                                                      # 不在 --up 路上的子樹 bytes 不變
        root = jread(g / "rollup.json")
        self.assertEqual(root["children"]["writer"]["stage"], "semi")                         # 6b：epoch 0 的 selfopt 抽了 close、verify 收下
        self.assertEqual(root["brain"], {k: jread(g / "ratings.json")["style:傲嬌"]["brain"][k] for k in ("nodes", "counter_on_brain", "counter_program", "excluded")})

    # 21. metatable（rollup 要的最小部分）：writer 列有 ratings、stage；彙總有 on_brain；--suggest 對有旁檔的候選標 N-4
    def test_metatable_sidecars(self):
        r = run(METATABLE, "--json", str(G))
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        w = next(n for n in d["nodes"] if n["path"] == "writer")
        self.assertIsInstance(w["ratings"], dict)
        self.assertEqual(w["stage"], jread(G / "writer" / "stage.json")["stage"])
        self.assertNotIn("stage", next(n for n in d["nodes"] if n["path"] == "idle"))
        s = d["summary"]
        dirs = [n for n in d["nodes"] if n["path"] != "." and "#" not in n["path"] and n.get("kind") not in ("data", "捷徑", "壞")]
        self.assertEqual(s["counter_on_brain"] + s["counter_program"], len(dirs))
        on = {n["path"] for n in d["nodes"] if n.get("stage") in ("agent", "semi") or (n.get("kind") == "agent" and "stage" not in n)}
        self.assertTrue({"writer", "writer-sol", "grader", "train/weigh"} <= on, on)   # metatable 整棵樹都算（rollup 的 brain 才只算每題會被叫到的）
        self.assertGreaterEqual(s["counter_on_brain"], 4)
        self.assertIn("| on_brain／program 節點數", run(METATABLE, str(G)).stdout)
        t = self.tmp / "sug"
        jwrite(t / "_metainfo", {"summary": "根", "kind": "program", "reads": ["tbl:a.json"]})
        jwrite(t / "tbl" / "_metainfo", {"summary": "小表", "kind": "data", "fs_needs": ["git_tracked"]})
        jwrite(t / "tbl" / "a.json", {"source": "s", "x": 1})
        rows = json.loads(run(METATABLE, "--json", "--suggest", str(t)).stdout)["summary"]["suggest"]
        self.assertEqual([(x["path"], x["rule"]) for x in rows], [("tbl", "B-3")])          # 對照：沒旁檔＝照舊是候選
        jwrite(t / "tbl" / "rollup.json", {"source": "s"})
        rows = json.loads(run(METATABLE, "--json", "--suggest", str(t)).stdout)["summary"]["suggest"]
        self.assertEqual([(x["path"], x["rule"], x["action"]) for x in rows], [("tbl", "N-4（原 B-3）", "不縮")])
        self.assertIn("N-4", run(METATABLE, "--suggest", str(t)).stdout)

    # ---- 步驟 3b：設定拆成格（plan/round4-data.md § 5）----
    def brief_of(self, g, example, task=None, tag="b"):
        """在樹 g 上只跑 brief 一格；回 (退出碼, brief.json bytes, rules.json bytes, stderr)"""
        ws = self.fresh("%s-%s-%d" % (tag, example, len(os.listdir(self.tmp))))
        jwrite(ws / "new" / example, task if task is not None else jread(EXAMPLES / example))
        st = ws / ".stack"
        st.mkdir()
        r = run(EXEC, str(g / "fsm.json") + "#/states/brief/exec", env={"AOS_WS": str(ws), "AOS_STACK": str(st) + "/"})
        rd = lambda n: (st / n).read_bytes() if (st / n).exists() else None   # noqa: E731
        return r.returncode, rd("brief.json"), rd("rules.json"), r.stderr

    def test_cells_resolve(self):
        """3b-1：id → (檔, pointer, 值)；expand 的旗標；不存在＝CellMissing；檔長成資料夾 id 不變、brief 產物 bytes 不變"""
        self.assertEqual(CELLS.resolve("cast.yuzu.tic.03"), (str(G / "data" / "cast" / "yuzu.json"), "/tic/03", {"text": "才沒"}))
        self.assertEqual(CELLS.resolve("styles.ng_marks")[0], str(G / "data" / "styles.json"))       # 第一段就是 data/ 根下的檔
        self.assertEqual(CELLS.resolve("tpl.generic.open.01")[0], str(G / "data" / "templates.json"))
        with self.assertRaises(CELLS.CellMissing):
            CELLS.resolve("cast.yuzu.tic.99")
        with self.assertRaises(CELLS.CellMissing):
            CELLS.resolve("cast.nobody.tic.01")
        r = run("python3", str(G / "cells.py"), "get", "cast.yuzu.nope")
        self.assertEqual((r.returncode, r.stderr.count("\n")), (1, 1))
        self.assertTrue(r.stderr.startswith("cells: CellMissing"), r.stderr)
        g = tree_copy(self.tmp / "t")
        data = str(g / "data")
        yz = jread(g / "data" / "cast" / "yuzu.json")
        self.assertEqual(len(CELLS.expand("cast.yuzu.gesture.*[reveal]", data)), 5)
        yz["gesture"]["05"]["reveal"] = False
        jwrite(g / "data" / "cast" / "yuzu.json", yz)
        self.assertNotIn("cast.yuzu.gesture.05", CELLS.expand("cast.yuzu.gesture.*[reveal]", data))  # 只回 reveal 為真的
        self.assertIn("cast.yuzu.gesture.05", CELLS.expand("cast.yuzu.gesture.*", data))
        yz["gesture"]["05"]["reveal"] = True
        jwrite(g / "data" / "cast" / "yuzu.json", yz)
        before = {ex: self.brief_of(g, ex) for ex in ("Q16.json", "cls-ribbon.json")}
        grown = g / "data" / "cast" / "yuzu"                                  # 長成資料夾：一個頂層 key 一個 <key>.json
        for k, v in yz.items():
            jwrite(grown / (k if k == "_metainfo" else k + ".json"), v)
        (g / "data" / "cast" / "yuzu.json").unlink()                          # 在暫存拷貝裡
        self.assertEqual(CELLS.resolve("cast.yuzu.tic.03", data), (str(grown / "tic.json"), "/03", {"text": "才沒"}))
        for ex, want in before.items():
            got = self.brief_of(g, ex)
            self.assertEqual(got[0], 0, got[3])
            self.assertEqual(got[1:3], want[1:3], ex)

    def old_tree(self):
        """步驟 3b 之前那一版的整棵樹（git archive），放成可以跑的樹（lib 指回真的）；拿不到就 skip"""
        t = self.tmp / "old"
        t.mkdir()
        tar = t / "old.tar"
        r = subprocess.run(["git", "-C", str(ROOT), "archive", "-o", str(tar), BEFORE_3B, "topdown/galtxt-a"], capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("拿不到 3b 前那一版（%s）：%s" % (BEFORE_3B, r.stderr.strip()))
        (t / "proto8").mkdir()
        subprocess.run(["tar", "xf", str(tar), "-C", str(t / "proto8")], check=True)
        os.symlink(ROOT / "lib", t / "proto8" / "lib")
        return t / "proto8" / "topdown" / "galtxt-a"

    def test_cells_equivalent(self):
        """3b-2：晴子、Q01 的 brief／rules bytes 不變；Q16、cls 的 contrast 集合相同、每份 total 相同；cast.json 沒有第二份口癖"""
        old = self.old_tree()
        for ex in ("Q01.json", "scene.json"):
            a, b = self.brief_of(old, ex, tag="o"), self.brief_of(G, ex, tag="n")
            self.assertEqual(a[0], 0, a[3])
            self.assertEqual(a[1:3], b[1:3], ex)
        old_ex = old / "plan" / "examples"
        for ex in ("Q16.json", "cls-ribbon.json", "cls-poster.json", "cls-lights.json"):
            a, b = self.brief_of(old, ex, jread(old_ex / ex), tag="o"), self.brief_of(G, ex, tag="n")
            self.assertEqual(b[0], 0, b[3])
            ra, rb = json.loads(a[2]), json.loads(b[2])
            for k in ("deny", "yield", "cover", "reveal", "ooc"):
                self.assertEqual(set(ra["contrast"][k]), set(rb["contrast"][k]), (ex, k))
            ba, bb = json.loads(a[1]), json.loads(b[1])
            if ex.startswith("cls"):
                self.assertEqual(a[1], b[1], ex)                                   # event 渲染得一字不差
            else:
                ba.pop("speaker_note"), bb.pop("speaker_note")                     # 挖空題的說話者設定改從格渲染（規劃內）
                self.assertEqual(ba, bb)
        for ex in ("Q01.json", "scene.json", "Q16.json", "cls-ribbon.json"):
            got = []
            for g, src in ((old, old_ex), (G, EXAMPLES)):
                ws = self.fresh("eq-%s-%d" % (ex, len(got)))
                jwrite(ws / "new" / ex, jread(src / ex))
                r = self.galtxt(g, ws=ws)
                self.assertEqual(r.returncode, 0, r.stderr)
                got.append([d["total"] for d in jread(ws / "out" / ex[:-5] / "score.json")["drafts"]])
            self.assertEqual(got[0], got[1], ex)
        cast = (G / "data" / "cast.json").read_text(encoding="utf-8")
        self.assertNotIn("哼", cast)
        self.assertEqual((G / "data" / "cast" / "yuzu.json").read_text(encoding="utf-8").count('"哼"'), 1)

    def test_lint_hits(self):
        """3b-3：hits 指到格（反差＝決定分數的那兩格）；每個 hit 解得到、字面在輸入裡；沒 cells 表＝全 []、分數不變"""
        fill = self.lint_rules("Q16.json")
        line = "宮澤柚葉：「哼，才沒有。不過……也不是不能接受」"
        o = self.lint_dims(fill, line)
        self.assertEqual((o["hits"]["反差"], o["dims"]["反差"]), (["style.tsun.deny.03", "style.tsun.yield.01"], 1.0))
        self.assertEqual(o["hits"]["洩底"], [])
        self.assertIn("cast.yuzu.tic.01", o["hits"]["語域"])
        scene = self.lint_rules("cls-ribbon.json")
        text = "\n".join(["（宮澤柚葉別過臉，耳根有點紅。）", "主角：「宮澤，那個要丟嗎？」", line.replace("」", "。」"), "主角：「好。」", "宮澤柚葉：「真是的。」"])
        o2 = self.lint_dims(scene, text)
        self.assertIn("cast.yuzu.gesture.02", o2["hits"]["洩底"])
        for out, src in ((o, line), (o2, text)):
            for ids in out["hits"].values():
                for i in ids:
                    v = CELLS.resolve(i)[2]
                    ms = v if isinstance(v, list) else [CELLS.marker(v)]
                    self.assertTrue(any(m in src for m in ms), (i, ms))
        bare = dict(fill, contrast={k: v for k, v in fill["contrast"].items() if k != "cells"})
        o3 = self.lint_dims(bare, line)
        self.assertEqual(o3["hits"], {"反差": [], "洩底": [], "語域": []})
        self.assertEqual(o3["dims"], o["dims"])

    def test_event_render(self):
        """3b-4：場景題沒寫 event＝從 scene.detail 渲染；寫了＝照抄；detail 不在 scene＝DetailMissing"""
        want = {"cls-ribbon.json": "文化祭閉幕後的黃昏教室收攤：柚葉嘴上嫌麻煩地拆彩帶，卻偷偷捲了一段塞進書包",
                "cls-lights.json": "文化祭閉幕後的黃昏教室收攤：收完要關燈，柚葉按了開關，卻站在窗邊不走"}
        for ex, ev in want.items():
            self.assertNotIn("event", jread(EXAMPLES / ex))
            code, b, _, err = self.brief_of(G, ex)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(b)["event"], ev)
        code, b, _, err = self.brief_of(G, "cls-ribbon.json", dict(jread(EXAMPLES / "cls-ribbon.json"), event="人寫的事件"))
        self.assertEqual(json.loads(b)["event"], "人寫的事件")
        code, b, _, err = self.brief_of(G, "cls-ribbon.json", dict(jread(EXAMPLES / "cls-ribbon.json"), detail="nope"))
        self.assertEqual((code, err.count("\n")), (1, 1))
        self.assertTrue(err.startswith("galtxt-a brief: DetailMissing"), err)

    def judge_tasks(self, ws):
        return [p.read_text(encoding="utf-8") for p in sorted((ws / ".stack" / "judge" / "runs").glob("*/ws/*/*.txt")) if p.parent.name != "out"]

    def test_rubric_render(self):
        """3b-5：評審題目的「人物設定」從 dims.json 像柚葉的格渲染；改格→題目跟著變、system.txt 不變、假腦分數不變"""
        system = (G / "grader" / "system.txt").read_text(encoding="utf-8")
        self.assertNotIn("嘴硬心軟", system)
        traits = [CELLS.text(CELLS.resolve(i)[2]) for i in CELLS.expand("cast.yuzu.trait.*")]
        self.assertEqual(len(traits), 3)
        self.put("Q16.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        tasks = self.judge_tasks(self.ws)
        self.assertTrue(tasks)
        for t in tasks:
            self.assertTrue(all(x in t for x in traits), t)
        g = tree_copy(self.tmp / "t")
        yz = jread(g / "data" / "cast" / "yuzu.json")
        yz["trait"]["01"]["text"] = "說話像砂紙"
        jwrite(g / "data" / "cast" / "yuzu.json", yz)
        ws = self.fresh("ws-trait")
        self.put("Q16.json", ws)
        r = self.galtxt(g, ws=ws)
        self.assertEqual(r.returncode, 0, r.stderr)
        for t in self.judge_tasks(ws):
            self.assertIn("說話像砂紙", t)
            self.assertNotIn("嘴硬心軟", t.split("前後文")[0].split("人物設定")[1])
        self.assertEqual((g / "grader" / "system.txt").read_bytes(), (G / "grader" / "system.txt").read_bytes())
        self.assertEqual([v["scores"] for v in jread(ws / ".stack" / "judge.json").values()],
                         [v["scores"] for v in jread(self.ws / ".stack" / "judge.json").values()])

    def test_template_cells(self):
        """3b-6：模板格都有 text、uses 解得到；{prop} 從場景格來；poster 難例指到缺的格；distilled 接在後面；Q16 正解不在任何格"""
        for f, pre in (("templates.json", "tpl"), ("templates.distilled.json", "tpld")):
            js = jread(G / "data" / f)
            for i, c in CELLS.ids(js, pre).items():
                self.assertIsInstance(c["text"], str, i)
                for u in c.get("uses", []):
                    CELLS.resolve(u)
            self.assertEqual(js["_metainfo"]["counter_cells"], CELLS.count_cells(js), f)
        g = self.staged("program")
        sc = jread(g / "data" / "scene" / "closeup.json")
        sc["prop"]["ribbon"]["text"] = "紙鶴串"
        jwrite(g / "data" / "scene" / "closeup.json", sc)
        ws = self.fresh("ws-rb")
        self.put("cls-ribbon.json", ws)
        r = self.galtxt(g, ws=ws)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("紙鶴串", (ws / "out" / "cls-ribbon" / "answer.txt").read_text(encoding="utf-8"))
        ws = self.fresh("ws-po")
        self.put("cls-poster.json", ws)
        r = self.galtxt(g, ws=ws)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = jl(g / "writer" / "hard.jsonl")[0]
        self.assertEqual(row["cells"], ["scene.closeup.detail.poster"])
        self.assertTrue(row["cells_hit"] and all(CELLS.resolve(i, str(g / "data")) for i in row["cells_hit"]), row)
        self.assertTrue(row["tpl"] and all(i.startswith("tpl.generic.") for i in row["tpl"]), row)
        dd = jread(g / "data" / "templates.distilled.json")                      # distill 追加 poster 的否認句 → 不再是難例、用到 tpld 格
        dd["by_detail"] = {"poster": {"deny": {"01": {"text": "才不是捨不得這張海報", "for": "scene.closeup.detail.poster",
                                                      "teacher": "test", "since": 1, "by": "distill"}}}}
        jwrite(g / "data" / "templates.distilled.json", dd)
        (g / "writer" / "hard.jsonl").unlink()
        ws = self.fresh("ws-po2")
        self.put("cls-poster.json", ws)
        r = self.galtxt(g, ws=ws)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("才不是捨不得這張海報", (ws / "out" / "cls-poster" / "answer.txt").read_text(encoding="utf-8"))
        self.assertFalse((g / "writer" / "hard.jsonl").exists())
        q = jread(G / "data" / "bench" / "Q16.json")
        for p in (G / "data").rglob("*.json"):
            if p.name == "Q16.json":
                continue
            body = p.read_text(encoding="utf-8")
            for ans in (q["answer"], q["answer_min"]):
                self.assertNotIn(ans.split("：", 1)[1], body, p)

    def test_cell_hits_rate(self):
        """3b-7：score.json 每份有 hits；rate 彙成 cell_hits（手算）；dims.json 每維的 cells 都 expand 得到"""
        self.put("cls-ribbon.json")
        r = self.galtxt()
        self.assertEqual(r.returncode, 0, r.stderr)
        for d in jread(self.ws / "out" / "cls-ribbon" / "score.json")["drafts"]:
            self.assertEqual(set(d["hits"]), {"反差", "洩底", "語域"})
        prof = jread(G / "data" / "dims.json")["profiles"]["傲嬌"]
        for dim, spec in prof.items():
            for p in spec["cells"]:
                self.assertTrue(CELLS.expand(p), (dim, p))
        self.assertEqual((prof["文筆"]["cells"], prof["承接"]["cells"]), ([], []))
        g = tree_copy(self.tmp / "t")
        jwrite(g / "human" / "samples.json", [])
        st = self.tmp / "st"
        dims = {"反差": 1.0, "像柚葉": 0.667, "承接": 0.667, "文筆": 0.667, "語域": 0.5, "洩底": 0.5, "護欄": 1.0}
        hits = [{"反差": ["style.tsun.deny.03", "style.tsun.yield.01"], "洩底": ["cast.yuzu.gesture.02"], "語域": []},
                {"反差": ["style.tsun.deny.03"], "洩底": [], "語域": ["cast.yuzu.tic.01"]},
                {"反差": ["style.tsun.deny.01"], "洩底": [], "語域": []}]
        drafts = [{"n": i + 1, "tier0": [] if i < 2 else ["FormatBad"], "tier1": 1, "total": 3.5 if i < 2 else 0,
                   "dims": dict(dims, 護欄=1.0 if i < 2 else 0.0), "hits": h} for i, h in enumerate(hits)]
        jwrite(st / "epochs" / "001" / "runs" / "a" / "ws" / "out" / "a" / "score.json",
               {"name": "a", "writer": "writer", "style": "傲嬌", "dims": {"多樣性": 0.3}, "drafts": drafts})
        r = run("python3", str(g / "train" / "rate.py"), env={"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws)}, cwd=g / "train")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(jread(g / "writer" / "ratings.json")["style:傲嬌"]["cell_hits"],     # 第三份沒過護欄＝不算
                         {"cast.yuzu.gesture.02": 1, "cast.yuzu.tic.01": 1, "style.tsun.deny.03": 2, "style.tsun.yield.01": 1})

    def test_cells_metainfo(self):
        """3b-8：data/_metainfo 列出每個格檔；每個格檔 counter_cells＝程式數的；metatable 行數不因多一格而變"""
        meta = jread(G / "data" / "_metainfo")
        files = ("cast/yuzu.json", "style/tsun.json", "place/classroom.json", "scene/closeup.json", "templates.json", "templates.distilled.json")
        total = 0
        for f in files:
            self.assertIn(f.split("/")[0] + ("/" if "/" in f else ""), meta["children"], f)
            js = jread(G / "data" / f)
            self.assertEqual(js["_metainfo"]["counter_cells"], CELLS.count_cells(js), f)
            per = js["_metainfo"].get("cells")
            if per:
                self.assertEqual(per, {k: CELLS.count_cells(js[k]) for k in per}, f)
            total += js["_metainfo"]["counter_cells"]
        self.assertEqual(meta["counter_cells"], total)
        self.assertIn("shared_write", meta["fs_needs"])
        g = tree_copy(self.tmp / "t")
        rows = lambda: len(json.loads(run(METATABLE, "--json", str(g)).stdout)["nodes"])   # noqa: E731
        n = rows()
        yz = jread(g / "data" / "cast" / "yuzu.json")
        yz["tic"]["06"] = {"text": "笨蛋"}
        jwrite(g / "data" / "cast" / "yuzu.json", yz)
        self.assertEqual(rows(), n)


ROLLUP = str(G / "meta" / "rollup" / "_entry")
BEFORE_3B = "970b8e2c"          # 步驟 3b（設定拆成格）之前那一版
sys.path.insert(0, str(G))
sys.dont_write_bytecode = True  # 樹裡不留 __pycache__
import cells as CELLS  # noqa: E402



# 梯度分配與回滾的單元驗的是機制、不是假腦的確定性模型：人寫的 beat 不接手假腦會隨抽樣變的環節（開場／收尾旁白），
# 所以 epoch 1 關掉抽樣差（GALTXT_FAKE_JITTER=0）當作「抽了工具、確定性升」。整條訓練（so-10）不設這個，靠 selfopt 抽 close／open 自己升。
STEADY = {"GALTXT_FAKE_JITTER": "0"}


def common_of(g):
    """拷貝樹的 train/common.py（ROOT＝拷貝），給測試叫 params_save、diff"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("galtxt_common_%x" % abs(hash(str(g))), str(g / "train" / "common.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Round4GradT(unittest.TestCase):
    """第四輪步驟 5（plan/round4.md § 4、§ 5.4；§ 10 測試 10、11、14、16）：diff、判斷器樹、verify 的梯度／判斷／回滾／分配。全部假腦、在拷貝上跑。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)

    # 10. diff：數值差、非數值 [舊,新]、集合 {+,-}、沒變的鍵不出現；兩邊同＝{}
    def test_diff(self):
        c = common_of(G)
        b = {"stage": "agent", "determinism": 0.3, "val": "ok", "cost": {"llm_tokens": 7000, "llm_calls": 2}, "dims": {"反差": 0.5, "洩底": None, "語域": 0.5},
             "tags": ["太直白", "承接自然"], "cells": ["cast.yuzu.tic.01"], "bench": {"guard_hit": 1}}
        a = {"stage": "semi", "determinism": 0.55, "val": "ok", "cost": {"llm_tokens": 8500, "llm_calls": 3}, "dims": {"反差": 0.75, "洩底": 0.5, "語域": 0.5},
             "tags": ["承接自然", "嘴硬心軟"], "cells": ["cast.yuzu.tic.01", "style.tsun.deny.03"], "bench": {"guard_hit": 1}}
        self.assertEqual(c.diff(b, a), {"stage": ["agent", "semi"], "determinism": 0.25, "cost.llm_tokens": 1500, "cost.llm_calls": 1,
                                        "dims.反差": 0.25, "dims.洩底": [None, 0.5], "tags": {"+": ["嘴硬心軟"], "-": ["太直白"]},
                                        "cells": {"+": ["style.tsun.deny.03"], "-": []}})
        self.assertEqual(c.diff(b, json.loads(json.dumps(b))), {})
        self.assertEqual(c.diff({}, {}), {})
        self.assertEqual(c.diff({"x": 1}, {}), {"x": [1, None]})
        self.assertEqual(c.diff({"v": 0.1 + 0.2}, {"v": 0.3}), {})                     # 三位小數內一樣＝沒變
        v = {"score_mean": 3.5, "counter_samples": 6, "dims": {"反差": 1.0}, "measure": {"一致": 0.5}, "guard_hit": 1, "bigram_overlap": 0.1,
             "tags": {"假腦": 6}, "cell_hits": {"cast.yuzu.tic.01": 3}, "brain": {"llm_tokens_per_question": 900, "llm_calls_per_question": 4}}
        sn = c.snapshot(v, {"stage": "semi", "tools": ["lint", "beat"]}, None)
        self.assertEqual(sn, {"val": "ok", "total_avg": 3.5, "determinism": 0.5, "dims": {"反差": 1.0}, "bench": {"guard_hit": 1, "bigram_overlap": 0.1},
                              "tags": ["假腦"], "cells": ["cast.yuzu.tic.01"], "cost": {"llm_tokens": 900, "llm_calls": 4},
                              "stage": "semi", "tools": ["beat", "lint"]})
        self.assertEqual(c.snapshot(v, None, {"llm_tokens": 0, "llm_calls": 0})["cost"], {"llm_tokens": 0, "llm_calls": 0})   # 那棵量得到＝用它的
        self.assertEqual(c.cell_prefix("data/templates.distilled.json"), "tpld")
        self.assertEqual(c.cell_prefix("data/cast/yuzu.json"), "cast.yuzu")
        self.assertIsNone(c.cell_prefix("writer/stage.json"))

    def weigh(self, g, qs, stage):
        ws = self.tmp / ("ws-" + stage)
        for i, q in enumerate(qs):
            jwrite(ws / "new" / ("%02d.json" % i), q)
        r = run(EXEC, "--dotenv-override", "--ws", str(ws), str(g / "train" / "weigh"),
                env={"AOS_STACK": str(self.tmp / ("st-" + stage)) + "/", "GALTXT_WEIGH_STAGE": stage}, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [(ws / "out" / ("%02d.json" % i)).read_text(encoding="utf-8").splitlines()[0] for i in range(len(qs))]

    # 11. 判斷器：rules.json 既定 → 護欄掉 B、token 歸零且 −0.2 A、−0.4 B、確定性 +0.2 token +1.5k A、全零 B；log.jsonl 一題一行；agent／rules 兩階相同；_metainfo 不變
    def test_weigh(self):
        g = tree_copy(self.tmp / "t")
        meta = (g / "train" / "weigh" / "_metainfo").read_bytes()
        P = {"min_gain": 0.25, "min_loss": 0.25}
        b0 = {"val": "ok", "total_avg": 3.5, "determinism": 0.3, "cost": {"llm_tokens": 7000, "llm_calls": 2}, "dims": {"護欄": 1.0}, "bench": {"guard_hit": 1}}
        c = common_of(g)

        def q(after):
            a = json.loads(json.dumps(b0))
            for k, x in after.items():
                h, _, t = k.partition(".")
                if t:
                    a[h][t] = x
                else:
                    a[k] = x
            return {"A": c.diff(b0, a), "B": {}, "before": b0, "after": a, "params": P, "epoch": 1, "subtree": "writer", "action": "t"}
        qs = [q({"dims.護欄": 0.5}),                                                       # 護欄掉 → B
              q({"cost.llm_tokens": 0, "cost.llm_calls": 0, "total_avg": 3.3}),            # token 歸零、分 −0.2 → A
              q({"cost.llm_tokens": 0, "cost.llm_calls": 0, "total_avg": 3.3, "val": "bad"}),   # 評級掉但殼拿掉、分沒掉超過 min_loss → A（固化的交換條件）
              q({"cost.llm_tokens": 0, "cost.llm_calls": 0, "total_avg": 3.1}),            # token 歸零、分 −0.4 → B
              q({"determinism": 0.5, "cost.llm_tokens": 8500, "cost.llm_calls": 3}),       # 確定性 +0.2、token +1.5k（半固化過渡）→ A
              q({}),                                                                       # 全零 → B
              q({"val": "bad", "total_avg": 3.4, "determinism": 0.9}),                     # 評級掉、腦沒拿掉 → B（就算確定性升）
              q({"bench.guard_hit": 0, "determinism": 0.9})]                               # Q16 錨掉 → B
        want = ["B", "A", "A", "B", "A", "B", "B", "B"]
        self.assertEqual(qs[5]["A"], {})
        for stage in ("agent", "rules"):
            got = self.weigh(g, qs, stage)
            self.assertEqual([l[-1] for l in got], want, stage)
            self.assertTrue(all(l.startswith("選：") for l in got))
        log = jl(g / "train" / "weigh" / "log.jsonl")
        self.assertEqual(len(log), 2 * len(qs))
        self.assertEqual([x["choice"] for x in log], want * 2)
        self.assertEqual({x["by"] for x in log}, {"train/weigh（agent）", "train/weigh（rules）"})
        self.assertEqual(log[1]["diff"], qs[1]["A"])
        self.assertTrue((self.tmp / "st-agent" / "history.jsonl").is_file())           # agent 階真的走了 loop（假腦）
        self.assertFalse((self.tmp / "st-rules" / "history.jsonl").exists())           # rules 階 0 次腦
        self.assertEqual((g / "train" / "weigh" / "_metainfo").read_bytes(), meta)
        (self.tmp / "ws-bad" / "new").mkdir(parents=True)
        r = run(EXEC, "--ws", str(self.tmp / "ws-bad"), str(g / "train" / "weigh"),
                env={"AOS_STACK": str(self.tmp / "st-bad") + "/", "GALTXT_WEIGH_STAGE": "nope"}, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("weigh: StateBad", r.stderr)

    def verify(self, g, st, env=None):
        return run(EXEC, str(g / "train" / "fsm.json") + "#/states/verify/exec",
                   env=dict({"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws)}, **(env or {})), timeout=600)

    def change(self, g, st, n, stage, change, created=()):
        """照 optimize 會做的：params_save（快照＋changed.json）→ 改 writer/stage.json"""
        common_of(g).params_save(str(st), n, change, ["writer/stage.json"], created=created)
        s = jread(g / "writer" / "stage.json")
        s.update(stage)
        jwrite(g / "writer" / "stage.json", s)

    def epoch0(self, g, st):
        r = self.verify(g, st)                                                    # 6b 起假腦 agent 預設就有抽樣差＝確定性 < 1
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(jread(st / "epochs" / "000" / "verify.json")["measure"]["一致"], 1.0)
        self.assertEqual((st / "epoch.txt").read_text(), "1\n")
        self.assertFalse((g / "train" / "weigh" / "log.jsonl").exists())           # 沒有 changed.json＝不叫判斷器

    # 14. 梯度分配：extract → writer/grad.json 與 tools/beat/grad.json 同一筆（assigned_from）；stage program → beat、voice 按叫用次數分攤、和為 1；lint、grader 不動
    def test_grad_assign(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        keep = {k: x for k, x in snapshot(g).items() if k.startswith(("grader/", "tools/lint/"))}
        self.epoch0(g, st)
        self.change(g, st, 1, {"stage": "semi", "tools": ["lint", "beat"]},
                    {"source": "test", "action": "extract", "subtree": "writer", "target": "tools/beat"})
        r = self.verify(g, st, env=STEADY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weigh A（確定性升）writer/extract", r.stdout)
        w, b = jread(g / "writer" / "grad.json"), jread(g / "writer" / "tools" / "beat" / "grad.json")
        s0 = w["steps"][0]
        self.assertEqual((s0["epoch"], s0["action"], s0["target"], s0["accepted"], s0["weigh"]["choice"]), (1, "extract", "tools/beat", True, "A"))
        self.assertEqual(s0["diff"]["stage"], ["agent", "semi"])
        self.assertEqual(s0["diff"]["tools"], {"+": ["beat"], "-": []})
        self.assertGreater(s0["diff"]["determinism"], 0)
        self.assertEqual(s0["changed_cells"], [])
        self.assertEqual(w["context"]["tree"], g.name)
        self.assertEqual((w["counter_steps"], w["counter_accepted"], w["counter_rolled_back"]), (1, 1, 0))
        self.assertEqual(w["sum"]["determinism"], s0["diff"]["determinism"])
        t0 = b["steps"][0]
        self.assertEqual((t0["assigned_from"], t0["step_epoch"], t0["assigned_share"]), ("writer", 1, 1))
        self.assertEqual((t0["diff"], t0["weigh"]), (s0["diff"], s0["weigh"]))
        self.assertNotIn("steps", jread(g / "writer" / "tools" / "voice" / "grad.json"))
        hist = jread(g / "writer" / "stage.json")["history"]
        self.assertEqual([(h["epoch"], h["stage"]) for h in hist], [(0, "agent"), (1, "semi")])
        self.assertEqual((hist[1]["action"], hist[1]["accepted"]), ("extract", True))
        self.assertEqual(jread(g / "train" / "optimize" / "ratings.json")["action:extract"]["counter_accepted"], 1)
        self.assertEqual(jread(g / "train" / "weigh" / "ratings.json")["judge:accept"]["counter_judged"], 1)
        self.assertEqual(len(jl(g / "train" / "weigh" / "log.jsonl")), 1)
        self.assertEqual(jread(g / "writer" / "rollup.json")["children"]["tools/beat"]["grad_total"]["determinism"], s0["diff"]["determinism"])
        self.assertIn("train/weigh", jread(g / "rollup.json")["brain"]["nodes"])
        # epoch 2：殼拿掉（stage program）→ 沒新工具，按叫用次數分給 beat、voice（lint 是捷徑，不算寫手的）
        self.change(g, st, 2, {"stage": "program", "tools": ["lint", "beat", "voice"]},
                    {"source": "test", "action": "stage", "subtree": "writer"})
        r = self.verify(g, st)
        self.assertIn(r.returncode, (0, 10), r.stderr)
        s1 = jread(g / "writer" / "grad.json")["steps"][1]
        self.assertEqual((s1["epoch"], s1["action"]), (2, "stage"))
        self.assertLess(s1["diff"]["cost.llm_calls"], 0)
        shares = {}
        for t in ("beat", "voice"):
            last = jread(g / "writer" / "tools" / t / "grad.json")["steps"][-1]
            self.assertEqual((last["assigned_from"], last["step_epoch"], last["action"]), ("writer", 2, "stage"))
            shares[t] = last["assigned_share"]
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=6)
        e1, e2 = (jread(st / "epochs" / x / "verify.json")["brain"] for x in ("001", "002"))
        self.assertEqual((e1["nodes"]["writer"], e2["nodes"]["writer"]), ("semi", "program"))   # brain 記這次實際跑的階
        self.assertEqual(e2["counter_on_brain"], e1["counter_on_brain"] - 1)                 # § 2.3 成功判準：on_brain 往下
        self.assertTrue(all(0 < x < 1 for x in shares.values()), shares)
        self.assertEqual({k: x for k, x in snapshot(g).items() if k.startswith(("grader/", "tools/lint/"))}, keep)

    # 16. 回滾：rules.json 暫改成「確定性升也拒」→ epoch 1 verify 退 10、stage.json 拷回、新建的工具資料夾刪掉、grad accepted false、counter_rolled_back 1
    def test_rollback(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        rules = jread(g / "train" / "weigh" / "rules.json")
        rules["reject_if"].append({"key": "determinism", "gt": 0, "label": "確定性升也拒"})
        jwrite(g / "train" / "weigh" / "rules.json", rules)
        self.epoch0(g, st)
        stage0 = jread(g / "writer" / "stage.json")
        (g / "writer" / "tools" / "close").mkdir()                                   # selfopt 會新建工具資料夾：回滾要整個刪
        (g / "writer" / "tools" / "close" / "tool.json").write_text("{}")
        self.change(g, st, 1, {"stage": "semi", "tools": ["lint", "beat"]},
                    {"source": "test", "action": "extract", "subtree": "writer", "target": "tools/beat"}, created=["writer/tools/close"])
        r = self.verify(g, st, env=STEADY)
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertIn("train: Regressed epoch 1 回滾 writer/extract beat（weigh: 拒A：確定性升也拒）", r.stderr)
        s = jread(g / "writer" / "stage.json")
        self.assertEqual((s["stage"], s["tools"]), ("agent", ["lint"]))
        self.assertEqual({k: x for k, x in s.items() if k != "history"}, {k: x for k, x in stage0.items() if k != "history"})
        self.assertEqual([(h["epoch"], h["stage"]) for h in s["history"]], [(0, "agent"), (1, "semi")])   # 記的是這次實際跑的階
        self.assertFalse(s["history"][1]["accepted"])
        self.assertFalse((g / "writer" / "tools" / "close").exists())
        w = jread(g / "writer" / "grad.json")
        self.assertFalse(w["steps"][0]["accepted"])
        self.assertEqual(w["steps"][0]["rolled_back"], ["writer/stage.json", "writer/tools/close"])
        self.assertEqual((w["counter_rolled_back"], w["counter_accepted"]), (1, 0))
        self.assertNotIn("determinism", w["sum"])                                   # 被拒的步不進 sum
        self.assertFalse(jread(g / "writer" / "tools" / "beat" / "grad.json")["steps"][0]["accepted"])
        a = jread(g / "train" / "optimize" / "ratings.json")["action:extract"]
        self.assertEqual((a["counter_applied"], a["counter_rolled_back"]), (1, 1))
        self.assertEqual((st / "epoch.txt").read_text(), "1\n")
        r = self.verify(g, st)                                                       # 收工後再叫：照 verify.json 退 10、不重判
        self.assertEqual(r.returncode, 10)
        self.assertEqual(len(jl(g / "train" / "weigh" / "log.jsonl")), 1)
        bad = self.tmp / "st2"                                                       # changed.json 的路徑出樹＝StateBad
        (bad / "epochs" / "001" / "params").mkdir(parents=True)
        shutil.copytree(st / "epochs" / "000", bad / "epochs" / "000")
        (bad / "epoch.txt").write_text("1\n")
        jwrite(bad / "epochs" / "001" / "params" / "changed.json",
               {"source": "test", "action": "extract", "subtree": "writer", "files": ["../../outside.json"], "created": []})
        r = self.verify(g, bad)
        self.assertEqual(r.returncode, 1)
        self.assertIn("train: StateBad", r.stderr)


class Round4OptT(unittest.TestCase):
    """步驟 6b（round4 § 5、§ 6；round4-selfopt.md § 3）：優化器照樹走＋selfopt 派工＋SelfoptFallback。§ 10 的 9、13、15、18 與 selfopt 的 so-8、so-10、so-11。全部假腦、tree_copy 上跑。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def optimize(self, g, st, *args, env=None):
        return run(str(g / "train" / "optimize" / "_entry"), *args, env=dict({"AOS_STACK": str(st) + "/"}, **(env or {})), timeout=600)

    def verify(self, g, st, env=None):
        return run(EXEC, str(g / "train" / "fsm.json") + "#/states/verify/exec",
                   env=dict({"AOS_STACK": str(st) + "/", "AOS_WS": str(self.ws)}, **(env or {})), timeout=600)

    def stage(self, g, **kw):
        jwrite(g / "writer" / "stage.json", dict(jread(g / "writer" / "stage.json"), **kw))

    def hard(self, g, *details):
        with open(g / "writer" / "hard.jsonl", "a", encoding="utf-8") as f:
            for d in details:
                f.write(json.dumps({"at": "t", "question": "cls-%s" % d, "brief_key": {"mode": "scene", "detail": d}, "why": "TemplateMissing",
                                    "output": "…", "cells": ["scene.closeup.detail.%s" % d]}, ensure_ascii=False) + "\n")

    # 13. 優化器照樹走：根 rollup（writer agent 21k、grader agent 7k、lint program）→ --dry-run 挑 writer、selfopt extract；
    #     tools_share 0.67 → stage program；program＋hard 有 poster → selfopt distill（held-out 的 lights 不算）；writer 沒動作 → 印「這圈沒動作」換下一棵；
    #     不是 --dry-run 的外部動作 → params/changed.json＋快照、stage.json 改了
    def test_optimize_tree(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        jwrite(g / "rollup.json", {"source": "t", "brain": {"nodes": {"writer": "agent", "grader": "agent", "tools/lint": "program", "train/weigh": "agent"}},
                                   "children": {"writer": {"cost": {"llm_tokens": 21000, "llm_calls": 2}}, "grader": {"cost": {"llm_tokens": 7000, "llm_calls": 3}},
                                                "tools/lint": {"cost": {"llm_tokens": 0, "llm_calls": 0}}}})
        before = snapshot(g)
        r = self.optimize(g, st, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"optimize: epoch 0 挑 writer（agent，calls 2/次、tokens 21000/次，determinism [^，]+，tools_share 0.17） → selfopt extract（腦還在做：開場旁白")
        self.assertEqual(snapshot(g), before)                                        # --dry-run 不寫、不派工
        self.assertFalse(st.exists())
        self.stage(g, stage="semi", tools=["lint", "beat", "voice"])               # 自檢＋反差節拍／遮掩句＋口癖句尾＝4/6
        r = self.optimize(g, st, "--dry-run")
        self.assertIn("tools_share 0.67） → stage program", r.stdout)
        self.stage(g, stage="program")
        self.hard(g, "lights", "poster")
        r = self.optimize(g, st, "--dry-run")
        self.assertIn("grader（agent，calls 3/次、tokens 7000/次", r.stdout)       # 還靠腦的先：grader 排在 program 的 writer 前面、沒動作
        self.assertIn("grader（agent，calls 3/次、tokens 7000/次，determinism None，tools_share None） 這圈沒動作", r.stdout)
        self.assertRegex(r.stdout, r"挑 writer（program.*→ selfopt distill（hard.jsonl 有模板接不住的 poster）")   # lights 是 held-out，不算
        (g / "writer" / "hard.jsonl").unlink()
        self.hard(g, "lights")
        r = self.optimize(g, st, "--dry-run")
        self.assertRegex(r.stdout, r"writer（program[^\n]*這圈沒動作")
        self.assertIn("optimize: 這圈沒有可做的動作", r.stdout)
        self.stage(g, stage="semi")                                                  # 真的改：外部動作留回滾清單
        (st).mkdir()
        (st / "epoch.txt").write_text("1\n")
        r = self.optimize(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        ch = jread(st / "epochs" / "001" / "params" / "changed.json")
        self.assertEqual((ch["source"], ch["action"], ch["subtree"], ch["target"], ch["files"]), ("optimize", "stage", "writer", "program", ["writer/stage.json"]))
        self.assertTrue(all((st / "epochs" / "001" / "params" / f).is_file() for f in ch["files"]))
        self.assertEqual(jread(st / "epochs" / "001" / "params" / "writer" / "stage.json")["stage"], "semi")
        self.assertEqual((jread(g / "writer" / "stage.json")["stage"], jread(g / "writer" / "stage.json")["since_epoch"]), ("program", 1))
        r = self.optimize(g, st)                                                     # 同一個 epoch 再叫：不重做
        self.assertIn("epoch 1 已經改過 writer/stage", r.stdout)
        r = self.optimize(g, st, "--bogus")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^optimize: FlagUnknown \S")

    # 9. 蒸餾：program 階 hard.jsonl 有 poster（＋held-out 的 lights）→ optimize 派 selfopt distill（shell＋假老師）→ templates.distilled.json 多 poster 的
    #    deny／yield／cover／open、沒有 lights（工具回 HeldOut）；changed.json.files 含它；verify 判 A（難例接住了）→ poster 那行 resolved_epoch；再跑 poster 不再記難例
    def test_distill(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        self.stage(g, stage="program", tools=["lint", "beat", "voice"])
        r = self.verify(g, st)                                                       # epoch 0（program；lights 會記一筆 held-out 的難例）
        self.assertEqual(r.returncode, 0, r.stderr)
        self.hard(g, "poster")
        r = self.optimize(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("→ selfopt distill（hard.jsonl 有模板接不住的 poster）；by auto", r.stdout)
        self.assertIn("run: writer by shell", r.stdout)                              # program 階＝純程式節點：臨時配 shell 當腦
        self.assertIn("optimize: selfopt writer distill：收了", r.stdout)
        by = jread(g / "data" / "templates.distilled.json")["by_detail"]
        self.assertEqual(set(by), {"poster"})                                        # held-out 的 lights 沒蒸進去
        self.assertTrue({"deny", "yield", "cover", "open"} <= set(by["poster"]))
        self.assertEqual(by["poster"]["deny"]["01"]["teacher"], "writer@agent")
        hist = jl(next((st / "epochs" / "001" / "selfopt" / "writer").glob("*/stack/history.jsonl")))
        self.assertTrue(any("HeldOut" in (m.get("content") or "") for m in hist if m.get("role") == "tool"))   # 假老師先試了 lights、被工具擋
        tries = [json.loads(c["function"]["arguments"]) for m in hist for c in m.get("tool_calls") or [] if c["function"]["name"] == "opt_try"]
        self.assertEqual(tries, [{"question": "cls-poster.json", "drafts": 1, "stage": "agent"}])   # 老師＝自己的 agent 階
        ch = jread(st / "epochs" / "001" / "params" / "changed.json")
        self.assertIn("data/templates.distilled.json", ch["files"])
        self.assertEqual((ch["action"], ch["goal"], ch["target"], ch["by"]), ("selfopt", "distill", "data/templates.distilled.json", "shell@selfopt"))
        self.assertEqual(jread(g / "writer" / "stage.json")["stage"], "program")      # distill 不換階
        r = self.verify(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weigh A（難例接住了）writer/selfopt", r.stdout)
        step = jread(g / "writer" / "grad.json")["steps"][-1]
        self.assertEqual((step["diff"]["hard.uncovered"], step["accepted"]), (-1, True))
        self.assertTrue(step["changed_cells"] and all(x.startswith("tpld.by_detail.poster.") for x in step["changed_cells"]))
        rows = {r_["brief_key"]["detail"]: r_ for r_ in jl(g / "writer" / "hard.jsonl")}
        self.assertEqual(rows["poster"]["resolved_epoch"], 1)
        self.assertEqual(sorted(rows["poster"]["resolved_cells"]), sorted(step["changed_cells"]))
        self.assertNotIn("resolved_epoch", rows["lights"])
        n = len(jl(g / "writer" / "hard.jsonl"))
        task = jread(EXAMPLES / "cls-poster.json")
        jwrite(self.ws / "new" / "cls-poster.json", task)
        r = run(EXEC, "--ws", str(self.ws), str(g), cwd=self.tmp, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(jl(g / "writer" / "hard.jsonl")), n)                   # 接得住了：不再記難例
        self.assertIn("折", (self.ws / "out" / "cls-poster" / "answer.txt").read_text(encoding="utf-8"))   # 用到蒸餾的句子

    # 15＋so-10. 整條訓練（假腦，max_epochs 4；§ 7.3 的四步要四個 epoch）：selfopt 抽 close → selfopt 抽 open → stage program（外部）→ selfopt 蒸餾 poster；
    #     判斷器四次都 A；held-out 的 lights 沒進模板；前四筆 history＝§ 10 測試 15 的 agent, semi, semi, program
    def test_train_selfopt(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "train" / "budget.json", dict(jread(g / "train" / "budget.json"), max_epochs=4))
        before = snapshot(g)
        r = run(EXEC, "--ws", str(self.ws), str(g / "train"), cwd=self.tmp, timeout=1200)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([t["state"] for t in jl(self.stack / "trace.jsonl")], ["verify", "train", "rate", "optimize"] * 4 + ["verify"])
        for line in ("optimize: epoch 1 挑 writer（agent", "→ selfopt extract", "抽了 close", "optimize: epoch 2 挑 writer（semi", "抽了 open",
                     "optimize: epoch 3 挑 writer（semi", "tools_share 0.5） → stage program", "optimize: epoch 4 挑 writer（program", "→ selfopt distill",
                     "weigh A（確定性升）writer/selfopt", "weigh A（評級升）writer/stage", "weigh A（難例接住了）writer/selfopt"):
            self.assertIn(line, r.stdout)
        s = jread(g / "writer" / "stage.json")
        hist = s["history"]
        self.assertEqual([h["stage"] for h in hist], ["agent", "semi", "semi", "program", "program"])
        self.assertEqual([(h.get("action"), h.get("accepted")) for h in hist[1:]], [("selfopt", True), ("selfopt", True), ("stage", True), ("selfopt", True)])
        det = [h["determinism"] for h in hist]
        self.assertTrue(det[0] < det[1] < det[2] == 1.0 and det == sorted(det), det)   # 抽一個工具升一截；殼拿掉前已 1.0（假腦只在開場／收尾旁白抽樣）
        self.assertEqual((s["tools"], s["tools_share"]), (["lint", "close", "open"], 0.5))
        self.assertEqual(s["decisions_left"], ["反差節拍", "口癖句尾", "遮掩句"])
        steps = jread(g / "writer" / "grad.json")["steps"]
        self.assertEqual([(x["action"], x.get("goal"), x["target"]) for x in steps],
                         [("selfopt", "extract", "tools/close"), ("selfopt", "extract", "tools/open"), ("stage", None, "program"),
                          ("selfopt", "distill", "data/templates.distilled.json")])
        self.assertEqual(steps[3]["by"], "shell@selfopt")
        for t in ("close", "open"):                                                  # selfopt 抽的工具＝那步整筆、殼拿掉那步分攤
            ts = jread(g / "writer" / "tools" / t / "grad.json")["steps"]
            self.assertEqual([(x["action"], x["assigned_share"]) for x in ts][0], ("selfopt", 1))
            self.assertEqual(ts[1]["action"], "stage")
            self.assertTrue(jread(g / "writer" / "tools" / t / "_metainfo")["author"].startswith("writer@selfopt"))
        self.assertEqual([x["choice"] for x in jl(g / "train" / "weigh" / "log.jsonl")], ["A"] * 4)
        o = jread(g / "train" / "optimize" / "ratings.json")
        self.assertEqual((o["action:selfopt"]["counter_accepted"], o["action:stage"]["counter_accepted"]), (3, 1))
        so = jread(g / "train" / "optimize" / "selfopt.json")
        self.assertEqual([(x["epoch"], x["goal"], x["by"], x["accepted"]) for x in so["runs"]],
                         [(1, "extract", "node", True), (2, "extract", "node", True), (4, "distill", "shell", True)])
        self.assertTrue(all(isinstance(x["counter_calls"], int) and x["counter_calls"] > 0 and isinstance(x["elapsed_ms"], int) for x in so["runs"]))
        self.assertEqual((so["sum"]["counter_runs"], so["sum"]["counter_accepted"]), (3, 3))
        root = jread(g / "rollup.json")["brain"]
        self.assertEqual(root["nodes"]["writer"], "program")
        self.assertTrue({"writer/tools/close", "writer/tools/open"} <= set(root["nodes"]))
        brains = [jread(self.stack / "epochs" / ("%03d" % i) / "verify.json")["brain"] for i in range(5)]
        tok = [b["llm_tokens_per_question"] for b in brains]
        self.assertEqual(tok, sorted(tok, reverse=True))                             # 單調不升（假腦 0）
        self.assertEqual(brains[-1]["counter_on_brain"], brains[0]["counter_on_brain"] - 1)
        self.assertLess(brains[3]["llm_calls_per_question"], brains[0]["llm_calls_per_question"])   # 殼拿掉：寫手的腦歸零
        self.assertEqual(brains[4]["llm_calls_per_question"], brains[3]["llm_calls_per_question"])  # epoch 4 前派的 selfopt（8 次腦）不算進每題
        by = jread(g / "data" / "templates.distilled.json")["by_detail"]
        self.assertEqual(set(by), {"poster"})                                        # poster 蒸進來、held-out 的 lights 沒有
        rows = {x["brief_key"]["detail"]: x for x in jl(g / "writer" / "hard.jsonl")}
        self.assertEqual((rows["poster"].get("resolved_epoch"), rows["lights"].get("resolved_epoch")), (4, None))
        samples = jread(g / "human" / "samples.json")                                # 步驟 7（§ 8.1）：epoch 1 後 3 筆、寫手到 program 之後（epoch 4 的 rate）補到 6，不覆蓋
        self.assertEqual(len(samples), 6)
        self.assertTrue(all((x["scene"]["style"], x["scene"]["place"]) == ("傲嬌", "教室") for x in samples))
        got = [(x["why_picked"], x["scene"]["pair_id"], x["scene"]["stage"], x["scene"]["epoch"], x["picked_at_epoch"]) for x in samples]
        self.assertEqual(got, [("pair-stage", "a4-q16", "agent", 0, 1), ("pair-stage", "a4-cls-lights", "agent", 0, 1), ("disagree", None, "agent", 0, 1),
                               ("pair-stage", "a4-q16", "program", 3, 4), ("pair-stage", "a4-cls-lights", "program", 3, 4), ("hard", None, "program", 4, 4)])
        self.assertEqual(samples[5]["question"], "cls-poster")                       # 難例那題蒸餾前的降級產出
        self.assertEqual("\n".join(samples[5]["lines"]), rows["poster"]["output"])
        self.assertTrue(all(x["id"].startswith("a4-") for x in samples) and len({x["id"] for x in samples}) == 6)
        after = snapshot(g)                                                          # so-12：既有 _metainfo、尺、規則表、人寫的模板不變
        frozen = [k for k in before if os.path.basename(k) in ("_metainfo", "fsm.json", "loop.json", "dims.json", "rules.json", "templates.json")]
        self.assertEqual([k for k in frozen if before[k] != after.get(k)], [])

    # so-8. selfopt 收下後 verify 回滾：判斷器規則暫改成全拒 → 退 10、新工具 close 整個刪、stage.json 拷回（agent、只有 lint）、grad 最後一步 selfopt／accepted false
    def test_selfopt_rollback(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        rules = jread(g / "train" / "weigh" / "rules.json")
        rules["reject_if"].append({"key": "determinism", "gt": -9, "label": "全拒"})
        jwrite(g / "train" / "weigh" / "rules.json", rules)
        self.assertEqual(self.verify(g, st).returncode, 0)
        stage0 = jread(g / "writer" / "stage.json")
        r = self.optimize(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("optimize: selfopt writer extract：收了", r.stdout)
        s = jread(g / "writer" / "stage.json")
        self.assertEqual((s["stage"], s["tools"]), ("semi", ["lint", "close"]))    # accept 搬回＋優化器把 stage 翻成 semi
        self.assertTrue((g / "writer" / "tools" / "close" / "_entry").is_file())
        ch = jread(st / "epochs" / "001" / "params" / "changed.json")
        self.assertEqual((ch["source"], ch["target"], ch["created"], ch["stage_flip"]), ("selfopt", "tools/close", ["writer/tools/close"], ["agent", "semi"]))
        r = self.verify(g, st)
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertIn("train: Regressed epoch 1 回滾 writer/selfopt close（weigh: 拒A：全拒）", r.stderr)
        self.assertFalse((g / "writer" / "tools" / "close").exists())
        self.assertFalse((g / "writer" / "opt_log.jsonl").exists())
        s = jread(g / "writer" / "stage.json")
        self.assertEqual({k: x for k, x in s.items() if k != "history"}, {k: x for k, x in stage0.items() if k != "history"})
        last = jread(g / "writer" / "grad.json")["steps"][-1]
        self.assertEqual((last["action"], last["accepted"], last["by"]), ("selfopt", False, "writer@selfopt"))
        self.assertIn("writer/tools/close", last["rolled_back"])
        self.assertEqual(jread(g / "train" / "optimize" / "ratings.json")["action:selfopt"]["counter_rolled_back"], 1)

    # so-11. fallback：selfopt 連兩次被 accept 拒（cheat）→ 第三次 optimize 印 SelfoptFallback、改走外部 extract（人寫的 beat）
    def test_selfopt_fallback(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        st.mkdir()
        cheat = {"GALTXT_FAKE_OPT": "cheat"}
        for k in (1, 2):
            (st / "epoch.txt").write_text("%d\n" % k)
            r = self.optimize(g, st, env=cheat)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("沒收（WriteDenied）", r.stdout)
            self.assertFalse((st / "epochs" / ("%03d" % k) / "params" / "changed.json").exists())
            self.assertNotIn("SelfoptFallback", r.stdout)
        runs = jread(g / "train" / "optimize" / "selfopt.json")["runs"]
        self.assertEqual([(x["epoch"], x["accepted"], x["code"]) for x in runs], [(1, False, "WriteDenied"), (2, False, "WriteDenied")])
        (st / "epoch.txt").write_text("3\n")
        r = self.optimize(g, st, env=cheat)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("optimize: SelfoptFallback writer（連 2 次 selfopt 被拒或回滾）", r.stdout)
        self.assertIn("→ extract tools/beat（人寫好的 beat", r.stdout)
        ch = jread(st / "epochs" / "003" / "params" / "changed.json")
        self.assertEqual((ch["source"], ch["action"], ch["target"]), ("optimize", "extract", "tools/beat"))
        s = jread(g / "writer" / "stage.json")
        self.assertEqual((s["stage"], s["tools"]), ("semi", ["lint", "beat"]))
        self.assertEqual(len(jread(g / "train" / "optimize" / "selfopt.json")["runs"]), 2)   # 外部動作不派工

    # 18. 預算：訓練預算只剩 2 次腦 → selfopt 的 budget 壓成 2、跑到頂被殺（BudgetSpent、不搬）；下一個 verify BudgetSpent 退 2；剩 0＝不派工
    def test_budget_selfopt(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        self.assertEqual(self.verify(g, st).returncode, 0)
        used = common_of(g).usage_of(str(st / "epochs"))["counter_calls"]
        jwrite(g / "train" / "budget.json", dict(jread(g / "train" / "budget.json"), max_calls=used + 2))
        before = snapshot(g)
        r = self.optimize(g, st)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("沒收（BudgetSpent）", r.stdout)
        cell = next((st / "epochs" / "001" / "selfopt" / "writer").glob("[0-9][0-9][0-9]"))
        self.assertEqual(jread(cell.parent / (cell.name + ".task.json"))["budget"]["max_calls"], 2)
        self.assertFalse((st / "epochs" / "001" / "params" / "changed.json").exists())
        after = snapshot(g)
        self.assertEqual({k for k in set(before) | set(after) if before.get(k) != after.get(k)}, {"train/optimize/selfopt.json"})
        r = self.verify(g, st)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("train: BudgetSpent max_calls", r.stderr)
        (st / "epoch.txt").write_text("2\n")
        r = self.optimize(g, st)
        self.assertIn("沒收（BudgetSpent）", r.stdout)
        self.assertFalse((st / "epochs" / "002" / "selfopt" / "writer").exists() and any((st / "epochs" / "002" / "selfopt" / "writer").glob("[0-9][0-9][0-9]")))


class Round4HumanT(unittest.TestCase):
    """步驟 7（round4 § 8）：human/import 匯入假人評（§ 10 測試 19）；優化器讀 calibration 的 untrusted。rate 配對挑樣本由 Round4OptT.test_train_selfopt／Round3T.test_train_whole 驗。全部 tree_copy 上跑。"""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)

    @staticmethod
    def sample(sid, q, stage, epoch, why, pair=None, dims=None):
        return {"id": sid, "team": "a", "round": 4, "question": q, "produced_by": "writer", "why_picked": why, "lines": ["宮澤柚葉：「哼。」"],
                "scene": {"cast": ["主角", "宮澤柚葉"], "place": "教室", "event": "收攤", "style": "傲嬌", "intent": "餘溫", "epoch": epoch, "stage": stage, "pair_id": pair},
                "auto_scores": {"val": "ok", "total": 3.7, "dims": dict({"反差": 1.0, "像柚葉": 0.667, "文筆": 0.667, "語域": 0.5}, **(dims or {}))}}

    def importer(self, g):
        return run(str(g / "human" / "import" / "_entry"), timeout=60)

    # 19. 人評匯入：5 筆（Q16 一對＋lights 的 agent 半邊＋disagree＋hard）＋一筆對不到 → writer by_stage 兩格、grader 像柚葉 agreement 手算、
    #     判斷器 judge:accept 一致度（人說 agent 好、判斷器選了 A＝沒確認）、calibration untrusted、SampleUnknown 跳過、RatingsBad 退 1、重跑不變
    def test_human_import(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "human" / "samples.json", [
            self.sample("a4-q16-agent-e0-1", "Q16", "agent", 0, "pair-stage", "a4-q16"),
            self.sample("a4-cls-lights-agent-e0-1", "cls-lights", "agent", 0, "pair-stage", "a4-cls-lights"),
            self.sample("a4-q16-agent-e0-2", "Q16", "agent", 0, "disagree"),
            self.sample("a4-q16-program-e3-1", "Q16", "program", 3, "pair-stage", "a4-q16"),
            self.sample("a4-cls-lights-program-e3-1", "cls-lights", "program", 3, "pair-stage", "a4-cls-lights"),
            self.sample("a4-cls-poster-program-e4-1", "cls-poster", "program", 4, "hard", dims={"像柚葉": 1.0})])
        rat = [{"id": "a4-q16-agent-e0-1", "overall": "good", "tags": ["像柚葉"], "dims": {"反差": 1.0, "像柚葉": 0.9, "文筆": 0.5}, "comment": "可以", "rated_at": "2026-10-26T01:00:00Z"},
               {"id": "a4-q16-program-e3-1", "overall": "bad", "tags": ["像套公式"], "dims": {"像柚葉": 0.1}, "comment": "", "rated_at": "2026-10-26T01:01:00Z"},
               {"id": "a4-cls-lights-agent-e0-1", "overall": "ok", "tags": [], "dims": {"像柚葉": 0.0}, "rated_at": "2026-10-26T01:02:00Z"},
               {"id": "a4-q16-agent-e0-2", "overall": "ok", "tags": ["想看下去"], "dims": {}, "rated_at": "2026-10-26T01:03:00Z"},
               {"id": "a4-cls-poster-program-e4-1", "overall": "bad", "tags": ["像套公式", "稱呼不對"], "dims": {"像柚葉": 0.0}, "rated_at": "2026-10-26T01:04:00Z"},
               {"id": "a-q01-writer-1", "overall": "good", "rated_at": "2026-10-25T00:00:00Z"}]          # 第三輪的舊樣本：對不到
        jwrite(g / "human" / "ratings.json", rat)
        jwrite(g / "writer" / "ratings.json", dict(jread(g / "writer" / "ratings.json"), **{"style:傲嬌": {"val": "good", "dims": {"像柚葉": 0.7, "反差": 1.0}}}))
        jwrite(g / "train" / "weigh" / "ratings.json", {"source": "t", "judge:accept": {"counter_judged": 4, "counter_chose_a": 4}})
        (g / "train" / "weigh" / "log.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in (
            {"epoch": 1, "subtree": "writer", "action": "selfopt", "choice": "A"}, {"epoch": 3, "subtree": "writer", "action": "stage", "choice": "A"})), encoding="utf-8")
        r = self.importer(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "import: SampleUnknown a-q01-writer-1\n")
        w = jread(g / "writer" / "human.json")["style:傲嬌"]
        self.assertEqual((w["val"], w["counter_ratings"], w["overall"]), ("bad", 5, {"good": 1, "ok": 2, "bad": 2}))   # ok／bad 平手取較差的
        self.assertEqual(w["tags"], {"像套公式": 2, "像柚葉": 1, "想看下去": 1, "稱呼不對": 1})
        self.assertEqual(set(w["by_stage"]), {"agent", "program"})
        self.assertEqual((w["by_stage"]["agent"]["val"], w["by_stage"]["agent"]["counter_ratings"], w["by_stage"]["program"]["counter_ratings"]), ("ok", 3, 2))
        self.assertEqual(w["by_stage"]["program"]["tags"]["像套公式"], 2)
        self.assertEqual(w["comments"], ["可以"])
        self.assertEqual(w["rated_at"], "2026-10-26T01:04:00Z")                      # 人評最晚那筆，不是現在（重跑不變）
        xs = [(0.667, 0.9), (0.667, 0.1), (0.667, 0.0), (1.0, 0.0)]                  # 像柚葉（自動, 人）：grader 量
        gd = jread(g / "grader" / "human.json")
        self.assertEqual(gd["dim:像柚葉"]["agreement"], round(1 - sum(abs(a - b) for a, b in xs) / 4, 3))
        self.assertEqual(gd["dim:像柚葉"]["bias"], round(sum(a - b for a, b in xs) / 4, 3))
        self.assertEqual((gd["dim:文筆"]["counter_ratings"], gd["dim:文筆"]["agreement"]), (1, round(1 - 0.167, 3)))
        self.assertNotIn("dim:反差", gd)
        lint = jread(g / "tools" / "lint" / "human.json")                            # 反差歸 lint（dims.json 的 by）；語域人評沒問＝沒有
        self.assertEqual((lint["dim:反差"]["agreement"], lint["dim:反差"]["counter_ratings"]), (1.0, 1))
        self.assertNotIn("dim:語域", lint)
        ja = jread(g / "train" / "weigh" / "ratings.json")["judge:accept"]
        self.assertEqual((ja["counter_judged"], ja["counter_chose_a"]), (4, 4))      # verify 的計數不動
        self.assertEqual((ja["counter_human_pairs"], ja["counter_confirmed"], ja["agreement"]), (1, 0, 0.0))   # Q16：人說 agent 好（B），判斷器 epoch 3 選了 A
        pairs = jread(g / "train" / "weigh" / "human.json")["judge:accept"]["pairs"]
        self.assertEqual([(p["pair_id"], p["epoch"], p["action"], p["human"], p["choice"], p["confirmed"]) for p in pairs], [("a4-q16", 3, "stage", "B", "A", False)])
        cal = jread(g / "human" / "calibration.json")
        self.assertEqual(set(cal["untrusted"]), {"dim:像柚葉"})                    # 4 筆、agreement 0.38 < 0.5；文筆只有 1 筆不算
        self.assertEqual(cal["untrusted"]["dim:像柚葉"]["by"], "grader")
        self.assertEqual(cal["cells"]["writer style:傲嬌"]["read"], "人 bad、自動 good：評審太鬆")
        self.assertTrue(any("模板太死" in x for x in cal["notes"]))
        self.assertEqual((cal["judge"]["counter_human_pairs"], cal["counter_ratings"]), (1, 5))
        outs = ("writer/human.json", "grader/human.json", "tools/lint/human.json", "train/weigh/ratings.json", "train/weigh/human.json", "human/calibration.json")
        once = {p: (g / p).read_bytes() for p in outs}
        r = self.importer(g)                                                         # 重跑：整格覆蓋，一字不變
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({p: (g / p).read_bytes() for p in outs}, once)
        rat[1]["pair"] = "差不多"                                                    # 網頁有配對題時照它：差不多＝判斷器收下算對
        jwrite(g / "human" / "ratings.json", rat)
        self.assertEqual(self.importer(g).returncode, 0)
        self.assertEqual(jread(g / "train" / "weigh" / "ratings.json")["judge:accept"]["counter_confirmed"], 1)
        for bad in ({"id": "x"}, [{"id": "a4-q16-agent-e0-1"}], [{"id": "a4-q16-agent-e0-1", "overall": "great"}]):
            jwrite(g / "human" / "ratings.json", bad)
            before = {p: (g / p).read_bytes() for p in outs}
            r = self.importer(g)
            self.assertEqual(r.returncode, 1, bad)
            self.assertRegex(r.stderr, r"^import: RatingsBad \S")
            self.assertEqual(r.stderr.count("\n"), 1)
            self.assertEqual({p: (g / p).read_bytes() for p in outs}, before)

    # 19 之二：優化器讀 calibration 的 untrusted——印一行、給節點的先前結果拿掉那維、task.json 多 untrusted
    def test_optimize_untrusted(self):
        g, st = tree_copy(self.tmp / "t"), self.tmp / "st"
        ws = self.tmp / "ws"
        (ws / "new").mkdir(parents=True)
        r = run(EXEC, str(g / "train" / "fsm.json") + "#/states/verify/exec", env={"AOS_STACK": str(st) + "/", "AOS_WS": str(ws)}, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        jwrite(g / "human" / "calibration.json", {"source": "t", "untrusted": {"dim:像柚葉": {"by": "grader", "agreement": 0.383, "counter_ratings": 4}}})
        r = run(str(g / "train" / "optimize" / "_entry"), "--dry-run", env={"AOS_STACK": str(st) + "/"}, timeout=600)
        self.assertIn("optimize: 人評說不可信的維度 dim:像柚葉（grader，agreement 0.383、4 筆）：這圈不當依據", r.stdout)
        r = run(str(g / "train" / "optimize" / "_entry"), env={"AOS_STACK": str(st) + "/"}, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        task = jread(next((st / "epochs" / "001" / "selfopt" / "writer").glob("*.task.json")))
        self.assertEqual(task["untrusted"], ["像柚葉"])
        self.assertIn("像柚葉 這幾維的自動分不可信", task["task"])
        self.assertIn("反差", json.dumps(task["history"], ensure_ascii=False))       # 別的維度還在
        self.assertNotIn("像柚葉", json.dumps(task["history"], ensure_ascii=False))
        drop = common_of(g).drop_dims
        self.assertEqual(drop({"dims": {"像柚葉": 1, "反差": 0}, "diff": {"dims.像柚葉": 0.2, "dims.反差": 0.1}, "x": [{"dims": {"像柚葉": 2}}]}, {"像柚葉"}),
                         {"dims": {"反差": 0}, "diff": {"dims.反差": 0.1}, "x": [{"dims": {}}]})


if __name__ == "__main__":
    unittest.main()
