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

# stdout 那一行與 aos-exec 的 stderr 都在這把鎖底下一次寫完，多項同時結束也不交錯（m3 步驟 2）
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

    def __init__(self, index, inst, interval_ms, stop_on_nonzero, err_path):
        self.index = index
        self.inst = inst
        self.interval_ms = interval_ms
        self.stop_on_nonzero = stop_on_nonzero
        self.err_path = err_path        # 絕對路徑；None＝接到 daemon 自己的 stderr
        self.env = None                 # 開 aos-exec 的環境；None＝照 daemon 的（控制模組沒掛）
        # m3n 步驟 2：以下狀態都在 cond 的鎖底下改；控制模組沒掛時只有 loop() 自己動它們
        self.cond = threading.Condition()
        self.running = False
        self.pending = False            # 叫醒記下的「跑一次」（叫幾次都只補一次）
        self.pending_keep = False       # 那次補跑帶不帶 keep_schedule（照最後一次叫醒）
        self.paused = False
        self.stopped = False            # 被 stop_on_nonzero 停掉
        self.last_exit = None
        self.last_end = None            # now() 格式的字串
        self.due = time.monotonic()     # 下次照週期該跑的時刻（monotonic）；剛開時立刻跑


def err_path_for(template, inst, start):
    """m3 步驟 1：`exec_err_path` 換掉 `<inst>`（inst 是檔＝它字面上的 dirname，是資料夾＝照字面），
    相對路徑以起點為準。沒寫 `exec_err_path` 回 None。"""
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
    """m3 步驟 1 加 m3n 步驟 1：回 (起點資料夾, [Item], 控制模組 socket 絕對路徑或 None)。
    兩邊都沒有 interval_ms、`modules` 不是物件丟 ValueError；`modules.control` 沒寫 `socket` 自然丟錯。"""
    top = read_config(path)
    modules = top.get("modules", {})
    if not isinstance(modules, dict):
        raise ValueError("modules 要是物件")       # 核心只認得它；目前只讀 control，其他鍵不看
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
                          err_path_for(top.get("exec_err_path"), inst, start)))
    sock = None
    if "control" in modules:                        # m3n：有寫就開；socket 相對以起點為準
        sock = os.path.abspath(os.path.join(start, modules["control"]["socket"]))
    return start, items, sock


def write_err(item, data):
    """aos-exec 這次的 stderr（已收齊）：先一行標頭，再原樣接上；有內容才寫。
    寫到 `item.err_path`（接在檔尾、父資料夾不在就建）或 daemon 自己的 stderr。"""
    if not data:
        return
    head = ("== %s index=%d inst=%s ==\n" % (now(), item.index, item.inst)).encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    with _out:
        if item.err_path is None:
            sys.stderr.flush()
            sys.stderr.buffer.write(head + data)
            sys.stderr.buffer.flush()
        else:
            os.makedirs(os.path.dirname(item.err_path), exist_ok=True)
            with open(item.err_path, "ab") as f:
                f.write(head + data)


def run_once(item, start):
    """m3 步驟 2：叫一次 aos-exec，等它結束，回 (碼, 毫秒)。被訊號殺的碼換成 128+N。"""
    t0 = time.monotonic()
    p = subprocess.Popen([EXEC, item.inst], cwd=start, env=item.env, start_new_session=True,
                         stdin=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err = p.stderr.read()               # 收齊再一次寫出，共用出口才不交錯
    p.stderr.close()
    code = p.wait()
    ms = int((time.monotonic() - t0) * 1000)
    write_err(item, err)
    return (128 - code if code < 0 else code), ms


def _next_run(item):
    """在 cond 的鎖底下等到該跑：有待補就跑（回它的 keep_schedule）；暫停、已停就一直等；
    否則等到 due（照週期跑的那次，回 False）。m3n 步驟 2。"""
    while True:
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
    控制模組沒掛時沒人碰狀態，行為跟 m3 一樣。"""
    while True:
        with item.cond:
            keep = _next_run(item)
            item.running = True
        code, ms = run_once(item, start)
        say("inst=%s exit=%d ms=%d" % (item.inst, code, ms))
        with item.cond:
            t = time.monotonic()
            item.running = False
            item.last_exit, item.last_end = code, now()
            # 照週期跑的、不帶 keep_schedule 的叫醒：週期從這次結束重新算；帶 keep_schedule 的
            # 不碰 due，除非 due 已經被這次蓋過去（不補跑漏掉的）
            if not keep or item.due <= t:
                item.due = t + item.interval_ms / 1000.0
            if code != 0 and item.stop_on_nonzero:
                item.stopped = True
                item.pending = False
                say("inst=%s stopped" % item.inst)


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


def main(argv=None):
    ap = _Parser(prog="aos-daemon", description="照設定檔的清單，定期叫 aos-exec")
    ap.add_argument("--config", required=True, metavar="F", help="設定檔（JSON）")
    a = ap.parse_args(argv)
    global _sock_path
    try:
        start, items, sock = load_setup(a.config)
    except (ValueError, DirectiveError) as e:
        sys.stderr.write("aos-daemon: config: %s\n" % e)
        return 1
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    if sock is not None:                # m3n：先開好 socket 再起各項，任務一開始就叫得到
        import aos_daemon_ctl
        for item in items:
            item.env = dict(os.environ, AOS_DAEMON_SOCKET=sock, AOS_DAEMON_INST=item.inst)
        _sock_path = sock               # 先記好再 bind：bind 完立刻來的訊號也刪得到
        aos_daemon_ctl.serve(sock, {item.inst: item for item in items})
    for item in items:
        threading.Thread(target=loop, args=(item, start), daemon=True).start()
    while True:                         # 所有項都停了也照樣開著（使用者 2026-10-01）
        signal.pause()
