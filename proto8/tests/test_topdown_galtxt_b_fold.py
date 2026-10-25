"""test_topdown_galtxt_b_fold - galtxt-b/plan/aos-fold（反向收攏原型，plan/round3-collapse.md §5）的五個子命令，全拿 galtxt-b 的複本做：
agent（5→4：把複本的 critic 先還原成 loop→fsm 範本形，再縮回去；三條路照過、跟原樹 verify 綠）、
link（解捷徑：有別的呼叫者＝複製、沒有＝整個搬過來）、layer（check/tools 沒 --force 要紅、什麼都不動；--force 才併）、
pack（brief/tables 合起來 > 8 KB 要印 F6 警告與讀者清單、不刪原資料夾）、verify（收攏前後綠、故意改一條 lint 規則的樹紅）。
另有命令列的錯（ArgumentsBad、FlagUnknown、TargetBad）。"""
import json, os, shutil, stat, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GB = ROOT / "topdown" / "galtxt-b"
FOLD = GB / "plan" / "aos-fold"
Q01, Q08 = "q01_河鹿堂讓書", "q08_河鹿堂進新書日"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_CF", "AOS_CD",
         "GALTXT_FAKE_BAD_FIRST", "GALTXT_FAKE_LINT", "GALTXT_FAKE_BAD_PLAN")

# critic 收攏前的範本形（round2 的原檔；act 的工作已經在 ask.py 裡，所以還原時 brain.py＝ask.py、act.py 什麼都不做）
FSM = {"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "idle",
       "states": {"idle": {"exec": "idle", "next": "think"},
                  "think": {"exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000,
                                     "_metainfo": {"summary": "問腦一次", "time_ms": {"val": 6000, "max": 120000}, "resource": "llm",
                                                   "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
                                                   "llm_calls": 1, "llm_tokens": {"val": 2200, "max": 4500}, "interrupt": "safe"}},
                            "next": "act"},
                  "act": {"exec": {"argv": ["python3", "act.py"], "timeout_ms": 30000}, "next": "idle"}}}
IDLE = '#!/bin/sh\nfor f in "$AOS_WS"/cur/*.json "$AOS_WS"/new/*.json; do [ -e "$f" ] && exit 0; done\nexit 10\n'


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def write(p, text, x=False):
    Path(p).write_text(text, encoding="utf-8")
    os.chmod(p, 0o755 if x else 0o644)


