"""控制包：restart／reload 在請求端做——先在 tasks.json 加一項釘同槽的 once，再寫核心的 kill（帶 run）。
spec 見同資料夾的 README.md。kernel 可以直接 import（把 proto7-2/modules/control、modules/tools 與 lib 加進 sys.path）。

    restart(node, slot, why="", reload=False, req_id=None, by=None) → {"ok", "msg", "run", "req_id", "ctl", "once", "diff"?, "outcome"?}

核心只認得 kill；這裡只用核心公開的檔案：birth.json、tasks.json（拿表鎖、G1 三態）、槽的 ctl.json。
"""
import os
import uuid

from aos7_fs import N, OK, Unknown, edit_json, fact, test_point, write_json
from aos7_taskside import decl_of

DEF_KEYS = ("argv", "inst", "x")                               # 從 birth 抄回去的定義（外加 name、mounts）
SCHED_KEYS = ("mode", "from_round", "until_round", "max_live", "enabled", "launch", "slot")   # reload 時去掉的排程欄


def dyn_mounts(birth):
    """birth.json 裡執行中加掛的（核心標了 dyn）→ {名字: 空間路徑}。"""
    m = (birth or {}).get("mounts") or {}
    return {n: v["to"] for n, v in m.items() if isinstance(v, dict) and v.get("dyn") and "to" in v and "at" in v}


def reload_item(node, birth):
    """reload：tasks.json 裡同名的第一個非 once 項，完整驗證過（核心 aos7_tick.check_item）才用，去掉排程欄位；
    掛載＝項目宣告加上沒被宣告接管的執行中加掛。回 (定義, None) 或 (None, 說明)；讀取故障丟 Unknown。"""
    import aos7_tick
    st, t = fact(os.path.join(node, ".aos", "tasks.json"))
    if st != OK:
        if st != N:
            raise Unknown("tasks.json %s" % t, kind=st)
        return None, "tasks.json %s" % ("不存在" if st == N else t)
    items = t.get("tasks") if isinstance(t, dict) else None
    found = [i for i in items or [] if isinstance(i, dict) and i.get("name") == birth.get("name") and i.get("mode") != "once"]
    if not found:
        return None, "tasks.json 沒有名為 %s 的非 once 項目；不加 reload 會照出生時的定義重起" % birth.get("name")
    try:
        aos7_tick.check_item(found[0])
    except ValueError as e:
        return None, "tasks.json 的 %s 不合格：%s" % (birth.get("name"), e)
    item = {k: v for k, v in found[0].items() if k not in SCHED_KEYS}
    decl = item.get("mounts") or {}
    item["mounts"] = dict({n: to for n, to in dyn_mounts(birth).items() if n not in decl}, **decl)
    return item, None


def def_diff(birth, item):
    """birth 的舊定義與 item 的新定義差在哪：{欄位: {old, new}}。"""
    out = {}
    for k in ("argv", "inst", "mounts", "x"):
        old = decl_of(birth) if k == "mounts" else birth.get(k)
        new = (item.get(k) or {}) if k == "mounts" else item.get(k)
        if old != new:
            out[k] = {"old": old, "new": new}
    return out


class Done(Exception):
    """鎖內發現這件 restart 已經做完（或原 run 已經換掉）：不改表，帶著重讀到的 birth 跳出 edit_json。"""
    def __init__(self, birth):
        super().__init__()
        self.birth = birth


def done(slot, birth, req_id):
    """「已經重起過、沒再做」的回傳。"""
    rid, x = "%s#%d" % (slot, birth["run"]), birth.get("x") or {}
    msg = ("這件 restart 已經起了 %s（%s 的重起），沒再做" % (rid, x.get("restart_of")) if x.get("req_id") == req_id
           else "槽已經換成 %s，要重起的那次不在了，沒再做" % rid)
    return {"ok": True, "msg": msg, "run": rid, "req_id": req_id, "once": "done"}


