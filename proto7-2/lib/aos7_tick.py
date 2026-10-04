"""aos7-tick：開一個回合——round +1、執行任務控制、審核加掛、照 tasks.json 在槽裡起任務，印一行 JSON 就結束，不等任務（spec.md 第 4 節）。

    aos7-tick <root> <node-id>

由 daemon 的 node 時間線呼叫（S-04、S-09、S-10），也可由人手執行。
讀 .aos/round.json、last-round.json、tasks.json 與各槽的 birth／pid／exit／ctl／mount-req；
寫 round.json、必要的 tasks.json，以及經 task／mount 層更新的槽檔、控制與掛載回條。
共用 action.lock 並讀 .aosd/gen.json、寫 .aos/action.owner.json（spec §2.5）；
交接見 §5.3：只起 runner，任務結果由 runner 與 tock 接續。

退出碼：0＝做了（或 gone／stale，stdout 說明）；3＝不知道（round.json 讀不到／內容不完整／上一回合還開著、
last-round.json 不能接、列不出槽、gen.json 不能用、看不到 node；什麼都沒寫，A2-02、P2-09）。
起點是 proto7-1 lib/aos7_tick.py；spawn/ 拿掉，一次性任務改成 tasks.json 的 `mode: "once"` 項（4.4 的 launch 標記）。
"""
import errno
import hashlib
import json
import os
import signal
import sys

import aos7_mount
import aos7_task
from aos7_fs import (BAD, FD_PREFIX, IO, MISSING, OK, ROUND_CLOSED, ROUND_NONE, ROUND_OPEN, LockTimeout, Unknown,
                     action_lock, edit_json, inject, is_gone, is_int, locked, node_path, now,
                     read_json, read_json3, read_round, sweep_tmp, test_point, write_json)
from aos7_task import EMPTY, ENDED, LIVE, UNKNOWN, NAME_RE, SLOT_RE

MODES = ("keep", "each", "once")
LOCK_WAIT = 1.0   # 4.2 第 4 步：tasks.json.lock 最多等 1 秒


# ---------- tasks.json ----------

def load_items(fnode):
    """從 fnode（持有的 node fd 路徑）讀任務表，回 (物件項目清單, 錯誤清單, tasks_rev)。
    不存在回空表、不記錯；I/O、格式壞掉回空表並記錯，讀不出原文時 rev 可為 None。
    只決定本回合能否起任務，不據此刪槽（spec §4.1～4.3、P2-09）。"""
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
    """驗證 item 任務物件的欄位型別，成功回 None，不合丟 ValueError。
    呼叫者只跳過這一項；必須在挑槽、算 run 前驗完（spec §4.1；P2-18 的 max_live 必須大於零）。"""
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
    ur = item.get("until_round")
    if ur is not None and not (is_int(ur) and ur >= 0):
        raise ValueError("until_round 要是非負整數，拿到 %r" % (ur,))
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
    if "ctl_id" in item and not isinstance(item["ctl_id"], str):
        raise ValueError("ctl_id 要是字串（restart 寫的，A2-05）")
    if "retry_lost" in item:
        # P2-02 選項：預設 false＝最多一次；true＝判 lost 時若看起來從沒起來過，加回重起（可能跑兩次）
        if not isinstance(item["retry_lost"], bool):
            raise ValueError("retry_lost 要是 true 或 false，拿到 %r" % (item["retry_lost"],))
        if mode != "once":
            raise ValueError("retry_lost 只給 once 項")
    if "retry_of" in item and not isinstance(item["retry_of"], str):
        raise ValueError("retry_of 要是字串（retry_lost 加回時寫的）")


def launch_of(item):
    """從 item 取出有效的 once 起動標記，回原 launch 物件（spec §4.4）。
    沒有標記、slot 或 run 格式不合回 None；此處不讀 birth，也不判定任務是否真的起過。"""
    la = item.get("launch")
    if isinstance(la, dict) and isinstance(la.get("slot"), str) and SLOT_RE.match(la["slot"]) and is_int(la.get("run")):
        return la
    return None


