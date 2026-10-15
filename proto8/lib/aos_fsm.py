#!/usr/bin/env python3
"""fsm：一拍跑一格的狀態機。讀回現在狀態、查表跑那一格、換狀態、寫 state 窗、退出。純標準庫。
照 NORMS N-20、N-36～N-41 的基礎實作（10-15 收工後瘦身：fsm 只管「現在是 A 狀態就跑 A 那格」）；說明在同資料夾的 fsm.md。

    python3 aos_fsm.py [--key 值 ...] [FSM.json | -]

設定從哪來照 aos_cli：FSM.json（可接 `#/位置`）、`-`＝stdin；純量 key 有同名旗標（`--start`、`--state`），
`states`、`end` 不鏡射；`--` 不收。`run(x, ident=None, base=None)` 收路徑或一份設定 dict，回這拍的退出碼。

    start   起始狀態名（必填，要在 states 裡）
    states  狀態名 → 格（必填；格的寫法見 aos_methods）。字串格的相對路徑從 FSM.json 所在的資料夾算
            （設定從 stdin／dict 來＝從 cwd 算，N-36）
    end     選填，名字的陣列（可以在表裡、也可以不在，N-40）
    state   state 窗（必填，N-19；缺 key 或 null＝WindowMissing、不執行）

不認得的 key 一律忽略（C-48；舊設定的 ctl、lock、max_steps、max_fails 也是）。

一拍：讀 state（檔還沒有＝從 start 起）→ 查格 → 跑格（stdin 照那張 inst 自己寫的，fsm 不碰；stdout 另外接一份來看 next）
→ 換狀態 → 寫 state → stdout 吐一行。
下一狀態：格 stdout 最後一份完整 JSON 的 `next` ＞ 表上靜態 next ＞ 留原狀態。結束（N-40）：剛跑的狀態在 `end` 裡，
或回的 next 不在表裡、在 `end` 裡＝這個 fsm 結束：那格的結果原樣吐成這拍 stdout 最後一份、phase 歸位 `start`。
出錯（N-38）：格結束碼非 0、吐了東西但沒有完整 JSON 物件、沒輸出又沒寫表上 next、查不到格、next 不在表裡也不在 end
＝phase 不動、這拍那行多 `error`、退出碼 1。格結束碼 0、stdout 什麼都沒吐、表上有 next＝照表上 next 走（10-15 使用者）。

state 窗：`{"phase"}`，只有 fsm 自己寫；不寫時間、pid（N-39）。
stdout：起了格（或查格就出錯）吐一行＝那格的 aos_inst 結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、
`exit_file`；沒起成格的是 null）＋`from`、`to`（出錯多 `error`: {code, msg}，msg 帶格 stderr 最後一份 N-29 錯誤；
結束那拍多 `"end": true`，拍它的 aos-loop 寫了 `stop_on_end` 就看它停）；
這行永遠不帶 `next`。
退出碼（N-43 只認 0／非 0）：0＝這拍正常；1＝格出錯；125＝fsm 自己出錯（設定不對、窗缺、state 讀寫不了）。
"""
import os
import sys
import time

import aos_cli
import aos_methods
from aos_cli import CliError
from aos_ctl_state import read_state, require, write_json
from aos_methods import MethodsError

__all__ = ["CELL_FAILED", "FLAGS", "FsmError", "base_of", "check_config", "main", "run"]

FLAGS = ("start", "state")
CELL_FAILED = 1                # 格出錯時的退出碼
ERR_LIMIT = 300                # error.msg 最多幾個字


class FsmError(CliError):
    """fsm 自己出錯（退出碼 125）。"""


def check_config(doc, ident=None, base=None):
    """驗設定、路徑轉成絕對的，回 cfg dict。base＝格的相對路徑從哪算（設定檔所在的資料夾；None＝cwd）。"""
    require(doc, ("state",), FsmError)
    try:
        start, states, end = aos_methods.check_table(doc, ident or "<stdin>")
    except MethodsError as e:
        raise FsmError(e.code, e.msg)
    v = doc.get("state")
    if not (isinstance(v, str) and v):
        raise FsmError("FieldType", "state 要是路徑字串，不是 %r" % (v,))
    return {"id": ident, "start": start, "states": states, "end": end, "state": os.path.abspath(v), "base": base}


