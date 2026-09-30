"""aos-exec 的底層：照一份解好的 inst 開串流、起子行程、等它（逾時／強停）、寫 exit 檔。

上層三種目標的解讀在 aos_exec.py（run_target／run_target_full／run_inst），daemon 的非同步
入口在 aos_exec_spawn.py；兩邊都經 `_execute_inst()` 做同一套前置檢查與串流設定。
照 ../spec/inst-posix/ 第 6 節：mkdir／append／inherit／merge、環境清空或疊加、新 process group、
逾時 SIGTERM → GRACE 秒 → SIGKILL、exit 檔十進位＋換行並 fsync 檔與父目錄。
"""
import os
import select
import signal
import subprocess
import sys
import time

DEFAULT_DIR_TARGET = os.path.join(".aos", "inst.json")
GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL
CHILD, AOS, USAGE = "child", "aos", "usage"      # run_target() 回的那個 kind


def _err(code, kind, msg):
    sys.stderr.write("aos-exec: %s\n" % msg)
    return code, kind


def _execute_inst(inst, timeout_ms, on_spawn=None, stderr=None, input_bytes=None, output=None,
                  timed_out=None, details=None, launcher=None):
    """共用的前置檢查與串流設定；有 input_bytes 時改走 stdin／stdout 管線。"""

    # 先建該建的目錄：cwd 自己，再來是三個輸出檔的父目錄。建不起來＝沒跑成（125）。
    to_make = [("cwd", inst["cwd"])] if inst["cwd_mkdir"] else []
    for name in ("stdout", "stderr", "exit"):
        if name == "stdout" and (input_bytes is not None or launcher is not None):
            continue                            # 收回 stdout，不開 inst 的輸出檔
        if name == "stderr" and stderr is not None:
            continue                            # 命令列蓋掉了，inst 的 stderr 設定整個不算
        if inst[name]["mkdir"]:
            to_make.append((name, os.path.dirname(inst[name]["path"]) or "."))
    for name, d in to_make:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            return _err(1, AOS, "%s 的 mkdir 建不起來 %s：%s" % (name, d, e))

    exit_path = inst["exit"]["path"]
    if exit_path:                       # 父目錄不存在＝aos-exec 自己失敗（沒開 mkdir 就不幫建）
        d = os.path.dirname(exit_path) or "."
        if not os.path.isdir(d):
            return _err(1, AOS, "exit 檔的父目錄不存在（沒開 mkdir 不會幫你建）：%s" % d)
    if not os.path.isdir(inst["cwd"]):  # 連 chdir 都做不到＝aos-exec 自己失敗，沒跑成
        return _err(1, AOS, "cwd 不是資料夾：%s" % inst["cwd"])

    env = {} if inst["envs_clear"] else dict(os.environ)
    env.update(inst["envs"])             # 只加不減；清空型式就是從空的開始加

    opened = []
    try:
        try:
            if input_bytes is not None or launcher is not None:
                fin, fout = subprocess.PIPE, subprocess.PIPE
            else:
                fin = None if inst["stdin"]["inherit"] else open(
                    inst["stdin"]["path"] or os.devnull, "rb")
                opened.append(fin)
                fout = _open_out(inst["stdout"])
                opened.append(fout)
            if stderr == "-":
                ferr = sys.stderr                # 繼承 aos-exec 的 stderr，不能 close
            elif stderr is not None:
                ferr = open(stderr, "wb")        # 命令列路徑以呼叫 aos-exec 時的 cwd 為中心
                opened.append(ferr)
            elif inst["stderr"]["merge"]:        # 跟 stdout 同一條，stdout 怎麼設它就怎麼走
                ferr = subprocess.STDOUT
            else:
                ferr = _open_out(inst["stderr"])
                opened.append(ferr)
        except OSError as e:
            return _err(1, AOS, "重導向的檔案開不起來：%s" % e)
        return (launcher or _spawn)(inst["argv"], inst["cwd"], env, fin, fout, ferr,
                      timeout_ms, exit_path, on_spawn, inst["exit"]["append"], input_bytes, output,
                      timed_out, details)
    finally:
        for f in opened:
            if f is not None:                    # inherit 的那條是 None，沒東西可關
                f.close()


