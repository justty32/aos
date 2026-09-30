"""照解好的 `Plan` 開程序：前置準備 → 起子程式（setsid）→ 等／逾時 → 寫 exit 檔。

對應 spec：proto6/spec/base/inst.md〈路徑、環境與指示詞〉（envs 疊加／clear、PATH 找 argv[0]）
與〈執行與錯誤〉（125／126／127／128+N、逾時 TERM→2 秒→KILL、exit 寫法與 fsync）。
搬自 proto5/lib/aos_exec_run.py 並簡化。

這個模組跟解析完全分開：只吃 `plan.Plan`，不 import 解析的東西。使用者自己寫開程序的話整個不用。
不做：切身分、cgroup、後代脫離 process group 的清理（spec 見 execution.md）、daemon 通道變數
（留 `base_env`／`forced_env` 參數讓呼叫方自己放）。
"""
import collections
import os
import signal
import subprocess
import time

from .errors import InstError

__all__ = ["RunResult", "run", "status_to_code", "write_exit", "GRACE"]

GRACE = 2.0     # 逾時：對整組 TERM 後等這麼久，還在就 KILL（只指 inst 自己的逾時）

# exit_code：結束碼（127／126／子程式碼／128+N）；timed_out：是否因逾時被送訊號；
# finalize_error：exit 檔寫不進去時的 InstError("FinalizeFailed")，其餘 None
RunResult = collections.namedtuple("RunResult", "exit_code timed_out finalize_error")


def run(plan, timeout=None, grace=GRACE, base_env=None, forced_env=None, stderr_override=None,
        pass_fds=(), on_spawn=None):
    """跑一次 `plan`，回 `RunResult`。前置準備失敗丟 `InstError("PrepareFailed")`（沒跑、不寫 exit）。

    - `timeout`：秒數，None＝不限。到了先對整個 process group 送 TERM，`grace` 秒後還在就 KILL。
    - `base_env`：runner 的環境（沒給＝`os.environ`）；沒 clear 就複製它再疊 `plan.envs`，有 clear 從空開始。
      daemon 給 tick 的通道變數應放在這裡（會被 clear 一起清掉）。
    - `forced_env`：最後才補、不受 clear 影響的變數（helper 例外、`AOS_TICK_LOCK_FD` 之類）。
    - `stderr_override`：runner 明示的 stderr，蓋過 inst（含 merge／inherit／append）：
      `"-"`＝繼承、字串＝路徑（建立並清空，相對呼叫者 cwd）、整數＝fd、有 `fileno()` 的物件也行。
    - `pass_fds`：要留給子程式的 fd（例如鎖）。
    - `on_spawn(popen)`：子程式起來後叫一次（呼叫方要拿 pid 可用）。
    找不到程式＝127、沒執行權＝126，這兩種算跑完一次，有 exit 照寫。
    """
    _prepare_dirs(plan, stderr_override is not None)
    env = _environment(plan, base_env, forced_env)
    opened = []
    try:
        try:
            fin = None if plan.stdin.inherit else _open(plan.stdin.path or os.devnull, "rb", opened)
            fout = _open_out(plan.stdout, opened)
            if stderr_override is not None:
                ferr = _override(stderr_override, opened)
            elif plan.stderr.merge:
                ferr = subprocess.STDOUT
            else:
                ferr = _open_out(plan.stderr, opened)
        except OSError as e:
            raise InstError("PrepareFailed", "串流開不起來：%s" % e)
        code, timed_out = _spawn_and_wait(plan, env, fin, fout, ferr, timeout, grace, pass_fds,
                                          on_spawn)
    finally:
        for f in opened:
            f.close()
    err = None
    if plan.exit.path:
        try:
            write_exit(plan.exit.path, code, plan.exit.append)
        except OSError as e:
            err = InstError("FinalizeFailed", "exit 檔寫不進去 %s：%s" % (plan.exit.path, e))
    return RunResult(code, timed_out, err)


def status_to_code(returncode):
    """Popen 的 returncode → 結束碼：正常照用，被訊號 N 結束（負數）→ 128+N。"""
    return returncode if returncode >= 0 else 128 - returncode


def write_exit(path, code, append=False):
    """寫十進位結束碼＋換行；預設覆蓋、`append` 追加；寫完 fsync 檔案與父目錄。"""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o666)
    try:
        os.write(fd, ("%d\n" % code).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


# ------------------------------------------------------------------ 內部 ----

def _prepare_dirs(plan, stderr_overridden):
    """建 cwd 與 mkdir 的父目錄；檢查 cwd 是資料夾、exit 父目錄存在。失敗＝PrepareFailed。"""
    todo = [("cwd", plan.cwd)] if plan.cwd_mkdir else []
    for name in ("stdout", "stderr", "exit"):
        s = getattr(plan, name)
        if name == "stderr" and stderr_overridden:
            continue
        if s.mkdir and s.path:
            todo.append((name, os.path.dirname(s.path)))
    for name, d in todo:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            raise InstError("PrepareFailed", "%s 的 mkdir 建不起來 %s：%s" % (name, d, e))
    if not os.path.isdir(plan.cwd):
        raise InstError("PrepareFailed", "cwd 不是資料夾：%s" % plan.cwd)
    if plan.exit.path and not os.path.isdir(os.path.dirname(plan.exit.path)):
        raise InstError("PrepareFailed", "exit 的父目錄不存在（沒開 mkdir 不幫建）：%s"
                        % os.path.dirname(plan.exit.path))


def _environment(plan, base_env, forced_env):
    env = {} if plan.envs_clear else dict(os.environ if base_env is None else base_env)
    env.update(plan.envs)
    if forced_env:
        env.update(forced_env)
    return env


def _open(path, mode, opened):
    f = open(path, mode)
    opened.append(f)
    return f


def _open_out(stream, opened):
    """stdout／stderr：inherit＝None（繼承）、append＝`ab`、否則 `wb`（建立並清空）；沒寫＝/dev/null。"""
    if stream.inherit:
        return None
    return _open(stream.path or os.devnull, "ab" if stream.append else "wb", opened)


def _override(value, opened):
    if value == "-":
        return None
    if isinstance(value, str):
        return _open(value, "wb", opened)
    return value            # fd 整數或有 fileno() 的物件，Popen 都吃


def _spawn_and_wait(plan, env, fin, fout, ferr, timeout, grace, pass_fds, on_spawn):
    """起子程式（新 session＝新 process group）並等它；回 `(結束碼, 是否逾時)`。

    argv[0] 沒有斜線時用疊好的 env 裡的 PATH 找；沒 PATH 用 `os.defpath`（Popen 本身就這樣）。
    """
    try:
        p = subprocess.Popen(plan.argv, cwd=plan.cwd, env=env, stdin=fin, stdout=fout, stderr=ferr,
                             start_new_session=True, close_fds=True, pass_fds=tuple(pass_fds))
    except (FileNotFoundError, NotADirectoryError):
        return 127, False
    except OSError:                 # PermissionError、ENOEXEC 等：找到了但執行不了
        return 126, False
    if on_spawn is not None:
        on_spawn(p)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        p.wait(timeout=None if deadline is None else max(0.0, deadline - time.monotonic()))
        return status_to_code(p.returncode), False
    except subprocess.TimeoutExpired:
        pass
    _killpg(p.pid, signal.SIGTERM)
    until = time.monotonic() + grace
    while time.monotonic() < until:
        if p.poll() is not None and not _group_exists(p.pid):
            break
        time.sleep(0.01)
    else:
        _killpg(p.pid, signal.SIGKILL)
    p.wait()
    return status_to_code(p.returncode), True


def _killpg(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
