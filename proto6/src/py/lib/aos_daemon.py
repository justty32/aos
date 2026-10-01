"""最核心的 aos-daemon：一個叫 aos-exec 的 cron（plan m3-daemon-core.md）。

讀設定檔裡的 inst 清單，每一項一條執行緒，照自己的週期叫一次 `<bin>/aos-exec <inst 字面值>`，
等它結束、stdout 印一行。沒有 socket、沒有登記、沒有收屍。核心沒有 id 這個概念：一項就是
它在 `insts` 物件裡的鍵（inst 字面值）與鍵的位置（使用者 2026-10-01）。
整份設定檔先經 aos 指示詞展開再讀（`expand()`）；頂層 `modules` 核心認得、不解讀。
〔使用者方向 2026-10-01〕POC 默認一切正常：設定檔讀得懂、路徑都對、aos-exec 叫得起來；
不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。
設定檔寫了 `modules.control` 就掛上控制模組（plan m3n-control-module.md，`lib/aos_daemon_ctl.py`）：
多開一個 unix socket 收 wake／pause／resume／status，並把 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`
放進每次 aos-exec 的環境。沒寫時跟 m3 一模一樣（沒人叫醒迴圈、不傳 env=）。
寫了 `modules.reload` 就收 SIGHUP 重讀同一份設定檔（plan m3m 模組一，`lib/aos_daemon_reload.py`）；
寫了 `modules.state`（原始值必須是 `{"$ref": "<檔>"}`）就把暫停／已停記進那個檔、重開時讀回
（plan m3m 模組三，`lib/aos_daemon_state.py`）；寫了 `modules.cgroup` 就每項一個 cgroup 框、
`aos-exec` 結束後清掉框裡的殘留才算這次結束（plan m3m 模組二，`lib/aos_daemon_cgroup.py`）。
"""
import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import threading
import time

from aos_directives import Context, DirectiveError, is_option_object, load_document, resolve_located

EXEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "aos-exec")
INST_MARK = "<inst>"

# 控制模組的 socket 絕對路徑；沒掛＝None。退出前要刪（m3n 步驟 6）
_sock_path = None

# 記住狀態模組（aos_daemon_state.StateFile）；沒掛＝None
_state = None

# 收屍／cgroup 模組（aos_daemon_cgroup.Tree）；沒掛＝None
_cg = None

# 目前的清單 {inst 字面值: Item}。控制模組、記住狀態、重讀設定共用同一個 dict 物件；
# 重讀設定加減項時在 _items_lock 底下原地改（m3m 模組一）
_items = {}
_items_lock = threading.Lock()

# stdout 那一行與 aos-exec 的 stdout／stderr 都在這把鎖底下一次寫完，多項同時結束也不交錯（m3 步驟 2）
_out = threading.Lock()


def now():
    """印出那一刻的本地時間，ISO 8601 帶時區，到秒：2026-10-01T15:04:05+08:00。"""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def clock(mono):
    """把 time.monotonic() 的時刻換成跟 now() 同格式的本地時間（status 的 next 用）。"""
    t = time.time() + (mono - time.monotonic())
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def say(text):
    """stdout 一行，帶時間，寫完立刻 flush。"""
    with _out:
        sys.stdout.write("%s %s\n" % (now(), text))
        sys.stdout.flush()


class Item:
    """清單的一項：`inst` 字面值＝`insts` 物件的鍵（原樣交給 aos-exec、也原樣印出）；index＝鍵的位置（從 0 起）。"""

    def __init__(self, index, inst, interval_ms, stop_on_nonzero, err_path, out_path=None, cgroup=None):
        self.index = index
        self.inst = inst
        self.interval_ms = interval_ms
        self.stop_on_nonzero = stop_on_nonzero
        self.err_path = err_path        # aos-exec 的 stderr 寫到哪（絕對路徑）；None＝丟掉（使用者 2026-10-01）
        self.out_path = out_path        # aos-exec 的 stdout 寫到哪；None＝丟掉
        self.env = None                 # 開 aos-exec 的環境；None＝照 daemon 的（控制模組沒掛）
        self.cgroup = cgroup or {}      # 這一項的 cgroup 上限 {檔名: 值}（設定的 "cgroup" 鍵；模組沒掛時不看）
        self.frame = None               # 這一項的 cgroup 框（絕對路徑）；None＝cgroup 模組沒掛
        # m3n 步驟 2：以下狀態都在 cond 的鎖底下改；控制模組沒掛時只有 loop() 自己動它們
        self.cond = threading.Condition()
        self.running = False
        self.pending = False            # 叫醒記下的「跑一次」（叫幾次都只補一次）
        self.pending_keep = False       # 那次補跑帶不帶 keep_schedule（照最後一次叫醒）
        self.paused = False
        self.stopped = False            # 被 stop_on_nonzero 停掉
        self.last_exit = None
        self.last_end = None            # now() 格式的字串
        self.end_mono = None            # 上一次結束的 monotonic 時刻（重讀設定改週期時用）
        self.due = time.monotonic()     # 下次照週期該跑的時刻（monotonic）；剛開時立刻跑
        self.removed = False            # 重讀設定時被拿掉：跑完這次（若在跑）就結束執行緒


