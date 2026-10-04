"""aos7-tick：開一個回合——round +1、執行任務控制、起任務，印一行 JSON 就結束，不等任務（spec.md 第 4 節）。

由 daemon 每回合呼叫，也可由人手跑；落實 S-09／S-10，控制與加掛見 spec §6／§4。
讀 node 的 timeline.json、tasks.json、spawn 與任務狀態；寫 round.json，透過 task／mount
寫任務出生、控制回條與掛載，消耗 spawn。action.lock／世代由共用 helper 管理（spec §2）。
整個動作的讀寫綁 node fd，實際路徑只供任務環境及掛載記錄使用（spec §4）。

    aos7-tick <root> <node-id>
"""
import json
import os
import signal
import sys
import time

import aos7_mount
import aos7_task
from aos7_fs import FD_PREFIX, action_lock, is_regular, node_path, now, read_json, write_json


def load_items(node):
    """從 node 路徑讀 tasks.json，回 (物件項目清單, 錯誤清單)（spec §4）。

    整份讀不懂當空表並記錯（probes/selfmod 6）；路徑不存在或存在性無法確認時可能不記錯。
    非物件的單項跳過，其他合法物件留給後續欄位驗證。
    """
    path = os.path.join(node, ".aos", "tasks.json")
    if os.path.lexists(path) and not is_regular(path):
        return [], ["tasks.json 不是一般檔（FIFO、資料夾…），當空表"]   # read_json 不讀它（probes/llmops n3）
    t = read_json(path)
    if t is None:
        return [], (["tasks.json 讀不懂（不是 JSON）"] if os.path.exists(path) else [])
    items = t.get("tasks") if isinstance(t, dict) else None
    if not isinstance(items, list):
        return [], ["tasks.json 要是 {\"tasks\": [...]}"] if t != {} else []
    errs = ["tasks[%d] 不是物件" % k for k, i in enumerate(items) if not isinstance(i, dict)]
    return [i for i in items if isinstance(i, dict)], errs


def item_name(item):
    """取項目物件 item 的名字，回非空字串；缺少或型別不對回 "task"（spec §4）。

    與 birth.json 的預設一致，避免 keep 用另一個名字計數（probes/selfmod bug 1）。
    """
    n = item.get("name")
    return n if isinstance(n, str) and n else "task"


def validate(item):
    """驗證項目物件 item 的定義欄位；通過回 None，不合丟 ValueError（spec §4）。

    tasks.json 與 spawn 共用，呼叫者只跳過這一項（probes/chaos B2～B4）；不在這裡讀檔。
    """
    n = item.get("name")
    if n is not None and not (isinstance(n, str) and n):
        raise ValueError("name 要是非空字串，拿到 %r" % (n,))
    if "argv" in item:
        a = item["argv"]
        if not (isinstance(a, list) and a and all(isinstance(x, str) and "\0" not in x for x in a)):
            raise ValueError("argv 要是非空的字串陣列，拿到 %r" % (a,))
    elif not isinstance(item.get("inst"), str):
        raise ValueError("要有 argv（字串陣列）或 inst（字串）")
    for k in ("mounts",):
        if k in item and item[k] is not None and not isinstance(item[k], dict):
            raise ValueError("%s 要是物件" % k)
    if "subroot" in item and not isinstance(item["subroot"], str):
        raise ValueError("subroot 要是字串")
    if "allow_stop" in item and not isinstance(item["allow_stop"], bool):
        raise ValueError("allow_stop 要是 true 或 false，拿到 %r" % (item["allow_stop"],))


def check_item(item):
    """對項目物件 item 做 spec §4 的完整檢查，通過回 None，不對丟 ValueError。
    包含 validate 的定義欄位與排程欄位 from_round／mode／max_live；不在這裡讀檔。
    restart reload 也先過這一關再剝排程欄位（astra-6 G-05）。"""
    validate(item)
    fr = item.get("from_round", 1)
    if isinstance(fr, bool) or not isinstance(fr, int):
        raise ValueError("from_round 要是整數，拿到 %r" % (fr,))
    if item.get("mode", "each") not in ("each", "keep"):
        raise ValueError("mode 要是 each 或 keep，拿到 %r" % (item.get("mode"),))
    ml = item.get("max_live")
    if ml is not None and (isinstance(ml, bool) or not isinstance(ml, int)):
        raise ValueError("max_live 要是整數，拿到 %r" % (ml,))


def should_start(item, rnd, live):
    """依項目 item、本回合 rnd、同名活任務計數 live 回傳是否可起（spec §4）。

    未到起始回合或名額已滿回 False；live 沒有的名字按 0 算，不另判讀取是否可靠。
    欄位型別不對丟 ValueError，交由呼叫者只跳過這一項。
    """
    check_item(item)
    if rnd < item.get("from_round", 1):
        return False
    if item.get("mode", "each") == "keep" and item_name(item) in live:
        return False
    ml = item.get("max_live")
    if ml is not None and live.get(item_name(item), 0) >= ml:   # 同名活任務已到上限：這回合不起（probes/longrun N-3）
        return False
    return True


