"""test_topdown_galtxt_b_selfopt - galtxt-b 自我優化工具包（lib/selfopt：六個工具＋claude_code＋host；plan/runs/round6/selfopt.md）。全部假腦、假 claude。
訓練場：train/init 複製出 tree/（一次，之後每個測試複製一份），session.json 指定節點、預算；工具用 aos-exec --ws 訓練場 叫（SELFOPT_SESSION 指 session）。
驗：工具契約（tool.json、_metainfo、錯誤一行 stderr＋stdout 退 1）、寫入範圍外拒寫、凍結節點拒寫、白名單、edit_self 先存 versions/、set（JSON 指標）、
extract_tool 建出能跑的工具、預算、host 假腦走一次後 lifecycle.history 多一筆、claude_code（假 claude）越界還原。repo 的定義資料夾 hash 不變。"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
KIT = GB / "lib" / "selfopt"
TOOLS = ("read_self", "read_runs", "edit_self", "extract_tool", "run_self_test", "note", "claude_code")
W = "draft/tools/writer"
PT = "draft/tools/director/tools/plan_template"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD", "AOS_CO")
FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
sys.stdin.read()
open("system.txt", "a", encoding="utf-8").write("（假 claude 加的一句）\n")
open("../../../brief/tables/cast.json", "a", encoding="utf-8").write(" ")
open("_metainfo", "a", encoding="utf-8").write(" ")
os.makedirs("../../newdir", exist_ok=True)
open("../../newdir/x.txt", "w").write("x")
print(json.dumps({"result": "假 claude：改了 system.txt", "num_turns": 2, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 10, "output_tokens": 5}, "permission_denials": []}))
'''


def env_base(extra=None):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR and not k.startswith(("GALTXT_", "SELFOPT_"))}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def tree_hash(root):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for n in sorted(files):
            p = os.path.join(d, n)
            h.update(p.encode())
            if not os.path.islink(p):
                h.update(Path(p).read_bytes())
    return h.hexdigest()


class SelfOpt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name) / "base"
        cls.base.mkdir()
        cls.repo_hash = tree_hash(GB / "draft")
        r = subprocess.run([EXEC, "--ws", str(cls.base), str(GB / "train" / "init")], capture_output=True, text=True,
                           env=env_base({"AOS_STACK": str(cls.base / ".stack") + "/"}))
        assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.f = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.rmtree(self.f)
        shutil.copytree(self.base, self.f, symlinks=True)

    def tearDown(self):
        self.assertEqual(tree_hash(GB / "draft"), self.repo_hash)      # 只動訓練場，不動 repo 的樹

    def session(self, node=W, **kw):
        s = dict({"session": "t", "node": node, "goal": "測試", "round": 1, "max_calls": 12, "max_tokens": 30000, "self_test": "fake",
                  "counter_calls": 0, "counter_tokens": 0, "calls": [], "edits": [], "self_tests": [], "attempted_violations": []}, **kw)
        p = self.f / "selfopt" / "t" / "session.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        return p

    def call(self, name, args, session=None, extra=None):
        e = env_base(dict({"AOS_STACK": str(self.f / ".stack" / name) + "/"}, **(extra or {})))
        if session:
            e["SELFOPT_SESSION"] = str(session)
        return subprocess.run([EXEC, "--ws", str(self.f), str(KIT / name)], input=json.dumps(args, ensure_ascii=False),
                              capture_output=True, text=True, env=e, timeout=600)

    # ── 契約 ──
    def test_contract_files(self):
        for t in TOOLS:
            with self.subTest(tool=t):
                self.assertTrue(os.access(KIT / t / "_entry", os.X_OK))
                spec = jload(KIT / t / "tool.json")
                self.assertTrue(spec["description"])
                self.assertEqual(spec["parameters"]["type"], "object")
                meta = jload(KIT / t / "_metainfo")
                self.assertTrue(meta["summary"])
                self.assertIn("time_ms", meta)
        links = sorted(os.listdir(KIT / "host" / "tools"))
        self.assertEqual([x for x in links if x != "_metainfo"], sorted(TOOLS[:-1]))     # host 掛六個（claude_code 由優化器直接叫）

    def test_errors_one_line_both_streams(self):
        r = self.call("read_self", {})                                     # 沒 SELFOPT_SESSION
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), r.stderr.strip())
        self.assertTrue(r.stdout.startswith("read_self: SessionMissing"))
        s = self.session()
        r = self.call("edit_self", {"path": "system.txt"}, s)              # 三種都沒給
        self.assertEqual(r.returncode, 1)
        self.assertIn("edit_self: ArgumentsBad", r.stdout)
        r = self.call("read_runs", {}, s)                                  # 還沒有 runs/
        self.assertIn("read_runs: RunsMissing", r.stdout)

    def test_read_self(self):
        out = json.loads(self.call("read_self", {}, self.session()).stdout)
        self.assertEqual(out["node"], W)
        self.assertIn("system_txt", out)
        files = {x["path"]: x for x in out["files"]}
        self.assertTrue(files["system.txt"]["editable"])
        self.assertFalse(files["act.py"]["editable"])
        self.assertFalse(files["tools/lint"]["editable"])                  # 捷徑到凍結的 lib/lint

    # ── 邊界 ──
    def test_out_of_scope_refused(self):
        s = self.session()
        before = (self.f / "tree" / "brief" / "tables" / "cast.json").read_bytes()
        r = self.call("edit_self", {"path": "../../../brief/tables/cast.json", "content": "{}"}, s)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ScopeBad", r.stdout)
        self.assertEqual((self.f / "tree" / "brief" / "tables" / "cast.json").read_bytes(), before)
        v = jload(s)["attempted_violations"]
        self.assertEqual([x["code"] for x in v], ["ScopeBad"])

    def test_frozen_refused(self):
        s = self.session()
        for path in ("tools/lint/_entry", "../../../judge/tools/critic/system.txt", "../../../lib/selfopt/guard.py"):
            with self.subTest(path=path):
                r = self.call("edit_self", {"path": path, "content": "x"}, s)
                self.assertEqual(r.returncode, 1)
                self.assertIn("FrozenBad", r.stdout)
        s2 = self.session(node="lib/lint")                                 # 節點本身凍結：自己的檔也不准
        r = self.call("edit_self", {"path": "tool.json", "content": "{}"}, s2)
        self.assertIn("FrozenBad", r.stdout)
        self.assertEqual(len(jload(s2)["attempted_violations"]), 1)

    def test_whitelist(self):
        s = self.session()
        for path in ("act.py", "_metainfo", "fsm.json", ".env"):
            with self.subTest(path=path):
                self.assertIn("WhitelistBad", self.call("edit_self", {"path": path, "content": "{}"}, s).stdout)

    def test_edit_self_saves_version_first(self):
        s = self.session()
        node = self.f / "tree" / W
        orig = (node / "system.txt").read_text(encoding="utf-8")
        r = self.call("edit_self", {"path": "system.txt", "edits": [{"old_text": "最多自檢兩次。", "new_text": "最多自檢一次。"}]}, s)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("最多自檢一次。", (node / "system.txt").read_text(encoding="utf-8"))
        self.assertEqual((node / "versions" / "selfopt_t" / "system.txt").read_text(encoding="utf-8"), orig)
        self.call("edit_self", {"path": "system.txt", "edits": [{"old_text": "最多自檢一次。", "new_text": "自檢一次。"}]}, s)
        self.assertEqual((node / "versions" / "selfopt_t" / "system.txt").read_text(encoding="utf-8"), orig)   # 同 session 只存改前
        self.assertIn("TextMissing", self.call("edit_self", {"path": "system.txt", "edits": [{"old_text": "沒有這句", "new_text": "x"}]}, s).stdout)

    def test_edit_self_set_json(self):
        s = self.session(node=PT)
        row = {"beats": [{"beat": "B0", "who": "旁白", "do": "x", "must": []}]}
        r = self.call("edit_self", {"path": "plans.json", "set": {"/plans/主角|舊車票": row}}, s)
        self.assertEqual(r.returncode, 0, r.stdout)
        plans = jload(self.f / "tree" / PT / "plans.json")
        self.assertEqual(plans["plans"]["主角|舊車票"], row)
        self.assertEqual(len(plans["plans"]), 5)
        self.assertIn("PointerMissing", self.call("edit_self", {"path": "plans.json", "set": {"/nope/x": 1}}, s).stdout)

    def test_budget_calls(self):
        s = self.session(max_calls=2)
        self.assertEqual(self.call("read_self", {}, s).returncode, 0)
        self.assertEqual(self.call("read_self", {}, s).returncode, 0)
        r = self.call("read_self", {}, s)
        self.assertIn("BudgetBad", r.stdout)
        self.assertIn("BudgetBad", self.call("run_self_test", {"brain": "real"}, self.session(self_test="fake")).stdout)

    def test_extract_tool(self):
        s = self.session()
        r = self.call("extract_tool", {"name": "strip_dash", "step": "把——換成……", "why": "測試",
                                       "rules": [{"pattern": "——", "replace": "……"}]}, s)
        self.assertEqual(r.returncode, 0, r.stdout)
        node = self.f / "tree" / W
        self.assertIn("交給工具 strip_dash", (node / "system.txt").read_text(encoding="utf-8"))
        lc = jload(node / "_metainfo")["lifecycle"]
        self.assertIn("strip_dash", lc["tools"])
        self.assertEqual(lc["counter_steps_tooled"], 3)
        x = subprocess.run([EXEC, str(node / "tools" / "strip_dash")], input='{"text": "啊——好"}', capture_output=True, text=True,
                           env=env_base({"AOS_STACK": str(self.f / ".stack" / "sd") + "/"}))
        self.assertEqual(json.loads(x.stdout)["text"], "啊……好")
        self.assertIn("ToolBad", self.call("extract_tool", {"name": "strip_dash", "step": "x", "why": "x", "rules": [{"pattern": "a", "replace": "b"}]}, s).stdout)
        self.assertIn("RulesBad", self.call("extract_tool", {"name": "bad_rx", "step": "x", "why": "x", "rules": [{"pattern": "(", "replace": "b"}]}, s).stdout)

    # ── 整個流程（host、假腦）──
    def host(self, name, q):
        (self.f / "new").mkdir(exist_ok=True)
        (self.f / "new" / (name + ".json")).write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([EXEC, "--ws", str(self.f), str(KIT / "host")], capture_output=True, text=True, timeout=900,
                           env=env_base({"AOS_STACK": str(self.f / "selfopt" / (".stack_" + name)) + "/"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        return jload(self.f / "selfopt" / name / "report.json")

    def test_host_fake_flow_adds_history(self):
        node = self.f / "tree" / W
        n0 = len(jload(node / "_metainfo")["lifecycle"].get("history", []))
        rep = self.host("w1", {"mode": "optimize", "node": W, "goal": "降低 token", "max_calls": 8, "self_test": "fake", "round": 1,
                               "fake_script": [{"name": "read_self", "arguments": {}},
                                               {"name": "edit_self", "arguments": {"path": "system.txt", "edits": [{"old_text": "最多自檢兩次。", "new_text": "最多自檢一次。"}]}},
                                               {"name": "edit_self", "arguments": {"path": "tools/lint/_entry", "content": "x"}},
                                               {"name": "run_self_test", "arguments": {}},
                                               {"name": "note", "arguments": {"why": "假腦測試", "expect": "token −"}}]})
        hist = jload(node / "_metainfo")["lifecycle"]["history"]
        self.assertEqual(len(hist), n0 + 1)
        self.assertEqual(hist[-1]["move"], "selfopt")
        self.assertEqual(hist[-1]["changed"], ["system.txt"])
        self.assertEqual(rep["tools_called"], ["read_self", "edit_self", "edit_self", "run_self_test", "note"])
        self.assertEqual([v["code"] for v in rep["attempted_violations"]], ["FrozenBad"])
        self.assertIn("最多自檢一次", rep["diff"]["system.txt"])
        self.assertEqual(rep["self_tests"][0]["code"], 0)
        self.assertTrue((self.f / "out" / "w1.txt").exists() and (self.f / "done" / "w1.json").exists())

    def test_host_notes_when_brain_does_not(self):
        node = self.f / "tree" / PT
        rep = self.host("p1", {"mode": "optimize", "node": PT, "goal": "消化難例", "fake_script": [{"name": "read_self", "arguments": {}}]})
        self.assertEqual(rep["noted"], "host")
        self.assertEqual(jload(node / "_metainfo")["lifecycle"]["history"][-1]["by"], "host")

    def test_host_token_budget_stops(self):
        rep = self.host("b1", {"mode": "optimize", "node": W, "goal": "x", "max_tokens": 0,
                               "fake_script": [{"name": "read_self", "arguments": {}}]})
        self.assertEqual(rep["tools_called"], [])
        self.assertIn("預算用完", rep["answer"])

    # ── claude_code（假 claude）──
    def test_claude_code_restores_out_of_scope(self):
        fake = self.f / "fakeclaude.py"
        fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        fake.chmod(0o755)
        s = self.session(max_usd=2.0)
        cast = (self.f / "tree" / "brief" / "tables" / "cast.json").read_bytes()
        meta = jload(self.f / "tree" / W / "_metainfo")
        r = self.call("claude_code", {"goal": "降低 token"}, s, {"SELFOPT_CLAUDE_BIN": str(fake)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["changed"], ["system.txt"])
        self.assertEqual(sorted(out["restored"]), ["brief/tables/cast.json", "draft/newdir/x.txt", W + "/_metainfo"])
        self.assertEqual((self.f / "tree" / "brief" / "tables" / "cast.json").read_bytes(), cast)
        self.assertFalse((self.f / "tree" / "draft" / "newdir").exists())
        self.assertIn("假 claude", (self.f / "tree" / W / "system.txt").read_text(encoding="utf-8"))
        self.assertTrue((self.f / "tree" / W / "versions" / "selfopt_t" / "system.txt").exists())
        after = jload(self.f / "tree" / W / "_metainfo")
        self.assertEqual(len(after["lifecycle"]["history"]), len(meta["lifecycle"].get("history", [])) + 1)
        sess = jload(s)
        self.assertEqual(len(sess["attempted_violations"]), 3)
        self.assertAlmostEqual(sess["claude_code"]["cost_usd"], 0.01)


if __name__ == "__main__":
    unittest.main()
