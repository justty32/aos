"""工具包的任務端函式庫：任務自己用的小函式（不在核心的任何迴圈裡；spec 第 4.5、5.5 節）。

- `task_env()`：從環境變數讀自己是誰。
- `wait_tock(...)`：等 `$AOS7_TASK/tock.json` 的回合數變大（S-11）。
- `resolver(taskdir)`：空間路徑 → 經過掛載點的實際路徑。
- `request(taskdir, path, ...)`：執行中加掛的請求（寫 `mount-req/`，tick 審核）。
- `read_jsonl(path)`：讀流水帳（歷史、事件），壞行跳過。
- `decl_of(birth)`：birth.json 的 mounts → 原本的宣告（控制包、once 保證包照 birth 重起時用）。

只讀寫任務自己的槽（tock.json、birth.json、mount-req／mount-done）；核心不 import 這個檔。
用法：把 `proto7-2/modules/tools` 與 `proto7-2/lib` 加進 sys.path 再 import。
"""
import json
import os
import time

from aos7_fs import read_json, write_json
from aos7_mount import DONE, REQ, _norm, req_name


def task_env():
    """任務從環境變數讀自己是誰（spec 5.5）。缺了丟 KeyError。

    無參數；回 root／node／node_id／task／tid／run 字典，run 轉成整數，格式錯誤拋 ValueError。"""
    e = os.environ
    return {"root": e["AOS7_ROOT"], "node": e["AOS7_NODE"], "node_id": e["AOS7_NODE_ID"],
            "task": e["AOS7_TASK"], "tid": e["AOS7_TID"], "run": int(e["AOS7_RUN"])}


def wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None):
    """等 tock.json 的 round 比 last_round 大，回新的 round；逾時回 None（S-11）。

    run＝這次執行的 run（預設取環境 AOS7_RUN）：tock.json 的 `run` 對不上（上一個 run 沒清乾淨的）當不存在（spec 5.1）。

    task_dir 是槽路徑、last_round 是已見回合；poll 是輪詢秒數、timeout 是等待上限秒數，
    None 表示不設上限。讀不到、格式壞或 run 不合就繼續等；不確定不假造回合（spec §5.5）。"""
    if run is None and os.environ.get("AOS7_RUN", "").isdigit():
        run = int(os.environ["AOS7_RUN"])
    path = os.path.join(task_dir, "tock.json")
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        t = read_json(path)
        # spec §5.1、§5.5：槽會重用，run 不符的舊通知不能讓新任務誤認已過一回合。
        if isinstance(t, dict) and isinstance(t.get("round"), int) and t["round"] > last_round \
                and (run is None or t.get("run") == run):
            return t["round"]
        if end is not None and time.monotonic() >= end:
            return None
        time.sleep(poll)


def resolver(taskdir):
    """回一個函式 resolve(空間路徑) → 經過掛載點的實際路徑；沒有掛載蓋到這個路徑就回 None。

    比對以路徑段為單位，取最長的掛載目標（`team/agents/bob/inbox` 蓋得到 `team/agents/bob/inbox/x.json`）。

    taskdir 是槽路徑，回傳上述 resolve 函式；birth.json 缺失或讀不到時採空表，無掛載可解析（spec §4.5）。
    """
    m = (read_json(os.path.join(taskdir, "birth.json"), {}) or {}).get("mounts") or {}
    table = sorted(((v["to"], v["at"]) for v in m.values() if isinstance(v, dict) and "at" in v),
                   key=lambda x: -len(x[0]))

    def resolve(path):
        """將參數 path 空間路徑映到已授予的最長掛載前綴，回傳路徑；首段為 .. 或無對應回 None，不檢查目標存活（spec §4.5）。"""
        p = _norm(path)
        if p.split("/")[0] == "..":
            return None
        for to, at in table:
            # spec §4.5：完整路徑段與最長前綴優先，避免 bob 的掛載誤涵蓋 bobby。
            if to == "." or p == to or p.startswith(to + "/"):
                rest = p if to == "." else p[len(to) + 1:]
                return os.path.join(at, rest) if rest and rest != "." else at
        return None
    return resolve


def request(taskdir, path, why="", name=None):
    """任務這邊用：要 path 能經過掛載點碰到。回 "mounted"／"pending"／"refused: 原因"；需要時寫請求檔（已有就不重寫）。

    被拒的回條留著，同一個名字不再自動重請；要再請就刪掉 mount-done 裡那份。

    taskdir 是槽、path 是目標、why 是理由、name 可指定請求名（spec §4.5）。
    掛載未知時回 pending；讀不到拒絕回條也會當作尚未拒絕而申請，真正准駁仍由 tick 審核。
    """
    if resolver(taskdir)(path) is not None:
        return "mounted"
    n = name or req_name(path)
    done = read_json(os.path.join(taskdir, DONE, n + ".json"))
    if isinstance(done, dict) and not (done.get("result") or {}).get("ok", True):
        return "refused: %s" % done["result"].get("msg")
    req = os.path.join(taskdir, REQ, n + ".json")
    if not os.path.exists(req):
        write_json(req, {"name": n, "path": path, "why": why})
    return "pending"


def read_jsonl(path, with_bad=False):
    """讀流水帳，壞行跳過：逐行各自解碼（append 被殺在多 byte 字元中間也只壞那一行）。with_bad=True 時回 (紀錄, 壞行數)。
    讀不到回已讀到的（通常空清單）。"""
    out, bad = [], 0
    try:
        with open(path, "rb") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line.decode("utf-8")))
                except ValueError:   # UnicodeDecodeError 也是 ValueError
                    bad += 1
    except OSError:
        pass
    return (out, bad) if with_bad else out


def decl_of(birth):
    """birth.json 的 mounts → 原本的宣告 {名字: 空間路徑}（只取掛上了的）。"""
    m = (birth or {}).get("mounts") or {}
    return {n: v["to"] for n, v in m.items() if isinstance(v, dict) and "to" in v and "at" in v}
