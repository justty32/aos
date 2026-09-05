"""aos run：反覆 exec。WRITER-BRIEF 4.10、裁決 2026-09-04（三種鐘＋通用停法）。

一趟 run 從頭到尾抱著那塊地的鎖，每格呼叫 execute.exec_once(hold_lock=True)。
停下來一定寫 .aos/stopped.json，讓「為什麼停」看得見。
"""
import json
import os
import signal
import sys
import time

from . import execute, exits, fsutil, layout, loader, registry, series as S

# ---- 停止原因代碼（.aos/stopped.json 的 `reason`）----
IDLE = "idle"                  # 閒著了：沒有 running 的串，這格也沒前進
STEPS_DONE = "steps_done"      # --steps N 跑滿了
BUDGET = "budget"              # --budget N 用完了
FAILED = "failed"              # 有串壞了
CONTROL_STOP = "control_stop"  # 控制收件匣收到 op:stop
STALLED = "stalled"            # 沒前進、但還沒閒著，而且沒給 --every（見 FINDINGS）
SIGNAL = "signal"              # 被 SIGTERM／SIGINT 請走
PARSE_ERROR = "parse_error"    # 原稿或模板解析拒絕

_EXIT = {
    IDLE: exits.OK,
    STEPS_DONE: exits.OK,
    CONTROL_STOP: exits.OK,
    STALLED: exits.OK,
    BUDGET: exits.STOPPED,
    FAILED: exits.STOPPED,
    SIGNAL: exits.CANCELLED,
    PARSE_ERROR: exits.PARSE,
}

_SLEEP_SLICE = 0.05   # 睡覺切這麼細，好讓控制信與訊號早點被看到


# ---------- 訊號 ----------
class _Stopper:
    """把 SIGTERM／SIGINT 收成一個旗標，格尾才真的停（不打斷跑到一半的指令）。"""

    def __init__(self):
        self.hit = None
        self._old = {}

    def install(self):
        for s in (signal.SIGTERM, signal.SIGINT):
            try:
                self._old[s] = signal.signal(s, self._on)
            except (ValueError, OSError):
                pass   # 不是主執行緒就算了
        return self

    def _on(self, signum, frame):
        self.hit = signum

    def restore(self):
        for s, old in self._old.items():
            try:
                signal.signal(s, old)
            except (ValueError, OSError):
                pass


# ---------- 控制收件匣 ----------
def control_scan(land):
    """列出 .aos/control/ 裡待處理的控制信（不看 done/ 子目錄）。"""
    d = land.control
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        p = os.path.join(d, f)
        if not os.path.isfile(p):
            continue
        out.append((p, fsutil.read_json(p)))
    return out


def control_done(land, path):
    """處理過的控制信挪到 .aos/control/done/，比刪掉看得見。"""
    dst_dir = os.path.join(land.control, "done")
    fsutil.ensure_dir(dst_dir)
    dst = os.path.join(dst_dir, os.path.basename(path))
    try:
        os.replace(path, dst)
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    return dst


def _check_control(land, notes):
    """回傳 (要不要停, 說明)。不認得的 op 也挪走並留一句指路的話。"""
    stop_msg = None
    for path, obj in control_scan(land):
        if not isinstance(obj, dict):
            control_done(land, path)
            notes.append("控制信 %s 不是 json 物件，已挪到 .aos/control/done/；"
                         "格式看 WRITER-BRIEF 4.6" % os.path.basename(path))
            continue
        op = obj.get("op")
        who = obj.get("from") or "（沒寫 from）"
        control_done(land, path)
        if op == "stop":
            if stop_msg is None:
                stop_msg = "%s 送來停止信（id %s）" % (who, str(obj.get("id"))[:8])
        else:
            notes.append("控制信 %s 的 `op` 是 `%s`，只認得 `stop`；已挪到 "
                         ".aos/control/done/。下一步：改成 "
                         '{"format_version":1,"id":"…","op":"stop","from":"…","at":"…"} 再投一次'
                         % (str(obj.get("id"))[:8], op))
    return (stop_msg is not None), stop_msg


