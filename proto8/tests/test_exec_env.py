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
        # 什麼都能設、不擋；cd 已經做了，改 AOS_CD 不會再 cd；.env 設的 AOS_CF／AOS_CD 挑完入口也不蓋掉
        # （10-21 晚：AOS_ENTRY 在讀完 .env 後才用來挑入口，所以這裡跑的是 other）
        d = prog(self.t, "p", 'echo "$AOS_CF|$AOS_CD|$AOS_STACK|$AOS_ENTRY|$(pwd -P)"\n', entry="other")
        put(Path(d, ".env"), "AOS_CF=cf\nAOS_CD=/nowhere\nAOS_STACK=st/\nAOS_ENTRY=other\n")
        real = str(Path(d).resolve())
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "cf|/nowhere|st/|other|%s\n" % real))

    # ---- 10-21 晚：AOS_ENTRY 的順序（ideas 10-21 § 5）：cd 進去、讀 .env，再照 $AOS_ENTRY 挑入口 ----

    def test_dir_env_sets_entry(self):
        d = prog(self.t, "p", "echo default\n")
        put(Path(d, "main"), '#!/bin/sh\necho "main|$AOS_CF|$AOS_ENTRY"\n', 0o755)
        put(Path(d, ".env"), "AOS_ENTRY=main\n")
        real = Path(d).resolve()
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "main|%s/main|main\n" % real))
        # 補找 $AOS_ENTRY.json 也用 .env 的值
        os.remove(Path(d, "main"))
        put(Path(d, "main.json"), ["echo", "main-json"])
        self.assertEqual(run("--ws", self.t, d)[:2], (0, "main-json\n"))
        # .env 指到不存在的入口＝入口不存在（不退回 _exec）
        os.remove(Path(d, "main.json"))
        self.assertEqual(run("--ws", self.t, d)[2], "入口不存在")

    def test_json_object_env_sets_entry_key(self):
        q = Path(self.t, "q")
        put(q / "cfg.json", {"_exec": ["echo", "default"], "alt": ["echo", "alt"], "in": {"alt": ["echo", "in-alt"]}})
        put(q / ".env", "AOS_ENTRY=alt\n")
        self.assertEqual(run("--ws", self.t, str(q / "cfg.json"))[:2], (0, "alt\n"))
        self.assertEqual(run("--ws", self.t, str(q / "cfg"))[:2], (0, "alt\n"))            # 補 .json
        self.assertEqual(run("--ws", self.t, str(q / "cfg.json") + "#/in")[:2], (0, "in-alt\n"))   # 檔#/指標
        # 外面設的 AOS_ENTRY 被 .env 蓋掉
        self.assertEqual(run("--ws", self.t, str(q / "cfg.json"), env={"AOS_ENTRY": "_exec"})[:2], (0, "alt\n"))

    def test_entry_in_subdir_reads_env_along_the_way(self):
        # AOS_ENTRY＝sub/run：沿路的資料夾（p、p/sub）的 .env 由外到內都讀（ideas 10-21 § 6 的 a）；AOS_CF／AOS_CD／cwd＝實際的檔
        d = Path(self.t, "p")
        put(d / ".env", "AOS_ENTRY=sub/run\nA=top\nB=top\n")
        put(d / "sub" / "run", '#!/bin/sh\necho "$A|$B|$AOS_CF|$AOS_CD|$(pwd -P)|$AOS_CO"\n', 0o755)
        put(d / "sub" / ".env", "B=sub-${A}\n")
        rs = (d / "sub").resolve()
        self.assertEqual(run("--ws", self.t, str(d))[:2], (0, "top|sub-top|%s/run|%s|%s|\n" % (rs, rs, rs)))

    def test_dir_picks_dir_all_the_way_down(self):
        # 挑到的是資料夾＝走進去、讀它的 .env、照當下的 AOS_ENTRY 再挑，一路往下
        d = Path(self.t, "p")
        put(d / ".env", "A=p\n")
        put(d / "_exec" / ".env", "B=mid\nAOS_ENTRY=go\n")
        put(d / "_exec" / "go" / ".env", "C=${A}${B}\n")
        put(d / "_exec" / "go" / "go", '#!/bin/sh\necho "$A|$B|$C|$AOS_CD|$(pwd -P)"\n', 0o755)
        rg = (d / "_exec" / "go").resolve()
        self.assertEqual(run("--ws", self.t, str(d))[:2], (0, "p|mid|pmid|%s|%s\n" % (rg, rg)))
        # 走回走過的資料夾＝入口壞（AOS_ENTRY＝. 的情形）
        put(d / ".env", "AOS_ENTRY=.\n")
        self.assertEqual(run("--ws", self.t, str(d))[2], "入口壞")

    def test_json_object_env_key(self):
        q = Path(self.t, "q")
        put(q / ".env", "A=file\nB=file\n")
        put(q / "x.json", {".env": {"B": "obj-${A}", "N": 3, "M": {"$env": "A", "$prefix": "env:"},
                                    "R": {"$ref": "v.json#/k"}},
                           "_exec": ["sh", "-c", 'echo "$A|$B|${N-unset}|$M|$R"']})
        put(q / "v.json", {"k": "ref-val"})
        # 真資料夾的 .env 先、物件的 .env key 後（後讀的贏）；值可放指示詞，解完不是字串的靜默跳過
        self.assertEqual(run("--ws", self.t, str(q / "x.json"))[:2], (0, "file|obj-file|unset|env:file|ref-val\n"))
        # .env key 設 AOS_ENTRY 改變挑哪格
        put(q / "y.json", {".env": {"AOS_ENTRY": "alt"}, "_exec": ["echo", "default"], "alt": ["echo", "alt"]})
        self.assertEqual(run("--ws", self.t, str(q / "y.json"))[:2], (0, "alt\n"))
        # 指示詞解不開、名字不合＝.env 壞，不印值
        put(q / "z.json", {".env": {"S": {"$env": "NOPE_NOT_SET"}}, "_exec": ["true"]})
        self.assertEqual(run("--ws", self.t, str(q / "z.json"))[2], ".env 壞")
        put(q / "z.json", {".env": {"1bad": "sk-SECRET"}, "_exec": ["true"]})
        rc, _, err, stderr = run("--ws", self.t, str(q / "z.json"))
        self.assertEqual((rc, err), (1, ".env 壞"))
        self.assertNotIn("SECRET", stderr)
        # .env 解完不是物件＝整個跳過
        put(q / "z.json", {".env": "x", "_exec": ["echo", "ok"]})
        self.assertEqual(run("--ws", self.t, str(q / "z.json"))[:2], (0, "ok\n"))

    def test_json_nested_objects_all_the_way_down(self):
        q = Path(self.t, "q")
        put(q / "x.json", {"_exec": {".env": {"A": "1", "AOS_ENTRY": "dev"},
                                     "dev": {".env": {"B": "${A}2"}, "_exec": ["no"],
                                             "dev": ["sh", "-c", 'echo "$A|$B|$AOS_CO|$AOS_CF"']}}})
        rx = (q / "x.json").resolve()
        self.assertEqual(run("--ws", self.t, str(q / "x.json"))[:2], (0, "1|12|/_exec/dev/dev|%s\n" % rx))

    def test_json_entry_is_dotenv(self):
        # 進入物件那一刻 AOS_ENTRY 就是 .env＝照做：.env 那格是入口，不當環境設定
        q = Path(self.t, "q")
        put(q / "x.json", {".env": ["sh", "-c", 'echo "dot|${A-unset}|$AOS_CO"'], "_exec": ["echo", "no"]})
        self.assertEqual(run("--ws", self.t, str(q / "x.json"), env={"AOS_ENTRY": ".env"})[:2], (0, "dot|unset|/.env\n"))
        # 物件自己的 .env key 把 AOS_ENTRY 改成 .env：先套（那時還不是 .env），再挑 .env 那格
        put(q / "y.json", {".env": {"AOS_ENTRY": ".env"}})
        self.assertEqual(run("--ws", self.t, str(q / "y.json"))[2], "入口壞")

    def test_aos_co(self):
        q = Path(self.t, "q")
        show = ["sh", "-c", 'echo "[$AOS_CO]"']
        put(q / "a.json", show)                                         # 整份檔就是入口＝空
        self.assertEqual(run("--ws", self.t, str(q / "a.json"))[1], "[]\n")
        put(q / "b.json", {"_exec": show})
        self.assertEqual(run("--ws", self.t, str(q / "b.json"))[1], "[/_exec]\n")
        put(q / "c.json", {"a": {"_exec": show}, "x/y": {"_exec": show}, "l": [show]})
        self.assertEqual(run("--ws", self.t, str(q / "c.json") + "#/a")[1], "[/a/_exec]\n")       # 檔#/指標也算
        self.assertEqual(run("--ws", self.t, str(q / "c.json") + "#/x~1y")[1], "[/x~1y/_exec]\n")
        self.assertEqual(run("--ws", self.t, str(q / "c.json") + "#/l/0")[1], "[/l/0]\n")
        put(q / "d.json", {"_exec": show}); put(q / "e.json", {"we~ird/k": show})
        self.assertEqual(run("--ws", self.t, str(q / "e.json"), env={"AOS_ENTRY": "we~ird/k"})[1], "[/we~0ird~1k]\n")
        prog(self.t, "p", 'echo "[$AOS_CO]"\n')                        # 不是 JSON＝空，外面的值被覆寫
        self.assertEqual(run("--ws", self.t, str(Path(self.t, "p")), env={"AOS_CO": "/old"})[1], "[]\n")
        put(q / ".env", "AOS_CO=from-env\n")                            # .env 設了就不蓋
        self.assertEqual(run("--ws", self.t, str(q / "b.json"))[1], "[from-env]\n")
        os.remove(q / ".env")
        put(q / "f.json", {".env": {"AOS_CO": "obj"}, "_exec": show})   # JSON .env key 設了也不蓋
        self.assertEqual(run("--ws", self.t, str(q / "f.json"))[1], "[obj]\n")
        # 字串轉向＝全新的一跳，AOS_CO 照下一跳算
        put(q / "g.json", {"_exec": "b.json"})
        self.assertEqual(run("--ws", self.t, str(q / "g.json"))[1], "[/_exec]\n")

    def test_flag_ws_beats_json_env_key(self):
        a, b = Path(self.t, "a"), Path(self.t, "b")
        a.mkdir(); b.mkdir()
        q = Path(self.t, "q")
        put(q / "x.json", {".env": {"AOS_WS": str(b)}, "_exec": ["sh", "-c", 'echo "$AOS_WS"']})
        self.assertEqual(run("--ws", str(a), str(q / "x.json"))[1], "%s\n" % a.resolve())
        self.assertEqual(run(str(q / "x.json"))[1], "%s\n" % b)
        # 資料夾一路往下時每層 .env 讀完旗標都蓋回
        d = Path(self.t, "p")
        put(d / "_exec" / ".env", "AOS_WS=%s\n" % b)
        put(d / "_exec" / "_exec", '#!/bin/sh\necho "$AOS_WS"\n', 0o755)
        self.assertEqual(run("--ws", str(a), str(d))[1], "%s\n" % a.resolve())

    def test_flag_ws_beats_env_with_entry(self):
        a, b = Path(self.t, "a"), Path(self.t, "b")
        a.mkdir(); b.mkdir()
        d = prog(self.t, "p", "echo default\n")
        put(Path(d, "main"), '#!/bin/sh\necho "main|$AOS_WS"\n', 0o755)
        put(Path(d, ".env"), "AOS_WS=%s\nAOS_ENTRY=main\n" % b)
        self.assertEqual(run("--ws", str(a), d)[:2], (0, "main|%s\n" % a.resolve()))
        self.assertEqual(run(d)[:2], (0, "main|%s\n" % b))

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
