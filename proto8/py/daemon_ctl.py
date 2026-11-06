"""daemon_ctl：daemon 的找址、名單、寄信回信與子 loop 控制共用介面。"""
import datetime
import fcntl
import json
import os
import shutil
import time
from contextlib import contextmanager

import aos_flags
import aos_ws

PROG = "aos-daemon-ctl"
USAGE = ("aos-daemon-ctl [--daemon D] add [--reply-to BOX] [--name N] [--ws WS] [--stack S] [--def DEF] [--limits JSON] XXX [-- ARGS...]"
         " | rm|stop|start|sleep|wake [--reply-to BOX] NAME | pause NAME | resume NAME | ls [--json] | where --stack NAME | ping [--timeout-s S]")
STATE = "procs_state.json"
PATHS = ("stack", "ws", "exec", "def")
NAMES = {"procs_loop": "loop.json", "procs_ctl_mailbox": "procs_ctl_mailbox", "procs_stderr": "stderr.txt"}

class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code



def find_daemon(flag=None):
    """--daemon ＞ $AOS_DAEMON ＞ cwd 的 ./.stack（11-05 題 3）；轉絕對。"""
    d = flag or os.environ.get("AOS_DAEMON", "")
    if not d and os.path.isdir(".stack"):
        d = ".stack"
    if not d:
        raise Fail("DaemonMissing", "no --daemon, AOS_DAEMON not set, and no .stack folder in the cwd (point it at the daemon's $AOS_STACK folder)")
    if not os.path.isdir(d):
        raise Fail("DaemonMissing", "daemon folder not found: %s" % d)
    return os.path.realpath(d)   # 11-05 B 線：daemon 的表相對它 stack 的真實路徑（解開捷徑）算，這裡也解開才拼得回


def abs_target(t, base):
    """相對的目標接在 base 後面（`檔#/指標` 只動 # 前面；絕對的、只有 #/… 的不動）。"""
    f, h, p = t.partition("#")
    if f and not f.startswith("/"):
        f = os.path.abspath(os.path.join(base, f))
    return f + h + p


