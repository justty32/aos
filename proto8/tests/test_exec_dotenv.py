"""aos-exec 的 .env 格式基礎子集與 --dotenv-override（10-22 ideas；N-58、N-59 第 4 件、N-60）。
格式：收下的寫法給的值同 python-dotenv（export 前綴、= 兩邊空白、沒引號去頭尾空白、空白＋# 註解、單雙引號剝一對、${名字}），
各家不一致的寫法＝.env 壞。蓋不蓋：沒旗標＝開始讀這份 .env 時環境已有的名字跳過（同一份檔裡同名照樣後者贏）；
--dotenv-override＝這一跳讀的每份 .env 都蓋，字串轉向、插進去的 aos-exec、loop 每拍的 aos-exec 不吃。
python-dotenv 有裝就把收下的寫法丟給 load_dotenv 當場比（沒裝就 skip；aos-exec 本身不依賴它）。"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

from test_exec_rules import put, run
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（10-23 照 impls）：檢查對得上原因開頭再拿掉

SHOW = 'import json, os, sys; print(json.dumps({k: os.environ.get(k) for k in sys.argv[1:]}))'

# (這行 .env, 名字, python-dotenv 給的值)：收下的寫法
GOOD = [
    ("export A=1", "A", "1"),
    ("export\tA=1", "A", "1"),
    ("export=1", "export", "1"),
    ("A = 1", "A", "1"),
    ("A\t=\t1", "A", "1"),
    ("A=  hi  ", "A", "hi"),
    ("A=1  # 說明", "A", "1"),
    ("A=x\t#c", "A", "x"),
    ("A=a#b", "A", "a#b"),    # 10-22 使用者先說報錯、後更正「還是跟python一樣吧」：照字面
    ("A=#fff", "A", "#fff"),
    ("A=a#b #c", "A", "a#b"),
    ("A=", "A", ""),
    # 10-22 使用者「按照python-dotenv把它當空白去掉」：值頭尾、# 前面的 Unicode 空白（全形、不換行空白…）也去掉
    ("A=a\u3000", "A", "a"),
    ("A=\u3000b", "A", "b"),
    ("A=a\u3000#c", "A", "a"),
    ("A=a\u00a0 # c", "A", "a"),
    ("A=\u3000'q'\u3000# c", "A", "q"),
    ("A='q'\u3000", "A", "q"),
    ("A=a\u3000b", "A", "a\u3000b"),
    ("A='a#b'", "A", "a#b"),
    ('A="#fff"', "A", "#fff"),
    ("A='a b # c $X'", "A", "a b # c $X"),
    ("A=  'q'  # c", "A", "q"),
    ("A='b'#c", "A", "b"),
    ('A="  a b # c \' "', "A", "  a b # c ' "),
    ('A="x" # c', "A", "x"),
    ('A="$HOME"', "A", "$HOME"),
    ('A=""', "A", ""),
    ("A=a\"b'c", "A", "a\"b'c"),
    ("A=x\\y", "A", "x\\y"),
]
# 各家不一致或不支援的寫法：.env 壞
BAD = ["A= # 說明", "A=\t#c", "A=\u3000#c",
       "A='x\\y'", "A='${HOME}'", 'A="x\\"y"', 'A="x\\ny"', 'A="c"d', "A='a'b", 'A="unclosed',
       "A='", "A=${HOME:-x}", "export A", "A B=1"]


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = self._t.name
        self.addCleanup(self._t.cleanup)

    def show(self, d, *names, flags=(), env=None):
        """d 的 _exec.json 印出這些名字的值（JSON），回 dict。"""
        put(Path(d, "_exec.json"), ["python3", "-c", SHOW, *names])
        rc, out, err, stderr = run(*flags, "--ws", self.t, str(d), env=env)
        self.assertEqual(rc, 0, stderr)
        return json.loads(out)

    # ---- 格式（B1～B9）----

    def test_good_lines(self):
        d = Path(self.t, "p")
        for line, name, want in GOOD:
            put(d / ".env", line + "\n")
            self.assertEqual(self.show(d, name, env={"HOME": "/h"})[name], want, line)

    def test_bad_lines(self):
        d = Path(self.t, "p")
        put(d / "_exec.json", ["true"])
        for line in BAD:
            put(d / ".env", "OK=1\n" + line + "\n")
            rc, out, err, stderr = run("--ws", self.t, str(d), env={"HOME": "/h"})
            self.assertEqual((rc, err), (1, ".env 壞"), line)
            self.assertIn("第 2 行", stderr, line)

    def test_bad_lines_never_print_value(self):
        d = Path(self.t, "p")
        put(d / "_exec.json", ["true"])
        for line in ("A= # sk-SECRET", "A='sk-SECRET\\'", "A=\"sk-SECRET\"x", "A=\"sk-SECRET", "A='sk-SECRET${X}'"):
            put(d / ".env", line + "\n")
            rc, out, err, stderr = run("--ws", self.t, str(d))
            self.assertEqual((rc, err), (1, ".env 壞"), line)
            self.assertNotIn("SECRET", stderr, line)

    def test_comment_cut_before_expand_and_quotes_expand(self):
        # 先切註解再展開：展開出來的值含 ` #` 不會被切；雙引號展開 ${}、單引號照字面（${ 在單引號裡＝壞，另測）
        d = Path(self.t, "p")
        put(d / ".env", 'A="x #y"\nB=${A} # c\nC="<${A}>"\nD=$A\n')
        self.assertEqual(self.show(d, "A", "B", "C", "D"), {"A": "x #y", "B": "x #y", "C": "<x #y>", "D": "$A"})

    # ---- 蓋不蓋 ----

    def test_default_keeps_existing_same_file_later_wins(self):
        d = Path(self.t, "p")
        put(d / ".env", "A=1\nB=1\nB=2\nC=${A}\nD=${B}\n")
        self.assertEqual(self.show(d, "A", "B", "C", "D", env={"A": "out"}), {"A": "out", "B": "2", "C": "out", "D": "2"})
        # 跳過的那行格式照驗、${} 照查
        put(d / ".env", "A=${NOPE_NOT_SET}\n")
        self.assertEqual(run("--ws", self.t, str(d), env={"A": "out"})[2], ".env 壞")
        put(d / ".env", "A='x\n")
        self.assertEqual(run("--ws", self.t, str(d), env={"A": "out"})[2], ".env 壞")

    def test_override_flag(self):
        d = Path(self.t, "p")
        put(d / ".env", "A=1\nB=1\nB=2\nC=${A}\n")
        want = {"A": "1", "B": "2", "C": "1"}
        self.assertEqual(self.show(d, "A", "B", "C", flags=("--dotenv-override",), env={"A": "out"}), want)
        # 重複給＝一樣；放 --ws 前後都行
        self.assertEqual(self.show(d, "A", "B", "C", flags=("--dotenv-override", "--dotenv-override"), env={"A": "out"}),
                         want)
        put(d / "_exec.json", ["true"])
        for flags in (("--dotenv-override=1",), ("--dotenv-override=",)):
            rc, out, err, stderr = run(*flags, str(d))
            self.assertEqual((rc, stderr.startswith("aos-exec: usage: ")), (1, True), flags)
        self.assertEqual(run("--ws", self.t, "--dotenv-override", str(d))[0], 0)

    def test_flag_reaches_every_env_in_this_hop(self):
        # 同一跳一路往下讀的每層都吃：資料夾 → $AOS_ENTRY 走進的資料夾 → JSON 物件的 .env key
        d = Path(self.t, "p")
        put(d / ".env", "A=p\nB=p\nAOS_ENTRY=sub\n")
        put(d / "sub" / ".env", "A=sub\nC=sub\n")
        put(d / "sub" / "sub.json", {".env": {"A": "obj", "D": "obj"}, "sub": ["python3", "-c", SHOW, "A", "B", "C", "D"]})
        rc, out, err, stderr = run("--dotenv-override", "--ws", self.t, str(d), env={"A": "out", "B": "out"})
        self.assertEqual(json.loads(out), {"A": "obj", "B": "p", "C": "sub", "D": "obj"}, stderr)
        # 沒旗標：原有的贏、外層（先讀的）贏內層（AOS_ENTRY 外面沒設，p 的 .env 設得了）
        rc, out, err, stderr = run("--ws", self.t, str(d), env={"A": "out", "B": "out"})
        self.assertEqual(json.loads(out), {"A": "out", "B": "out", "C": "sub", "D": "obj"}, stderr)

    def test_redirect_does_not_take_flag(self):
        # 字串轉向＝全新一跳、不吃旗標（10-21 E4）：r 那跳蓋、t 那跳不蓋
        r, t = Path(self.t, "r"), Path(self.t, "t")
        put(r / "_exec.json", '"../t"')
        put(t / ".env", "A=t\nB=t\n")
        put(t / "_exec.json", ["python3", "-c", SHOW, "A", "B"])
        rc, out, _, stderr = run("--dotenv-override", "--ws", self.t, str(r), env={"A": "out"})
        self.assertEqual(json.loads(out), {"A": "out", "B": "t"}, stderr)
        put(r / ".env", "A=r\n")
        rc, out, _, stderr = run("--dotenv-override", "--ws", self.t, str(r), env={"A": "out"})
        self.assertEqual(json.loads(out), {"A": "r", "B": "t"}, stderr)
        rc, out, _, stderr = run("--ws", self.t, str(r), env={"A": "out"})
        self.assertEqual(json.loads(out), {"A": "out", "B": "t"}, stderr)

    def test_loop_beat_needs_extra_hop_for_flag(self):
        # loop 每拍叫 aos-exec -- <run>，-- 後面寫不了旗標：要蓋就多一跳，body 寫 ["aos-exec", "--dotenv-override", "think"]
        q = Path(self.t, "q")
        put(q / "think" / ".env", "A=think\n")
        put(q / "think" / "_exec.json", ["sh", "-c", 'echo "$A" >> "$AOS_WS/seen"'])
        for body, want in ((["aos-exec", "--dotenv-override", "think"], "think"), (["aos-exec", "think"], "out")):
            put(q / "loop.json", {"_exec": ["aos-loop", {"$env": "AOS_CF"}], "run": "loop.json#/body", "body": body, "max": 2})
            seen = Path(self.t, "seen")
            if seen.exists():
                seen.unlink()
            self.assertEqual(run("--ws", self.t, str(q / "loop.json"), env={"A": "out"})[0], 0)
            self.assertEqual(seen.read_text(), "%s\n%s\n" % (want, want), body)

    def test_json_env_key_format_unchanged(self):
        # JSON 的 .env key：格式不套引號、註解那些（JSON 自己有引號），只套蓋不蓋
        q = Path(self.t, "q")
        put(q / "x.json", {".env": {"A": "'a' # c", "B": "x"}, "_exec": ["python3", "-c", SHOW, "A", "B"]})
        rc, out, _, stderr = run("--ws", self.t, str(q / "x.json"), env={"B": "out"})
        self.assertEqual(json.loads(out), {"A": "'a' # c", "B": "out"}, stderr)
        rc, out, _, stderr = run("--dotenv-override", "--ws", self.t, str(q / "x.json"), env={"B": "out"})
        self.assertEqual(json.loads(out), {"A": "'a' # c", "B": "x"}, stderr)

    # ---- 選配：跟 python-dotenv 當場比 ----

    def test_same_as_python_dotenv(self):
        try:
            import dotenv  # noqa: F401
        except ImportError:
            self.skipTest("沒裝 python-dotenv")
        d = Path(self.t, "p")
        cases = [(line, [name]) for line, name, _ in GOOD] + [("A=${B}\nB=in\nC=${B}\nB=again", ["A", "B", "C"])]
        base = {"HOME": "/h", "A": "out-a", "B": "out"}
        for text, names in cases:
            text += "\n"
            put(d / ".env", text)
            for override in (False, True):
                got = self.show(d, *names, flags=("--dotenv-override",) if override else (), env=base)
                code = ("import dotenv, io, json, os, sys; dotenv.load_dotenv(stream=io.StringIO(sys.stdin.read()), "
                        "override=%s); print(json.dumps({k: os.environ.get(k) for k in %r}))" % (override, names))
                env = {k: v for k, v in os.environ.items() if k not in names}
                env.update(base)
                want = json.loads(subprocess.run([sys.executable, "-c", code], input=text, capture_output=True,
                                                 text=True, env=env, check=True).stdout)
                self.assertEqual(got, want, (text, override))


if __name__ == "__main__":
    unittest.main()
