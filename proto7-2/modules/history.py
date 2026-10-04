"""歷史 module 的參考實作（spec.md 第 9 節，可選、非核心）：一個普通的 keep 任務，每收到一次 tock 把「上一次」追加到自己的地方。

    tasks.json：{"name": "history", "mode": "keep",
                 "argv": ["python3", "<這個檔>", "--src", "team", "--src", "team/agents/amy", "--max-lines", "1000"],
                 "mounts": {"amy": "team/agents/amy/.aos"}}

- `--src <node id>`：要記哪個 node 的 `.aos/last-round.json`（可多個；預設自己的 node）。先找掛載（resolve 空間路徑），
  沒掛就照 `$AOS7_ROOT/<id>` 讀——要守 S-10「只碰給的資料夾」的話，別的 node 請用 mounts 掛進來。
- `--status`：另外記 daemon 的 `.aosd/status.json` 的 `last_event`（取樣，可能漏；要完整的用 `.aosd/log.on`）。
- 寫到 `<自己的 node>/history/<id 換成 +>.jsonl`（`--out` 改資料夾）；`--max-lines N` 超過就只留最後 N 行（輪替是它自己的事）。
- 它是取樣的：看到 `round` 跳號就記一行 `{"gap": [從, 到]}`，補不回來。已記到第幾回合存在槽裡的 state.json（換 run 接得上）。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import aos7_mount  # noqa: E402
from aos7_fs import append_jsonl, now, read_json, task_env, wait_tock, write_json  # noqa: E402


def src_path(me, resolve, nid, rel):
    """node id 的 `.aos/<rel>`：有掛載走掛載，否則照空間根讀。"""
    space = (".aos/" if nid in (".", "") else nid.rstrip("/") + "/.aos/") + rel
    p = resolve(space)
    return p or os.path.join(me["root"], space)


def trim(path, keep):
    """只留最後 keep 行（整份重寫；它自己的檔，自己管大小）。"""
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
    """記一次：每個來源的 last-round.json 有新的 round 就追加；跳號記 gap。回有沒有改 state。"""
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
            append_jsonl(os.path.join(args.out, "daemon-events.jsonl"), ev)
            st["last_event"] = ev
            changed = True
    return changed


def main(argv=None):
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
