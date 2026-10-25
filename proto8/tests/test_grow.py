"""test_grow - grow/aos-grow（函數往上長一級／縮回一級，呼叫方跟著改、行為不變）。

設計：proto8/thinking/2026-10-24-fn-grow.md。核心那個測試把 demo/agent-dan 複製兩份、只長其中一份，
用假腦（沒設 AOS_BRAIN_URL）各跑兩題，抹掉時間後工作區與 stack 每個檔都要一樣。"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GROW = str(ROOT / "extras" / "grow" / "aos-grow")
DAN = ROOT / "demo" / "agent-dan"
CODES = ("ArgumentsBad", "FlagUnknown", "CfgMissing", "CfgBad", "TargetBad", "NameBad", "WriteFailed")
TS = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)")


def grow(*args):
    r = subprocess.run([sys.executable, GROW, *args], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        m = re.match(r"aos-grow: ([A-Z][A-Za-z]+) \S", line)
        assert m and m.group(1) in CODES, "aos-grow 的錯誤行格式不對：%r" % line
    return r


def code(r):
    return r.stderr.split()[1] if r.stderr else None


def tree(d):
    out = {}
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            p = os.path.join(base, f)
            out[os.path.relpath(p, d)] = Path(p).read_bytes()
    return out


def run_agent(agent, extra=None):
    ws = tempfile.mkdtemp(prefix="grow-ws-")
    os.makedirs(ws + "/new")
    for i, q in enumerate(["幾點了？", "現在時間"]):
        Path(ws, "new", "q%d.txt" % i).write_text(q, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = path_with(env.get("PATH", ""))
    env.update(extra or {})
    r = subprocess.run([EXEC, str(agent)], cwd=ws, env=env, capture_output=True, text=True)
    files = {}
    for base, _, fs in os.walk(ws):
        for f in fs:
            p = os.path.join(base, f)
            s = TS.sub("<T>", Path(p).read_text(encoding="utf-8"))
            files[os.path.relpath(p, ws)] = re.sub(r'"elapsed_ms": \d+', '"elapsed_ms": N', s)
    shutil.rmtree(ws)
    return r.returncode, TS.sub("<T>", r.stderr), files


class GrowDan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="grow-")
        self.before, self.after = Path(self.tmp, "before"), Path(self.tmp, "after")
        ign = shutil.ignore_patterns("__pycache__")
        shutil.copytree(DAN, self.before, ignore=ign)
        shutil.copytree(DAN, self.after, ignore=ign)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_dry_run_writes_nothing(self):
        old = tree(self.after)
        r = grow("--dry-run", "up", "%s/fsm.json#/states/think/exec" % self.after, "--to", "dir", "--take", "brain.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(tree(self.after), old)
        self.assertIn("建資料夾", r.stdout)
        self.assertIn('+           "think": {"exec": "think", "next": "act"},', r.stdout)
        self.assertIn("brain.py →", r.stdout)

    def grow_both(self):
        fsm = "%s/fsm.json" % self.after
        self.assertEqual(grow("up", fsm + "#/states/think/exec", "--to", "dir", "--take", "brain.py").returncode, 0)
        self.assertEqual(grow("up", fsm + "#/states/act/exec", "--to", "file").returncode, 0)
        states = json.loads(Path(fsm).read_text())["states"]
        self.assertEqual(states["think"]["exec"], "think")
        self.assertEqual(states["act"]["exec"], "act")
        self.assertEqual(json.loads(Path(self.after, "act.json").read_text()), {"argv": ["python3", "act.py"], "timeout_ms": 60000})
        self.assertEqual(json.loads(Path(self.after, "think", "_entry").read_text()),
                         {"argv": ["python3", {"$env": "AOS_CD", "$path": "/brain.py"}], "timeout_ms": 120000, "cwd": ".."})
        self.assertFalse(Path(self.after, "brain.py").exists())

    def test_same_result_after_growing(self):
        """鐵律 1：長完跑起來一樣（假腦兩題；腦掛掉的失敗路徑也一樣）。"""
        self.grow_both()
        for extra in (None, {"AOS_BRAIN_URL": "http://127.0.0.1:9/v1"}):
            a, b = run_agent(self.before, extra), run_agent(self.after, extra)
            self.assertEqual(a, b, "extra=%r" % extra)
        self.assertEqual(a[0], 1)                      # 第二輪是腦掛掉的，真的走到失敗那條
        self.assertEqual(run_agent(self.after)[0], 0)

    def test_round_trip(self):
        """長上去再縮回來＝原本那格的值（think 搬了 brain.py 縮不回單檔，act 走 file → dir → file → 內嵌）。"""
        fsm = "%s/fsm.json" % self.after
        orig = json.loads(Path(fsm).read_text())
        self.grow_both()
        self.assertEqual(code(grow("down", fsm + "#/states/think/exec")), "TargetBad")
        self.assertEqual(grow("up", fsm + "#/states/act/exec", "--to", "dir").returncode, 0)
        self.assertTrue(Path(self.after, "act", "_entry").is_file())
        self.assertFalse(Path(self.after, "act.json").exists())
        self.assertEqual(grow("down", fsm + "#/states/act/exec").returncode, 0)   # 資料夾 → 檔
        self.assertEqual(grow("down", fsm + "#/states/act/exec").returncode, 0)   # 檔 → 內嵌
        self.assertEqual(json.loads(Path(fsm).read_text())["states"]["act"], orig["states"]["act"])
        self.assertFalse(Path(self.after, "act.json").exists())


class Rebase(unittest.TestCase):
    """搬位置時 cwd、$ref、$env AOS_CD 改成指回原處；AOS_CF／AOS_CO 不搬。"""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="grow-")
        self.cfg = Path(self.d, "fsm.json")

    def tearDown(self):
        shutil.rmtree(self.d)

    def put(self, inst, extra=None):
        doc = {"states": {"s": {"exec": inst}}}
        doc.update(extra or {})
        self.cfg.write_text(json.dumps(doc))
        return "%s#/states/s/exec" % self.cfg

    def test_dir_rebases_paths(self):
        caller = self.put({"argv": ["x", {"$ref": "#/args"}, {"$ref": "lib/a.json#/b"}, {"$env": "AOS_CD", "$path": "/tools"}],
                           "cwd": "sub", "stdout": "o.txt"})
        self.assertEqual(grow("up", caller, "--to", "dir").returncode, 0)
        got = json.loads(Path(self.d, "s", "_entry").read_text())
        self.assertEqual(got, {"argv": ["x", {"$ref": "../fsm.json#/args"}, {"$ref": "../lib/a.json#/b"},
                                        {"$env": "AOS_CD", "$path": "/../tools"}],
                               "cwd": "../sub", "stdout": "o.txt"})
        self.assertEqual(grow("down", caller).returncode, 0)
        self.assertEqual(json.loads(Path(self.d, "s.json").read_text())["cwd"], "sub")

    def test_file_points_own_refs_back(self):
        caller = self.put({"argv": ["x", {"$ref": "#/args"}]})
        self.assertEqual(grow("up", caller, "--to", "file", "--name", "job").returncode, 0)
        self.assertEqual(json.loads(Path(self.d, "job.json").read_text()), {"argv": ["x", {"$ref": "fsm.json#/args"}]})

    def test_refusals(self):
        caller = self.put({"argv": ["x", {"$env": "AOS_CF"}]})
        self.assertEqual(code(grow("up", caller, "--to", "file")), "TargetBad")
        caller = self.put({"argv": ["x"]})
        Path(self.d, "s.json").write_text("{}")
        self.assertEqual(code(grow("up", caller, "--to", "file")), "NameBad")
        os.remove(Path(self.d, "s.json"))
        self.assertEqual(code(grow("up", caller)), "ArgumentsBad")
        self.assertEqual(code(grow("--nope", "up", caller, "--to", "file")), "FlagUnknown")
        self.assertEqual(code(grow("up", "%s#/states/zz/exec" % self.cfg, "--to", "file")), "CfgMissing")
        self.assertEqual(code(grow("up", "%s#/states/s" % self.cfg, "--to", "file")), "TargetBad")   # 不是單子
        # 縮回：還有別格叫它＝不內嵌
        self.put("s", {"other": {"exec": "s"}})
        Path(self.d, "s.json").write_text(json.dumps({"argv": ["x"]}))
        self.assertEqual(code(grow("down", "%s#/states/s/exec" % self.cfg)), "NameBad")


if __name__ == "__main__":
    unittest.main()
