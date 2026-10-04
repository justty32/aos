"""共用的小工具：錯誤四分支的入口（讀檔 fact、紀錄 hold、例外 Unknown）、原子寫、flock、動作鎖、路徑（spec.md 第 0、2.5 節）。

**錯誤四分支**（spec §0）：N 不存在＝當沒有；U 不知道＝保留現狀、不前進、記一筆（hold）；B 輸入不合＝拒收那一件並回報；
K 中斷＝不偵測，靠「先寫證據再動作」＋重做冪等＋清寫者已死的暫存檔。讀檔一律經 fact，程序一律經 aos7_proc.proc。
任務端的 wait_tock／task_env／read_jsonl 在工具包（modules/tools/aos7_taskside.py）；測試鉤子的本體在 tests/_hooks.py。"""
import contextlib
import datetime
import errno
import json
import os
import re
import stat
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")

# ---------- 錯誤四分支（spec §0） ----------

GONE_ERRNO = (errno.ENOENT, errno.ENOTDIR)   # 只有這兩種算「確定不存在」；其他（EIO、ESTALE、EACCES…）是「看不到」
N, OK, BAD, U = "missing", "ok", "bad", "unknown"


def is_gone(e):
    """OSError e 是不是「確定不存在」。其他錯誤一律是「不知道」。"""
    return isinstance(e, OSError) and e.errno in GONE_ERRNO


def errname(e):
    """OSError 的 errno 名（EIO…），給紀錄的 kind 用。"""
    return errno.errorcode.get(getattr(e, "errno", None), type(e).__name__)


class Unknown(Exception):
    """U 不知道：讀不到、核心自己寫的檔壞掉、/proc 讀不完整、等鎖逾時……呼叫的人保留現狀、不前進、記一筆。
    kind 是錯誤類型（errno 名、round-unknown、lock…）。tick／tock 遇到它什麼都不寫，退出碼 3。"""

    def __init__(self, why, kind="unknown"):
        super().__init__(why)
        self.kind = kind


def hold(where, kind, why, **extra):
    """組一筆「不知道／失敗」紀錄 {"kind", "where", "why", "at"}＋extra（status 的 last_error、總結的 errors、notify_errors
    都用這個格式）。why 太長時保留開頭（錯誤類型、根因）與結尾（路徑、提示），中間換成「…」。"""
    why = str(why)
    if len(why) > 300:
        why = why[:120] + " … " + why[-177:]
    return dict(extra, kind=kind, where=where, why=why, at=now())


_HOOKS = []   # 測試鉤子模組：環境 AOS7_TEST_HOOKS 指到 tests/_hooks.py 才載入；正常環境 inject／test_point 什麼都不做


def _hook(name, *args):
    if not _HOOKS:
        path, mod = os.environ.get("AOS7_TEST_HOOKS"), None
        if path:
            import importlib.util
            spec = importlib.util.spec_from_file_location("aos7_test_hooks", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        _HOOKS.append(mod)
    if _HOOKS[0]:
        getattr(_HOOKS[0], name)(*args)


def inject(op, path):
    """故障注入點（只給測試）。"""
    _hook("inject", op, path)


def test_point(name):
    """SIGKILL／卡住的重現點（只給測試）。"""
    _hook("test_point", name)


def now():
    """給人看的時間字串（ISO 8601、毫秒）；邏輯不依賴牆鐘。"""
    return datetime.datetime.now().isoformat(timespec="milliseconds")


# ---------- 讀寫檔（spec §0） ----------

def fact(path, dir_fd=None):
    """核心讀 JSON 檔的唯一入口，回 (狀態, 值)：(N, None) 確定不存在｜(OK, 值) 讀到（型別由呼叫的人看）｜
    (BAD, 說明) 一般檔、讀得到，但不是 JSON｜(U, 說明) 讀不到，或存在但不是一般檔（FIFO、資料夾、socket）。

    BAD 怎麼歸由呼叫的人照「誰寫的檔」決定：核心自己寫的檔壞了＝U（只可能是被手改或磁碟壞）；別人寫給核心的（tasks.json、
    timeline.json、控制請求）壞了＝B（拒收那一件並回報）。非阻塞開，FIFO 不會卡住讀的人。"""
    name = os.path.basename(str(path))
    notreg = U, "%s 存在但不是一般檔，讀不出內容" % name
    try:
        inject("open", path)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as e:
        if e.errno in GONE_ERRNO:
            return N, None
        return notreg if e.errno in (errno.ENXIO, errno.EISDIR) else (U, "%s 讀不到：%r" % (name, e))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return notreg
        with os.fdopen(fd, "rb") as f:
            data = f.read()
    except OSError as e:
        return U, "%s 讀不到：%r" % (name, e)
    try:
        return OK, json.loads(data.decode("utf-8"))
    except ValueError:
        return BAD, "%s 不是 JSON（半寫或寫壞）" % name


def read_json(path, default=None):
    """寬鬆讀：不是 OK 就回 default。只給「讀不到照預設也無妨」的地方（顯示、提示）；判定一律用 fact。"""
    st, v = fact(path)
    return v if st == OK else default


def write_json(path, obj):
    """原子寫：先寫 `.<名>.tmp.<pid>` 再 rename（列資料夾的人略過 `.` 開頭的，不會讀到半份）；需要的話建資料夾。
    被殺在 rename 之前會留下暫存檔，寫者確定不在之後由 sweep_tmp 清。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    test_point("tmp:" + os.path.basename(path))
    os.replace(tmp, path)


TMP_RE = re.compile(r"^\.(.+)\.tmp\.([0-9]+)$")


def sweep_tmp(d):
    """清掉資料夾 d 裡寫者已經不在的暫存檔 `.<名>.tmp.<pid>`，回清掉的檔名。只有 pid 確定不在（ESRCH）才刪；
    pid 在（可能被重用）、看不到、列不出資料夾都保留，下次再看。"""
    out = []
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for n in names:
        m = TMP_RE.match(n)
        if not m:
            continue
        try:
            os.kill(int(m.group(2)), 0)
            continue                     # 寫者還在（或 pid 被重用）
        except ProcessLookupError:
            pass
        except OSError:
            continue                     # EPERM：程序在，只是不是我們的
        try:
            os.unlink(os.path.join(d, n))
            out.append(n)
        except OSError:
            pass
    return out


def append_jsonl(path, obj):
    """流水帳加一行（事件 log.jsonl、歷史）。檔尾是沒寫完的半行（上次 append 被殺）就先補換行，新的一行不會跟它黏成一條壞行。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a+b") as f:
        end = f.seek(0, os.SEEK_END)
        if end and os.pread(f.fileno(), 1, end - 1) != b"\n":
            f.write(b"\n")
        f.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))


