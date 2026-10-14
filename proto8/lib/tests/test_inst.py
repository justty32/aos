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
        """寫 NAME/inst.json、run() 一次，回 exit 檔的內容（結果 dict 的 code 要跟 exit 檔一樣）。"""
        res = aos_inst.run(self.inst(name, sh, exit=name + ".exit", **keys))
        self.assertEqual("%d\n" % res["code"], self.read(name + ".exit").splitlines()[-1] + "\n")
        return self.read(name + ".exit")

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

    def test_child_code_only_in_exit_file(self):
        self.assertEqual(self.run_inst("r", "exit 7"), "7\n")
        self.assertEqual(aos_inst.run(self.inst("n", "exit 7"))["code"], 7)      # 沒寫 exit：照樣正常，碼在結果裡

    def test_exit_and_streams(self):
        self.assertEqual(self.run_inst("a", "echo hi; echo err >&2; exit 3", stdout="a.out", stderr_merge=True), "3\n")
        self.assertEqual(self.read("a.out"), "hi\nerr\n")

    def test_exit_append_and_read_exit(self):
        for sh in ("exit 1", "exit 2"):
            self.run_inst("a", sh, exit_append=True)
        self.assertEqual(self.read("a.exit"), "1\n2\n")
        self.assertEqual(aos_inst.read_exit(self.p("a.exit")), 2)
        self.assertIsNone(aos_inst.read_exit(self.p("nope.exit")))

    def test_timeout_and_grace_in_json(self):
        self.assertEqual(self.run_inst("t", "sleep 5", timeout_ms=100), "143\n")
        t0 = time.monotonic()
        self.assertEqual(self.run_inst("k", "trap '' TERM; sleep 5", timeout_ms=100, grace_ms=200), "137\n")
        self.assertLess(time.monotonic() - t0, 2)

    def test_timeout_grace_types(self):
        for keys in ({"timeout_ms": 0}, {"timeout_ms": "5s"}, {"grace_ms": -1}, {"grace_ms": True}):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.parse(dict({"argv": ["true"]}, **keys), self.tmp)
            self.assertEqual(c.exception.code, "FieldType")

    def test_errors(self):
        for keys, code in (({"argv": []}, "FieldType"), ({"argv": ["/no/such/prog"]}, "CommandNotFound"),
                           ({"argv": ["true"], "stdout": "x", "stdout_inherit": True}, "Conflict"),
                           ({"argv": ["true"], "cwd": "/no/such/dir"}, "CwdMissing")):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.run(self.write("e.json", keys))
            self.assertEqual(c.exception.code, code)

    def test_error_names_file(self):
        self.write("e.json", {"argv": ["x", {"$env": "AOS_TEST_NOPE"}]})
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.load(self.p("e.json"))
        self.assertIn(os.path.realpath(self.p("e.json")) + ":/argv/1", c.exception.msg)

    def test_cli(self):
        # 退出碼只說 aos_inst 自己：子程式回 5 照樣 0，5 在 exit 檔
        d = self.inst("c", "exit 5", exit="c.exit")
        self.assertEqual((self.cli(d).returncode, self.read("c.exit")), (0, "5\n"))
        self.write("x.json", "#!/bin/sh\n")
        self.write("nf.json", {"argv": ["/no/such/prog"]})
        self.write("nx.json", {"argv": [self.p("x.json")]})
        for target, code, err in (("nope.json", 125, "ReadFailed"), ("nf.json", 127, "CommandNotFound"),
                                  ("nx.json", 126, "CommandNotExecutable")):
            r = self.cli(self.p(target))
            self.assertEqual((r.returncode, self.err(r)), (code, err))

    def test_cli_forwards_signal_then_grace(self):
        # 收到 SIGTERM 轉給子程式；子程式不理就過 grace_ms SIGKILL；aos_inst 自己照樣 0
        d = self.inst("s", "trap '' TERM; echo go > s.go; sleep 30", exit="s.exit", grace_ms=200)
        proc = subprocess.Popen([sys.executable, INST, d], cwd=self.tmp, stdout=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s.go")))
        t0 = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 0)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual(self.read("s.exit"), "137\n")

    def test_cli_stdout_result(self):
        # stdout＝一份結果；exit 檔照寫
        r = self.cli(self.inst("o", "exit 4", exit="o.exit", timeout_ms=5000))
        res = json.loads(r.stdout)
        self.assertEqual(set(res), {"id", "code", "signal", "timed_out", "pid", "ms", "exit_file"})
        self.assertEqual((res["code"], res["signal"], res["timed_out"], res["exit_file"], res["id"]),
                         (4, None, False, self.p("o.exit"), os.path.realpath(self.p("o/inst.json"))))
        self.assertEqual(self.read("o.exit"), "4\n")
        res = aos_inst.run({"argv": ["sleep", "5"], "timeout_ms": 100, "id": "me"})     # run(dict)
        self.assertEqual((res["code"], res["signal"], res["timed_out"], res["id"]), (143, 15, True, "me"))

    def test_cli_stdin_flags_dashdash(self):
        # stdin 只看第一份、其餘警告；旗標蓋過；-- 蓋過 argv
        r = self.cli("--exit", "s.exit", "-", input='{"argv": ["sh", "-c", "exit 2"], "exit": "no.exit"} {"x": 1}')
        self.assertEqual((r.returncode, self.read("s.exit")), (0, "2\n"), r.stderr)
        self.assertEqual(json.loads(r.stderr)["warning"]["code"], "ExtraInput")
        self.assertIsNone(json.loads(r.stdout)["id"])                              # stdin 來又沒寫 id＝null
        r = self.cli("--cwd", self.tmp, "--stdout", "d.out", "--", "echo", "hi")
        self.assertEqual((r.returncode, self.read("d.out")), (0, "hi\n"), r.stderr)
        r = self.cli("-", input='{"argv": ["true"], "stdin_inherit": true}')          # D-5
        self.assertEqual((r.returncode, self.err(r)), (125, "Conflict"))
        r = self.cli("--nope", "1", "--", "true")
        self.assertEqual((r.returncode, self.err(r)), (125, "UnknownFlag"))

    def node(self, name="node.json"):
        """一份 JSON 放好幾格：clock 是 inst（argv 用 ../ 摸旁邊的 shared）、x 不是物件。"""
        return self.write(name, {"shared": {"sh": "echo hi >> c.out"},
                                 "clock": {"argv": ["sh", "-c", {"$ref": "#../../../shared/sh"}], "cwd": self.tmp,
                                           "exit": "c.exit", "exit_append": True},
                                 "x": 5})

    def test_target_pointer(self):
        path = self.node()
        real = os.path.realpath(path)
        self.assertEqual(aos_inst.run(path + "#/clock")["code"], 0)   # 視窗：$ref 的 ../ 照整份檔算
        self.assertEqual((self.read("c.out"), self.read("c.exit")), ("hi\n", "0\n"))
        self.assertEqual(aos_inst.find(path + "#/clock"), real + "#/clock")
        self.assertEqual(aos_inst.find(path + "#/clock/../clock"), real + "#/clock")
        for whole in (path, path + "#", path + "#/"):                  # 沒 pointer 或 #/ ＝純 realpath
            self.assertEqual(aos_inst.find(whole), real)
        for target, code in ((path + "#/x", "FieldType"), (path + "#/nope", "ReferencePointerInvalid"),
                             (path + "#clock", "ReferencePointerInvalid"), (path + "#/", "FieldType")):
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
        self.assertEqual(c.exception.code, "ReferencePointerInvalid")


if __name__ == "__main__":
    unittest.main()
