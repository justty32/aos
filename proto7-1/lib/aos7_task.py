"""任務資料夾的共用邏輯：列任務、判斷狀態、kill、執行 ctl.json、寫 spawn、起任務（spec.md 第 4～6 節）。

tick、tock、daemon 共用；kernel 也可以 import `list_tasks`／`task_state`／`is_live` 來看任務。
所有函式只讀寫檔案與送訊號，不留任何記憶體狀態。
"""
import json
import os
import re
import signal
import subprocess
import sys
import time

import aos7_mount
from aos7_fs import BIN, FD_PREFIX, env_with_bin, node_path, now, read_json, real_path, tail_jsonl, write_json


KILL_GRACE = 1.0   # spec 第 6 節：SIGTERM 後等至多 1 秒，還在就 SIGKILL
LIVE_STATES = ("born", "live")


# ---------- 路徑 ----------

def tasks_dir(node):
    """`<node>/.aos/tasks/`。"""
    return os.path.join(node, ".aos", "tasks")


def task_dir(node, tid):
    return os.path.join(tasks_dir(node), tid)


def old_dir(node):
    """`<node>/.aos/tasks-old/`：tock 把結束超過 keep_ended_rounds 回合的任務資料夾搬來這裡（Q3）。"""
    return os.path.join(node, ".aos", "tasks-old")


def find_task_dir(node, tid):
    """tid 的資料夾：先找 tasks/，再找 tasks-old/；都沒有回 None。"""
    for d in (task_dir(node, tid), os.path.join(old_dir(node), tid)):
        if os.path.isdir(d):
            return d
    return None


def last_logged_round(node):
    """rounds.jsonl 最後幾行裡最大的整數 round（round.json 壞掉時接著數用；probes/chaos B6）；沒有回 None。"""
    rows = tail_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), 20)
    rs = [x.get("round") for x in rows if isinstance(x, dict)]
    rs = [r for r in rs if isinstance(r, int) and not isinstance(r, bool)]
    return max(rs) if rs else None


def list_tasks(node):
    """回這個 node 所有任務的 tid（排序過）。node 是絕對路徑。"""
    try:
        return sorted(d for d in os.listdir(tasks_dir(node))
                      if os.path.isfile(os.path.join(tasks_dir(node), d, "birth.json")))
    except OSError:
        return []


def birth_of(tdir):
    """讀 birth.json；壞掉或不是物件回 {}（任務自己改壞也不拖垮 tick／tock；astra-4 I-05）。"""
    b = read_json(os.path.join(tdir, "birth.json"))
    return b if isinstance(b, dict) else {}


def name_of(tdir):
    """任務的 name：birth.json 的，讀不到就從 tid 推（`<name>-r<回合>[-k]`），免得 keep 以為沒有活實例又起一份。"""
    n = birth_of(tdir).get("name")
    if isinstance(n, str) and n:
        return n
    return re.sub(r"-r\d+(-\d+)?$", "", os.path.basename(tdir))


# ---------- 程序 ----------

def pid_alive(pid):
    """程序在不在（殭屍算不在）。"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def group_alive(pgid):
    """程序群組還有沒有成員（殭屍不算）。"""
    if not isinstance(pgid, int) or pgid <= 0:
        return False
    for pid in _all_pids():
        st = _stat(pid)
        if st and st[2] == pgid and st[0] != "Z":
            return True
    return False


def _all_pids():
    return [int(p) for p in os.listdir("/proc") if p.isdigit()]


def _stat(pid):
    """回 (state, ppid, pgid) 或 None。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            rest = f.read().rsplit(")", 1)[1].split()
        return rest[0], int(rest[1]), int(rest[2])
    except (OSError, IndexError, ValueError):
        return None