# ---------- 鎖（spec §0、§2.5） ----------

class LockTimeout(Unknown):
    """等鎖超過時限（U 的一種：這次不做，下次再試）。"""

    def __init__(self, why):
        super().__init__(why, kind="lock")


@contextlib.contextmanager
def locked(path, timeout=None):
    """對 `<path>.lock` 拿 flock（多人讀—改—寫同一個檔的約定）。timeout 秒內拿不到丟 LockTimeout；None＝一直等。
    鎖檔不 unlink：保留同一個 inode，等鎖的與新來的才不會各鎖一份。"""
    import fcntl
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    end = None if timeout is None else time.monotonic() + timeout
    with open(path + ".lock", "a") as lk:
        while True:
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | (0 if end is None else fcntl.LOCK_NB))
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise LockTimeout(path) from None
                time.sleep(0.01)
        yield


def edit_json(path, fn, default=None, timeout=None):
    """讀—改—寫一個 JSON 檔，期間拿 `<path>.lock`（tasks.json 的寫的人都用它，不會互相蓋掉）。fn(舊內容) 回新內容，None＝不寫。
    舊內容照三態：不存在＝交給 fn 的是 default；讀不到或壞掉＝不知道原本有什麼 → 丟 Unknown、不寫（絕不當空表把整份換掉，G1）。"""
    with locked(path, timeout):
        st, cur = fact(path)
        if st not in (OK, N):
            raise Unknown("%s %s，不知道原本有什麼，沒寫" % (os.path.basename(path), cur), kind=st)
        new = fn(cur if st == OK else default)
        if new is not None:
            write_json(path, new)
        return new


# ---------- 回合與總結（spec §2.2、§3、§7） ----------

ROUND_OPEN, ROUND_CLOSED, ROUND_NONE = "open", "closed", "none"


def read_round(path):
    """round.json 的判定（daemon、tick、tock 共用），回 (狀態, 內容, 說明)：(ROUND_OPEN／ROUND_CLOSED, r, None)＝物件、
    `round` 整數、`open` 是 true／false（只有明確的 false 才是已關）｜(ROUND_NONE, None, None) 確定不存在（新空間）｜
    (U, None, 說明) 讀不到、不是一般檔、半寫、缺欄、型別不對——不知道，不能當已關。"""
    st, r = fact(path)
    if st == N:
        return ROUND_NONE, None, None
    if st == OK and isinstance(r, dict) and is_int(r.get("round")) and isinstance(r.get("open"), bool):
        return (ROUND_OPEN if r["open"] else ROUND_CLOSED), r, None
    if st == U:
        return U, None, r
    return U, None, ("round.json 內容不完整（%s）；要 {\"round\": 整數, \"open\": true/false}，確認上一回合收完後請人寫回，"
                     "例如 {\"round\": N, \"open\": false}" % (r if st == BAD else json.dumps(r, ensure_ascii=False)[:120]))


