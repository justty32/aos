"""test_lua_aos - Lua 寫 aos（proto8/extras/langs/lua）：編出來跟手寫的 demo 一樣、真跑結果一樣；nvim 外掛 headless 走一遍。

設計：proto8/thinking/2026-10-24-lua-nvim.md。lua／luajit／nvim 都沒有就整份 skip；nvim 那段沒有 nvim 才 skip。"""
import json, os, re, shutil, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

LUA_DIR = ROOT / "extras" / "langs" / "lua"
AOS_LUA = str(LUA_DIR / "bin" / "aos-lua")
EX = LUA_DIR / "examples"
NVIM_DIR = ROOT / "extras" / "editors" / "nvim"
EXEC = tool("aos-exec")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO",
         "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")


def runners():
    """能跑 aos-lua 的方式：lua、luajit、nvim -l（有哪個算哪個）。"""
    out = []
    for name in ("lua", "luajit"):
        if shutil.which(name):
            out.append([name, AOS_LUA])
    if shutil.which("nvim"):
        out.append(["nvim", "-l", AOS_LUA])
    return out


RUNNERS = runners()


def env():
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    return e


def aos_lua(*args, runner=None):
    return subprocess.run((runner or RUNNERS[0]) + list(args), capture_output=True, text=True, env=env())


def files(d):
    """{相對路徑: (內容 bytes, 是否 +x)}，略過 __pycache__。"""
    out = {}
    for p in sorted(Path(d).rglob("*")):
        if "__pycache__" in p.parts or p.is_dir():
            continue
        out[str(p.relative_to(d))] = (p.read_bytes(), os.access(p, os.X_OK))
    return out


def same_tree(test, built, hand):
    a, b = files(built), files(hand)
    test.assertEqual(sorted(a), sorted(b))
    for name in a:
        (ta, xa), (tb, xb) = a[name], b[name]
        test.assertEqual(xa, xb, name + " 的 +x 不一樣")
        if name.endswith(".json") or name == "_entry" and not xa:
            test.assertEqual(json.loads(ta), json.loads(tb), name)
        else:
            test.assertEqual(ta, tb, name)


def run_agent(agent, question):
    """在新工作區放一題、aos-exec 跑到停；回 (結果, 答案, trace 的格名)。"""
    ws = Path(tempfile.mkdtemp(prefix="lua-aos-ws-"))
    (ws / "new").mkdir()
    (ws / "new" / "q1.txt").write_text(question)
    r = subprocess.run([EXEC, "--ws", str(ws), str(agent)], capture_output=True, text=True, env=env(), timeout=60)
    out = ws / "out" / "q1.txt"
    trace = ws / ".stack" / "trace.jsonl"
    states = [json.loads(l)["state"] for l in trace.read_text().splitlines()] if trace.exists() else []
    answer = out.read_text() if out.exists() else None
    if answer:   # agent-dan 的假腦叫 clock，答案裡有當下時間：抹掉才比得了
        answer = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "<時間>", answer)
    shutil.rmtree(ws)
    return r, answer, states


