"""aos7-tick <root> <node-id>：開一個回合——round +1、任務控制、審核加掛、照 tasks.json 在槽裡起任務，印一行 JSON 就結束，
不等任務（spec.md 第 4 節）。退出碼：0＝做了（或 gone／stale）；3＝不知道（回合判不出或還開著、列不出槽、gen.json 不能用、
看不到 node），什麼都沒寫；其他（例外）＝失敗，時間線照樣退避、不算一回合。"""
import errno
import hashlib
import json
import os
import signal
import sys
import types

import aos7_mount
import aos7_task
from aos7_fs import (BAD, FD_PREFIX, N, OK, U, ROUND_CLOSED, ROUND_NONE, ROUND_OPEN, LockTimeout, Unknown, action_lock,
                     edit_json, errname, fact, inject, is_gone, is_int, locked, node_path, now, read_round,
                     sweep_tmp, test_point, write_json)
from aos7_task import EMPTY, ENDED, LIVE, UNKNOWN, NAME_RE, SLOT_RE

MODES = ("keep", "each", "once")
LOCK_WAIT = 1.0   # tasks.json.lock 最多等 1 秒


# ---------- tasks.json ----------

def load_items(fnode):
    """讀任務表，回 (物件項目, 錯誤, tasks_rev＝原文 sha1 前 12 碼)。不存在＝空表；讀不到或不是一般檔（U）＝這回合不起、記錯；
    不是 JSON 或不是 {"tasks": [...]}（B：別人寫的輸入不合）＝當空表、記錯。"""
    path = os.path.join(fnode, ".aos", "tasks.json")
    st, t = fact(path)
    rev = None
    try:
        if st in (OK, BAD):
            with open(path, "rb") as f:
                rev = hashlib.sha1(f.read()).hexdigest()[:12]
    except OSError:
        pass
    if st == N:
        return [], [], rev
    if st == U:
        return [], ["%s，這回合不起" % t], rev
    if st == BAD:
        return [], ["tasks.json 讀不懂（不是 JSON），當空表"], rev
    items = t.get("tasks") if isinstance(t, dict) else None
    if not isinstance(items, list):
        return [], ["tasks.json 要是 {\"tasks\": [...]}，當空表"], rev
    errs = ["tasks[%d] 不是物件" % k for k, i in enumerate(items) if not isinstance(i, dict)]
    return [i for i in items if isinstance(i, dict)], errs, rev


# 欄位：(名字, 沒寫時的值, 合格嗎, 不合時說什麼)。不合的那一項跳過、記 tasks_error，其他照起（spec §4.1）
FIELDS = (("mode", "each", lambda v: v in MODES, "要是 keep、each 或 once"),
          ("max_live", 1, lambda v: is_int(v) and v >= 1, "要是正整數"),
          ("from_round", 1, is_int, "要是整數"),
          ("until_round", None, lambda v: v is None or (is_int(v) and v >= 0), "要是非負整數"),
          ("enabled", True, lambda v: isinstance(v, bool), "要是 true 或 false"),
          ("mounts", None, lambda v: v is None or isinstance(v, dict), "要是物件"),
          ("x", {}, lambda v: isinstance(v, dict), "要是物件（模組用的宣告欄位，核心照抄）"))
# 移出核心的舊欄位：帶了＝那項不合，指到接手的模組包（不靜默忽略：忽略會讓人以為功能還在）
MOVED = {"subroot": "subroot／allow_stop 已移到子 daemon 包：argv 改成 aos7-subd <subroot> [--allow-stop] -- ..."
                    "（modules/subd/README.md）",
         "retry_lost": "retry_lost 已移到 once 保證包：改寫成 \"x\": {\"retry_lost\": true}，並在 node 上跑 retry_lost 任務"
                       "（modules/once_retry/README.md）"}
MOVED["allow_stop"] = MOVED["subroot"]


