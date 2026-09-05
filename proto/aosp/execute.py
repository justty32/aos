"""aos exec：走一步（一格）。WRITER-BRIEF 4.2 / 4.4 / 4.5。"""
import os
import subprocess
import sys

from . import fsutil, inbox, instrun, layout, loader, regs, registry, series as S, status

OK = "ok"
FAIL = "fail"
HOLD = "hold"          # 這格不動，不算失敗
END = "end"


def _ext(sr, key):
    sr.setdefault("ext", {})
    sr["ext"].setdefault(key, {})
    return sr["ext"][key]


def _pick_next(land, step, prog):
    """成功後跳哪：select > then > 下一步。"""
    sel = step.get("select")
    if sel:
        p = land.resolve(sel)
        try:
            with open(p, "r", encoding="utf-8") as f:
                line = f.readline().strip()
            if line:
                return line
        except FileNotFoundError:
            pass
    if step.get("then"):
        return step["then"]
    return loader.next_step_name(prog, step["name"])


def bad_result_path(land, raw):
    """落點檢查。回傳錯誤訊息，沒問題就 None。

    相對路徑以指定它的那塊地的根為基準（已由 land.resolve 處理）；
    不准指進任何 `.aos/`（那是機器的，人與子地不該往裡面寫）。
    """
    full = os.path.abspath(land.resolve(raw))
    parts = full.split(os.sep)
    if layout.AOS_DIR in parts:
        return ("結果落點 `%s` 指進了 %s/（那是機器自己的目錄，不准當落點）；"
                "換一個地上的路徑，例如 `out/xxx.txt`" % (raw, layout.AOS_DIR))
    return None


def _fail_series(land, sr, reason, message):
    """I-03 最保守預設：沒寫 on_fail 就停在原地、狀態 failed、寫停止原因檔。"""
    sr["status"] = S.FAILED
    sr["fail_reason"] = {"reason": reason, "message": message,
                         "step": sr["cursor"], "at": fsutil.now_iso()}
    fsutil.write_json(land.stopped, {
        "format_version": 1,
        "reason": reason,
        "message": message,
        "series": sr["id"],
        "step": sr["cursor"],
        "at": fsutil.now_iso(),
    })


def _do_inst(land, sr, step, tick, timeout_ms, extra_env, exclusive_used):
    inst = step["inst"]
    groups = inst.get("exclusive") or []
    for g in groups:
        if g in exclusive_used:
            # 同組的指令不在同一格跑，後到的延到下一格
            return HOLD, "exclusive", "跟同格別的指令搶 `%s`，延到下一格" % g
    for g in groups:
        exclusive_used.add(g)
    res = instrun.run_inst(land, tick, inst, sr["id"], timeout_ms=timeout_ms, extra_env=extra_env)
    ok, reason, msg = instrun.transport_ok(res)
    if not ok:
        return FAIL, reason, msg
    ok, reason, msg = instrun.semantic_ok(land, step, res)
    if not ok:
        return FAIL, reason, msg
    return OK, None, None


def _open_call(land, sr, step, tick):
    """寫呼叫記錄 .aos/calls/<call id>.json；同一步只開一次。"""
    calls = _ext(sr, "calls")
    cid = calls.get(step["name"])
    if cid and os.path.exists(land.call(cid)):
        return cid, fsutil.read_json(land.call(cid))
    cid = fsutil.new_id()
    rec = {
        "format_version": 1,
        "id": cid,
        "tick": tick,
        "series": sr["id"],
        "step": step["name"],
        "child": os.path.abspath(land.resolve(step["child"])),
        "mode": step["mode"],
        "result": land.resolve(step["result"]),
        "args": step.get("args") or {},
        "opened_at": fsutil.now_iso(),
    }
    fsutil.write_json(land.call(cid), rec)
    calls[step["name"]] = cid
    return cid, rec


def _child_env(rec, parent_root):
    env = {"AOS_RESULT": rec["result"], "AOS_CALLER": parent_root}
    for k, v in (rec.get("args") or {}).items():
        env["AOS_ARG_%s" % str(k).upper()] = str(v)
    return env


