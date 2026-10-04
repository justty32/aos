"""proto7-2 共用的小工具：JSON 檔讀寫（原子、三態）、時間字串、路徑、動作鎖、PATH 加 bin（spec.md 第 0、2.5、5 節）。
任務端的 wait_tock／task_env 在工具包（modules/tools/aos7_taskside.py）；測試鉤子的本體在 tests/_hooks.py。

起點複製自 proto7-1 lib/aos7_fs.py，拿掉 tasks-old／tail_jsonl，加上三態讀檔 read_json3 與 edit_json 的等鎖逾時。

daemon、tick／tock、ctl 與普通任務共用；依呼叫者給的 path 讀寫 JSON／JSONL 與 .lock，
並讀 /proc 的程序身分。動作鎖另讀 .aosd/gen.json、寫 .aos/action.owner.json；不自行推進回合。"""
import contextlib
import datetime
import errno
import json
import os
import re
import stat
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


# ---------- 三態的共同小工具（spec 第 0 節；A2-01 把判定收斂到這裡與 aos7_proc、aos7_task.judge） ----------

GONE_ERRNO = (errno.ENOENT, errno.ENOTDIR)   # 只有這兩種算「確定不存在」；其他（EIO、ESTALE、EACCES…）是「看不到」


def is_gone(e):
    """OSError e 是不是「確定不存在」（ENOENT／ENOTDIR）。其他錯誤一律是「不知道」，呼叫的人要保留現狀（spec §0）。"""
    return isinstance(e, OSError) and e.errno in GONE_ERRNO


class Unknown(Exception):
    """推定不了的事實（round.json 讀不到、gen.json 不能用、看不到 node…）：tick／tock 什麼都不寫，退出碼 3（P2-09）。"""


_HOOKS = []   # 測試鉤子模組（tests/_hooks.py）：環境 AOS7_TEST_HOOKS 指到它才載入；正常環境 inject／test_point 什麼都不做