def _groups_with_descendants(pgid):
    """pgid 本身，加上這群組成員所有後代所在的群組。

    為什麼要後代：搬來的 aos-exec 會把 inst 的子程式開在**另一個 session**，
    只殺 aos-exec 的群組收不到它（problems-core.md P-05）。"""
    table = {p: _stat(p) for p in _all_pids()}
    table = {p: s for p, s in table.items() if s}
    members = {p for p, s in table.items() if s[2] == pgid}
    seen, todo = set(members), list(members)
    while todo:
        parent = todo.pop()
        for p, s in table.items():
            if s[1] == parent and p not in seen:
                seen.add(p)
                todo.append(p)
    return {pgid} | {table[p][2] for p in seen if p in table}


def _is_runner(pid):
    """是 aos7-run（任務的包裝）嗎：它等任務死了自己寫 exit.json，不能先殺它。"""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return any(a.endswith(b"aos7-run") for a in f.read().split(b"\0"))
    except OSError:
        return False


def _env_has(pid, want):
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            return want <= set(f.read().split(b"\0"))
    except OSError:
        return False


def group_is_task(pgid, tid, node):
    """pid.json 的 pgid 真的是這個任務的嗎：群組沒有活成員（沒東西可打），或有成員（或成員的父程序＝aos7-run）
    的環境變數 AOS7_TID＋AOS7_NODE 是這個任務。pid.json 在任務自己寫得到的 taskdir，改了 pgid 的不能讓 kill 打到別人（probes/chaos B7）。"""
    if not isinstance(pgid, int) or pgid <= 1:
        return False
    want = {b"AOS7_NODE=" + node.encode(), b"AOS7_TID=" + tid.encode()}
    members = [(p, st) for p, st in ((p, _stat(p)) for p in _all_pids()) if st and st[2] == pgid and st[0] != "Z"]
    if not members:
        return True
    return any(_env_has(p, want) or _env_has(st[1], want) for p, st in members)


def _escaped(tid, node, skip):
    """環境變數 AOS7_TID、AOS7_NODE 都是這個任務、但已經不是後代的程序（雙 fork、setsid 後被 init 收養；probes/polyglot N5）。
    tid 給 None＝這個 node 的任何任務（有 AOS7_TID 就算；node 消失時用，Q4）。"""
    return _env_procs({node}, tid, skip)


def _env_procs(nodes, tid, skip):
    """一次掃 `/proc/*/environ`：AOS7_NODE 在 nodes 裡（tid 給了還要 AOS7_TID 相符；沒給要有 AOS7_TID）的程序，不含 aos7-run。"""
    want_nodes = {b"AOS7_NODE=" + n.encode() for n in nodes}
    want_tid = None if tid is None else b"AOS7_TID=" + tid.encode()
    out = []
    for pid in _all_pids():
        if pid in skip:
            continue
        try:
            with open("/proc/%d/environ" % pid, "rb") as f:
                env = set(f.read().split(b"\0"))
        except OSError:
            continue
        if not (env & want_nodes):
            continue
        if (want_tid in env) if want_tid is not None else any(x.startswith(b"AOS7_TID=") for x in env):
            if not _is_runner(pid):
                out.append(pid)
    return out


def _me_and_ancestors():
    me = {os.getpid()}
    p = os.getppid()
    while p > 1 and p not in me:      # 不殺自己與祖先（子 daemon 本身也是某個 node 的任務）
        me.add(p)
        st = _stat(p)
        p = st[1] if st else 1
    return me


def sweep_nodes(nodes):
    """daemon stop（帶 kill）的最後收尾（astra-5 F-01）：環境變數 AOS7_NODE 是 nodes 之一、有 AOS7_TID 的程序
    （已結束任務留下的子孫、tasks-old 裡的也算；Q1 範圍：群組＋活後代＋環境相符），連同它們的群組與後代收掉。
    一次掃 /proc，不逐任務掃。aos7-run 不殺（它等任務死了自己寫 exit.json）。回 (收到的群組數, 乾不乾淨)。"""
    me = _me_and_ancestors()
    groups = set()
    for pid in _env_procs(set(nodes), None, me):
        st = _stat(pid)
        if st and st[2] not in me and st[2] > 1:
            groups.add(st[2])
    clean = True
    for g in sorted(groups):
        clean = kill_group(g) and clean
    return len(groups), clean