def _do_call(land, sr, step, tick, timeout_ms):
    bad = bad_result_path(land, step["result"])
    if bad:
        return FAIL, "bad_result_path", bad
    cid, rec = _open_call(land, sr, step, tick)
    # 落點的目錄由父先開好，子只管寫檔（子不准 mkdir -p：父地都不在了還建目錄，
    # 等於在墳墓上蓋房子）。父地不在就當場失敗。
    if not os.path.isdir(land.root):
        return FAIL, "caller_gone", "父地 %s 不見了，這個呼叫沒有落點可寫" % land.root
    try:
        fsutil.ensure_dir(os.path.dirname(rec["result"]))
    except OSError as e:
        return FAIL, "bad_result_path", "開不了落點目錄 %s：%s" % (
            os.path.dirname(rec["result"]), e)
    child = layout.Land(rec["child"])
    if not child.is_land():
        return FAIL, "not_a_land", "子地 %s 不是一塊地（沒有 .aos/layout.json）" % child.root
    if step["mode"] == "sync":
        # 父每格對子做一次 aos exec；子沒閒著這步就停在原地
        try:
            rep = exec_once(child, timeout_ms=timeout_ms, extra_env=_child_env(rec, land.root))
        except fsutil.LockBusy as e:
            return HOLD, "lock_busy", str(e)
        if not rep["idle"]:
            return HOLD, "child_running", "子地還在跑（子的第 %d 格）" % rep["tick"]
        state, st = status.triple(rec["result"])
        if state == status.OK:
            return OK, None, None
        if state == status.FAILED:
            return FAIL, st.get("reason", "failed"), st.get("message", "子地說壞了")
        return FAIL, "no_result", "子地閒著了，但結果落點 %s 沒東西" % rec["result"]
    # async：登記子的時鐘後這步立刻成功
    clock = step.get("clock") or {"kind": "until", "until": "idle"}
    registry.register(child.root, clock, budget=step.get("budget"), parent=land.root,
                      result=rec["result"])
    if not registry.daemon_alive():
        # WRITER-BRIEF 4.11 第 6 條：daemon 不在就自己 detach 起一支
        _detach_run(child.root, clock, _child_env(rec, land.root))
    return OK, None, None


def _detach_run(child_root, clock, env_extra):
    argv = [sys.executable, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "aos.py"), "run", child_root, "--register"]
    kind = clock.get("kind")
    if kind == "steps":
        argv += ["--steps", str(clock.get("steps", 1))]
    elif kind == "every":
        argv += ["--every", str(clock.get("every_ms", 200)), "--until", "idle"]
    elif kind == "once":
        argv += ["--steps", "1"]
    else:
        argv += ["--until", "idle"]
    env = dict(os.environ)
    env.update({k: str(v) for k, v in env_extra.items()})
    logdir = layout.Land(child_root).aos
    fsutil.ensure_dir(logdir)
    log = open(os.path.join(logdir, "detached.log"), "ab")
    subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     start_new_session=True, close_fds=True)


def _do_await(land, sr, step, tick):
    bad = bad_result_path(land, step["result"])
    if bad:
        return FAIL, "bad_result_path", bad
    result = land.resolve(step["result"])
    state, st = status.triple(result)
    if state == status.OK:
        return OK, None, None
    if state == status.FAILED:
        return FAIL, st.get("reason", "failed"), st.get("message", "等到的是壞消息")
    waited = _ext(sr, "awaits")
    n = int(waited.get(step["name"], 0)) + 1
    waited[step["name"]] = n
    mx = step.get("max_ticks")
    if mx is not None and n > int(mx):
        status.write_failed(result, status.AWAIT_TIMEOUT,
                            "等了 %d 格還沒等到 %s" % (n, result))
        return FAIL, status.AWAIT_TIMEOUT, "等了 %d 格（上限 %s）" % (n, mx)
    return HOLD, "waiting", "還在等 %s（第 %d 格）" % (result, n)


