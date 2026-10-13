#!/usr/bin/env python3
"""daemon：管很多個 loop 的表；自己也是一個 loop（每一圈＝掃一次控制資料夾）。純標準庫。

    python3 aos_daemon.py DAEMON.json

`run(path)` 跟命令列一模一樣。

daemon.json（先用指示詞 lib 解，基準＝daemon 啟動時的 cwd）：

    control_dir    控制資料夾（必填），沒有就建
    load           起來後先 load 這個檔（選填；跟丟一條 load 指令一樣，但失敗＝起不來）
    save           收工時先 save 到這個檔（選填；SIGTERM、ctl 的 stop、times 跑完才存，SIGINT 不存）
    work_dir       替 loop 生包裝檔的地方（選填；沒寫＝control_dir 旁邊的 loops/）
    grace_ms       收工時等底下的 loop 多久，過了整群 SIGKILL（非負整數；沒寫＝10000；要比 loop 的 grace_ms 長）
    times          掃幾圈就收工（非負整數；null＝不限，預設）
    interval_ms    每圈隔多久（非負整數；沒寫＝200）
    interval_mode  "after"＝掃完再隔 interval_ms（預設）；"fixed"＝固定週期，掃超過一拍就跳拍（state 的 skipped），同 loop
    ctl            daemon 自己的 ctl.json（選填；不能放在 control_dir 裡）：paused＝不掃資料夾（指令堆著、loop 照跑）、
                   stop＝收工（now＝底下的 loop 當場收掉；沒 now＝等它們這次跑完）、times、interval_ms、interval_mode
    ctl_poll_ms    多久看一次 ctl.json（正整數；沒寫＝1000）
    state          daemon 自己的 state.json（選填）：骨架跟 loop 同一份（id、state、pid、runs＝掃了幾圈、times、interval_ms、
                   interval_mode、ctl_mtime、last_error＝最近一圈印到 stderr 的最後一行錯，沒有＝null），
                   加上 skipped、loops（表上幾個；要細節用 list／get／state 指令查）

表上每個 loop 是一支子程序 `aos_loop.py LOOP.json`（自成一個 session），daemon 跟它之間只靠兩個檔：寫它的 ctl.json、
讀它的 state.json。loop.json 有寫 ctl／state 就用它寫的；沒寫的，daemon 在 `work_dir/<編號>/` 生一份包裝檔
`loop.json`（每個 key 用 `$ref` 指回原檔，補上 ctl、state 指到同一個資料夾）、起的是包裝檔；移除或收工時刪掉那個資料夾。

指令：往控制資料夾放一個 `名字.json`。daemon 每圈把裡面的 `*.json` 照檔名順序讀進來處理，處理完改成 `名字.json.done`，
內容換成一問一答：

    {"request": 原指令, "ok": true,  "result": 結果}
    {"request": 原指令, "ok": false, "error": {"code": "NotFound", "msg": "白話"}}

讀到不合法的 JSON 也一樣當場變成 `.done`（`request` 是讀到的原文字串，error.code＝BadCommand）。
寫到一半被讀到＝BadCommand，寫的人自己負責（先寫 `.` 開頭的檔再改名）；`.` 開頭的檔不讀。`.done` 由丟指令的人清。不 fsync。

指令一律 {"op", "id", ...參數}。`id` 要是 loop.json（或 inst.json）的絕對路徑（相對＝FieldType），daemon 轉成 realpath；
後面可以接 `#/位置`（同 aos_inst 的 TARGET：那份檔裡那一格），id＝realpath ＋ `#` ＋ 正規化過的位置（同一份檔兩個位置＝兩個 loop）：

    {"op": "add",       "id": ID}                 起一個 loop                                  → result＝realpath
                                                  ID 也可以是 inst.json（頂層沒有 "inst"、有 "argv"）：當成只跑一次的 loop，
                                                  包裝檔 {"inst": {"$ref": 它}, "times": 1}；id 照樣是那份 inst.json 的 realpath
    {"op": "set",       "id": ID, "how": {...}}   改 times／interval_ms／interval_mode（寫進它的 ctl.json）
    {"op": "pause",     "id": ID, "wait": B}      暫停；wait＝true 等這次跑完，false 當場收掉（預設 true）
    {"op": "resume",    "id": ID}                 繼續
    {"op": "add_times", "id": ID, "delta": N}     總次數加減 N（最少到 0；不限次數＝Conflict；loop 已經退出就沒作用）
    {"op": "remove",    "id": ID, "wait": B}      停掉它（ctl 的 stop）、等行程結束、從表上拿掉 → result＝最後的狀態物件
    {"op": "state",     "id": ID}                 → result＝狀態字串（loop 還沒寫 state.json＝"starting"）
    {"op": "get",       "id": ID}                 → result＝狀態物件（就是它的 state.json；次數跑完的 loop 會自己退出，
                                                  留在表上、state "done"；其他原因結束的＝"stopped"）
    {"op": "list"}                                → result＝[狀態物件, ...]
    {"op": "save",      "path": P}                表存成一份 JSON（整份重寫）                → result＝存了幾個
    {"op": "load",      "path": P}                從 save 存的檔一次起回來                    → result＝[id, ...]

set／pause／resume／add_times 回改完的狀態物件，**等 loop 讀到了才回**（它的 state.json 的 ctl_mtime 趕上 daemon 寫的那份）；
pause 還要等這次真的停了；remove 等行程結束。等的期間指令檔留在原地。loop 行程已經結束的，馬上回當下的狀態。
error.code（只供參考，看 ok 就好）：BadCommand、UnknownOp、FieldType、NotFound、Exists、Conflict、ReadFailed、JsonSyntax、
WriteFailed、Internal。

save 存每個 loop 的 {"loop": loop.json 的 realpath, "ctl": 當下 ctl.json 的內容}；runs 在 loop 行程裡、不存，
load 回來從 0 數。先寫 `.名字.tmp` 再改名。load 全有全無：某個 loop.json 不在（NotFound）、已經在表上或檔裡重複、
它自己的 state.json 裡的 pid 還活著（Exists）、格式不對（FieldType）——任何一點不對就回 error，一個都不起。
load 會把存下來的 ctl 內容寫回各 loop 的 ctl.json 再起它。

收工：SIGTERM＝先 save（config 有 save）、對每個 loop 的 session 送 SIGTERM、等 grace_ms、沒走的整群 SIGKILL。
SIGINT 同樣收、不存。ctl 的 stop／times 跑完：先 save；now＝同 SIGTERM，沒 now＝替每個 loop 的 ctl.json 寫 stop、等它們自己結束。
跑起來之後出意外不結束，只往 stderr 印一行（同一件事印一次）：控制資料夾看不了（ScanFailed）、回覆寫不了
（ReplyFailed：改把指令改名成 .done；改名也不行就放著不管）、指令處理出了沒料到的錯（回 Internal）。
命令列退出碼：0＝正常結束；1＝起不來，或收工時 save 失敗（stderr 印一行「代號: 白話」）。
"""
import math
import os
import signal
import sys
import threading
import time