def check_item(item):
    """驗證一個任務項目，不合丟 ValueError（呼叫的人只跳過這一項）。要在挑槽、算 run 之前驗完。"""
    n = item.get("name")
    if not (isinstance(n, str) and NAME_RE.match(n)):
        raise ValueError("name 必填，只能用英數、_、-，拿到 %r" % (n,))
    if "argv" in item:
        a = item["argv"]
        if not (isinstance(a, list) and a and all(isinstance(x, str) and "\0" not in x for x in a)):
            raise ValueError("argv 要是非空的字串陣列，拿到 %r" % (a,))
        if "inst" in item:
            raise ValueError("argv 與 inst 只能二選一")
    elif not isinstance(item.get("inst"), str):
        raise ValueError("要有 argv（字串陣列）或 inst（字串）")
    for k, default, ok, why in FIELDS:
        if not ok(item.get(k, default)):
            raise ValueError("%s %s，拿到 %r" % (k, why, item.get(k, default)))
    for k, why in MOVED.items():
        if k in item:
            raise ValueError(why)
    if "slot" in item:   # once 釘槽（控制包 restart、once 保證包加回時用）
        s = item["slot"]
        m = SLOT_RE.match(s) if isinstance(s, str) else None
        if item.get("mode", "each") != "once":
            raise ValueError("slot 只給 once 項")
        if not m or m.group(1) != n:
            raise ValueError("slot 要是 %s 或 %s.<數字>，拿到 %r" % (n, n, s))


def launch_of(item):
    """once 項的起動標記 `launch`＝{"slot", "run", "round"}（spec §4.4）；沒有或格式不合回 None。"""
    la = item.get("launch")
    if isinstance(la, dict) and isinstance(la.get("slot"), str) and SLOT_RE.match(la["slot"]) and is_int(la.get("run")):
        return la
    return None


def next_run(prev, rnd):
    """新 run＝起它的回合數；不大於上一個 run（回合數被人手倒退）就用上一個＋1，run 一定遞增（spec §5.2）。"""
    return rnd if not is_int(prev) or rnd > prev else prev + 1


def table_slots(items):
    """表上還認得的槽名（tock 刪槽用）：保守的保留清單——max_live 壞了也留基本槽，釘的 slot、launch 指的槽都算。"""
    names = set()
    for it in items:
        n = it.get("name")
        if not (isinstance(n, str) and NAME_RE.match(n)):
            continue
        ml = it.get("max_live", 1)
        names.update(aos7_task.slot_names(n, ml if is_int(ml) and ml >= 1 else 1))
        if isinstance(it.get("slot"), str):
            names.add(it["slot"])
        la = launch_of(it)
        if la:
            names.add(la["slot"])
    return names


# ---------- 挑這回合要起的 ----------

def plan_round(ctx, items, views, rnd, p):
    """表鎖內替這回合選槽、算 run（spec §4.2～4.4），結果放進 p；once 項要起的先在 items 裡記 launch（呼叫的人寫回
    tasks.json 之後才起）。只在確知是空槽或已結束的槽起；判不出的槽不起、記 skipped。"""
    def view(slot):
        if slot not in views:
            views[slot] = aos7_task.judge_resolved(aos7_task.slot_dir(ctx.fnode, slot), ctx.node, slot, rnd)
        return views[slot]

    def free(slot):
        return slot not in p.used and view(slot).state in (EMPTY, ENDED)

    valid = []
    for k, item in enumerate(items):
        label = item.get("name") if isinstance(item.get("name"), str) else "tasks[%d]" % k
        try:
            check_item(item)
        except ValueError as e:
            p.errors.append("%s：%s" % (label, e))
            continue
        valid.append(item)
    # once 先排：控制包 restart 加的 once（釘同槽）先佔槽，同名 keep 才不會搶先起；used 保證一槽一回合只起一次。
    order = [i for i in valid if i.get("mode") == "once"] + [i for i in valid if i.get("mode", "each") != "once"]
    for item in order:
        name, mode = item["name"], item.get("mode", "each")
        if item.get("enabled", True) is False or rnd < item.get("from_round", 1):
            continue
        # until_round：回合數超過它就不再起新 run（已在跑的不殺；分配者掛了，使用權照樣到期）。項目與槽留著
        expired = item.get("until_round") is not None and rnd > item["until_round"]
        if expired and not (item.get("mode") == "once" and launch_of(item)):
            continue
        slots = aos7_task.slot_names(name, item.get("max_live", 1))
        if mode == "once":
            la = launch_of(item)
            if la:
                v = view(la["slot"])
                if v.state == UNKNOWN and v.run is None:
                    p.skipped.append({"name": name, "slot": la["slot"], "why": "unknown: %s" % v.get("why")})
                    continue
                # 槽的 run 就是標記的 run＝交接已開始（可能沒跑成，但不能再起第二份）
                if v.run == la["run"]:
                    p.drop.append(item)     # 已經起了（或起到一半，交給 5.4 判定）：刪掉這項，不重起
                    p.changed = True
                    continue
                if expired:
                    continue                # 上次沒起成、但已過 until_round：不再起（項目留著給人看）
                cands = [la["slot"]]        # 上次在寫 birth.json 之前就被殺：同一個槽用新的 run 照常起
            else:
                cands = [item["slot"]] if isinstance(item.get("slot"), str) else slots
            slot = next((s for s in cands if free(s)), None)
            if slot is None:
                why = "unknown" if any(view(s).state == UNKNOWN for s in cands if s not in p.used) else "busy"
                p.skipped.append({"name": name, "slot": cands[0] if len(cands) == 1 else None, "why": why})
                continue
            run = next_run(max([x for x in (view(slot).run, (la or {}).get("run")) if is_int(x)], default=None), rnd)
            item["launch"] = {"slot": slot, "run": run, "round": rnd}
            p.changed = True
            p.used.add(slot)
            p.starts.append((item, slot, run, True))
        else:   # keep：補滿所有空槽；each：一個空槽起一次，上一次還在跑（沒空槽）就跳過這回合
            pick = [s for s in slots if free(s)]
            pick = pick if mode == "keep" else pick[:1]
            unk = [s for s in slots if s not in p.used and s not in pick and view(s).state == UNKNOWN]
            for slot in pick:
                p.used.add(slot)
                p.starts.append((item, slot, next_run(view(slot).run, rnd), False))
            if mode == "keep":
                p.skipped += [{"name": name, "slot": s, "why": "unknown: %s" % view(s).get("why")} for s in unk]
            elif not pick:
                p.skipped.append({"name": name, "why": "unknown" if unk else "busy"})


