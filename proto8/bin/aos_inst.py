"""aos_inst：讀一張單子（JSON）、跑一次子程式的庫。純標準庫，不 import 別的。

    import aos_inst; aos_inst.run(dict 或 FILE[, args])    行程內跑，回結果 dict（aos-exec 跑 inst 單子入口時用）
    FILE 第一行是 `#!` 就丟掉那一行，剩下當 JSON；args 接在 argv 後面。
10-22 使用者「aos-inst指令可以刪掉了，跟C++版一樣做成lib就好」：aos-inst 命令列刪了（C++ 版 inst 也是 lib），
單子一律經 aos-exec 跑（沒 +x 的入口檔、`檔#/指標`、loop／fsm 的 `…#/body`）。

單子認得的 key（其他一律忽略）：
    argv            非空字串陣列（必填）
    cwd             在哪跑（沒寫＝呼叫者的 cwd）
    envs            {名字: 字串}，疊在現有環境上
    stdin           從哪個檔讀；沒寫＝接呼叫者的
    stdout/stderr   寫到哪個檔（覆寫）；沒寫＝接呼叫者的；stdout_append／stderr_append: true 改附加
    timeout_ms      最多跑幾毫秒（正整數；沒寫＝不限），到了先 SIGTERM
    grace_ms        SIGTERM 後等幾毫秒還沒結束就 SIGKILL（非負整數；沒寫＝2000；0＝直接 SIGKILL）
相對路徑：cwd 從呼叫者的 cwd 算；stdin／stdout／stderr 從解出來的 cwd 算。

指示詞（N-45）：單子裡任何位置的 {"$env": 名} 換成那個環境變數的值。{"$ref": "檔"} 換成那份 JSON 檔的整份內容
（第一行 #! 跳過）；{"$ref": "檔#/a"} 或 {"$ref": "檔", "at": "/a"} 換成檔內那個位置的值（JSON pointer；兩個都寫＝
at 接在 #/ 後面，10-20 ideas D1、D7）；換進來的值接著解。相對檔名從寫著這個 $ref 的檔所在的資料夾算（ref_base；
被 $ref 進來的檔解開捷徑再算）。指標取的是檔的原文（不穿過裡面的 $ref）。
換出來是字串時：有 "$path" 就接上去（字串拼接：`#` 開頭直接接，其他中間剛好一個 /，寫絕對路徑也是接上去；
10-21 傍晚 ideas § 9，原 os.path.join），再在前面加 "$prefix"（10-20 ideas D9～D11；舊的 "path" key 不再有作用）；換出來不是字串，$path／$prefix 靜默不作用。
錯分兩類（10-20 ideas D12～D15）：真的解不開——變數沒設、$ref 檔讀不到（含不是 JSON）、指不到、繞圈——＝單子的錯；
寫法（格式）寬容——物件有 $ref 就只看 $ref（$env 不管），其餘 key、不認得的 $xxx 都不管；$path／$prefix／at 不是
字串（at 也不是空字串或 / 開頭）＝當沒寫；$ref／$env 的值不是字串或空字串、# 後不是 /、只有 #/… 沒檔名＝換不了，
整個物件原封不動留著。
argv[0] 帶 / 又 exec 不了（不是 +x 的一般檔：資料夾、沒 +x 的檔、不在，或帶 #/）＝前面插 aos-exec、照 PATH 找
（10-20 ideas D3、D5：["tools/stamp", "a"]＝["aos-exec", "tools/stamp", "a"]；10-21 起 a 是 args，工作區只由 --ws 給）。

單子的錯（單子壞、程式找不到、$env 沒設、$ref 解不開）丟 InstError；aos-exec 接住、退 1，
stderr 一行「aos-exec: 單子跑不起來：原因」。子程式的碼由 aos-exec 透明轉交（被訊號停掉＝128＋訊號號碼）。
run() 回 {"code", "signal", "timed_out", "pid", "ms", "received"}（received＝跑的期間收到、轉給子程式的第一個
SIGINT／SIGTERM／SIGHUP，沒有＝None；給 aos-loop／aos-fsm「收完這拍再以 128＋N 結束」用）；子程式回幾號、被逾時收掉都算正常跑完，
單子有問題或起不來丟 InstError。

行程群組（P-36）：子程式自成一個行程群組（start_new_session），逾時與轉來的訊號都對整個群組送
（killpg），grace 到了 SIGKILL 整個群組——子程式底下的孫程式一起收掉。

argv[0] 是 +x 但沒有 #! 的檔（ENOEXEC）時照 execvp 的做法改用 `/bin/sh 那個檔 args...` 再起一次（ideas § 21「不擋」）。
"""
import errno
import json
import os
import shutil
import signal
import subprocess
import threading
import time

