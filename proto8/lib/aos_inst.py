#!/usr/bin/env python3
"""inst：讀一份 JSON、用指示詞 lib 解好、挑認得的 key、跑一次。純標準庫。

    python3 aos_inst.py TARGET

TARGET 是 `.json` 檔，或資料夾（找 `<資料夾>/.aos/inst.json`，沒有再找 `<資料夾>/inst.json`）。
相對路徑的基準一律是呼叫者現在的工作目錄：指示詞的相對檔名、`cwd` 這個 key 從這裡算；
`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。

認得的 key（其他一律忽略）：

    argv            非空字串陣列（必填）
    cwd             在哪跑（沒寫＝呼叫 aos_inst 時的 cwd）；cwd_mkdir: true 先建好
    envs            {名字: 字串}，疊在現有環境上；envs_clear: true 改成從空的開始
    stdin           從哪個檔讀；stdin_inherit: true 改接呼叫者的
    stdout/stderr   寫到哪個檔（覆寫）；*_append 改附加、*_mkdir 先建上層資料夾、*_inherit 改接呼叫者的
    stderr_merge    true＝stderr 併進 stdout
    exit            子程式跑完，把它的結束碼（十進位＋換行）寫進這個檔，並確實存到磁碟；
                    exit_append 改附加一行、exit_mkdir 先建上層資料夾
    timeout_ms      最多跑幾毫秒（非負整數；沒寫或 0＝不限）。時間到先送 SIGTERM，
                    過了 timeout_grace_ms 還沒結束再送 SIGKILL
    timeout_grace_ms  SIGTERM 之後等幾毫秒才 SIGKILL（非負整數；沒寫＝2000；0＝直接 SIGKILL）

沒寫的串流一律接 /dev/null。布林 key 沒寫＝false。

子程式的結束碼只走 `exit` 檔，而且只有它自己結束時才寫：被訊號停掉（含逾時被停）、
或根本沒起來，都不寫 `exit`——aos 不替它代寫。
exit 寫不進去不管，不算錯。
`run()` 回子程式的結束碼給 Python 呼叫者；aos_inst 自己出錯（單子有問題、程式找不到、檔打不開…）丟 `InstError`。

命令列的退出碼只說 aos_inst 自己的狀況：0＝子程式跑完了（不管它成功失敗）；
1＝aos_inst 自己出錯、子程式沒跑（stderr 印一行「代號: 白話」）。
"""
import json
import os
import subprocess
import sys

from aos_directives import DirectiveError, resolve

__all__ = ["InstError", "find", "load", "parse", "run"]

_BOOLS = ("cwd_mkdir", "envs_clear", "stdin_inherit",
          "stdout_append", "stdout_mkdir", "stdout_inherit",
          "stderr_append", "stderr_mkdir", "stderr_inherit", "stderr_merge",
          "exit_append", "exit_mkdir")


class InstError(Exception):
    """這份 inst 被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。指示詞的錯照原代號包進來。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def find(target):
    """TARGET → inst.json 的路徑。"""
    if os.path.isdir(target):
        for p in (os.path.join(target, ".aos", "inst.json"), os.path.join(target, "inst.json")):
            if os.path.isfile(p):
                return p
        raise InstError("NotFound", "%s 裡沒有 .aos/inst.json 也沒有 inst.json" % target)
    return target


def load(target):
    """讀 TARGET 的 inst，以呼叫者現在的 cwd 為基準，回 `parse()` 的結果。"""
    path = find(target)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        doc = json.loads(raw)
    except ValueError as e:
        raise InstError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))
    return parse(doc, os.getcwd())


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

    for k, default in (("timeout_ms", 0), ("timeout_grace_ms", 2000)):
        t = doc.get(k, default)
        if not (isinstance(t, int) and not isinstance(t, bool) and t >= 0):
            raise InstError("FieldType", "%s 要是非負整數，不是 %r" % (k, t))
        inst[k] = t

    # cwd 從基準算，沒寫＝呼叫者現在的 cwd；三個串流與 exit 從解出來的 cwd 算
    for k in ("cwd", "stdin", "stdout", "stderr", "exit"):
        v = doc.get(k)
        if v is not None and not isinstance(v, str):
            raise InstError("FieldType", "%s 要是字串路徑，不是 %r" % (k, v))
        if k == "cwd":
            inst[k] = os.getcwd() if v is None else os.path.join(base_dir, v)
        else:
            inst[k] = None if v is None else os.path.join(inst["cwd"], v)

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
    """照 `parse()` 的結果跑一次，等它結束，寫 exit 檔。aos_inst 自己出錯丟 `InstError`。

    回 returncode：自己結束＝它的碼，被訊號停掉＝負的訊號號碼（例如 -9），這時不寫 exit。"""
    try:
        if inst["cwd_mkdir"]:
            os.makedirs(inst["cwd"], exist_ok=True)
    except OSError as e:
        raise InstError("MkdirFailed", "建不了 cwd %s：%s" % (inst["cwd"], e))
    if not os.path.isdir(inst["cwd"]):
        raise InstError("CwdMissing", "cwd %s 不是資料夾" % inst["cwd"])
    env = dict(inst["envs"]) if inst["envs_clear"] else dict(os.environ, **inst["envs"])
    opened = []
    try:
        try:
            stdin = _stream(inst, "stdin", opened)
            stdout = _stream(inst, "stdout", opened)
            stderr = subprocess.STDOUT if inst["stderr_merge"] else _stream(inst, "stderr", opened)
        except OSError as e:
            raise InstError("OpenFailed", "串流開不了：%s" % e)
        try:
            child = subprocess.Popen(inst["argv"], cwd=inst["cwd"], env=env,
                                     stdin=stdin, stdout=stdout, stderr=stderr)
        except FileNotFoundError:
            raise InstError("CommandNotFound", "找不到要跑的程式 %s" % inst["argv"][0])
        except PermissionError:
            raise InstError("CommandNotExecutable", "%s 不能執行" % inst["argv"][0])
        except OSError as e:
            raise InstError("LaunchFailed", "起不了 %s：%s" % (inst["argv"][0], e))
    finally:
        for f in opened:
            f.close()
    code = _wait(child, inst["timeout_ms"], inst["timeout_grace_ms"])
    if inst["exit"] is not None and code >= 0:
        try:
            _write_exit(inst["exit"], code, inst["exit_append"], inst["exit_mkdir"])
        except OSError:
            pass        # 寫不進去不管
    return code


def _wait(child, timeout_ms, grace_ms):
    """等子程式結束；超時先 SIGTERM，再等 grace_ms 還沒結束就 SIGKILL（grace_ms＝0 直接 SIGKILL）。
    回 returncode：自己結束＝它的碼，被訊號停掉＝負的訊號號碼。"""
    try:
        return child.wait(timeout_ms / 1000 if timeout_ms else None)
    except subprocess.TimeoutExpired:
        pass
    if grace_ms:
        child.terminate()
        try:
            return child.wait(grace_ms / 1000)
        except subprocess.TimeoutExpired:
            pass
    child.kill()
    return child.wait()


def _write_exit(path, code, append, mkdir):
    """結束碼寫成「十進位＋換行」，檔案與上層資料夾都 fsync，確定存到磁碟才算數。"""
    parent = os.path.dirname(path)
    if mkdir:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o644)
    try:
        os.write(fd, b"%d\n" % code)
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


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
    if len(args) != 1:
        print("用法：aos_inst.py TARGET", file=sys.stderr)
        return 1
    try:
        run(load(args[0]))
        return 0
    except InstError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