def kill_group(pgid, grace=KILL_GRACE, also=()):
    """對 pgid（連同後代的群組）與 also（另外找到的程序所在的群組）送 SIGTERM，等至多 grace 秒，還在就 SIGKILL。回 True＝收乾淨。"""
    groups = _groups_with_descendants(pgid)
    for pid in also:
        st = _stat(pid)
        if st:
            groups |= _groups_with_descendants(st[2])
    for g in groups:
        try:
            os.killpg(g, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if not any(group_alive(g) for g in groups):
            return True
        time.sleep(0.02)
    for g in groups:
        try:
            os.killpg(g, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.05)
    return not any(group_alive(g) for g in groups)


# ---------- 狀態 ----------

def task_state(tdir):
    """回任務狀態字串（spec 第 5 節）：

    - "ended"：有 exit.json
    - "live"：有 pid.json，任務程序或 aos7-run 還在
    - "lost"：有 pid.json，任務與 aos7-run 都不在，又沒 exit.json
    - "born"：只有 birth.json（剛起，算活）
    """
    if os.path.exists(os.path.join(tdir, "exit.json")):
        return "ended"
    pid = read_json(os.path.join(tdir, "pid.json"))
    if not isinstance(pid, dict) or not pid:
        return "born"
    if pid_alive(pid.get("pid")) or pid_alive(pid.get("runner_pid")):
        return "live"
    # aos7-run 可能剛好在這一瞬間寫完 exit.json（P-07），再看一次
    if os.path.exists(os.path.join(tdir, "exit.json")):
        return "ended"
    return "lost"


def is_live(state):
    return state in LIVE_STATES


def live_tasks(node):
    """回 node 上活著（born 或 live）的 tid 清單。"""
    return [t for t in list_tasks(node) if is_live(task_state(task_dir(node, t)))]


# ---------- 控制 ----------

def kill_task(tdir):
    """kill 一個任務，回 (ok, msg)。已結束當成功。"""
    if os.path.exists(os.path.join(tdir, "exit.json")):
        # 主程序結束了，但它開的子孫可能還在（astra-4 I-04）：照樣找環境變數是這個任務的程序收掉
        tid = os.path.basename(tdir)
        node = real_path(os.path.dirname(os.path.dirname(os.path.dirname(tdir))))   # tick／tock 給的是 /proc/self/fd/N
        left = _escaped(tid, node, {os.getpid()})
        if not left:
            return True, "already ended"
        st = _stat(left[0])
        clean = kill_group(st[2] if st else left[0], also=left)
        return clean, "already ended; %d leftover process(es) %s" % (len(left), "killed" if clean else "still alive")
    end = time.monotonic() + KILL_GRACE
    pid = read_json(os.path.join(tdir, "pid.json"))
    while not isinstance(pid, dict) and time.monotonic() < end:   # 剛起、aos7-run 還沒寫 pid.json
        time.sleep(0.02)
        pid = read_json(os.path.join(tdir, "pid.json"))
    if not pid:
        return False, "no pid.json"
    node = real_path(os.path.dirname(os.path.dirname(os.path.dirname(tdir))))
    tid = os.path.basename(tdir)
    also = _escaped(tid, node, {os.getpid(), pid.get("runner_pid")})
    if not group_is_task(pid.get("pgid"), tid, node):
        # pid.json 被改過（或 pgid 壞掉）：不打那個群組，只收環境變數相符的
        if also:
            st = _stat(also[0])
            clean = kill_group(st[2] if st else also[0], also=also)
        else:
            clean = True
        return False, "pid.json 的 pgid %r 不是這個任務的群組，沒動它；環境變數相符的 %d 個程序%s" % (
            pid.get("pgid"), len(also), "收掉了" if clean else "沒收乾淨")
    clean = kill_group(pid.get("pgid"), also=also)
    return clean, "killed" if clean else "still alive after SIGKILL"


def kill_node_procs(node, known=(), skip=()):
    """node 消失時收掉它上面的任務（Q4）：known＝daemon 平常記著的 [(pgid, runner_pid)]（只用 pgid），
    再加上環境變數 AOS7_NODE 是這個 node 的程序（pid.json 跟著資料夾被刪了也找得到）。回收到的群組數與乾不乾淨。"""
    me = _me_and_ancestors()
    groups = set()
    for pgid, _runner in known:
        if isinstance(pgid, int) and pgid > 1 and pgid not in me:
            groups.add(pgid)
    left = _escaped(None, node, me)
    for pid in left:
        st = _stat(pid)
        if st and st[2] not in me:
            groups.add(st[2])
    clean = True
    for g in sorted(groups):
        clean = kill_group(g) and clean
    return len(groups), clean   # aos7-run 不殺：任務死了它自己經 fd 寫 exit.json（搬家時寫到新位置）


def write_spawn(node, fname, item):
    """寫 `<node>/.aos/spawn/<fname>.json`：請下個 tick 起一個任務。"""
    write_json(os.path.join(node, ".aos", "spawn", fname + ".json"), item)


RESTART_KEYS = ("name", "argv", "inst", "subroot", "allow_stop")   # restart 從 birth.json 抄的定義欄位
DIFF_KEYS = ("argv", "inst", "mounts", "subroot", "allow_stop")


def dyn_mounts(birth):
    """birth.json 裡執行中加掛的（標了 dyn）→ {名字: 空間路徑}。"""
    m = (birth or {}).get("mounts") or {}
    return {n: v["to"] for n, v in m.items() if isinstance(v, dict) and v.get("dyn") and "to" in v and "at" in v}


def reload_item(node, birth):
    """restart reload 的新定義：node 現在的 tasks.json 裡跟 birth.json 同名的項目（第一個），去掉 mode／from_round／max_live，
    掛載＝項目的宣告加上執行中加掛的（同名以項目為準）。回 (項目, None) 或 (None, 說明)；說明時整個 ctl 不執行。"""
    import aos7_tick   # tick import 這個模組，放在這裡免得互相 import
    name = birth.get("name") if isinstance(birth.get("name"), str) and birth.get("name") else "task"
    items, errs = aos7_tick.load_items(node)
    found = [i for i in items if aos7_tick.item_name(i) == name]
    if not found:
        why = "；".join(errs) if errs and not items else "tasks.json 沒有名為 %s 的項目" % name
        return None, "%s；沒執行（沒 kill）。不加 reload 會照出生時的定義重起" % why
    try:
        aos7_tick.check_item(found[0])   # 第 4 節完整檢查（含 mode／from_round／max_live）先過，才剝排程欄位（astra-6 G-05）
    except ValueError as e:
        return None, "tasks.json 的 %s 不合格：%s；沒執行（沒 kill）" % (name, e)
    item = {k: v for k, v in found[0].items() if k not in ("mode", "from_round", "max_live", "restart_of", "spawn",
                                                             "mounts_dyn")}
    item["name"] = name
    decl = item.get("mounts") or {}
    # 同名以宣告為準，來源也改成宣告：只有沒被宣告接管的才算執行中加掛（標 dyn；astra-6 G-06）
    dyn = {n: to for n, to in dyn_mounts(birth).items() if n not in decl}
    item["mounts"] = dict(dyn, **decl)
    if dyn:
        item["mounts_dyn"] = sorted(dyn)
    return item, None


def def_diff(birth, item):
    """舊（birth.json）→ 新（reload 的項目）定義有變的欄位：{欄: {"old", "new"}}。掛載比宣告（名字→空間路徑）。"""
    out = {}
    for k in DIFF_KEYS:
        old = aos7_mount.decl_of(birth) if k == "mounts" else birth.get(k)
        new = item.get(k)
        if k == "mounts":
            new = new or {}
        if old != new:
            out[k] = {"old": old, "new": new}
    return out


def run_ctl(node, tid):
    """執行 `<taskdir>/ctl.json`（若有），搬成 ctl-done.json。回紀錄 dict 或 None。"""
    tdir = task_dir(node, tid)
    path = os.path.join(tdir, "ctl.json")
    ctl = read_json(path)
    if ctl is None and not os.path.exists(path):
        return None
    bad = None
    if not isinstance(ctl, dict):         # 讀不懂或不是物件（例如 `[]`）：寫失敗回條、搬走，不拖垮 tick（同 daemon ctl）
        bad = "unreadable JSON" if ctl is None else "not a JSON object"
        ctl = {"raw": "unreadable" if ctl is None else ctl}
    op = ctl.get("op")
    diff = None
    if bad:
        ok, msg = False, bad
    elif op == "kill":
        ok, msg = kill_task(tdir)
    elif op == "restart":
        birth = birth_of(tdir)
        reload = ctl.get("reload", False)
        item, diff = None, None
        if not isinstance(reload, bool):
            ok, msg = False, "reload 要是 true 或 false，拿到 %r；沒執行（沒 kill）" % (reload,)
        elif reload:
            item, msg = reload_item(node, birth)   # 照現在 tasks.json 的同名項目（使用者 10-03 Q6）
            ok = item is not None
        else:
            item = {k: birth[k] for k in RESTART_KEYS if k in birth}
            item["mounts"] = aos7_mount.decl_of(birth)   # 新任務照原本的宣告重新掛
        if item is not None:
            dyn = dyn_mounts(birth)
            if dyn and not reload:
                item["mounts_dyn"] = sorted(dyn)   # 新任務照樣標 dyn（下次 reload 還分得出來）；reload 的由 reload_item 算
            if reload:
                diff = def_diff(birth, item)
            ok, msg = kill_task(tdir)
            item["restart_of"] = tid
            write_spawn(node, "restart-" + tid, item)
            msg += "; spawn written" + ("（reload：照 tasks.json 的 %s；%s）" % (
                item.get("name") or "task", "；".join("%s %s → %s" % (k, json.dumps(v["old"], ensure_ascii=False),
                                                              json.dumps(v["new"], ensure_ascii=False))
                                                     for k, v in diff.items()) or "定義沒變") if reload else "")
    else:
        ok, msg = False, "unknown op %r" % op
    ctl["result"] = {"ok": ok, "msg": msg, "at": now()}
    if diff is not None:
        ctl["result"]["diff"] = diff   # reload：舊 → 新定義有變的欄位，讀回條就知道生效的是哪版
    write_json(os.path.join(tdir, "ctl-done.json"), ctl)
    try:
        os.remove(path)
    except OSError:
        pass
    return {"tid": tid, "op": op, "ok": ok}


def run_all_ctl(node):
    """對 node 每個任務執行 ctl.json，回紀錄清單。一個任務的 ctl 處理失敗（ctl-done.json 變成資料夾、寫不進去…）
    只在它那筆記 `ok: false`＋`err`，其他任務照做，不拖垮 tick／tock（astra-5 F-06）。"""
    out = []
    for tid in list_tasks(node):
        try:
            r = run_ctl(node, tid)
        except Exception as e:   # noqa: BLE001
            r = {"tid": tid, "op": None, "ok": False, "err": repr(e)[:200]}
        if r:
            out.append(r)
    return out


# ---------- 起任務 ----------

def new_tid(node, name, rnd):
    """`<name>-r<回合>`，撞名加 -2、-3。"""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name or "task")
    base = "%s-r%d" % (safe, rnd)
    tid, n = base, 1
    while os.path.exists(task_dir(node, tid)) or os.path.exists(os.path.join(old_dir(node), tid)):
        n += 1
        tid = "%s-%d" % (base, n)
    return tid