def err_path_for(template, inst, start):
    """m3 步驟 1：`exec_err_path`／`exec_out_path` 換掉 `<inst>`（inst 是檔＝它字面上的 dirname，
    是資料夾＝照字面），相對路徑以起點為準。沒寫回 None（＝丟掉）。"""
    if template is None:
        return None
    if INST_MARK in template:
        is_dir = os.path.isdir(os.path.join(start, inst))
        template = template.replace(INST_MARK, inst if is_dir else (os.path.dirname(inst) or "."))
    return os.path.join(start, template)


def expand(value, ctx, position):
    """整份設定檔展開 aos 指示詞（`$ref`／`$fmt`／`$env`），一路走進物件與陣列。

    `$ref` 的相對檔名以設定檔所在的資料夾為準（含被引進來的檔裡再 `$ref`，中心路徑不換）；
    `$opt` 物件原樣留著不走進去（核心沒有吃選項的位置，留給模組）。循環鏈往下帶，引到祖先＝`ReferenceCycle`。
    """
    loc = resolve_located(value, ctx, position)
    v = loc.value
    if isinstance(v, dict) and not is_option_object(v):
        return {k: expand(x, loc.ctx, loc.position + [k]) for k, x in v.items()}
    if isinstance(v, list):
        return [expand(x, loc.ctx, loc.position + [str(i)]) for i, x in enumerate(v)]
    return v


def read_config(path):
    """讀設定檔、整份展開指示詞，回展開後的 JSON。讀不到、不是 JSON、指示詞錯都是 `DirectiveError`。"""
    doc = load_document(path)
    return expand(doc.root, Context(doc, base_dir=os.path.dirname(os.path.abspath(path))), [])


def load_config(path):
    """m3 步驟 1：讀設定檔（先展開指示詞），回 (起點資料夾, [Item])。"""
    return load_setup(path)[:2]


def load_setup(path):
    """m3 步驟 1 加 m3n 步驟 1：回 (起點資料夾, [Item], 控制模組 socket 絕對路徑或 None)。"""
    s = load_full(path)
    return s.start, s.items, s.sock


class Setup:
    """`load_full()` 的結果。`modules` 是展開後的 `modules`，但 `state` 換成狀態檔的絕對路徑
    （重讀設定比對「模組改了沒」用）；`state_data` 是狀態檔的內容（沒讀或不在＝`{"insts": {}}`）。"""

    def __init__(self, start, items, sock, modules, state_path, state_data, out_tmpl=None, err_tmpl=None):
        self.start, self.items, self.sock = start, items, sock
        self.modules, self.state_path, self.state_data = modules, state_path, state_data
        self.out_tmpl, self.err_tmpl = out_tmpl, err_tmpl     # 頂層 exec_out_path／exec_err_path 原字（重讀比對用）

    @property
    def reload(self):
        return "reload" in self.modules

    @property
    def cgroup(self):
        return "cgroup" in self.modules


