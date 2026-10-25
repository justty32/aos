"""test_topdown_galtxt_a - 跑 topdown/galtxt-a（由上而下拆的 galgame 台詞管線：brief → write（寫手 agent）→ check（lint）→ judge（評審 agent）→ pick）。

規劃：proto8/topdown/galtxt-a/plan/round1.md § 6.3。全部離線（假腦）；連真模型的那個（test_real_model）localhost:4000 連不上就 skip。"""
import json, os, subprocess, tempfile, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
G = ROOT / "topdown" / "galtxt-a"
EXAMPLES = G / "plan" / "examples"
LINT = str(G / "check" / "tools" / "lint")
REAL_URL = "http://localhost:4000/v1"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
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
        link = G / "write" / "tools" / "writer" / "tools" / "lint"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../../../../check/tools/lint")
        self.assertEqual(link.resolve(), (G / "check" / "tools" / "lint").resolve())
        second = (G / "check" / "tools" / "lint" / "_entry").read_text(encoding="utf-8").splitlines()[1]
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
        r = run(EXEC, str(G / "brief"), env=env)
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
        self.assertEqual(run(EXEC, str(G / "brief"), env=env).returncode, 0)
        (self.stack / "drafts").mkdir()
        (self.stack / "drafts" / "1.txt").write_text("手寫的第一份\n", encoding="utf-8")
        r = run(EXEC, str(G / "write"), env=env)
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

    def test_metainfo_consistent(self):
        top, w, j = self.meta("."), self.meta("write"), self.meta("judge")
        self.assertGreaterEqual(top["llm_calls"]["max"], w["llm_calls"]["max"] + j["llm_calls"]["max"])
        writer = self.meta("write/tools/writer")
        loop = json.loads((G / "write/tools/writer/loop.json").read_text())
        self.assertGreaterEqual(writer["llm_calls"]["max"], loop["max"] // 3)
        judge = self.meta("judge/tools/judge")
        loop = json.loads((G / "judge/tools/judge/loop.json").read_text())
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
                self.assertGreaterEqual(cell["exec"]["timeout_ms"], self.meta(s)["time_ms"]["max"], s)
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


if __name__ == "__main__":
    unittest.main()