def next_run(prev, rnd):
    """由上一個 run 值 prev、本回合 rnd 算出新 run 整數（spec §5.2，W4）。
    prev 不是整數就用 rnd；否則至少是 prev + 1，人工倒退回合也不重用舊身分。"""
    return rnd if not is_int(prev) or rnd > prev else prev + 1


def table_slots(items):
    """從 items 任務物件清單回傳表上仍認得的槽名集合，供 tock 刪槽判斷（spec §5.1）。
    無效 name 跳過；max_live 壞掉先保留基本槽，另保留明示 slot 與有效 launch 指向的槽。
    這是保守保留清單，不等同 check_item 的可啟動清單，也不負責讀表失敗的判斷。"""
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
    """一回合的起動計畫：在表鎖內選槽、記 launch，放鎖後才真正 spawn（spec §4.2）。"""
    def __init__(self):
        """建立空的計畫、佔槽集合與錯誤／略過清單；無參數，初始化 self，回 None。"""
        self.starts = []        # [(item, slot, run, once_key)]
        self.used = set()       # 這個 tick 已排的槽
        self.skipped = []       # [{"name", "slot"?, "why"}]
        self.errors = []
        self.drop = []          # 已經起過的 once 項（照 launch 標記比對）：直接刪
        self.changed = False    # tasks.json 要寫回