def read_loop(path):
    """讀一份 loop.json（第一行 #! 跳過）→ 物件；讀不了、不是 JSON＝LoopBad。"""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if text.startswith("#!"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
        cfg = json.loads(text)
    except (OSError, ValueError) as e:
        raise Fail("LoopBad", "%s is unreadable or not JSON: %s" % (path, e))
    if not isinstance(cfg, dict):
        raise Fail("LoopBad", "%s must be a JSON object" % path)
    return cfg


def read_entry_json(path):
    """入口找法用：讀一份沒 +x 的檔當 JSON（第一行 #! 跳過）。讀不了、不是 JSON＝EntryBad（aos-exec 也會這樣報）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        raise Fail("EntryBad", "cannot read %s: %s" % (path, e))
    if text.startswith("#!"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    try:
        return json.loads(text)
    except ValueError as e:
        raise Fail("EntryBad", "%s is not JSON: %s" % (path, e))


def pointer(v, ptr, where):
    """JSON pointer（RFC 6901，N-62）：ptr＝"" 或 "/a/b"。指不到＝EntryBad（判型用，不細分 EntryMissing）。"""
    if ptr == "":
        return v
    if not ptr.startswith("/"):
        raise Fail("EntryBad", "%s: # must be followed by /" % where)
    for tok in ptr[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(v, dict) and tok in v:
            v = v[tok]
        elif isinstance(v, list) and tok.isdigit() and int(tok) < len(v):
            v = v[int(tok)]
        else:
            raise Fail("EntryBad", "%s points nowhere" % where)
    return v


def find_loop(xxx):
    """add 的自動識別（11-04，four-elements 08 步 7；使用者「拿掉，不應該看特定檔案。add這塊，就是看最終指向的json的內部結構。」）：
    照 aos-exec 的找法（N-61／N-62 的子集）走到入口，看最後指到的 JSON 長怎樣。回 (loop 設定物件, 它所在的檔, 它在檔裡的指標, 相對路徑的起點)，
    exec 型回 None。不看檔名（loop.json 這個名字不出現在這裡）；.env 不讀（只判型、不是真的跑），$ref／$env 不解。
      資料夾＝XXX/$AOS_ENTRY（預設 _entry；沒有再找 .json）；可執行檔（+x）＝exec 型；
      JSON：陣列且 [0] 是 aos-loop＝[1] 是 loop 設定檔（從這份檔的資料夾算）、讀它；其他陣列＝exec 型；字串＝轉向（從這份檔的資料夾算）再來一遍；
      物件有 argv＝單子＝exec 型；物件沒 argv、有 exec＝它就是 loop 設定；沒 argv 沒 exec＝取 js[$AOS_ENTRY] 再來（同一份檔、指標往下）。
    繞圈＝EntryBad；路徑不在＝PathMissing。"""
    ent = os.environ.get("AOS_ENTRY") or "_entry"
    seen = set()
    path, _, ptr = abs_target(xxx, os.getcwd()).partition("#")
    while True:
        key = (os.path.realpath(path), ptr)
        if key in seen:
            raise Fail("EntryBad", "the entry of %s loops (%s#%s)" % (xxx, path, ptr))
        seen.add(key)
        if os.path.isdir(path):
            if ptr:
                raise Fail("EntryBad", "%s is a folder and cannot take #/" % path)
            nxt = os.path.join(path, ent)
            if not os.path.exists(nxt) and os.path.isfile(nxt + ".json"):
                nxt += ".json"
            if not os.path.exists(nxt):
                return None   # 找不到入口：當 exec 型交給 daemon（aos-exec 會報 EntryMissing，寫在小格的 stderr）
            path = nxt
            continue
        if not os.path.isfile(path):
            raise Fail("PathMissing", "%s not found" % path)
        if not ptr and os.access(path, os.X_OK):
            return None   # 可執行檔
        base = os.path.dirname(path)
        v = pointer(read_entry_json(path), ptr, "%s#%s" % (path, ptr))
        while isinstance(v, dict) and "argv" not in v and "exec" not in v:   # 沒 argv 的物件＝當資料夾，取 js[$AOS_ENTRY] 一路往下
            if ent not in v:
                return None
            v = v[ent]
            ptr += "/" + ent.replace("~", "~0").replace("/", "~1")
        if isinstance(v, dict):
            if "argv" in v:
                return None   # 單子
            return v, path, ptr, base   # 有 exec：loop 設定
        if isinstance(v, list):
            if len(v) >= 2 and v[0] == "aos-loop" and isinstance(v[1], str) and not v[1].startswith("-"):
                lp, _, lptr = abs_target(v[1], base).partition("#")   # loop 設定檔（可以帶 #/指標）
                try:
                    cfg = pointer(read_entry_json(lp), lptr, "%s#%s" % (lp, lptr))
                except Fail as e:
                    raise Fail("LoopBad", str(e))
                if not isinstance(cfg, dict):
                    raise Fail("LoopBad", "%s#%s must be a JSON object" % (lp, lptr))
                return cfg, lp, lptr, os.path.dirname(lp)
            return None   # 別的 argv 陣列
        if isinstance(v, str):
            path, _, ptr = abs_target(v, base).partition("#")   # 轉向
            continue
        raise Fail("EntryBad", "%s#%s is not an entry (must be a single, an argv array, a string or an object)" % (path, ptr))


def loop_spec(found):
    """loop 型的子項設定：那份 loop 設定（去掉 _entry），相對的 exec 目標照它的資料夾轉絕對；exec 是內嵌單子＝換成指回原處的字串目標。"""
    cfg, path, ptr, base = found
    cfg = dict(cfg)
    cfg.pop("_entry", None)
    ex = cfg.get("exec")
    if isinstance(ex, str):
        cfg["exec"] = abs_target(ex, base)
    elif isinstance(ex, list) and ex and isinstance(ex[0], str):
        cfg["exec"] = [abs_target(ex[0], base)] + ex[1:]
    elif isinstance(ex, dict) and "$ref" not in ex and "$env" not in ex:   # 內嵌單子：指回原檔，AOS_CD 與相對路徑照原地
        cfg["exec"] = path + "#" + ptr + "/exec"
    # 11-04（four-elements 08 步 6「不補名」）：ctl／state 不補（aos-loop 自己沒寫＝ctl.json／state.json）。只有 exec 的 loop 設定
    # 交給 daemon 會被認成 exec 型（題 3：物件只有 exec＝跑一次），所以補一格 "interval_ms": 0——aos-loop 的預設本來就是 0，行為不變
    if set(cfg) <= {"exec", "ws", "stack", "def", "limits"}:   # 同 daemon 的 is_once 認的那幾個 key
        cfg["interval_ms"] = 0
    return cfg



def names_of(d):
    """讀取 daemon 回報的檔名；壞值用預設，信箱 null 保留。"""
    try:
        with open(os.path.join(d, STATE), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    out = dict(NAMES)
    if isinstance(st, dict):
        for key in NAMES:
            value = st.get(key)
            if isinstance(value, str) and value:
                out[key] = value
            elif key == "procs_ctl_mailbox" and key in st and value is None:
                out[key] = None
    return out



def table(d, v):
    """procs_state 的表：物件原樣；切檔（{"$ref": [分檔, …]}）照順序讀回來合起來。"""
    if isinstance(v, dict) and isinstance(v.get("$ref"), list):
        out = {}
        for ref in v["$ref"]:
            with open(os.path.join(d, ref), encoding="utf-8") as fh:
                out.update(json.load(fh))
        return out
    if not isinstance(v, dict):
        raise ValueError("the table is not an object")
    return v


def resolve(d, row):
    """表上一列的 stack／ws／exec／def 拼回絕對（11-05：daemon 存相對 daemon stack）。exec 的 # 片段照留；
    值照字面（D 已 realpath）。不是字串的（null、內嵌單子）不動。回新的一列。"""
    out = dict(row)
    for k in PATHS:
        v = out.get(k)
        if isinstance(v, str) and v:
            f, h, p = v.partition("#")
            out[k] = (os.path.normpath(os.path.join(d, f)) if f else f) + h + p
    return out



def state(d):
    """讀名單窗與切檔；解析失敗時稍等一次，避免讀到寫入交界。"""
    path = os.path.join(d, STATE)
    if not os.path.isfile(path):
        raise Fail("StateMissing", "%s not found (daemon not started yet, or procs_state is off)" % path)
    for attempt in range(2):
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            procs = table(d, st.get("procs", {}))
            return {"daemon": st.get("daemon"), "responded_at": st.get("responded_at"),
                    "mailbox_warning": st.get("mailbox_warning"),
                    "procs": {n: resolve(d, r) if isinstance(r, dict) else r for n, r in procs.items()}}
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            if attempt:
                raise Fail("StateBad", "cannot parse %s: %s" % (path, exc))
            time.sleep(0.05)


def rows(d):
    return state(d)["procs"]



def row_of(d, name):
    """表上那一列；表上沒有＝ProcMissing（不看小格資料夾在不在）。"""
    r = rows(d).get(name)
    if not isinstance(r, dict):
        raise Fail("ProcMissing", "%s is not on the daemon table (only running, stopping, stopped, sleeping rows count; removed ones are gone, see aos-daemon-ctl ls)" % name)
    return r


def cell_of(d, name, row=None):
    """proc 的 stack：procs_state 那一列的 stack（11-03 procs § 2b；預設小格 <D>/procs/<名字> 也是 daemon 寫在列上的）。拿 stack 只在這裡。"""
    r = row_of(d, name) if row is None else row
    s = r.get("stack")
    if not isinstance(s, str) or not s:
        raise Fail("StateBad", "the row of %s has no stack" % name)
    return s.rstrip("/") or "/"



LIMIT_INTS = ("mem_mb", "cpu_s", "procs", "file_mb", "files")   # limits 的正整數 key（同 aos-sandbox、daemon 的 check_limits）；另有 user（字串）



def check_limits(v, where, code):
    """limits（11-05 feat-proto 件 5）：物件，key 只有 LIMIT_INTS（正整數）與 user（非空字串）。錯＝code（宣告 InterfaceBad、--limits ArgumentsBad）。"""
    keys = ", ".join(LIMIT_INTS + ("user",))
    if not isinstance(v, dict):
        raise Fail(code, "%s must be a JSON object such as {\"mem_mb\": 512, \"cpu_s\": 60} (keys: %s), not %s" % (where, keys, json.dumps(v, ensure_ascii=False)))
    for k, x in v.items():
        if k == "user":
            if not isinstance(x, str) or not x:
                raise Fail(code, "user in %s must be a non-empty string (account name), not %s" % (where, json.dumps(x, ensure_ascii=False)))
        elif k in LIMIT_INTS:
            if type(x) is not int or x <= 0:
                raise Fail(code, "%s in %s must be a positive integer, not %s" % (k, where, json.dumps(x, ensure_ascii=False)))
        else:
            raise Fail(code, "unknown key %s in %s (keys: %s)" % (k, where, keys))
    return v



def add_letter(xxx, extra=(), name=None, ws=None, stack=None, def_dir=None, limits=None):
    """判型並組成掛子信；給定的路徑從目前目錄算起。"""
    xxx = abs_target(xxx, os.getcwd())
    path = xxx.partition("#")[0]
    if not os.path.exists(path):
        raise Fail("PathMissing", "%s not found" % path)
    found = find_loop(xxx)
    if found and extra:
        raise Fail("ArgumentsBad", "loop type (the entry of %s leads to loop config %s) takes no arguments; put them in that config's exec" % (path, found[1]))
    if ws is not None:
        if not ws:
            raise Fail("ArgumentsBad", "--ws must not be empty (usage: %s)" % USAGE)
        ws = os.path.abspath(ws)   # 從呼叫當下的 cwd 算（daemon 會從它自己的 cwd 算，所以這裡先轉）
        if not os.path.isdir(ws):
            raise Fail("PathMissing", "--ws is not a folder: %s" % ws)
    if stack is not None:
        if not stack:
            raise Fail("ArgumentsBad", "--stack must not be empty (usage: %s)" % USAGE)
        stack = os.path.abspath(stack)   # 同 --ws 從呼叫當下的 cwd 算；在不在不驗（daemon 起它時建）
    name = name or os.path.basename(path.rstrip("/"))
    if found:
        spec = loop_spec(found)
    else:
        spec = {"exec": [xxx] + list(extra) if extra else xxx}
    spec["def"] = os.path.abspath(path)   # 11-04（使用者「那就b。」）：定義資料夾，daemon 記進表的 def 欄
    if def_dir is not None:          # 11-05：aos-agent 的定義宣告了 entry（XXX＝定義裡的那個入口）時，def 另給
        if not def_dir or not os.path.isdir(def_dir):
            raise Fail("PathMissing", "--def is not a folder: %s" % def_dir)
        spec["def"] = os.path.abspath(def_dir)
    if ws:
        spec["ws"] = ws
    if stack:
        spec["stack"] = stack
    if limits is not None:
        spec["limits"] = limits     # 11-05：原樣（{}＝不限、蓋過 daemon 的預設）
    if limits is not None:
        check_limits(limits, "limits", "ArgumentsBad")
    return name, {"procs_added": {name: spec}}



def need_ctl(d, name, row=None):
    """它的 stack 裡 daemon 寫的 loop.json（名字照窗上的 procs_loop）→ (stack, ctl 檔的路徑)；沒有那份（exec 型）或 ctl 是 null＝CtlMissing。
    ctl 沒寫＝ctl.json（aos-loop 的預設名，11-04 起 daemon 不再替它補）。"""
    stack = cell_of(d, name, row)
    lj = os.path.join(stack, names_of(d)["procs_loop"])
    if not os.path.isfile(lj):
        raise Fail("CtlMissing", "%s has no ctl (an exec type can only run and be removed)" % name)
    c = read_loop(lj).get("ctl", "ctl.json")
    if not isinstance(c, str) or not c:
        raise Fail("CtlMissing", "%s has no ctl (ctl in its loop.json is %s)" % (name, json.dumps(c)))
    return stack, os.path.join(stack, c)


# 11-05 portable-flow 衝突 1「嚴格分」：每個動詞只收一種 phase；用錯的提示（照表上的 phase 給下一步）
PHASE_OK = {"stop": "running", "sleep": "running", "start": "stopped", "wake": "sleeping"}
PHASE_HINT = {
    ("stop", "sleeping"): "%s is sleeping (no need to stop it); wake it first, then stop, or just rm",
    ("stop", "stopped"): "%s is already stopped",
    ("stop", "stopping"): "%s is stopping; wait until it has stopped; if it never stops (stuck, or SIGSTOP), rm it (TERM, then KILL after 10s)",
    ("sleep", "sleeping"): "%s is already sleeping",
    ("sleep", "stopped"): "%s is stopped (no need to sleep it); start brings it back",
    ("sleep", "stopping"): "%s is stopping; wait until it has stopped; if it never stops (stuck, or SIGSTOP), rm it (TERM, then KILL after 10s)",
    ("start", "sleeping"): "%s is sleeping; use wake (start only starts stopped ones)",
    ("start", "running"): "%s is already running",
    ("start", "stopping"): "%s is stopping; start it after it has stopped; if it never stops (stuck, or SIGSTOP), rm it (TERM, then KILL after 10s)",
    ("wake", "stopped"): "%s is stopped; use start (wake only wakes sleeping ones)",
    ("wake", "running"): "%s is awake (running); no need to wake it",
    ("wake", "stopping"): "%s is stopping, not sleeping",
}


def need_phase(cmd, name, row):
    ph = row.get("phase")
    if ph != PHASE_OK[cmd]:
        msg = PHASE_HINT.get((cmd, ph), "%%s is %s; %s only takes %s ones" % (ph, cmd, PHASE_OK[cmd]))
        raise Fail("PhaseBad", msg % name)



def write_ctl(d, name, cmd):
    row = row_of(d, name)
    stack, path = need_ctl(d, name, row)
    # 11-05 第二輪：只收 running 的（stopped／sleeping 的列沒有行程；起來時子 loop 把讀到的第一份 ctl 當基準線、不執行＝這道 pause 默默丟了，
    # 原本照寫、印 seq、退 0，看起來像成功）
    if row.get("phase") != "running":
        raise Fail("PhaseBad", "%s is %s; %s only takes running ones (a loop takes the ctl it finds when it starts as its baseline, so it would be lost)"
                   % (name, row.get("phase"), cmd))
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
        seq = old.get("seq") if isinstance(old, dict) else None
    except (OSError, ValueError):
        seq = None
    seq = seq + 1 if isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0 else 1
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"cmd": cmd, "seq": seq}) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (path, e))
    wait_applied(d, name, stack, cmd, seq)
    return seq



APPLY_S = 5.0   # pause／resume 等子 loop 套用的上限（暫停中的 loop 每秒讀一次 ctl、閒著的每圈讀）


def wait_applied(d, name, stack, cmd, seq):
    """等子 loop 的 state 窗 ctl_seq 追上 seq（11-05 晚 listen paused bug）；state 窗是 null＝不等；等不到＝提醒行。"""
    try:
        sname = read_loop(os.path.join(stack, names_of(d)["procs_loop"])).get("state", "state.json")
    except Fail:
        return
    if not isinstance(sname, str) or not sname:
        return
    spath, end = os.path.join(stack, sname), time.monotonic() + APPLY_S
    while True:
        try:
            with open(spath, encoding="utf-8") as fh:
                got = json.load(fh).get("ctl_seq")
        except (OSError, ValueError, AttributeError):
            got = None
        if got == seq:
            return
        if time.monotonic() >= end:
            aos_flags.warn(PROG, "%s has not applied %s (seq %d) within %g s (it reads its ctl between steps; a long step delays it); "
                           "a stop or sleep sent before it applies overwrites or drops it" % (name, cmd, seq, APPLY_S))
            return
        time.sleep(0.05)



def _post(args, text="", code="PostFailed"):
    """共用 aos-post 執行入口；下層錯誤直接透出。"""
    try:
        rc, out = aos_ws.run_post(args, text)
    except aos_ws.Error as exc:
        raise Fail(exc.code, str(exc))
    if rc:
        raise Fail(code, "aos-post %s exited %d" % (args[0], rc))
    return out.rstrip("\n")


def mailbox_of(d, direct=False):
    """掛子信與 ping 走同一個收件位置。"""
    kernel = os.environ.get("AOS_KERNEL", "")
    if kernel and not direct:
        box = os.path.abspath(kernel)
        if not os.path.isdir(os.path.join(box, "new")):
            raise Fail("MailboxMissing", "%s (AOS_KERNEL) is not a mailbox (judge not started yet?)" % box)
        return box
    mb = names_of(d)["procs_ctl_mailbox"]
    if not mb:
        raise Fail("MailboxMissing", "the daemon of %s has no mailbox (procs_ctl_mailbox in procs_state.json is null; do not set procs_ctl_mailbox to null in daemon.json)" % d)
    box = os.path.join(d, mb)
    if not os.path.isdir(os.path.join(box, "new")):
        raise Fail("MailboxMissing", "%s is not a mailbox (daemon not started yet, or its mailbox is off)" % box)
    return box


def send(d, body, reply_to=None, direct=False):
    """寄信只回信名，不替呼叫者列印。"""
    if not shutil.which("aos-post"):
        raise Fail("CommandMissing", "no aos-post on PATH")
    args = ["send"] + (["--reply-to", reply_to] if reply_to else []) + [mailbox_of(d, direct)]
    return _post(args, json.dumps(body, ensure_ascii=False), "SendFailed")


def _letter(path):
    try:
        with open(os.path.join(path, "letter.json"), encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _letters(box, stage):
    try:
        return sorted(n for n in os.listdir(os.path.join(box, stage)) if not n.startswith("."))
    except OSError:
        return []


def _claim(box, name):
    try:
        os.rename(os.path.join(box, "new", name), os.path.join(box, "cur", name))
        return True
    except FileNotFoundError:
        return False


@contextmanager
def _reply_lock(box):
    """共用信箱的收信與垃圾回收互斥，避免同封 cur 信重複 done。"""
    try:
        with open(os.path.join(box, ".reply.lock"), "a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    except OSError as exc:
        raise Fail("PostFailed", "cannot access reply mailbox %s: %s" % (box, exc))


def reply_box(d):
    """共用回信信箱；只按信件時間清理超過十分鐘的回信。"""
    stack = os.environ.get("AOS_STACK", "")
    if stack:
        box = os.path.abspath(os.path.join(stack, "daemon_reply"))
    else:
        box = os.path.abspath(os.path.join(mailbox_of(d, direct=True), "reply"))
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        _post(["init", box])
    with _reply_lock(box):
        cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - 600
        for stage in ("new", "cur"):
            for name in _letters(box, stage):
                letter = _letter(os.path.join(box, stage, name))
                try:
                    stamp = datetime.datetime.fromisoformat(letter["sent_at"].replace("Z", "+00:00"))
                    if stamp.tzinfo is None or stamp.timestamp() >= cutoff:
                        continue
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                if stage == "new" and not _claim(box, name):
                    continue
                _post(["done", box, name])
    return box


def take_reply(box, letter):
    """只認領自己的回信，其他呼叫者的回信留在原處。"""
    with _reply_lock(box):
        for name in _letters(box, "new"):
            envelope = _letter(os.path.join(box, "new", name))
            if envelope.get("in_reply_to") != letter or not _claim(box, name):
                continue
            body = _letter(os.path.join(box, "cur", name)).get("body")
            _post(["done", box, name])
            return body if isinstance(body, dict) else {}
    return None


def ask(d, body, timeout_s=3, direct=False):
    box = reply_box(d)
    letter = send(d, body, reply_to=box, direct=direct)
    end = time.monotonic() + timeout_s
    while True:
        got = take_reply(box, letter)
        if got is not None:
            return got
        if time.monotonic() >= end:
            return None
        time.sleep(min(0.05, max(0, end - time.monotonic())))


def ping(d, timeout_s=3, direct=False):
    return ask(d, {"ping": True}, timeout_s, direct)


def wait_taken(box, letter, secs=3):
    end = time.monotonic() + secs
    while os.path.lexists(os.path.join(box, "new", letter)):
        if time.monotonic() >= end:
            return False
        time.sleep(min(0.05, max(0, end - time.monotonic())))
    return True


def supervisor(d, st):
    """只讀上一層對這台 daemon 的看法，不自行判活。"""
    up = st.get("daemon")
    if up is None:
        return None, None, None
    if not isinstance(up, str) or not os.path.isabs(up):
        return up, None, "relative path as the daemon inherited it; cannot tell where it is"
    try:
        procs = rows(up)
    except Fail as exc:
        if exc.code not in ("StateMissing", "StateBad"):
            raise
        return up, None, "no readable procs_state.json there"
    for row in procs.values():
        stack = row.get("stack") if isinstance(row, dict) else None
        if isinstance(stack, str) and os.path.realpath(stack) == os.path.realpath(d):
            return up, row.get("phase"), row.get("reason")
    return up, None, "this daemon is not on its table"
