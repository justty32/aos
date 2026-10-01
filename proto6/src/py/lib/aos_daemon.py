"""最核心的 aos-daemon：一個叫 aos-exec 的 cron（plan m3-daemon-core.md）。

讀設定檔裡的 inst 清單，每一項一條執行緒，照自己的週期叫一次 `<bin>/aos-exec <inst 字面值>`，
等它結束、stdout 印一行。沒有 socket、沒有登記、沒有收屍。
〔使用者方向 2026-10-01〕POC 默認一切正常：設定檔讀得懂、路徑都對、aos-exec 叫得起來；
不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。
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

EXEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "aos-exec")
INST_MARK = "<inst>"

# stdout 那一行與 aos-exec 的 stderr 都在這把鎖底下一次寫完，多項同時結束也不交錯（m3 步驟 2）
_out = threading.Lock()


def now():
    """印出那一刻的本地時間，ISO 8601 帶時區，到秒：2026-10-01T15:04:05+08:00。"""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def say(text):
    """stdout 一行，帶時間，寫完立刻 flush。"""
    with _out:
        sys.stdout.write("%s %s\n" % (now(), text))
        sys.stdout.flush()


class Item:
    """清單的一項：id＝`inst` 字面值；index＝在 `insts` 的位置（從 0 起）。"""

    def __init__(self, index, inst, interval_ms, stop_on_nonzero, err_path):
        self.index = index
        self.inst = inst
        self.id = inst
        self.interval_ms = interval_ms
        self.stop_on_nonzero = stop_on_nonzero
        self.err_path = err_path        # 絕對路徑；None＝接到 daemon 自己的 stderr


def err_path_for(template, inst, start):
    """m3 步驟 1：`exec_err_path` 換掉 `<inst>`（inst 是檔＝它字面上的 dirname，是資料夾＝照字面），
    相對路徑以起點為準。沒寫 `exec_err_path` 回 None。"""
    if template is None:
        return None
    if INST_MARK in template:
        is_dir = os.path.isdir(os.path.join(start, inst))
        template = template.replace(INST_MARK, inst if is_dir else (os.path.dirname(inst) or "."))
    return os.path.join(start, template)


def load_config(path):
    """m3 步驟 1：讀設定檔，回 (起點資料夾, [Item])。兩邊都沒有 interval_ms 丟 ValueError。"""
    with open(path, encoding="utf-8") as f:
        top = json.load(f)
    start = os.path.abspath(top.get("cwd", "."))     # 相對的 cwd 也以 daemon 啟動時的工作目錄為起點
    items = []
    for i, entry in enumerate(top["insts"]):
        interval = entry.get("interval_ms", top.get("interval_ms"))
        if interval is None:
            raise ValueError("insts[%d]（%s）沒有 interval_ms，頂層也沒有" % (i, entry["inst"]))
        stop = entry.get("stop_on_nonzero", top.get("stop_on_nonzero", False))
        items.append(Item(i, entry["inst"], interval, stop,
                          err_path_for(top.get("exec_err_path"), entry["inst"], start)))
    return start, items


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
    p = subprocess.Popen([EXEC, item.inst], cwd=start, start_new_session=True,
                         stdin=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err = p.stderr.read()               # 收齊再一次寫出，共用出口才不交錯
    p.stderr.close()
    code = p.wait()
    ms = int((time.monotonic() - t0) * 1000)
    write_err(item, err)
    return (128 - code if code < 0 else code), ms


def loop(item, start):
    """m3 步驟 3、4：叫 → 等 → 印 → 睡 interval_ms；非 0 且 stop_on_nonzero 就印 stopped、不再叫。"""
    while True:
        code, ms = run_once(item, start)
        say("id=%s exit=%d ms=%d" % (item.id, code, ms))
        if code != 0 and item.stop_on_nonzero:
            say("id=%s stopped" % item.id)
            return
        time.sleep(item.interval_ms / 1000.0)


def _quit(signum, frame):
    """m3 步驟 5：SIGINT／SIGTERM 直接退出、回 0，不殺也不等子程序。"""
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
    try:
        start, items = load_config(a.config)
    except ValueError as e:
        sys.stderr.write("aos-daemon: config: %s\n" % e)
        return 1
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    for item in items:
        threading.Thread(target=loop, args=(item, start), daemon=True).start()
    while True:                         # 所有項都停了也照樣開著（使用者 2026-10-01）
        signal.pause()
