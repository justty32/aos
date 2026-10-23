#!/usr/bin/env python3
"""test_cli.py：aos-util 三扇門的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py build/util_cli

util_cli＝stdin 讀一份 JSON（aos::read_stdin）、原樣印出（aos::emit）、出錯印錯誤（aos::emit_error）。
"""
import json
import subprocess
import sys

BIN = sys.argv[1]
failures = 0


def check(name, stdin, rc, out=None, err=None):
    global failures
    r = subprocess.run([BIN], input=stdin, capture_output=True, text=True)
    got = (r.returncode, r.stdout if out is not None else None,
           json.loads(r.stderr)["error"]["code"] if err is not None and r.stderr else None)
    want = (rc, out, err)
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


# emit 排版＝Python json.dumps(v, ensure_ascii=False)：", "、": "、key 照原順序、非 ASCII 原樣
doc = '{"z": 1, "a": [true, false, null, 1.5, -2, "中\\"文"], "m": {}, "e": []}'
check("emit 排版", doc, 0, json.dumps(json.loads(doc), ensure_ascii=False) + "\n")
check("跨行", '\n{\n "a":\n 1\n}\n', 0, '{"a": 1}\n')
check("壞尾丟掉", '{"a": 1} {"bad', 0, '{"a": 1}\n')
check("空＝{}", "", 0, "{}\n")
check("只有空白＝{}", "  \n\t", 0, "{}\n")
check("多份＝InputExtra", "{} {}", 1, err="InputExtra")
check("解不出來＝InputBad", "{", 1, err="InputBad")

if failures:
    print("test_cli：%d 個失敗" % failures)
    sys.exit(1)
print("test_cli：全部通過")
