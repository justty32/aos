"""test_janet - Janet 編成 aos（proto8/extras/langs/janet）：編例子、用 aos-exec 真的跑（agent_dan 那兩案 11-03 隨 examples/agent_dan.janet 封存到 proto8/archive/agent-dan-langs/）。

設計：proto8/thinking/2026-10/24/janet-compile.md。沒裝 janet 就整個 skip。"""
import json, os, re, shutil, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with, fsm_steps  # noqa: E402

JANET = shutil.which("janet")
LANG = ROOT / "extras" / "langs" / "janet"
COMPILER = str(LANG / "bin" / "aos-janet")
EXAMPLES = LANG / "examples"
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
        # P-44（11-04）：不認得的旗標＝FlagUnknown、開關帶值＝ArgumentsBad、`--` 之後都是位置參數
        r = run(COMPILER, "--nope", str(self.tmp / "e.janet"), str(self.tmp / "eo"))
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "FlagUnknown"))
        r = run(COMPILER, "--force=1", str(self.tmp / "e.janet"), str(self.tmp / "eo"))
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "ArgumentsBad"))
        r = run(COMPILER, "--force", "--", str(self.tmp / "e.janet"), str(self.tmp / "eo"))
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
