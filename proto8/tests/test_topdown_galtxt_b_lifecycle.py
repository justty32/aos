"""test_topdown_galtxt_b_lifecycle - galtxt-b 第 6 輪（plan/round6.md §7 第 1～3 項的已做部分）：節點生命週期。
director 走完 agent→script→pure（run.py＋tools/plan_template、versions/ 留舊版）：四題＋default 全過 plan_lint、表外的開關（prop 舊車票）降級＋
難例只寫小格（定義資料夾 hash 不變）＋score.degraded；writer 抽 trim（純函數）：三條修剪各一紅一綠、不改台詞句數、假腦叫 trim 那條路；
關閉開關（ablation）；_metainfo.lifecycle 形狀與 counter 不等式。全部假腦。"""
import hashlib, json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
SET = GB / "train" / "set"
DIRECTOR = GB / "draft" / "tools" / "director"
A = "新書_宮澤_主角先_梅花章"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD", "AOS_CO")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR and not k.startswith("GALTXT_")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def tree_hash(root):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for n in sorted(files):
            p = os.path.join(d, n)
            h.update(p.encode())
            if not os.path.islink(p):
                h.update(Path(p).read_bytes())
    return h.hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def scene(self, **kw):
        q = json.loads((SET / (A + ".json")).read_text(encoding="utf-8"))
        q.update(kw)
        return q

    def galtxt(self, q, name="q", env=None):
        ws = self.tmp / ("ws_" + name)
        (ws / "new").mkdir(parents=True)
        (ws / "new" / (name + ".json")).write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB, env=env, cwd=self.tmp, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return ws, ws / "out" / name

    def brief(self, q):
        ws = self.tmp / "b"
        shutil.rmtree(ws, ignore_errors=True)
        (ws / "new").mkdir(parents=True)
        (ws / ".stack").mkdir()
        (ws / "new" / "x.json").write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB / "brief", env={"AOS_STACK": str(ws / ".stack") + "/"}, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((ws / ".stack" / "brief.json").read_text(encoding="utf-8"))