class Fold(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.copy = self.tmp / "galtxt-b"
        shutil.copytree(GB, self.copy, symlinks=True, ignore=shutil.ignore_patterns(".stack", "plan"))
        (self.tmp / "ws").mkdir()

    def fold(self, *args):
        return run("python3", FOLD, *args, cwd=self.tmp, timeout=600)

    def verify(self, a, b, q=Q08, env=()):
        args = ["verify", a, b, "--ws", self.tmp / "ws", "--question", GB / "examples" / (q + ".json")]
        for kv in env:
            args += ["--env", kv]
        return self.fold(*args)

    def scenarios(self, tree):
        """demo.sh 的三段（q01 一稿過、q08 打回、q01 自檢）＋director 壞一次：都要結束碼 0。"""
        for q, env in ((Q01, {}), (Q08, {"GALTXT_FAKE_BAD_FIRST": "1"}), (Q01, {"GALTXT_FAKE_LINT": "1"}), (Q01, {"GALTXT_FAKE_BAD_PLAN": "1"})):
            with self.subTest(q=q, env=env):
                ws = self.tmp / ("run-" + q + "-" + "-".join(env))
                (ws / "new").mkdir(parents=True)
                shutil.copyfile(GB / "examples" / (q + ".json"), ws / "new" / (q + ".json"))
                r = run(EXEC, "--ws", ws, tree, env=env, cwd=self.tmp, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue((ws / "out" / q / "answer.txt").exists())

    def unfold_critic(self):
        """把複本的 critic 還原成 round2 的範本形（loop.json→fsm.json idle→think→act、sh 的 _entry、idle/）。"""
        c = self.copy / "judge" / "tools" / "critic"
        write(c / "_entry", "#!/bin/sh\n# _entry - 範本\nexec aos-loop loop.json\n", x=True)
        write(c / "loop.json", json.dumps({"exec": "fsm.json", "max": 6}) + "\n")
        write(c / "fsm.json", json.dumps(FSM, ensure_ascii=False) + "\n")
        (c / "idle").mkdir()
        write(c / "idle" / "_entry", IDLE, x=True)
        write(c / "idle" / "_metainfo", json.dumps({"summary": "有題目退 0、沒有退 10", "time_ms": 5}) + "\n")
        shutil.copyfile(c / "ask.py", c / "brain.py")
        write(c / "act.py", "# act.py - 什麼都不做（brain.py＝ask.py 已經寫好答案）\n")
        meta = json.loads((c / "_metainfo").read_text(encoding="utf-8"))
        meta.update(grow_level=5, interrupt="resumable")
        write(c / "_metainfo", json.dumps(meta, ensure_ascii=False) + "\n")
        os.remove(c / "ask.py")
        return c

    def test_agent(self):
        c = self.unfold_critic()
        # 還沒寫 ask.py＝TargetBad、什麼都不動
        r = self.fold("agent", c, "--script", "ask.py")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad \S")
        self.assertTrue((c / "fsm.json").exists())
        shutil.copyfile(c / "brain.py", c / "ask.py")
        # 範本形跟原樹（單發）比：只差 critic 小格的 state.txt、trace.jsonl（預期差異）
        r = self.verify(self.copy, GB, env=["GALTXT_FAKE_BAD_FIRST=1"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("預期差異", r.stderr)
        # dry-run 什麼都不寫
        before = sorted(os.listdir(c))
        r = self.fold("--dry-run", "agent", c, "--script", "ask.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"argv": ["python3", "ask.py"]', r.stdout)
        self.assertEqual(sorted(os.listdir(c)), before)
        # 真的縮
        r = self.fold("agent", c, "--script", "ask.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(c)), [".env", "_entry", "_metainfo", "ask.py", "system.txt"])
        self.assertFalse(os.stat(c / "_entry").st_mode & stat.S_IXUSR)               # JSON 單子不 +x（P-40）
        self.assertEqual(json.loads((c / "_entry").read_text()),
                         {"argv": ["python3", "ask.py"], "timeout_ms": 120000, "_metainfo": {"$ref": "_metainfo"}})
        meta = json.loads((c / "_metainfo").read_text())
        self.assertEqual((meta["grow_level"], meta["interrupt"]), (4, "safe"))
        self.assertIn("resumable→safe", r.stderr)
        self.scenarios(self.copy)
        r = self.verify(self.copy, GB)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("預期差異", r.stderr)                                    # 兩邊都是單發，逐檔一樣
        # 再縮一次＝已經不是範本形
        r = self.fold("agent", c, "--script", "ask.py")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad \S")

    def test_link(self):
        w, ck, lib = (self.copy / "draft/tools/writer/tools/lint", self.copy / "check/tools/lint", self.copy / "lib/lint")
        # writer 那條：check 也指 lib/lint＝複製一份過來，lib/lint 留著、callers 少一個
        r = self.fold("link", w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["how"], "copy")
        self.assertTrue(w.is_dir() and not w.is_symlink() and lib.is_dir())
        self.assertEqual(len(json.loads((lib / "_metainfo").read_text())["callers"]), 1)
        self.assertEqual(json.loads((w / "_metainfo").read_text())["callers"], ["draft/tools/writer/（腦自檢，brief_path）"])
        # check 那條：沒有別的捷徑了＝整個搬過來，lib/lint 不見
        r = self.fold("link", ck)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["how"], "move")
        self.assertTrue(ck.is_dir() and not ck.is_symlink() and os.access(ck / "_entry", os.X_OK) and (ck / "tool.json").exists())
        self.assertFalse(lib.exists())
        self.assertIn("要人改", r.stderr)
        # 不是捷徑＝TargetBad
        r = self.fold("link", ck)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad \S")
        self.scenarios(self.copy)
        self.assertEqual(self.verify(GB, self.copy, env=["GALTXT_FAKE_LINT=1"]).returncode, 0)

    def test_layer(self):
        t = self.copy / "check" / "tools"
        entry = (self.copy / "check" / "_entry").read_text()
        r = self.fold("layer", t)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad .*P-33")
        self.assertTrue((t / "lint").is_symlink())                                   # 什麼都沒動
        self.assertEqual((self.copy / "check" / "_entry").read_text(), entry)
        r = self.fold("layer", t, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        lint = self.copy / "check" / "lint"
        self.assertTrue(lint.is_symlink() and lint.resolve() == (self.copy / "lib" / "lint").resolve())
        self.assertEqual(os.readlink(lint), "../lib/lint")
        self.assertFalse(t.exists())
        self.assertIn('"aos-exec", "lint"', (self.copy / "check" / "_entry").read_text())
        self.assertEqual(self.verify(GB, self.copy, env=["GALTXT_FAKE_BAD_FIRST=1"]).returncode, 0)
        # 不只一個子項＝TargetBad
        r = self.fold("layer", self.copy / "draft" / "tools", "--force")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad \S")

    def test_pack(self):
        d = self.copy / "brief" / "tables"
        r = self.fold("--dry-run", "pack", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.copy / "brief" / "tables.json").exists())
        r = self.fold("pack", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("F6", r.stderr)                                                # 13 KB > 8 KB
        self.assertIn("brief/_entry:", r.stdout)                                     # 讀者清單
        js = json.loads((self.copy / "brief" / "tables.json").read_text())
        self.assertEqual(set(js), {"address", "banned", "beats", "cast", "events", "openers", "places", "samples", "_metainfo"})
        self.assertEqual(js["cast"], json.loads((d / "cast.json").read_text()))
        self.assertTrue(d.is_dir())                                                  # 不刪：人改完讀者、verify 過了再刪
        r = self.fold("pack", d)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: NameBad \S")
        r = self.fold("pack", self.copy / "draft")                                  # 有不是 JSON 的東西＝不打包
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: TargetBad \S")

    def test_verify(self):
        r = self.verify(GB, self.copy, env=["GALTXT_FAKE_BAD_FIRST=1"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        summary = json.loads(r.stdout.splitlines()[-1])
        self.assertEqual((summary["code"], summary["counter_bad"]), ([0, 0], 0))
        self.assertGreater(summary["counter_time_only"], 0)                          # trace／measure 只差時間欄
        lint = self.copy / "lib" / "lint" / "_entry"
        s = lint.read_text()
        self.assertIn('bad(1, "exclaim",', s)
        write(lint, s.replace('bad(1, "exclaim",', 'bad(1, "exclaim_changed",'), x=True)
        r = self.verify(GB, self.copy, env=["GALTXT_FAKE_BAD_FIRST=1"])
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-fold: VerifyFailed \S")
        self.assertIn("exclaim_changed", r.stdout)

    def test_cli_errors(self):
        for args, code in ((["agent"], "ArgumentsBad"), (["bogus", "x"], "ArgumentsBad"), (["--nope", "pack", "x"], "FlagUnknown"),
                           (["pack", "x", "--script", "a"], "ArgumentsBad"), (["--dry-run", "verify", "a", "b"], "ArgumentsBad"),
                           (["pack", str(self.tmp / "nope")], "TargetBad"), (["link", str(self.copy / "lib")], "TargetBad")):
            with self.subTest(args=args):
                r = self.fold(*args)
                self.assertEqual(r.returncode, 1)
                self.assertRegex(r.stderr, r"^aos-fold: %s \S" % code)
                self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
