#!/usr/bin/env python3
"""loop：包一個 inst，跑幾次、隔多久，一邊讀 ctl 窗、寫 state 窗。純標準庫。

    python3 aos_loop.py [--key 值 ...] [LOOP.json | -]

設定從哪來照 aos_cli：LOOP.json（可接 `#/位置`）、`-`＝stdin、外層純量 key 都有同名旗標（`--times 3`、`--ctl c.json`…），
蓋過檔或 stdin；`inst` 是物件、不鏡射。`--` 不收。`run(x)` 跟命令列一樣，x＝路徑或一份設定 dict。

loop.json（先解指示詞，基準＝呼叫者的 cwd；只在起來時讀一次）：

    inst           一份 inst 格式（必填）；要指向現成的就寫 {"$ref": "job/inst.json"}
    ctl            ctl 窗的路徑（必填，N-19；缺 key 或 null＝WindowMissing、不執行）
    state          state 窗的路徑（必填，同上）
    times          總共跑幾次（非負整數；null＝不限；沒寫＝1）
    interval_ms    跑完隔多久再起下一次（非負整數；沒寫＝0）
    stop_on_end    true＝包的是 aos-fsm（或照它的寫法）時，這次 stdout 裡有 fsm 結束那拍的那行（帶 `"end": true`、`from`、`to`，
                   N-40）就不再起新的一次、loop 正常結束（end＝"done"）；inst 寫了 stdout 檔就讀這次寫進去的那段，沒寫
                   ＝loop 每次替它接一個暫存檔、讀完刪掉。沒寫＝false
    id             選填字串，state 的 id（沒寫＝LOOP.json 的 realpath（有 `#/位置` 就接上）；從 stdin 來又沒寫＝null）

ctl、state 的相對路徑從呼叫者的 cwd 算。ctl 窗起來時不在沒關係（還沒有控制，之後出現了照樣讀）。
`inst` 不對（解不開、型別錯）＝起不來，stderr 一份錯誤（代號照 aos_inst 的）、退出 1。

每一次：起子程序 `aos_inst.py -`（自成一個 session），解好的 inst 從 stdin 灌進去 → 等它結束 → 整群補 SIGKILL 清孫程式 → 收屍。
aos_inst 的退出碼只說它自己：0＝子程式跑完，`last_code`＝它 stdout 那份結果的 code；
非 0＝aos_inst 自己出錯，`last_error`＝它 stderr 最後一份錯誤（「代號: 白話」）。被收掉的那次也算跑過一次。
aos_inst 的 stderr 不轉到 loop 自己的 stderr（C-52 只管自己這一層），只記在 state 窗的 last_error。
收掉正在跑的那次＝對它整群送 SIGTERM、等它自己結束（aos_inst 保證過它的 grace_ms 會收掉子程式）。

stdout（N-12，JSON 串流）：每一次一份 {"run": 第幾次, "code": last_code, "ms": 跑了幾毫秒}，結束時一份
{"end": "done"|"stopped", "runs", "last_code", "signal"}（signal＝被哪個訊號停掉，沒有＝null）。stderr：只有 loop 自己的錯誤（N-29 JSON），沒有警告。

ctl 窗（宣告式；NORMS N-06～N-08）：寫的是「我要它現在怎樣」，loop 只讀不寫，每圈看一次（讀整份、內容跟上次不同才重驗）。
認的欄位（都選填；不認的忽略）：

    paused         true＝不再起新的一次（正在跑的那次跑完）
    stop           true＝不再起新的一次，正在跑的那次結束後 loop 結束。stop 是終點：讀到一次就算數，改回 false 也不會復活
    times、interval_ms   蓋過 loop.json 外層的值
    seq            流水號（非負整數），state 的 ctl_seq 回報上次採用的那份

要當場收掉正在跑的那次＝對 loop 送 SIGTERM（見下）。兩個都寫了 stop 壓過 paused。沒寫的欄位＝loop.json 的初始值（集中在 `want()`）。
壞 JSON、不是物件、型別不對：整份不採用，維持上一次的好狀態，原因記在 state 窗的 last_warning（不寫 stderr，N-08）。
檔不見了：維持上一次、同樣記 last_warning。之後讀到好的那份就清回 null。

次數跑完（runs ≥ times）就結束、退出（有 ctl 也一樣）；想再跑就重新起。

state 窗（骨架跟 daemon 共用，見 lib ctl_state.md）：`id`、`state`（waiting／running／paused／done／stopping／stopped）、
`pid`、`started`、`boot_id`、`runs`、`times`、`interval_ms`、`last_error`、`ctl_seq`、`beat`；
loop 自己多 `last_code`、`last_warning`。內容沒變也每秒碰一次（心跳）。先寫 `.名字.tmp` 再改名；
寫不了＝窗壞了（同 N-19 窗缺）：收掉正在跑的那次、結束，stderr 一份 StateWriteFailed、退出 1。

收到 SIGINT／SIGTERM／SIGHUP（只在主執行緒接）：收掉正在跑的那次（整群 SIGTERM、等它結束）、不再起新的；
哪個訊號記在 state 窗的 `signal` 與結束那份的 `signal`。

退出碼只說 loop 自己，不沿用下層的碼（C-52）：
- 0＝正常結束（次數跑完、stop）；子程式回非 0 不算錯（在 last_code）。
- 1＝有錯：設定不對、用法不對、state 窗寫不了、或最後一次是 aos_inst 自己出錯（stderr 一份錯誤，代號＝last_error 的代號；
  細節在 state 窗 last_error）；中途出錯後來好了不算。
- 被訊號停掉＝1（不寫 stderr；哪個訊號在 state 窗與結束那份的 `signal`）。
`run()` 正常回 None，其餘丟 `LoopError`（`exit` 屬性＝上面的退出碼）。

給 daemon 重用的拍引擎：`Loop` 類別的 `beat()`（到點時做什麼）、`idle()`（每一圈都做）、`extra()`（state 多的欄位）、
`finish_up()`（結束前）四個掛鉤。
"""
import json
import math
import os
import signal
import subprocess
import sys
import threading
import tempfile
import time