# ---------- 審核加掛（4.5） ----------

def serve_mounts(ctx, views):
    """審核活任務的執行中加掛請求（spec §4.5），回帶 run id 的紀錄。tasks.json 讀不到＝不知道 mount_allow，這回合不審。"""
    st, t = fact(os.path.join(ctx.fnode, ".aos", "tasks.json"))
    if st == U:
        return [{"run": None, "name": None, "path": None, "ok": False, "msg": "%s，這回合不審加掛（請求留著）" % t}]
    allow = t.get("mount_allow") if st == OK and isinstance(t, dict) else None
    out = []
    for slot, v in sorted(views.items()):
        if v.state != LIVE or v.run is None:
            continue
        try:
            for r in aos7_mount.serve(ctx.root, aos7_task.slot_dir(ctx.fnode, slot), allow,
                                      real_taskdir=aos7_task.slot_dir(ctx.node, slot)):
                out.append(dict(r, run=aos7_task.run_id(slot, v.run)))
        except Exception as e:   # noqa: BLE001
            out.append({"run": aos7_task.run_id(slot, v.run), "name": None, "path": None, "ok": False,
                        "msg": "加掛處理失敗：%r" % (e,)})
    return out


# ---------- tick 本體 ----------

def held_node(fn, root, node_id, gone):
    """抓住 node 的 fd 跑 fn(fnode, node)（fnode＝`/proc/self/fd/N`：node 中途被搬走照樣寫到它，被刪就寫不進去）。
    node 不在、或 node 本身是符號連結（O_NOFOLLOW：絕不沿連結寫出空間根的最小保險）→ 回 gone；看不到（EIO…）丟 Unknown。
    動作中 node 被刪（.aos 不在了）也回 gone。`.aos/` 不在就經 fd 建（登記不要求它先存在）。"""
    node = node_path(root, node_id)
    try:
        inject("node-open", node)
        nfd = os.open(node, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as e:
        if is_gone(e) or e.errno == errno.ELOOP:
            return dict(gone)
        raise Unknown("看不到 node %s：%r" % (node_id, e), kind=errname(e)) from None
    fnode = FD_PREFIX + str(nfd)
    try:
        try:
            os.makedirs(os.path.join(fnode, ".aos"), exist_ok=True)
            return fn(fnode, node)
        except (FileNotFoundError, NotADirectoryError):
            if not os.path.isdir(os.path.join(fnode, ".aos")):
                return dict(gone)
            raise
    finally:
        os.close(nfd)


def next_round(fnode):
    """這回合的回合數，回 (回合數, 說明)（spec §3）：明確 `open: false` → round＋1；還開著、或判不出 → 丟 Unknown（不拿
    last-round.json 接號：那樣會把還開著的同號回合再開一次）；round.json 不存在 → 照 last-round.json 接著數，它也不存在
    從 1 起，它讀不到或壞掉丟 Unknown（不從 1 重數）。"""
    st, r, why = read_round(os.path.join(fnode, ".aos", "round.json"))
    if st == ROUND_CLOSED:
        return r["round"] + 1, []
    if st == ROUND_OPEN:
        raise Unknown("第 %d 回合還開著（round.json open: true），先 tock 收掉才開下一回合" % r["round"], kind="round-open")
    if st != ROUND_NONE:
        raise Unknown(why, kind="round-unknown")
    lst, lr = fact(os.path.join(fnode, ".aos", "last-round.json"))
    if lst == N:
        return 1, []
    if lst == OK and isinstance(lr, dict) and is_int(lr.get("round")):
        return lr["round"] + 1, ["round.json 不見了，從 last-round.json 的 %d 接著數" % lr["round"]]
    raise Unknown("round.json 不見了，last-round.json 也不能用（%s）；請人寫回 round.json（例如 {\"round\": N, \"open\": false}）"
                  % (lr if lst != OK else "內容不完整"), kind="round-unknown")


def tick(root, node_id):
    """開一個回合（spec §4.2），回 {round, started, tasks_rev}；node 不在回 gone、舊世代的動作回 stale。"""
    root = os.path.realpath(root)   # 空間根本身經過連結也照實際位置

    def act(fnode, node):
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "started": [], "stale": True}
            return _tick(root, node_id, node, fnode)
    return held_node(act, root, node_id, {"round": None, "started": [], "gone": True})