def live_names(node):
    """掃 node 路徑的活任務，回 {name: 個數}，供 keep／max_live 判斷（spec §4／§5）。

    活性與缺檔沿用 task_state；列不到 tasks 會回空表，birth 讀不到則由 name_of 從 tid 推名。
    """
    names = {}
    for tid in aos7_task.live_tasks(node):
        n = aos7_task.name_of(aos7_task.task_dir(node, tid))
        names[n] = names.get(n, 0) + 1
    return names


def spawn_items(obj):
    """把已讀取的 spawn 內容 obj 轉成物件項目清單（spec §4）。

    支援單項或 `{"batch": [項目, ...]}`（一個檔一次 rename，整批同一回合起；probes/swarm N3）。
    obj 非物件回空清單，batch 的非物件項目略過；欄位合法性留給 should_start。
    """
    if isinstance(obj, dict) and isinstance(obj.get("batch"), list):
        return [i for i in obj["batch"] if isinstance(i, dict)]
    return [obj] if isinstance(obj, dict) else []


def serve_mounts(root, fnode, node=None):
    """審核空間根 root 下活任務的加掛請求，回含 tid 的結果清單（spec §4；S-23、M-6）。

    tasks.json 的 `mount_allow` 前綴清單沒寫或整份讀不到＝全給（仍驗空間邊界）。

    fnode＝讀寫用的 node 路徑（tick 給 `/proc/self/fd/N`），node＝實際路徑（掛載點記在 birth.json 的 `at`）。
    一個任務處理失敗只記在它那筆，其他照做（astra-5 F-06）。"""
    node = node or fnode
    t = read_json(os.path.join(fnode, ".aos", "tasks.json"), {})
    allow = t.get("mount_allow") if isinstance(t, dict) else None
    out = []
    for tid in aos7_task.live_tasks(fnode):
        try:
            for r in aos7_mount.serve(root, aos7_task.task_dir(fnode, tid), allow,
                                      real_taskdir=aos7_task.task_dir(node, tid)):
                out.append(dict(r, tid=tid))
        except Exception as e:   # noqa: BLE001
            out.append({"tid": tid, "name": None, "path": None, "ok": False, "msg": "加掛處理失敗：%r" % (e,)})
    return out


def node_still_there(fnode):
    """檢查 fd 路徑 fnode 的 timeline.json，仍是一般檔時回 None（spec §4）。

    不在、不是一般檔或 stat 失敗皆丟 FileNotFoundError，讓 held_node 收成 gone。
    """
    if not os.path.isfile(os.path.join(fnode, ".aos", "timeline.json")):
        raise FileNotFoundError(fnode)


GONE = {"round": None, "started": [], "ctl": [], "gone": True}


def held_node(fn, root, node_id, gone):
    """抓住 node 目錄的 fd，把 `/proc/self/fd/N`（fnode）交給 fn(fnode, node) 做整個動作（astra-5 F-09）：
    node 被搬走時寫到新位置；被刪掉時寫入失敗（不會在舊路徑建出鬼目錄）→ 回 gone（spec §4）。

    root 是空間根、node_id 是相對路徑；回 fn 的結果或 gone 字典的副本。
    開不了 node（含 I/O 錯誤）或看不到 timeline.json 也回 gone；其他動作例外原樣上拋。
    """
    node = node_path(root, node_id)
    try:
        nfd = os.open(node, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return dict(gone)
    fnode = FD_PREFIX + str(nfd)
    try:
        if not os.path.isfile(os.path.join(fnode, ".aos", "timeline.json")):
            # node 已經不在（刪掉、搬走）：什麼都不寫，免得把資料夾建回來（probes/subtimeline 1、rename N9）
            return dict(gone)
        try:
            return fn(fnode, node)
        except (FileNotFoundError, NotADirectoryError):
            if not os.path.isfile(os.path.join(fnode, ".aos", "timeline.json")):
                return dict(gone)   # 動作中途 node 被刪：寫不進去就收手
            raise
    finally:
        os.close(nfd)


def tick(root, node_id):
    """對空間根 root、相對 node_id 做一次 tick，回 {"round", "started", "ctl"}（spec §2／§4）。

    node 不在或無法開啟多 gone，舊 daemon 的動作多 stale；這兩種不做回合寫入。
    """
    def act(fnode, node):
        """以 fd 路徑 fnode 鎖住動作，node 為實際路徑；回 tick 結果或世代不符的 stale。"""
        # spec §2：鎖住後才比 gen，避免舊 daemon 的排隊動作倒寫新世代的回合。
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "started": [], "ctl": [], "stale": True}
            return _tick(root, node_id, node, fnode)
    return held_node(act, root, node_id, GONE)


