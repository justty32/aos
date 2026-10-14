#!/usr/bin/env python3
"""loop：包一個 inst，跑幾次、隔多久，一邊讀一個 ctl.json。純標準庫。

    python3 aos_loop.py LOOP.json

`run(path)` 跟命令列一模一樣，只收 loop.json 的路徑。路徑後面可以接 `#/位置`（同 aos_inst 的 TARGET）：
loop 本體是那份檔裡那一格（要是物件），裡面 `$ref` 的位置照整份檔算；id＝realpath ＋ `#` ＋ 位置。

loop.json（先用指示詞 lib 解，基準＝呼叫者的 cwd；外層的 key 只在起來時讀一次）：

    inst           一份 inst 格式（必填）；要指向現成的就寫 {"$ref": "job/inst.json"}
    times          總共跑幾次（非負整數；null＝不限；沒寫＝1）
    interval_ms    間隔（非負整數；沒寫＝0）
    interval_mode  "after"＝跑完再隔 interval_ms（預設）；"fixed"＝固定週期，每 interval_ms 到點起一次，
                   跑超過週期就跳過錯過的拍、對齊下一拍（不補跑、不重疊），跳過幾拍記在 state 的 skipped
    grace_ms       收掉正在跑的那次時，SIGTERM 之後等多久整群 SIGKILL（非負整數；沒寫＝5000；要比 inst 裡的 grace_ms 長）
    ctl            ctl.json 的路徑（選填；沒寫＝沒有控制，只能用訊號停）
    ctl_poll_ms    多久看一次 ctl.json（正整數；沒寫＝1000）
    state          state.json 的路徑（選填；狀態有變就整份寫過去）
    error_wait_ms  aos_inst 自己出錯的那次之後，下一次至少隔多久（非負整數；沒寫＝1000）

ctl、state 的相對路徑從呼叫者的 cwd 算。id＝loop.json 的 realpath（有 `#/位置` 就接在後面）。
loop.json（含 `inst` 那格和裡面的指示詞）只在起來時讀一次、解一次，之後每次都用記憶體裡那份；跑的途中要改只能走 ctl.json。
`inst` 不對（解不開、型別錯）＝起不來，退出碼沿用 aos_inst 的（參考 125）。

每一次：起子程序 `aos_inst.py`（自成一個 session）→ 等它結束 → 整群補 SIGKILL 清掉孫程式 → 收屍。
aos_inst 的退出碼只說它自己：0＝子程式跑完，`last_code` 讀 inst 的 exit 檔最後一行（沒寫 exit＝null）；
非 0＝aos_inst 自己出錯，`last_error`＝它 stderr 的最後一行。被收掉的那次也算跑過一次。
`inst` 交給 aos_inst 的方式：起來時把解好的 inst 寫成暫存資料夾裡的一份 inst.json，每次都把它的路徑給 aos_inst，結束時刪掉。

ctl.json（宣告式；NORMS N-06～N-08）：寫的是「我要它現在怎樣」，loop 只讀不寫，每 ctl_poll_ms 看一次，
每次讀整份、內容跟上次不同才重驗（不靠 mtime，4 ms 內的等長改動也看得到）。認的欄位（都選填；不認的忽略）：

    paused         true＝不再起新的一次；{"val": true, "now": true}＝當場收掉正在跑的那次
    stop           true＝不再起新的一次，正在跑的那次結束後 loop 結束；{"val": true, "now": true}＝當場收掉再結束。
                   stop 是終點：讀到一次就算數，改回 false 也不會復活
    times、interval_ms、interval_mode   蓋過 loop.json 外層的值

`true`＝`{"val": true, "now": false}`。兩個都寫了 stop 壓過 paused（收不收當場看 stop 的 now）。沒寫的欄位＝loop.json 的初始值（不是上一版 ctl 的值；集中在 `want()`）。
壞 JSON、不是物件、型別不對：整份不採用，維持上一次的好狀態，stderr 印一行（同一件事印一次）。
檔不見了：維持上一次的狀態、印一次；起來時就不在＝還沒有控制（之後出現了照樣讀）。

次數跑完（runs ≥ times）就結束、退出（有 ctl 也一樣）；想再跑就重新起。

state.json（選填；骨架跟 daemon 共用，見 lib README）：`id`、`state`（waiting／running／paused／done／stopping／stopped）、
`pid`、`runs`、`times`、`interval_ms`、`interval_mode`、`ctl_mtime`（上次套用的 ctl.json 的 mtime；沒有＝null）、`last_error`；
loop 自己多 `skipped`、`last_code`。
先寫 `.名字.tmp` 再改名；寫不了印一次、不算錯。

收到 SIGINT／SIGTERM／SIGHUP（只在主執行緒接）：收掉正在跑的那次（整群 SIGTERM，過 grace_ms 整群 SIGKILL）、不再起新的。

退出碼只說 loop 自己（數字只供參考）：
- 0＝正常結束（次數跑完、stop）；子程式回非 0 不算錯（在 exit 檔、last_code）。
- 看最後一次：最後一次是 aos_inst 自己出錯＝沿用 aos_inst 的退出碼；中途出錯後來好了不算。
- 被訊號停掉＝128＋訊號號碼；loop.json 本身不對、用法不對＝125。
`run()` 正常回 None，其餘丟 `LoopError`（`exit` 屬性＝上面的退出碼）。
"""
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