def _tick(root, node_id, node, fnode):
    """動作鎖內開回合：判回合、清暫存、寫 round.json、任務控制、判槽、審加掛、挑要起的（表鎖內記 launch）、
    記 reaped、起任務、刪起完的 once。開回合之前推定不了丟 Unknown；開了之後單項出錯只記 tasks_error。"""
    rpath = os.path.join(fnode, ".aos", "round.json")
    rnd, errs = next_round(fnode)
    sweep_tmp(os.path.join(fnode, ".aos"))
    _slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s" % lerr, kind="listdir")
    state = {"round": rnd, "open": True, "tick_at": now(), "tock_at": None, "started": [], "ctl": [], "mounts": []}
    write_json(rpath, state)
    test_point("tick-opened")
    ctx = aos7_task.Ctx(root, node_id, node, fnode, rnd)

    state["ctl"] = aos7_task.run_all_ctl(ctx)

    # 先把現有的槽判定一遍（含疑似 lost 的身分掃描與收程序），放在拿 tasks.json.lock 之前：收程序可能要一秒
    views = {}
    slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        errs.append("列不出 .aos/tasks/：%s，這回合不起任務" % lerr)
        slots = None
    for slot in slots or ():
        try:
            views[slot] = aos7_task.judge_resolved(aos7_task.slot_dir(fnode, slot), node, slot, rnd)
        except Exception as e:   # noqa: BLE001  一個槽壞掉只記它
            views[slot] = aos7_task.View(state=UNKNOWN, run=None, why=repr(e)[:200])
    state["mounts"] = serve_mounts(ctx, views)

    # 這回合的起動計畫：starts＝[(項目, 槽, run, 是 once)]、used＝已排的槽、drop＝已經起過的 once 項、changed＝表要寫回
    p = types.SimpleNamespace(starts=[], used=set(), skipped=[], errors=[], drop=[], changed=False)
    tpath = os.path.join(fnode, ".aos", "tasks.json")
    rev = None
    try:
        # 表鎖內只挑槽、寫 launch，放鎖之後才起程序（不讓起程序的時間佔住共用的表）
        with locked(tpath, LOCK_WAIT):
            items, lerrs, rev = load_items(fnode) if slots is not None else ([], [], None)
            p.errors += lerrs
            plan_round(ctx, items, views, rnd, p)
            if p.changed:
                test_point("before-launch")
                write_json(tpath, _rewrite(tpath, items, p))   # launch 標記在寫 birth.json 之前落地
                test_point("after-launch")
    except LockTimeout:
        p.errors.append("tasks.json.lock 一秒內拿不到，這回合不從 tasks.json 起任何東西")
    except Unknown as e:
        p.starts = []   # launch 標記沒落地：這回合一個都不起（once 不能沒有標記就起）
        p.errors.append("%s；這回合不起任何東西" % e)

    # 要重用的槽裡有「已結束、還沒報過」的 run（tock 之後才結束）：清掉之前先記進 round.json，tock 照樣報
    reaped = []
    for item, slot, run, _once in p.starts:
        v = views.get(slot)
        if v is not None and aos7_task.unreported(v):
            reaped.append(aos7_task.ended_record(v, aos7_task.slot_dir(fnode, slot)))
    state.update({"tasks_rev": rev, "reaped": reaped, "skipped": p.skipped})
    if errs + p.errors:
        state["tasks_error"] = errs + p.errors
    write_json(rpath, state)

    started, once_started = [], []
    for item, slot, run, once in p.starts:
        try:
            rid = aos7_task.start_in_slot(ctx, item, slot, run)
        except Exception as e:   # noqa: BLE001  起不來的一項只記它；node 被刪了就整個收手
            if not os.path.isdir(os.path.join(fnode, ".aos")):
                raise FileNotFoundError(fnode)
            state.setdefault("tasks_error", []).append("%s：%s" % (item.get("name"), e))
            p.skipped.append({"name": item.get("name"), "slot": slot, "why": "error: %s" % str(e)[:200]})
            continue
        started.append(rid)
        if once:
            once_started.append((slot, run))
    test_point("before-once-delete")
    # 起了才刪 once 項（先刪再起，中途被殺就無痕漏掉）；刪不掉沒關係，下一個 tick 照 launch 標記比對 birth 就知道起過了
    if once_started:
        try:
            edit_json(tpath, lambda t: _drop_launched(t, once_started), timeout=LOCK_WAIT)
        except Unknown as e:
            state.setdefault("tasks_error", []).append("起完的 once 項這回合沒刪成：%s" % e)
        test_point("after-once-delete")
    state["started"] = started
    write_json(rpath, state)
    return {"round": rnd, "started": started, "tasks_rev": rev}