def exec_one_series(land, sr, tick, timeout_ms, extra_env, exclusive_used):
    """對一條串走一步。回傳 (是否前進, 說明, 等什麼|None)。

    第三個值不是 None 就代表這條串停在原地等一個結果（`await` 或同步 `call`），
    run 不可以把這種情況當成「閒著」而停掉。
    """
    prog = loader.load_program(land, sr["template"])
    if sr["cursor"] in (None, "end"):
        sr["status"] = S.DONE
        return True, "串做完了", None
    step = loader.step_by_name(prog, sr["cursor"])
    if step is None:
        _fail_series(land, sr, "no_such_step",
                     "游標指向 `%s`，模板 `%s` 沒有這一步；有的是：%s"
                     % (sr["cursor"], sr["template"],
                        "、".join(s["name"] for s in prog["steps"])))
        return True, "游標指向不存在的步", None
    t = regs.table(land, sr, tick)
    try:
        step = regs.sub(step, t)
    except regs.MissingReg as e:
        _fail_series(land, sr, "missing_reg", str(e))
        return True, str(e), None

    kind = step["kind"]
    if kind == "inst":
        out, reason, msg = _do_inst(land, sr, step, tick, timeout_ms, extra_env, exclusive_used)
    elif kind == "call":
        out, reason, msg = _do_call(land, sr, step, tick, timeout_ms)
    else:
        out, reason, msg = _do_await(land, sr, step, tick)

    if out == HOLD:
        why = None if reason == "exclusive" else {
            "series": sr["id"], "step": step["name"], "kind": kind,
            "why": reason, "message": msg,
        }
        return False, msg, why
    if out == OK:
        nxt = _pick_next(land, step, prog)
        sr["cursor"] = nxt
        if nxt == "end":
            sr["status"] = S.DONE
            _drop_frame(land, sr["id"])
        return True, "推到 `%s`" % nxt, None
    # FAIL
    if step.get("on_fail"):
        sr["cursor"] = step["on_fail"]
        if sr["cursor"] == "end":
            sr["status"] = S.DONE
        return True, "失敗，跳去 `%s`（%s：%s）" % (step["on_fail"], reason, msg), None
    _fail_series(land, sr, reason or "failed", msg or "")
    return True, "失敗停在 `%s`（%s：%s）" % (step["name"], reason, msg), None


def _drop_frame(land, series_id):
    """串跑完由 exec 在推游標同一步刪堆疊框；壞掉的留著。"""
    d = land.frame(series_id)
    for root, dirs, files in os.walk(d, topdown=False):
        for f in files:
            try:
                os.unlink(os.path.join(root, f))
            except OSError:
                pass
        for x in dirs:
            try:
                os.rmdir(os.path.join(root, x))
            except OSError:
                pass
    try:
        os.rmdir(d)
    except OSError:
        pass


def exec_once(land, timeout_ms=None, extra_env=None, hold_lock=False, template="main"):
    """走一格。回傳報告 dict。

    {"tick":N,"advanced":bool,"idle":bool,"notes":[…],"inbox":{…}}
    """
    if not land.is_land():
        raise NotALand("%s 不是一塊地；先跑：python3 proto/aos.py init %s" % (land.root, land.root))
    lock = None
    if not hold_lock:
        lock = fsutil.Lock(land.lock).acquire()
    try:
        baton, fresh = S.load_or_start(land, template, cursor=None)
        if fresh:
            prog = loader.load_program(land, template)
            baton["series"][0]["cursor"] = prog["steps"][0]["name"]
        tick = baton["tick"]
        notes = []
        advanced = False
        exclusive_used = set()
        waiting = []
        for sr in list(baton["series"]):
            if sr.get("status") != S.RUNNING:
                continue
            moved, note, why = exec_one_series(land, sr, tick, timeout_ms, extra_env,
                                               exclusive_used)
            notes.append("[%s] %s" % (sr["id"][:8], note))
            advanced = advanced or moved
            if why:
                waiting.append(why)
        baton["tick"] = tick + 1
        S.save(land, baton)
        box = inbox.process(land, tick, timeout_ms=timeout_ms)
        if box["inst"] or box["mail"] or box["rejected"]:
            advanced = True
        return {
            "land": land.root,
            "tick": tick,
            "next_tick": baton["tick"],
            "advanced": advanced,
            "idle": S.idle(baton),
            "waiting": waiting,
            "notes": notes,
            "inbox": box,
            "series": baton["series"],
        }
    finally:
        if lock:
            lock.release()


class NotALand(Exception):
    """不是一塊地。對應退出碼 4。"""
