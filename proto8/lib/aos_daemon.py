#!/usr/bin/env python3
"""daemon：一個 loop（同一個拍引擎），每拍多做「收屍、掃控制資料夾、套策略格」，同時顧著一群長壽的子 loop。純標準庫。
照 NORMS N-12 重做、候選 g 拍板（10-14）：daemon.json＝loop.json 的超集，一份合法的 loop.json 丟給 aos-daemon 也能跑。

    python3 aos_daemon.py [--key 值 ...] [DAEMON.json | -]

設定從哪來照 aos_cli（同 aos_loop）：DAEMON.json（可接 `#/位置`）、`-`＝stdin、外層純量 key 有同名旗標；`--` 不收。
`run(x)` 跟命令列一樣，x＝路徑或一份設定 dict。

daemon.json（先用指示詞 lib 解，基準＝daemon 啟動時的 cwd；只在起來時讀一次）。跟 loop.json 同名的 key 同義：

    inst           daemon 自己每拍跑一次的身體（選填；跑法同 loop：阻塞到它結束，記 last_code／last_error）
    ctl、state     自己的 ctl 窗、state 窗（必填，N-19）；ctl 不能放在 control_dir 裡
    times          跑幾拍就收工（非負整數；null＝不限，預設——跟 loop 的預設 1 不同）
    interval_ms    每拍隔多久（非負整數；沒寫＝200）
    interval_mode、ctl_poll_ms、error_wait_ms、id   同 loop
    grace_ms       收工時等底下的 loop 多久，過了整群 SIGKILL（非負整數；沒寫＝10000）
  daemon 多的：
    children       初始表（陣列）：每項＝一個 aos-loop 設定的 TARGET（路徑、`檔#/位置`，或內嵌物件）；起來時等同逐個 add
    policies       {"child_exit": inst TARGET}：子項結束時問它怎麼辦（見下）；沒設＝leave
    control_dir    控制資料夾（選填；沒給＝不掃資料夾，N-13）
    table          table 窗的路徑（選填）：子項六態的表，有變就整份寫；也是存檔
    load           true＝起來時讀 table 窗接回（預設 false）
    work_dir       每個子項一格 `work_dir/N/`（選填；沒寫＝state 窗旁邊的 loops/）

每拍：收屍（每圈都做）→ 掃控制資料夾 → 跑 inst（有的話）。runs＝拍數。paused＝不拍（指令堆著、子項照跑）；
stop＝收工（now＝子項當場收掉；沒 now＝替它們寫 stop、等它們跑完）；times 跑完同 stop（不帶 now）。

子項：一支子程序 `aos_loop.py -`（自成 session），設定從 stdin 灌進去（`id`＝原 TARGET 的 id）。loop 設定沒寫 ctl／state 的，
放在 `work_dir/N/ctl.json`、`state.json`；子 loop 的 stdout 丟掉（結果從 state 窗讀）、stderr 落 `work_dir/N/err.json`（只在出錯時長）。
daemon 只靠兩個窗控制它：寫它的 ctl（帶流水號 seq）、讀它的 state（ctl_seq 趕上＝讀到了）。
子項六態 phase：starting／running／exited／backoff／stopping／removed，寫在 table 窗（先寫表、再 Popen）。
子項結束（不是 remove、不是收工）：有 `policies.child_exit` 就跑那格 inst，stdin＝{id, code, exits, last_state}，
stdout 最後一份＝{action: restart|leave|remove, after_ms}；restart＝退避 after_ms 再起。exits ≥ 5 強制 leave。
`load: true`：讀 table 窗，pid＋啟動時間（/proc）對得上的認領、不重起；對不上的當 exited 走策略格；backoff 的馬上重起。
收工時表留著（work_dir/N 也留著，給下次接回）；remove 才刪那格。

指令（N-10）：往控制資料夾放 `名字.json`，處理完變 `名字.json.done`，內容一問一答
`{"request", "ok", "result"|"error": {"code", "msg"}}`；`.` 開頭不讀；`.done` 由丟的人清。指令一律 {"op", "id", ...}，
id＝loop.json（或 inst.json）的絕對路徑，可接 `#/位置`：

    add        起一個（inst.json：頂層沒有 inst、有 argv 的，包成只跑一次的 loop）     → result＝id
    set        {"how": {times／interval_ms／interval_mode}}               → 改完的狀態物件
    pause      {"wait": B}（預設 true；false＝當場收掉）                    → 狀態物件（等真的停了）
    resume、add_times {"delta": N}                                          → 狀態物件
    remove     {"wait": B}  停掉、等行程結束、從表上拿掉、刪 work_dir/N     → 最後的狀態物件
    state      → 狀態字串；get → 狀態物件（它的 state 窗＋phase）；list → [狀態物件, ...]

set／pause／resume／add_times 等 loop 讀到了才回；等的期間指令檔留在原地。
error.code（只供參考）：BadCommand、UnknownOp、FieldType、NotFound、Exists、Conflict、ReadFailed、JsonSyntax、WriteFailed、Internal。

stdout 同 loop：跑了 inst 的拍一份 {run, code, ms}（沒 inst＝不吐）、結束一份總結。state 窗：共同骨架加 skipped、last_code、loops（表上幾個）；
last_error＝inst 自己出錯那行，沒有就是最近一圈掃資料夾的錯（ScanFailed、ReplyFailed），都沒有＝null。
跑起來之後出意外（PolicyFailed、RestartFailed、TableWriteFailed、收工時寫不了子項 ctl 的 WriteFailed）不結束、不寫 stderr，
記在 state 窗的 last_warning（「代號: 白話」，最近一件；ctl 窗壞檔的優先）；子 loop 自己的 stderr 落 work_dir/N/err.json，不轉上來
（C-52；10-15 使用者「都按照推薦。」）。退出碼只說 daemon 自己、不沿用下層的碼：0＝正常收工（含收到 SIGTERM／SIGINT：這是 daemon 照設計的收工路，哪個訊號記在 state 窗與結束那份的 `signal`）；
1＝起不來、state 窗寫不了、最後一拍 inst 自己出錯（stderr 一份錯誤，同 loop）。
"""
import os
import sys