class Director(Base):
    def template(self, brief):
        r = run(EXEC, DIRECTOR / "tools" / "plan_template", input=json.dumps({"brief": brief}, ensure_ascii=False), cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def plan_lint(self, plan, brief):
        r = run(EXEC, GB / "draft" / "tools" / "plan_lint", input=json.dumps({"plan": plan, "brief": brief}, ensure_ascii=False),
                cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)["violations"]

    def test_four_and_default_pass_plan_lint(self):
        for p in sorted(SET.glob("*.json")):
            with self.subTest(q=p.stem):
                b = self.brief(json.loads(p.read_text(encoding="utf-8")))
                got = self.template(b)
                sw = b["scene"]["switches"]
                self.assertEqual((got["hit"], got["key"], got["degraded"]), (True, "%s|%s" % (sw["first_speaker"], sw["prop"]), []))
                self.assertEqual(self.plan_lint(got["plan"], b), [])
                self.assertEqual(got["plan"]["beats"][2]["who"], sw["first_speaker"])     # B2 開口權照開關
        b = self.brief(self.scene(switches={"first_speaker": "主角", "prop": "舊車票"}, must_mention=[["新書", "進新書日"], ["舊車票"]]))
        got = self.template(b)
        self.assertEqual((got["hit"], got["degraded"]), (False, ["plan_template: 主角|舊車票 不在表上，用 default"]))
        self.assertEqual(self.plan_lint(got["plan"], b), [])
        self.assertEqual(self.template(b), got)                                          # 純函數：同輸入同輸出

    def test_hard_case_degrades_without_touching_definition(self):
        before = tree_hash(GB)
        ws, out = self.galtxt(self.scene(switches={"first_speaker": "主角", "prop": "舊車票"},
                                         must_mention=[["新書", "進新書日"], ["舊車票"]]))
        s = json.loads((out / "score.json").read_text(encoding="utf-8"))
        self.assertEqual(s["degraded"], ["plan_template: 主角|舊車票 不在表上，用 default"])
        cases = [json.loads(l) for l in (ws / ".stack" / "director" / "hard_cases.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 1)
        self.assertEqual((cases[0]["node"], cases[0]["input"]["switches"]["prop"], cases[0]["output"]),
                         ("draft/tools/director", "舊車票", "plans.json#/default"))
        self.assertEqual(json.loads((out / "measure.json").read_text())["agents"]["director"]["counter_llm_calls"], 0)
        self.assertEqual(tree_hash(GB), before)                                          # runtime 不寫定義資料夾（P-15）
        _, out = self.galtxt(self.scene(), name="ok")
        self.assertEqual(json.loads((out / "score.json").read_text(encoding="utf-8"))["degraded"], [])

    def test_versions_kept(self):
        v = DIRECTOR / "versions"
        self.assertTrue((v / "v0_agent" / "ask.py").exists() and (v / "v0_agent" / "system.txt").exists())
        self.assertIn('FALLBACK = "agent"', (v / "v1_script" / "run.py").read_text(encoding="utf-8"))
        self.assertEqual((v / "v1_script" / "tools" / "agent").resolve(), (v / "v0_agent").resolve())
        self.assertFalse((DIRECTOR / "ask.py").exists())
        m = json.loads((DIRECTOR / "_metainfo").read_text(encoding="utf-8"))
        self.assertEqual([h["to"] for h in m["lifecycle"]["history"]], ["script", "pure"])

    def test_v1_script_asks_brain_only_off_table(self):
        """v1_script 換進樹的複本：表上的題不叫 agent；表外的題叫 agent（假腦）出表、不記難例。"""
        t = self.tmp / "tree"
        shutil.copytree(GB, t, symlinks=True, ignore=shutil.ignore_patterns("plan", "train", "human"))
        d = t / "draft" / "tools" / "director"
        v1 = self.tmp / "v1"
        shutil.copytree(d / "versions" / "v1_script", v1, symlinks=False)
        for x in list(d.iterdir()):
            if x.name != "versions":
                shutil.rmtree(x) if x.is_dir() else x.unlink()
        for x in v1.iterdir():
            shutil.move(str(x), str(d / x.name))
        for name, q, agent in (("on", self.scene(), False),
                               ("off", self.scene(switches={"first_speaker": "主角", "prop": "舊車票"}), True)):
            ws = self.tmp / ("w" + name)
            (ws / "new").mkdir(parents=True)
            (ws / "new" / "q.json").write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
            r = run(EXEC, "--ws", ws, t, cwd=self.tmp, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((ws / ".stack" / "director" / "agent" / "llm.jsonl").exists(), agent, name)
            self.assertFalse((ws / ".stack" / "director" / "hard_cases.jsonl").exists())


class Trim(Base):
    def setUp(self):
        super().setUp()
        self.b = self.brief(self.scene())

    def trim(self, text):
        r = run(EXEC, GB / "draft" / "tools" / "writer" / "tools" / "trim", input=json.dumps({"text": text, "brief": self.b}, ensure_ascii=False),
                cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_rules(self):
        base = ["【梅雨傍晚・河鹿堂】", "（門鈴響了。）", "主角：「挖寶挖成這樣？」", "宮澤柚葉：「才不是。拿著。」", "主角：「是是。」",
                "宮澤柚葉：「下次也來。」", "主角：「好。」"]
        green = self.trim("\n".join(base))
        self.assertEqual((green["text"], green["changes"]), ("\n".join(base), []))
        five = base[:2] + ["（一）", "（二）", "（三）", "（四）"] + base[2:]               # 旁白 5 行 → 4
        got = self.trim("\n".join(five))
        self.assertEqual(sum(1 for l in got["text"].splitlines() if l.startswith("（")), 4)
        self.assertNotIn("（四）", got["text"])
        bang = base[:3] + ["宮澤柚葉：「才不是！拿著！」", "主角：「是是。」", "宮澤柚葉：「下次也來！」", "主角：「好。」"]   # 她的「！」3 個 → 2
        got = self.trim("\n".join(bang))
        self.assertEqual(got["text"].count("！"), 2)
        self.assertIn("宮澤柚葉：「下次也來。」", got["text"])
        self.assertEqual([c["rule"] for c in got["changes"]], ["exclaim"])
        cp = base[:3] + ["宮澤柚葉：「才不是為了你。」", "主角：「是是。」", "宮澤柚葉：「才不是為了你。下次也來。」", "主角：「好。」"]   # 口癖 2 次 → 第二次換「哼」
        got = self.trim("\n".join(cp))
        self.assertIn("宮澤柚葉：「哼。下次也來。」", got["text"])
        self.assertEqual(got["text"].count("才不是為了你"), 1)
        for text in (five, bang, cp):                                                   # 修剪不改台詞句數
            out = self.trim("\n".join(text))["text"]
            self.assertEqual(sum(1 for l in out.splitlines() if "：「" in l), sum(1 for l in text if "：「" in l))

    def test_errors(self):
        r = run(EXEC, GB / "draft" / "tools" / "writer" / "tools" / "trim", input='{"text": 1}', cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^trim: ArgumentsBad \S")

    def test_writer_calls_trim(self):
        ws, out = self.galtxt(self.scene(), env={"GALTXT_FAKE_TRIM": "1"})
        h = [json.loads(l) for l in (ws / ".stack" / "writer" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(h[1]["tool_calls"][0]["function"]["name"], "trim")
        self.assertTrue(json.loads(h[2]["content"])["changes"])
        check = json.loads((out / "check.json").read_text(encoding="utf-8"))
        self.assertFalse([v for v in check["violations"] if v["rule"] in ("narration_max", "exclaim")])


class Ablation(Base):
    def test_switches(self):
        ws, out = self.galtxt(self.scene(), env={"GALTXT_OFF_DIRECTOR": "1"})
        self.assertTrue(json.loads((out / "score.json").read_text(encoding="utf-8"))["degraded"][0].startswith("ablation: GALTXT_OFF_DIRECTOR"))
        self.assertFalse((ws / ".stack" / "director" / "hard_cases.jsonl").exists())
        ws, _ = self.galtxt(self.scene(), name="l", env={"GALTXT_OFF_TRIM": "1", "GALTXT_FAKE_TRIM": "1"})
        h = [json.loads(l) for l in (ws / ".stack" / "writer" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(h[1]["tool_calls"][0]["function"]["name"], "trim")                   # 假腦照叫，但工具已拿掉
        self.assertIn("ToolUnknown trim", h[2]["content"])
        ws, out = self.galtxt(self.scene(), name="r", env={"GALTXT_OFF_REDRAFT": "1", "GALTXT_FAKE_BAD_FIRST": "1"})
        self.assertEqual(len(json.loads((out / "check.json").read_text(encoding="utf-8"))["history"]), 1)
        self.assertNotEqual(self.brief(self.scene())["samples"], [])
        ws = self.tmp / "s"
        (ws / "new").mkdir(parents=True)
        (ws / ".stack").mkdir()
        (ws / "new" / "x.json").write_text(json.dumps(self.scene(), ensure_ascii=False), encoding="utf-8")
        r = run(EXEC, "--ws", ws, GB / "brief", env={"AOS_STACK": str(ws / ".stack") + "/", "GALTXT_OFF_SAMPLES": "1"}, cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((ws / ".stack" / "brief.json").read_text(encoding="utf-8"))["samples"], [])


class Shape(unittest.TestCase):
    def test_lifecycle_and_zones(self):
        seen = 0
        for d, dirs, files in os.walk(GB):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x != "plan"]
            if "_metainfo" not in files:
                continue
            m = json.loads(Path(d, "_metainfo").read_text(encoding="utf-8"))
            lc = m.get("lifecycle")
            if lc is None:
                continue
            with self.subTest(dir=os.path.relpath(d, GB)):
                seen += 1
                self.assertIn(lc["stage"], ("agent", "tools", "script", "pure"))
                self.assertLessEqual(lc.get("counter_steps_tooled", 0), lc.get("counter_steps_total", 0))
                if lc["stage"] == "pure":
                    self.assertEqual(lc.get("brain_decides"), [])
                    self.assertIs(m.get("uses_llm"), False)
        self.assertGreaterEqual(seen, 5)
        root = json.loads((GB / "_metainfo").read_text(encoding="utf-8"))
        self.assertEqual(root["tree_id"], "galtxt-b")
        for s in root["subtrees"]:
            p = s if isinstance(s, str) else s["path"]
            self.assertTrue((GB / p / "_metainfo").exists(), p)
        w = json.loads((GB / "draft" / "tools" / "writer" / "_metainfo").read_text(encoding="utf-8"))
        self.assertEqual(w["lifecycle"]["stage"], "tools")
        self.assertEqual(set(w["lifecycle"]["tools"]), {"lint", "trim"})


if __name__ == "__main__":
    unittest.main()