def _sweep_stale_control(land):
    """開跑前掃掉陳年控制信：run 沒在跑的時候投進來的停止信是舊帳，
    留著會害下一趟 run 莫名其妙第一格就停（看不見的狀態）。"""
    n = 0
    for path, _obj in control_scan(land):
        control_done(land, path)
        n += 1
    return n


# ---------- 時鐘 ----------
def clock_from(steps=None, every_ms=None, until=None):
    """把旗標翻成登記表的時鐘規格（WRITER-BRIEF 4.6）。"""
    if steps is not None:
        return {"kind": "steps", "steps": int(steps)}
    if every_ms is not None:
        return {"kind": "every", "every_ms": int(every_ms)}
    return {"kind": "until", "until": "idle"}


# ---------- 停止原因檔 ----------
def write_stopped(land, reason, message, series=None, step=None):
    """格式跟 execute._fail_series 寫的一致。"""
    rec = {
        "format_version": 1,
        "reason": reason,
        "message": message,
        "series": series,
        "step": step,
        "at": fsutil.now_iso(),
    }
    fsutil.write_json(land.stopped, rec)
    return rec


def _clear_stopped(land):
    """每趟 run 一開始先清掉上一輪的停止原因檔，免得使用者看到陳年舊帳。"""
    try:
        os.unlink(land.stopped)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _failed_ids(rep):
    return set(s["id"] for s in rep.get("series", []) if s.get("status") == S.FAILED)


def _fail_note(rep, sid):
    for s in rep.get("series", []):
        if s["id"] == sid:
            fr = s.get("fail_reason") or {}
            return fr.get("reason") or FAILED, fr.get("message") or "", fr.get("step")
    return FAILED, "", None


def _as_land(land):
    return land if isinstance(land, layout.Land) else layout.Land(land)


def _tick_line(rep):
    bits = []
    for n in rep["notes"]:
        bits.append(n)
    box = rep.get("inbox") or {}
    for k, label in (("mail", "搬信"), ("inst", "跑投遞指令"), ("rejected", "拒收")):
        if box.get(k):
            bits.append("收件匣%s %d 筆" % (label, len(box[k])))
    if not bits:
        bits.append("沒串在跑")
    return "第 %d 格：%s" % (rep["tick"], "；".join(bits))


# ---------- 主體 ----------
_WAIT_NAP_MS = 100