def _tick(root, node_id, node, fnode=None):
    """在已拿鎖的 node 開回合、處理控制與啟動，回 {round, started, ctl}（spec §3／§4／§6）。

    root／node_id 定位空間；node 是實際路徑（環境、cwd、掛載點），fnode 是讀寫用的
    `/proc/self/fd/N`（省略時用 node）。回合讀不懂就從流水帳接號；帳也讀不到從 1 起。
    """
    fnode = fnode or node
    rpath = os.path.join(fnode, ".aos", "round.json")
    old = read_json(rpath, {})
    prev = old.get("round") if isinstance(old, dict) else None
    errs = []
    if not isinstance(prev, int) or isinstance(prev, bool):
        lr = aos7_task.last_logged_round(fnode)
        if lr is not None:
            # round.json 壞了：從 rounds.jsonl 最後一行接著數，不從 1 重數、不重號（probes/chaos B6）
            errs.append("round.json 壞了（round=%r），從 rounds.jsonl 的 %d 接著數" % (prev, lr))
            prev = lr
        else:
            prev = 0
    rnd = prev + 1
    state = {"round": rnd, "open": True, "tick_at": now(), "tock_at": None, "started": [], "ctl": [], "mounts": []}
    write_json(rpath, state)
    if os.environ.get("AOS7_TEST_TICK_HANG") == node_id:
        time.sleep(10 ** 6)   # 只給測試：模擬 tick 卡在 I/O（以前用 FIFO 的 tasks.json，現在 read_json 不會卡了）

    # spec §4：先控制再加掛、再起任務，使 restart 寫的 spawn 能在這次 tick 接著啟動。
    state["ctl"] = aos7_task.run_all_ctl(fnode)
    state["mounts"] = serve_mounts(root, fnode, node)

    started = []
    claimed = set()   # 這個 tick 已經認領的子根：同 tick 第二項宣告同一個不起（astra-7 H-02）
    sdir = os.path.join(fnode, ".aos", "spawn")
    live = live_names(fnode)
    # spec §4：先處理 spawn 並即時加計名額，後面的 tasks.json 不會忽略同回合剛起的 keep。
    for fn in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        if not fn.endswith(".json") or fn.startswith("."):
            continue
        path = os.path.join(sdir, fn)
        obj = read_json(path)
        items = spawn_items(obj)
        if not items:
            errs.append("spawn %s：讀不懂或不是項目" % fn)
        elif isinstance(obj, dict) and isinstance(obj.get("batch"), list) and len(items) < len(obj["batch"]):
            errs.append("spawn %s：batch 裡 %d 項不是物件，沒起" % (fn, len(obj["batch"]) - len(items)))
        for item in items:
            try:
                # spawn 也照 mode／max_live（keep 已有同名活的就不起；probes/llmops：補起一份變兩份）；restart 寫的沒有 mode＝each
                if not should_start(dict(item, from_round=1), rnd, live):
                    errs.append("spawn %s：%s 已有活的（keep／max_live），沒起" % (fn, item_name(item)))
                    continue
                tid = aos7_task.start_task(root, node_id, dict(item, spawn=fn), rnd, fnode=fnode, claimed=claimed)
            except Exception as e:   # noqa: BLE001  壞的一項只跳過那項，檔照刪，不變成每回合的毒丸（probes/chaos B3、astra-5 F-06）
                node_still_there(fnode)
                errs.append("spawn %s：%s" % (fn, e))
                continue
            started.append(tid)
            live[item_name(item)] = live.get(item_name(item), 0) + 1
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                os.rename(path, os.path.join(fnode, ".aos", ".spawn-bad-%s-%d" % (fn, rnd)))
            else:
                os.remove(path)   # 起完才刪（spec 第 4 節）：中途被殺，下次 tick 會再起一次，不會無痕丟掉（astra-4 I-02）
        except OSError as e:
            errs.append("spawn %s 刪不掉：%s" % (fn, e))

    items, errs2 = load_items(fnode)
    errs += errs2
    for k, item in enumerate(items):
        label = item.get("name") if isinstance(item.get("name"), str) and item.get("name") else "tasks[%d]" % k
        try:
            if not should_start(item, rnd, live):
                continue
        except (ValueError, TypeError) as e:   # 壞的一項跳過、記下來，其他項照起（probes/selfmod 6、bug 2）
            errs.append("%s：%s" % (label, e))
            continue
        try:
            started.append(aos7_task.start_task(root, node_id, item, rnd, fnode=fnode, claimed=claimed))
        except Exception as e:   # noqa: BLE001  起不來的一項只記它，其他項照起（astra-5 F-06）
            node_still_there(fnode)
            errs.append("%s：%s" % (label, e))
            continue
        live[item_name(item)] = live.get(item_name(item), 0) + 1

    state["started"] = started
    if errs:
        state["tasks_error"] = errs
    write_json(rpath, state)
    return {"round": rnd, "started": started, "ctl": state["ctl"]}


def main(argv=None):
    """薄入口呼叫；argv 為 root、node-id（None 取命令列），印 JSON，正常回 0、用法錯回 1。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tick <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 不用 SIG_IGN（會傳給起的任務）；很快結束；被一起 kill（子 daemon 的程序群組）時做完這回合（probes/nest3 N1），SIGKILL 保底
    r = tick(argv[0], argv[1])
    print(json.dumps({k: r[k] for k in ("round", "started", "gone", "stale") if k in r}, ensure_ascii=False))
    return 0
