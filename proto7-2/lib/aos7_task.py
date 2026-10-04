"""槽與任務：槽名、三態判定、lost 判定前的身分掃描、kill／restart、在槽裡起新的 run（spec.md 第 4.1、5、6 節）。

tick、tock、daemon 共用。起點是 proto7-1 lib/aos7_task.py，改成「槽＝照名字重用的任務資料夾」＋ run 號。
讀寫一律經呼叫的人給的路徑（tick／tock 給 `/proc/self/fd/N/...`，node 中途被刪就寫不進去、不建鬼目錄）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

import aos7_mount
import aos7_proc
from aos7_fs import (BIN, BAD, FD_PREFIX, IO, MISSING, OK, edit_json, env_with_bin, is_int, node_path, now,
                     proc_starttime, read_json, read_json3, real_path, test_point, write_json, LockTimeout)

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SLOT_RE = re.compile(r"^([A-Za-z0-9_-]+)(?:\.([1-9][0-9]*))?$")

# 換 run 時清掉的基礎設施檔（spec 5.1）。ctl.json／ctl-done.json 不清（problems.md P2-04）。
INFRA_FILES = ("birth.json", "pid.json", "out.log", "exit.json", "tock.json", "writes.jsonl")
INFRA_DIRS = ("mnt", "mount-req", "mount-done")

EMPTY, LIVE, ENDED, UNKNOWN, SUSPECT = "empty", "live", "ended", "unknown", "suspect"


# ---------- 路徑與名字 ----------

def tasks_dir(node):
    """`<node>/.aos/tasks/`。"""
    return os.path.join(node, ".aos", "tasks")


def slot_dir(node, slot):
    return os.path.join(tasks_dir(node), slot)


def slot_names(name, max_live=1):
    """name 的槽名：`name`、`name.1`…`name.(max_live−1)`（spec 5.1）。"""
    return [name] + ["%s.%d" % (name, k) for k in range(1, max(1, max_live))]


def run_id(slot, run):
    return "%s#%s" % (slot, run)


def list_slots(node):
    """`.aos/tasks/` 底下的槽名（略過 `.` 開頭與名字不合的）。回 (清單, 錯誤或 None)：列不出來（I/O）＝不知道。"""
    import errno
    try:
        names = os.listdir(tasks_dir(node))
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return [], None
        return [], repr(e)[:200]
    return sorted(n for n in names if not n.startswith(".") and SLOT_RE.match(n)), None


# ---------- 讀一個槽 ----------

def _same_run(path, run):
    """讀 pid.json／exit.json／tock.json：回 (狀態, 值)；`run` 跟這次不同（上一個 run 沒清乾淨的）當不存在（spec 5.1）。"""
    st, v = read_json3(path)
    if st == OK:
        if isinstance(v, dict) and v.get("run") == run:
            return OK, v
        return MISSING, None
    if st == BAD:
        return MISSING, None   # 原子寫不會半寫；壞掉的是別人寫壞的，不算這次的
    return st, v


class View(dict):
    """一個槽的判定結果：state、run、birth、pid、exit、why。"""

    @property
    def state(self):
        return self["state"]

    @property
    def run(self):
        return self.get("run")


def judge(fslot, node, slot, cur_round):
    """spec 5.4 的表：回 View。fslot＝讀寫用的槽路徑；node＝node 的實際路徑（身分掃描比 AOS7_NODE）。

    不做任何破壞性動作；SUSPECT（疑似 lost）交給 resolve。"""
    bst, birth = read_json3(os.path.join(fslot, "birth.json"))
    if bst == MISSING:
        return View(state=EMPTY, run=None)
    if bst == IO:
        return View(state=UNKNOWN, run=None, why="birth.json 讀不到：%s" % birth)
    if bst == BAD or not isinstance(birth, dict) or not is_int(birth.get("run")):
        # 內容壞掉：只比 NODE＋TID 做身分掃描，有相符活程序＝活（run 不明），沒有＝空槽
        alive = aos7_proc.env_procs(node, slot, runners=True)
        return View(state=LIVE if alive else EMPTY, run=None, why="birth.json 壞了", broken=True)
    run = birth["run"]
    v = View(state=None, run=run, birth=birth)
    est, ex = _same_run(os.path.join(fslot, "exit.json"), run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    if est == IO:
        return View(v, state=UNKNOWN, why="exit.json 讀不到：%s" % ex)
    pst, pid = _same_run(os.path.join(fslot, "pid.json"), run)
    if pst == IO:
        return View(v, state=UNKNOWN, why="pid.json 讀不到：%s" % pid)
    runner = birth.get("runner") if isinstance(birth.get("runner"), dict) else None
    r_state = aos7_proc.same_process(runner.get("pid"), runner.get("starttime")) if runner else None
    if pst == OK:
        t_state = aos7_proc.same_process(pid.get("pid"), pid.get("starttime"))
        if aos7_proc.ALIVE in (t_state, r_state):
            return View(v, state=LIVE, pid=pid)
        if aos7_proc.UNKNOWN in (t_state, r_state):
            return View(v, state=LIVE, pid=pid, unsure="starttime 讀不到，當活（K-05）")
        return _recheck(View(v, pid=pid), fslot, run, "任務與 runner 都不在")
    if runner:
        if r_state == aos7_proc.ALIVE:
            return View(v, state=LIVE)
        if r_state == aos7_proc.UNKNOWN:
            return View(v, state=LIVE, unsure="runner 的 starttime 讀不到，當活（K-05）")
        return _recheck(v, fslot, run, "沒有 pid.json，runner 已不在")
    br = birth.get("round")
    if is_int(br) and is_int(cur_round) and br <= cur_round - 2:
        return _recheck(v, fslot, run, "沒有 pid.json、沒有 runner，起了兩回合以上")
    return View(v, state=LIVE, unsure="剛起")


def _recheck(v, fslot, run, why):
    """判成疑似 lost 前再看一次 exit.json（runner 可能剛好在這一瞬間寫完；proto7-1 P-07）。"""
    est, ex = _same_run(os.path.join(fslot, "exit.json"), run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    if est == IO:
        return View(v, state=UNKNOWN, why="exit.json 讀不到")
    return View(v, state=SUSPECT, why=why)


def resolve(v, fslot, node, slot, cur_round):
    """疑似 lost 一律先做身分掃描（NODE＋TID＋RUN）：找到相符的活程序先照 Q1 收掉，再判 lost；找不到就判 lost（spec 5.4）。
    lost 寫 exit.json `{"run", "code": null, "lost": true}`。收不乾淨（SIGKILL 後還在）＝不知道，不判 lost。回新的 View。"""
    if v.state != SUSPECT:
        return v
    pgid = (v.get("pid") or {}).get("pgid")
    found = aos7_proc.env_procs(node, slot, v.run)
    note = None
    if found or (pgid and aos7_proc.group_alive(pgid)):
        clean, msg = aos7_proc.kill_identity(node, slot, v.run, pgid)
        if not clean:
            return View(v, state=UNKNOWN, why="疑似 lost，但相符的程序收不掉：%s" % msg)
        note = "lost 前收掉相符的殘留程序：%s" % msg
    est, ex = _same_run(os.path.join(fslot, "exit.json"), v.run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    ex = {"run": v.run, "code": None, "lost": True, "at": now(), "round": cur_round}
    if note:
        ex["note"] = note
    write_json(os.path.join(fslot, "exit.json"), ex)
    return View(v, state=ENDED, exit=ex)


def judge_resolved(fslot, node, slot, cur_round):
    return resolve(judge(fslot, node, slot, cur_round), fslot, node, slot, cur_round)


def ended_record(v, fslot):
    """已結束的 run → last-round.json `ended` 的一筆。被任務控制收掉的帶 `by_ctl`。"""
    ex = v.get("exit") or {}
    rec = {"run": run_id(os.path.basename(fslot), v.run), "code": ex.get("code")}
    if ex.get("lost"):
        rec["lost"] = True
    if ex.get("error"):
        rec["error"] = str(ex["error"])[:200]
    cd = read_json(os.path.join(fslot, "ctl-done.json"))
    res = cd.get("result") if isinstance(cd, dict) else None
    if isinstance(res, dict) and res.get("run") == rec["run"] and cd.get("op") in ("kill", "restart") and res.get("ok"):
        rec["by_ctl"] = {"op": cd.get("op"), "by": cd.get("by")}
    return rec


def unreported(v):
    """已結束、但還沒在任何回合的 last-round.json 報過（exit.json 沒有 seen_round）。"""
    return v.state == ENDED and not is_int((v.get("exit") or {}).get("seen_round"))


# ---------- 任務控制（第 6 節） ----------

RESTART_KEYS = ("name", "argv", "inst", "subroot", "allow_stop")
DIFF_KEYS = ("argv", "inst", "mounts", "subroot", "allow_stop")
SCHED_KEYS = ("mode", "from_round", "max_live", "enabled", "launch", "slot", "restart_of", "mounts_dyn")


def dyn_mounts(birth):
    """birth.json 裡執行中加掛的（標了 dyn）→ {名字: 空間路徑}。"""
    m = (birth or {}).get("mounts") or {}
    return {n: v["to"] for n, v in m.items() if isinstance(v, dict) and v.get("dyn") and "to" in v and "at" in v}


def reload_item(fnode, birth):
    """restart reload（Q6）：tasks.json 裡同名的第一個非 once 項，完整驗證過才用，去掉排程欄位；
    掛載＝項目宣告加上沒被宣告接管的執行中加掛。回 (項目, None) 或 (None, 說明)。"""
    import aos7_tick
    name = birth.get("name")
    items, errs, _rev = aos7_tick.load_items(fnode)
    found = [i for i in items if i.get("name") == name and i.get("mode") != "once"]
    if not found:
        why = "；".join(errs) if errs and not items else "tasks.json 沒有名為 %s 的非 once 項目" % name
        return None, "%s；沒執行（沒 kill）。不加 reload 會照出生時的定義重起" % why
    try:
        aos7_tick.check_item(found[0])
    except ValueError as e:
        return None, "tasks.json 的 %s 不合格：%s；沒執行（沒 kill）" % (name, e)
    item = {k: v for k, v in found[0].items() if k not in SCHED_KEYS}
    decl = item.get("mounts") or {}
    dyn = {n: to for n, to in dyn_mounts(birth).items() if n not in decl}
    item["mounts"] = dict(dyn, **decl)
    if dyn:
        item["mounts_dyn"] = sorted(dyn)
    return item, None


def def_diff(birth, item):
    out = {}
    for k in DIFF_KEYS:
        old = aos7_mount.decl_of(birth) if k == "mounts" else birth.get(k)
        new = (item.get(k) or {}) if k == "mounts" else item.get(k)
        if old != new:
            out[k] = {"old": old, "new": new}
    return out


def _wait_pid_json(fslot, run, v, limit=aos7_proc.KILL_GRACE):
    """剛起、aos7-run 還沒寫 pid.json：等一下（最多 limit 秒），免得 kill 打在任務起來之前。"""
    end = time.monotonic() + limit
    while time.monotonic() < end:
        st, pid = _same_run(os.path.join(fslot, "pid.json"), run)
        if st == OK:
            return pid
        est, _ = _same_run(os.path.join(fslot, "exit.json"), run)
        if est == OK:
            return None
        time.sleep(0.02)
    return None


def kill_run(fslot, node, slot, v):
    """收掉 v 這一次 run（Q1 範圍），回 (ok, msg)。已結束算成功，順便收相符的殘留。"""
    if v.state == ENDED:
        clean, msg = aos7_proc.kill_identity(node, slot, v.run)
        return clean, "already ended" + ("" if msg.startswith("no process") else "; leftover: " + msg)
    pid = v.get("pid")
    if pid is None and v.state == LIVE:
        pid = _wait_pid_json(fslot, v.run, v)
    clean, msg = aos7_proc.kill_identity(node, slot, v.run, (pid or {}).get("pgid"))
    # 給 runner 一點時間寫 exit.json（code 負數＝被訊號殺），回合總結才看得到結束
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        if _same_run(os.path.join(fslot, "exit.json"), v.run)[0] == OK:
            break
        time.sleep(0.02)
    return clean, msg


def run_ctl(ctx, slot):
    """執行 `<槽>/ctl.json`（若有），搬成 ctl-done.json（蓋掉舊的）。回紀錄 dict 或 None。"""
    fslot = slot_dir(ctx.fnode, slot)
    path = os.path.join(fslot, "ctl.json")
    st, ctl = read_json3(path)
    if st == MISSING:
        return None
    if st == IO:
        return {"slot": slot, "op": None, "ok": False, "err": "ctl.json 讀不到：%s（下一次再看）" % ctl}
    bad = None
    if st == BAD or not isinstance(ctl, dict):
        bad = "unreadable JSON" if st == BAD else "not a JSON object"
        ctl = {"raw": "unreadable" if st == BAD else ctl}
    op = ctl.get("op")
    diff = None
    v = judge_resolved(fslot, ctx.node, slot, ctx.round)
    target = ctl.get("run")
    rid = run_id(slot, v.run) if v.run is not None else None
    if bad:
        ok, msg = False, bad
    elif op not in ("kill", "restart"):
        ok, msg = False, "unknown op %r" % (op,)
    elif target is not None and not is_int(target):
        ok, msg = False, "run 要是整數，拿到 %r" % (target,)
    elif v.state == UNKNOWN:
        ok, msg = False, "槽的狀態不知道（%s），沒執行" % v.get("why")
    elif v.state == EMPTY or v.run is None:
        ok, msg = False, "槽裡沒有可以 %s 的 run" % op
    elif target is not None and target != v.run:
        ok, msg = False, "指定的 run %d 已經不是現在的（現在是 %s），沒執行" % (target, rid)
    elif op == "kill":
        ok, msg = kill_run(fslot, ctx.node, slot, v)
    else:
        birth = v.get("birth") or {}
        reload = ctl.get("reload", False)
        item = None
        if not isinstance(reload, bool):
            ok, msg = False, "reload 要是 true 或 false，拿到 %r；沒執行（沒 kill）" % (reload,)
        elif reload:
            item, msg = reload_item(ctx.fnode, birth)
            ok = item is not None
        else:
            item = {k: birth[k] for k in RESTART_KEYS if k in birth}
            item["mounts"] = aos7_mount.decl_of(birth)
            dyn = dyn_mounts(birth)
            if dyn:
                item["mounts_dyn"] = sorted(dyn)
        if item is not None:
            if reload:
                diff = def_diff(birth, item)
            item.update({"name": birth.get("name"), "mode": "once", "slot": slot, "restart_of": rid})
            # 先加 once 項、再 kill：中途被殺時 once 項等槽空了才起，不會「殺了沒重起」
            try:
                edit_json(os.path.join(ctx.fnode, ".aos", "tasks.json"),
                          lambda t: _append_items(t, [item]), default=None, timeout=1.0)
            except LockTimeout:
                ok, msg = False, "tasks.json.lock 一秒內拿不到，沒執行（沒 kill）"
            else:
                ok, msg = kill_run(fslot, ctx.node, slot, v)
                msg += "; once 項已加進 tasks.json（slot %s）" % slot
                if reload:
                    msg += "（reload：%s）" % ("；".join("%s %s → %s" % (
                        k, json.dumps(d["old"], ensure_ascii=False), json.dumps(d["new"], ensure_ascii=False))
                        for k, d in diff.items()) or "定義沒變")
    ctl["result"] = {"ok": ok, "msg": msg, "at": now(), "run": rid}
    if diff is not None:
        ctl["result"]["diff"] = diff
    write_json(os.path.join(fslot, "ctl-done.json"), ctl)
    try:
        os.remove(path)
    except OSError:
        pass
    return {"slot": slot, "run": rid, "op": op, "ok": ok}


def _append_items(t, items):
    """tasks.json 內容加幾項（讀不懂的整份不動、回 None 不寫）。"""
    if t is None:
        t = {"tasks": []}
    if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
        raise ValueError("tasks.json 不是 {\"tasks\": [...]}，沒加")
    t = dict(t)
    t["tasks"] = list(t.get("tasks", [])) + list(items)
    return t


def run_all_ctl(ctx):
    """對每個槽執行 ctl.json。一個槽處理失敗只在它那筆記 `ok: false`＋`err`，其他照做。"""
    out = []
    slots, err = list_slots(ctx.fnode)
    if err:
        return [{"slot": None, "op": None, "ok": False, "err": "列不出槽：%s" % err}]
    for slot in slots:
        try:
            r = run_ctl(ctx, slot)
        except Exception as e:   # noqa: BLE001
            r = {"slot": slot, "op": None, "ok": False, "err": repr(e)[:200]}
        if r:
            out.append(r)
    return out


# ---------- 子 daemon（2.7） ----------

OWNER_ENV = ("AOS7_OWNER_NODE", "AOS7_OWNER_TID", "AOS7_ALLOW_STOP")


def registered_nodes(root):
    """`<root>/.aosd/nodes.json` 登記的 node id（讀不到回空）。"""
    nj = read_json(os.path.join(root, ".aosd", "nodes.json"))
    nodes = nj.get("nodes") if isinstance(nj, dict) else None
    return list(nodes) if isinstance(nodes, dict) else []


def under(nid, prefix):
    """node id nid 在 prefix 底下或就是它。"""
    return prefix == "." or nid == prefix or nid.startswith(prefix + "/")


def subroot_of(root, node_id, sub):
    """檢查 `subroot`：回 (空間路徑, None) 或 (None, 錯誤)。要在自己的 node 底下、不能是 node 本身、
    不能包住父 daemon 已登記的 node（spec 4.1）。"""
    good, bad = aos7_mount.check({"subroot": sub})
    if not good:
        return None, (bad or ["subroot 不合"])[0]
    sp = good["subroot"]
    if not (aos7_mount.in_root(root, sp) and os.path.realpath(node_path(root, sp)).startswith(
            os.path.realpath(node_path(root, node_id)) + os.sep)):
        return None, "subroot %s 要在自己的 node（%s）底下" % (sub, node_id)
    inside = [n for n in registered_nodes(root) if under(n, sp)]
    if inside:
        return None, "subroot %s 包住了父 daemon 已登記的 node %s" % (sp, ", ".join(sorted(inside)))
    return sp, None


def stopped_note(root, sub):
    path = os.path.join(node_path(root, sub), ".aosd", "stopped.json")
    if not os.path.lexists(path):
        return None
    st = read_json(path)
    st = st if isinstance(st, dict) else {}
    return "子 daemon（%s）已被 %s 在 %s stop%s；刪掉 %s/.aosd/stopped.json 就會再起" % (
        sub, st.get("by") or "?", st.get("at") or "?", "（%s）" % st["why"] if st.get("why") else "", sub)


def subroot_running(sp):
    """子根 `<sp>/.aosd/daemon.lock` 有人拿著嗎：非阻塞 flock 試得到就馬上放掉、回 False。"""
    import fcntl
    try:
        fd = os.open(os.path.join(sp, ".aosd", "daemon.lock"), os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    finally:
        os.close(fd)
    return False


def check_subroot(ctx, item, claimed):
    """起帶 subroot 的任務前的檢查（2.7）。不合丟 ValueError；合格回子根空間路徑或 None（沒帶 subroot）。"""
    sub = item.get("subroot")
    if sub is None:
        return None
    sp, err = subroot_of(ctx.root, ctx.node_id, sub)
    if err:
        raise ValueError(err)
    note = stopped_note(ctx.root, sp)
    if note:
        raise ValueError(note)
    if sp in claimed:
        raise ValueError("子根 %s 這個 tick 已經有別項認領，沒起" % sp)
    fsp = os.path.join(ctx.fnode, os.path.relpath(node_path(ctx.root, sp), ctx.node))
    if subroot_running(fsp):
        ow = read_json(os.path.join(fsp, ".aosd", "owner.json"))
        o = (ow.get("owner") if isinstance(ow, dict) else None) or {}
        raise ValueError("子根 %s 已經有 daemon 在跑（owner：node %s 任務 %s），沒起" % (
            sp, o.get("node", "?"), o.get("tid", "?")))
    return sp


# ---------- 起任務（5.3） ----------

class Ctx:
    """一次 tick／tock 的環境：root、node_id、node（實際路徑）、fnode（讀寫用的 fd 路徑）、round。"""

    def __init__(self, root, node_id, node, fnode, rnd):
        self.root, self.node_id, self.node, self.fnode, self.round = root, node_id, node, fnode, rnd


def same_dir(node, fnode):
    """抓著的 node（fd 路徑）跟字串路徑 node 現在指的還是同一個資料夾嗎。不是 fd 路徑當同一個。"""
    if not fnode.startswith(FD_PREFIX):
        return True
    try:
        return os.path.samestat(os.stat(node), os.stat(fnode))
    except OSError:
        return False


def clear_slot(fslot):
    """換 run：清掉上一個 run 的基礎設施檔，任務自己寫的檔留著（spec 5.1，W6）。"""
    import errno
    for n in INFRA_FILES:
        try:
            os.unlink(os.path.join(fslot, n))
        except IsADirectoryError:
            shutil.rmtree(os.path.join(fslot, n), ignore_errors=True)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    for n in INFRA_DIRS:
        p = os.path.join(fslot, n)
        if os.path.islink(p) or os.path.isfile(p):
            os.unlink(p)
        elif os.path.isdir(p):
            shutil.rmtree(p)


def start_in_slot(ctx, item, slot, run, sub=None):
    """在槽裡起新的 run（spec 5.3 第 2～5 步；第 1 步的判定由呼叫的人做完）。回 run id。

    起不來（aos7-run 起不了、node 中途被換掉）照樣寫 exit.json code 127，任務不會永遠算剛起。"""
    root, node, fnode, rnd = ctx.root, ctx.node, ctx.fnode, ctx.round
    tdir = slot_dir(node, slot)
    fslot = slot_dir(fnode, slot)
    os.makedirs(fslot, exist_ok=True)
    clear_slot(fslot)
    birth = {"name": item.get("name"), "slot": slot, "run": run, "round": rnd, "node": ctx.node_id,
             "once": item.get("mode") == "once", "restart_of": item.get("restart_of"), "at": now(), "runner": None}
    if "inst" in item:
        birth["inst"] = item["inst"]
    else:
        birth["argv"] = item.get("argv", [])
    if not same_dir(node, fnode):
        why = "node %s 在 tick 中途被搬走或換掉（現在在 %s），沒起" % (ctx.node_id, real_path(fnode))
        birth.update({"mounts": {}, "error": why})
        write_json(os.path.join(fslot, "birth.json"), birth)
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd, "error": why})
        return run_id(slot, run)
    birth["mounts"] = aos7_mount.make(root, tdir, item.get("mounts") or {}, fs_taskdir=fslot, node=node, fnode=fnode)
    for n in item.get("mounts_dyn") or ():
        if isinstance(birth["mounts"].get(n), dict):
            birth["mounts"][n]["dyn"] = True
    if "allow_stop" in item:
        birth["allow_stop"] = item["allow_stop"]
    if sub:
        birth["subroot"] = sub
        fsp = os.path.join(fnode, os.path.relpath(node_path(root, sub), node))
        os.makedirs(os.path.join(fsp, ".aosd"), exist_ok=True)
    elif item.get("subroot") is not None:
        birth["subroot_error"] = "subroot 沒通過檢查"
    bpath = os.path.join(fslot, "birth.json")
    write_json(bpath, birth)
    test_point("after-birth")
    env = env_with_bin()
    for k in ("AOS7_SUBROOT", "AOS7_GEN", "AOS7_EARLY", "AOS7_INCOMPLETE", "AOS7_TEST_CRASH", "AOS7_TEST_HANG") \
            + OWNER_ENV:
        env.pop(k, None)
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": ctx.node_id, "AOS7_TASK": tdir,
                "AOS7_TID": slot, "AOS7_RUN": str(run)})
    if sub:
        env["AOS7_SUBROOT"] = node_path(root, sub)
        env.update({"AOS7_OWNER_NODE": ctx.node_id, "AOS7_OWNER_TID": slot,
                    "AOS7_ALLOW_STOP": "1" if item.get("allow_stop") is True else "0"})
    try:
        tfd = os.open(fslot, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as e:
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd,
                                                      "error": str(e)})
        return run_id(slot, run)
    try:
        if not same_dir(node, fnode):
            raise OSError("node %s 在起任務前被搬走或換掉（現在在 %s），沒起" % (ctx.node_id, real_path(fnode)))
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir, str(tfd)], cwd=fnode, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, pass_fds=(tfd,))
    except OSError as e:
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd,
                                                      "error": str(e)})
    else:
        test_point("after-popen")
        birth["runner"] = {"pid": p.pid, "starttime": proc_starttime(p.pid)}
        try:
            cur = read_json(bpath)
            if isinstance(cur, dict) and cur.get("run") == run:
                cur["runner"] = birth["runner"]   # 保留 runner 之前可能已經被別的步驟改過的欄位
                write_json(bpath, cur)
        except OSError:
            pass
    finally:
        os.close(tfd)
    return run_id(slot, run)