import aos_cli
import aos_inst
from aos_cli import CliError
from aos_ctl_state import CtlFile, StateFile, _int, require, state_doc, want
from aos_proc import _exited, reap, stop

__all__ = ["Loop", "LoopError", "check_config", "load_config", "run"]

AOS_INST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos_inst.py")
DEFAULTS = {"id": None, "times": 1, "interval_ms": 0, "ctl": None, "state": None, "stop_on_end": False}
_CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
_PATHS = ("ctl", "state", "table", "work_dir", "ctl_dir")


class LoopError(CliError):
    """loop 自己出錯。`code`＝錯誤代號，`msg`＝白話，`exit`＝命令列退出碼，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg, exit=1):
        super().__init__(code, msg)
        self.exit = exit


def _ok(k, v):
    if k in _PATHS:
        return v is None or isinstance(v, str) and v
    return {"id": v is None or isinstance(v, str), "times": v is None or _int(v),
            "load": isinstance(v, bool), "stop_on_end": isinstance(v, bool), "children": isinstance(v, list),
            "policies": isinstance(v, dict)}.get(k, _int(v))


def check_config(ident, doc, defaults=DEFAULTS, need_inst=True, err=LoopError):
    """驗解好的設定（外層型別、填預設），回 (id, cfg)；cfg["inst"]＝解好的 inst（沒寫＝None）。
    id＝設定的 `id` ＞ 給的 ident。daemon.json 也用這個（`defaults` 換成 daemon 的、`need_inst=False`）。"""
    if need_inst and "inst" not in doc:
        raise err("FieldType", "%s 沒有 inst" % ident)
    cfg = {"inst": doc.get("inst")}
    for k, default in defaults.items():
        v = doc.get(k, default)
        if not _ok(k, v):
            raise err("FieldType", "%s 的 %s 值不對：%r" % (ident, k, v))
        cfg[k] = os.path.abspath(v) if k in _PATHS and v else v
    return (cfg.get("id") or ident), cfg


def load_config(path, defaults=DEFAULTS, need_inst=True, err=LoopError):
    """讀 TARGET（可接 `#/位置`）、整份解好，交給 `check_config()`。只在起來時讀這一次。"""
    try:
        doc, ident = aos_cli.load_target(path)
    except CliError as e:
        raise err(e.code, e.msg)
    return check_config(ident, doc, defaults, need_inst, err)


# ---- 子程序（行程群組的 stop／reap 在 aos_proc）----

class _Tail:
    """讀一條管子到底，記住最後一行非空的（不轉到自己的 stderr：下層的錯只記進 state 窗，C-52）。"""

    def __init__(self, pipe):
        self.last = None
        self.thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self.thread.start()

    def _read(self, pipe):
        for line in pipe:
            text = line.decode("utf-8", "replace")
            if text.strip():
                self.last = text.strip()
        pipe.close()


def _json(line):
    try:
        v = json.loads(line or "")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def _err_line(line):
    """aos_inst 的 stderr 一行：`{"error": {"code", "msg"}}` → 「代號: 白話」；其他原樣。"""
    e = _json(line).get("error")
    return "%s: %s" % (e.get("code"), e.get("msg")) if isinstance(e, dict) else line


# ---- 拍引擎 ----

class Loop:
    """一個會反覆跑的東西：讀 ctl 窗、寫 state 窗、照節奏每拍做 `beat()`。loop 每拍＝跑一次 inst；daemon 重用它。"""
    name = "loop"

    def __init__(self, ident, cfg):
        self.id, self.cfg = ident, cfg
        require(cfg, ("ctl", "state"), LoopError)
        self.inst = None
        if cfg["inst"] is not None:
            try:
                aos_inst.parse(cfg["inst"], os.getcwd(), ident or "<stdin>")
            except aos_inst.InstError as e:
                raise LoopError(e.code, e.msg)
            self.inst = json.dumps(cfg["inst"]).encode("utf-8")
        self.initial = {"paused": False, "stop": False, "times": cfg["times"], "interval_ms": cfg["interval_ms"]}
        self.ctl = CtlFile(cfg["ctl"], self.name)
        self.state_file = StateFile(cfg["state"], self.name)
        self.runs = 0
        self.last_code = self.last_error = None
        self.inst_exit = 0          # 最後一次是 aos_inst 自己出錯＝它的退出碼（只用來判斷有沒有錯，不往上傳），否則 0
        self.proc = None
        self.signal = None          # 被哪個訊號停掉（state 窗、結束那份的 signal）
        self.stopping = False       # stop 讀到過一次就算數
        self.ended = False          # stop_on_end：包的 fsm 走到 end 了
        self.watch = None           # stop_on_end：(這次 stdout 的檔, 從哪讀起, 是不是自己接的暫存檔)
        self.last_end = None        # 上一次結束的時間（monotonic）；None＝還沒跑過

    # ---- 掛鉤（daemon 覆寫）----

    def beat(self, w, now):
        """到點了：起 inst；沒有 inst 就當這拍跑完了。"""
        if self.inst is None:
            self.t0 = now
            self.record(None, None, 0)
        else:
            self.start_inst(now)

    def idle(self, w):
        """每一圈都做（daemon：收屍、處理指令）。"""

    def extra(self):
        return {"last_code": self.last_code}

    def error_now(self):
        """state 的 last_error。"""
        return self.last_error

    def warning_now(self):
        """state 的 last_warning（daemon 再加表與子項的）。"""
        return self.ctl.warning

    def finish_up(self, final, now, got):
        """結束前（daemon：存檔、收子項）。final＝"done"／"stopped"，now＝要不要當場收。"""

    # ---- 身體 ----

    def _payload(self):
        """這次灌給 aos_inst 的 inst；stop_on_end 時順便記下要讀哪個 stdout（沒寫檔＝接暫存檔）。"""
        if not self.cfg.get("stop_on_end"):
            return self.inst
        inst = self.cfg["inst"]
        out = inst.get("stdout")
        if isinstance(out, str) and out:
            base = os.path.abspath(inst["cwd"]) if isinstance(inst.get("cwd"), str) else os.getcwd()
            path = os.path.join(base, out)
            try:
                off = os.path.getsize(path) if inst.get("stdout_append") else 0
            except OSError:
                off = 0
            self.watch = (path, off, False)
            return self.inst
        fd, path = tempfile.mkstemp(prefix="aos-loop-", suffix=".out")
        os.close(fd)
        self.watch = (path, 0, True)
        doc = dict(inst, stdout=path, stdout_append=False, stdout_mkdir=False)
        return json.dumps(doc).encode("utf-8")

    def _saw_end(self):
        """這次 stdout 裡有沒有 fsm 結束那行（{"from", "to", "end": true}）；暫存檔讀完刪掉。"""
        path, off, mine = self.watch
        self.watch = None
        try:
            with open(path, "rb") as f:
                f.seek(off)
                text = f.read().decode("utf-8", "replace")
        except OSError:
            text = ""
        finally:
            if mine:
                try:
                    os.remove(path)
                except OSError:
                    pass
        return any(isinstance(d, dict) and d.get("end") is True and "from" in d and "to" in d
                   for d in aos_cli.read_stream(text))

    def start_inst(self, now):
        self.t0 = now
        payload = self._payload()
        self.proc = subprocess.Popen([sys.executable, AOS_INST, "-"], start_new_session=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.out, self.err = _Tail(self.proc.stdout), _Tail(self.proc.stderr)
        try:
            self.proc.stdin.write(payload)
            self.proc.stdin.close()
        except OSError:
            pass        # aos_inst 先死了：照它的退出碼算

    def finish(self, rc):
        self.out.thread.join(1)
        self.err.thread.join(1)
        if self.watch is not None and self._saw_end():
            self.ended = True
        if rc == 0:
            self.record(_json(self.out.last).get("code"), None, 0)
        elif rc > 0:
            self.record(None, _err_line(self.err.last) or "aos_inst 退出碼 %d" % rc, rc)
        else:
            self.record(None, None, 0)      # aos_inst 被整群收掉了
        self.proc = None

    def record(self, code, error, inst_exit):
        self.runs += 1
        self.last_code, self.last_error, self.inst_exit = code, error, inst_exit
        self.last_end = time.monotonic()
        if self.inst is not None:       # 每拍那份只在真的跑了 inst 時吐（daemon 沒 inst＝只吐結束總結）
            aos_cli.emit({"run": self.runs, "code": code, "ms": round((self.last_end - self.t0) * 1000)})

    # ---- 節奏 ----

    def due(self, w):
        """下一次最早什麼時候起（monotonic）：上一次結束再隔 interval_ms。"""
        return -math.inf if self.last_end is None else self.last_end + w["interval_ms"] / 1000

    def status(self, w, final=None):
        if final:
            state = final
        elif self.stopping:
            state = "stopping"
        elif self.proc:
            state = "running"
        elif w["paused"]:
            state = "paused"
        elif w["times"] is not None and self.runs >= w["times"]:
            state = "done"
        else:
            state = "waiting"
        return state_doc(self.id, state, w, self.ctl, self.runs, self.error_now(), last_warning=self.warning_now(),
                         signal=self.signal, **self.extra())

    def serve(self, got):
        final, now_ = None, True
        w = want(self.initial, {})
        try:
            while True:
                now = time.monotonic()
                self.ctl.poll()
                w = want(self.initial, self.ctl.good)
                if w["stop"] and not self.stopping:
                    self.stopping, now_ = True, False
                self.idle(w)
                if got:
                    self.signal = got[0]
                    if self.proc:
                        self.finish(stop(self.proc))
                    final = "stopped"
                    break
                if self.proc and _exited(self.proc.pid, 0):
                    self.finish(reap(self.proc))
                if not self.proc:
                    done = w["times"] is not None and self.runs >= w["times"]
                    if self.stopping:
                        final = "stopped"
                        break
                    if done or self.ended:
                        final, now_ = "done", False
                        break
                    if not w["paused"] and now >= self.due(w):
                        self.beat(w, now)
                self.state_file.write(self.status(w))
                if self.state_file.failed:          # 窗壞了：收工（正在跑的那次在 finally 收掉）
                    final, now_ = "stopped", True
                    break
                time.sleep(0.01 if self.proc else 0.02)
        finally:
            if self.proc:
                self.finish(stop(self.proc))
            self.state_file.write(self.status(w, "stopping"))
            try:
                self.finish_up(final or "stopped", now_, got)
            finally:
                self.state_file.write(self.status(w, final or "stopped"))
                aos_cli.emit({"end": final or "stopped", "runs": self.runs, "last_code": self.last_code,
                              "signal": self.signal})

    def run(self):
        main = threading.current_thread() is threading.main_thread()
        got = []
        old = {s: signal.signal(s, lambda signum, frame: got.append(signum)) for s in _CAUGHT} if main else {}
        try:
            self.serve(got)
        finally:
            for s, h in old.items():
                signal.signal(s, h)
        if got:
            raise LoopError("Signaled", "收到訊號 %d" % got[0])
        if self.state_file.failed:
            raise LoopError("StateWriteFailed", self.state_file.failed)
        if self.inst_exit:
            code = (self.last_error or "InstError").split(":")[0]
            raise LoopError(code, "最後一次 aos_inst 自己出錯：%s" % self.last_error)


def run(x):
    """跟命令列一樣：x＝LOOP.json 的路徑（可接 `#/位置`）或一份設定 dict。正常結束回 None；loop 自己出錯丟 `LoopError`。"""
    if isinstance(x, dict):
        Loop(*check_config(None, x)).run()
    else:
        Loop(*load_config(x)).run()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        doc, ident, piped, rest = aos_cli.config(args, tuple(DEFAULTS))
        if rest is not None:
            raise LoopError("Usage", "aos_loop 不收 --")
        Loop(*check_config(ident, doc)).run()
        return 0
    except LoopError as e:
        if e.code != "Signaled":
            aos_cli.error(e.code, e.msg)
        return e.exit
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