@unittest.skipUnless(RUNNERS, "沒有 lua、luajit、nvim")
class TestBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lua-aos-"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def build(self, src, runner=None):
        out = self.tmp / Path(src).stem
        r = aos_lua("build", str(EX / src), str(out), runner=runner)
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def test_ann_same_as_demo(self):
        same_tree(self, self.build("agent_ann.lua"), ROOT / "demo" / "agent-ann")

    def test_dan_same_as_demo(self):
        same_tree(self, self.build("agent_dan.lua"), ROOT / "demo" / "agent-dan")

    def test_runners_agree(self):
        """lua、luajit、nvim -l 編出來逐位元組一樣。"""
        outs = []
        for i, runner in enumerate(RUNNERS):
            out = self.tmp / ("r%d" % i)
            r = aos_lua("build", str(EX / "agent_dan.lua"), str(out), runner=runner)
            self.assertEqual(r.returncode, 0, (runner, r.stderr))
            outs.append(files(out))
        for o in outs[1:]:
            self.assertEqual(o, outs[0])

    def test_run_same_as_demo(self):
        """假腦下，編出來的 ann、dan 跟手寫的跑出一樣的答案與 trace。"""
        for src, hand in (("agent_ann.lua", "agent-ann"), ("agent_dan.lua", "agent-dan")):
            built = self.build(src)
            r1, a1, s1 = run_agent(built, "17*23 是多少？\n")
            r2, a2, s2 = run_agent(ROOT / "demo" / hand, "17*23 是多少？\n")
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertEqual((r1.returncode, a1, s1), (r2.returncode, a2, s2), src)
            self.assertIn("FAKE ANSWER", a1)

    def test_daemon_clocks(self):
        """for 迴圈產生三個子 loop，各跑 n 次 aos-tick。"""
        out = self.build("clocks.lua")
        ws = self.tmp / "ws"
        ws.mkdir()
        r = subprocess.run([EXEC, "--ws", str(ws), str(out)], capture_output=True, text=True, env=env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in (1, 2, 3):
            self.assertEqual((ws / ".stack" / ("clock_%d" % n) / "tick.txt").read_text().strip(), str(n))

    def test_json_pointer(self):
        r = aos_lua("json", str(EX / "agent_dan.lua"), "fsm.json#/states/think/exec")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"argv": ["python3", "brain.py"], "timeout_ms": 120000})
        r = aos_lua("json", str(EX / "agent_dan.lua"), "fsm.json#/states/nope")
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "PathMissing"))

    def test_ls(self):
        r = aos_lua("ls", str(EX / "clocks.lua"))
        self.assertEqual(r.stdout.split(), ["_entry", "daemon.json"])

    def test_shape_errors_point_at_source_line(self):
        cases = {
            'return aos.fsm{start = "a", states = {a = {exec = "x", next = "b"}}}': "next（b）不在 states",
            'return aos.fsm{start = "z", states = {a = {exec = "x", next = "a"}}}': "start（z）不在 states",
            'return aos.loop{max = 3}': "aos.loop 缺 exec",
            'return aos.inst{argv = {}}': "非空的 argv",
            'return aos.env("X", {pth = "a"})': "不認得修飾 pth",
            'return aos.dir{["a/b"] = "x"}': "不含 / 的字串",
        }
        for body, want in cases.items():
            src = self.tmp / "bad.lua"
            # 不寫成 return aos.fsm{...}：那是尾呼叫，Lua 會丟掉呼叫者那一層，錯誤就沒有行號（邊緣狀況，見 thinking）
            src.write_text('local aos = require("aos")\nlocal x = ' + body[len("return "):] + "\nreturn x\n")
            r = aos_lua("ls", str(src))
            self.assertEqual(r.returncode, 1, body)
            self.assertTrue(r.stderr.startswith("aos-lua: SourceBad "), r.stderr)
            self.assertIn("bad.lua:2:", r.stderr, body)   # 指到原始檔第 2 行
            self.assertIn(want, r.stderr, body)

    def test_arguments_bad(self):
        r = aos_lua("build", str(EX / "clocks.lua"))
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "ArgumentsBad"))

    def test_json_values(self):
        src = self.tmp / "v.lua"
        src.write_text('local aos = require("aos")\nreturn {a = aos.array(), b = {}, c = 1.5, d = "引號\\"\\n", '
                       'e = aos.null, f = aos.obj{{"z", 1}, {"y", 2}}, g = 120000}\n')
        r = aos_lua("json", str(src))
        self.assertEqual(r.returncode, 0, r.stderr)
        v = json.loads(r.stdout)
        self.assertEqual(v, {"a": [], "b": {}, "c": 1.5, "d": "引號\"\n", "e": None, "f": {"z": 1, "y": 2}, "g": 120000})
        self.assertLess(r.stdout.index('"z"'), r.stdout.index('"y"'))   # aos.obj 照寫的順序


@unittest.skipUnless(shutil.which("nvim"), "沒有 nvim")
class TestNvim(unittest.TestCase):
    def test_headless_smoke(self):
        """editors/nvim/tests/smoke.lua：在 nvim --clean --headless 裡把外掛的指令都走一遍。"""
        r = subprocess.run(["nvim", "--clean", "--headless", "-l", str(NVIM_DIR / "tests" / "smoke.lua")],
                           capture_output=True, text=True, env=env(), timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("smoke: 全部通過", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