def _open_out(field):
    """stdout／stderr 一格：inherit＝None（Popen 就繼承）、append＝`ab`、不然 `wb`（建立並清空）；
    沒寫路徑＝/dev/null。"""
    if field["inherit"]:
        return None
    return open(field["path"] or os.devnull, "ab" if field["append"] else "wb")


def _spawn(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path, on_spawn=None,
           exit_append=False, input_bytes=None, output=None, timed_out=None, details=None):
    """跑一次、等它、逾時就砍，回 `(結束狀態, "child")`（順便寫 exit 檔）。

    argv[0] 走**疊加後**的 env 裡的 PATH（subprocess 帶 env= 時本來就這樣查；env 被清空、
    裡面沒有 PATH 時，Python 的 `os.get_exec_path()` 退回 `os.defpath`）。找不到＝127、
    沒執行權＝126，這兩種都算「跑完了一次」。
    """
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
    except ValueError as e:
        return _err(1, AOS, "FieldTypeMismatch: 無法啟動子程式：%s" % e)
    except PermissionError as e:
        return _finish(126, exit_path, "沒有執行權：%s（exit 126）" % e, exit_append)
    except (FileNotFoundError, NotADirectoryError) as e:
        return _finish(127, exit_path, "找不到程式：%s（exit 127）" % e, exit_append)
    except OSError as e:
        return _finish(126, exit_path, "起不了子行程：%s（exit 126）" % e, exit_append)

    if on_spawn:
        on_spawn(p)                                 # 開起來了：aos-run 要拿得到它才砍得掉
    if details is not None:
        _wait_full(p, timeout_ms, details)
        if on_spawn:
            on_spawn(None)
        code = p.returncode
        return _finish(code if code >= 0 else 128 + (-code), exit_path, None, exit_append)
    deadline = time.monotonic() + timeout_ms / 1000.0 if timeout_ms else None
    captured = b""
    pending_input = input_bytes
    while not getattr(p, "_aos_stop", None):
        limit = max(0, deadline - time.monotonic()) if deadline is not None else None
        if on_spawn is not None:
            limit = min(limit, 0.05) if limit is not None else 0.05
        try:
            if input_bytes is None:
                p.wait(timeout=limit)
            else:
                captured, _ = p.communicate(input=pending_input, timeout=limit)
            break
        except subprocess.TimeoutExpired:
            pending_input = None
            if deadline is not None and time.monotonic() >= deadline:
                if timed_out is not None:
                    timed_out[0] = True
                terminate(p)
    if getattr(p, "_aos_stop", None):
        until, groups = p._aos_stop
        # 父進程先退出也給後代同一個寬限；nested run_inst 另開的 session 也在快照裡。
        try:
            remaining = max(0, until - time.monotonic())
            if input_bytes is None:
                p.wait(timeout=remaining)
            else:
                captured, _ = p.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass
        # 沒有活後代就不必等滿；killpg(0) 把 zombie 當存在，至多多等兩秒。
        while time.monotonic() < until and any(_group_exists(g) for g in groups):
            time.sleep(min(0.02, max(0, until - time.monotonic())))
        _signal_groups(groups, signal.SIGKILL)
        if input_bytes is None:
            p.wait()
        else:
            captured, _ = p.communicate()
    if output is not None:
        output.append(captured)
    code = p.returncode
    if on_spawn:
        on_spawn(None)                              # 收完屍：那個 pid 別再被砍
    return _finish(code if code >= 0 else 128 + (-code), exit_path, None, exit_append)


def _pidfd(p):
    """子行程的 pidfd（Linux 5.3＋）：它一結束就可讀，等的人不必睡滿一個 poll。拿不到回 None（改用睡）。
    子行程還沒收屍，pid 不會被別人重用，所以這時開的 pidfd 一定指它。"""
    try:
        return os.pidfd_open(p.pid)
    except (AttributeError, OSError):
        return None


