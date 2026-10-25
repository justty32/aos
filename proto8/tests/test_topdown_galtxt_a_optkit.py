"""test_topdown_galtxt_a_optkit - galtxt-a 的 optkit（自我優化工具包，plan/round4-selfopt.md 步驟 6a）：九支 opt_* 工具、shell、run／accept、claude（claude code CLI 代勞）。

兩組：
- TreeContractT：optkit/opt_test 對拷貝跑的那幾個（optkit/tests.json 點名）——G 讀環境變數 GALTXT_TREE（沒設＝setUpClass 自己拷一份真樹，不弄髒真樹）。只驗工具契約與既有行為，不碰尺。
- OptkitT：round4-selfopt § 6 的 so-1～so-7、so-9、so-12（6a 的部分；so-8 回滾、so-10 整條訓練、so-11 fallback 要 6b 的優化器）＋ cc-1～3（optkit/claude，用 PATH 上的假 claude）。
全部離線（假腦、假 claude）；每個測試在 tree_copy 上跑。"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
G_REAL = ROOT / "topdown" / "galtxt-a"
EXAMPLES = G_REAL / "plan" / "examples"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "GALTXT_OPT", "GALTXT_FAKE_OPT", "GALTXT_STAGE")
OPT_TOOLS = ("opt_describe", "opt_history", "opt_read", "opt_edit", "opt_write", "opt_extract", "opt_try", "opt_test", "opt_note")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR and not k.startswith("OPTKIT_") and k != "GALTXT_TREE"}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, **kw)


def jread(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jwrite(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def jl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def tree_copy(t):
    """同 test_topdown_galtxt_a.tree_copy：整棵拷到 t/proto8/topdown/galtxt-a、t/proto8/lib 指回真的 lib"""
    g = Path(t) / "proto8" / "topdown" / "galtxt-a"
    shutil.copytree(G_REAL, g, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    os.symlink(ROOT / "lib", Path(t) / "proto8" / "lib")
    return g


def snapshot(root, skip=()):
    out = {}
    for here, subs, files in os.walk(root):
        subs[:] = [s for s in subs if s != "__pycache__"]
        for n in subs + files:
            p = Path(here) / n
            rel = str(p.relative_to(root))
            if rel.split("/")[0] in skip:
                continue
            out[rel] = ("L", os.readlink(p)) if p.is_symlink() else (p.read_bytes(), os.access(p, os.X_OK)) if p.is_file() else "dir"
    return out


# ------------------------------------------------------------------ opt_test 跑的那組

class TreeContractT(unittest.TestCase):
    """optkit/opt_test 叫的（GALTXT_TREE＝拷貝根）：writer/tools 底下每支工具守契約、beat／voice 既有行為不變、stage.json 合法、program 階跑得通"""

    @classmethod
    def setUpClass(cls):
        cls._t = None
        if os.environ.get("GALTXT_TREE"):
            cls.G = Path(os.environ["GALTXT_TREE"])
        else:
            cls._t = tempfile.TemporaryDirectory()
            cls.G = tree_copy(cls._t.name)
        cls.tmp = Path(tempfile.mkdtemp(prefix="treecontract-"))

    @classmethod
    def tearDownClass(cls):
        if cls._t:
            cls._t.cleanup()
        assert str(cls.tmp).startswith(tempfile.gettempdir())
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tools(self):
        d = self.G / "writer" / "tools"
        return sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink() and (p / "tool.json").exists())

    def call(self, name, args):
        return run(EXEC, self.G / "writer" / "tools" / name, input=args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
                   env={"AOS_STACK": str(self.tmp / "toolstack" / name) + "/"})

    def test_tools_contract(self):
        names = [p.name for p in self.tools()]
        self.assertTrue({"beat", "voice"} <= set(names), names)
        for d in self.tools():
            spec = jread(d / "tool.json")
            self.assertTrue({"description", "parameters"} <= set(spec), d)
            self.assertEqual(spec["parameters"].get("type"), "object", d)
            e = d / "_entry"
            self.assertTrue(os.access(e, os.X_OK), e)
            src = e.read_text(encoding="utf-8")
            self.assertTrue(src.startswith("#!"), e)
            if "python" in src.splitlines()[0]:
                compile(src, str(e), "exec")                       # 編譯得過（不寫 __pycache__）
            self.assertIn("kind", jread(d / "_metainfo"), d)
            r = self.call(d.name, "")                               # 空 stdin：退 0 或 1、stdout 至少一行
            self.assertIn(r.returncode, (0, 1), (d.name, r.stderr))
            self.assertTrue(r.stdout.strip(), d.name)
            r = self.call(d.name, "nope")                           # 不是 JSON：退 1、stderr 一行「名: ArgumentsBad」
            self.assertEqual(r.returncode, 1, d.name)
            self.assertRegex(r.stderr, r"^%s: ArgumentsBad \S" % d.name)

    def test_beat_voice_behavior(self):
        """同 test_topdown_galtxt_a 測試 6 的既有行為（介面不變：不帶新參數＝輸出一樣）"""
        r = self.call("beat", {"deny": "才沒有", "yield": "也不是不能接受", "cover": "真是的"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        out = r.stdout.strip()
        self.assertTrue(0 <= out.index("才沒有") < out.index("也不是不能接受") < out.index("真是的"), out)
        r = self.call("beat", {"deny": "才沒有"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr.count("SlotMissing"), 2)
        r = self.call("voice", {"text": "才沒有。不過……也不是不能接受，真是的。", "who": "宮澤柚葉", "ending": "啦"})
        self.assertEqual((r.returncode, r.stdout), (0, "宮澤柚葉：「才沒有。不過……也不是不能接受，真是的啦。」\n"))
        self.assertEqual(self.call("voice", {"text": "{calls}拿著。", "calls": "你"}).stdout, "哼，你拿著。\n")
        r = self.call("voice", {})
        self.assertEqual((r.returncode, r.stdout.count("\n")), (0, 1))
        self.assertRegex(r.stderr, r"^voice: SlotMissing text")

    def test_stage(self):
        st = jread(self.G / "writer" / "stage.json")
        self.assertIn(st["stage"], ("agent", "semi", "program"))
        have = {p.name for p in (self.G / "writer" / "tools").iterdir() if (p / "tool.json").exists()}
        self.assertTrue(set(st["tools"]) <= have, set(st["tools"]) - have)

    def test_compose_program(self):
        ws = self.tmp / "ws-program"
        (ws / "new").mkdir(parents=True)
        jwrite(ws / "new" / "cls-ribbon.json", dict(jread(EXAMPLES / "cls-ribbon.json"), drafts=1))
        r = run(EXEC, "--ws", ws, self.G, env={"GALTXT_STAGE": "program", "GALTXT_JUDGE": "off"}, cwd=self.tmp, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (ws / "out" / "cls-ribbon" / "answer.txt").read_text(encoding="utf-8").splitlines()
        self.assertTrue(len(lines) >= 5, lines)


# ------------------------------------------------------------------ 假的 LLM（抓腦看到什麼）

class Stub:
    """本機一個 OpenAI 相容的假端點：記下每個請求的 body，回一則純文字"""

    def __init__(self, reply="宮澤柚葉：「哼。」"):
        self.bodies = []
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                stub.bodies.append(json.loads(self.rfile.read(n)))
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": reply}}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d/v1" % self.srv.server_address[1]

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


FAKE_CLAUDE = r'''#!/usr/bin/env python3
# 假的 claude（cc 測試用）：記下 argv／cwd／prompt，照 FAKE_CLAUDE 做事，印 claude -p --output-format json 的形狀
import json, os, sys, time
prompt = sys.stdin.read()
with open(os.environ["FAKE_CLAUDE_LOG"], "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}, f, ensure_ascii=False)
mode = os.environ.get("FAKE_CLAUDE", "edit")
if mode == "hang":
    time.sleep(60)
if mode == "edit":
    s = open("_entry", encoding="utf-8").read()
    s = s.replace('text = "%s，%s" % (tics[0], text)', 'text = "%s，%s" % (tics[0], text)   # claude 看過')
    open("_entry", "w", encoding="utf-8").write(s)
if mode == "cheat":
    with open("../../../data/dims.json", "a", encoding="utf-8") as f:
        f.write("\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "改好了", "num_turns": 3,
                  "duration_ms": 1234, "total_cost_usd": 0.0123, "session_id": "fake",
                  "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50},
                  "modelUsage": {"claude-sonnet-fake": {}}}))
'''


# ------------------------------------------------------------------ optkit 本身

class OptkitT(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.g = tree_copy(self.tmp / "t")
        self.kit = self.g / "optkit"

    # ---- 共用 ----
    def allow(self, sub, orig=None):
        r = run(sys.executable, "-B", "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import optkit_common as oc; "
                "print(json.dumps(oc.allow_entries(sys.argv[2], sys.argv[3]), ensure_ascii=False))", self.kit, orig or self.g, sub)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def sandbox(self, sub="writer", heldout=("lights",)):
        """不經 run 的沙箱：原樹 self.g 再拷一份當拷貝（optkit 換成指回原樹的捷徑，同 run）；回 (拷貝根, 環境)"""
        sb = self.tmp / "sb" / "proto8" / "topdown" / "galtxt-a"
        shutil.copytree(self.g, sb, symlinks=True, ignore=lambda d, n: [x for x in n if Path(d) == self.g and x in ("plan", "meta", "optkit")])
        os.symlink(self.kit, sb / "optkit")
        os.symlink(ROOT / "lib", self.tmp / "sb" / "proto8" / "lib")
        env = {"OPTKIT_TREE": str(sb), "OPTKIT_SUBTREE": sub, "OPTKIT_ALLOW": self.allow(sub), "OPTKIT_ORIG": str(self.g),
               "OPTKIT_HELDOUT": json.dumps(list(heldout)), "OPTKIT_CELL": str(self.tmp / "sbcell"), "OPTKIT_EPOCH": "0"}
        return sb, env

    def opt(self, name, args, env, sb=None):
        return run(self.kit / name / "_entry", input=args if isinstance(args, str) else json.dumps(args, ensure_ascii=False), env=env,
                   cwd=sb or self.tmp, timeout=900)

    def task(self, text="請優化", **extra):
        p = self.tmp / ("task-%d.json" % len(list(self.tmp.glob("task-*.json"))))
        jwrite(p, dict({"task": text}, **extra))
        return p

    def selfopt(self, sub, env=None, by=None, **task):
        cell = self.tmp / ("cell-%s-%d" % (sub.replace("/", "_"), len(list(self.tmp.glob("cell-*")))))
        args = [self.kit / "run" / "_entry", sub, "--task", self.task(**task), "--cell", cell, "--epoch", "0"] + (["--by", by] if by else [])
        return run(*args, env=env, cwd=self.tmp, timeout=900), cell

    def accept(self, cell, *args, env=None):
        return run(self.kit / "accept" / "_entry", cell, *args, env=env, cwd=self.tmp, timeout=900)

    def semi(self):
        jwrite(self.g / "writer" / "stage.json", dict(jread(self.g / "writer" / "stage.json"), stage="semi", tools=["lint", "beat", "voice"]))

    def calls(self, cell):
        return [c["function"]["name"] for m in jl(cell / "stack" / "history.jsonl") for c in m.get("tool_calls") or []]

    def tool_results(self, cell):
        return [m["content"] for m in jl(cell / "stack" / "history.jsonl") if m.get("role") == "tool"]

    # so-1 工具契約：九支各有三檔、tool.json 形狀、沒環境／空 stdin／壞 stdin 都一行錯（stderr＋stdout）不炸
    def test_contract(self):
        sb, env = self.sandbox()
        for n in OPT_TOOLS:
            d = self.kit / n
            self.assertEqual(sorted(os.listdir(d)), ["_entry", "_metainfo", "tool.json"], n)
            spec = jread(d / "tool.json")
            self.assertTrue({"description", "parameters"} <= set(spec), n)
            self.assertEqual(spec["parameters"]["type"], "object", n)
            self.assertEqual(jread(d / "_metainfo")["kind"], "program", n)
            self.assertTrue((self.g / "writer" / "tools" / n).is_symlink(), n)
            self.assertTrue((self.kit / "shell" / "tools" / n).is_symlink(), n)
            r = self.opt(n, "{}", {})                                   # 沒 OPTKIT_*：EnvMissing
            self.assertEqual(r.returncode, 1, n)
            self.assertRegex(r.stderr, r"^%s: EnvMissing \S" % n)
            self.assertEqual(r.stderr.count("\n"), 1, n)
            self.assertEqual(r.stdout, r.stderr, n)
            r = self.opt(n, "nope", env)
            self.assertEqual((r.returncode, r.stderr.count("\n")), (1, 1), n)
            self.assertRegex(r.stderr, r"^%s: ArgumentsBad \S" % n)
        for n in ("opt_describe", "opt_history"):                        # 空 stdin＝{}：直接有結果
            r = self.opt(n, "", env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["subtree"], "writer")
        d = json.loads(self.opt("opt_describe", "", env).stdout)
        self.assertEqual(d["kind"], "agent")
        self.assertIn("收尾旁白", d["decisions_left"])                    # brain $ref → stage.json 解開了
        self.assertIn("writer/tools/*/", d["opt_writes_allowed"])
        for n in ("opt_read", "opt_edit", "opt_write", "opt_extract", "opt_try", "opt_note"):   # 缺必要參數：一行 ArgumentsBad
            r = self.opt(n, "", env)
            self.assertEqual((r.returncode, r.stderr.count("\n")), (1, 1), (n, r.stderr))
            self.assertRegex(r.stderr, r"^%s: \w+ \S" % n)

    # so-2 白名單：尺拒、system.txt 准、新工具准、正解讀不到、出拷貝拒、拷貝裡加寬 opt_writes 沒用
    def test_whitelist(self):
        sb, env = self.sandbox()
        dims = (sb / "data" / "dims.json").read_text(encoding="utf-8")
        r = self.opt("opt_edit", {"path": "data/dims.json", "edits": [{"old_text": dims[:12], "new_text": dims[:12] + " "}]}, env)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^opt_edit: WriteDenied data/dims.json")
        self.assertEqual((sb / "data" / "dims.json").read_text(encoding="utf-8"), dims)
        first = (sb / "writer" / "system.txt").read_text(encoding="utf-8").splitlines()[0]
        r = self.opt("opt_edit", {"path": "writer/system.txt", "edits": [{"old_text": first, "new_text": first + "（改）"}]}, env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("（改）", (sb / "writer" / "system.txt").read_text(encoding="utf-8"))
        r = self.opt("opt_write", {"path": "writer/tools/new/_entry", "content": "#!/bin/sh\necho hi\n"}, env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.opt("opt_write", {"path": "writer/tools/voice/tool.json", "content": "{}"}, env)     # 既有工具資料夾不算新建
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied writer/tools/voice/tool.json")
        r = self.opt("opt_write", {"path": "writer/_metainfo", "content": "{}"}, env)                 # M7
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied writer/_metainfo")
        r = self.opt("opt_read", {"path": "data/bench/Q16.json"}, env)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^opt_read: PathDenied ")
        self.assertNotIn("answer", r.stdout)
        r = self.opt("opt_read", {"path": "../../../proto8/tests/aos_bins.py"}, env)
        self.assertRegex(r.stderr, r"^opt_read: PathBad ")
        os.symlink(self.tmp, sb / "writer" / "out_link")                                            # 捷徑解開在拷貝外
        r = self.opt("opt_read", {"path": "writer/out_link/task-0.json"}, env)
        self.assertRegex(r.stderr, r"^opt_read: PathBad ")
        r = self.opt("opt_read", {"path": "writer/tools/voice/_entry"}, env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("voice - ", r.stdout)
        m = jread(sb / "writer" / "_metainfo")                                                      # 拷貝裡加寬：沒用（白名單從原樹算）
        jwrite(sb / "writer" / "_metainfo", dict(m, opt_writes=m["opt_writes"] + ["../brief.py"]))
        env2 = dict(env, OPTKIT_ALLOW=self.allow("writer"))
        brief = (sb / "brief.py").read_text(encoding="utf-8").splitlines()[1]
        r = self.opt("opt_edit", {"path": "brief.py", "edits": [{"old_text": brief, "new_text": brief + " "}]}, env2)
        self.assertRegex(r.stderr, r"^opt_edit: WriteDenied brief.py：不在白名單")
        self.assertIn("brief.py", self.allow("writer", orig=sb.parent / "galtxt-a"))               # 對照：從拷貝算就會被加寬

    # so-3 #append 與 #/指標
    def test_append_pointer(self):
        sb, env = self.sandbox()
        p = sb / "data" / "templates.distilled.json"
        base = jread(p)
        poster = {"deny": {"01": {"text": "才沒有在看海報", "for": "scene.closeup.detail.poster"}}}
        r = self.opt("opt_write", {"path": "data/templates.distilled.json", "content": json.dumps(dict(base, by_detail={"poster": poster}), ensure_ascii=False)}, env)
        self.assertEqual(r.returncode, 0, r.stderr)
        bad = dict(base, by_detail={"poster": {"deny": {"01": {"text": "改掉了", "for": "x"}}}})
        r = self.opt("opt_write", {"path": "data/templates.distilled.json", "content": json.dumps(bad, ensure_ascii=False)}, env)
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied .*只准追加")
        r = self.opt("opt_write", {"path": "data/templates.distilled.json",
                                   "content": json.dumps(dict(base, by_detail={"poster": poster, "lights": poster}), ensure_ascii=False)}, env)
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied .*HeldOut.*lights")
        r = self.opt("opt_write", {"path": "data/templates.json", "content": "{}"}, env)            # 人寫的模板：deny
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied data/templates.json")
        st = jread(sb / "writer" / "stage.json")
        r = self.opt("opt_write", {"path": "writer/stage.json", "content": json.dumps(dict(st, tools=st["tools"] + ["beat"]), ensure_ascii=False)}, env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.opt("opt_write", {"path": "writer/stage.json", "content": json.dumps(dict(st, stage="program"), ensure_ascii=False)}, env)
        self.assertRegex(r.stderr, r"^opt_write: WriteDenied .*其他位置也變了")
        tj = (sb / "writer" / "tools" / "voice" / "tool.json").read_text(encoding="utf-8")
        r = self.opt("opt_edit", {"path": "writer/tools/voice/tool.json", "edits": [{"old_text": '"required": ["text"]', "new_text": '"required": ["text", "who"]'}]}, env)
        self.assertRegex(r.stderr, r"^opt_edit: WriteDenied ")                                     # required 不准動
        r = self.opt("opt_edit", {"path": "writer/tools/voice/tool.json",
                                  "edits": [{"old_text": '"description": "句尾語氣詞，例：啦"}', "new_text": '"description": "句尾語氣詞，例：啦"}, "idx": {"type": "integer"}'}]}, env)
        self.assertEqual(r.returncode, 0, r.stderr)                                                 # properties 追加：准
        self.assertNotEqual((sb / "writer" / "tools" / "voice" / "tool.json").read_text(encoding="utf-8"), tj)

    # so-4 agent 示範：writer semi 階、GALTXT_OPT=1 跑拷貝 → 劇本的 tool_call 序列、close 三檔、stage.tools 含 close、opt_log 一行；原樹不變
    def test_agent_selfopt(self):
        self.semi()
        before = snapshot(self.g)
        r, cell = self.selfopt("writer", task="請把收尾旁白做成工具 close", history={"runs": []})
        self.assertEqual(r.returncode, 0, r.stderr + (cell / "run.log").read_text(encoding="utf-8"))
        self.assertEqual(r.stderr, "")
        self.assertRegex(r.stdout, r"^run: writer by node：6 次腦")
        self.assertEqual(self.calls(cell), ["opt_describe", "opt_history", "opt_extract", "opt_test", "opt_note"])
        res = self.tool_results(cell)
        self.assertEqual(json.loads(res[3])["counter_fail"], 0, res[3])                              # opt_test 綠
        self.assertGreater(json.loads(res[3])["counter_pass"], 0)
        tree = cell / "tree" / "proto8" / "topdown" / "galtxt-a"
        close = tree / "writer" / "tools" / "close"
        self.assertEqual(sorted(os.listdir(close)), ["_entry", "_metainfo", "tool.json"])
        self.assertEqual(jread(close / "_metainfo")["author"], "writer@selfopt epoch 0")
        self.assertIn("close", jread(tree / "writer" / "stage.json")["tools"])
        log = jl(tree / "writer" / "opt_log.jsonl")
        self.assertEqual(len(log), 1)
        self.assertIn("writer/tools/close/_entry", {f["path"] for f in log[0]["files"]})
        out = run(EXEC, close, input='{"hint": "動作"}', env={"AOS_STACK": str(self.tmp / "cs") + "/"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(out.stdout.startswith("（"), out.stdout)
        self.assertEqual(snapshot(self.g), before)                                                    # accept 前原樹 bytes 不變
        rj = jread(cell / "run.json")
        self.assertEqual((rj["by"], rj["heldout"], rj["budget_spent"]), ("node", ["lights"], None))
        self.assertEqual(sorted(os.listdir(cell / "questions")), ["Q16-fixed.json", "cls-poster.json", "cls-ribbon.json"])   # 驗證題不在
        self.assertTrue((tree / "optkit").is_symlink())

    # so-4 下半：平常（沒 GALTXT_OPT）腦看不到 opt_*、system 是 system.txt；優化模式看得到、system 換 system.opt.txt（假端點抓請求）
    def test_tools_visible_only_in_opt(self):
        self.semi()
        stub = Stub()
        self.addCleanup(stub.close)
        ws = self.tmp / "ws"
        (ws / "new").mkdir(parents=True)
        jwrite(ws / "new" / "cls-ribbon.json", dict(jread(EXAMPLES / "cls-ribbon.json"), drafts=1))
        r = run(EXEC, "--ws", ws, self.g, env={"AOS_BRAIN_URL": stub.url, "GALTXT_JUDGE": "off"}, cwd=self.tmp, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(stub.bodies)
        normal = [b for b in stub.bodies]
        for b in normal:
            names = {t["function"]["name"] for t in b.get("tools") or []}
            self.assertEqual(names, {"lint", "beat", "voice"})
            self.assertEqual(b["messages"][0]["content"], (self.g / "writer" / "system.txt").read_text(encoding="utf-8"))
        stub.bodies.clear()
        r, cell = self.selfopt("writer", env={"AOS_BRAIN_URL": stub.url})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(stub.bodies), 1)
        names = {t["function"]["name"] for t in stub.bodies[0]["tools"]}
        self.assertEqual(names, {"lint", "beat", "voice"} | set(OPT_TOOLS))
        self.assertEqual(stub.bodies[0]["messages"][0]["content"], (self.g / "writer" / "system.opt.txt").read_text(encoding="utf-8"))
        self.assertIn('"subtree": "writer"', stub.bodies[0]["messages"][1]["content"])
        a = self.accept(cell)
        self.assertEqual((a.returncode, a.stdout), (0, "accept: writer 沒有變動\n"))

    # so-5 程式示範：shell 對 voice → _entry 變、properties.idx 在、required 不變；accept 後不帶 idx 的輸出跟改前一樣、帶 idx 輪替
    def test_shell_voice(self):
        voice = self.g / "writer" / "tools" / "voice"
        call = lambda args: run(EXEC, voice, input=json.dumps(args, ensure_ascii=False), env={"AOS_STACK": str(self.tmp / "vs") + "/"})   # noqa: E731
        samples = [{"text": "拿著。"}, {"text": "{calls}拿著。", "calls": "你", "who": "宮澤柚葉"}, {"text": "哼，好啦。", "ending": "啦"}, {}]
        before = [(call(a).stdout, call(a).returncode) for a in samples]
        req = jread(voice / "tool.json")["parameters"]["required"]
        r, cell = self.selfopt("writer/tools/voice", task="同題三份口癖都是『哼』；請讓口癖照 idx 輪替")
        self.assertEqual(r.returncode, 0, r.stderr + (cell / "run.log").read_text(encoding="utf-8"))
        self.assertRegex(r.stdout, r"^run: writer/tools/voice by shell：7 次腦")
        self.assertEqual(self.calls(cell), ["opt_describe", "opt_read", "opt_edit", "opt_edit", "opt_test", "opt_note"])
        tree = cell / "tree" / "proto8" / "topdown" / "galtxt-a"
        tv = tree / "writer" / "tools" / "voice"
        self.assertNotEqual((tv / "_entry").read_bytes(), (voice / "_entry").read_bytes())
        spec = jread(tv / "tool.json")
        self.assertIn("idx", spec["parameters"]["properties"])
        self.assertEqual(spec["parameters"]["required"], req)
        self.assertEqual(jread(tv / "_metainfo"), jread(voice / "_metainfo"))                        # 殼不屬於節點：_metainfo 不變
        a = self.accept(cell)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual([(call(x).stdout, call(x).returncode) for x in samples], before)            # 不帶 idx：一樣
        self.assertEqual(call({"text": "拿著。", "idx": 1}).stdout, "才不是，拿著。\n")               # 帶 idx：輪替
        self.assertEqual(call({"text": "拿著。", "idx": 5}).stdout, "哼，拿著。\n")
        ch = jread(cell / "params" / "changed.json")
        self.assertEqual((ch["action"], ch["subtree"], ch["by"]), ("selfopt", "writer/tools/voice", "shell@selfopt"))
        self.assertEqual(set(ch["files"]), {"writer/tools/voice/_entry", "writer/tools/voice/tool.json", "writer/tools/voice/opt_log.jsonl"})

    # so-6 accept 搬回（＋ so-12 M7）：--dry-run 不搬；搬了以後 close 三檔在原樹、changed.json 對、原版本在 params、尺與宣告 bytes 不變
    def test_accept_moves(self):
        self.semi()
        before = snapshot(self.g)
        r, cell = self.selfopt("writer", task="請把收尾旁白做成工具 close")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.accept(cell, "--dry-run")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertRegex(a.stdout, r"^accept: writer 會收 5 個檔")
        self.assertEqual(snapshot(self.g), before)
        self.assertFalse((cell / "params").exists() or (cell / "accept.json").exists())
        a = self.accept(cell)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertRegex(a.stdout, r"^accept: writer 收了 5 個檔.*新工具 writer/tools/close")
        after = snapshot(self.g)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"writer/stage.json", "writer/opt_log.jsonl", "writer/tools/close",
                                   "writer/tools/close/_entry", "writer/tools/close/_metainfo", "writer/tools/close/tool.json"})
        self.assertTrue(after["writer/tools/close/_entry"][1])                                       # +x 跟著搬
        ch = jread(cell / "params" / "changed.json")
        self.assertEqual((ch["source"], ch["action"], ch["subtree"], ch["by"], ch["created"]), ("selfopt", "selfopt", "writer", "writer@selfopt", ["writer/tools/close"]))
        self.assertEqual(set(ch["files"]), changed - {"writer/tools/close"})
        self.assertEqual(ch["cells"], [])
        self.assertEqual(ch["test"]["counter_fail"], 0)
        self.assertEqual((cell / "params" / "writer" / "stage.json").read_bytes(), before["writer/stage.json"][0])   # 回滾用的原版本
        self.assertFalse((cell / "params" / "writer" / "tools" / "close").exists())                  # 新檔沒有原版本
        self.assertTrue(jread(cell / "accept.json")["accepted"])
        for k in before:                                                                              # so-12 M7：宣告、尺、評審、訓練 bytes 不變
            if k.endswith(("_metainfo", "fsm.json", "dims.json", "lint_switches.json")) or k.startswith(("grader/", "train/", "tools/lint/", "data/bench/")):
                self.assertEqual(after.get(k), before[k], k)
        r = run(sys.executable, "-B", "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import common; "      # 步驟 5 的通用回滾吃得下這份 changed.json
                "common.rollback(sys.argv[2], json.load(open(sys.argv[3], encoding='utf-8')))",
                self.g / "train", cell / "params", cell / "params" / "changed.json", cwd=self.g / "train")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.g), before)

    # so-7 作弊與改壞：cheat＝工具層擋下、程式直接改尺被 accept 抓；break＝opt_test 紅 → accept 拒；原樹都不變
    def test_cheat_and_break(self):
        self.semi()
        before = snapshot(self.g)
        r, cell = self.selfopt("writer", env={"GALTXT_FAKE_OPT": "cheat"})
        self.assertEqual(r.returncode, 0, r.stderr)
        res = self.tool_results(cell)
        self.assertRegex(res[1], r"^opt_edit: WriteDenied data/dims.json")
        self.assertRegex(res[2], r"^opt_write: PathDenied proto8/tests/test_cheat.py")
        self.assertRegex(res[3], r"^opt_read: PathDenied data/bench/Q16.json")
        a = self.accept(cell)
        self.assertEqual(a.returncode, 1)
        self.assertRegex(a.stderr, r"^accept: WriteDenied data/dims.json（deny.json always")
        self.assertEqual(a.stderr.count("\n"), 1)
        self.assertFalse(jread(cell / "accept.json")["accepted"])
        self.assertEqual(snapshot(self.g), before)
        r, cell = self.selfopt("writer/tools/voice", env={"GALTXT_FAKE_OPT": "break"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(json.loads(self.tool_results(cell)[2])["counter_fail"], 0)
        a = self.accept(cell)
        self.assertEqual(a.returncode, 1)
        self.assertRegex(a.stderr, r"^accept: TestFailed opt_test 紅：\S")
        self.assertEqual(snapshot(self.g), before)
        a = self.accept(cell, "--no-test")                                                            # 對照：不跑測試就會收（證明是測試擋的）
        self.assertEqual(a.returncode, 0, a.stderr)

    # so-9 預算：max_calls 2 → BudgetSpent、run.json 記著、accept 不收、原樹不變
    def test_budget(self):
        self.semi()
        before = snapshot(self.g)
        r, cell = self.selfopt("writer", budget={"max_calls": 2})
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^run: BudgetSpent 腦 [3-9]／2 則")
        self.assertEqual(r.stderr.count("\n"), 1)
        self.assertTrue(jread(cell / "run.json")["budget_spent"])
        a = self.accept(cell)
        self.assertEqual(a.returncode, 1)
        self.assertRegex(a.stderr, r"^accept: RunFailed ")
        self.assertEqual(snapshot(self.g), before)
        r, _ = self.selfopt("writer", budget={"max_calls": 99})                                       # 只能壓低：99 照 budget.json 的 12
        self.assertEqual(r.returncode, 0, r.stderr)

    # run／accept 的參數錯
    def test_run_errors(self):
        r, _ = self.selfopt("train")
        self.assertRegex(r.stderr, r"^run: SubtreeBad train ")
        r, _ = self.selfopt("../x")
        self.assertRegex(r.stderr, r"^run: SubtreeBad ")
        p = self.tmp / "bad.json"
        p.write_text("[]")
        r = run(self.kit / "run" / "_entry", "writer", "--task", p, "--cell", self.tmp / "c", cwd=self.tmp)
        self.assertRegex(r.stderr, r"^run: TaskBad ")
        r = run(self.kit / "run" / "_entry", "writer", "--task", self.task(), cwd=self.tmp)
        self.assertRegex(r.stderr, r"^run: StackMissing ")
        a = self.accept(self.tmp / "nowhere")
        self.assertRegex(a.stderr, r"^accept: CellBad ")

    # ---- claude（cc-1～3）：PATH 上放假的 claude ----
    def fake_claude(self, mode):
        b = self.tmp / "fakebin"
        b.mkdir(exist_ok=True)
        (b / "claude").write_text(FAKE_CLAUDE, encoding="utf-8")
        (b / "claude").chmod(0o755)
        log = self.tmp / "claude-call.json"
        return {"PATH": str(b) + os.pathsep + path_with(os.environ.get("PATH", "")), "FAKE_CLAUDE": mode, "FAKE_CLAUDE_LOG": str(log)}, log

    # cc-1 claude 改 voice（白名單內）→ run 0、usage.jsonl 一行（token、美元、輪數、秒數）、旗標、cwd＝拷貝裡的節點；accept 收
    def test_claude_edit(self):
        env, log = self.fake_claude("edit")
        r, cell = self.selfopt("writer/tools/voice", env=env, by="claude", task="請讓口癖照 idx 輪替", history={"runs": [{"total": 3.1}]})
        self.assertEqual(r.returncode, 0, r.stderr + (cell / "run.log").read_text(encoding="utf-8"))
        self.assertRegex(r.stdout, r"^run: writer/tools/voice by claude：3 次腦、180 token、\d+ ms；報告：改好了")
        call = jread(log)
        tree = cell / "tree" / "proto8" / "topdown" / "galtxt-a"
        self.assertEqual(call["cwd"], str(tree / "writer" / "tools" / "voice"))
        argv = call["argv"]
        for flag, val in (("-p", None), ("--output-format", "json"), ("--tools", "Read,Edit,Write,Glob,Grep"), ("--permission-mode", "acceptEdits"),
                          ("--permission-prompts", "none"), ("--max-turns", "30"), ("--max-budget-usd", "1.0"), ("--add-dir", str(tree))):
            self.assertIn(flag, argv)
            if val:
                self.assertEqual(argv[argv.index(flag) + 1], val, flag)
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("Bash", argv[argv.index("--tools") + 1])
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertIn("Read(/%s/data/bench/**)" % tree, settings["permissions"]["deny"])
        self.assertIn("請讓口癖照 idx 輪替", call["prompt"])
        self.assertIn("writer/tools/voice/_entry", call["prompt"])                                   # 白名單寫在 prompt 裡
        self.assertIn('"total": 3.1', call["prompt"])                                                # 先前結果
        usage = jl(self.kit / "usage.jsonl")
        self.assertEqual(len(usage), 1)
        u = usage[0]
        self.assertEqual((u["cost_usd"], u["total_tokens"], u["num_turns"], u["duration_ms"], u["subtree"], u["models"]),
                         (0.0123, 180, 3, 1234, "writer/tools/voice", ["claude-sonnet-fake"]))
        self.assertIsInstance(u["elapsed_ms"], int)
        a = self.accept(cell)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertIn("claude 看過", (self.g / "writer" / "tools" / "voice" / "_entry").read_text(encoding="utf-8"))
        self.assertEqual(jread(cell / "params" / "changed.json")["by"], "claude@selfopt")

    # cc-2 claude 改尺（繞過工具直接寫）→ accept WriteDenied、原樹不變
    def test_claude_cheat(self):
        env, _ = self.fake_claude("cheat")
        before = snapshot(self.g, skip=("optkit",))
        r, cell = self.selfopt("writer/tools/voice", env=env, by="claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.accept(cell)
        self.assertEqual(a.returncode, 1)
        self.assertRegex(a.stderr, r"^accept: WriteDenied data/dims.json")
        self.assertEqual(snapshot(self.g, skip=("optkit",)), before)

    # cc-3 claude 卡住 → 逾時殺掉（BudgetSpent）、usage 照記一行 timed_out
    def test_claude_timeout(self):
        env, _ = self.fake_claude("hang")
        r, cell = self.selfopt("writer/tools/voice", env=env, by="claude", budget={"max_elapsed_ms": 1500})
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^run: BudgetSpent claude（claude: BudgetSpent 超過 1.5 秒")
        u = jl(self.kit / "usage.jsonl")[-1]
        self.assertTrue(u["timed_out"])
        self.assertLess(u["elapsed_ms"], 20000)


if __name__ == "__main__":
    unittest.main()