def _state_ref(raw, base_dir):
    """m3m 模組三：原始設定檔的 `modules.state` 必須是 `{"$ref": "<檔名>"}`（不帶 `#` 位置、不帶 `$at`），
    回 (狀態檔絕對路徑, 拿掉 state 之後的原始根)；沒寫 state 回 (None, 原始根)。
    相對檔名照其他 `$ref`，以設定檔所在資料夾為準。"""
    mods = raw.get("modules") if isinstance(raw, dict) else None
    if not isinstance(mods, dict) or "state" not in mods:
        return None, raw
    ref = mods["state"]
    if not (isinstance(ref, dict) and set(ref) == {"$ref"} and isinstance(ref["$ref"], str)
            and ref["$ref"] and "#" not in ref["$ref"]):
        raise ValueError('modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）')
    rest = dict(raw, modules={k: v for k, v in mods.items() if k != "state"})
    return os.path.join(base_dir, ref["$ref"]), rest


def load_full(path, read_state=True):
    """讀設定檔、展開指示詞，回 `Setup`。兩邊都沒有 interval_ms、`modules` 不是物件丟 ValueError；
    `modules.control` 沒寫 `socket` 自然丟錯。

    `modules.state` 先從原始檔拿出來（它指的檔第一次要寫時才建，不在時不能算 `$ref` 讀不到），
    其餘照整份展開；狀態檔在就照一般 `$ref` 展開讀進來，不在＝`{"insts": {}}`。
    `read_state=False`（重讀設定用）不讀狀態檔：重讀時以記憶體為準。"""
    doc = load_document(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    ctx = Context(doc, base_dir=base_dir)
    state_path, raw = _state_ref(doc.root, base_dir)
    top = expand(raw, ctx, [])
    modules = top.get("modules", {})
    if not isinstance(modules, dict):
        raise ValueError("modules 要是物件")       # 核心只認得它；目前讀 control、reload、state
    if state_path is None and "state" in modules:   # 例如整個 modules 是 $ref 引進來的
        raise ValueError('modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）')
    # 展開完才看 cwd（它也可以是 $ref 引進來的值）；相對的 cwd 以 daemon 啟動時的工作目錄為起點，不是設定檔的資料夾
    start = os.path.abspath(top.get("cwd", "."))
    items = []
    # insts 是物件：鍵＝inst 字面值、值＝該項設定（可為 {}）；位置照鍵的順序（JSON 讀入保序）（使用者 2026-10-01）
    for i, (inst, entry) in enumerate(top["insts"].items()):
        interval = entry.get("interval_ms", top.get("interval_ms"))
        if interval is None:
            raise ValueError("insts 的 %s 沒有 interval_ms，頂層也沒有" % json.dumps(inst, ensure_ascii=False))
        stop = entry.get("stop_on_nonzero", top.get("stop_on_nonzero", False))
        items.append(Item(i, inst, interval, stop,
                          err_path_for(top.get("exec_err_path"), inst, start),
                          err_path_for(top.get("exec_out_path"), inst, start),
                          entry.get("cgroup")))
    sock = None
    if "control" in modules:                        # m3n：有寫就開；socket 相對以起點為準
        sock = os.path.abspath(os.path.join(start, modules["control"]["socket"]))
    state_data = {"insts": {}}
    if state_path is not None:
        modules = dict(modules, state=state_path)
        if read_state and os.path.exists(state_path):
            state_data = expand(doc.root["modules"]["state"], ctx, ["modules", "state"])
    return Setup(start, items, sock, modules, state_path, state_data,
                 top.get("exec_out_path"), top.get("exec_err_path"))


def _block(item, stream, data):
    """收齊的一段輸出加標頭：`== <時間> <stdout|stderr> index=<n> inst=<inst> ==`；內容沒換行結尾就補一個。"""
    head = ("== %s %s index=%d inst=%s ==\n" % (now(), stream, item.index, item.inst)).encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    return head + data


def write_outputs(item, out, err):
    """aos-exec 這次的 stdout、stderr（已收齊）：各自有內容才寫，前面一行標頭，接在 `out_path`／`err_path`
    指的檔尾（父資料夾不在就建）。兩段在同一把鎖底下寫完，多項同時結束也不交錯。"""
    parts = []
    if out and item.out_path:
        parts.append((item.out_path, _block(item, "stdout", out)))
    if err and item.err_path:
        parts.append((item.err_path, _block(item, "stderr", err)))
    if not parts:
        return
    with _out:
        for path, data in parts:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "ab") as f:
                f.write(data)