def _nap(fd, pause):
    """睡 pause 秒；有 pidfd 就在子行程結束那一刻醒（09-24 tick-gap：以前平均多睡半個 poll_ms）。"""
    if fd is None:
        time.sleep(pause)
        return
    try:
        select.select([fd], [], [], pause)
    except (OSError, ValueError):
        time.sleep(pause)


def _wait_full(p, timeout_ms, details):
    """cpu 專用等待：取消／逾時都只處理一個 pgid，控制回呼不中斷。"""
    fd = _pidfd(p)
    try:
        _wait_loop(p, timeout_ms, details, fd)
    finally:
        if fd is not None:
            os.close(fd)


def _wait_loop(p, timeout_ms, details, fd):
    deadline = time.monotonic() + timeout_ms / 1000 if timeout_ms else None
    until = None
    while True:
        alive = p.poll() is None
        if until is None and not alive:
            return
        cancel = bool(details["on_poll"](p)) if details["on_poll"] else False
        now = time.monotonic()
        if cancel and p.poll() is None:
            details["stopped"] = True
        if until is None and p.poll() is None:
            expired = deadline is not None and now >= deadline
            if cancel or expired:
                details["timed_out"] = expired
                _signal_groups({p.pid}, signal.SIGTERM)
                until = now + GRACE
        if until is not None:
            if not _group_exists(p.pid):
                p.wait()
                return
            if now >= until:
                _signal_groups({p.pid}, signal.SIGKILL)
                p.wait()
                return
        pause = details["poll"]
        limit = until if until is not None else deadline
        if limit is not None:
            pause = min(pause, max(0, limit - time.monotonic()))
        _nap(fd if until is None else None, pause)


def terminate(p):
    """第一次取消：快照後代 groups、TERM；_spawn 在兩秒期限後 KILL 並收屍。

    Linux /proc 補上 nested run_inst 的 setsid 邊界；其他 POSIX 至少處理原 group。
    不追捕終止開始後才新生或已脫離親子樹的 daemon。
    """
    if getattr(p, "_aos_stop", None):
        return
    groups = {p.pid}
    parents = {}
    try:
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % name) as f:
                    fields = f.read().rsplit(")", 1)[1].split()
                parents[int(name)] = (int(fields[1]), int(fields[2]))
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    descendants = {p.pid}
    while True:
        added = {pid for pid, (parent, _) in parents.items() if parent in descendants} - descendants
        if not added:
            break
        descendants.update(added)
    groups.update(parents[pid][1] for pid in descendants if pid in parents)
    groups.discard(os.getpgrp())
    p._aos_stop = (time.monotonic() + GRACE, groups)
    _signal_groups(groups, signal.SIGTERM)


def _signal_groups(groups, sig):
    for group in groups:
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            pass


def _group_exists(group):
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False


def _finish(status, exit_path, note, exit_append=False):
    """收尾：該說的說一句、該寫的 exit 檔寫掉，回 `(那個結束狀態, "child")`。

    走到這裡就代表**跑完了一次**（126／127／逾時也算），所以 kind 是 child、exit 檔照寫；
    只有 exit 檔本身寫不進去才翻成 aos。`exit_append`＝接在檔尾（`exit` 的 append 選項）。
    """
    if note:
        sys.stderr.write("aos-exec: %s\n" % note)
    if exit_path:
        try:
            _write_exit(exit_path, status, exit_append)
        except OSError as e:
            return _err(1, AOS, "exit 檔寫不進去 %s：%s" % (exit_path, e))
    return status, CHILD


def _write_exit(path, status, append=False):
    """`exit` 欄位：十進位結束碼＋一個換行，fsync 檔案與它的父目錄（崩潰後對帳的證據）。
    `append`＝不清空、接在檔尾（一次一行）；不然建立並清空。"""
    d = os.path.dirname(path) or "."
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o666)
    try:
        os.write(fd, ("%d\n" % status).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)

