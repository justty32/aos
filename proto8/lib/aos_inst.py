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
    exit            子程式跑完，把它的結束碼（十進位＋換行）寫進這個檔；
                    exit_append 改附加一行、exit_mkdir 先建上層資料夾

沒寫的串流一律接 /dev/null。布林 key 沒寫＝false。

JSON 只寫跟呼叫者不一樣的地方，其他一律從 aos_inst 本身繼承：子程式留在 aos_inst 的行程群組與 session，
終端機的 Ctrl-C、`timeout` 指令這類整群送的訊號，子程式和 aos_inst 一起收到。
要限時、要清孫程式，由啟動 aos_inst 的人決定（例如 `timeout -k 2 5 aos_inst.py x`，或起在新群組裡整群砍）。
Python 呼叫者沒辦法從外面砍，所以 `run()` 只留非在裡面做不可的開關（見 `run()`）。

子程式的結束碼只走 `exit` 檔：自己結束＝它的碼；被訊號停掉＝128＋訊號號碼（SIGTERM＝143、SIGKILL＝137）。
根本沒起來就不寫。exit 寫不進去不管，不算錯。
`run()` 不回東西；aos_inst 自己出錯（單子有問題、程式找不到、檔打不開…）丟 `InstError`。

命令列的退出碼只說 aos_inst 自己的狀況：0＝子程式跑完了（不管它成功失敗）；
1＝aos_inst 自己出錯、子程式沒跑（stderr 印一行「代號: 白話」）。
命令列收到 SIGINT／SIGTERM／SIGHUP 自己不死，轉給子程式，照樣等它結束、寫 exit。
"""
import json
import os
import signal
import subprocess
import sys
import time

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
    """TARGET → inst.json 的路徑（realpath：絕對、沒有 . 與 ..、捷徑都解開；同一份檔永遠得到同一個字串）。"""
    if os.path.isdir(target):
        for p in (os.path.join(target, ".aos", "inst.json"), os.path.join(target, "inst.json")):
            if os.path.isfile(p):
                return os.path.realpath(p)
        raise InstError("NotFound", "%s 裡沒有 .aos/inst.json 也沒有 inst.json" % target)
    return os.path.realpath(target)


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


_FORWARDED = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
_POLL = 0.05


def run(inst, timeout_ms=None, grace_ms=2000, forward_signals=False, stop=None):
    """照 `parse()` 的結果跑一次，等它結束，寫 exit 檔。不回東西；aos_inst 自己出錯丟 `InstError`。

    開關只留非在 run() 裡做不可的（只有 run() 手上有子程式）：
      timeout_ms       最多等幾毫秒（正整數；None＝不限），時間到就收掉子程式
      grace_ms         收掉＝先 SIGTERM，過了 grace_ms 還沒結束再 SIGKILL（非負整數；0＝直接 SIGKILL）
      forward_signals  True＝跑的期間 SIGINT／SIGTERM／SIGHUP 不打斷呼叫者，轉給子程式（只能在主執行緒）
      stop             停止鈕（例如 threading.Event，有 is_set() 就行）；別的執行緒按下去，就收掉子程式
    等的時候被打斷（例外穿過來）：先收掉子程式、寫 exit，再把原本的例外丟出去。"""
    if not (timeout_ms is None or _int(timeout_ms) and timeout_ms > 0):
        raise ValueError("timeout_ms 要是正整數或 None，不是 %r" % (timeout_ms,))
    if not (_int(grace_ms) and grace_ms >= 0):
        raise ValueError("grace_ms 要是非負整數，不是 %r" % (grace_ms,))
    child = None
    pending = []

    def forward(signum, frame):
        if child is None:
            pending.append(signum)      # 還沒起來，起來再補送
        else:
            child.send_signal(signum)

    old = {sig: signal.signal(sig, forward) for sig in _FORWARDED} if forward_signals else {}
    try:
        child = _start(inst)
        for sig in pending:
            child.send_signal(sig)
        interrupted = None
        try:
            code = _wait(child, timeout_ms, grace_ms, stop)
        except BaseException as e:
            interrupted = e
            code = _stop(child, grace_ms)
        if inst["exit"] is not None:
            try:
                _write_exit(inst["exit"], code if code >= 0 else 128 - code, inst["exit_append"], inst["exit_mkdir"])
            except OSError:
                pass        # 寫不進去不管
        if interrupted is not None:
            raise interrupted
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _start(inst):
    """建 cwd、開串流、起子程式，回 Popen。"""
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
            return subprocess.Popen(inst["argv"], cwd=inst["cwd"], env=env,
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


def _wait(child, timeout_ms, grace_ms, stop):
    """等子程式結束（timeout_ms＝None 不限時）；超時或 stop 被按下就 `_stop`。
    有 stop 時每 _POLL 秒看一次。回 returncode：自己結束＝它的碼，被訊號停掉＝負的訊號號碼。"""
    deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000
    while True:
        step = None if stop is None else _POLL
        if deadline is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                return _stop(child, grace_ms)
            step = left if step is None else min(step, left)
        try:
            return child.wait(step)
        except subprocess.TimeoutExpired:
            if stop is not None and stop.is_set():
                return _stop(child, grace_ms)


def _stop(child, grace_ms):
    """SIGTERM，等 grace_ms 還沒結束就 SIGKILL（grace_ms＝0 直接 SIGKILL）。回 returncode。
    收的途中再被打斷就不等 grace，直接 SIGKILL。"""
    if grace_ms:
        child.terminate()
        try:
            return child.wait(grace_ms / 1000)
        except BaseException:
            pass
    child.kill()
    while True:
        try:
            return child.wait()
        except BaseException:
            pass


def _write_exit(path, code, append, mkdir):
    """結束碼寫成「十進位＋換行」。"""
    if mkdir:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a" if append else "w") as f:
        f.write("%d\n" % code)


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
        run(load(args[0]), forward_signals=True)
        return 0
    except InstError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