import aos_cli
from aos_cli import CliError
from aos_loop import DEFAULTS as _LOOP, Loop, LoopError, check_config
# 表在 aos_daemon_table，指令與控制資料夾在 aos_daemon_folder；這裡 re-export
from aos_daemon_folder import _Folder, handle
from aos_daemon_table import AOS_LOOP, DaemonError, Table

__all__ = ["Daemon", "DaemonError", "handle", "load_config", "run"]

DEFAULTS = dict(_LOOP, times=None, interval_ms=200, grace_ms=10000, control_dir=None, work_dir=None, table=None,
                load=False, children=[], policies={})


def check(ident, doc):
    """驗 daemon.json（解好的），回 (id, cfg)。"""
    ident, cfg = check_config(ident, doc, DEFAULTS, need_inst=False, err=DaemonError)
    if cfg["work_dir"] is None and cfg["state"]:
        cfg["work_dir"] = os.path.join(os.path.dirname(cfg["state"]), "loops")
    d = cfg["control_dir"]
    if d and cfg["ctl"] and os.path.commonpath([cfg["ctl"], d]) == d:
        raise DaemonError("Conflict", "ctl %s 不能放在 control_dir 裡（會被當成指令讀）" % cfg["ctl"])
    if not (cfg["policies"].get("child_exit") is None or isinstance(cfg["policies"]["child_exit"], (str, dict))):
        raise DaemonError("FieldType", "policies.child_exit 要是 inst TARGET")
    if cfg["load"] and not cfg["table"]:
        raise DaemonError("FieldType", "load: true 要有 table 窗")
    return ident, cfg


def load_config(path):
    """讀 daemon.json，回 (id, 填好預設值的 dict)。"""
    try:
        doc, ident = aos_cli.load_target(path)
    except CliError as e:
        raise DaemonError(e.code, e.msg)
    return check(ident, doc)


class Daemon(Loop):
    name = "daemon"

    def __init__(self, ident, cfg):
        super().__init__(ident, cfg)
        self.table = Table(cfg, ident)
        self.folder = None
        if cfg["control_dir"]:
            try:
                os.makedirs(cfg["control_dir"], exist_ok=True)
            except OSError as e:
                raise DaemonError("MkdirFailed", "建不了控制資料夾：%s" % e)
            self.folder = _Folder(cfg["control_dir"])

    def start_table(self):
        """接回 table 窗、起 children（失敗＝起不來；已經起的收掉）。"""
        try:
            if self.cfg["load"]:
                self.table.load()
            for i, t in enumerate(self.cfg["children"]):
                if isinstance(t, str) and not os.path.isabs(t):
                    t = os.path.abspath(t)
                if isinstance(t, dict) or self.table._config(t, i)[0] not in self.table.entries:
                    self.table.add(t, i)
        except BaseException:
            self.table.shutdown(True, self.cfg["grace_ms"], [])
            raise

    def beat(self, w, now):
        if self.folder:
            self.folder.scan(self.table)
        super().beat(w, now)

    def idle(self, w):
        self.table.tick()
        if self.folder:
            self.folder.flush()

    def extra(self):
        return {"skipped": self.skipped, "last_code": self.last_code, "loops": len(self.table.entries)}

    def error_now(self):
        return self.last_error or (self.folder.last_error if self.folder else None)

    def warning_now(self):
        return self.ctl.warning or self.table.warning

    def finish_up(self, final, now, got):
        self.table.shutdown(now, self.cfg["grace_ms"], got)
        if self.folder:
            self.folder.flush()

    def run(self):
        self.start_table()
        try:
            super().run()
        except LoopError as e:
            if e.code != "Signaled":
                raise


def run(x):
    """跟命令列一樣：x＝DAEMON.json 的路徑或一份設定 dict。正常收工回 None；起不來丟 DaemonError／LoopError。"""
    Daemon(*(check(None, x) if isinstance(x, dict) else load_config(x))).run()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        doc, ident, piped, rest = aos_cli.config(args, tuple(k for k in DEFAULTS if k not in ("children", "policies")))
        if rest is not None:
            raise DaemonError("Usage", "aos_daemon 不收 --")
        Daemon(*check(ident, doc)).run()
        return 0
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
