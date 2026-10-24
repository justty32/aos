#!/usr/bin/env python3
"""test_cli.py：aos-json 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-json

每個案例開一個空資料夾、擺好檔、跑一次 aos-json，看退出碼、stdout、錯誤代號與檔改完的原文。
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-json"))
failures = 0
count = 0


def check(name, got, want):
    global failures, count
    count += 1
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


class Box:
    """一個空資料夾：put 擺檔、run 跑 aos-json、read 讀檔原文。"""

    def __init__(self, files=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        for name, text in (files or {}).items():
            self.put(name, text)

    def put(self, name, text):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text if isinstance(text, str) else json.dumps(text))

    def read(self, name):
        with open(os.path.join(self.dir, name), encoding="utf-8") as f:
            return f.read()

    def run(self, *args, stdin="", env=None):
        r = subprocess.run([BIN, *args], cwd=self.dir, input=stdin, capture_output=True, text=True,
                           env=dict(os.environ, **(env or {})))
        code = None
        if r.returncode == 1 and r.stderr.startswith("aos-json: "):
            code = r.stderr.split()[1]
        return r.returncode, r.stdout, code

    def ls(self):
        out = []
        for root, _, names in os.walk(self.dir):
            out += [os.path.relpath(os.path.join(root, n), self.dir) for n in names]
        return sorted(out)


FSM = '{\n    "start": "idle",\n    "states": {"$ref": "states.json"},\n    "exec": {"$env": "AOS_CF", "$path": "#/x"}\n}\n'
STATES = '{\n  "idle": {"exec": "idle", "next": "think"},\n  "think": {\n    "exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000},\n    "next": "idle"\n  }\n}\n'

# ---- get ----
b = Box({"fsm.json": FSM, "states.json": STATES})
check("get 原文", b.run("get", "fsm.json#/start"), (0, '"idle"\n', None))
check("get 整份一行", b.run("get", "states.json#/idle"), (0, '{"exec": "idle", "next": "think"}\n', None))
check("get --str", b.run("get", "--str", "fsm.json#/start"), (0, "idle\n", None))
check("get --str 不是字串", b.run("get", "--str", "fsm.json#/states")[2], "TargetBad")
check("get 指示詞原樣", b.run("get", "fsm.json#/states"), (0, '{"$ref": "states.json"}\n', None))
check("get 路上有 $ref 沒 --follow", b.run("get", "fsm.json#/states/think")[2], "PointerMissing")
check("get --follow 穿過 $ref", b.run("get", "--follow", "fsm.json#/states/think/next"), (0, '"idle"\n', None))
check("get --resolve 解 $ref", json.loads(b.run("get", "--resolve", "fsm.json#/states")[1])["idle"]["next"], "think")
check("get --resolve 解 $env", b.run("get", "--resolve", "--str", "fsm.json#/exec", env={"AOS_CF": "/a/f.json"}),
      (0, "/a/f.json#/x\n", None))
check("get --resolve $env 沒設", b.run("get", "--resolve", "fsm.json#/exec", env={"AOS_CF": ""})[0], 0)
e = dict(os.environ)
e.pop("AOS_CF", None)
r = subprocess.run([BIN, "get", "--resolve", "fsm.json#/exec"], cwd=b.dir, capture_output=True, text=True, env=e)
check("get --resolve $env 沒設＝DirectiveBad", r.stderr.split()[1:2], ["DirectiveBad"])
check("get 指不到", b.run("get", "fsm.json#/nope")[2], "PointerMissing")
check("get # 後不是 /", b.run("get", "fsm.json#start")[2], "SpecBad")
check("get 沒檔名", b.run("get", "#/a")[2], "SpecBad")
check("get 檔不在", b.run("get", "nope.json")[2], "FileMissing")
os.mkdir(os.path.join(b.dir, "d"))
check("get 資料夾", b.run("get", "d")[2], "FileBad")
b.put("bad.json", "{not json")
check("get 不是 JSON", b.run("get", "bad.json")[2], "FileBad")
b.put("esc.json", {"a/b": {"~c": 1}, "arr": [10, 11]})
check("get ~0 ~1", b.run("get", "esc.json#/a~1b/~0c"), (0, "1\n", None))
check("get 陣列索引", b.run("get", "esc.json#/arr/1"), (0, "11\n", None))
check("get 索引前導 0 不收", b.run("get", "esc.json#/arr/01")[2], "PointerMissing")
b.put("lit.json", {"x": {"$ref": "states.json", "k": 5}})
check("get 指示詞物件裡的字面 key（原文）", b.run("get", "lit.json#/x/k"), (0, "5\n", None))
b.put("sb.json", '#!/usr/bin/env aos-exec\n{"a": 1}\n')
check("get 跳過 #!", b.run("get", "sb.json#/a"), (0, "1\n", None))
check("get 參數太多", b.run("get", "a", "b")[2], "ArgumentsBad")

# ---- $ref 陣列（合成一份）----
m = Box({"m.json": '{"s": {"$ref": ["a.json", "b.json"]}, "l": {"$ref": ["la.json", "lb.json"]}}',
         "a.json": '{"x": 1, "y": 2}', "b.json": '{"y": 3}', "la.json": "[1, 2]", "lb.json": "[3]"})
check("get --follow 合物件：後蓋前", m.run("get", "--follow", "m.json#/s/y"), (0, "3\n", None))
check("get --follow 合物件：只在前面那份", m.run("get", "--follow", "m.json#/s/x"), (0, "1\n", None))
check("get --follow 接陣列：索引換算", m.run("get", "--follow", "m.json#/l/2"), (0, "3\n", None))
check("where 合物件指到最後有它的那份", m.run("where", "m.json#/s/y")[1], "m.json#/s\nb.json#/y\n")
m.put("bad.json", '{"s": {"$ref": ["a.json", "la.json"]}}')
check("合不起來", m.run("get", "--follow", "bad.json#/s/x")[2], "DirectiveBad")
check("set --follow 新 key 寫進最後一份", m.run("set", "--follow", "m.json#/s/z", "9")[0], 0)
check("  b.json 多了 z", json.loads(m.read("b.json")), {"y": 3, "z": 9})
check("set --follow 整個換合起來的值＝TargetBad", m.run("set", "--follow", "m.json#/s", "{}")[2], "TargetBad")
m.put("b.json", '{"y": 3, "x": 7}')
check("del --follow 每一份有的都刪", m.run("del", "--follow", "m.json#/s/x")[0], 0)
check("  a.json 沒 x", json.loads(m.read("a.json")), {"y": 2})
check("  b.json 沒 x", json.loads(m.read("b.json")), {"y": 3})

# ---- where ----
w = Box({"fsm.json": FSM, "states.json": STATES, "c.json": '{"to": {"$ref": "d/e.json#/v"}}', "d/e.json": '{"v": 1}',
         "loop1.json": '{"a": {"$ref": "loop2.json#/a"}}', "loop2.json": '{"a": {"$ref": "loop1.json#/a"}}'})
check("where 沒指示詞", w.run("where", "fsm.json#/start")[1], "fsm.json#/start\n")
check("where 穿 $ref", w.run("where", "fsm.json#/states/think/next")[1], "fsm.json#/states\nstates.json#/think/next\n")
check("where 指到的值是 $ref", w.run("where", "c.json#/to")[1], "c.json#/to\nd/e.json#/v\n")
check("where $env", w.run("where", "fsm.json#/exec")[1], "fsm.json#/exec\n$env AOS_CF\n")
check("where 繞圈", w.run("where", "loop1.json#/a")[2], "DirectiveBad")
check("where 走不下去 $env", w.run("where", "fsm.json#/exec/x")[2], "PointerMissing")

# ---- peek ----
p = Box({"fsm.json": FSM, "states.json": STATES, "long.json": json.dumps({"s": "字" * 40, "n": None, "o": {str(i): i for i in range(9)}})})
check("peek 頂層", p.run("peek", "fsm.json")[1],
      'fsm.json {3} start, states, exec\n  start: "idle"\n  states: $ref "states.json"\n  exec: $env AOS_CF $path "#/x"\n')
check("peek --follow 展開 $ref", p.run("peek", "--follow", "fsm.json#/states")[1],
      'fsm.json#/states {2} idle, think（$ref 展開）\n  idle: {2} exec, next\n  think: {2} exec, next\n')
check("peek --depth 2", p.run("peek", "--follow", "--depth", "2", "fsm.json#/states/think")[1],
      'fsm.json#/states/think {2} exec, next\n  exec: {2} argv, timeout_ms\n    argv: ["python3", "brain.py"]\n'
      '    timeout_ms: 120000\n  next: "idle"\n')
check("peek 純值整個印", p.run("peek", "--follow", "fsm.json#/states/think/exec/timeout_ms")[1],
      "fsm.json#/states/think/exec/timeout_ms: 120000\n")
out = p.run("peek", "long.json")[1]
check("peek 長字串截斷", "…（共 120 位元組）" in out and "o: {9} 0, 1, 2, 3, 4, 5…" in out, True)
check("peek --depth 0 只有第一行", p.run("peek", "--depth", "0", "fsm.json")[1], "fsm.json {3} start, states, exec\n")
check("peek --depth 壞", p.run("peek", "--depth", "x", "fsm.json")[2], "ArgumentsBad")

# ---- set：值、位置 ----
s = Box({"fsm.json": FSM, "states.json": STATES})
check("set 數字", s.run("set", "fsm.json#/n", "3")[0], 0)
check("set 從 stdin", s.run("set", "fsm.json#/o", stdin='{"a": [1]}\n')[0], 0)
check("set --str", s.run("set", "--str", "fsm.json#/start", "think")[0], 0)
check("set --str stdin 去一個換行", s.run("set", "--str", "fsm.json#/t", stdin="a b\n")[0], 0)
d = json.loads(s.read("fsm.json"))
check("  值都寫進去", (d["n"], d["o"], d["start"], d["t"]), (3, {"a": [1]}, "think", "a b"))
check("set 值不是 JSON", s.run("set", "fsm.json#/n", "abc")[2], "ValueBad")
check("set stdin 空", s.run("set", "fsm.json#/n")[2], "ValueMissing")
check("set 值只有空白", s.run("set", "fsm.json#/n", "  ")[2], "ValueMissing")
check("set 參數多", s.run("set", "fsm.json#/n", "1", "2")[2], "ArgumentsBad")
check("set 檔名後的 -- 是多的參數", s.run("set", "fsm.json#/n", "--", "-3")[2], "ArgumentsBad")
check("set -- 負數", s.run("set", "--", "fsm.json#/n", "-3")[0], 0)
check("set 上一層不在", s.run("set", "fsm.json#/a/b/c", "1")[2], "PointerMissing")
check("set --parents", s.run("set", "--parents", "fsm.json#/a/b/c", "1")[0], 0)
check("  建了路上的物件", json.loads(s.read("fsm.json"))["a"], {"b": {"c": 1}})
check("set 陣列已有的索引", s.run("set", "fsm.json#/o/a/0", "5")[0], 0)
check("set 陣列超出", s.run("set", "fsm.json#/o/a/1", "5")[2], "PointerMissing")
check("set 上一層是純值", s.run("set", "fsm.json#/n/x", "5")[2], "TargetBad")
check("set 路上是指示詞＝FollowMissing", s.run("set", "fsm.json#/states/idle/next", '"x"')[2], "FollowMissing")
check("set 指示詞物件裡加 key 也擋", s.run("set", "fsm.json#/exec/k", "1")[2], "FollowMissing")
check("set --follow 改被參照的檔", s.run("set", "--follow", "fsm.json#/states/idle/next", '"act"')[0], 0)
check("  states.json 改了", json.loads(s.read("states.json"))["idle"]["next"], "act")
check("set 直接指著指示詞＝原地換", s.run("set", "fsm.json#/exec", '"idle"')[0], 0)
check("  fsm.json 的 exec", json.loads(s.read("fsm.json"))["exec"], "idle")
check("set 整份", s.run("set", "new.json", '{"a": 1}')[0], 0)
check("  新檔", s.read("new.json"), '{\n  "a": 1\n}\n')
check("沒留下暫存檔", [n for n in s.ls() if n.startswith(".") or "/." in n], [])

# ---- 排版：只改變的那一塊 ----
f = Box({"f.json": '#!/usr/bin/env aos-exec\n{\n    "a": {"x": 1, "y": [1, 2]},\n    "b": "keep   this",\n'
                   '    "c": {\n        "d": 1\n    }\n}\n', "one.json": '{"a":1,"b":{"c":2}}'})
os.chmod(os.path.join(f.dir, "f.json"), 0o755)
f.run("set", "f.json#/a/x", "2")
check("改一個值只動那個字", f.read("f.json"),
      '#!/usr/bin/env aos-exec\n{\n    "a": {"x": 2, "y": [1, 2]},\n    "b": "keep   this",\n    "c": {\n        "d": 1\n    }\n}\n')
check("權限留著", stat.S_IMODE(os.stat(os.path.join(f.dir, "f.json")).st_mode), 0o755)
f.run("append", "f.json#/a/y", "3")
check("append 一行的陣列", '"y": [1, 2, 3]' in f.read("f.json"), True)
f.run("set", "f.json#/c/e", '{"z": [1]}')
check("多行的物件加 key 照縮排", f.read("f.json").split('"c": ')[1],
      '{\n        "d": 1,\n        "e": {\n            "z": [\n                1\n            ]\n        }\n    }\n}\n')
f.run("del", "f.json#/b")
check("刪 key 其他不動", '"keep' not in f.read("f.json") and f.read("f.json").startswith('#!/usr/bin/env aos-exec\n{\n    "a": {"x": 2'), True)
f.run("del", "f.json#/a/y/0")
check("刪陣列第一個", '"y": [2, 3]' in f.read("f.json"), True)
f.run("set", "one.json#/b/c", "3")
check("一行的檔照一行", f.read("one.json"), '{"a":1,"b":{"c":3}}')
f.run("set", "one.json#/z", "1")
check("一行的檔加 key", f.read("one.json"), '{"a":1,"b":{"c":3}, "z": 1}')
mt = os.stat(os.path.join(f.dir, "one.json")).st_mtime_ns
os.utime(os.path.join(f.dir, "one.json"), ns=(1, 1))
f.run("set", "one.json#/z", "1")
check("沒變就不寫", os.stat(os.path.join(f.dir, "one.json")).st_mtime_ns, 1)
os.symlink("f.json", os.path.join(f.dir, "link.json"))
f.run("set", "link.json#/a/x", "9")
check("捷徑留著、改到它指的檔", (os.path.islink(os.path.join(f.dir, "link.json")), json.loads(f.read("f.json").split("\n", 1)[1])["a"]["x"]), (True, 9))

# ---- batch ----
t = Box({"fsm.json": FSM, "states.json": STATES})
check("batch 一次改很多", t.run("batch", "--follow", "fsm.json", stdin='{"/start": "think", "/states/think/next": "act"}')[0], 0)
check("  兩份檔都改了", (json.loads(t.read("fsm.json"))["start"], json.loads(t.read("states.json"))["think"]["next"]), ("think", "act"))
before = t.read("fsm.json")
check("batch 有一個失敗＝都不寫", t.run("batch", "fsm.json", stdin='{"/start": "x", "/nope/a": 1}')[2], "PointerMissing")
check("  原文沒動", t.read("fsm.json"), before)
check("batch 不是物件", t.run("batch", "fsm.json", stdin="[1]")[2], "ValueBad")
check("batch key 不是指標", t.run("batch", "fsm.json", stdin='{"start": 1}')[2], "SpecBad")
check("batch 參數", t.run("batch")[2], "ArgumentsBad")

# ---- del、append、merge ----
u = Box({"x.json": '{"a": [1], "o": {"k": 1}, "s": "str"}'})
check("del 指不到", u.run("del", "x.json#/nope")[2], "PointerMissing")
check("del 整份", u.run("del", "x.json")[2], "TargetBad")
check("append 不是陣列", u.run("append", "x.json#/o", "1")[2], "TargetBad")
check("append 指不到", u.run("append", "x.json#/zz", "1")[2], "PointerMissing")
check("merge", u.run("merge", "x.json#/o", '{"k": 2, "j": null}')[0], 0)
check("  淺層合、null 照放", json.loads(u.read("x.json"))["o"], {"k": 2, "j": None})
check("merge 值不是物件", u.run("merge", "x.json#/o", "[1]")[2], "ValueBad")
check("merge 目標不是物件", u.run("merge", "x.json#/s", "{}")[2], "TargetBad")

# ---- env、ref ----
v = Box({"x.json": '{"out": "/abs/out", "body": {"argv": ["a"], "in": {"$ref": "sub/in.json"}}}', "sub/in.json": "{}"})
check("env", v.run("env", "--path", "out", "x.json#/out", "AOS_WS")[0], 0)
check("  寫成 $env", json.loads(v.read("x.json"))["out"], {"$env": "AOS_WS", "$path": "out"})
check("env 名字空", v.run("env", "x.json#/out", "")[2], "ArgumentsBad")
check("ref 目標寫法不合", v.run("ref", "x.json#/out", "#/a")[2], "ValueBad")
check("ref --move 搬到新檔", v.run("ref", "--move", "x.json#/body", "sub/body.json")[0], 0)
check("  原地成了 $ref", json.loads(v.read("x.json"))["body"], {"$ref": "sub/body.json"})
check("  新檔裡的相對 $ref 跟著改", json.loads(v.read("sub/body.json"))["in"], {"$ref": "in.json"})
check("  解出來跟搬之前一樣", json.loads(v.run("get", "--resolve", "x.json#/body")[1]), {"argv": ["a"], "in": {}})
check("ref --move 目標已在", v.run("ref", "--move", "x.json#/out", "sub/in.json")[2], "TargetBad")
check("ref --move 到檔內位置", v.run("ref", "--move", "x.json#/out", "sub/in.json#/out")[0], 0)
check("  搬過去", json.loads(v.read("sub/in.json")), {"out": {"$env": "AOS_WS", "$path": "out"}})
v.put("y.json", '{"a": {"b": 1}}')
check("ref --move 搬進自己裡面", v.run("ref", "--move", "y.json#/a", "y.json#/a/c")[2], "TargetBad")
check("ref --move 資料夾不在", v.run("ref", "--move", "y.json#/a", "nodir/z.json")[2], "FileMissing")
check("ref 原地", v.run("ref", "y.json#/a", "z.json")[0], 0)

# ---- check、--check ----
c = Box({"loop.json": '{"exec": "", "max": 1}', "fsm.json": FSM, "states.json": STATES,
         "bad.json": '{"states": {"$ref": "nope.json"}, "x": {"$ref": "#/a"}, "e": {"$env": "NOPE_NOT_SET"}}',
         "daemon.json": '{"loops": {"a": {"exec": {"cwd": "x"}}, "b": {"exec": ["aos-loop", {"$env": "X"}]}}}'})
check("check 乾淨", c.run("check", "fsm.json"), (0, "", None))
check("check exec 空字串", c.run("check", "loop.json")[1].split(": ")[1].split()[0], "ExecBad")
out = c.run("check", "bad.json")[1]
check("check $ref 讀不到、寫法不合", ("bad.json#/states: DirectiveBad" in out, "bad.json#/x: DirectiveFormBad" in out), (True, True))
check("check $env 沒設預設不報", "NOPE_NOT_SET" in out, False)
check("check --env 才報", "NOPE_NOT_SET" in c.run("check", "--env", "bad.json")[1], True)
out = c.run("check", "daemon.json")[1]
check("check daemon 單子沒 argv", ("daemon.json#/loops/a/exec: ExecBad" in out, "loops/b" in out), (True, False))
check("check 多份一起", c.run("check", "fsm.json", "loop.json")[0], 1)
check("set --check 擋下形狀不對", c.run("set", "--check", "--follow", "fsm.json#/states/think/exec", "[]")[2], "CheckFailed")
check("  沒寫", json.loads(c.read("states.json"))["think"]["exec"]["timeout_ms"], 120000)
check("set --check 原本就有的問題不擋", c.run("set", "--check", "loop.json#/max", "2")[0], 0)

# ---- 命令列、寫不了 ----
z = Box({"x.json": "{}"})
check("沒參數", z.run()[2], "ArgumentsBad")
check("不認得的子命令", z.run("nope")[2], "CommandUnknown")
check("不認得的旗標", z.run("get", "--nope", "x.json")[2], "FlagUnknown")
if os.geteuid() != 0:
    os.chmod(z.dir, 0o555)
    check("資料夾不能寫＝WriteFailed", z.run("set", "x.json#/a", "1")[2], "WriteFailed")
    os.chmod(z.dir, 0o755)

print("aos-json test_cli：%d 個，失敗 %d" % (count, failures))
sys.exit(1 if failures else 0)
