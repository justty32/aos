"""歷史 module 的參考實作（spec.md 第 9 節，可選、非核心）：一個普通的 keep 任務，每收到一次 tock 把「上一次」追加到自己的地方。

    tasks.json：{"name": "history", "mode": "keep",
                 "argv": ["python3", "<這個檔>", "--src", "team", "--src", "team/agents/amy", "--max-lines", "1000"],
                 "mounts": {"amy": "team/agents/amy/.aos"}}

- `--src <node id>`：要記哪個 node 的 `.aos/last-round.json`（可多個；預設自己的 node）。先找掛載（resolve 空間路徑），
  沒掛就照 `$AOS7_ROOT/<id>` 讀——要守 S-10「只碰給的資料夾」的話，別的 node 請用 mounts 掛進來。
- `--status`：另外記 daemon 的 `.aosd/status.json` 的 `last_event`（取樣，可能漏；要完整的用 `.aosd/log.on`）。
- 寫到 `<自己的 node>/history/<id 換成 +>.jsonl`（`--out` 改資料夾）；`--max-lines N` 超過就只留最後 N 行（輪替是它自己的事），
  node 歷史與 `daemon-events.jsonl` 都套用（A2-10）。
- 收到 tock 時 last-round.json 已經是那一回合的（tock 先提交總結才寫 tock.json；A2-12），不會讀到上一回合。
- 它是取樣的：看到 `round` 跳號就記一行 `{"gap": [從, 到]}`，補不回來。已記到第幾回合存在槽裡的 state.json（換 run 接得上）。

由 tick 經 aos7-run 啟動（S-10），以 wait_tock 讀槽內 tock.json；這是 P2-16 的參考 module。
另讀／寫 state.json 保存取樣進度，追加 history/*.jsonl；保留期限屬 module，核心只留上一次（spec §0、§8、§9）。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import aos7_mount  # noqa: E402
from aos7_fs import append_jsonl, now, read_json, task_env, wait_tock, write_json  # noqa: E402


def src_path(me, resolve, nid, rel):
    """node id 的 `.aos/<rel>`：有掛載走掛載，否則照空間根讀。

    me 是 task_env 結果、resolve 是掛載解析器、nid 是來源 node id、rel 是 .aos 下檔名；回傳路徑，不驗證存在（spec §9）。
    """
    space = (".aos/" if nid in (".", "") else nid.rstrip("/") + "/.aos/") + rel
    p = resolve(space)
    return p or os.path.join(me["root"], space)


def trim(path, keep):
    """只留最後 keep 行（整份重寫；它自己的檔，自己管大小）。

    path 是自己的歷史檔、keep 是保留行數；回傳 None。讀不到就保留現況，寫入失敗交呼叫端處理（spec §9）。
    """
    try:
        with open(path, "rb") as f:
            lines = f.read().splitlines(True)
    except OSError:
        return
    if len(lines) <= keep:
        return
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "wb") as f:
        f.writelines(lines[-keep:])
    os.replace(tmp, path)


def once(me, args, resolve, st):
    """記一次：每個來源的 last-round.json 有新的 round 就追加；跳號記 gap。回有沒有改 state。

    me 是環境、args 是來源與輸出選項、resolve 是掛載解析器、st 是原地更新的進度；回傳 bool（spec §9）。
    來源不可讀或回合欄位不合就略過、保留已見回合；未知不當作新回合或 gap。
    """
    changed = False
    seen = st.setdefault("seen", {})
    for nid in args.src or [me["node_id"]]:
        lr = read_json(src_path(me, resolve, nid, "last-round.json"))
        if not (isinstance(lr, dict) and isinstance(lr.get("round"), int)):
            continue
        prev = seen.get(nid)
        if prev is not None and lr["round"] <= prev:
            continue
        out = os.path.join(args.out, nid.replace("/", "+") + ".jsonl")
        if prev is not None and lr["round"] > prev + 1:
            # spec §9：核心只留上一次；缺號只能留下 gap，不把沒看見的回合捏成歷史。
            append_jsonl(out, {"gap": [prev + 1, lr["round"] - 1], "at": now()})
        append_jsonl(out, lr)
        if args.max_lines:
            trim(out, args.max_lines)
        seen[nid] = lr["round"]
        changed = True
    if args.status:
        s = read_json(os.path.join(me["root"], ".aosd", "status.json"))
        ev = s.get("last_event") if isinstance(s, dict) else None
        if isinstance(ev, dict) and ev != st.get("last_event"):
            out = os.path.join(args.out, "daemon-events.jsonl")
            append_jsonl(out, ev)
            if args.max_lines:
                trim(out, args.max_lines)   # A2-10：--max-lines 也套在事件歷史
            st["last_event"] = ev
            changed = True
    return changed


def main(argv=None):
    """解析 argv（None 用命令列），以 keep 任務身分等待 tock 並取樣；達 --rounds 限制回 0，預設持續執行（spec §9，P2-16）。"""
    ap = argparse.ArgumentParser(prog="history")
    ap.add_argument("--src", action="append")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--max-lines", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=0, help="收到這麼多次 tock 就結束（0＝一直跑；測試用）")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    me = task_env()
    args.out = args.out or os.path.join(me["node"], "history")
    resolve = aos7_mount.resolver(me["task"])
    spath = os.path.join(me["task"], "state.json")
    # spec §5.1、§8 不變條件三：進度屬任務自己的 state，換 run 不清，避免從頭重記歷史。
    st = read_json(spath, {})
    st = st if isinstance(st, dict) else {}
    last, k = 0, 0
    while not args.rounds or k < args.rounds:
        last = wait_tock(me["task"], last)
        k += 1
        if once(me, args, resolve, st):
            write_json(spath, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