def run_once(item, start):
    """m3 步驟 2：叫一次 aos-exec，等它結束，回 (碼, 毫秒, 有沒有收屍)。被訊號殺的碼換成 128+N。
    stdout／stderr 沒設路徑就直接丟到 /dev/null；有設就收齊再一次寫出（共用出口才不交錯）。

    m3m 模組二（掛了 cgroup，`item.frame` 有值）：子程序先進那一項的框再 exec aos-exec；aos-exec 一結束
    （毫秒算到這裡）就清框（框裡還有程序就 `cgroup.kill`、等清空），清完才收齊輸出、回來。
    殘留的程序可能還拿著輸出的 pipe，所以 pipe 另開執行緒讀，清完框它才讀得到結尾。"""
    t0 = time.monotonic()
    pipe = lambda path: subprocess.DEVNULL if path is None else subprocess.PIPE
    argv = [EXEC, item.inst]
    if item.frame is not None:
        argv = _cg.argv(item.frame, argv)
    p = subprocess.Popen(argv, cwd=start, env=item.env, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=pipe(item.out_path), stderr=pipe(item.err_path))
    reaped = False
    if item.frame is None:
        out, err = p.communicate()
        ms = int((time.monotonic() - t0) * 1000)
    else:
        got = {}
        reader = threading.Thread(target=lambda: got.update(r=p.communicate()), daemon=True)
        reader.start()
        p.wait()
        ms = int((time.monotonic() - t0) * 1000)
        import aos_daemon_cgroup
        reaped = aos_daemon_cgroup.clear(item.frame)
        reader.join()
        out, err = got["r"]
    code = p.returncode
    write_outputs(item, out, err)
    return (128 - code if code < 0 else code), ms, reaped


def _next_run(item):
    """在 cond 的鎖底下等到該跑：有待補就跑（回它的 keep_schedule）；暫停、已停就一直等；
    否則等到 due（照週期跑的那次，回 False）。m3n 步驟 2。被重讀設定拿掉了回 None。"""
    while True:
        if item.removed:
            return None
        if item.pending and not item.stopped:
            keep = item.pending_keep
            item.pending = item.pending_keep = False
            return keep
        if item.stopped or item.paused:
            item.cond.wait()
            continue
        left = item.due - time.monotonic()
        if left <= 0:
            return False
        item.cond.wait(left)


def loop(item, start):
    """m3 步驟 3、4：叫 → 等 → 印 → 睡 interval_ms；非 0 且 stop_on_nonzero 就印 stopped、不再叫。
    m3n 步驟 2：睡改成等 cond（叫得醒）；停掉時執行緒不結束、一直等（resume 救得回來）。
    控制模組沒掛時沒人碰狀態，行為跟 m3 一樣。
    m3m：被重讀設定拿掉的項，正在跑的那次照樣跑完印完，之後執行緒結束（掛了 cgroup 就刪框）。
    掛了 cgroup：「這次結束」＝aos-exec 結束而且框清空；有清到東西時 `exit=` 之後多印一行 `reaped`。"""
    while True:
        with item.cond:
            keep = _next_run(item)
            if keep is not None:
                item.running = True
        if keep is None:
            _gone(item)
            return
        code, ms, reaped = run_once(item, start)
        say("inst=%s exit=%d ms=%d" % (item.inst, code, ms))
        if reaped:
            say("inst=%s reaped" % item.inst)
        stopped = False
        with item.cond:
            t = time.monotonic()
            item.running = False
            item.last_exit, item.last_end, item.end_mono = code, now(), t
            removed = item.removed
            if not removed:
                # 照週期跑的、不帶 keep_schedule 的叫醒：週期從這次結束重新算；帶 keep_schedule 的
                # 不碰 due，除非 due 已經被這次蓋過去（不補跑漏掉的）
                if not keep or item.due <= t:
                    item.due = t + item.interval_ms / 1000.0
                if code != 0 and item.stop_on_nonzero:
                    item.stopped = stopped = True
                    item.pending = False
                    say("inst=%s stopped" % item.inst)
        if removed:
            _gone(item)
            return
        if stopped:
            state_changed()


def _gone(item):
    """被重讀設定拿掉的項，執行緒結束前：掛了 cgroup 就刪它的框（m3m 模組二）。
    同一個 inst 已經又被加回來（新的一項用同一個框）就不刪。在 _items_lock 底下做，跟重讀設定建框排開。
    呼叫時不能拿著 item.cond（鎖的順序是 _items_lock → item.cond）。"""
    if item.frame is None:
        return
    with _items_lock:
        if item.inst not in _items:
            _cg.remove(item.frame)