def _read(cfg):
    """讀回現在狀態；檔還沒有＝start（N-36）。檔在但讀不懂＝StateBad。"""
    if not os.path.exists(cfg["state"]):
        return cfg["start"]
    st = read_state(cfg["state"])
    if st is None or not isinstance(st.get("phase"), str):
        raise FsmError("StateBad", "state 窗 %s 讀不懂（要有字串 phase）" % cfg["state"])
    return st["phase"]


def _write(cfg, phase):
    try:
        write_json(cfg["state"], {"phase": phase})
    except OSError as e:
        raise FsmError("StateWriteFailed", "寫不了 state 窗 %s：%s" % (cfg["state"], e))


def tick(cfg):
    """跑一拍，回退出碼（0 或 CELL_FAILED）。"""
    start, states, end = cfg["start"], cfg["states"], cfg["end"]
    phase = _read(cfg)
    to, give, err, ended = phase, None, None, False
    line = {"id": None, "code": None, "signal": None, "timed_out": False, "pid": None, "ms": None, "exit_file": None}
    t0 = time.monotonic()
    try:
        inst, inst_id, static = aos_methods.cell(states, phase, cfg["id"], cfg["base"])
        result, ret = aos_methods.run_cell(inst, inst_id)
        line.update({k: v for k, v in result.items() if k not in ("cell_error", "cell_empty")})
        if result["code"] != 0:
            ce = result.get("cell_error")       # 格自己 stderr 的 N-29 錯誤＝真正原因
            raise MethodsError("CellFailed", "%s: %s" % (ce["code"], ce["msg"]) if ce
                               else "格 %s 結束碼 %d" % (phase, result["code"]))
        if not isinstance(ret, dict):
            if not result.get("cell_empty"):
                raise MethodsError("NoResult", "格 %s 沒吐完整的 JSON 物件（N-12：半份不算）" % phase)
            if static is None:
                raise MethodsError("NoResult", "格 %s 沒輸出，表上也沒寫 next" % phase)
            ret = None                          # 沒輸出、表上有 next＝照表上走（N-38）
        nxt = ret["next"] if ret is not None and "next" in ret else static
        if not (nxt is None or isinstance(nxt, str)):
            raise MethodsError("BadNext", "格 %s 回的 next 要是狀態名，不是 %r" % (phase, nxt))
        nxt = phase if nxt is None else nxt
        if phase in end or (nxt not in states and nxt in end):
            to, give, ended = start, ret, True     # 結束（N-40 b、c）：phase 歸位，那格的結果原樣交出去（沒輸出＝不吐）
        elif nxt in states:
            to = nxt
        else:
            raise MethodsError("UnknownNext", "格 %s 回的 next %r 不在表裡也不在 end 裡" % (phase, nxt))
    except MethodsError as e:
        err = {"code": e.code, "msg": e.msg[:ERR_LIMIT]}           # phase 不動（N-38）
    if line["ms"] is None:
        line["ms"] = round((time.monotonic() - t0) * 1000)
    line.update({"from": phase, "to": to})
    if ended:
        line["end"] = True             # 結束那拍的那行（拍它的 loop 寫了 stop_on_end 就看這個停）
    if err:
        line["error"] = err
    _write(cfg, to)
    aos_cli.emit(line)
    if give is not None:
        aos_cli.emit(give)
    return CELL_FAILED if err else 0


def base_of(target):
    """TARGET（`檔#/位置`）→ 那份檔所在資料夾的絕對路徑（格的相對路徑從這裡算，N-36）。"""
    return os.path.dirname(os.path.realpath(target.split("#", 1)[0]))


def run(x, ident=None, base=None):
    """跟命令列一樣跑一拍：x＝FSM.json 的路徑（可接 `#/位置`）或一份設定 dict（格的相對路徑從 base 算，None＝cwd）。
    回退出碼（0 或 CELL_FAILED）；fsm 自己出錯丟 `FsmError`。"""
    if isinstance(x, str):
        base = base_of(x)
        try:
            x, ident = aos_cli.load_target(x)
        except CliError as e:
            raise FsmError(e.code, e.msg)
    return tick(check_config(x, ident, base))


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        doc, ident, piped, rest = aos_cli.config(args, FLAGS)
        if rest is not None:
            raise FsmError("Usage", "aos_fsm 不收 --")
        target = aos_cli.parse_argv(args, FLAGS)[0]
        return run(doc, ident, None if piped or target is None else base_of(target))
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 125


if __name__ == "__main__":
    sys.exit(main())
