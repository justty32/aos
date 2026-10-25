"""test_topdown_galtxt_a - 跑 topdown/galtxt-a（由上而下拆的 galgame 台詞管線：brief → write（寫手 agent）→ check（lint）→ judge（評審 agent）→ pick）。

規劃：proto8/topdown/galtxt-a/plan/round1.md § 6.3；第二輪收攏（round2-collapse.md § 4 第 8 步）只改路徑與讀法、斷言不改，另加 collapse 與 metatable --suggest 的測試；
第三輪（round3.md § 11 的 1～11）加 Round3T：傲嬌與 Q16、選路、writer-sol、假腦技能表、rate、optimize、整條訓練、回滾、預算、M7（會寫樹的都在拷貝上跑）。全部離線（假腦）；連真模型的那個（test_real_model）localhost:4000 連不上就 skip。"""
import json, os, shutil, statistics, subprocess, tempfile, unittest, urllib.request
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
            self.assertIn("source", json.loads(p.read_text(encoding="utf-8")), p)   # 每張表標出處

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

    # 7. optimize 單元
    def optimize(self, g, *args, st=None):
        return run(str(g / "train" / "optimize" / "_entry"), *args, env={"AOS_STACK": str(st or self.tmp / "st") + "/"})

    def ratings(self, g, writer, **cells):
        r = jread(g / writer / "ratings.json")
        for style, (val, avg) in cells.items():
            r["style:" + style] = {"val": val, "score_avg": avg, "counter_samples": 6,
                                   "dims": {"語域": 1.0, "語意": 0.5, "多樣性": 0.3, "護欄": 1.0}}
        jwrite(g / writer / "ratings.json", r)

    def test_optimize(self):
        g = tree_copy(self.tmp / "t")
        jwrite(g / "train" / "set.json", dict(jread(g / "train" / "set.json"), writers=["writer", "writer-sol"]))   # round4 收窄後只剩 writer；
        # 這個單元驗 round3 的選路優化器（步驟 6 才重寫），在拷貝上把寫手列表改回兩個
        route = lambda: jread(g / "data" / "route.json")["by_style"]      # noqa: E731
        self.ratings(g, "writer", 傲嬌=("ok", 3.0), 文靜=("good", 4.0), 元氣=("good", 4.0), 天然=("none", None))
        self.ratings(g, "writer-sol", 傲嬌=("good", 4.0), 文靜=("good", 4.5), 元氣=("good", 4.0), 天然=("none", None))
        before = snapshot(g)
        r = self.optimize(g, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("傲嬌: writer → writer-sol", r.stdout)
        self.assertEqual(snapshot(g), before)                            # --dry-run 不寫
        self.assertFalse((self.tmp / "st").exists())
        r = self.optimize(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(route(), {"傲嬌": "writer-sol", "文靜": "writer-sol"})   # 同 good 比 score_avg；元氣平手留原值；天然全 none 不列
        params = self.tmp / "st" / "epochs" / "000" / "params"
        self.assertEqual(jread(params / "route.json")["by_style"], {})   # 改之前的快照
        self.assertTrue((params / "writer-sol" / "ratings.json").is_file())
        self.assertTrue(jread(params / "optimize.json")["changed"])
        r = self.optimize(g)                                             # 再跑一次：不動
        self.assertIn("route 不變", r.stdout)
        self.assertFalse(jread(params / "optimize.json")["changed"])
        h = jread(g / "writer-sol" / "human.json")                       # 人評否決：bad 且 ≥ 3 筆
        h["style:傲嬌"] = {"val": "bad", "counter_ratings": 3}
        jwrite(g / "writer-sol" / "human.json", h)
        self.optimize(g)
        self.assertEqual(route(), {"文靜": "writer-sol"})
        h["style:傲嬌"]["counter_ratings"] = 2                            # < 3 筆不算
        jwrite(g / "writer-sol" / "human.json", h)
        self.optimize(g)
        self.assertEqual(route(), {"傲嬌": "writer-sol", "文靜": "writer-sol"})
        o = jread(g / "train" / "optimize" / "ratings.json")             # 回滾比進步多＝min_gap 升成 1：同 val 不換
        o["action:route"] = {"val": "bad", "counter_applied": 1, "counter_improved": 0, "counter_regressed": 1}
        jwrite(g / "train" / "optimize" / "ratings.json", o)
        self.ratings(g, "writer", 文靜=("good", 4.9))
        r = self.optimize(g)
        self.assertIn("policy.min_gap 0 → 1", r.stdout)
        self.assertEqual(jread(g / "train" / "optimize" / "policy.json")["min_gap"], 1)
        self.assertEqual(route()["文靜"], "writer-sol")
        o["action:route"] = {"val": "good", "counter_applied": 3, "counter_improved": 2, "counter_regressed": 1, "counter_improved_streak": 2}
        jwrite(g / "train" / "optimize" / "ratings.json", o)
        self.optimize(g)
        self.assertEqual(jread(g / "train" / "optimize" / "policy.json")["min_gap"], 0)
        self.assertNotIn("文靜", route())                                 # 換回 default（writer）＝不列
        r = self.optimize(g, "--bogus")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^optimize: FlagUnknown \S")

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
            self.assertEqual({k: nodes.get(k) for k in ("writer", "grader", "tools/lint", "writer-sol")},
                             {"writer": "agent", "grader": "agent", "tools/lint": "program", "writer-sol": "agent"})
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
            self.assertTrue({"id", "team", "scene", "lines", "produced_by", "auto_scores", "round"} <= set(s), s)
            self.assertTrue(s["id"].startswith("a-"))
            self.assertEqual(s["team"], "a")
            self.assertTrue(1 <= len(s["lines"]) <= 8)
            self.assertTrue((g / s["produced_by"] / "_entry").is_file())
            self.assertTrue({"cast", "place", "event", "style", "intent"} <= set(s["scene"]))
            self.assertEqual((s["scene"]["style"], s["scene"]["place"]), (sets["scope"]["style"], sets["scope"]["place"]))   # 全在收窄範圍
        self.assertEqual(len({s["id"] for s in samples}), len(samples))
        qs = {q[:-5].lower() for q in sets["train"] + sets["verify"]}    # 先每個（寫手, 風格, 題）格一筆：訓練＋驗證每題都有
        self.assertEqual({q for q in qs if any(s["id"].startswith("a-%s-writer-" % q) for s in samples)}, qs)
        self.assertEqual(len(jl(self.stack / "verify.jsonl")), 2)
        self.assertEqual([t["state"] for t in jl(self.stack / "trace.jsonl")], ["verify", "train", "rate", "optimize", "verify"])
        after = snapshot(g)                                               # M7：只有量出來的旁檔變（route 沒換＝route.json、optimize 評級不動）
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"writer/ratings.json", "grader/ratings.json", "ratings.json", "human/samples.json",
                                   "rollup.json", "writer/rollup.json", "grader/rollup.json"})   # round4 步驟 4：rate／verify 叫 rollup --up
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

    # 7. 確定性：Q16-fixed 三份同 hint；program、假腦 agent 的「一致」都是 1.0；JITTER 讓 agent 的「一致」< 1、＝1 − 多樣性
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
        self.assertEqual(one(G, tag="a")["一致"], 1.0)
        d = one(G, env={"GALTXT_FAKE_JITTER": "1"}, tag="j")
        self.assertLess(d["一致"], 1.0)
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
        frozen = {k for k in before if os.path.basename(k) in ("_metainfo", "fsm.json", "loop.json", "dims.json")}
        self.assertTrue(frozen and not (frozen & changed), frozen & changed)
        allowed = {"ratings.json", "stage.json", "grad.json", "rollup.json", "human.json", "hard.jsonl", "log.jsonl",
                   "templates.json", "samples.json", "route.json", "policy.json"}
        self.assertEqual({k for k in changed if os.path.basename(k) not in allowed}, set())
        self.assertTrue({"rollup.json", "writer/rollup.json", "grader/rollup.json"} <= changed)    # rate／verify 叫了 rollup --up
        for k in ("writer/tools/beat/rollup.json", "tools/lint/rollup.json", "train/optimize/rollup.json"):
            self.assertNotIn(k, changed)                                                      # 不在 --up 路上的子樹 bytes 不變
        root = jread(g / "rollup.json")
        self.assertEqual(root["children"]["writer"]["stage"], "agent")
        self.assertEqual(root["brain"], {k: jread(g / "ratings.json")["style:傲嬌"]["brain"][k] for k in ("nodes", "counter_on_brain", "counter_program")})

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
        self.assertEqual(s["counter_on_brain"], jread(G / "rollup.json").get("brain", {}).get("counter_on_brain", 3))   # 未訓練：writer、writer-sol、grader
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


ROLLUP = str(G / "meta" / "rollup" / "_entry")


if __name__ == "__main__":
    unittest.main()
