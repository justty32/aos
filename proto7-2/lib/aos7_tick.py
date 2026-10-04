"""aos7-tick：開一個回合——round +1、執行任務控制、審核加掛、照 tasks.json 在槽裡起任務，印一行 JSON 就結束，不等任務（spec.md 第 4 節）。

    aos7-tick <root> <node-id>

退出碼：0＝做了（或 gone／stale，stdout 說明）；3＝round.json 讀不到或兩份回合數都不能用（不知道，什麼都沒寫）。
起點是 proto7-1 lib/aos7_tick.py；spawn/ 拿掉，一次性任務改成 tasks.json 的 `mode: "once"` 項（4.4 的 launch 標記）。
"""
import hashlib
import json
import os
import signal
import sys

import aos7_mount
import aos7_task
from aos7_fs import (BAD, FD_PREFIX, IO, MISSING, OK, LockTimeout, action_lock, edit_json, is_int, locked,
                     node_path, now, read_json, read_json3, test_point, write_json)
from aos7_task import EMPTY, ENDED, LIVE, UNKNOWN, NAME_RE, SLOT_RE

MODES = ("keep", "each", "once")
LOCK_WAIT = 1.0   # 4.2 第 4 步：tasks.json.lock 最多等 1 秒


# ---------- tasks.json ----------

def load_items(fnode):
    """讀 tasks.json，回 (項目清單（只含物件）, 錯誤清單, tasks_rev)。整份讀不懂當空表並記錯。"""
    path = os.path.join(fnode, ".aos", "tasks.json")
    st, t = read_json3(path)
    rev = None
    try:
        if st in (OK, BAD):
            with open(path, "rb") as f:
                rev = hashlib.sha1(f.read()).hexdigest()[:12]
    except OSError:
        pass
    if st == MISSING:
        return [], [], rev
    if st == IO:
        return [], ["tasks.json 讀不到：%s，這回合不起" % t], rev
    if st == BAD:
        return [], ["tasks.json 讀不懂（不是 JSON），當空表"], rev
    items = t.get("tasks") if isinstance(t, dict) else None
    if not isinstance(items, list):
        return [], ["tasks.json 要是 {\"tasks\": [...]}，當空表"], rev
    errs = ["tasks[%d] 不是物件" % k for k, i in enumerate(items) if not isinstance(i, dict)]
    return [i for i in items if isinstance(i, dict)], errs, rev


def check_item(item):
    """第 4.1 節的欄位型別檢查；不對丟 ValueError（只跳過這一項）。驗證在挑槽、算 run 之前做完。"""
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
    mode = item.get("mode", "each")
    if mode not in MODES:
        raise ValueError("mode 要是 keep、each 或 once，拿到 %r" % (mode,))
    ml = item.get("max_live", 1)
    if not is_int(ml) or ml < 1:
        raise ValueError("max_live 要是正整數，拿到 %r" % (ml,))
    fr = item.get("from_round", 1)
    if not is_int(fr):
        raise ValueError("from_round 要是整數，拿到 %r" % (fr,))
    if not isinstance(item.get("enabled", True), bool):
        raise ValueError("enabled 要是 true 或 false，拿到 %r" % (item.get("enabled"),))
    if item.get("mounts") is not None and not isinstance(item["mounts"], dict):
        raise ValueError("mounts 要是物件")
    if "subroot" in item and not isinstance(item["subroot"], str):
        raise ValueError("subroot 要是字串")
    if "allow_stop" in item and not isinstance(item["allow_stop"], bool):
        raise ValueError("allow_stop 要是 true 或 false，拿到 %r" % (item["allow_stop"],))
    if "slot" in item:
        s = item["slot"]
        if mode != "once":
            raise ValueError("slot 只給 once 項")
        m = SLOT_RE.match(s) if isinstance(s, str) else None
        if not m or m.group(1) != n:
            raise ValueError("slot 要是 %s 或 %s.<數字>，拿到 %r" % (n, n, s))
    if "mounts_dyn" in item and not (isinstance(item["mounts_dyn"], list)
                                     and all(isinstance(x, str) for x in item["mounts_dyn"])):
        raise ValueError("mounts_dyn 要是字串陣列")


def launch_of(item):
    """once 項的 launch 標記 {"slot", "run", "round"}；沒有或壞掉回 None。"""
    la = item.get("launch")
    if isinstance(la, dict) and isinstance(la.get("slot"), str) and SLOT_RE.match(la["slot"]) and is_int(la.get("run")):
        return la
    return None