def state_changed():
    """暫停或已停變了（pause、resume、stop_on_nonzero 停掉、重讀設定拿掉項）：掛了記住狀態模組就當場寫整份。"""
    if _state is not None:
        _state.save(snapshot())


def snapshot():
    """目前清單的 [Item]（照鍵的順序），在 _items_lock 底下拷一份。"""
    with _items_lock:
        return list(_items.values())


def give_env(item, sock):
    """控制模組掛著時，開 aos-exec 的環境多放兩個變數（m3n 步驟 4）。"""
    if sock is not None:
        item.env = dict(os.environ, AOS_DAEMON_SOCKET=sock, AOS_DAEMON_INST=item.inst)


def start_item(item, start):
    threading.Thread(target=loop, args=(item, start), daemon=True).start()


def _quit(signum, frame):
    """m3 步驟 5：SIGINT／SIGTERM 直接退出、回 0，不殺也不等子程序。
    控制模組掛著時先刪 socket 檔（m3n 步驟 6）。"""
    if _sock_path is not None:
        try:
            os.unlink(_sock_path)
        except FileNotFoundError:       # 訊號來在 bind 之前：還沒建
            pass
    os._exit(0)


class _Parser(argparse.ArgumentParser):
    """aos 結束碼慣例：argparse 的用法錯預設回 2，改回 1。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "%s: error: %s\n" % (self.prog, message))


def _catch_hup():
    """m3m 模組一：接 SIGHUP，回一個 pipe 的讀端；主執行緒讀它等 SIGHUP。
    用 `signal.set_wakeup_fd`：每個訊號的編號都會寫進 pipe，所以訊號來在任何時候都不會漏；
    重讀中又來幾次，讀出來是同一批，讀完再重讀一次就好。SIGHUP 的 Python handler 什麼都不做
    （只為了不被預設動作殺掉）。"""
    r, w = os.pipe()
    os.set_blocking(w, False)
    signal.set_wakeup_fd(w)
    signal.signal(signal.SIGHUP, lambda signum, frame: None)
    return r


def main(argv=None):
    ap = _Parser(prog="aos-daemon", description="照設定檔的清單，定期叫 aos-exec")
    ap.add_argument("--config", required=True, metavar="F", help="設定檔（JSON）")
    a = ap.parse_args(argv)
    global _sock_path, _state, _cg
    try:
        setup = load_full(a.config)
    except (ValueError, DirectiveError) as e:
        sys.stderr.write("aos-daemon: config: %s\n" % e)
        return 1
    start, items, sock = setup.start, setup.items, setup.sock
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    if setup.cgroup:                    # m3m 模組二：沒有委派好的 cgroup v2 就自然丟錯、回 1（C1）
        import aos_daemon_cgroup
        _cg = aos_daemon_cgroup.Tree()
        for item in items:
            _cg.make(item, startup=True)
            _cg.announce(item, say)
    with _items_lock:
        _items.update((item.inst, item) for item in items)
    if setup.state_path is not None:    # m3m 模組三：照檔恢復暫停、已停（不在清單上的鍵丟掉）
        import aos_daemon_state
        _state = aos_daemon_state.StateFile(setup.state_path, setup.state_data)
        aos_daemon_state.restore(items, setup.state_data)
    if sock is not None:                # m3n：先開好 socket 再起各項，任務一開始就叫得到
        import aos_daemon_ctl
        for item in items:
            give_env(item, sock)
        _sock_path = sock               # 先記好再 bind：bind 完立刻來的訊號也刪得到
        aos_daemon_ctl.serve(sock, _items)
    hup = None
    if setup.reload:                    # m3m 模組一：沒掛時 SIGHUP 照 Python 預設（daemon 被殺）
        import aos_daemon_reload
        hup = _catch_hup()
    for item in items:
        start_item(item, start)
    while True:                         # 所有項都停了也照樣開著（使用者 2026-10-01）
        if hup is None:
            signal.pause()
        elif signal.SIGHUP in os.read(hup, 512):
            aos_daemon_reload.reload(a.config, setup)
