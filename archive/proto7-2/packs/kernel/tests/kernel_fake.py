"""測試用的薄入口：在內建規則外再註冊幾條假規則（spec §5「薄入口注入」），再跑 aos7_kernel.main。

- `echo`：`from` ≤ tock ≤ `until`（預設 1～不限）時，把 `emit` 裡的候選照抄出去；`"run": "$run"` 換成快照裡該目標 birth 的 run（讀不到就略過那筆）。
  每筆（含換好的 run）只出一次，記在 rstate["fired"]；`"once": false` 每個 tock 都出。
- `boom`：丟例外。
- `raw`：原樣回 ctx.config["ret"]（list 當 tuple 用；`"ret_shape": "list"` 時回 list，驗證要拒絕）。
"""
import json
import os
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACK)
import aos7_kernel  # noqa: E402


def _run_of(snap, target):
    for it in snap:
        if it["file"].endswith("birth.json") and it["src"]["slot"] == target.get("slot") and it["read"] == "ok":
            return it["run"]
    return None


def echo(ctx, snap, rstate):
    cfg = ctx["config"]
    fired = list(rstate.get("fired", []))
    out = []
    if cfg.get("from", 1) <= ctx["tock"] <= cfg.get("until", 10 ** 9):
        for c in cfg.get("emit", []):
            c = dict(c)
            if c.get("run") == "$run":
                c["run"] = _run_of(snap, c.get("target") or {})
                if c["run"] is None:
                    continue
            key = json.dumps(c, sort_keys=True, ensure_ascii=False)
            if cfg.get("once", True) and key in fired:
                continue
            fired.append(key)
            out.append(c)
    return dict(rstate, fired=fired[-20:], seen=ctx["tock"]), out


def boom(ctx, snap, rstate):
    raise RuntimeError("假規則故意壞掉")


def raw(ctx, snap, rstate):
    ret = ctx["config"].get("ret")
    return ret if ctx["config"].get("ret_shape") == "list" else tuple(ret)


RULES = dict(aos7_kernel.RULES, echo=echo, boom=boom, raw=raw)

if __name__ == "__main__":
    sys.exit(aos7_kernel.main(rules=RULES))
