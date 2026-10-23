#!/usr/bin/env python3
"""test_cli.py：aos-schema 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-schema

每個案例：餵一個 schema 檔與一份 stdin，看退出碼、stdout 解成的 JSON（或 stderr 的錯誤代號）。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "bin", "aos-schema"))
DATA = os.path.join(HERE, "data")
INST_SCHEMA = os.path.join(HERE, "..", "examples", "inst.schema.json")

failures = 0


def run(args, stdin_path):
    """跑一次，回 (退出碼, stdout 解成 JSON 或 None, 錯誤代號或 None, 原始 stdout)。"""
    with open(stdin_path, "rb") as f:
        r = subprocess.run([BIN, *args], stdin=f, capture_output=True, text=True)
    out = json.loads(r.stdout) if r.returncode == 0 and r.stdout else None
    err = json.loads(r.stderr)["error"]["code"] if r.returncode == 1 and r.stderr else None
    return r.returncode, out, err, r.stdout


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


def pointers(out):
    return [p["pointer"] for p in out["problems"]]


# 驗過：stdout 一行、排版同 Python json.dumps、退 0
rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "inst_ok.json"))
check("valid", (rc, raw, err), (0, '{"valid": true, "problems": []}\n', None))

# stdin 空＝{}：缺 argv，報在整份（""）
rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "empty.txt"))
check("empty_stdin", (rc, out["valid"], pointers(out), "argv" in out["problems"][0]["message"]), (0, False, [""], True))

rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "inst_no_argv.json"))
check("missing_required", (rc, out["valid"], pointers(out), "argv" in out["problems"][0]["message"]),
      (0, False, [""], True))

# 這兩份資料各有不止一個問題；只看該報的那格有沒有在清單裡
rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "inst_bad_type.json"))
check("wrong_type", (rc, out["valid"], "/argv/1" in pointers(out)), (0, False, True))

rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "inst_bad_timeout.json"))
check("out_of_range", (rc, out["valid"], "/timeout_ms" in pointers(out)), (0, False, True))

# 壞尾丟掉：前面那份算
rc, out, err, raw = run([INST_SCHEMA], os.path.join(DATA, "tail_garbage.txt"))
check("tail_garbage", (rc, out["valid"]), (0, True))

# 工具自己出錯：stderr 一行、退 1
check("input_extra", run([INST_SCHEMA], os.path.join(DATA, "two_docs.txt"))[:3], (1, None, "InputExtra"))
check("input_bad_json", run([INST_SCHEMA], os.path.join(DATA, "broken.txt"))[:3], (1, None, "InputBad"))
check("schema_bad", run([os.path.join(DATA, "bad.schema.json")], os.path.join(DATA, "inst_ok.json"))[:3],
      (1, None, "SchemaBad"))
check("file_missing", run([os.path.join(DATA, "no_such.json")], os.path.join(DATA, "inst_ok.json"))[:3],
      (1, None, "SchemaMissing"))
check("schema_not_json", run([os.path.join(DATA, "broken.txt")], os.path.join(DATA, "inst_ok.json"))[:3],
      (1, None, "SchemaBad"))
check("usage", run([], "/dev/null")[:3], (1, None, "ArgumentsBad"))

if failures:
    print("test_cli：%d 個失敗" % failures)
    sys.exit(1)
print("test_cli：全部通過")