def run(land, steps=None, every_ms=None, until=None, budget=None, timeout_ms=None,
        register=False, quiet=False, printer=None, home=None):
    """反覆 exec 一塊地，回傳一份報告 dict。

    三種鐘（裁決 2026-09-04）：
      --steps N     跑 N 格
      --every <ms>  每隔這麼久跑一格（配 --until idle）
      --until idle  跑到閒著
      三個都沒給＝等同 --until idle

    通用停法：這格沒有任何串前進、也沒有新指令產生就停。
    """
    land = _as_land(land)
    if not land.is_land():
        raise execute.NotALand(
            "%s 不是一塊地（沒有 %s）；下一步：python3 proto/aos.py init %s"
            % (land.root, land.layout, land.root))

    out = {
        "land": land.root,
        "clock": clock_from(steps, every_ms, until),
        "budget": budget,
        "started_at": fsutil.now_iso(),
        "stopped_at": None,
        "ticks": 0,
        "first_tick": None,
        "last_tick": None,
        "idle": False,
        "reason": None,
        "message": "",
        "exit": exits.OK,
        "series": [],
        "notes": [],
        "ticks_detail": [],
    }
    say = printer if printer is not None else (lambda s: None)

    lock = fsutil.Lock(land.lock)
    try:
        lock.acquire()
    except fsutil.LockBusy:
        raise fsutil.LockBusy(
            "%s 已經有一支 exec／run 在跑（鎖 %s）；下一步：等它跑完，"
            "或確認沒有孤兒鎖後手動刪掉那個檔" % (land.root, land.lock))

    stopper = _Stopper().install()
    registered = False
    try:
        _clear_stopped(land)
        swept = _sweep_stale_control(land)
        if swept:
            msg = "開跑前清掉 %d 封陳年停止信（沒有 run 在跑時投進來的），挪到 .aos/control/done/" % swept
            out["notes"].append(msg)
            say(msg)

        if register:
            _register_self(land, out["clock"], budget, home)
            registered = True

        n = 0
        _pre = S.load(land) or {"series": []}
        known_failed = set(x["id"] for x in _pre.get("series", [])
                           if x.get("status") == S.FAILED)
        reason = None
        message = ""
        fail_series = None
        fail_step = None
        last_wait_sig = None
        last_wait_say = -99

        while True:
            if stopper.hit:
                reason, message = SIGNAL, "收到訊號 %s，在格尾停下來" % stopper.hit
                break
            try:
                rep = execute.exec_once(land, timeout_ms=timeout_ms, hold_lock=True)
            except loader.ParseError as e:
                reason, message = PARSE_ERROR, str(e)
                break
            n += 1
            out["ticks"] = n
            if out["first_tick"] is None:
                out["first_tick"] = rep["tick"]
            out["last_tick"] = rep["tick"]
            out["idle"] = rep["idle"]
            out["series"] = rep["series"]
            out["ticks_detail"].append({
                "tick": rep["tick"], "advanced": rep["advanced"], "idle": rep["idle"],
                "notes": rep["notes"],
                "waiting": rep.get("waiting") or [],
                "inbox": {k: len(v) for k, v in (rep.get("inbox") or {}).items()},
            })
            say(_tick_line(rep))

            # 開跑前就壞掉的串不算這趟的鍋
            now_failed = _failed_ids(rep)
            fresh = now_failed - known_failed
            known_failed = now_failed

            # --- 停止條件，由重到輕 ---
            if fresh:
                sid = sorted(fresh)[0]
                r, m, stp = _fail_note(rep, sid)
                reason, message = FAILED, "串 %s 在 `%s` 壞了（%s：%s）" % (sid[:8], stp, r, m)
                fail_series, fail_step = sid, stp
                break

            seen_notes = len(out["notes"])
            hit, cmsg = _check_control(land, out["notes"])
            for note in out["notes"][seen_notes:]:
                say("  " + note)
            if hit:
                reason, message = CONTROL_STOP, cmsg
                break

            if rep["idle"] and not rep["advanced"]:
                reason, message = IDLE, "閒著了：接力棒裡沒有 running 的串"
                break
            if steps is not None and n >= int(steps):
                reason, message = STEPS_DONE, "--steps %d 跑完了" % int(steps)
                break
            if budget is not None and n >= int(budget):
                reason, message = BUDGET, "--budget %d 格用完了，還沒跑完" % int(budget)
                break
            waiting = rep.get("waiting") or []
            if not rep["advanced"] and not waiting:
                if every_ms is None:
                    reason = STALLED
                    message = ("這格沒有任何串前進，但還沒閒著，也沒有串在等結果。"
                               "沒給 --every 就不空轉燒 CPU。下一步："
                               "`aos status %s` 看卡在哪，或加 `--every <毫秒> --until idle` 繼續等"
                               % land.root)
                    break

            if not rep["advanced"] and waiting:
                # 刻意偏離 WRITER-BRIEF 的「沒產出新指令就停」：父投出 async 呼叫／LLM
                # 請求後，下一格本來就沒事做，照字面走 run 會在結果回來前就停掉，
                # 子跑完寫的結果永遠沒人收。只要還有串停在 await／同步 call 等結果，
                # 就不算閒著（edge-cases B01）。
                w = waiting[0]
                sig = tuple(sorted((x["series"], x["step"]) for x in waiting))
                # 每格都印同一句只是洗版；換了等的對象、或每 20 格才再說一次
                if sig != last_wait_sig or (n - last_wait_say) >= 20:
                    note = "有 %d 條串在等結果，run 不算閒著（串 %s 的 `%s`：%s）" % (
                        len(waiting), w["series"][:8], w["step"], w["message"])
                    out["notes"].append(note)
                    say("  " + note)
                    last_wait_sig, last_wait_say = sig, n
                if every_ms is None:
                    # 沒給 --every 也不能停，但要睡一下別燒 CPU
                    if _nap(land, stopper, _WAIT_NAP_MS, out["notes"]):
                        reason, message = CONTROL_STOP, "等結果時收到停止信"
                        break
                    continue

            if every_ms is not None:
                if _nap(land, stopper, every_ms, out["notes"]):
                    reason, message = CONTROL_STOP, "睡到一半收到停止信"
                    break

        out["reason"] = reason or IDLE
        out["message"] = message
        out["exit"] = _EXIT.get(out["reason"], exits.OK)
        out["stopped_at"] = fsutil.now_iso()
        write_stopped(land, out["reason"], out["message"], series=fail_series, step=fail_step)
        if out["reason"] == PARSE_ERROR:
            raise loader.ParseError(out["message"])
        return out
    finally:
        stopper.restore()
        if registered:
            _unregister_self(land, home)
        lock.release()


