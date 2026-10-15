"""proto8/lib 的自動測試：inst（aos_inst）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。
"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest

from helpers import INST, Tmp
import aos_inst  # noqa: E402


class Inst(Tmp):
    def run_inst(self, name, sh, **keys):
        """寫 NAME/inst.json、run() 一次，回結果的 code（子程式的碼只在這份結果裡，N-30）。"""
        return aos_inst.run(self.inst(name, sh, **keys))["code"]

    def cli(self, *args, input=None):
        return subprocess.run([sys.executable, INST, *args], capture_output=True, text=True, cwd=self.tmp, input=input)

    def err(self, r):
        """命令列 stderr 吐的錯誤代號（N-12：一份 {"error": {"code", "msg"}}）。"""
        return json.loads(r.stderr.splitlines()[-1])["error"]["code"]

    def test_find(self):
        d = self.inst("a", "true")
        self.assertEqual(aos_inst.find(d), os.path.realpath(d + "/inst.json"))
        self.write("b/.aos/inst.json", {"argv": ["true"]})
        self.write("b/inst.json", {"argv": ["true"]})
        self.assertEqual(aos_inst.find(self.p("b")), os.path.realpath(self.p("b/.aos/inst.json")))
        os.makedirs(self.p("empty"))
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.find(self.p("empty"))
        self.assertEqual(c.exception.code, "NotFound")

    def test_find_follows_aos_dirname(self):
        # 資料夾 TARGET 先找 $AOS_DIRNAME/inst.json（沒設＝.aos；空字串＝資料夾本身；N-35）
        self.write("b/.aos/inst.json", {"argv": ["true"]})
        self.write("b/meta/inst.json", {"argv": ["true"]})
        self.write("b/inst.json", {"argv": ["true"]})
        old = os.environ.pop("AOS_DIRNAME", None)
        self.addCleanup(lambda: os.environ.__setitem__("AOS_DIRNAME", old) if old is not None
                        else os.environ.pop("AOS_DIRNAME", None))
        for name, want in (("meta", "b/meta/inst.json"), ("", "b/inst.json"), ("nope", "b/inst.json")):
            os.environ["AOS_DIRNAME"] = name
            self.assertEqual(aos_inst.find(self.p("b")), os.path.realpath(self.p(want)), name)
        os.environ["AOS_DIRNAME"] = "a/b"
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.find(self.p("b"))
        self.assertEqual(c.exception.code, "DirnameBad")

    def test_child_code_in_result(self):
        self.assertEqual(self.run_inst("r", "exit 7"), 7)
        self.assertEqual(self.run_inst("z", "true"), 0)

    def test_streams(self):
        self.assertEqual(self.run_inst("a", "echo hi; echo err >&2; exit 3", stdout="a.out", stderr_merge=True), 3)
        self.assertEqual(self.read("a.out"), "hi\nerr\n")
        for sh in ("echo 1", "echo 2"):
            self.run_inst("b", sh, stdout="b.out", stdout_append=True)
        self.assertEqual(self.read("b.out"), "1\n2\n")
        self.run_inst("c", "echo deep", stdout="d/e/c.out", stdout_mkdir=True)
        self.assertEqual(self.read("d/e/c.out"), "deep\n")

    def test_dev_streams_inherit(self):
        # 要接呼叫者的串流就寫 /dev/stdin、/dev/stdout、/dev/stderr（沒有 *_inherit 布林了）
        r = self.cli("--stdin", "/dev/stdin", "--stdout", "/dev/stdout", "--stderr", "/dev/stderr", "--",
                     "sh", "-c", "read x; echo got $x; echo e >&2", input="hi\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "got hi")
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["code"], 0)
        self.assertEqual(r.stderr, "e\n")

    def test_timeout_and_grace_in_json(self):
        self.assertEqual(self.run_inst("t", "sleep 5", timeout_ms=100), 143)
        t0 = time.monotonic()
        self.assertEqual(self.run_inst("k", "trap '' TERM; sleep 5", timeout_ms=100, grace_ms=200), 137)
        self.assertLess(time.monotonic() - t0, 2)

    def test_timeout_grace_types(self):
        for keys in ({"timeout_ms": 0}, {"timeout_ms": "5s"}, {"grace_ms": -1}, {"grace_ms": True}):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.parse(dict({"argv": ["true"]}, **keys), self.tmp)
            self.assertEqual(c.exception.code, "FieldType")

    def test_errors(self):
        for keys, code in (({"argv": []}, "FieldType"), ({"argv": ["/no/such/prog"]}, "CommandNotFound"),
                           ({"argv": ["true"], "stderr": "x", "stderr_merge": True}, "Conflict"),
                           ({"argv": ["true"], "cwd": "/no/such/dir"}, "CwdMissing")):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.run(self.write("e.json", keys))
            self.assertEqual(c.exception.code, code)

    def test_error_names_file(self):
        self.write("e.json", {"argv": ["x", {"$env": "AOS_TEST_NOPE"}]})
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.load(self.p("e.json"))
        self.assertEqual(c.exception.code, "DirectiveBad")
        self.assertIn(os.path.realpath(self.p("e.json")) + ":/argv/1", c.exception.msg)

    def test_cli(self):
        # 退出碼只說 aos_inst 自己：子程式回 5 照樣 0，5 在結果裡
        r = self.cli(self.inst("c", "exit 5"))
        self.assertEqual((r.returncode, json.loads(r.stdout)["code"]), (0, 5))
        self.write("x.json", "#!/bin/sh\n")
        self.write("nf.json", {"argv": ["/no/such/prog"]})
        self.write("nx.json", {"argv": [self.p("x.json")]})
        for target, code, err in (("nope.json", 1, "ReadFailed"), ("nf.json", 1, "CommandNotFound"),
                                  ("nx.json", 1, "CommandNotExecutable")):     # 一律 1，看 code 分
            r = self.cli(self.p(target))
            self.assertEqual((r.returncode, self.err(r)), (code, err))

    def test_cli_forwards_signal_then_grace(self):
        # 收到 SIGTERM 轉給子程式；子程式不理就過 grace_ms SIGKILL；aos_inst 自己照樣 0
        d = self.inst("s", "trap '' TERM; echo go > s.go; sleep 30", grace_ms=200)
        proc = subprocess.Popen([sys.executable, INST, d], cwd=self.tmp, stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s.go")))
        t0 = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual(json.loads(out)["code"], 137)

    def test_cli_stdout_result(self):
        r = self.cli(self.inst("o", "exit 4", timeout_ms=5000))
        res = json.loads(r.stdout)
        self.assertEqual(set(res), {"id", "code", "signal", "timed_out", "pid", "ms"})
        self.assertEqual((res["code"], res["signal"], res["timed_out"], res["id"]),
                         (4, None, False, os.path.realpath(self.p("o/inst.json"))))
        res = aos_inst.run({"argv": ["sleep", "5"], "timeout_ms": 100, "id": "me"})     # run(dict)
        self.assertEqual((res["code"], res["signal"], res["timed_out"], res["id"]), (143, 15, True, "me"))

    def test_cli_stdin_flags_dashdash(self):
        # stdin 多份＝InputExtra 錯（退非 0、不跑）；一份照跑；旗標蓋過；-- 蓋過 argv
        r = self.cli("-", input='{"argv": ["sh", "-c", "echo x > s.out"]} {"x": 1}')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stderr)["error"]["code"], "InputExtra")
        self.assertFalse(os.path.exists(self.p("s.out")))
        r = self.cli("--timeout-ms", "5000", "-", input='{"argv": ["sh", "-c", "exit 2"]}')
        self.assertEqual((r.returncode, r.stderr, json.loads(r.stdout)["code"]), (0, "", 2))
        self.assertIsNone(json.loads(r.stdout)["id"])                              # stdin 來又沒寫 id＝null
        r = self.cli("--cwd", self.tmp, "--stdout", "d.out", "--", "echo", "hi")
        self.assertEqual((r.returncode, self.read("d.out")), (0, "hi\n"), r.stderr)
        r = self.cli("--nope", "1", "--", "true")
        self.assertEqual((r.returncode, self.err(r)), (1, "FlagUnknown"))

    def node(self, name="node.json"):
        """一份 JSON 放好幾格：clock 是 inst（argv 用 $ref 指旁邊的小檔）、x 不是物件。"""
        self.write("shared.json", {"sh": "echo hi >> c.out"})
        return self.write(name, {"clock": {"argv": ["sh", "-c", {"$ref": self.p("shared.json") + "#/sh"}], "cwd": self.tmp},
                                 "x": 5})

    def test_target_pointer(self):
        path = self.node()
        real = os.path.realpath(path)
        self.assertEqual(aos_inst.run(path + "#/clock")["code"], 0)
        self.assertEqual(self.read("c.out"), "hi\n")
        self.assertEqual(aos_inst.find(path + "#/clock"), real + "#/clock")
        for whole in (path, path + "#", path + "#/"):                  # 沒 pointer 或 #/ ＝純 realpath
            self.assertEqual(aos_inst.find(whole), real)
        for target, code in ((path + "#/x", "FieldType"), (path + "#/nope", "PointerBad"),
                             (path + "#clock", "PointerBad"), (path + "#/", "FieldType")):
            with self.subTest(target=target), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.run(target)
            self.assertEqual(c.exception.code, code)
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.run(path + "#/x")
        self.assertIn(real + "#/x", c.exception.msg)                   # 錯誤訊息帶路徑
        r = self.cli(path + "#/clock")
        self.assertEqual((r.returncode, self.read("c.out")), (0, "hi\nhi\n"), r.stderr)

    def test_target_pointer_dir_and_first_hash(self):
        # 資料夾：先照現有規矩找 inst.json 再套位置
        self.node("d/inst.json")
        self.assertEqual(aos_inst.find(self.p("d") + "#/clock"), os.path.realpath(self.p("d/inst.json")) + "#/clock")
        self.assertEqual(aos_inst.run(self.p("d") + "#/clock")["id"], os.path.realpath(self.p("d/inst.json")) + "#/clock")
        self.assertEqual(self.read("c.out"), "hi\n")
        # 檔名含 # 不支援：遇第一個 # 就切，後面 b.json 當位置、不是 / 開頭
        self.write("a#b.json", {"argv": ["true"]})
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.run(self.p("a#b.json"))
        self.assertEqual(c.exception.code, "PointerBad")


if __name__ == "__main__":
    unittest.main()
