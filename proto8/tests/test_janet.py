"""test_janet - Janet 編成 aos（proto8/extras/langs/janet）：編三個例子、用 aos-exec 真的跑，agent-dan 跟手寫版比。

設計：proto8/thinking/2026-10-24-janet-compile.md。沒裝 janet 就整個 skip。"""
import json, os, re, shutil, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

JANET = shutil.which("janet")
LANG = ROOT / "extras" / "langs" / "janet"
COMPILER = str(LANG / "bin" / "aos-janet")
EXAMPLES = LANG / "examples"
DAN = ROOT / "demo" / "agent-dan"
EXEC = tool("aos-exec")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO",
         "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


def run(*args, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def files(root):
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


@unittest.skipUnless(JANET, "沒裝 janet")
class JanetCompile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def compile(self, name):
        out = self.tmp / name
        r = run(COMPILER, str(EXAMPLES / (name + ".janet")), str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def ask_dan(self, prog):
        ws = self.tmp / ("ws-" + Path(prog).name)
        (ws / "new").mkdir(parents=True)
        (ws / "new" / "q1.txt").write_text("現在幾點？\n", encoding="utf-8")
        r = run(EXEC, "--ws", str(ws), str(prog), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = TIME.sub("<時間>", (ws / ".stack" / "history.jsonl").read_text(encoding="utf-8"))
        answer = TIME.sub("<時間>", (ws / "out" / "q1.txt").read_text(encoding="utf-8"))
        trace = [json.loads(line)["state"] for line in (ws / ".stack" / "trace.jsonl").read_text().splitlines()]
        return files(ws), history, answer, trace, (ws / ".stack" / "state.txt").read_text()

    def test_agent_dan_same_shape(self):
        """編出來的檔跟手寫的一樣多；JSON 檔內容相同（順序、空白可以不同）；Python 葉子位元組相同。"""
        out = self.compile("agent_dan")
        self.assertEqual(files(out), files(DAN))
        for f in ("fsm.json", "loop.json", "tools/clock/tool.json", "tools/math/tool.json"):
            self.assertEqual(json.loads((out / f).read_text()), json.loads((DAN / f).read_text()), f)
        for f in ("brain.py", "act.py", "system.txt", "tools/math/_entry"):
            self.assertEqual((out / f).read_bytes(), (DAN / f).read_bytes(), f)
        self.assertEqual(json.loads((out / "_entry").read_text()), ["aos-loop", "loop.json"])   # 手寫版是 sh，這裡是 argv 陣列
        self.assertIn("AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low\n", (out / ".env").read_text())
        self.assertIn("算一個算術式子", (out / "tools/math/tool.json").read_text(encoding="utf-8"))   # 中文不跳脫
        for f in ("idle/_entry", "tools/clock/_entry", "tools/math/_entry"):
            self.assertTrue(os.access(out / f, os.X_OK), f)

    def test_agent_dan_runs_same(self):
        """假腦（叫 clock 再答）：兩版跑完的工作區、history、答案、走過的格都一樣（時間換掉）。"""
        out = self.compile("agent_dan")
        got, want = self.ask_dan(out), self.ask_dan(DAN)
        self.assertEqual(got, want)
        self.assertIn("FAKE ANSWER to: 現在幾點？（clock said: <時間>）", got[2])

    def test_count_loop_fsm(self):
        """loop＋fsm，葉子是 Janet：tick 數到 3、第 4 次退 10，loop 以 0 結束；tock 印三行。"""
        out = self.compile("count")
        self.assertTrue((out / "tick" / "_entry").read_text().startswith("#!/usr/bin/env janet\n"))
        ws = self.tmp / "ws"
        ws.mkdir()
        r = run(EXEC, "--ws", str(ws), str(out), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / "out.txt").read_text(), "tock\n" * 3)
        self.assertEqual((ws / ".stack" / "n.txt").read_text(), "3\n")

    def test_steps_seq_par_if(self):
        """seq 依序、par 兩步都跑、if 看工作區有沒有 flag；每一步一個小格。"""
        out = self.compile("steps")
        ws = self.tmp / "ws"
        ws.mkdir()
        r = run(EXEC, "--ws", str(ws), str(out), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (ws / "out.txt").read_text().splitlines()
        self.assertEqual(lines[0], "一")
        self.assertEqual(sorted(lines[1:3]), ["二a", "二b"])
        self.assertEqual(lines[3:], ["沒有 flag"])
        (ws / "flag").touch()
        r = run(EXEC, "--ws", str(ws), str(out), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / "out.txt").read_text().splitlines()[-1], "有 flag")
        for d in ("s1", "s2/p1", "s2/p2", "s3/cond", "s3/then", "s3/else"):
            self.assertTrue((ws / ".stack" / d).is_dir(), d)

    def test_seq_stops_on_failure(self):
        """seq 的一步非 0：以它的碼結束、後面不跑。"""
        src = self.tmp / "p.janet"
        src.write_text('(def program (aos-seq (inst ["sh" "-c" "exit 7"]) (inst ["touch" (env "AOS_WS" "/after")])))')
        out, ws = self.tmp / "o", self.tmp / "ws"
        ws.mkdir()
        self.assertEqual(run(COMPILER, str(src), str(out)).returncode, 0)
        self.assertEqual(run(EXEC, "--ws", str(ws), str(out)).returncode, 7)
        self.assertFalse((ws / "after").exists())

    def errors(self, source, *args):
        src = self.tmp / "e.janet"
        src.write_text(source)
        r = run(COMPILER, *args, str(src), str(self.tmp / "eo"))
        self.assertEqual(r.returncode, 1)
        m = re.match(r"aos-janet: ([A-Z][A-Za-z]+) \S", r.stderr.splitlines()[-1])
        self.assertTrue(m, r.stderr)
        return m.group(1)

    def test_errors(self):
        self.assertEqual(self.errors("(def x 1)"), "ProgramMissing")
        self.assertEqual(self.errors('(def program (dir "a" (obj "k" 1 "k" 2)))'), "KeyTwice")
        self.assertEqual(self.errors('(def program (dir "x/y" 1))'), "NameBad")
        self.assertEqual(self.errors('(def program (dir "idle" 1 "f.json" (aos-fsm (idle (dir "_entry" (sh "true")) idle))))'),
                         "NameTaken")
        self.assertEqual(self.errors("(def program (dir \"a\" (nope)))"), "SourceBad")
        (self.tmp / "eo").mkdir(exist_ok=True)
        (self.tmp / "eo" / "keep").write_text("x")
        self.assertEqual(self.errors('(def program (dir "a" 1))'), "OutExists")
        r = run(COMPILER, "--force", str(self.tmp / "e.janet"), str(self.tmp / "eo"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.tmp / "eo" / "keep").read_text(), "x")   # --force 不刪別的檔
        r = run(COMPILER, "only-one")
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "ArgumentsBad"))


if __name__ == "__main__":
    unittest.main()
