#!/usr/bin/env python3
"""規則判官（假判官）：通用 kernel（aos_kernel.py）的判官格，純規則、跟 agent 判官同一個介面。純標準庫。

    python3 judge_rules.py      （stdin＝kernel 的 state 窗子集 queue／running／slots／budget；stdout 一份 {"run", "defer", "reject"}）

用到 state 窗的 queue {id: {priority, _metainfo, …}} 與 slots {資源: {total, used}}。規則：human 的信先排，
再看級數（low／normal／high＝-1／0／1，數字取正負號），再先來後到（id 字典序）；每種資源補滿空格的進 run，
其餘進 defer。不 reject。
"""
import json
import sys

LEVELS = {"low": -1, "normal": 0, "high": 1}


def level(pri):
    v = (pri or {}).get("level") if isinstance(pri, dict) else None
    if isinstance(v, str):
        return LEVELS.get(v.lower(), 0)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (v > 0) - (v < 0)
    return 0


def decide(snap):
    slots = snap.get("slots") or {}
    left = {k: v.get("total", 0) - v.get("used", 0) for k, v in slots.items()}
    queue = snap.get("queue") or {}

    def res(x):
        meta = queue[x].get("_metainfo")
        return meta.get("resource") if isinstance(meta, dict) else None

    out = {"run": [], "defer": [], "reject": []}
    for x in sorted(queue, key=lambda x: (res(x) != "human", -level(queue[x].get("priority")), x)):
        k = res(x)
        go = left.get(k, 0) > 0
        if go:
            left[k] -= 1
        out["run" if go else "defer"].append(x)
    return out


if __name__ == "__main__":
    print(json.dumps(decide(json.load(sys.stdin)), ensure_ascii=False))
