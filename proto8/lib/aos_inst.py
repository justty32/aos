#!/usr/bin/env python3
"""inst：讀一份 JSON、用指示詞 lib 解好、挑認得的 key、跑一次。純標準庫。

    python3 aos_inst.py [--key 值 ...] [TARGET | -] [-- argv...]

設定從哪來照 aos_cli（NORMS N-12、D-1～D-3）：TARGET 檔、`-`＝stdin（JSON 串流只看第一份）、都沒給＝`{}`；
純量 key 都有同名旗標（`--timeout-ms 100`、`--cwd-mkdir true`…），蓋過檔或 stdin；`--` 後面整段蓋過 `argv`。
設定從 stdin 來時 `stdin_inherit` ＝Conflict（stdin 已經被設定用掉了，D-5）。

TARGET 是 `.json` 檔，或資料夾（找 `<資料夾>/$AOS_DIRNAME/inst.json`（沒設＝`.aos`），沒有再找 `<資料夾>/inst.json`）。
後面可以接 `#/位置`（JSON pointer，寫法同指示詞 `$ref`）：只跑那份檔裡那一格（要是物件）。遇到第一個 `#` 就切，
檔名含 `#` 的不支援；資料夾先照上面找到 inst.json 再套位置。那一格是整份檔的視窗：裡面 `$ref` 的位置照整份檔算。
相對路徑的基準一律是呼叫者現在的工作目錄：指示詞的相對檔名、`cwd` 這個 key 從這裡算；
`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。

認得的 key（其他一律忽略）：

    argv            非空字串陣列（必填）
    cwd             在哪跑（沒寫＝呼叫 aos_inst 時的 cwd）；cwd_mkdir: true 先建好
    envs            {名字: 字串}，疊在現有環境上；envs_clear: true 改成從空的開始
    stdin           從哪個檔讀；stdin_inherit: true 改接呼叫者的
    stdout/stderr   寫到哪個檔（覆寫）；*_append 改附加、*_mkdir 先建上層資料夾、*_inherit 改接呼叫者的
    stderr_merge    true＝stderr 併進 stdout
    exit            選填：子程式跑完，把它的結束碼（十進位＋換行）寫進這個檔（要碼讀 stdout 的結果就好，N-30）；
                    exit_append 改附加一行、exit_mkdir 先建上層資料夾
    timeout_ms      最多跑幾毫秒（正整數；沒寫或 null＝不限），到了就收掉
    grace_ms        收掉＝先 SIGTERM，過 grace_ms 還沒結束再 SIGKILL（非負整數；沒寫＝2000；0＝直接 SIGKILL）
    id              選填字串，原樣放進結果（沒寫＝TARGET 的 id；從 stdin 來又沒寫＝null）

沒寫的串流一律接 /dev/null。布林 key 沒寫＝false。

JSON 只寫跟呼叫者不一樣的地方，其他一律從 aos_inst 本身繼承：子程式留在 aos_inst 的行程群組與 session，
終端機的 Ctrl-C、`timeout` 指令這類整群送的訊號，子程式和 aos_inst 一起收到。
監工的事 aos_inst 不管：要從外面停它、要連孫程式一起清，由啟動 aos_inst 的人做——把 aos_inst 起在新的 session，
送 SIGTERM 給 aos_inst（它轉給子程式），過一段時間整群 SIGKILL（aos_loop 就這樣做）。

結果（N-12：stdout＝返回值）：跑完往 stdout 吐一份 JSON
    {"id", "code", "signal", "timed_out", "pid", "ms", "exit_file"}
code＝子程式的碼（被訊號停掉＝128＋訊號號碼，同 exit 檔）、signal＝訊號號碼或 null、timed_out＝被 timeout_ms 收掉、
pid＝子程式的 pid、ms＝跑了幾毫秒、exit_file＝exit 檔的路徑或 null。`run()` 回同一份 dict。
- `exit` 選填，寫了就照寫（與舊時代的橋樑，暫定 e；要子程式的碼讀上面那份結果的 code）：自己結束＝它的碼；被訊號停掉＝128＋訊號號碼（SIGTERM＝143、SIGKILL＝137）。
  根本沒起來就不寫。寫不進去不管，不算錯。
- aos_inst 自己的碼＝命令列退出碼／`run()` 有沒有丟例外：0＝正常做完（子程式回幾號、被限時收掉都算正常做完）；
  非 0＝aos_inst 自己出錯（單子有問題、程式找不到、檔打不開…），`run()` 丟 `InstError`，命令列 stderr 吐一份
  `{"error": {"code", "msg"}}`。數字只供參考，照 Unix 包裝程式（env、timeout）的慣例：127＝找不到程式、126＝不能執行、
  125＝其他（`exit_code()`）。
命令列（和在主執行緒呼叫的 `run()`）收到 SIGINT／SIGTERM／SIGHUP 自己不死，轉給子程式，照樣等它結束、寫 exit；
轉過去之後過 grace_ms 還沒結束就 SIGKILL。
"""
import os
import signal
import subprocess
import sys
import threading
import time