def _nap(land, stopper, every_ms, notes):
    """--every 的間隔。睡覺時也顧控制收件匣，不然 aos stop 要等一整個間隔。

    回傳 True＝睡到一半收到停止信（或訊號）。
    """
    deadline = time.time() + float(every_ms) / 1000.0
    while time.time() < deadline:
        if stopper.hit:
            return False   # 訊號交給外層那個 if 處理
        hit, _msg = _check_control(land, notes)
        if hit:
            return True
        time.sleep(min(_SLEEP_SLICE, max(0.0, deadline - time.time())))
    return False


def _register_self(land, clock, budget, home=None):
    """--register：往登記表寫一筆，並把自己的 pid 寫進去。"""
    reg = registry.load(home)
    if registry.find(reg, land.root) is None:
        registry.register(land.root, clock, budget=budget, home=home)
    # 已經有一筆（多半是 daemon 剛登記的）就別覆蓋它的時鐘與預算
    registry.update(land.root, home=home, pid=os.getpid(), state=registry.RUNNING)


def _unregister_self(land, home=None):
    """跑完（含被中斷）一定要改回 stopped，別讓登記表留幽靈。"""
    try:
        registry.update(land.root, home=home, pid=None, state=registry.STOPPED)
    except Exception:
        pass


# ---------- CLI ----------
def _print_human(out, quiet):
    print("停了：%s — %s" % (out["reason"], out["message"]))
    print("  跑了 %d 格（第 %s ~ %s 格），停止原因檔：%s/.aos/stopped.json"
          % (out["ticks"], out["first_tick"], out["last_tick"], out["land"]))


def cli_run(args):
    land = layout.Land(args.land)
    quiet = bool(getattr(args, "quiet", False))
    as_json = bool(getattr(args, "json", False))
    printer = None if (quiet or as_json) else (lambda s: print(s))
    try:
        out = run(land,
                  steps=args.steps,
                  every_ms=args.every,
                  until=args.until,
                  budget=args.budget,
                  timeout_ms=args.timeout,
                  register=bool(getattr(args, "register", False)),
                  quiet=quiet,
                  printer=printer)
    except execute.NotALand as e:
        sys.stderr.write("錯誤：%s\n" % e)
        return exits.NOT_A_LAND
    except loader.ParseError as e:
        sys.stderr.write("錯誤：%s\n下一步：改好 %s 再跑一次；停止原因記在 %s\n"
                         % (e, land.source("main"), land.stopped))
        return exits.PARSE
    except fsutil.LockBusy as e:
        sys.stderr.write("錯誤：%s\n" % e)
        return exits.LOCK_BUSY
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    else:
        _print_human(out, quiet)
    return out["exit"]
