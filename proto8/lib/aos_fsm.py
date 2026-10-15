#!/usr/bin/env python3
"""fsm：一拍跑一格的狀態機。讀回現在狀態、查表跑那一格、換狀態、寫 state 窗、退出。純標準庫。
照 NORMS N-20、N-36～N-41 的基礎實作（10-15）；說明在同資料夾的 fsm.md。

    python3 aos_fsm.py [--key 值 ...] [FSM.json | -]

設定從哪來照 aos_cli：FSM.json（可接 `#/位置`）、`-`＝stdin；純量 key 有同名旗標（`--start`、`--state`、`--ctl`、
`--lock`、`--max-steps`、`--max-fails`），`states`、`end` 不鏡射；`--` 不收。`run(x)` 收路徑或一份設定 dict。

    start      起始狀態名（必填，要在 states 裡）
    states     狀態名 → 格（必填；格的寫法見 aos_methods）
    end        選填，出口名單（巢狀的內層用，N-40）
    state      state 窗（必填，N-19；缺 key 或 null＝WindowMissing、不執行）
    ctl        ctl 窗（選填）：paused／stop 任一為真＝這拍不起格就退出；seq 回音到 state 的 ctl_seq
    lock       lock 窗（選填）：一個資料夾，mkdir 拿鎖、退出前 rmdir；已經在＝LockBusy（fsm 自己出錯）
    max_steps  選填正整數：自上次在 start 起跑了這麼多格，再跑＝MaxSteps 錯（照出錯規則）
    max_fails  選填正整數，預設 3：連續出錯這麼多次就停住（state 的 halted: true），之後的拍不起格、等人；
               人要接手＝把 state 窗的 halted 拿掉或改 false（或刪掉整份 state＝從 start 重來）。成功一次 fails 歸零

一拍：拿鎖 → 讀 ctl → 讀 state（檔還沒有＝從 start 起）→ 查格 → state 先寫 `step`＋`running: true` → 跑格
（stdin＝`{"state", "step", "prev", "cfg"}`，cfg＝這份設定整份、指示詞解好、旗標併進去）→ 讀格 stdout 最後一份 → 換狀態 → 寫 state → stdout 吐一行 → 放鎖。

state 窗：`{"phase", "step", "running", "data", "last_error", "ctl_seq", "fails", "halted"}`，只有 fsm 自己寫；不寫時間、pid（N-39）。
stdout：起了格就吐一行 `{"step", "from", "to", "code", "ms"}`（出錯多 `error`；永遠不帶 `next`）；
內層走到 `end` 名單裡的 next 時，再把格的那份結果原樣吐成最後一份。ctl 擋下的那拍什麼都不吐。
退出碼只說 fsm 自己：0＝這拍做完（格出錯由表處理也是 0）；125＝設定不對、窗缺、拿不到鎖、state 讀寫不了。
"""
import os
import sys
import time

import aos_cli
import aos_methods
from aos_cli import CliError
from aos_ctl_state import CtlFile, read_state, require, write_json
from aos_methods import MethodsError

__all__ = ["FLAGS", "FsmError", "check_config", "main", "run"]

FLAGS = ("start", "state", "ctl", "lock", "max_steps", "max_fails")
MAX_FAILS = 3                  # 沒寫 max_fails 的預設
ERR_LIMIT = 300                # last_error 最多幾個字


class FsmError(CliError):
    """fsm 自己出錯（退出碼 125）。格出錯不算，那個由表處理。"""


def check_config(doc, ident=None):
    """驗設定、路徑轉成絕對的，回 cfg dict（多 `id`＝設定的 id）。"""
    require(doc, ("state",), FsmError)
    try:
        start, states, end = aos_methods.check_table(doc, ident or "<stdin>")
    except MethodsError as e:
        raise FsmError(e.code, e.msg)
    cfg = {"id": ident, "start": start, "states": states, "end": end, "doc": doc}   # doc 原樣給格當 stdin 的 cfg
    for k in ("state", "ctl", "lock"):
        v = doc.get(k)
        if not (v is None or isinstance(v, str) and v):
            raise FsmError("FieldType", "%s 要是路徑字串或 null，不是 %r" % (k, v))
        cfg[k] = None if v is None else os.path.abspath(v)
    m = doc.get("max_steps")
    if not (m is None or isinstance(m, int) and not isinstance(m, bool) and m >= 1):
        raise FsmError("FieldType", "max_steps 要是正整數或 null，不是 %r" % (m,))
    cfg["max_steps"] = m
    k = doc.get("max_fails", MAX_FAILS)
    if not (isinstance(k, int) and not isinstance(k, bool) and k >= 1):
        raise FsmError("FieldType", "max_fails 要是正整數，不是 %r" % (k,))
    cfg["max_fails"] = k
    return cfg


def _write(cfg, st):
    try:
        write_json(cfg["state"], st)
    except OSError as e:
        raise FsmError("StateWriteFailed", "寫不了 state 窗 %s：%s" % (cfg["state"], e))