def summary_ok(lr):
    """last-round.json 是不是一份完整的總結（物件、round 整數、tock_at 字串、started／alive／ended 陣列）。不完整的不拿來重播。"""
    return (isinstance(lr, dict) and is_int(lr.get("round")) and isinstance(lr.get("tock_at"), str)
            and all(isinstance(lr.get(k), list) for k in ("started", "alive", "ended")))


# ---------- 動作鎖與世代（spec §2.5） ----------

def proc_starttime(pid):
    """程序的啟動時間（`/proc/<pid>/stat` 第 22 欄）；讀不到回 None。跟 pid 一起記，才認得出還是不是同一個程序（pid 會重用）。"""
    try:
        inject("proc-stat", "/proc/%d/stat" % pid)
        with open("/proc/%d/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return None


OWNER = "action.owner.json"   # `<node>/.aos/action.owner.json`：現在（或最後）拿著 action.lock 的動作是誰


@contextlib.contextmanager
def action_lock(root, node):
    """tick／tock 整個動作期間拿 `<node>/.aos/action.lock`，拿到後比 daemon 世代：yield True＝現役、可以寫；
    False＝舊 daemon 起的動作（環境 AOS7_GEN 跟 gen.json 不同），什麼都不要寫。沒有 AOS7_GEN（人手跑）不比。
    gen.json 不能用＝不知道 → 丟 Unknown。確定是現役才寫 action.owner.json（pid、gen、starttime），給新 daemon 認出舊持有者。
    node 被刪時開不了鎖檔（FileNotFoundError），呼叫的人當 gone。"""
    import fcntl
    with open(os.path.join(node, ".aos", "action.lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        mine = os.environ.get("AOS7_GEN")
        if mine is not None:
            # 拿到鎖之後才比：排在新 daemon 動作後面的舊動作，這時一定看得到世代換了
            st, cur = fact(os.path.join(root, ".aosd", "gen.json"))
            if st != OK or not isinstance(cur, dict) or not is_int(cur.get("gen")):
                raise Unknown("gen.json 不能用（%s），分不出自己是不是舊世代的動作，什麼都沒寫" % cur, kind="gen-unknown")
            if str(cur["gen"]) != mine:
                yield False
                return
        try:
            write_json(os.path.join(node, ".aos", OWNER),
                       {"pid": os.getpid(), "gen": int(mine) if mine and mine.isdigit() else None,
                        "starttime": proc_starttime(os.getpid()), "at": now()})
        except OSError:
            pass
        yield True


def reap_stale_owner(node, gen):
    """動作等 action.lock 逾時後呼叫：鎖沒人拿回 (None, None)；持有者是舊世代、而且 pid 的啟動時間跟它記的一樣（確定是
    同一個程序）→ SIGKILL 它（鎖跟著放掉）、回 (pid, None)；拿著鎖卻認不出身分＝不知道 → 不殺，回 (None, 原因)。"""
    import fcntl
    import signal
    try:
        fd = os.open(os.path.join(node, ".aos", "action.lock"), os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None, None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return None, None
    except OSError:
        pass
    finally:
        os.close(fd)
    ow = read_json(os.path.join(node, ".aos", OWNER))
    pid, og, st = (ow.get("pid"), ow.get("gen"), ow.get("starttime")) if isinstance(ow, dict) else (None, None, None)
    if not (is_int(pid) and pid > 1 and pid != os.getpid()):
        return None, "action.owner.json 讀不到、壞了或缺 pid，認不出持鎖者"
    if not (is_int(og) and is_int(gen) and og < gen):
        return None, "持鎖者 pid %d 記的世代 %r 不比現在的 %r 舊，不是舊 daemon 留下的" % (pid, og, gen)
    if st is None or proc_starttime(pid) != st:
        return None, "pid %d 的啟動時間認不出或對不上（pid 可能已被重用），無法確認還是同一個程序" % pid
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError as e:
        return None, "SIGKILL pid %d 失敗：%r" % (pid, e)
    return pid, None


# ---------- 路徑與環境 ----------

FD_PREFIX = "/proc/self/fd/"


def node_path(root, node_id):
    """node id → 絕對路徑（根是 "."）。"""
    root = os.path.abspath(root)
    return root if node_id in (".", "") else os.path.join(root, node_id)


def canonical_node(root, node_id):
    """node 的實際身分路徑＝realpath(root)／node_id；登記時 node 的 realpath 要等於它（路上不能有符號連結）。"""
    r = os.path.realpath(root)
    return r if node_id in (".", "") else os.path.join(r, node_id)


def env_with_bin(env=None):
    """複製一份環境，PATH 前面加上 proto7-2 的 bin/。"""
    env = dict(os.environ if env is None else env)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    return env


def is_int(v):
    """真的整數（JSON 的 true／false 不算）。"""
    return isinstance(v, int) and not isinstance(v, bool)
