"""proto7-1 共用的小工具：JSON 檔讀寫（原子）、時間字串、路徑、任務環境（spec.md 第 0、5 節）。"""
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


def edit_json(path, fn, default=None):
    """讀—改—寫一個 JSON 檔，期間對 `<path>.lock` 拿 flock（多個寫的人約定都用它，就不會互相蓋掉；probes/selfmod、lifecycle）。

    fn(舊內容) 回新內容；回 None＝不寫。回寫進去的內容。tick 只讀不拿鎖（寫是原子的，讀到的一定是完整的一版）。"""
    import fcntl
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        new = fn(read_json(path, default))
        if new is not None:
            write_json(path, new)
        return new


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


def tail_jsonl(path, k, block=65536):
    """流水帳最後 k 行（壞行跳過）：從檔尾往回一塊一塊讀，不讀整個檔（astra-3 三-3）。"""
    if k <= 0:
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos, buf = f.tell(), b""
            while pos > 0 and buf.count(b"\n") <= k:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
    except OSError:
        return []
    lines = buf.split(b"\n")
    if pos > 0:
        lines = lines[1:]  # 第一段可能是半行
    out = []
    for line in lines[-(k + 1):]:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out[-k:]


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


TASK_DIRS = ("tasks", "tasks-old")   # 任務資料夾在 `.aos/tasks/`；tock 把結束很久的搬到 `.aos/tasks-old/`（Q3）


def task_dirs_of(aos):
    """`<aos>/tasks/` 與 `<aos>/tasks-old/` 底下所有任務資料夾：[(tid, 路徑)]，依 tid 排序（tasks 的在前）。

    同一個 tid 只回一次（列完 tasks/、列 tasks-old/ 之前剛好被 tock 搬過去的，不重複算；astra-5 F-02）。"""
    out, seen = [], set()
    for sub in TASK_DIRS:
        base = os.path.join(aos, sub)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for t in names:
            if not t.startswith(".") and t not in seen:
                seen.add(t)
                out.append((t, os.path.join(base, t)))
    return out


def locate_task(aos, tid):
    """tid 現在的資料夾（先 tasks/ 再 tasks-old/）；都沒有回 None。"""
    for sub in TASK_DIRS:
        d = os.path.join(aos, sub, tid)
        if os.path.isdir(d):
            return d
    return None


def task_read(aos, tid, d, fn, tries=3):
    """穩定地讀一個任務資料夾（astra-5 F-02）：fn(d) 讀需要的檔、回結果；讀完時 d 已經不在
    （讀到一半被 tock 搬到 tasks-old/），就重新定位、整份重讀。回 (資料夾, 結果)；
    任務哪裡都找不到、或一直在搬，回 (None, None)＝讀不齊（unknown），呼叫的人不能把它當「沒有」或 0。"""
    for _ in range(tries):
        try:
            v = fn(d)
        except (FileNotFoundError, NotADirectoryError):
            v = None
            ok = False
        else:
            ok = True
        if ok and os.path.isdir(d):
            return d, v
        d = locate_task(aos, tid)
        if d is None:
            return None, None
    return None, None


def task_env():
    """任務從環境變數讀自己是誰（spec 第 5 節）。缺了丟 KeyError。"""
    e = os.environ
    return {"root": e["AOS7_ROOT"], "node": e["AOS7_NODE"], "node_id": e["AOS7_NODE_ID"],
            "task": e["AOS7_TASK"], "tid": e["AOS7_TID"]}


def wait_tock(task_dir, last_round, poll=0.02, timeout=None):
    """等 tock.json 的 round 比 last_round 大，回新的 round；逾時回 None（S-11）。"""
    path = os.path.join(task_dir, "tock.json")
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        t = read_json(path)
        # 不是物件（`[1]`、`2`）當沒有、繼續等（astra-5 F-06）
        if isinstance(t, dict) and isinstance(t.get("round"), int) and t["round"] > last_round:
            return t["round"]
        if end is not None and time.monotonic() >= end:
            return None
        time.sleep(poll)


def env_with_bin(env=None):
    """複製一份環境，PATH 前面加上 proto7-1 的 bin/。"""
    env = dict(os.environ if env is None else env)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    return env
