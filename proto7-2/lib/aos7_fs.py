"""proto7-2 共用的小工具：JSON 檔讀寫（原子、三態）、時間字串、路徑、動作鎖、任務環境（spec.md 第 0、2.5、5 節）。

起點複製自 proto7-1 lib/aos7_fs.py，拿掉 tasks-old／tail_jsonl，加上三態讀檔 read_json3 與 edit_json 的等鎖逾時。"""
import contextlib
import datetime
import json
import os
import stat
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


def now():
    """給人看的時間字串（spec 第 0 節：邏輯不依賴它）。"""
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def read_json(path, default=None):
    """讀 JSON 檔；不存在、壞掉或不是一般檔（FIFO、資料夾…）回 default。

    用 O_NONBLOCK 開：控制檔、tasks.json、spawn 被換成 FIFO 時不會卡死 daemon 主迴圈或 tick（probes/chaos B10、llmops）。"""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return default
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return default
        with os.fdopen(fd, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def is_regular(path):
    """path 是一般檔（不跟符號連結以外的特殊檔：FIFO、資料夾、裝置都回 False）。"""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def write_json(path, obj):
    """原子寫：先寫暫存檔再 rename；需要的話建資料夾。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    # 暫存檔以 `.` 開頭：別人列資料夾（`*.json`、sh 的 `ls`）時不會讀到寫一半的檔（probes/polyglot N11）
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


class LockTimeout(Exception):
    """edit_json／locked 等鎖超過時限。"""


@contextlib.contextmanager
def locked(path, timeout=None):
    """對 `<path>.lock` 拿 flock（spec 第 0 節：多人讀—改—寫同一個檔的約定）。timeout 秒內拿不到丟 LockTimeout；None＝一直等。"""
    import fcntl
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path + ".lock", "a") as lk:
        if timeout is None:
            fcntl.flock(lk, fcntl.LOCK_EX)
        else:
            end = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= end:
                        raise LockTimeout(path) from None
                    time.sleep(0.01)
        yield


def edit_json(path, fn, default=None, timeout=None):
    """讀—改—寫一個 JSON 檔，期間拿 `<path>.lock`（tasks.json、paused.json 的寫的人都用它，就不會互相蓋掉）。

    fn(舊內容) 回新內容；回 None＝不寫。回寫進去的內容。timeout 見 locked。"""
    with locked(path, timeout):
        new = fn(read_json(path, default))
        if new is not None:
            write_json(path, new)
        return new


# ---------- 三態讀檔（spec 第 0 節） ----------

OK, MISSING, BAD, IO = "ok", "missing", "bad", "io"


def read_json3(path, dir_fd=None):
    """讀 JSON，分清楚三態：回 (狀態, 值)。

    - ("ok", 值)：讀到、解得開（值可能不是物件，型別由呼叫的人看）。
    - ("missing", None)：確定不存在（ENOENT／ENOTDIR），或不是一般檔（FIFO、資料夾當不存在；spec 第 0 節）。
    - ("bad", None)：一般檔、讀得到，但不是 JSON（人手寫壞）。
    - ("io", 錯誤字串)：讀不到（EIO、EACCES、ESTALE…）＝**不知道**，不能當不存在也不能當壞掉去做破壞性動作。"""
    import errno
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.ENXIO):
            return MISSING, None
        if e.errno == errno.EISDIR:
            return MISSING, None
        return IO, repr(e)[:200]
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return MISSING, None
        with os.fdopen(fd, "rb") as f:
            data = f.read()
    except OSError as e:
        return IO, repr(e)[:200]
    try:
        return OK, json.loads(data.decode("utf-8"))
    except ValueError:
        return BAD, None


def test_point(name):
    """只給測試：環境 AOS7_TEST_CRASH 列到 name（逗號分隔）就在這裡 SIGKILL 自己，模擬 kill -9 打在這一步。"""
    want = os.environ.get("AOS7_TEST_CRASH")
    if want and name in want.split(","):
        import signal
        os.kill(os.getpid(), signal.SIGKILL)
    hang = os.environ.get("AOS7_TEST_HANG")
    if hang and name in hang.split(","):
        time.sleep(10 ** 6)


def proc_starttime(pid):
    """程序的啟動時間（`/proc/<pid>/stat` 第 22 欄，開機後的 clock tick）；程序不在回 None。

    跟 pid 一起記，才認得出「還是同一個程序」（pid 會被重用；astra-5 F-04）。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return None


OWNER = "action.owner.json"   # `<node>/.aos/action.owner.json`：現在（或最後）拿著 action.lock 的動作是誰


@contextlib.contextmanager
def action_lock(root, node):
    """tick／tock 整個動作期間對 `<node>/.aos/action.lock` 拿 flock，拿到後比對 daemon 世代（astra-4 I-01）。

    yield True＝可以寫；False＝自己是舊 daemon 起的動作（環境 AOS7_GEN 跟 `<root>/.aosd/gen.json` 不同），什麼都不要寫。
    新 daemon 先換世代才起時間線；舊動作要嘛在新動作之前做完（拿著鎖時新的進不來），要嘛拿到鎖時看到世代變了。
    沒有 AOS7_GEN（人手跑、測試）不比對。

    拿到鎖後寫 `.aos/action.owner.json`＝`{"pid","gen","starttime"}`：新 daemon 的動作等鎖逾時時，靠它認出
    「舊世代、還是同一個程序」的持有者並 SIGKILL（astra-5 F-04；不 unlink 鎖檔）。node 是動作拿著的路徑
    （tick／tock 給的是 `/proc/self/fd/N`，node 被刪時開不了鎖檔 → FileNotFoundError，由呼叫的人當 gone）。"""
    import fcntl
    with open(os.path.join(node, ".aos", "action.lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        mine = os.environ.get("AOS7_GEN")
        try:
            write_json(os.path.join(node, ".aos", OWNER),
                       {"pid": os.getpid(), "gen": int(mine) if mine and mine.isdigit() else None,
                        "starttime": proc_starttime(os.getpid()), "at": now()})
        except OSError:
            pass
        cur = read_json(os.path.join(root, ".aosd", "gen.json"), {}) or {}
        yield mine is None or not isinstance(cur, dict) or str(cur.get("gen")) == mine


def reap_stale_owner(node, gen):
    """新 daemon（世代 gen）的動作等 action.lock 逾時後呼叫：持有者是舊世代、而且 pid 的啟動時間跟它記的一樣
    （確定是同一個程序）就 SIGKILL 它，鎖跟著放掉，下一圈重試（astra-5 F-04）。回被殺的 pid 或 None。"""
    import signal
    ow = read_json(os.path.join(node, ".aos", OWNER))
    if not isinstance(ow, dict):
        return None
    pid, og, st = ow.get("pid"), ow.get("gen"), ow.get("starttime")
    if not (isinstance(pid, int) and pid > 1 and pid != os.getpid() and isinstance(og, int) and isinstance(gen, int)
            and og < gen and st is not None and proc_starttime(pid) == st):
        return None
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return None
    return pid


def holder_unverified(node, gen):
    """reap_stale_owner 沒殺時呼叫：action.lock 現在真的有人拿著、卻無法確認是舊世代的同一個程序，回說明 dict
    {"pid", "why", "hint"}；鎖沒人拿（例如逾時的是自己的動作、已被收掉）回 None。不殺任何程序（astra-6 G-10）。"""
    import fcntl
    try:
        fd = os.open(os.path.join(node, ".aos", "action.lock"), os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        held = True
    else:
        held = False
    finally:
        os.close(fd)
    if not held:
        return None
    ow = read_json(os.path.join(node, ".aos", OWNER))
    pid = ow.get("pid") if isinstance(ow, dict) else None
    if not isinstance(ow, dict):
        why = "action.owner.json 讀不到或壞了，認不出持鎖者"
    elif not (isinstance(pid, int) and pid > 1):
        why = "action.owner.json 缺 pid（拿到 %r）" % (pid,)
    elif not isinstance(ow.get("gen"), int):
        why = "action.owner.json 缺 gen（拿到 %r），分不出是不是舊 daemon 的" % (ow.get("gen"),)
    elif isinstance(gen, int) and ow["gen"] >= gen:
        why = "持鎖者記的世代 %d 不比現在的 %d 舊，不是舊 daemon 留下的" % (ow["gen"], gen)
    elif ow.get("starttime") is None:
        why = "action.owner.json 缺 starttime（寫的當下讀不到 /proc），無法確認 pid %d 還是同一個程序" % pid
    else:
        cur = proc_starttime(pid)
        why = ("讀不到 /proc/%d/stat（程序不在或沒權限），無法確認身分" % pid if cur is None else
               "pid %d 的啟動時間 %s 跟紀錄的 %s 不符（pid 可能已被重用）" % (pid, cur, ow.get("starttime")))
    hint = ("沒殺任何程序。請人工確認是誰拿著 %s（例如 `fuser`／`lsof`）：確定是舊的 tick／tock 就 kill 它，"
            "或補正 action.owner.json 的 pid／gen／starttime，下一次逾時會自動回收" % os.path.join(real_path(node), ".aos",
                                                                                       "action.lock"))
    return {"pid": pid if isinstance(pid, int) else None, "why": why, "hint": hint}


FD_PREFIX = "/proc/self/fd/"


def real_path(p):
    """`/proc/self/fd/N/...`（tick／tock 抓著 node 的 fd 寫檔；astra-5 F-09）→ 現在的實際路徑；其他原樣。"""
    if not p.startswith(FD_PREFIX):
        return p
    rest = p[len(FD_PREFIX):]
    fd, _, tail = rest.partition("/")
    try:
        base = os.readlink(FD_PREFIX + fd)
    except OSError:
        return p
    if base.endswith(" (deleted)"):
        base = base[:-len(" (deleted)")]
    return os.path.join(base, tail) if tail else base


def append_jsonl(path, obj):
    """流水帳加一行。檔尾是沒寫完的一行（上次 append 中途被殺、沒有換行結尾）就先補換行，
    新的一行獨立成行，不會跟半行黏成一條壞行（astra-6 G-08）。回補換行前那段半行的位元組數（沒有是 0）。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a+b") as f:
        end = f.seek(0, os.SEEK_END)
        torn = 0
        if end and os.pread(f.fileno(), 1, end - 1) != b"\n":
            back = min(end, 1 << 20)
            tail = os.pread(f.fileno(), back, end - back)
            torn = len(tail) - (tail.rfind(b"\n") + 1)
            f.write(b"\n")
        f.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    return torn


def read_jsonl(path, with_bad=False):
    """讀流水帳，壞行跳過。以 bytes 逐行讀、每行各自 UTF-8 解碼＋json.loads：半個 UTF-8 字元（append 被殺在多 byte 字元中間）
    也只壞那一行，後面的合法行照讀，不會整檔丟例外或回空清單（astra-7 H-04）。with_bad=True 時回 (紀錄, 壞行數)；
    空行不算壞行。"""
    out, bad = [], 0
    try:
        with open(path, "rb") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line.decode("utf-8")))
                except ValueError:   # UnicodeDecodeError 也是 ValueError
                    bad += 1
    except OSError:
        pass
    return (out, bad) if with_bad else out


def node_path(root, node_id):
    """node id → 絕對路徑（根是 "."）。"""
    root = os.path.abspath(root)
    return root if node_id in (".", "") else os.path.join(root, node_id)


def node_id_of(root, path):
    """絕對路徑 → node id。"""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return "." if rel == "." else rel.replace(os.sep, "/")


def join_id(base, rel):
    """node id 接相對路徑（kernel 算成員 id 用）。"""
    if base in (".", ""):
        return os.path.normpath(rel).replace(os.sep, "/")
    return os.path.normpath(os.path.join(base, rel)).replace(os.sep, "/")




def aos_dir(node):
    return os.path.join(node, ".aos")


def task_env():
    """任務從環境變數讀自己是誰（spec 5.5）。缺了丟 KeyError。"""
    e = os.environ
    return {"root": e["AOS7_ROOT"], "node": e["AOS7_NODE"], "node_id": e["AOS7_NODE_ID"],
            "task": e["AOS7_TASK"], "tid": e["AOS7_TID"], "run": int(e["AOS7_RUN"])}


def wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None):
    """等 tock.json 的 round 比 last_round 大，回新的 round；逾時回 None（S-11）。

    run＝這次執行的 run（預設取環境 AOS7_RUN）：tock.json 的 `run` 對不上（上一個 run 沒清乾淨的）當不存在（spec 5.1）。"""
    if run is None and os.environ.get("AOS7_RUN", "").isdigit():
        run = int(os.environ["AOS7_RUN"])
    path = os.path.join(task_dir, "tock.json")
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        t = read_json(path)
        if isinstance(t, dict) and isinstance(t.get("round"), int) and t["round"] > last_round \
                and (run is None or t.get("run") == run):
            return t["round"]
        if end is not None and time.monotonic() >= end:
            return None
        time.sleep(poll)


def env_with_bin(env=None):
    """複製一份環境，PATH 前面加上 proto7-2 的 bin/。"""
    env = dict(os.environ if env is None else env)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    return env


def is_int(v):
    """真的整數（bool 不算）。"""
    return isinstance(v, int) and not isinstance(v, bool)
