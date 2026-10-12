#!/usr/bin/env python3
"""inst：讀一份 JSON、用指示詞 lib 解好、挑認得的 key、跑一次。純標準庫。

    python3 aos_inst.py TARGET [--base inst|cwd]

TARGET 是 `.json` 檔，或資料夾（找 `<資料夾>/.aos/inst.json`，沒有再找 `<資料夾>/inst.json`）。
`--base` 選相對路徑的基準：`inst`（預設）＝inst 的家（給資料夾就是那個資料夾，給檔案就是檔案所在的資料夾）；
`cwd`＝呼叫者現在的工作目錄。指示詞的相對檔名、`cwd`、`stdin`／`stdout`／`stderr` 的相對路徑全部從這裡算。

認得的 key（其他一律忽略）：

    argv            非空字串陣列（必填）
    cwd             在哪跑（沒寫＝基準）；cwd_mkdir: true 先建好
    envs            {名字: 字串}，疊在現有環境上；envs_clear: true 改成從空的開始
    stdin           從哪個檔讀；stdin_inherit: true 改接呼叫者的
    stdout/stderr   寫到哪個檔（覆寫）；*_append 改附加、*_mkdir 先建上層資料夾、*_inherit 改接呼叫者的
    stderr_merge    true＝stderr 併進 stdout

沒寫的串流一律接 /dev/null。布林 key 沒寫＝false。

`run()` 回子程式的結束碼（被訊號殺掉＝128+N；找不到程式＝127、不能執行＝126）。
命令列：inst 自己出錯（讀不到、格式不對、指示詞解不開）印一行到 stderr、退出碼 125。
"""
import json
import os
import subprocess
import sys

from aos_directives import DirectiveError, resolve

__all__ = ["InstError", "find", "load", "parse", "run"]

_BOOLS = ("cwd_mkdir", "envs_clear", "stdin_inherit",
          "stdout_append", "stdout_mkdir", "stdout_inherit",
          "stderr_append", "stderr_mkdir", "stderr_inherit", "stderr_merge")


class InstError(Exception):
    """這份 inst 被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。指示詞的錯照原代號包進來。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def find(target):
    """TARGET → (inst.json 的路徑, inst 的家)。"""
    if os.path.isdir(target):
        for p in (os.path.join(target, ".aos", "inst.json"), os.path.join(target, "inst.json")):
            if os.path.isfile(p):
                return p, os.path.abspath(target)
        raise InstError("NotFound", "%s 裡沒有 .aos/inst.json 也沒有 inst.json" % target)
    return target, os.path.dirname(os.path.abspath(target))


def load(target, base="inst"):
    """讀 TARGET 的 inst，回 `parse()` 的結果。`base`＝"inst" 或 "cwd"。"""
    if base not in ("inst", "cwd"):
        raise InstError("BadBase", "base 只能是 inst 或 cwd，不是 %r" % (base,))
    path, home = find(target)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        doc = json.loads(raw)
    except ValueError as e:
        raise InstError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))
    return parse(doc, home if base == "inst" else os.getcwd())


def parse(doc, base_dir):
    """解指示詞、驗認得的 key，回一個欄位都填好的 dict（路徑都是絕對的，None＝沒寫）。"""
    base_dir = os.path.abspath(base_dir)
    try:
        doc = resolve(doc, base_dir)
    except DirectiveError as e:
        raise InstError(e.code, e.msg)
    if not isinstance(doc, dict):
        raise InstError("FieldType", "inst 要是物件，不是 %s" % type(doc).__name__)
    inst = {k: _bool(doc, k) for k in _BOOLS}

    argv = doc.get("argv")
    if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
        raise InstError("FieldType", "argv 要是非空的字串陣列，不是 %r" % (argv,))
    inst["argv"] = argv

    envs = doc.get("envs", {})
    if not (isinstance(envs, dict) and all(isinstance(v, str) for v in envs.values())):
        raise InstError("FieldType", "envs 要是 {名字: 字串}，不是 %r" % (envs,))
    inst["envs"] = envs

    for k in ("cwd", "stdin", "stdout", "stderr"):
        v = doc.get(k)
        if v is not None and not isinstance(v, str):
            raise InstError("FieldType", "%s 要是字串路徑，不是 %r" % (k, v))
        inst[k] = None if v is None else os.path.join(base_dir, v)
    if inst["cwd"] is None:
        inst["cwd"] = base_dir

    for k in ("stdin", "stdout", "stderr"):
        if inst[k + "_inherit"] and inst[k] is not None:
            raise InstError("Conflict", "%s 跟 %s_inherit 只能二選一" % (k, k))
    if inst["stderr_merge"] and (inst["stderr"] is not None or inst["stderr_inherit"]):
        raise InstError("Conflict", "stderr_merge 不能再寫 stderr 或 stderr_inherit")
    return inst


def _bool(doc, k):
    v = doc.get(k, False)
    if not isinstance(v, bool):
        raise InstError("FieldType", "%s 要是 true／false，不是 %r" % (k, v))
    return v


def run(inst):
    """照 `parse()` 的結果跑一次，等它結束，回結束碼。"""
    if inst["cwd_mkdir"]:
        os.makedirs(inst["cwd"], exist_ok=True)
    env = dict(inst["envs"]) if inst["envs_clear"] else dict(os.environ, **inst["envs"])
    opened = []
    try:
        stdin = _stream(inst, "stdin", opened)
        stdout = _stream(inst, "stdout", opened)
        stderr = subprocess.STDOUT if inst["stderr_merge"] else _stream(inst, "stderr", opened)
        try:
            code = subprocess.run(inst["argv"], cwd=inst["cwd"], env=env,
                                  stdin=stdin, stdout=stdout, stderr=stderr).returncode
        except FileNotFoundError:
            return 127
        except PermissionError:
            return 126
        return 128 - code if code < 0 else code
    finally:
        for f in opened:
            f.close()


def _stream(inst, k, opened):
    """一個串流要接什麼：None＝接呼叫者的；否則開檔（沒寫路徑就是 /dev/null）。"""
    if inst[k + "_inherit"]:
        return None
    path = inst[k] or os.devnull
    if k == "stdin":
        f = open(path, "rb")
    else:
        if inst[k] and inst[k + "_mkdir"]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        f = open(path, "ab" if inst[k + "_append"] else "wb")
    opened.append(f)
    return f


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    base = "inst"
    if len(args) == 3 and args[1] == "--base":
        args, base = args[:1], args[2]
    if len(args) != 1:
        print("用法：aos_inst.py TARGET [--base inst|cwd]", file=sys.stderr)
        return 125
    try:
        return run(load(args[0], base))
    except InstError as e:
        print(e, file=sys.stderr)
        return 125
    except OSError as e:
        print("OpenFailed: %s" % e, file=sys.stderr)
        return 125


if __name__ == "__main__":
    sys.exit(main())
