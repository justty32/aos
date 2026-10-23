#!/usr/bin/env python3
"""test_cli.py：aos-directive 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-directive

每個案例開一個空資料夾、擺好檔、從 stdin 餵一份 JSON，看退出碼與 stdout（或 stderr 的錯誤代號）。
"""
import json
import os
import subprocess
import sys
import tempfile

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "bin",
                                                                          "aos-directive"))


def run(stdin, files=None, args=(), env=None, links=None):
    """在空資料夾跑一次，回 (退出碼, stdout 第一行解成 JSON 或 None, 錯誤代號或 None)。"""
    with tempfile.TemporaryDirectory() as work:
        for name, doc in (files or {}).items():
            path = os.path.join(work, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(doc if isinstance(doc, str) else json.dumps(doc))
        for name, target in (links or {}).items():      # 捷徑：name → target（相對於 name 所在資料夾）
            path = os.path.join(work, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.symlink(target, path)
        r = subprocess.run([BIN, *args], cwd=work, input=stdin if isinstance(stdin, str) else json.dumps(stdin),
                           capture_output=True, text=True, env=dict(os.environ, **(env or {})))
        out = json.loads(r.stdout) if r.returncode == 0 else None
        err = json.loads(r.stderr)["error"]["code"] if r.returncode == 1 else None
        return r.returncode, out, err, r.stdout


failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


# 沒有指示詞：原樣、key 順序照原本、排版同 Python json.dumps
rc, out, err, raw = run('{"b": 1, "a": [true, null, "中"]}')
check("原樣", raw, '{"b": 1, "a": [true, null, "中"]}\n')

# $ref 整份檔
check("$ref", run({"x": {"$ref": "a.json"}}, {"a.json": [1, 2]})[:3], (0, {"x": [1, 2]}, None))
# 巢狀 $ref：從寫著它的那個檔所在的資料夾算
files = {"refs/a.json": {"y": {"$ref": "sub/b.json"}}, "refs/sub/b.json": {"z": {"$ref": "../c.json"}},
         "refs/c.json": "\"deep\""}
check("巢狀 $ref", run({"x": {"$ref": "refs/a.json"}}, files)[:3], (0, {"x": {"y": {"z": "deep"}}}, None))
# 巢狀 $ref 不是從 cwd 算
check("巢狀 $ref 不從 cwd 算", run({"x": {"$ref": "refs/a.json"}}, {"refs/a.json": {"$ref": "refs/b.json"},
                                                                  "refs/b.json": "1"})[:3],
      (1, None, "DirectiveBad"))
# 被 $ref 的檔是捷徑：它裡面的 $ref 從捷徑實際指向的檔所在的資料夾算
check("捷徑解開", run({"x": {"$ref": "a/x.json"}}, {"lib/x.json": {"$ref": "y.json"}, "lib/y.json": "\"lib\"",
                                                 "a/y.json": "\"a\""}, links={"a/x.json": "../lib/x.json"})[:3],
      (0, {"x": "lib"}, None))
# $ref 取檔內位置（10-20 ideas D1、D7；修飾詞 10-23 起叫 $at）：檔#/指標、$at、兩個都寫＝$at 接在後面；~0／~1 跳脫；陣列索引
data = {"a.json": {"k": {"m": [10, 20]}, "s~/x": "esc", "msg": "hi"}}
check("#/ 指標", run({"x": {"$ref": "a.json#/k/m/1"}}, data)[:3], (0, {"x": 20}, None))
check("$at", run({"x": {"$ref": "a.json", "$at": "/k"}}, data)[:3], (0, {"x": {"m": [10, 20]}}, None))
check("#/ 再接 $at", run({"x": {"$ref": "a.json#/k", "$at": "/m/0"}}, data)[:3], (0, {"x": 10}, None))
check("$at 空字串", run({"x": {"$ref": "a.json#/msg", "$at": ""}}, data)[:3], (0, {"x": "hi"}, None))
check("~0~1", run({"x": {"$ref": "a.json#/s~0~1x"}}, data)[:3], (0, {"x": "esc"}, None))
check("指不到", run({"x": {"$ref": "a.json#/zz"}}, data)[:3], (1, None, "DirectiveBad"))
check("索引前導 0 指不到", run({"x": {"$ref": "a.json#/k/m/01"}}, data)[:3], (1, None, "DirectiveBad"))
check("#! 第一行跳過", run({"x": {"$ref": "s.json#/a"}}, {"s.json": '#!/usr/bin/env x\n{"a": 1}'})[:3],
      (0, {"x": 1}, None))
# 同一檔不同指標不算繞圈；同一檔同一指標才算
check("同檔不同指標", run({"x": {"$ref": "a.json#/p"}}, {"a.json": {"p": {"$ref": "a.json#/q"}, "q": 5}})[:3],
      (0, {"x": 5}, None))
check("同檔同指標繞圈", run({"x": {"$ref": "a.json#/p"}}, {"a.json": {"p": {"$ref": "a.json#/p"}}})[:3],
      (1, None, "DirectiveBad"))
# $env
check("$env", run({"x": {"$env": "AOS_DIR_TEST"}}, env={"AOS_DIR_TEST": "v"})[:3], (0, {"x": "v"}, None))
check("$env 沒有", run({"x": {"$env": "AOS_DIR_TEST_NOPE"}})[:3], (1, None, "DirectiveBad"))
# $path、$prefix（D9、D10）：字串拼接（10-21 傍晚 ideas § 9：# 開頭直接接、其他中間剛好一個 /、絕對路徑也是接上去）、再加前綴；$env、$ref 都能帶
E = {"AOS_DIR_TEST": "/s"}
check("$path", run({"x": {"$env": "AOS_DIR_TEST", "$path": "plan"}}, env=E)[:3], (0, {"x": "/s/plan"}, None))
check("$path 值結尾 /", run({"x": {"$env": "AOS_DIR_TEST", "$path": "a/b"}}, env={"AOS_DIR_TEST": "/s/"})[:3],
      (0, {"x": "/s/a/b"}, None))
check("$path 絕對也是接上去", run({"x": {"$env": "AOS_DIR_TEST", "$path": "/abs/p"}}, env=E)[:3], (0, {"x": "/s/abs/p"}, None))
check("$path # 開頭直接接", run({"x": {"$env": "AOS_DIR_TEST", "$path": "#/a"}}, env={"AOS_DIR_TEST": "/s/x.json"})[:3],
      (0, {"x": "/s/x.json#/a"}, None))
check("$path 兩邊多個 /", run({"x": {"$env": "AOS_DIR_TEST", "$path": "//a"}}, env={"AOS_DIR_TEST": "/s//"})[:3],
      (0, {"x": "/s/a"}, None))
check("$path 空字串＝不接", run({"x": {"$env": "AOS_DIR_TEST", "$path": ""}}, env={"AOS_DIR_TEST": "/s/"})[:3],
      (0, {"x": "/s/"}, None))
check("$path 值是 /", run({"x": {"$env": "AOS_DIR_TEST", "$path": "a"}}, env={"AOS_DIR_TEST": "/"})[:3],
      (0, {"x": "/a"}, None))
check("$path＋$prefix", run({"x": {"$env": "AOS_DIR_TEST", "$path": "a.txt", "$prefix": "--file="}}, env=E)[:3],
      (0, {"x": "--file=/s/a.txt"}, None))
check("只有 $prefix", run({"x": {"$env": "AOS_DIR_TEST", "$prefix": "-C"}}, env=E)[:3], (0, {"x": "-C/s"}, None))
check("$path／$prefix null", run({"x": {"$env": "AOS_DIR_TEST", "$path": None, "$prefix": None}}, env=E)[:3],
      (0, {"x": "/s"}, None))
check("$ref 字串＋$path＋$prefix", run({"x": {"$ref": "a.json#/msg", "$path": "x", "$prefix": "p="}}, data)[:3],
      (0, {"x": "p=hi/x"}, None))
check("$ref 不是字串：$path／$prefix 靜默", run({"x": {"$ref": "a.json#/k/m/0", "$path": "x", "$prefix": "p"}},
                                              data)[:3], (0, {"x": 10}, None))
check("舊的 path 不作用", run({"x": {"$env": "AOS_DIR_TEST", "path": "plan"}}, env=E)[:3], (0, {"x": "/s"}, None))
check("$path 變數沒設", run({"x": {"$env": "AOS_DIR_TEST_NOPE", "$path": "p"}})[:3], (1, None, "DirectiveBad"))
# $ref 指到資料夾＝讀不到、算錯（10-21 傍晚 ideas § 9「維持報錯」；不走進去找入口）
for x in ({"$ref": "dir"}, {"$ref": "dir#/k"}, {"$ref": "dir", "$at": "/k"}):
    check("$ref 指到資料夾 %r" % (x,), run({"x": x}, {"dir/_entry.json": {"k": 1}})[:3], (1, None, "DirectiveBad"))
# 寫法寬容（D14）：當沒寫
check("$path／$prefix 型別不對", run({"x": {"$env": "AOS_DIR_TEST", "$path": 3, "$prefix": ["x"]}}, env=E)[:3],
      (0, {"x": "/s"}, None))
check("$at 型別不對", run({"x": {"$ref": "a.json#/msg", "$at": 3}}, data)[:3], (0, {"x": "hi"}, None))
check("$at 不是 / 開頭", run({"x": {"$ref": "a.json#/msg", "$at": "k"}}, data)[:3], (0, {"x": "hi"}, None))
# 10-23 命名統合：沒帶 $ 的 at 是普通 key、不作用（不認得的 key 不管）
check("舊的 at 不作用", run({"x": {"$ref": "a.json#/k", "at": "/m/0"}}, data)[:3], (0, {"x": {"m": [10, 20]}}, None))
check("不認得的 $xxx 不管", run({"x": {"$env": "AOS_DIR_TEST", "$fmt": "%s", "$nope": 1}}, env=E)[:3],
      (0, {"x": "/s"}, None))
check("沒 $ref／$env 的物件照常往下解", run({"x": {"$fmt": "x", "a": {"$env": "AOS_DIR_TEST"}}}, env=E)[:3],
      (0, {"x": {"$fmt": "x", "a": "/s"}}, None))
# 寫法寬容（D15）：換不了、整個物件原封不動
for name, d in (("$ref 不是字串", {"$ref": 3}), ("$ref 空字串", {"$ref": ""}), ("只有 #/", {"$ref": "#/s"}),
                ("# 後不是 /", {"$ref": "a.json#s"}), ("檔#", {"$ref": "a.json#"}), ("$env 不是字串", {"$env": 3}),
                ("$env 空字串", {"$env": ""}), ("$env null", {"$env": None, "$path": "a"}),
                ("有 $ref 只看 $ref", {"$ref": 3, "$env": "AOS_DIR_TEST"}),
                ("裡面不解", {"$ref": 3, "a": {"$env": "AOS_DIR_TEST"}})):
    check("原封不動：" + name, run({"x": d}, data, env=E)[:3], (0, {"x": d}, None))
# 找不到檔、壞 JSON、繞圈
check("找不到檔", run({"x": {"$ref": "nope.json"}})[:3], (1, None, "DirectiveBad"))
check("壞 JSON", run({"x": {"$ref": "bad.json"}}, {"bad.json": "{"})[:3], (1, None, "DirectiveBad"))
check("繞圈", run({"x": {"$ref": "a.json"}}, {"a.json": {"$ref": "b.json"}, "b.json": {"$ref": "a.json"}})[:3],
      (1, None, "DirectiveBad"))
# $ref 陣列（10-23 使用者「"$ref":["a.json", "b.json#/c/d]"」）：幾份照順序合成一份
M = {"a.json": {"x": 1, "y": {"p": 1}}, "b.json": {"c": {"d": {"y": {"q": 2}, "z": 3}}}, "l1.json": [1, 2],
     "l2.json": {"k": [3]}, "s.json": "\"str\"", "n.json": "5",
     "sub/r.json": {"v": {"$ref": "t.json"}}, "sub/t.json": "\"sub-t\"", "t.json": "\"top-t\""}
check("$ref 陣列：合物件、後面的蓋前面的（淺層）", run({"o": {"$ref": ["a.json", "b.json#/c/d"]}}, M)[:3],
      (0, {"o": {"x": 1, "y": {"q": 2}, "z": 3}}, None))
check("$ref 陣列：同名 key 位置留在第一次", run({"o": {"$ref": ["a.json", "b.json#/c/d"]}}, M)[3],
      '{"o": {"x": 1, "y": {"q": 2}, "z": 3}}\n')
check("$ref 陣列：接陣列", run({"o": {"$ref": ["l1.json", "l2.json#/k", "l1.json"]}}, M)[:3],
      (0, {"o": [1, 2, 3, 1, 2]}, None))
check("$ref 陣列：只有一份＝它本身", run({"o": {"$ref": ["s.json"], "$path": "x"}}, M)[:3], (0, {"o": "str/x"}, None))
check("$ref 陣列：$at 接在每一份後面", run({"o": {"$ref": ["b.json#/c", "a.json"], "$at": "/d"}},
                                          {"a.json": {"d": {"w": 0}}, "b.json": {"c": {"d": {"z": 3}}}})[:3],
      (0, {"o": {"z": 3, "w": 0}}, None))
check("$ref 陣列：每一份裡的 $ref 從它自己的資料夾算", run({"o": {"$ref": ["sub/r.json", "a.json"]}}, M)[:3],
      (0, {"o": {"v": "sub-t", "x": 1, "y": {"p": 1}}}, None))
check("$ref 陣列：物件與陣列混在一起", run({"o": {"$ref": ["a.json", "l1.json"]}}, M)[:3], (1, None, "DirectiveBad"))
check("$ref 陣列：兩份字串合不起來", run({"o": {"$ref": ["s.json", "s.json"]}}, M)[:3], (1, None, "DirectiveBad"))
check("$ref 陣列：兩份數字合不起來", run({"o": {"$ref": ["n.json", "n.json"]}}, M)[:3], (1, None, "DirectiveBad"))
check("$ref 陣列：有一份讀不到", run({"o": {"$ref": ["a.json", "nope.json"]}}, M)[:3], (1, None, "DirectiveBad"))
check("$ref 陣列：有一份指不到", run({"o": {"$ref": ["a.json", "b.json#/zz"]}}, M)[:3], (1, None, "DirectiveBad"))
check("$ref 陣列：繞圈", run({"o": {"$ref": ["a.json", "c.json"]}}, dict(M, **{"c.json": {"$ref": ["a.json", "c.json"]}}))[:3],
      (1, None, "DirectiveBad"))
check("$ref 陣列：同一份寫兩次不算繞圈", run({"o": {"$ref": ["a.json", "a.json"]}}, M)[:3],
      (0, {"o": {"x": 1, "y": {"p": 1}}}, None))
for name, d in (("空陣列", {"$ref": []}), ("元素不是字串", {"$ref": ["a.json", 3]}), ("元素空字串", {"$ref": ["a.json", ""]}),
                ("元素只有 #/", {"$ref": ["a.json", "#/x"]}), ("元素 # 後不是 /", {"$ref": ["a.json", "b.json#c"]}),
                ("元素是陣列", {"$ref": [["a.json"]]})):
    check("$ref 陣列原封不動：" + name, run({"o": d}, M)[:3], (0, {"o": d}, None))
# stdin：空＝{}、多份＝InputExtra、解不出來＝InputBad；參數＝ArgumentsBad
check("stdin 空", run("")[:3], (0, {}, None))
check("stdin 多份", run("{} {}")[:3], (1, None, "InputExtra"))
check("stdin 壞", run("{")[:3], (1, None, "InputBad"))
check("參數", run("{}", args=["x"])[:3], (1, None, "ArgumentsBad"))

if failures:
    print("test_cli：%d 個失敗" % failures)
    sys.exit(1)
print("test_cli：全部通過")