def plan_round(ctx, items, views, rnd, p):
    """在表鎖內替 rnd 回合選槽與 run，原地更新 items、views 快取及計畫 p，回 None。
    ctx 提供 node 路徑；未知狀態留槽不啟動，錯項只記 p.errors（spec §4.1～4.4、§5.3）。
    once 先排，launch 先記；這裡不 spawn，呼叫者須先把更新後任務表落盤。"""
    def view(slot):
        """取 slot 的判定 View，缺快取就依 ctx／rnd 判定並存入 views。
        讀不到保留 UNKNOWN；starttime 不明可為帶 unsure 的 LIVE（spec §5.4、P2-08）。"""
        if slot not in views:
            views[slot] = aos7_task.judge_resolved(aos7_task.slot_dir(ctx.fnode, slot), ctx.node, slot, rnd)
        return views[slot]

    def free(slot):
        """回 slot 是否本回合未佔用且確知空槽或已結束；未知／活著一律 False。
        這是准入判斷，不把「不知道」說成「已結束」（spec §0、§5.3 不變條件二）。"""
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
    # spec §6：restart 的 once 先佔槽，避免同名 keep 搶先啟動；used 保證一槽一回合只起一次。
    order = [i for i in valid if i.get("mode") == "once"] + [i for i in valid if i.get("mode", "each") != "once"]
    for item in order:
        name, mode = item["name"], item.get("mode", "each")
        if item.get("enabled", True) is False or rnd < item.get("from_round", 1):
            continue
        # until_round（使用者 10-04）：回合數超過它就不再起新 run（跟 from_round 對稱；已在跑的不殺，要收由 kernel 自己 kill）。
        # 用途：分配者掛了，使用權照樣到期。項目與槽留著，跟 enabled:false 一樣。
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
                # spec §4.4、P2-02：birth 同 run 就視為交接已開始；可能沒跑過，但不得再起第二份。
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
    """替 views 中已知 run 的活槽處理加掛請求，ctx 提供空間及 node 路徑。
    回附 run id 的回條清單；單槽例外變失敗回條，UNKNOWN 槽不處理。
    mount_allow 讀不到時目前沿用未設定值 None（spec §4.5 的根內預設許可）。"""
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
    """持有 root／node_id 的目錄 fd，呼叫 fn(fnode, node)，回其結果或 gone 的副本。
    fnode 是 /proc/self/fd/N，node 是字串路徑；fd 讓搬移後仍操作原目錄（spec §2.5）。

    開 node 時：
    - 確定不存在（ENOENT／ENOTDIR），或 node 本身被換成符號連結（O_NOFOLLOW → ELOOP）→ gone。這是「不沿連結寫出空間根」的
      最小保險；路徑中間段被換成符號連結是誤用（spec §11），不再每次重驗整條路徑。
    - 其他錯誤（EIO、ESTALE、EACCES…）＝看不到 → 丟 Unknown（退出碼 3），不當 gone。
    動作中 .aos 確定消失也回 gone，其餘例外外拋。fd 最後關閉；不沿舊字串路徑重建被刪掉的 node（P2-05）。"""
    node = node_path(root, node_id)
    try:
        inject("node-open", node)
        nfd = os.open(node, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as e:
        if is_gone(e) or e.errno == errno.ELOOP:
            return dict(gone)
        raise Unknown("看不到 node %s：%r" % (node_id, e)) from None
    fnode = FD_PREFIX + str(nfd)
    try:
        try:
            # spec §1、P2-05：登記不要求 .aos 預先存在，經 fd 建立才不會復活已搬走的舊路徑。
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


def next_round(fnode):
    """讀 fnode 下的回合檔，回 (新回合數, 錯誤清單)（spec §2.2、§3、P2-06；A2-02）。判定只用 read_round：

    - 明確 `open: false` → round+1。
    - `open: true` → 丟 Unknown：上一回合還開著，tick 不自己開下一回合（不變條件一，daemon 會先 tock 收掉）。
    - 讀不到、半寫、缺 open、型別不對 → 丟 Unknown：分不出上一回合關了沒，**不再用 last-round.json 接著數**
      （那樣會把還開著的同號回合再開一次、蓋掉它的 reaped／started；A2-02）。請人確認後寫回 round.json。
    - 不存在 → 用 last-round.json 的 round 接著數；last-round.json 也不存在從 1 起；它讀不到或壞掉丟 Unknown（不從 1 重數）。"""
    st, r, why = read_round(os.path.join(fnode, ".aos", "round.json"))
    if st == ROUND_CLOSED:
        return r["round"] + 1, []
    if st == ROUND_OPEN:
        raise Unknown("第 %d 回合還開著（round.json open: true），先 tock 收掉才開下一回合" % r["round"])
    if st != ROUND_NONE:
        raise Unknown(why)
    lst, lr = read_json3(os.path.join(fnode, ".aos", "last-round.json"), strict=True)   # A3-03：不是一般檔＝不知道
    if lst == MISSING:
        return 1, []
    if lst == OK and isinstance(lr, dict) and is_int(lr.get("round")):
        return lr["round"] + 1, ["round.json 不見了，從 last-round.json 的 %d 接著數" % lr["round"]]
    raise Unknown("round.json 不見了，last-round.json 也%s；請人寫回 round.json（例如 {\"round\": N, \"open\": false}）"
                  % ("讀不到：%s" % lr if lst == IO else "不能用"))


def tick(root, node_id):
    """替空間 root 的 node_id 開一次回合，回 round／started／tasks_rev 結果（spec §4.2）。
    node 開不了回 gone，舊世代回 stale；推定不了丟 Unknown，交 main 回退出碼 3。
    呼叫者 daemon 先確認舊回合已關（§2.2 不變條件一），此入口負責 fd 與動作鎖。"""
    root = os.path.realpath(root)   # 空間根本身經過連結也照實際位置

    def act(fnode, node):
        """以 fnode（持有的 fd 路徑）、node（原字串路徑）在動作鎖內跑 tick，回結果。
        拿鎖後比世代，舊 daemon 的動作回 stale，不繼續改回合（spec §2.5）。"""
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "started": [], "stale": True}
            return _tick(root, node_id, node, fnode)
    return held_node(act, root, node_id, GONE)