def restart(node, slot, why="", reload=False, req_id=None, by=None):
    """重起 node 上 slot 現在的 run：同一個槽、新 run，任務自己寫的 state 接得上。回結果 dict（`ok` 是請求端做完了沒；
    `ok:false` 的 `outcome` 區分 unknown 與 refused，不改其他欄位的意義）。

    1. 讀 birth.json 拿 run 與定義（reload 改取 tasks.json 同名項）；讀不到、壞掉＝不做。
    2. 拿 tasks.json.lock 加一項 once：`slot` 釘同槽、`x.restart_of`＝原 run id、`x.req_id`＝這件請求的 id；表上已有同槽同 req_id
       的不重加，槽現在的 birth 已帶同一個 req_id（已經重起過）就什麼都不做——重送同一件請求用同一個 req_id。
       鎖內再讀一次 birth：已帶同 req_id 或 run 已不是第 1 步那次（並行的同一件請求先做完了）＝不加、回 done（A4-02）。
       表或鎖內的 birth 讀不到、壞掉＝拒寫（G1），不做第 3 步。
    3. 寫槽的 ctl.json＝`{"op": "kill", "run": 原 run}`。tick／tock 收掉它之後，下一個 tick 先處理 once、在同一個槽起新 run。

    在 2、3 之間死掉：once 項等槽空才起（busy），沒有「殺了沒重起」；重試責任在請求端（用同一個 req_id 再呼叫一次）。"""
    node = os.path.abspath(node)
    fslot = os.path.join(node, ".aos", "tasks", slot)
    req_id = req_id or uuid.uuid4().hex
    st, birth = fact(os.path.join(fslot, "birth.json"))
    if not (st == OK and isinstance(birth, dict) and isinstance(birth.get("run"), int) and birth.get("name")):
        return {"ok": False, "msg": "槽 %s 的 birth.json %s，不知道要重起哪一次，沒做" % (
            slot, birth if st not in (OK, N) else ("不存在" if st == N else "內容不合")), "req_id": req_id,
            "outcome": "refused" if st == N else "unknown"}
    run = birth["run"]
    rid = "%s#%d" % (slot, run)
    if (birth.get("x") or {}).get("req_id") == req_id:
        # 這件請求已經重起出現在這個 run（請求端重試時 once 早就起了、從表上刪了）：不再加、不再 kill
        return done(slot, birth, req_id)
    diff = None
    if reload:
        try:
            item, why_not = reload_item(node, birth)
        except Unknown as e:
            return {"ok": False, "msg": "%s；沒做（沒 kill）" % e, "run": rid, "req_id": req_id,
                    "outcome": "unknown"}
        if item is None:
            return {"ok": False, "msg": "%s；沒做（沒 kill）" % why_not, "run": rid, "req_id": req_id,
                    "outcome": "refused"}
        diff = def_diff(birth, item)
    else:
        item = {k: birth[k] for k in DEF_KEYS if k in birth}
        item["mounts"] = decl_of(birth)
    item.update({"name": birth["name"], "mode": "once", "slot": slot,
                 "x": dict(item.get("x") or {}, restart_of=rid, req_id=req_id)})
    dup = []

    def add(t):
        # 第 1 步的 birth 是鎖外讀的快照：鎖內重讀，同 req_id 的另一個呼叫可能已經在這之間重起完了（A4-02）
        st, cur = fact(os.path.join(fslot, "birth.json"))
        if not (st == OK and isinstance(cur, dict) and isinstance(cur.get("run"), int)):
            raise Unknown("槽 %s 的 birth.json 不能用（%s），沒加" % (slot, cur if st not in (OK, N) else st), kind="bad")
        if (cur.get("x") or {}).get("req_id") == req_id or cur["run"] != run:
            raise Done(cur)
        t = {"tasks": []} if t is None else t
        if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
            raise Unknown("tasks.json 不是 {\"tasks\": [...]}，沒加", kind="bad")
        if any(isinstance(i, dict) and i.get("slot") == slot and (i.get("x") or {}).get("req_id") == req_id
               for i in t.get("tasks", [])):
            dup.append(True)
            return None
        return dict(t, tasks=list(t.get("tasks", [])) + [item])
    try:
        edit_json(os.path.join(node, ".aos", "tasks.json"), add, timeout=1.0)
    except Done as e:
        return done(slot, e.birth, req_id)
    except Unknown as e:
        return {"ok": False, "msg": "%s；沒做（沒 kill）" % ("tasks.json.lock 一秒內拿不到" if e.kind == "lock" else e),
                "run": rid, "req_id": req_id, "outcome": "unknown"}
    test_point("restart-after-append")
    ctl = os.path.join(fslot, "ctl.json")
    write_json(ctl, {"op": "kill", "run": run, "by": by or "control", "why": why or "restart", "id": req_id})
    out = {"ok": True, "msg": "once 項%s（slot %s），已送 kill %s" % ("上次已加過、沒再加" if dup else "已加進 tasks.json",
                                                                   slot, rid),
           "run": rid, "req_id": req_id, "ctl": ctl, "once": "dup" if dup else "added"}
    if diff is not None:
        out["diff"] = diff
    return out