def _rewrite(tpath, items, p):
    """表鎖內重組任務表（記了 launch 的項目換進去、已起過的 once 拿掉，其餘原樣）。重讀照三態：讀不到、壞掉或不是
    {"tasks": [...]}＝不知道原本有什麼 → 丟 Unknown、不寫回（G1）。"""
    st, t = fact(tpath)
    raw = t.get("tasks") if st == OK and isinstance(t, dict) else None
    if not isinstance(raw, list):
        raise Unknown("tasks.json 重讀時%s，launch 標記沒寫" % (t if st != OK else "不是 {\"tasks\": [...]}"))
    t = dict(t)
    it = iter(items)
    out = []
    for x in raw:
        if isinstance(x, dict):
            cur = next(it)
            if not any(cur is d for d in p.drop):
                out.append(cur)
        else:
            out.append(x)
    t["tasks"] = out
    return t


def _drop_launched(t, started):
    """從最新的表刪掉起完的 once（照 launch 的 slot＋run 比對，不照位置：中間有人改過表也不會刪錯）；沒得刪回 None。"""
    if not isinstance(t, dict) or not isinstance(t.get("tasks"), list):
        return None
    keys = {(s, r) for s, r in started}
    out = [i for i in t["tasks"] if not (isinstance(i, dict) and i.get("mode") == "once" and launch_of(i)
                                         and (launch_of(i)["slot"], launch_of(i)["run"]) in keys)]
    if len(out) == len(t["tasks"]):
        return None
    t = dict(t)
    t["tasks"] = out
    return t


def main(argv=None):
    """命令列入口；退出碼見檔頭。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tick <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # SIGTERM 不中斷，把動作做完（逾時由 SIGKILL 保底）
    try:
        r = tick(argv[0], argv[1])
    except Unknown as e:
        print(json.dumps({"unknown": str(e)}, ensure_ascii=False))
        print("aos7-tick: %s" % e, file=sys.stderr)
        return 3
    print(json.dumps({k: r[k] for k in ("round", "started", "tasks_rev", "gone", "stale") if k in r},
                     ensure_ascii=False))
    return 0