def _hooks():
    """第一次呼叫時照 AOS7_TEST_HOOKS 載入測試鉤子模組，回它或 None。"""
    if not _HOOKS:
        path, mod = os.environ.get("AOS7_TEST_HOOKS"), None
        if path:
            import importlib.util
            spec = importlib.util.spec_from_file_location("aos7_test_hooks", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        _HOOKS.append(mod)
    return _HOOKS[0]


def inject(op, path):
    """故障注入點（只給測試）：有鉤子模組就交給它決定要不要丟 OSError。"""
    if _hooks():
        _HOOKS[0].inject(op, path)


def now():
    """給人看的時間字串（spec 第 0 節：邏輯不依賴它）。

    無參數；回本機 ISO 8601 字串，精度毫秒。"""
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def read_json(path, default=None):
    """讀 JSON 檔；不存在、壞掉或不是一般檔（FIFO、資料夾…）回 default。

    用 O_NONBLOCK 開：控制檔、tasks.json、spawn 被換成 FIFO 時不會卡死 daemon 主迴圈或 tick（probes/chaos B10、llmops）。

    path 是檔案路徑，default 是失敗時的回值；成功回任意 JSON 值。此寬鬆介面不分失敗原因，
    要保留「不知道」的生命週期判定應用 read_json3（spec §0）。"""
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
    """path 指向一般檔嗎（跟隨符號連結；FIFO、資料夾、裝置都回 False）。

    參數 path 可為符號連結（會跟隨）；回 bool，stat 讀不到也回 False，並非三態判定（spec §0）。"""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def write_json(path, obj):
    """原子寫：先寫暫存檔再 rename；需要的話建資料夾。

    path 是目的檔、obj 是可 JSON 編碼的值；成功回 None，寫入失敗向外拋例外（spec §0）。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    # spec §0：暫存檔以 `.` 開頭，列資料夾時不讀到半份 JSON（probes/polyglot N11）。
    # 被 SIGKILL 在 rename 之前會留下暫存檔：寫者 pid 不在之後由 sweep_tmp 清（A2-07）。
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    test_point("tmp:" + os.path.basename(path))
    os.replace(tmp, path)


TMP_RE = re.compile(r"^\.(.+)\.tmp\.([0-9]+)$")


def sweep_tmp(d):
    """清掉資料夾 d 裡「寫者已經不在」的原子寫暫存檔 `.<名>.tmp.<pid>`（A2-07）。回清掉的檔名清單。

    write_json／aos7-run 的 write_at 被 SIGKILL 在 rename 之前會留下它們，平常沒人收就會一直累積。
    只看 pid 確定不在（kill(0) 回 ESRCH）才刪；pid 在（可能被重用）、看不到、列不出資料夾都保留，下次再看（spec §0）。
    tick／tock 在拿著 action.lock 時清自己的 `.aos/` 與槽；daemon 清 `.aosd/`、`ctl/`、`ctl-done/`。"""
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
            continue                     # 寫者還在（或 pid 被重用）：不動
        except ProcessLookupError:
            pass
        except OSError:
            continue                     # EPERM 等：程序在，只是不是我們的
        try:
            os.unlink(os.path.join(d, n))
            out.append(n)
        except OSError:
            pass
    return out


class LockTimeout(Exception):
    """edit_json／locked 等鎖超過時限。"""


@contextlib.contextmanager
def locked(path, timeout=None):
    """對 `<path>.lock` 拿 flock（spec 第 0 節：多人讀—改—寫同一個檔的約定）。timeout 秒內拿不到丟 LockTimeout；None＝一直等。

    path 是資料檔路徑；作為 context manager yield None，區塊結束時關 fd 釋放鎖。"""
    import fcntl
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    # spec §0、§2.5：只關 fd 釋鎖，不 unlink；保留同一 inode 才不會讓等鎖者與新來者各鎖一份。
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

    fn(舊內容) 回新內容；回 None＝不寫。回寫進去的內容。timeout 見 locked。

    path 是目的檔；default 供讀不到時交給 fn；回 fn 的結果（含 None），鎖／寫入錯誤向外拋。"""
    with locked(path, timeout):
        new = fn(read_json(path, default))
        if new is not None:
            write_json(path, new)
        return new


# ---------- 三態讀檔（spec 第 0 節） ----------

OK, MISSING, BAD, IO = "ok", "missing", "bad", "io"


def read_json3(path, dir_fd=None, strict=False):
    """讀 JSON，分清楚三態：回 (狀態, 值)。

    - ("ok", 值)：讀到、解得開（值可能不是物件，型別由呼叫的人看）。
    - ("missing", None)：確定不存在（ENOENT／ENOTDIR）；`strict=False` 時不是一般檔（FIFO、資料夾、socket）也當不存在。
    - ("bad", None)：一般檔、讀得到，但不是 JSON（人手寫壞）。
    - ("io", 錯誤字串)：讀不到（EIO、EACCES、ESTALE…）＝**不知道**，不能當不存在也不能當壞掉去做破壞性動作。

    **strict=True 給生命週期檔**（round.json、last-round.json、birth.json、pid.json、exit.json；A3-03）：存在但不是一般檔
    ＝「有東西在那裡、讀不出內容」＝不知道，回 ("io", 說明)，不當不存在——否則把 birth.json 換成 FIFO 會被當空槽而雙開、
    把開著的 round.json 換成 FIFO 會從 last-round.json 接號再開同一回合。照樣非阻塞開，FIFO 不會卡住讀的人。
    其他檔（控制垃圾、tasks.json、timeline.json…）維持「當不存在」。

    path 是檔案路徑，dir_fd 可指定相對路徑的基準目錄 fd。四種讀檔結果供上層組成
    是／否／不知道三態；BAD 如何解讀由該檔案的契約決定，不混同 I/O 失敗。"""
    notreg = (IO, "%s 存在但不是一般檔（FIFO、資料夾…），讀不出內容（A3-03）" % os.path.basename(str(path))) \
        if strict else (MISSING, None)
    try:
        inject("open", path)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return MISSING, None
        if e.errno in (errno.ENXIO, errno.EISDIR):
            return notreg   # socket 等開不了的特殊檔、資料夾：有東西，不是一般檔
        return IO, repr(e)[:200]
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return notreg
        with os.fdopen(fd, "rb") as f:
            data = f.read()
    except OSError as e:
        return IO, repr(e)[:200]
    try:
        return OK, json.loads(data.decode("utf-8"))
    except ValueError:
        return BAD, None


ROUND_OPEN, ROUND_CLOSED, ROUND_NONE = "open", "closed", "none"


def read_round(path):
    """round.json 的三態（spec §2.2、§3；A2-02）：回 (狀態, 內容, 說明)。daemon、tick、tock 都只用這一個判定。

    - ("open", r, None)／("closed", r, None)：物件、`round` 是整數、`open` 是 true／false——**只有明確的 `open: false` 才是已關的證據**。
    - ("none", None, None)：確定不存在（新空間、或被人刪了；tick 照 last-round.json 接著數）。
    - (IO, None, 說明)：讀不到。
    - (BAD, 內容, 說明)：半寫、不是物件、缺 `open`、型別不對——跟讀不到一樣是「不知道」，不能當已關（不然會跳過或覆蓋未提交的回合）。"""
    st, r = read_json3(path, strict=True)   # A3-03：round.json 被換成 FIFO／資料夾＝不知道，不是新空間
    if st == MISSING:
        return ROUND_NONE, None, None
    if st == IO:
        return IO, None, "round.json 讀不到：%s" % r
    if st == OK and isinstance(r, dict) and is_int(r.get("round")) and isinstance(r.get("open"), bool):
        return (ROUND_OPEN if r["open"] else ROUND_CLOSED), r, None
    shown = "半寫或不是 JSON" if st == BAD else json.dumps(r, ensure_ascii=False)[:120]
    return BAD, r, ("round.json 內容不完整（%s）；要 {\"round\": 整數, \"open\": true/false}，"
                    "確認上一回合收完後請人寫回，例如 {\"round\": N, \"open\": false}" % shown)


def summary_ok(lr):
    """last-round.json 的內容是不是一份完整的總結（tock 自己寫的那種）：物件、round 是整數、tock_at 是字串、
    started／alive／ended 是陣列（spec §3、§7）。不完整的不拿來重播，tock 照常重新產生一份（A2-02 疑點：原本只比 round）。
    tock 自己寫的總結是原子寫、寫完讀回確認，只有人手寫壞的才會走到這裡；那時已補過 seen_round 的結束不會再報（核心不補）。"""
    return (isinstance(lr, dict) and is_int(lr.get("round")) and isinstance(lr.get("tock_at"), str)
            and all(isinstance(lr.get(k), list) for k in ("started", "alive", "ended")))


def test_point(name):
    """SIGKILL／卡住的重現點（只給測試，P2-15）：有鉤子模組就交給它。"""
    if _hooks():
        _HOOKS[0].test_point(name)


def proc_starttime(pid):
    """程序的啟動時間（`/proc/<pid>/stat` 第 22 欄，開機後的 clock tick）；讀不到回 None。

    跟 pid 一起記，才認得出「還是同一個程序」（pid 會被重用；astra-5 F-04）。

    pid 是程序號；成功回 int，讀不到或 stat 內容不合也回 None（不知道），不據此認定死亡（spec §2.5、§5.4）。"""
    try:
        inject("proc-stat", "/proc/%d/stat" % pid)
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

    **先比世代、確定是現役才寫** `.aos/action.owner.json`＝`{"pid","gen","starttime"}`（舊世代的動作什麼都不寫）：新 daemon 的動作
    等鎖逾時時，靠它認出「舊世代、還是同一個程序」的持有者並 SIGKILL（astra-5 F-04；不 unlink 鎖檔）。
    gen.json 讀不到、壞掉、不是 `{"gen": 整數}`＝不知道世代 → 丟 Unknown（退出碼 3、daemon 退避），不當成現役放行。
    node 是動作拿著的路徑（tick／tock 給的是 `/proc/self/fd/N`，node 被刪時開不了鎖檔 → FileNotFoundError，由呼叫的人當 gone）。

    root 是 daemon 根，node 是已抓住的 node 路徑；回值是 context manager，區塊取得布林寫入許可（spec §2.5）。"""
    import fcntl
    with open(os.path.join(node, ".aos", "action.lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        mine = os.environ.get("AOS7_GEN")
        if mine is not None:
            # spec §2.5：拿鎖後才比 gen，讓排在新 daemon 後面的舊動作看到世代已換。
            st, cur = read_json3(os.path.join(root, ".aosd", "gen.json"))
            if st != OK or not isinstance(cur, dict) or not is_int(cur.get("gen")):
                raise Unknown("gen.json 不能用（%s），分不出自己是不是舊世代的動作，什麼都沒寫" % (cur if st == IO else st))
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
    """新 daemon（世代 gen）的動作等 action.lock 逾時後呼叫：持有者是舊世代、而且 pid 的啟動時間跟它記的一樣
    （確定是同一個程序）就 SIGKILL 它，鎖跟著放掉，下一圈重試（astra-5 F-04）。回被殺的 pid 或 None。

    node 指向持鎖者紀錄所在 node；gen 是接管者世代。讀不到紀錄、不能核對身分或送訊號失敗
    都回 None；三態的「不知道」保留程序，交上層記 last_error（spec §0、§2.5）。"""
    import signal
    ow = read_json(os.path.join(node, ".aos", OWNER))
    if not isinstance(ow, dict):
        return None
    pid, og, st = ow.get("pid"), ow.get("gen"), ow.get("starttime")
    # spec §0、§2.5：pid 可能重用；舊 gen 加上同 starttime 都確認，才有權收持鎖者。
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
    {"pid", "why", "hint"}；鎖沒人拿（例如逾時的是自己的動作、已被收掉）回 None。不殺任何程序（astra-6 G-10）。

    node 是鎖所在 node，gen 是目前世代；開不了鎖檔也回 None，不能據此證明無持鎖者。
    這是人工恢復診斷，並不授權 kill（spec §2.5）。"""
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
    """`/proc/self/fd/N/...`（tick／tock 抓著 node 的 fd 寫檔；astra-5 F-09）→ 現在的實際路徑；其他原樣。

    p 是字串路徑；回供顯示或環境使用的字串，readlink 失敗保留 p。
    轉出的路徑不取代實際寫入用的 fd，避免目錄換名後寫到另一個 inode（spec §2.5）。"""
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
    新的一行獨立成行，不會跟半行黏成一條壞行（astra-6 G-08）。回補換行前那段半行的位元組數（沒有是 0）。

    path 是流水帳檔，obj 是要追加的 JSON 值；寫失敗拋例外。用於可選歷史／事件紀錄，
    不負責輪替或清理（spec §9）。"""
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
    空行不算壞行。

    path 是流水帳檔；with_bad 決定回清單或二元組。讀不到時回已讀到的結果（通常空清單），
    不把它當作核心狀態的三態證據（spec §9）。"""
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
    """node id → 絕對路徑（根是 "."）。

    root 是空間根、node_id 是相對 id；回路徑字串，不驗證邊界或存在性（spec §1、S-14）。"""
    root = os.path.abspath(root)
    return root if node_id in (".", "") else os.path.join(root, node_id)


def canonical_node(root, node_id):
    """node 的「實際身分」路徑＝realpath(root)／node_id：登記時 node 的 realpath 要等於它（路徑上不能有符號連結）。
    不等＝路徑上有符號連結，不登記（請登記實際位置）。"""
    r = os.path.realpath(root)
    return r if node_id in (".", "") else os.path.join(r, node_id)


def node_id_of(root, path):
    """絕對路徑 → node id。

    root 是空間根、path 是 node 路徑；回以 / 分隔的相對 id，不驗證是否越界（spec §1、S-14）。"""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return "." if rel == "." else rel.replace(os.sep, "/")


def join_id(base, rel):
    """node id 接相對路徑（kernel 算成員 id 用）。

    base 是基準 id、rel 是相對路徑；回正規化 id，不做 root 邊界驗證（spec §1）。"""
    if base in (".", ""):
        return os.path.normpath(rel).replace(os.sep, "/")
    return os.path.normpath(os.path.join(base, rel)).replace(os.sep, "/")




def aos_dir(node):
    """依 node 路徑回傳其 .aos/ 路徑字串；不存取磁碟（spec §3）。"""
    return os.path.join(node, ".aos")


def env_with_bin(env=None):
    """複製一份環境，PATH 前面加上 proto7-2 的 bin/。

    env 是來源映射（None 取目前環境）；回新 dict，不修改原本環境（spec §5.5）。"""
    env = dict(os.environ if env is None else env)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    return env


def is_int(v):
    """真的整數（bool 不算）。

    v 是待驗值；回 bool，排除 JSON 的 true／false 冒充回合或 run 整數（spec §3、§5.2）。"""
    return isinstance(v, int) and not isinstance(v, bool)
