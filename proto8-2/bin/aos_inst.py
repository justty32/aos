"""aos-inst：讀一張單子（JSON）、跑一次子程式。純標準庫。proto8-2 自己的一份，不 import proto8。

    aos-inst FILE [args...]        FILE 第一行是 `#!` 就丟掉那一行，剩下當 JSON；args 接在 argv 後面
    import aos_inst; aos_inst.run(dict 或 FILE)    行程內跑，回結果 dict（aos-loop／aos-fsm 用）

單子認得的 key（其他一律忽略）：
    argv            非空字串陣列（必填）
    cwd             在哪跑（沒寫＝呼叫者的 cwd）
    envs            {名字: 字串}，疊在現有環境上
    stdin           從哪個檔讀；沒寫＝接呼叫者的
    stdout/stderr   寫到哪個檔（覆寫）；沒寫＝接呼叫者的；stdout_append／stderr_append: true 改附加
    timeout_ms      最多跑幾毫秒（正整數；沒寫＝不限），到了先 SIGTERM
    grace_ms        SIGTERM 後等幾毫秒還沒結束就 SIGKILL（非負整數；沒寫＝2000；0＝直接 SIGKILL）
相對路徑：cwd 從呼叫者的 cwd 算；stdin／stdout／stderr 從解出來的 cwd 算。

單子裡任何位置的 {"$env": 名} 換成那個環境變數的值；{"$env": 名, "path": 子路徑} 換成
os.path.join(值, 子路徑)。變數沒設＝單子的錯。只有 $env，沒有 $ref。

結束碼：命令列退出碼＝子程式的碼（透明轉交；被訊號停掉＝128＋訊號號碼）。aos-inst 自己的錯
（單子壞、程式找不到、$env 沒設）退 1，stderr 一行「aos-inst: 原因」。
run() 回 {"code", "signal", "timed_out", "pid", "ms"}；子程式回幾號、被逾時收掉都算正常跑完，
單子有問題或起不來丟 InstError。

行程群組（P-36）：子程式自成一個行程群組（start_new_session），逾時與轉來的訊號都對整個群組送
（killpg），grace 到了 SIGKILL 整個群組——子程式底下的孫程式一起收掉。
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time

__all__ = ["InstError", "load", "main", "parse", "run"]

_KEYS_BOOL = ("stdout_append", "stderr_append")
_FORWARDED = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class InstError(Exception):
    """aos-inst 自己的錯：單子壞、程式找不到、$env 沒設…"""


def _env(x):
    """把 x 裡所有 {"$env": 名[, "path": 子路徑]} 換成字串。"""
    if isinstance(x, list):
        return [_env(v) for v in x]
    if isinstance(x, dict):
        if "$env" not in x:
            return {k: _env(v) for k, v in x.items()}
        name, path = x["$env"], x.get("path")
        extra = set(x) - {"$env", "path"}
        if not isinstance(name, str) or extra or not (path is None or isinstance(path, str)):
            raise InstError('$env 只能是 {"$env": 變數名} 或 {"$env": 變數名, "path": 子路徑}：%r' % (x,))
        if name not in os.environ:
            raise InstError("環境變數 %s 沒設定" % name)
        return os.environ[name] if path is None else os.path.join(os.environ[name], path)
    return x


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse(doc, base=None, args=()):
    """解 $env、驗認得的 key，回欄位都填好的 dict（None＝沒寫＝接呼叫者的）。args 接在 argv 後面。"""
    base = os.path.abspath(base or os.getcwd())
    doc = _env(doc)
    if not isinstance(doc, dict):
        raise InstError("單子要是 JSON 物件，不是 %s" % type(doc).__name__)
    argv = doc.get("argv")
    if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
        raise InstError("argv 要是非空的字串陣列，不是 %r" % (argv,))
    inst = {"argv": argv + list(args)}
    envs = doc.get("envs", {})
    if not (isinstance(envs, dict) and all(isinstance(v, str) for v in envs.values())):
        raise InstError("envs 要是 {名字: 字串}，不是 %r" % (envs,))
    inst["envs"] = envs
    for k in ("cwd", "stdin", "stdout", "stderr"):
        v = doc.get(k)
        if v is not None and not isinstance(v, str):
            raise InstError("%s 要是字串路徑，不是 %r" % (k, v))
        if k == "cwd":
            inst[k] = base if v is None else os.path.join(base, v)
        else:
            inst[k] = None if v is None else os.path.join(inst["cwd"], v)
    for k in _KEYS_BOOL:
        v = doc.get(k, False)
        if not isinstance(v, bool):
            raise InstError("%s 要是 true／false，不是 %r" % (k, v))
        inst[k] = v
    t = doc.get("timeout_ms")
    if not (t is None or (_int(t) and t > 0)):
        raise InstError("timeout_ms 要是正整數，不是 %r" % (t,))
    g = doc.get("grace_ms", 2000)
    if not (_int(g) and g >= 0):
        raise InstError("grace_ms 要是非負整數，不是 %r" % (g,))
    inst["timeout_ms"], inst["grace_ms"] = t, g
    return inst


def load(path):
    """讀單子檔：第一行是 `#!` 就丟掉，剩下 json.loads。"""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise InstError("讀不到 %s：%s" % (path, e))
    if text.startswith("#!"):
        text = text.partition("\n")[2]
    try:
        return json.loads(text)
    except ValueError as e:
        raise InstError("%s 不是 JSON：%s" % (path, e))


def run(x, args=()):
    """跑一次：x＝單子檔路徑，或單子 dict（基準＝呼叫者的 cwd）。回結果 dict；單子有問題、起不來丟 InstError。
    在主執行緒呼叫時，跑的期間 SIGINT／SIGTERM／SIGHUP 不打斷呼叫者，轉給子程式；
    轉過去之後再等 grace_ms，還沒結束就 SIGKILL。"""
    doc = load(x) if isinstance(x, str) else x
    return _run(parse(doc, os.getcwd(), args))


def _run(inst):
    timeout_ms, grace_ms = inst["timeout_ms"], inst["grace_ms"]
    child = None
    pending = []
    killed_at = []      # 第一次轉訊號之後的 SIGKILL 期限

    def forward(signum, frame):
        if not killed_at:
            killed_at.append(time.monotonic() + grace_ms / 1000)
        if child is None:
            pending.append(signum)
        else:
            _sig(child, signum)

    main_thread = threading.current_thread() is threading.main_thread()
    old = {sig: signal.signal(sig, forward) for sig in _FORWARDED} if main_thread else {}
    try:
        t0 = time.monotonic()
        child = _start(inst)
        for sig in pending:
            _sig(child, sig)
        interrupted, timed_out = None, False
        try:
            rc, timed_out = _wait(child, timeout_ms, grace_ms, killed_at)
        except BaseException as e:
            interrupted = e
            rc = _stop(child, grace_ms)
        if interrupted is not None:
            raise interrupted
        return {"code": rc if rc >= 0 else 128 - rc, "signal": -rc if rc < 0 else None,
                "timed_out": timed_out, "pid": child.pid, "ms": round((time.monotonic() - t0) * 1000)}
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def _start(inst):
    if not os.path.isdir(inst["cwd"]):
        raise InstError("cwd %s 不是資料夾" % inst["cwd"])
    env = dict(os.environ, **inst["envs"])
    opened = []
    try:
        try:
            stdin = _stream(inst, "stdin", opened)
            stdout = _stream(inst, "stdout", opened)
            stderr = _stream(inst, "stderr", opened)
        except OSError as e:
            raise InstError("串流開不了：%s" % e)
        try:
            return subprocess.Popen(inst["argv"], cwd=inst["cwd"], env=env,
                                    stdin=stdin, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
        except FileNotFoundError:
            raise InstError("找不到要跑的程式 %s" % inst["argv"][0])
        except PermissionError:
            raise InstError("%s 不能執行" % inst["argv"][0])
        except OSError as e:
            raise InstError("起不了 %s：%s" % (inst["argv"][0], e))
    finally:
        for f in opened:
            f.close()


def _sig(child, signum):
    """對子程式的整個行程群組送訊號（單子起的程式自成一個群組，P-36）；群組已經沒了就算了。"""
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass


def _wait(child, timeout_ms, grace_ms, killed_at):
    """等子程式結束；超過 timeout_ms（None＝不限）就 _stop。回 (returncode, 是不是逾時收掉的)。"""
    deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000
    while True:
        try:
            return child.wait(0.05), False
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if killed_at and now >= killed_at[0]:
            _sig(child, signal.SIGKILL)
        elif deadline is not None and now >= deadline:
            return _stop(child, grace_ms), True


def _stop(child, grace_ms):
    """SIGTERM，等 grace_ms 還沒結束就 SIGKILL（0＝直接 SIGKILL）。回 returncode。"""
    if grace_ms:
        _sig(child, signal.SIGTERM)
        try:
            return child.wait(grace_ms / 1000)
        except BaseException:
            pass
    _sig(child, signal.SIGKILL)
    while True:
        try:
            return child.wait()
        except BaseException:
            pass


def _stream(inst, k, opened):
    """None＝接呼叫者的；否則開檔。"""
    path = inst[k]
    if path is None:
        return None
    if k == "stdin":
        f = open(path, "rb")
    else:
        f = open(path, "ab" if inst[k + "_append"] else "wb")
    opened.append(f)
    return f


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("aos-inst: usage: aos-inst FILE [args...]", file=sys.stderr)
        return 1
    try:
        return run(args[0], args[1:])["code"]
    except InstError as e:
        print("aos-inst: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