import aos_cli
from aos_cli import CliError
from aos_cli import is_int as _int
from aos_directives import DirectiveError, resolve, split_target, target_id

__all__ = ["FLAGS", "InstError", "dirname", "exit_code", "find", "load", "main", "parse", "read_exit", "run"]

_BOOLS = ("cwd_mkdir", "envs_clear", "stdin_inherit",
          "stdout_append", "stdout_mkdir", "stdout_inherit",
          "stderr_append", "stderr_mkdir", "stderr_inherit", "stderr_merge",
          "exit_append", "exit_mkdir")


class InstError(CliError):
    """這份 inst 被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。指示詞的錯照原代號包進來。"""


FLAGS = ("id", "cwd", "stdin", "stdout", "stderr", "exit", "timeout_ms", "grace_ms") + _BOOLS     # 鏡射成旗標的 key


def exit_code(err):
    """InstError → 命令列退出碼：CommandNotFound＝127、CommandNotExecutable＝126、其他＝125。"""
    return {"CommandNotFound": 127, "CommandNotExecutable": 126}.get(err.code, 125)


def read_exit(path):
    """讀 exit 檔最後一行的結束碼（exit_append 時每次附加一行，所以看最後一行）。
    檔不在、讀不了、內容不是整數都回 None。過渡用：loop、tasks 都改讀 stdout 那份結果的 code 了。"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().split()
        return int(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def find(target):
    """TARGET → id：inst.json 的路徑（realpath：絕對、沒有 . 與 ..、捷徑都解開；同一份檔永遠得到同一個字串），
    TARGET 有 `#/位置` 就再接上 `#` 與正規化過的位置（同一份檔兩個位置＝兩個 id）。"""
    return target_id(*_find(target))


def _find(target):
    """TARGET → (inst.json 的 realpath, 位置 tuple)。"""
    try:
        file, pos = split_target(target)
    except DirectiveError as e:
        raise InstError(e.code, e.msg)
    return _file(file), pos


def dirname():
    """資料夾 TARGET 裡放 inst.json 的子資料夾名：環境變數 `AOS_DIRNAME`，沒設＝`.aos`；空字串＝資料夾本身
    （同 proto7-1 的 aos_dirname；N-35）。含 `/`、或是 `.`、`..`＝`BadDirname`。"""
    n = os.environ.get("AOS_DIRNAME")
    n = ".aos" if n is None else n
    if "/" in n or n in (".", ".."):
        raise InstError("BadDirname", "AOS_DIRNAME 要是單一資料夾名或空字串（不含 /、不是 . 或 ..）：%r" % n)
    return n


def _file(file):
    """TARGET 的檔那一段 → inst.json 的 realpath（資料夾：先找 $AOS_DIRNAME/inst.json 再找 inst.json）。"""
    if os.path.isdir(file):
        sub = dirname()
        for p in (os.path.join(file, sub, "inst.json"), os.path.join(file, "inst.json")):
            if os.path.isfile(p):
                return os.path.realpath(p)
        raise InstError("NotFound", "%s 裡沒有 %s/inst.json 也沒有 inst.json" % (file, sub or "."))
    return os.path.realpath(file)


def load(target):
    """讀 TARGET 的 inst，以呼叫者現在的 cwd 為基準，回 `parse()` 的結果。"""
    try:
        doc, ident = aos_cli.load_target(target, _file)
    except CliError as e:
        raise InstError(e.code, e.msg)
    return parse(doc, os.getcwd(), ident)


def parse(doc, base_dir, ident="<input>", at=(), piped=False):
    """解指示詞、驗認得的 key，回一個欄位都填好的 dict（路徑都是絕對的，None＝沒寫）。
    `ident`＝doc 從哪來（`load()` 給 inst.json 的 realpath），指示詞的錯誤訊息用它指出是哪份檔。
    `at`＝inst 在 doc 裡的位置（TARGET 的 `#/位置`；`()`＝整份），指到的那一格要是物件。
    `piped`＝設定是從 stdin 讀的：`stdin_inherit` 就是 Conflict（D-5）。"""
    base_dir = os.path.abspath(base_dir)
    try:
        doc = resolve(doc, base_dir, ident, at)
    except DirectiveError as e:
        raise InstError(e.code, e.msg)
    if not isinstance(doc, dict):
        raise InstError("FieldType", "inst %s 要是物件，不是 %s" % (target_id(ident, at), type(doc).__name__))
    inst = {k: _bool(doc, k) for k in _BOOLS}
    i = doc.get("id", ident if ident not in ("<input>", "<stdin>") else None)
    if not (i is None or isinstance(i, str)):
        raise InstError("FieldType", "id 要是字串或 null，不是 %r" % (i,))
    inst["id"] = i

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

    t = doc.get("timeout_ms")
    if not (t is None or _int(t) and t > 0):
        raise InstError("FieldType", "timeout_ms 要是正整數或 null，不是 %r" % (t,))
    g = doc.get("grace_ms", 2000)
    if not (_int(g) and g >= 0):
        raise InstError("FieldType", "grace_ms 要是非負整數，不是 %r" % (g,))
    inst["timeout_ms"], inst["grace_ms"] = t, g

    for k in ("stdin", "stdout", "stderr"):
        if inst[k + "_inherit"] and inst[k] is not None:
            raise InstError("Conflict", "%s 跟 %s_inherit 只能二選一" % (k, k))
    if inst["stderr_merge"] and (inst["stderr"] is not None or inst["stderr_inherit"]):
        raise InstError("Conflict", "stderr_merge 不能再寫 stderr 或 stderr_inherit")
    if piped and inst["stdin_inherit"]:
        raise InstError("Conflict", "設定從 stdin 來，stdin_inherit 接不到東西")
    return inst


def _bool(doc, k):
    v = doc.get(k, False)
    if not isinstance(v, bool):
        raise InstError("FieldType", "%s 要是 true／false，不是 %r" % (k, v))
    return v


_FORWARDED = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def run(x):
    """跟命令列一樣跑一次：x＝TARGET（路徑，可接 `#/位置`）或一份設定 dict（D-4；基準＝呼叫者的 cwd）。
    起那個 posix 呼叫、等它結束，把子程式的結束碼寫進 exit 檔（自己結束＝它的碼，被訊號停掉＝128＋訊號號碼）。
    回結果 dict（同命令列的 stdout）；單子有問題、起不來丟 `InstError`。子程式回幾號、被限時收掉都算正常做完。

    在主執行緒呼叫時，跑的期間 SIGINT／SIGTERM／SIGHUP 不打斷呼叫者，轉給子程式；
    轉過去之後再等 grace_ms，還沒結束就 SIGKILL。不在主執行緒就不轉（Python 只准主執行緒接訊號）。"""
    return _run(parse(x, os.getcwd()) if isinstance(x, dict) else load(x))


def _run(inst):
    """照 `parse()` 的結果跑一次，回結果 dict。"""
    timeout_ms, grace_ms = inst["timeout_ms"], inst["grace_ms"]
    child = None
    pending = []
    killed_at = []      # 第一次轉訊號之後的 SIGKILL 期限

    def forward(signum, frame):
        if not killed_at:
            killed_at.append(time.monotonic() + grace_ms / 1000)
        if child is None:
            pending.append(signum)      # 還沒起來，起來再補送
        else:
            child.send_signal(signum)

    main = threading.current_thread() is threading.main_thread()
    old = {sig: signal.signal(sig, forward) for sig in _FORWARDED} if main else {}
    try:
        t0 = time.monotonic()
        child = _start(inst)
        for sig in pending:
            child.send_signal(sig)
        interrupted, timed_out = None, False
        try:
            rc, timed_out = _wait(child, timeout_ms, grace_ms, killed_at)
        except BaseException as e:
            interrupted = e
            rc = _stop(child, grace_ms)
        code = rc if rc >= 0 else 128 - rc
        if inst["exit"] is not None:
            try:
                _write_exit(inst["exit"], code, inst["exit_append"], inst["exit_mkdir"])
            except OSError:
                pass        # 寫不進去不管
        if interrupted is not None:
            raise interrupted
        return {"id": inst["id"], "code": code, "signal": -rc if rc < 0 else None, "timed_out": timed_out,
                "pid": child.pid, "ms": round((time.monotonic() - t0) * 1000), "exit_file": inst["exit"]}
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


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


def _wait(child, timeout_ms, grace_ms, killed_at):
    """等子程式結束；超過 timeout_ms（None＝不限）就 `_stop`；轉過訊號（killed_at 有期限）、過了期限還沒結束就 SIGKILL。
    回 (returncode, 是不是限時到了收掉的)：returncode 自己結束＝它的碼，被訊號停掉＝負的訊號號碼。"""
    deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000
    while True:
        try:
            return child.wait(0.05), False
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if killed_at and now >= killed_at[0]:
            child.kill()
        elif deadline is not None and now >= deadline:
            return _stop(child, grace_ms), True


def _stop(child, grace_ms):
    """SIGTERM，等 grace_ms 還沒結束就 SIGKILL（grace_ms＝0 直接 SIGKILL）。回 returncode。
    收的途中再被打斷就不等 grace，直接 SIGKILL。"""
    if grace_ms:
        child.send_signal(signal.SIGTERM)
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
    try:
        doc, ident, piped, rest = aos_cli.config(args, FLAGS, _file)
        if rest is not None:
            doc["argv"] = rest
        aos_cli.emit(_run(parse(doc, os.getcwd(), ident or ("<stdin>" if piped else "<input>"), piped=piped)))
        return 0
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return exit_code(e)


if __name__ == "__main__":
    sys.exit(main())