def _read(cfg):
    """讀回 state 窗；檔還沒有＝從 start 起（N-36）。檔在但讀不懂＝StateBad。"""
    if not os.path.exists(cfg["state"]):
        return {"phase": cfg["start"], "step": 0, "running": False, "data": None, "last_error": None, "ctl_seq": None,
                "fails": 0, "halted": False}
    st = read_state(cfg["state"])
    if st is None or not isinstance(st.get("phase"), str) or not isinstance(st.get("step", 0), int):
        raise FsmError("StateBad", "state 窗 %s 讀不懂（要有字串 phase、整數 step）" % cfg["state"])
    return st


def tick(cfg):
    """跑一拍（鎖已經拿好）。"""
    seq, held = None, False
    if cfg["ctl"]:
        ctl = CtlFile(cfg["ctl"], "fsm")
        ctl.poll()
        seq = ctl.seq
        held = any(ctl.good.get(k, (False,))[0] for k in ("paused", "stop"))
    st = _read(cfg)
    if held or st.get("halted") is True:     # 這拍不起格；只把 seq 回音寫回去（停住＝等人把 halted 拿掉）
        if st.get("ctl_seq") != seq:
            _write(cfg, dict(st, ctl_seq=seq))
        return
    start, states = cfg["start"], cfg["states"]
    phase, data, step = st["phase"], st.get("data"), st.get("step", 0)
    prev = {"interrupted": True, "data": data} if st.get("running") is True else data
    fails = st.get("fails") if isinstance(st.get("fails"), int) else 0
    out = {"phase": phase, "step": step, "running": False, "data": data, "last_error": None, "ctl_seq": seq,
           "fails": 0, "halted": False}
    line = {"step": step, "from": phase, "to": phase, "code": None, "ms": 0}
    t0 = time.monotonic()
    try:
        if cfg["max_steps"] is not None and step >= cfg["max_steps"]:
            raise MethodsError("MaxSteps", "自上次在 %s 起已經跑了 %d 格（max_steps）" % (start, step))
        inst, inst_id, static = aos_methods.cell(states, phase, cfg["id"])
        step += 1
        _write(cfg, dict(st, step=step, running=True, ctl_seq=seq))      # 起格前先寫 step：被殺一半下一拍認得出來
        out["step"] = line["step"] = step
        result, ret = aos_methods.run_cell(inst, inst_id, {"state": phase, "step": step, "prev": prev,
                                                                   "cfg": cfg["doc"]})
        line["code"] = result["code"]
        if result["code"] != 0:
            ce = result.get("cell_error")       # 格自己 stderr 的 N-29 錯誤＝真正原因
            raise MethodsError("CellFailed", "%s: %s" % (ce["code"], ce["msg"]) if ce
                               else "格 %s 結束碼 %d" % (phase, result["code"]))
        ret = ret if isinstance(ret, dict) else {}
        nxt = ret["next"] if "next" in ret else static
        if not (nxt is None or isinstance(nxt, str)):
            raise MethodsError("BadNext", "格 %s 回的 next 要是狀態名，不是 %r" % (phase, nxt))
        nxt = phase if nxt is None else nxt
        if nxt in states:
            to, give = nxt, None
        elif nxt in cfg["end"]:
            to, give = start, ret      # 交給外層：子 phase 歸位，ret 原樣吐成最後一份
        else:
            raise MethodsError("UnknownNext", "格 %s 回的 next %r 不在表裡也不在 end 裡" % (phase, nxt))
        out.update(phase=to, data=ret.get("data"), step=0 if to == start else step)
    except MethodsError as e:
        err = ("%s: %s" % (e.code, e.msg))[:ERR_LIMIT]
        give, line["error"], out["last_error"] = None, err, err
        out["fails"] = fails + 1                         # 連續出錯幾次；成功一次就歸零
        out["halted"] = out["fails"] >= cfg["max_fails"]  # 到 max_fails 就停住：之後的拍不起格，等人
        if "error" in states and phase != "error":       # 跳去 error 格，下一拍才跑；error 格自己出錯不再跳
            out.update(phase="error", step=0, data={"state": phase, "error": err, "data": data})
    line["to"], line["ms"] = out["phase"], round((time.monotonic() - t0) * 1000)
    _write(cfg, out)
    aos_cli.emit(line)
    if give is not None:
        aos_cli.emit(give)


def run(x, ident=None):
    """跟命令列一樣跑一拍：x＝FSM.json 的路徑（可接 `#/位置`）或一份設定 dict。fsm 自己出錯丟 `FsmError`。"""
    if isinstance(x, str):
        try:
            x, ident = aos_cli.load_target(x)
        except CliError as e:
            raise FsmError(e.code, e.msg)
    cfg = check_config(x, ident)
    lock = cfg["lock"]
    if lock:
        try:
            os.mkdir(lock)
        except FileExistsError:
            raise FsmError("LockBusy", "lock 窗 %s 已經有人拿著" % lock)
        except OSError as e:
            raise FsmError("LockFailed", "拿不了 lock 窗 %s：%s" % (lock, e))
    try:
        tick(cfg)
    finally:
        if lock:
            try:
                os.rmdir(lock)
            except OSError:
                pass


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        doc, ident, piped, rest = aos_cli.config(args, FLAGS)
        if rest is not None:
            raise FsmError("Usage", "aos_fsm 不收 --")
        run(doc, ident)
        return 0
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 125


if __name__ == "__main__":
    sys.exit(main())