def subroot_of(root, node_id, sub):
    """檢查任務的 `subroot`：回 (空間路徑, None) 或 (None, 錯誤)。要在任務自己的 node 底下、不能是 node 本身
    （S-10；probes/llmteam 誤解 2：寫成 "sub" 就在空間根建了 .aosd）。"""
    good, bad = aos7_mount.check({"subroot": sub})
    sp = node_path(root, good["subroot"]) if good else None
    if good and aos7_mount.in_root(root, good["subroot"]) and os.path.realpath(sp).startswith(
            os.path.realpath(node_path(root, node_id)) + os.sep):
        return good["subroot"], None
    return None, (bad or ["subroot %s 要在自己的 node（%s）底下" % (sub, node_id)])[0]


def stopped_note(root, sub):
    """子根有 `.aosd/stopped.json`（子 daemon 被路二 stop 過，Q5）就回說明字串，否則 None。"""
    path = os.path.join(node_path(root, sub), ".aosd", "stopped.json")
    if not os.path.lexists(path):
        return None
    st = read_json(path)
    st = st if isinstance(st, dict) else {}
    return "子 daemon（%s）已被 %s 在 %s stop%s；刪掉 %s/.aosd/stopped.json 就會再起" % (
        sub, st.get("by") or "?", st.get("at") or "?", "（%s）" % st["why"] if st.get("why") else "", sub)


