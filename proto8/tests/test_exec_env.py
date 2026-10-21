"""aos-exec 讀 AOS_CD 裡的 .env（10-21 ideas § 4；N-59、N-58、N-60）。
步驟：cd 到 AOS_CD → 設好 AOS_* → 讀 .env → 解指示詞 → 解語法糖 → 開跑；優先順序 旗標 ＞ .env ＞ 原本的環境變數 ＞ 預設；
字串轉向＝交給下一層、全新的一次 aos-exec（旗標不帶、args 照接、下一層讀它自己的 .env）。"""
import os, tempfile, unittest
from pathlib import Path

from test_exec_rules import put, prog, run


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = self._t.name
        self.addCleanup(self._t.cleanup)

    def test_basic_lines(self):
        d = prog(self.t, "p", 'printf "%s|%s|%s|%s|%s|%s\\n" "$A" "$B" "$C" "$D" "${E-unset}" "$F"\n')
        put(Path(d, ".env"), "# 註解\n\n   # 縮排的註解\nA=1\r\n  B=x=y\nC=$HOME 不是展開 $\nD=\nF=a  # 不是註解\nA=2\n")
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "2|x=y|$HOME 不是展開 $||unset|a  # 不是註解\n"))

    def test_no_env_file(self):
        d = prog(self.t, "p", 'echo "${A-unset}"\n')
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "unset\n"))

    def test_expand_in_order_and_path(self):
        # .env 設的 PATH 讓 argv 陣列的 argv[0] 找得到 bin/ 裡的程式；${AOS_CD} 是 aos-exec 剛算好的值
        q = Path(self.t, "q")
        put(q / "bin" / "hello", "#!/bin/sh\necho \"hello $X $Y\"\n", 0o755)
        put(q / ".env", "PATH=${AOS_CD}/bin:${PATH}\nX=1\nY=${X}2${X}\n")
        put(q / "_exec.json", ["hello"])
        self.assertEqual(run("--ws", self.t, str(q))[:2], (0, "hello 1 121\n"))
        # 沒有 .env 時同一個入口找不到 hello
        os.remove(q / ".env")
        self.assertEqual(run("--ws", self.t, str(q))[2], "起不來")

    def test_priority_flag_env_outer(self):
        d = prog(self.t, "p", 'echo "$AOS_WS"\n')
        a, b, c = (Path(self.t, n) for n in "abc")
        for x in (a, b, c):
            x.mkdir()
        put(Path(d, ".env"), "AOS_WS=%s\n" % b)
        self.assertEqual(run("--ws", str(a), d, env={"AOS_WS": str(c)})[1], "%s\n" % a.resolve())   # 旗標贏
        self.assertEqual(run(d, env={"AOS_WS": str(c)})[1], "%s\n" % b)                            # .env 贏外面
        os.remove(Path(d, ".env"))
        self.assertEqual(run(d, env={"AOS_WS": str(c)})[1], "%s\n" % c)                            # 外面贏預設

    def test_env_can_set_aos_vars(self):
        # 什麼都能設、不擋；cd 已經做了，改 AOS_CD 不會再 cd
        d = prog(self.t, "p", 'echo "$AOS_CF|$AOS_CD|$AOS_STACK|$AOS_ENTRY|$(pwd -P)"\n')
        put(Path(d, ".env"), "AOS_CF=cf\nAOS_CD=/nowhere\nAOS_STACK=st/\nAOS_ENTRY=other\n")
        real = str(Path(d).resolve())
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "cf|/nowhere|st/|other|%s\n" % real))

    def test_redirect_two_layers(self):
        # r 的入口是字串轉向到 t：兩層 .env 都讀、後讀的贏；--ws 只在第一層有效（轉向＝全新一次、旗標不帶）；args 照接
        a, b, c = (Path(self.t, n) for n in "abc")
        for x in (a, b, c):
            x.mkdir()
        r = Path(self.t, "r")
        put(r / "_exec.json", '"../t"')
        put(r / ".env", "A=r\nB=r\nAOS_WS=%s\n" % c)
        t = Path(prog(self.t, "t", 'echo "$A|$B|$C|$AOS_WS|$*"\n'))
        put(t / ".env", "B=t\nC=${A}+t\n")
        self.assertEqual(run("--ws", str(a), str(r), "x", "y")[:2], (0, "r|t|r+t|%s|x y\n" % a.resolve()))
        # 第二層的 .env 設 AOS_WS：沒有旗標可以蓋它，它贏（旗標不帶過去）
        put(t / ".env", "AOS_WS=%s\n" % b)
        self.assertEqual(run("--ws", str(a), str(r))[1], "r|r||%s|\n" % b)

    def test_unset_reference_is_error(self):
        d = prog(self.t, "p", "echo ran\n")
        put(Path(d, ".env"), "A=1\nB=x${NOPE_NOT_SET}y\n")
        rc, out, err, stderr = run("--ws", self.t, d)
        self.assertEqual((rc, out, err), (1, "", ".env 壞"))
        self.assertIn("第 2 行", stderr)
        self.assertIn(str(Path(d, ".env").resolve()), stderr)

    def test_bad_lines_never_print_value(self):
        secret = "sk-SECRET1234"
        d = prog(self.t, "p", "echo ran\n")
        for n, text in ((1, secret), (2, "OK=1\n1BAD=%s" % secret), (1, "X=%s${oops" % secret),
                        (1, "X=%s${1x}" % secret), (1, "%s-NAME=v" % secret), (1, "X=%s${NOPE}" % secret)):
            put(Path(d, ".env"), text + "\n")
            rc, out, err, stderr = run("--ws", self.t, d)
            self.assertEqual((rc, out, err), (1, "", ".env 壞"), text)
            self.assertIn("第 %d 行" % n, stderr)
            self.assertNotIn("SECRET", stderr, text)

    def test_unreadable(self):
        d = prog(self.t, "p", "echo ran\n")
        e = put(Path(d, ".env"), "SECRET=sk-SECRET\n", 0o000)
        if os.access(e, os.R_OK):
            self.skipTest("以 root 跑，chmod 000 也讀得到")
        rc, out, err, stderr = run("--ws", self.t, d)
        self.assertEqual((rc, out, err), (1, "", ".env 讀不到"))
        self.assertNotIn("SECRET", stderr)

    def test_env_is_a_directory(self):
        d = prog(self.t, "p", "echo ran\n")
        Path(d, ".env").mkdir()
        self.assertEqual(run("--ws", self.t, d)[2], ".env 讀不到")

    def test_directive_sees_env_values(self):
        # $env 指示詞（argv 陣列與單子）讀得到 .env 設的值
        q = Path(self.t, "q")
        put(q / ".env", "FOO=from-dotenv\n")
        put(q / "_exec.json", ["echo", {"$env": "FOO", "$prefix": "argv:"}])
        self.assertEqual(run("--ws", self.t, str(q))[:2], (0, "argv:from-dotenv\n"))
        put(q / "_exec.json", {"argv": ["echo", {"$env": "FOO", "$prefix": "inst:"}]})
        self.assertEqual(run("--ws", self.t, str(q))[:2], (0, "inst:from-dotenv\n"))

    def test_inserted_aos_exec_inherits_and_reads_own(self):
        # argv[0] 帶 / 又 exec 不了＝插 aos-exec：子程式繼承含 .env 的環境，並讀它自己那裡的 .env
        q = Path(self.t, "q")
        put(q / ".env", "A=parent\nB=parent\n")
        put(q / "_exec.json", ["tools/t", "z"])
        tool = Path(prog(q / "tools", "t", 'echo "$A|$B|$*"\n'))
        put(tool / ".env", "B=child\n")
        self.assertEqual(run("--ws", self.t, str(q))[:2], (0, "parent|child|z\n"))


if __name__ == "__main__":
    unittest.main()
