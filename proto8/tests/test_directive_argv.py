"""10-20 拍板（proto8/thinking/2026-10-20-ideas.md D1～D8）：$ref 取檔內位置（#/ 與 at）、argv 陣列放指示詞、
argv[0] 帶 / 又 exec 不了＝前面插 aos-exec（入口 argv 陣列、單子、loop／fsm 內嵌單子都一樣）。"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
sys.path.insert(0, str(BIN))
import aos_inst  # noqa: E402


def env_of(extra=None, bin_on_path=True):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    if bin_on_path:   # aos 的程式不動 PATH：D3 靠的是呼叫者放進 PATH 的 aos-exec
        e["PATH"] = str(BIN) + os.pathsep + e.get("PATH", "")
    e.update(extra or {})
    return e


def run(prog, *args, env=None, cwd=None, bin_on_path=True):
    r = subprocess.run([str(BIN / prog), *map(str, args)], capture_output=True, text=True,
                       env=env_of(env, bin_on_path), cwd=cwd)
    return r.returncode, r.stdout, r.stderr


def put(path, text, mode=0o644):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))
    p.chmod(mode)
    return p


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name).resolve()
        self.addCleanup(self._t.cleanup)
        self.ws = self.t / "ws"
        self.ws.mkdir()
        # 共用的 $ref 目標：sub/data.json
        put(self.t / "q" / "sub" / "data.json",
            {"a": {"b": ["echo", "deep"], "w": "word"}, "msg": "hi", "s~/x": "esc"})

    def entry(self, doc, *args, **kw):
        put(self.t / "q" / "_exec.json", doc)
        return run("aos-exec", "--ws", self.ws, self.t / "q", *args, **kw)

    def err(self, r, head):
        rc, _, stderr = r
        self.assertEqual(rc, 1, stderr)
        self.assertEqual(len(stderr.strip().splitlines()), 1, stderr)
        self.assertTrue(stderr.startswith("aos-exec: " + head), stderr)

    # ───── D1、D7：$ref 取檔內位置 ─────

    def test_d1_ref_hash_pointer(self):
        r = self.entry({"argv": ["echo", {"$ref": "sub/data.json#/a/w"}, {"$ref": "sub/data.json#/s~0~1x"}]})
        self.assertEqual(r[:2], (0, "word esc\n"), r[2])

    def test_d1_ref_at(self):
        r = self.entry({"argv": {"$ref": "sub/data.json", "at": "/a/b"}})
        self.assertEqual(r[:2], (0, "deep\n"), r[2])

    def test_d1_ref_whole_file_and_nested_relative(self):
        # 被 $ref 進來的檔裡的 $ref 從那個檔所在的資料夾算
        put(self.t / "q" / "sub" / "outer.json", {"argv": ["echo", {"$ref": "data.json#/msg"}]})
        r = run("aos-inst", put(self.t / "q" / "s.json", {"argv": ["sh", "-c", "exit 0"],
                                                            "stdin": {"$ref": "sub/outer.json", "at": "/argv/0"}}))
        self.assertEqual(r[0], 1)   # stdin "echo" 這個檔不在，證明 at 取到 "echo"
        self.assertIn("echo", r[2])
        r = run("aos-inst", put(self.t / "q" / "w.json", {"$ref": "sub/outer.json"}))
        self.assertEqual(r[:2], (0, "hi\n"), r[2])

    def test_d7_hash_then_at(self):
        r = self.entry({"argv": {"$ref": "sub/data.json#/a", "at": "/b"}})
        self.assertEqual(r[:2], (0, "deep\n"), r[2])
        r = self.entry({"argv": ["echo", {"$ref": "sub/data.json#/a/b", "at": "/1"}]})
        self.assertEqual(r[:2], (0, "deep\n"), r[2])

    def test_ref_errors(self):
        # 真的解不開（讀不到、指不到、繞圈）＝錯；寫法不合的見 test_directive_lenient.py（10-20 D12～D15）
        for doc in ({"argv": ["echo", {"$ref": "sub/nope.json"}]},
                    {"argv": ["echo", {"$ref": "sub/data.json#/zz"}]}):
            self.err(self.entry(doc), "單子跑不起來")
        put(self.t / "q" / "loop1.json", {"x": {"$ref": "loop2.json"}})
        put(self.t / "q" / "loop2.json", {"$ref": "loop1.json#/x"})
        r = self.entry({"argv": ["echo", {"$ref": "loop1.json#/x"}]})
        self.err(r, "單子跑不起來")
        self.assertIn("繞圈", r[2])

    def test_ref_and_env_together_only_ref(self):
        r = self.entry({"argv": ["echo", {"$ref": "sub/data.json#/msg", "$env": "AOS_NOPE_XYZ", "path": "p"}]})
        self.assertEqual(r[:2], (0, "hi\n"), r[2])

    def test_d7_at_appended_pins_whole_object(self):
        # at 空字串＝只取 #/a；值是物件、放在 argv 裡＝單子的 argv 不是字串陣列
        self.err(self.entry({"argv": ["echo", {"$ref": "sub/data.json#/a", "at": ""}]}), "單子跑不起來")

    # ───── D2、D8：argv 陣列放指示詞 ─────

    def test_d2_argv_array_env(self):
        r = self.entry(["sh", "-c", 'echo "$1"', "sh", {"$env": "AOS_CD", "$path": "x"}])
        self.assertEqual(r[:2], (0, "%s/x\n" % (self.t / "q")), r[2])
        r = self.entry({"_exec": ["echo", {"$env": "AOS_WS"}]})
        self.assertEqual(r[:2], (0, "%s\n" % self.ws), r[2])

    def test_d8_argv_array_ref(self):
        r = self.entry([{"$ref": "sub/data.json#/a/b/0"}, {"$ref": "sub/data.json", "at": "/msg"}], "tail")
        self.assertEqual(r[:2], (0, "hi tail\n"), r[2])

    def test_argv_array_directive_errors(self):
        self.err(self.entry(["echo", {"$env": "AOS_NOPE_XYZ"}]), "入口壞")
        self.err(self.entry(["echo", {"$ref": "sub/data.json#/a"}]), "入口壞")   # 解出來不是字串
        self.err(self.entry(["echo", {"$ref": "sub/nope.json"}]), "入口壞")
        self.err(self.entry(["echo", {"k": 1}]), "入口壞")
        self.err(self.entry(["echo", 1]), "入口壞")

    # ───── D3、D4、D5：argv[0] 帶 / 又 exec 不了＝aos-exec ─────

    def tools(self):
        put(self.t / "q" / "tools" / "stamp" / "_exec",
            '#!/bin/sh\necho "stamp ws=$AOS_WS cf=$AOS_CF arg=$1"\n', 0o755)
        put(self.t / "q" / "tools" / "j.json", ["sh", "-c", 'echo "json cf=$AOS_CF"'])
        put(self.t / "q" / "tools" / "cfg.json", {"t": {"u": ["echo", "ptr"]}})
        put(self.t / "q" / "tools" / "x.sh", '#!/bin/sh\necho "x cf=$AOS_CF"\n', 0o755)

    def test_d3_argv_array_dir_json_pointer(self):
        self.tools()
        stamp = self.t / "q" / "tools" / "stamp" / "_exec"
        r = self.entry(["tools/stamp"])
        self.assertEqual(r[:2], (0, "stamp ws=%s cf=%s arg=\n" % (self.ws, stamp)), r[2])
        r = self.entry(["tools/j.json"])                         # 沒 +x 的 JSON 檔
        self.assertEqual(r[:2], (0, "json cf=%s\n" % (self.t / "q" / "tools" / "j.json")), r[2])
        r = self.entry(["tools/j"])                              # 不在 → aos-exec 補找 .json
        self.assertEqual(r[0], 0, r[2])
        r = self.entry(["tools/cfg.json#/t/u"])                  # 帶 #/
        self.assertEqual(r[:2], (0, "ptr\n"), r[2])

    def test_d3_x_file_still_direct(self):
        self.tools()
        r = self.entry(["tools/x.sh"])          # +x 檔照舊直接 exec：AOS_CF 還是外層的入口
        self.assertEqual(r[:2], (0, "x cf=%s\n" % (self.t / "q" / "_exec.json")), r[2])

    def test_d5_second_element_is_arg(self):
        # 10-21 起 aos-exec 的工作區只由 --ws 給：["tools/stamp", "a"] 的 a 是 args，不再是 WS
        self.tools()
        other = self.t / "other"; other.mkdir()
        r = self.entry(["tools/stamp", "a"])
        self.assertIn("ws=%s " % self.ws, r[1], r[2])
        self.assertTrue(r[1].endswith("arg=a\n"), r[1])
        r = self.entry(["tools/stamp", str(other)])          # 舊寫法的 WS 位置＝普通的 args
        self.assertIn("ws=%s " % self.ws, r[1], r[2])
        self.assertTrue(r[1].endswith("arg=%s\n" % other), r[1])
        # 要換工作區：argv 裡自己寫 aos-exec --ws
        r = self.entry(["aos-exec", "--ws", str(other), "tools/stamp", "b"])
        self.assertIn("ws=%s " % other, r[1], r[2])
        self.assertTrue(r[1].endswith("arg=b\n"), r[1])
        # args 接在後面：["tools/stamp"] + 呼叫時的 args → 原樣接上
        r = self.entry(["tools/stamp"], "c")
        self.assertTrue(r[1].endswith("arg=c\n"), r[1])

    def test_d4_no_slash_is_path_only(self):
        self.tools()
        put(self.t / "q" / "stampdir" / "_exec", "#!/bin/sh\necho no\n", 0o755)
        self.err(self.entry(["stampdir"]), "起不來")             # 沒 / ＝照 PATH 找，不看 cwd 的資料夾
        self.assertEqual(self.entry({"argv": ["stampdir"]})[0], 1)

    def test_d3_needs_aos_exec_on_path(self):
        self.tools()
        r = self.entry({"argv": ["tools/stamp"]}, bin_on_path=False)
        self.assertEqual(r[0], 1)
        self.assertIn("找不到要跑的程式 aos-exec", r[2])

    def test_d3_inst(self):
        self.tools()
        stamp = self.t / "q" / "tools" / "stamp" / "_exec"
        r = self.entry({"argv": ["tools/stamp", "a"]})          # aos-exec 的單子入口
        self.assertEqual(r[:2], (0, "stamp ws=%s cf=%s arg=a\n" % (self.ws, stamp)), r[2])
        s = put(self.t / "q" / "s.json", {"argv": ["./tools/cfg.json#/t/u"], "cwd": str(self.t / "q")})
        self.assertEqual(run("aos-inst", s)[:2], (0, "ptr\n"))         # aos-inst 命令列
        res = aos_inst.parse({"argv": ["tools/stamp"]})
        self.assertEqual(aos_inst.argv0(res["argv"], str(self.t / "q")), ["aos-exec", "tools/stamp"])
        self.assertEqual(aos_inst.argv0(["tools/x.sh"], str(self.t / "q")), ["tools/x.sh"])
        self.assertEqual(aos_inst.argv0(["x.sh"], str(self.t / "q" / "tools")), ["x.sh"])

    def test_d3_loop_and_fsm_inline(self):
        self.tools()
        q = self.t / "q"
        stack = self.t / "st"; stack.mkdir()
        # 10-21：loop 的內嵌單子寫 檔#/body；run 的相對路徑照 cwd 算（L4），單子裡的 $ref 由 aos-exec 從 loop.json 的資料夾算
        loop = put(q / "loop.json", {"run": "q/loop.json#/body", "max": 1,
                                     "body": {"argv": ["tools/stamp", "L"], "cwd": str(q),
                                              "stdout": {"$env": "AOS_STACK", "$path": "out"},
                                              "envs": {"MSG": {"$ref": "sub/data.json#/msg"}}}})
        r = run("aos-loop", loop, cwd=self.t, env={"AOS_WS": str(self.ws), "AOS_STACK": str(stack)})
        self.assertEqual(r[0], 0, r[2])
        self.assertTrue((stack / "out").read_text().endswith("arg=L\n"))
        # fsm（10-21 plan F2）：格的內嵌單子寫 檔#/states/<名>/body；val 的相對路徑照 cwd 算，
        # 單子裡的 $ref 由 aos-exec 從 fsm.json 所在的資料夾算（cwd 在別處）
        fsm = put(q / "fsm.json", {"start": "a", "states": {"a": {
            "val": "q/fsm.json#/states/a/body",
            "body": {"argv": [{"$ref": "sub/data.json", "at": "/a/b/0"}, {"$ref": "sub/data.json#/msg"}],
                     "stdout": {"$env": "AOS_STACK", "$path": "fout"}}, "next": "a"}}})
        r = run("aos-fsm", fsm, cwd=self.t, env={"AOS_STACK": str(stack)})
        self.assertEqual(r[0], 0, r[2])
        self.assertEqual((stack / "fout").read_text(), "hi\n")
        fsm2 = put(q / "fsm2.json", {"start": "a", "states": {"a": {
            "val": "q/fsm2.json#/states/a/body",
            "body": {"argv": ["tools/cfg.json#/t/u"], "cwd": str(q),
                     "stdout": {"$env": "AOS_STACK", "$path": "fout2"}}, "next": "a"}}})
        r = run("aos-fsm", fsm2, cwd=self.t, env={"AOS_STACK": str(stack)})
        self.assertEqual(((stack / "fout2").read_text(), r[0]), ("ptr\n", 0), r[2])


if __name__ == "__main__":
    unittest.main()