__all__ = ["InstError", "argv0", "load", "parse", "resolve", "run"]

_KEYS_BOOL = ("stdout_append", "stderr_append")
_FORWARDED = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class InstError(Exception):
    """單子的錯：單子壞、程式找不到、$env 沒設…"""


def _pointer(doc, ptr, where):
    """RFC 6901：ptr 是空字串（整份）或 `/a/b`（`~1`＝`/`、`~0`＝`~`）。"""
    if ptr == "":
        return doc
    for tok in ptr[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(doc, dict) and tok in doc:
            doc = doc[tok]
        elif isinstance(doc, list) and tok.isdigit() and (tok == "0" or not tok.startswith("0")) \
                and int(tok) < len(doc):
            doc = doc[int(tok)]
        else:
            raise InstError("$ref 指不到：%s#%s" % (where, ptr))
    return doc


_KEEP = object()   # 格式不合（B 類）：整個指示詞物件原封不動留著


def _ref(x, base, chain):
    """{"$ref": "檔[#/指標]"[, "at": 指標]} → 那個位置的值（接著解完）；寫法不合回 _KEEP。"""
    ref, at = x["$ref"], x.get("at")
    if not isinstance(ref, str):
        return _KEEP
    if not (isinstance(at, str) and (at == "" or at.startswith("/"))):
        at = None                       # at 寫法不合＝當沒寫
    path, hashed, ptr = ref.partition("#")
    if not path or hashed and not ptr.startswith("/"):
        return _KEEP                    # 空字串、只有 #/…、# 後不是 /
    ptr += at or ""                     # D7：at 接在 #/ 後面
    f = os.path.realpath(os.path.join(base, path))
    if (f, ptr) in chain:
        raise InstError("$ref 繞圈：%s" % " → ".join(a + ("#" + b if b else "") for a, b in chain + ((f, ptr),)))
    return _resolve(_pointer(load(f, "$ref "), ptr, f), os.path.dirname(f), chain + ((f, ptr),))


def _env(x):
    """{"$env": 名} → 那個環境變數的值；名不是非空字串回 _KEEP；沒設＝錯。"""
    name = x["$env"]
    if not isinstance(name, str) or not name:
        return _KEEP
    if name not in os.environ:
        raise InstError("環境變數 %s 沒設定" % name)
    return os.environ[name]


def join(v, sub):
    """$path 的字串拼接（10-21 傍晚 ideas § 9，原 os.path.join）：sub 以 # 開頭＝直接接在後面（`x.json` + `#/a`）；
    空字串＝不接；其他＝去掉 v 結尾的 /、去掉 sub 開頭的 /，中間剛好一個 /（寫絕對路徑不再整個取代）。"""
    if not sub:
        return v
    if sub.startswith("#"):
        return v + sub
    return v.rstrip("/") + "/" + sub.lstrip("/")


def _resolve(x, base, chain=()):
    """把 x 裡所有指示詞換掉（N-45，10-20 改）：有 $ref／$env 的物件整個換成值，物件裡其餘 key 不管；
    換出來是字串時再照 $path 接上去（join）、前面加 $prefix（兩欄不是字串＝當沒寫）。"""
    if isinstance(x, list):
        return [_resolve(v, base, chain) for v in x]
    if not isinstance(x, dict):
        return x
    if "$ref" in x:                     # 同時有 $env 只看 $ref
        v = _ref(x, base, chain)
    elif "$env" in x:
        v = _env(x)
    else:
        return {k: _resolve(v, base, chain) for k, v in x.items()}
    if v is _KEEP:
        return x
    if isinstance(v, str):              # 換出來不是字串＝$path／$prefix 靜默不作用
        sub, pre = x.get("$path"), x.get("$prefix")
        if isinstance(sub, str):
            v = join(v, sub)
        if isinstance(pre, str):
            v = pre + v
    return v


def resolve(x, ref_base=None):
    """解指示詞（N-45）。ref_base＝$ref 相對檔名的起點（寫著它的檔所在的資料夾；沒給＝cwd）。丟 InstError。"""
    return _resolve(x, os.path.abspath(ref_base or os.getcwd()))


def argv0(argv, cwd):
    """argv[0] 帶 / 又 exec 不了（不是 +x 的一般檔，或帶 #/）→ 前面插 aos-exec（10-20 ideas D3）；其他原樣。"""
    a = argv[0]
    if "/" not in a:
        return argv
    p = os.path.join(cwd, a)
    if "#/" in a or not (os.path.isfile(p) and os.access(p, os.X_OK)):
        return ["aos-exec"] + argv
    return argv


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse(doc, base=None, args=(), ref_base=None):
    """解指示詞、驗認得的 key，回欄位都填好的 dict（None＝沒寫＝接呼叫者的）。args 接在 argv 後面。
    base＝cwd 的起點（呼叫者的 cwd）；ref_base＝$ref 的起點（寫著單子的檔所在的資料夾；沒給＝base）。"""
    base = os.path.abspath(base or os.getcwd())
    doc = resolve(doc, ref_base or base)
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


def load(path, what=""):
    """讀單子檔（或 $ref 的檔）：第一行是 `#!` 就丟掉，剩下 json.loads。"""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise InstError("%s讀不到 %s：%s" % (what, path, e))
    if text.startswith("#!"):
        text = text.partition("\n")[2]
    try:
        return json.loads(text)
    except ValueError as e:
        raise InstError("%s%s 不是 JSON：%s" % (what, path, e))


def run(x, args=(), ref_base=None):
    """跑一次：x＝單子檔路徑，或單子 dict（基準＝呼叫者的 cwd）。回結果 dict；單子有問題、起不來丟 InstError。
    $ref 的起點：x 是檔＝它（解開捷徑）所在的資料夾；x 是 dict＝ref_base（寫著它的檔所在的資料夾），沒給＝cwd。
    在主執行緒呼叫時，跑的期間 SIGINT／SIGTERM／SIGHUP 不打斷呼叫者，轉給子程式；
    轉過去之後再等 grace_ms，還沒結束就 SIGKILL。"""
    if isinstance(x, str):
        doc, ref_base = load(x), os.path.dirname(os.path.realpath(x))
    else:
        doc = x
    return _run(parse(doc, os.getcwd(), args, ref_base))


def _run(inst):
    timeout_ms, grace_ms = inst["timeout_ms"], inst["grace_ms"]
    child = None
    pending = []
    killed_at = []      # 第一次轉訊號之後的 SIGKILL 期限
    received = []       # 收到的訊號（結果的 received＝第一個）

    def forward(signum, frame):
        received.append(signum)
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
                "timed_out": timed_out, "pid": child.pid, "ms": round((time.monotonic() - t0) * 1000),
                "received": received[0] if received else None}
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
        def popen(argv):
            return subprocess.Popen(argv, cwd=inst["cwd"], env=env, stdin=stdin, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
        inst["argv"] = argv0(inst["argv"], inst["cwd"])   # 帶 / 又 exec 不了＝交給 PATH 上的 aos-exec（D3）
        try:
            try:
                return popen(inst["argv"])
            except OSError as e:
                if e.errno != errno.ENOEXEC:
                    raise
                # 同 execvp：+x 但沒 #! 的檔改用 /bin/sh 跑（ideas § 21「不擋」；aos-exec 的 argv 陣列入口不這樣）
                prog = inst["argv"][0]
                if "/" not in prog:
                    prog = shutil.which(prog, path=env.get("PATH", os.defpath)) or prog
                return popen(["/bin/sh", prog] + inst["argv"][1:])
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