def subroot_running(sp):
    """子根 `<sp>/.aosd/daemon.lock` 有人拿著嗎（有 daemon 在跑）：非阻塞 flock 試得到就馬上放掉、回 False（astra-6 G-04）。"""
    import fcntl
    try:
        fd = os.open(os.path.join(sp, ".aosd", "daemon.lock"), os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return False   # 沒有鎖檔：沒人跑過
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    finally:
        os.close(fd)   # 關掉就放掉
    return False


def same_dir(node, fnode):
    """tick 抓著的 node（fnode＝`/proc/self/fd/N`）跟字串路徑 node 現在指的還是同一個資料夾嗎（中途搬走、換成符號連結就不是；
    astra-6 G-02）。不是 fd 路徑當同一個。"""
    if not fnode.startswith(FD_PREFIX):
        return True
    try:
        return os.path.samestat(os.stat(node), os.stat(fnode))
    except OSError:
        return False


def start_task(root, node_id, item, rnd, fnode=None):
    """建掛載點、寫 birth.json，用 aos7-run 起任務（新 session，不等）。回 tid。

    帶 `subroot` 而子根有 stopped.json（路二 stop 過；Q5）時不起，丟 ValueError（tick 記進 tasks_error）。
    fnode＝寫檔用的 node 路徑（tick 給 node 目錄 fd 的 `/proc/self/fd/N`：node 中途被刪就寫不進去、不建鬼目錄；
    astra-5 F-09）；任務的環境、cwd、掛載點記錄用實際路徑。"""
    root = os.path.abspath(root)
    node = node_path(root, node_id)
    fnode = fnode or node
    sub = item.get("subroot")
    sub_ok, sub_err = subroot_of(root, node_id, sub) if isinstance(sub, str) else (None, None)
    if sub_ok:
        note = stopped_note(root, sub_ok)
        if note:
            raise ValueError(note)
    sp = None
    if sub_ok:
        sp = os.path.join(fnode, os.path.relpath(node_path(root, sub_ok), node))   # 子根在 node 底下：經 fnode 看
        if subroot_running(sp):
            # 子根已經有 daemon 在跑：這個任務起了也拿不到 daemon.lock，不能先把 owner.json 改成自己（astra-6 G-04）
            ow = read_json(os.path.join(sp, ".aosd", "owner.json"))
            ow = ow if isinstance(ow, dict) else {}
            raise ValueError("子根 %s 已經有 daemon 在跑（owner：node %s 任務 %s），沒起、沒改 owner.json" % (
                sub_ok, ow.get("node", "?"), ow.get("tid", "?")))
    tid = new_tid(fnode, item.get("name"), rnd)
    tdir = task_dir(node, tid)
    ftdir = task_dir(fnode, tid)
    os.makedirs(ftdir, exist_ok=True)   # 先佔住 tid，掛載點建在裡面
    if not same_dir(node, fnode):
        # tick 抓著 node 的期間它被搬走或換掉：不照舊路徑建掛載、不起 runner（會建回舊 node 或跑到別的 node），
        # 受控失敗：寫 birth＋exit.json（code 127），任務是 ended，不會永遠 born；新位置由 keep 重起（Q4；astra-6 G-02）
        why = "node %s 在 tick 中途被搬走或換掉（現在在 %s），沒起" % (node_id, real_path(fnode))
        write_json(os.path.join(ftdir, "birth.json"), {"tid": tid, "name": item.get("name") or "task", "node": node_id,
                                                       "round": rnd, "mounts": {}, "at": now(),
                                                       "restart_of": item.get("restart_of"), "error": why})
        write_json(os.path.join(ftdir, "exit.json"), {"code": 127, "at": now(), "round": rnd, "error": why})
        return tid
    birth = {"tid": tid, "name": item.get("name") or "task", "node": node_id, "round": rnd,
             "mounts": aos7_mount.make(root, tdir, item.get("mounts") or {}, fs_taskdir=ftdir, node=node, fnode=fnode),
             "at": now(), "restart_of": item.get("restart_of")}
    for n in item.get("mounts_dyn") or ():
        # restart 帶過來的執行中加掛：照樣標 dyn，之後 reload 才分得出哪些不是 tasks.json 宣告的（Q6）
        if isinstance(birth["mounts"].get(n), dict):
            birth["mounts"][n]["dyn"] = True
    if item.get("spawn"):
        birth["spawn"] = item["spawn"]   # 從哪個 spawn 檔起的（追得到請求的去向；astra-4 I-02）
    if "allow_stop" in item:
        birth["allow_stop"] = item["allow_stop"]
    if sub_ok:
        # 這個任務要在 sub 開子 daemon（路一）：先建 `<sub>/.aosd/`，父 daemon 掃描就跳過它，
        # 不會在子 daemon 起來前把裡面的 node 當自己的（P-11；probes/nest3 N3）
        os.makedirs(os.path.join(sp, ".aosd"), exist_ok=True)
        # 子 daemon 歸屬起它的 node（使用者 10-03 Q5）：路二的 stop 要 allow_stop 才有效；擁有者可直接改這個檔
        write_json(os.path.join(sp, ".aosd", "owner.json"),
                   {"node": node_id, "tid": tid, "allow_stop": item.get("allow_stop") is True, "at": now()})
        birth["subroot"] = sub_ok
    elif sub_err:
        birth["subroot_error"] = sub_err
    if "inst" in item:
        birth["inst"] = item["inst"]
    else:
        birth["argv"] = item.get("argv", [])
    write_json(os.path.join(ftdir, "birth.json"), birth)
    env = env_with_bin()
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": node_id,
                "AOS7_TASK": tdir, "AOS7_TID": tid})
    env.pop("AOS7_SUBROOT", None)   # 子 daemon 起的任務不要繼承父任務的
    if birth.get("subroot"):
        # 子根的絕對路徑：argv 寫 ["aos7-daemon", "$AOS7_SUBROOT"]，不必管 cwd 是 node（probes/llmteam 誤解 1）
        env["AOS7_SUBROOT"] = node_path(root, birth["subroot"])
    # 寫入紀錄（spec 第 5 節）：aos7-run 起任務時才把 audit_site/ 放進任務的 PYTHONPATH，
    # 不給 aos7-run 自己（它寫的 pid.json、exit.json 不算任務的寫入；probes/polyglot N7）
    # aos7-run 拿任務資料夾的 fd（第二個參數）讀 birth、寫 pid／exit，cwd 也是 tick 抓著的 node：之後 node 被搬走，
    # runner 跟著同一個資料夾，不會照舊路徑讀不到 birth 而留下「永遠剛起」的任務（astra-6 G-02）
    try:
        tfd = os.open(ftdir, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as e:
        write_json(os.path.join(ftdir, "exit.json"), {"code": 127, "at": now(), "round": rnd, "error": str(e)})
        return tid
    try:
        subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir, str(tfd)], cwd=fnode, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, pass_fds=(tfd,))
    except OSError as e:
        # 連 aos7-run 都起不來（node 中途被刪、cwd 不在…）：照樣寫 exit.json，不留「永遠剛起」的任務
        write_json(os.path.join(ftdir, "exit.json"), {"code": 127, "at": now(), "round": rnd, "error": str(e)})
    finally:
        os.close(tfd)
    return tid