def _tick(root, node_id, node, fnode):
    """在已持有動作鎖下開回合、處理控制／加掛並起任務，回 round／started／tasks_rev。
    root、node_id 是空間識別，node 是原路徑，fnode 是持有的 fd 路徑（spec §4.2）。
    開回合前無法讀回合或列槽丟 Unknown；開後的單項錯誤記 tasks_error，其他項繼續。"""
    rpath = os.path.join(fnode, ".aos", "round.json")
    rnd, errs = next_round(fnode)
    sweep_tmp(os.path.join(fnode, ".aos"))   # A2-07：拿著 action.lock 時清掉寫者已死的原子寫暫存檔
    # A3-08：上一回合關上時有沒寫進去的 tock.json（round.json 的 notify_errors），開下一回合前補一次；還補不上的記進 tasks_error
    import aos7_tock
    owed = aos7_tock.retry_notify(fnode, node, read_json(rpath))
    if owed:
        errs.append("第 %d 回合欠的 tock.json 還補不上：%s" % (rnd - 1, json.dumps(owed, ensure_ascii=False)[:300]))
    _slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s" % lerr)
    # spec §0、§4.2、P2-09：開回合前先確認能列槽，不把 I/O 失敗當成沒有任務。
    state = {"round": rnd, "open": True, "tick_at": now(), "tock_at": None, "started": [], "ctl": [], "mounts": []}
    write_json(rpath, state)
    test_point("tick-opened")   # P2-15：保留可重現卡住動作的測試鉤子，供 daemon 逾時恢復驗證。
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
        # spec §4.2～4.3：先鎖表完成准入與 launch 落盤，放鎖才 spawn，避免整段起程序佔住共用表。
        with locked(tpath, LOCK_WAIT):
            items, lerrs, rev = load_items(fnode)
            p.errors += lerrs
            plan_round(ctx, items, views, rnd, p)
            if p.changed:
                test_point("before-launch")
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
    claimed = set()   # spec §2.7：同一 tick 的多項 subroot 不可重複認領，子 daemon 尚未拿鎖也要擋。
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
    # spec §4.4：spawn 交接成功才刪 once；若先刪、再 spawn 時被殺，任務會無痕漏掉。
    if once_started:
        try:
            edit_json(tpath, lambda t: _drop_launched(t, once_started), timeout=LOCK_WAIT)
        except (LockTimeout, ValueError) as e:
            # 刪不掉沒關係：下一個 tick 照 launch 標記比對 birth.json，知道已經起了就刪（4.4）
            state.setdefault("tasks_error", []).append("起完的 once 項這回合沒刪成：%s" % e)
        test_point("after-once-delete")
    state["started"] = started
    write_json(rpath, state)
    return {"round": rnd, "started": started, "tasks_rev": rev}


def _raw_items(t):
    """從已讀 JSON 值 t 取 tasks 清單；回原 list，格式不符回 None，不做檔案 I/O。"""
    items = t.get("tasks") if isinstance(t, dict) else None
    return items if isinstance(items, list) else None


def _rewrite(tpath, items, p):
    """在表鎖內重組 tpath 任務表並回新物件，實際寫入由呼叫者做（spec §4.3）。
    items 是已加 launch 的物件清單，p.drop 是要移除的原物件；其餘欄位與非物件項位置保留。
    重讀值不是物件時以空表為基底；本函式不重新驗證起動計畫。"""
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
    """從最新任務表 t 刪除 launch 的 slot＋run 符合 started 配對清單的 once，回新表。
    格式不合或沒有項目可刪回 None，讓 edit_json 不寫回（spec §4.2 第 6 步、§4.4）。
    比對起動身分而非列表位置，避免 spawn 期間別人增刪表後刪錯項。"""
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
    """解析 argv（None 用命令列）的 root／node-id，跑 tick 並印 JSON。
    回 0 表示完成或 gone／stale，1 表示用法錯，3 表示 Unknown（spec §4.2、P2-09）。"""
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