def next_run(prev, rnd):
    """run＝起它的回合數；不大於上一個 run 就用上一個＋1（spec 5.2，W4）。"""
    return rnd if not is_int(prev) or rnd > prev else prev + 1


def table_slots(items):
    """tasks.json 現在「認得」的槽名（刪槽判斷用；spec 5.1）。"""
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

class Plan:
    def __init__(self):
        self.starts = []        # [(item, slot, run, once_key)]
        self.used = set()       # 這個 tick 已排的槽
        self.skipped = []       # [{"name", "slot"?, "why"}]
        self.errors = []
        self.drop = []          # 已經起過的 once 項（照 launch 標記比對）：直接刪
        self.changed = False    # tasks.json 要寫回


def plan_round(ctx, items, views, rnd, p):
    """在 tasks.json.lock 裡呼叫：照 4.2 第 4 步挑要起的，決定槽與 run；once 項寫 launch 標記（改 items 本身）。"""
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
    order = [i for i in valid if i.get("mode") == "once"] + [i for i in valid if i.get("mode", "each") != "once"]
    for item in order:
        name, mode = item["name"], item.get("mode", "each")
        if item.get("enabled", True) is False or rnd < item.get("from_round", 1):
            continue
        slots = aos7_task.slot_names(name, item.get("max_live", 1))
        if mode == "once":
            la = launch_of(item)
            if la:
                v = view(la["slot"])
                if v.state == UNKNOWN and v.run is None:
                    p.skipped.append({"name": name, "slot": la["slot"], "why": "unknown: %s" % v.get("why")})
                    continue
                if v.run == la["run"]:
                    p.drop.append(item)     # 已經起了（或起到一半，交給 5.4 判定）：刪掉這項，不重起
                    p.changed = True
                    continue
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
        elif mode == "keep":
            for slot in slots:
                if free(slot):
                    p.used.add(slot)
                    p.starts.append((item, slot, next_run(view(slot).run, rnd), False))
                elif slot not in p.used and view(slot).state == UNKNOWN:
                    p.skipped.append({"name": name, "slot": slot, "why": "unknown: %s" % view(slot).get("why")})
        else:   # each：一個空槽起一次；上一次還在跑（沒空槽）就跳過這回合
            slot = next((s for s in slots if free(s)), None)
            if slot is None:
                unk = [s for s in slots if s not in p.used and view(s).state == UNKNOWN]
                p.skipped.append({"name": name, "why": "unknown" if unk else "busy"})
                continue
            p.used.add(slot)
            p.starts.append((item, slot, next_run(view(slot).run, rnd), False))


# ---------- 審核加掛（4.5） ----------

def serve_mounts(ctx, views):
    t = read_json(os.path.join(ctx.fnode, ".aos", "tasks.json"), {})
    allow = t.get("mount_allow") if isinstance(t, dict) else None
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

GONE = {"round": None, "started": [], "gone": True}


def held_node(fn, root, node_id, gone):
    """抓住 node 目錄的 fd，把 `/proc/self/fd/N`（fnode）交給 fn(fnode, node) 做整個動作（spec 2.5）：
    node 被搬走時寫到新位置；被刪掉時寫入失敗（不在舊路徑建鬼目錄）→ 回 gone。"""
    node = node_path(root, node_id)
    try:
        nfd = os.open(node, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return dict(gone)
    fnode = FD_PREFIX + str(nfd)
    try:
        try:
            os.makedirs(os.path.join(fnode, ".aos"), exist_ok=True)
            return fn(fnode, node)
        except (FileNotFoundError, NotADirectoryError):
            if not os.path.isdir(os.path.join(fnode, ".aos")):
                return dict(gone)   # 動作中途 node 被刪：寫不進去就收手
            raise
    finally:
        os.close(nfd)


class _Skip(Exception):
    """這回合不從 tasks.json 起任何東西（錯誤已記）。"""


class Unknown(Exception):
    """推定不了的事實（round.json 讀不到…）：什麼都不寫，退出碼 3。"""


def next_round(fnode):
    """回 (新回合數, 錯誤清單)。round.json 讀不到＝不知道；內容壞掉用 last-round.json 接著數；兩個都不能用＝不知道（spec 第 3 節）。"""
    st, r = read_json3(os.path.join(fnode, ".aos", "round.json"))
    if st == IO:
        raise Unknown("round.json 讀不到：%s" % r)
    if st == OK and isinstance(r, dict) and is_int(r.get("round")):
        return r["round"] + 1, []
    lst, lr = read_json3(os.path.join(fnode, ".aos", "last-round.json"))
    if lst == IO:
        raise Unknown("round.json 不能用、last-round.json 讀不到：%s" % lr)
    lr_round = lr.get("round") if lst == OK and isinstance(lr, dict) and is_int(lr.get("round")) else None
    if st == MISSING:
        return (lr_round or 0) + 1, ([] if lr_round is None else ["round.json 不見了，從 last-round.json 的 %d 接著數"
                                                                  % lr_round])
    if lr_round is None:
        raise Unknown("round.json 壞了，last-round.json 也不能用；請人寫回 round.json（例如 {\"round\": N, \"open\": false}）")
    return lr_round + 1, ["round.json 壞了，從 last-round.json 的 %d 接著數" % lr_round]


def tick(root, node_id):
    """做一次 tick，回 {"round", "started", "tasks_rev"}（node 不在 `gone`、舊世代 `stale`，都什麼都不寫）。
    推定不了（Unknown）丟出去。"""
    root = os.path.abspath(root)

    def act(fnode, node):
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "started": [], "stale": True}
            return _tick(root, node_id, node, fnode)
    return held_node(act, root, node_id, GONE)


