"""aos7-tick：開一個回合——round +1、執行任務控制、起任務，印一行 JSON 就結束，不等任務（spec.md 第 4 節）。

    aos7-tick <root> <node-id>
"""
import json
import os
import signal
import sys

import aos7_mount
import aos7_task
from aos7_fs import action_lock, node_path, now, read_json, write_json


def load_items(node):
    """讀 tasks.json 的項目，回 (項目清單, 錯誤清單)。整份讀不懂當空表並記錯（probes/selfmod 6）。"""
    path = os.path.join(node, ".aos", "tasks.json")
    t = read_json(path)
    if t is None:
        return [], (["tasks.json 讀不懂（不是 JSON）"] if os.path.exists(path) else [])
    items = t.get("tasks") if isinstance(t, dict) else None
    if not isinstance(items, list):
        return [], ["tasks.json 要是 {\"tasks\": [...]}"] if t != {} else []
    errs = ["tasks[%d] 不是物件" % k for k, i in enumerate(items) if not isinstance(i, dict)]
    return [i for i in items if isinstance(i, dict)], errs


def item_name(item):
    """項目的名字（沒寫是 "task"，跟 birth.json 一樣；probes/selfmod bug 1）。"""
    n = item.get("name")
    return n if isinstance(n, str) and n else "task"


def should_start(item, rnd, live):
    """這一項本回合要不要起；欄位型別不對丟 ValueError（只跳過這一項）。"""
    fr = item.get("from_round", 1)
    if isinstance(fr, bool) or not isinstance(fr, int):
        raise ValueError("from_round 要是整數，拿到 %r" % (fr,))
    if rnd < fr:
        return False
    mode = item.get("mode", "each")
    if mode not in ("each", "keep"):
        raise ValueError("mode 要是 each 或 keep，拿到 %r" % (mode,))
    if mode == "keep" and item_name(item) in live:
        return False
    ml = item.get("max_live")
    if ml is not None:
        if isinstance(ml, bool) or not isinstance(ml, int):
            raise ValueError("max_live 要是整數，拿到 %r" % (ml,))
        if live.get(item_name(item), 0) >= ml:   # 同名活任務已到上限：這回合不起（probes/longrun N-3）
            return False
    if not (("argv" in item and isinstance(item["argv"], list)) or isinstance(item.get("inst"), str)):
        raise ValueError("要有 argv（陣列）或 inst（字串）")
    return True


def live_names(node):
    """活任務的 {name: 個數}（keep、max_live 判斷用）。"""
    names = {}
    for tid in aos7_task.live_tasks(node):
        n = aos7_task.name_of(aos7_task.task_dir(node, tid))
        names[n] = names.get(n, 0) + 1
    return names


def spawn_items(obj):
    """一個 spawn 檔的內容 → 項目清單：單一項目，或 `{"batch": [項目, ...]}`（一個檔一次 rename，整批同一回合起；probes/swarm N3）。"""
    if isinstance(obj, dict) and isinstance(obj.get("batch"), list):
        return [i for i in obj["batch"] if isinstance(i, dict)]
    return [obj] if isinstance(obj, dict) else []


def serve_mounts(root, node):
    """審核活任務的加掛請求（S-23、M-6）：tasks.json 的 `mount_allow` 前綴清單，沒寫＝全給。"""
    t = read_json(os.path.join(node, ".aos", "tasks.json"), {})
    allow = t.get("mount_allow") if isinstance(t, dict) else None
    out = []
    for tid in aos7_task.live_tasks(node):
        for r in aos7_mount.serve(root, aos7_task.task_dir(node, tid), allow):
            out.append(dict(r, tid=tid))
    return out


def tick(root, node_id):
    """做一次 tick，回 {"round", "started", "ctl"}（node 不在多 `gone`，舊 daemon 的動作多 `stale`，都什麼都不寫）。"""
    node = node_path(root, node_id)
    if not os.path.isfile(os.path.join(node, ".aos", "timeline.json")):
        # node 已經不在（刪掉、搬走）：什麼都不寫，免得把資料夾建回來（probes/subtimeline 1、rename N9）
        return {"round": None, "started": [], "ctl": [], "gone": True}
    with action_lock(root, node) as ok:
        if not ok:
            return {"round": None, "started": [], "ctl": [], "stale": True}
        return _tick(root, node_id, node)


def _tick(root, node_id, node):
    rpath = os.path.join(node, ".aos", "round.json")
    old = read_json(rpath, {})
    rnd = (old.get("round", 0) if isinstance(old, dict) and isinstance(old.get("round"), int) else 0) + 1
    state = {"round": rnd, "open": True, "tick_at": now(), "tock_at": None, "started": [], "ctl": [], "mounts": []}
    write_json(rpath, state)

    state["ctl"] = aos7_task.run_all_ctl(node)
    state["mounts"] = serve_mounts(root, node)

    started = []
    sdir = os.path.join(node, ".aos", "spawn")
    for fn in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        if not fn.endswith(".json"):
            continue
        obj = read_json(os.path.join(sdir, fn))
        for item in spawn_items(obj):
            started.append(aos7_task.start_task(root, node_id, dict(item, spawn=fn), rnd))
        os.remove(os.path.join(sdir, fn))   # 起完才刪（spec 第 4 節）：中途被殺，下次 tick 會再起一次，不會無痕丟掉（astra-4 I-02）

    live = live_names(node)
    items, errs = load_items(node)
    for k, item in enumerate(items):
        try:
            if not should_start(item, rnd, live):
                continue
        except ValueError as e:   # 壞的一項跳過、記下來，其他項照起（probes/selfmod 6、bug 2）
            errs.append("%s：%s" % (item.get("name", "tasks[%d]" % k), e))
            continue
        started.append(aos7_task.start_task(root, node_id, item, rnd))
        live[item_name(item)] = live.get(item_name(item), 0) + 1

    state["started"] = started
    if errs:
        state["tasks_error"] = errs
    write_json(rpath, state)
    return {"round": rnd, "started": started, "ctl": state["ctl"]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tick <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 不用 SIG_IGN（會傳給起的任務）；很快結束；被一起 kill（子 daemon 的程序群組）時做完這回合（probes/nest3 N1），SIGKILL 保底
    r = tick(argv[0], argv[1])
    print(json.dumps({k: r[k] for k in ("round", "started", "gone", "stale") if k in r}, ensure_ascii=False))
    return 0