import aos_inst
from aos_directives import DirectiveError, locate, resolve, split_target, target_id
# ctl.json、state.json 在 aos_ctl_state，行程群組在 aos_proc；這裡 re-export，daemon 和既有的 import 照用
from aos_ctl_state import _MODES, STATES, CtlFile, StateFile, _int, parse_ctl, read_state, state_doc, want, write_json
from aos_proc import _exited, _killpg, kill, reap

__all__ = ["CtlFile", "LoopError", "STATES", "StateFile", "load_config", "parse_ctl", "read_state", "run", "state_doc",
           "want", "write_json"]

AOS_INST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_inst.py")
DEFAULTS = {"times": 1, "interval_ms": 0, "interval_mode": "after", "grace_ms": 5000, "ctl": None,
            "ctl_poll_ms": 1000, "state": None, "error_wait_ms": 1000}
_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class LoopError(Exception):
    """loop 自己出錯。`code`＝錯誤代號，`msg`＝白話，`exit`＝命令列退出碼，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg, exit=125):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg
        self.exit = exit


def _read_json(path, err=LoopError):
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise err("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise err("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))


def load_config(path, defaults=DEFAULTS, need_inst=True, err=LoopError):
    """讀 loop.json、整份解好（含 `inst` 那格），驗外層型別、填預設，回 (realpath, cfg)；cfg["inst"]＝解好的 inst。
    只在起來時讀這一次。daemon.json 也用這個（`defaults` 換成 daemon 的、`need_inst=False`）。
    `path` 可以接 `#/位置`：只讀那一格（整份檔的視窗），realpath 那格回的是 id（realpath ＋ `#` ＋ 位置）。"""
    try:
        file, pos = split_target(path)
    except DirectiveError as e:
        raise err(e.code, e.msg)
    real = os.path.realpath(file)
    ident = target_id(real, pos)
    root = _read_json(real, err)
    try:
        doc = locate(root, pos, real)
        if not isinstance(doc, dict):
            raise err("FieldType", "%s 要是物件" % ident)
        if need_inst and "inst" not in doc:
            raise err("FieldType", "%s 沒有 inst" % ident)
        outer = resolve(root, os.getcwd(), real, pos)
    except DirectiveError as e:
        raise err(e.code, e.msg)
    cfg = {"inst": outer.get("inst")} if need_inst else {}
    for k, default in defaults.items():
        v = outer.get(k, default)
        ok = {"times": v is None or _int(v), "interval_mode": v in _MODES, "ctl_poll_ms": _int(v, 1),
              "ctl": v is None or isinstance(v, str) and v, "state": v is None or isinstance(v, str) and v,
              "load": v is None or isinstance(v, str) and v, "save": v is None or isinstance(v, str) and v,
              "work_dir": v is None or isinstance(v, str) and v, "control_dir": isinstance(v, str) and v,
              }.get(k, _int(v))
        if not ok:
            raise err("FieldType", "%s 的 %s 值不對：%r" % (ident, k, v))
        cfg[k] = os.path.abspath(v) if isinstance(v, str) and k not in ("interval_mode",) else v
    return ident, cfg


# ---- 子程序（行程群組的 kill／reap 在 aos_proc）----

class _Tail:
    """把 aos_inst 的 stderr 原樣轉到自己的 stderr，記住最後一行。"""

    def __init__(self, pipe):
        self.last = None
        self.thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self.thread.start()

    def _read(self, pipe):
        for line in pipe:
            sys.stderr.write(line.decode("utf-8", "replace"))
            sys.stderr.flush()
            if line.strip():
                self.last = _err_line(line.decode("utf-8", "replace").strip())
        pipe.close()


def _err_line(line):
    """aos_inst 的 stderr 一行：`{"error": {"code", "msg"}}` → 「代號: 白話」；其他原樣。"""
    try:
        e = json.loads(line)["error"]
        return "%s: %s" % (e["code"], e["msg"])
    except (ValueError, KeyError, TypeError):
        return line


# ---- 主迴圈 ----

class _Loop:
    def __init__(self, path):
        self.id, self.cfg = load_config(path)
        c = self.cfg
        try:
            self.exit_path = aos_inst.parse(c["inst"], os.getcwd(), self.id)["exit"]
        except aos_inst.InstError as e:
            raise LoopError(e.code, e.msg, aos_inst.exit_code(e))
        self.initial = {"paused": (False, False), "stop": (False, False), "times": c["times"],
                        "interval_ms": c["interval_ms"], "interval_mode": c["interval_mode"]}
        self.ctl = CtlFile(c["ctl"]) if c["ctl"] else None
        self.runs = self.skipped = 0
        self.last_code = self.last_error = None
        self.inst_exit = 0          # 最後一次是 aos_inst 自己出錯＝它的退出碼，否則 0
        self.proc = self.tail = None
        self.stopping = False       # stop 讀到過一次就算數
        self.last_end = None        # 上一次結束的時間（monotonic）；None＝還沒跑過
        self.last_err = False
        self.anchor = None          # fixed：第 0 拍的時間
        self.tick = -1              # fixed：上一次起在第幾拍
        self.state_file = StateFile(c["state"], "loop")
        self.said = None

    def _say(self, msg):
        if self.said != msg:
            self.said = msg
            print("loop: %s" % msg, file=sys.stderr)

    def due(self, w):
        """下一次最早什麼時候起（monotonic）。"""
        if self.last_end is None:
            return -math.inf
        earliest = self.last_end + (self.cfg["error_wait_ms"] / 1000 if self.last_err else 0)
        iv = w["interval_ms"] / 1000
        if w["interval_mode"] == "after" or iv == 0 or self.anchor is None:
            return max(earliest, self.last_end + iv)
        n = max(self.tick + 1, math.ceil((earliest - self.anchor) / iv))
        return self.anchor + n * iv

    def start(self, w, now):
        if w["interval_mode"] == "fixed" and w["interval_ms"]:
            iv = w["interval_ms"] / 1000
            if self.anchor is None:
                self.anchor, n = now, 0
            else:
                n = max(self.tick + 1, math.floor((now - self.anchor) / iv))
                self.skipped += n - self.tick - 1
            self.tick = n
        else:
            self.anchor, self.tick = None, -1
        self.proc = subprocess.Popen([sys.executable, AOS_INST, self.wrapper],
                                     start_new_session=True, stderr=subprocess.PIPE)
        self.tail = _Tail(self.proc.stderr)

    def finish(self, rc):
        self.tail.thread.join(1)
        if rc == 0:
            code = None if self.exit_path is None else aos_inst.read_exit(self.exit_path)
            self.record(code, None, 0)
        elif rc > 0:
            self.record(None, self.tail.last or "aos_inst 退出碼 %d" % rc, rc)
        else:
            self.record(None, None, 0)      # aos_inst 被整群收掉了
        self.proc = self.tail = None

    def record(self, code, error, inst_exit):
        self.runs += 1
        self.last_code, self.last_error, self.inst_exit = code, error, inst_exit
        self.last_end, self.last_err = time.monotonic(), error is not None

    def status(self, w, final=None):
        if final:
            state = final
        elif self.stopping:
            state = "stopping"
        elif self.proc:
            state = "running"
        elif w["paused"][0]:
            state = "paused"
        elif w["times"] is not None and self.runs >= w["times"]:
            state = "done"
        else:
            state = "waiting"
        return state_doc(self.id, state, w, self.ctl, self.runs, self.last_error, skipped=self.skipped,
                         last_code=self.last_code)

    def write_state(self, st):
        self.state_file.write(st)

    def serve(self, got):
        c = self.cfg
        next_poll = 0
        final = None
        while True:
            now = time.monotonic()
            if self.ctl and now >= next_poll:
                self.ctl.poll()
                next_poll = now + c["ctl_poll_ms"] / 1000
            w = want(self.initial, self.ctl.good if self.ctl else {})
            if w["stop"][0]:
                self.stopping = True
            if got:
                if self.proc:
                    self.finish(kill(self.proc, c["grace_ms"]))
                final = "stopped"
                break
            if self.proc:
                if _exited(self.proc.pid, 0):
                    self.finish(reap(self.proc))
                elif w["stop"][1] if self.stopping else w["paused"][0] and w["paused"][1]:   # stop 壓過 paused
                    self.finish(kill(self.proc, c["grace_ms"]))
            if not self.proc:
                done = w["times"] is not None and self.runs >= w["times"]
                if self.stopping:
                    final = "stopped"
                    break
                if done:
                    final = "done"
                    break
                if not w["paused"][0] and not done and now >= self.due(w):
                    self.start(w, now)
            self.write_state(self.status(w))
            time.sleep(0.01 if self.proc else 0.02)
        self.write_state(self.status(w, final))

    def run(self):
        main = threading.current_thread() is threading.main_thread()
        got = []
        old = {s: signal.signal(s, lambda signum, frame: got.append(signum)) for s in _CAUGHT} if main else {}
        tmp = tempfile.mkdtemp(prefix="aos-loop-")
        self.wrapper = os.path.join(tmp, "inst.json")
        try:
            write_json(self.wrapper, self.cfg["inst"])      # 起來時解好的那份，每次都用它
            self.serve(got)
        finally:
            if self.proc:
                kill(self.proc, self.cfg["grace_ms"])
            shutil.rmtree(tmp, ignore_errors=True)
            for s, h in old.items():
                signal.signal(s, h)
        if got:
            raise LoopError("Signaled", "收到訊號 %d" % got[0], 128 + got[0])
        if self.inst_exit:
            code = (self.last_error or "InstError").split(":")[0]
            raise LoopError(code, "最後一次 aos_inst 自己出錯：%s" % self.last_error, self.inst_exit)


def run(path):
    """跟命令列 `aos_loop.py LOOP.json` 一模一樣。正常結束回 None；loop 自己出錯丟 `LoopError`。"""
    _Loop(path).run()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：aos_loop.py LOOP.json", file=sys.stderr)
        return 125
    try:
        run(args[0])
        return 0
    except LoopError as e:
        if e.code not in ("Signaled",) and not e.msg.startswith("最後一次"):
            print(e, file=sys.stderr)
        return e.exit


if __name__ == "__main__":
    sys.exit(main())