def _tick(root, node_id, node, fnode):
    rpath = os.path.join(fnode, ".aos", "round.json")
    rnd, errs = next_round(fnode)
    _slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s" % lerr)
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

    p = Plan()
    tpath = os.path.join(fnode, ".aos", "tasks.json")
    rev = None
    try:
        if slots is None:
            raise _Skip()
        with locked(tpath, LOCK_WAIT):
            items, lerrs, rev = load_items(fnode)
            p.errors += lerrs
            plan_round(ctx, items, views, rnd, p)
            if p.changed:
                write_json(tpath, _rewrite(tpath, items, p))   # launch 標記在寫 birth.json 之前落地（4.4）
                test_point("after-launch")
    except LockTimeout:
        p.errors.append("tasks.json.lock 一秒內拿不到，這回合不從 tasks.json 起任何東西")
    except _Skip:
        pass

    # 要重用的槽裡有「已結束、還沒報過」的 run：清掉之前先記進 round.json，tock 照樣報（problems.md P2-03）
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
    claimed = set()
    for item, slot, run, once in p.starts:
        try:
            sub = aos7_task.check_subroot(ctx, item, claimed)
            if sub:
                claimed.add(sub)
            rid = aos7_task.start_in_slot(ctx, item, slot, run, sub)
        except Exception as e:   # noqa: BLE001  起不來的一項只記它，其他項照起
            if not os.path.isdir(os.path.join(fnode, ".aos")):
                raise FileNotFoundError(fnode)
            state.setdefault("tasks_error", []).append("%s：%s" % (item.get("name"), e))
            p.skipped.append({"name": item.get("name"), "slot": slot, "why": "error: %s" % str(e)[:200]})
            continue
        started.append(rid)
        if once:
            once_started.append((slot, run))
    test_point("before-once-delete")
    if once_started:
        try:
            edit_json(tpath, lambda t: _drop_launched(t, once_started), timeout=LOCK_WAIT)
        except (LockTimeout, ValueError) as e:
            # 刪不掉沒關係：下一個 tick 照 launch 標記比對 birth.json，知道已經起了就刪（4.4）
            state.setdefault("tasks_error", []).append("起完的 once 項這回合沒刪成：%s" % e)
    state["started"] = started
    write_json(rpath, state)
    return {"round": rnd, "started": started, "tasks_rev": rev}


def _raw_items(t):
    items = t.get("tasks") if isinstance(t, dict) else None
    return items if isinstance(items, list) else None


def _rewrite(tpath, items, p):
    """拿著鎖時重組 tasks.json：保留原檔其他欄位與非物件項目的位置，物件項目換成（可能加了 launch 的）同一批，刪掉 drop 的。"""
    t = read_json(tpath)
    t = dict(t) if isinstance(t, dict) else {}
    raw = _raw_items(t) or []
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
    """刪掉 launch 標記對得上（slot＋run）的 once 項：照標記比對，不照位置（中間有人改過檔也不會刪錯；4.2 第 6 步）。"""
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
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tick <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 收到 SIGTERM 不中斷，把動作做完（SIGKILL 保底；spec 2.5）
    try:
        r = tick(argv[0], argv[1])
    except Unknown as e:
        print(json.dumps({"unknown": str(e)}, ensure_ascii=False))
        print("aos7-tick: %s" % e, file=sys.stderr)
        return 3
    print(json.dumps({k: r[k] for k in ("round", "started", "tasks_rev", "gone", "stale") if k in r},
                     ensure_ascii=False))
    return 0
