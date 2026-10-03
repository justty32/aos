"""reduce 任務，兩種：

    python3 reduce.py same   同回合：等 round.json 的 started 收齊（含自己），再等每個 map 的 exit.json
    python3 reduce.py next   下一回合：讀 rounds.jsonl 上一回合那行（started／ended／alive），不夠的再看 exit.json

結果寫 `<node>/out/r<批的回合>/reduce-<same|next>.json`。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import aos7_fs as fs  # noqa: E402

how = sys.argv[1]
node, task, tid = os.environ["AOS7_NODE"], os.environ["AOS7_TASK"], os.environ["AOS7_TID"]
tasks_dir = os.path.join(node, ".aos", "tasks")
rnd = fs.read_json(os.path.join(task, "birth.json"))["round"]
t0 = time.monotonic()


def name_of(t):
    return (fs.read_json(os.path.join(tasks_dir, t, "birth.json"), {}) or {}).get("name")


def wait_exit(tids, timeout=8.0):
    """沒有「這批都結束了」的訊號：只能一個一個輪詢 exit.json。"""
    end, codes = time.monotonic() + timeout, {}
    while time.monotonic() < end:
        for t in tids:
            if t not in codes:
                ex = fs.read_json(os.path.join(tasks_dir, t, "exit.json"))
                if ex is not None:
                    codes[t] = ex.get("code")
        if len(codes) == len(tids):
            break
        time.sleep(0.01)
    return codes


def collect(batch_round, maps, codes, extra):
    out_dir = os.path.join(node, "out", "r%d" % batch_round)
    ok, total = 0, 0
    for f in os.listdir(out_dir) if os.path.isdir(out_dir) else []:
        if f.endswith(".json") and f[:-5].isdigit():
            ok += 1
            total += fs.read_json(os.path.join(out_dir, f), {}).get("sum", 0)
    res = dict({"by": tid, "batch_round": batch_round, "n_maps": len(maps), "ok_files": ok, "sum": total,
                "failed": sorted([t, c] for t, c in codes.items() if c != 0),
                "unknown": sorted(t for t in maps if t not in codes),
                "waited_ms": round((time.monotonic() - t0) * 1000)}, **extra)
    fs.write_json(os.path.join(out_dir, "reduce-%s.json" % how), res)


if how == "same":
    # round.json 的 started 是 tick 起完全部才寫的；自己出現在裡面＝清單完整了
    while True:
        st = fs.read_json(os.path.join(node, ".aos", "round.json"), {}) or {}
        if st.get("round") == rnd and tid in st.get("started", []):
            break
        if time.monotonic() - t0 > 5:
            break
        time.sleep(0.005)
    seen_ms = round((time.monotonic() - t0) * 1000)
    maps = [t for t in st.get("started", []) if name_of(t) == "map"]
    codes = wait_exit(maps)
    collect(rnd, maps, codes, {"started_seen_ms": seen_ms})
else:
    prev = rnd - 1
    line = None
    for r in fs.tail_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), 5):
        if r.get("round") == prev:
            line = r
    if line is None:
        sys.exit(0)
    maps = [t for t in line.get("started", []) if name_of(t) == "map"]
    from_line = {e["tid"]: e.get("code") for e in line.get("ended", []) if e.get("tid") in maps}
    codes = dict(from_line)
    codes.update(wait_exit([t for t in maps if t not in from_line]))
    collect(prev, maps, codes, {"known_from_rounds_line": len(from_line),
                                "alive_at_tock": len([t for t in line.get("alive", []) if t in maps])})