from aos_loop import CtlFile, StateFile, load_config as _load_cfg, state_doc, want
# 表在 aos_daemon_table，指令與控制資料夾在 aos_daemon_folder；這裡 re-export，既有的 import 照用
from aos_daemon_folder import _Folder, _load, _save, handle
from aos_daemon_table import AOS_LOOP, DaemonError, Table

__all__ = ["DaemonError", "load_config", "run"]

DEFAULTS = {"control_dir": None, "load": None, "save": None, "work_dir": None, "grace_ms": 10000,
            "times": None, "interval_ms": 200, "interval_mode": "after", "ctl": None, "ctl_poll_ms": 1000, "state": None}
_CAUGHT = (signal.SIGINT, signal.SIGTERM)


def load_config(path):
    """讀 daemon.json，回 (realpath, 填好預設值的 dict)。"""
    ident, cfg = _load_cfg(path, DEFAULTS, need_inst=False, err=DaemonError)
    if cfg["work_dir"] is None:
        cfg["work_dir"] = os.path.join(os.path.dirname(cfg["control_dir"]), "loops")
    if cfg["ctl"] and os.path.commonpath([cfg["ctl"], cfg["control_dir"]]) == cfg["control_dir"]:
        raise DaemonError("Conflict", "ctl %s 不能放在 control_dir 裡（會被當成指令讀）" % cfg["ctl"])
    return ident, cfg


# ---- 主迴圈：daemon 自己也是一個 loop ----

def serve(ident, cfg, got):
    """跑到收工。got＝收到的訊號（list，訊號處理函式往裡面放）。save 失敗丟 DaemonError（loop 們照樣收掉）。"""
    try:
        os.makedirs(cfg["control_dir"], exist_ok=True)
    except OSError as e:
        raise DaemonError("MkdirFailed", "建不了控制資料夾：%s" % e)
    table = Table(cfg)
    folder = _Folder(cfg["control_dir"])
    if cfg["load"]:
        _load(table, cfg["load"])
    ctl = CtlFile(cfg["ctl"], "daemon") if cfg["ctl"] else None
    initial = {"paused": (False, False), "stop": (False, False), "times": cfg["times"], "interval_ms": cfg["interval_ms"],
               "interval_mode": cfg["interval_mode"]}
    runs, skipped, next_poll, next_scan = 0, 0, 0, 0
    anchor, tick = None, -1         # fixed：第 0 拍的時間、這一圈在第幾拍（同 loop）
    sf = StateFile(cfg["state"], "daemon")
    w = want(initial, {})

    def doc(state):
        return state_doc(ident, state, w, ctl, runs, folder.last_error, skipped=skipped, loops=len(table.entries))
    save, now_ = False, True
    try:
        while True:
            t = time.monotonic()
            if ctl and t >= next_poll:
                ctl.poll()
                next_poll = t + cfg["ctl_poll_ms"] / 1000
            w = want(initial, ctl.good if ctl else {})
            table.reap()
            if got:
                save = signal.SIGTERM in got
                break
            if w["stop"][0]:
                save, now_ = True, w["stop"][1]
                break
            if w["times"] is not None and runs >= w["times"]:
                save, now_ = True, False
                break
            if not w["paused"][0] and t >= next_scan:
                iv = w["interval_ms"] / 1000
                if w["interval_mode"] == "fixed" and iv:
                    if anchor is None:
                        anchor, tick = t, 0
                    else:
                        n = max(tick + 1, math.floor((t - anchor) / iv))
                        skipped += n - tick - 1
                        tick = n
                else:
                    anchor, tick = None, -1
                folder.scan(table)
                runs += 1
                next_scan = anchor + (tick + 1) * iv if anchor is not None else time.monotonic() + iv
            sf.write(doc("paused" if w["paused"][0] else "waiting"))
            time.sleep(0.02)
    finally:
        try:
            if save and cfg["save"]:
                _save(table, cfg["save"])
        finally:
            sf.write(doc("stopping"))
            table.shutdown(now_, cfg["grace_ms"], got)
            folder.flush()
            for e in list(table.entries.values()):
                table.drop(e)
            sf.write(doc("stopped"))


def run(path):
    """跟命令列 `aos_daemon.py DAEMON.json` 一模一樣。正常收工回 None；起不來或 save 失敗丟 DaemonError。"""
    main = threading.current_thread() is threading.main_thread()
    got = []
    old = {s: signal.signal(s, lambda signum, frame: got.append(signum)) for s in _CAUGHT} if main else {}
    try:
        serve(*load_config(path), got)
    finally:
        for s, h in old.items():
            signal.signal(s, h)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：aos_daemon.py DAEMON.json", file=sys.stderr)
        return 1
    try:
        run(args[0])
        return 0
    except DaemonError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
