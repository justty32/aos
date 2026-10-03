"""supervisor：Erlang 式 supervisor 樹 kernel（one_for_one／rest_for_one、重啟上限、退避、升級），只用現有 tasks.json／spawn／ctl。

三個 node 跑同一份政策、同一組子工作，差在 supervisor 怎麼起子工作、什麼時候看：
  keep_tock   子工作是 tasks.json 的 keep 項，退避／停用＝把項目拿掉；每個 tock 看一次
  keep_poll   同上，但每 20 ms 看一次（不等回合）
  spawn_tock  tasks.json 只有 supervisor；起子工作一律寫 spawn；每個 tock 看一次

子工作：chain（rest_for_one、依序起）db → cache（第一代 3 個 tock 後 crash）→ web；
pool（one_for_one）w1（每一代 1 個 tock 後 crash）＋ w2；tmp：job（temporary，2 個 tock 後 exit 0）。
重啟上限 30 回合內 3 次，退避 1、2、4 回合；用完＝升級（寫 escalation.json、收掉整組、不再起）。

想逼出：keep 跟 supervisor 搶著起任務時，daemon／tick 缺什麼（D-18 的 enabled／not_before／restart_policy）。
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402

PY = pl.PY
CHILD = os.path.join(HERE, "child.py")
SUP = os.path.join(HERE, "sup.py")
NODES = {"keep_tock": ("keep", "tock"), "keep_poll": ("keep", "poll"), "spawn_tock": ("spawn", "tock")}
EXTRA_ROUNDS = 12


def child(name, *a):
    return {"argv": [PY, CHILD, name] + [str(x) for x in a]}


def policy(mode, react):
    ch = {"db": child("db", "stable", 0.15), "cache": child("cache", "crash_once", 3, "db"),
          "web": child("web", "stable", 0.05, "cache"), "w1": child("w1", "crash_each", 1),
          "w2": child("w2", "stable", 0), "job": dict(child("job", "temp", 2), restart="temporary")}
    lim = {"max_restarts": 3, "window_rounds": 30, "backoff": [1, 2, 4]}
    return {"mode": mode, "react": react, "children": ch, "groups": [
        dict(lim, id="chain", strategy="rest_for_one", ordered=True, children=["db", "cache", "web"]),
        dict(lim, id="pool", strategy="one_for_one", children=["w1", "w2"]),
        dict(lim, id="tmp", strategy="one_for_one", children=["job"])]}


def main():
    r = pl.Result("supervisor")
    with pl.Space("supervisor") as sp:
        for nid, (mode, react) in NODES.items():
            sp.node(nid, [{"name": "sup", "mode": "keep", "argv": [PY, SUP]}], interval_ms=100,
                    files={"sup.json": policy(mode, react)})
        sp.start()

        def ev(nid):
            return pl.fs.read_jsonl(sp.path(nid, "events.jsonl"))

        def sj(nid):
            return pl.fs.read_jsonl(sp.path(nid, "sup.jsonl"))

        def settled(nid):
            e = ev(nid)
            web = [x for x in e if x["ev"] == "start" and x["name"] == "web"]
            return (os.path.exists(sp.path(nid, "escalation.json")) and len(web) >= 2
                    and any(x["ev"] == "temp-exit" for x in sj(nid)))
        try:
            sp.wait_for(lambda: all(settled(n) for n in NODES), timeout=25, msg="三個 node 都升級、chain 復原、job 做完")
        except pl.ProbeTimeout:
            for n in NODES:     # 卡住時留線索
                print("--", n, "settled" if settled(n) else "NOT settled", "round", sp.round_of(n))
                for x in sj(n)[-12:]:
                    print("   sup", {k: v for k, v in x.items() if k != "t"})
                print("   err", sp.status().get("nodes", {}).get(n, {}).get("last_error"))
            raise
        base = {n: sp.round_of(n) for n in NODES}
        sp.wait_for(lambda: all(sp.round_of(n) >= base[n] + EXTRA_ROUNDS for n in NODES), timeout=10)
        for n in NODES:
            sp.ctl("pause", node=n)
        sp.wait_for(lambda: all(sp.status().get("nodes", {}).get(n, {}).get("phase") == "paused" for n in NODES),
                    timeout=10)

        summary = {}
        for nid in NODES:
            e, s = ev(nid), sj(nid)
            starts = collections.defaultdict(list)
            for x in e:
                if x["ev"] == "start":
                    starts[x["name"]].append(x)
            plans = [x for x in s if x["ev"] == "restart-planned"]
            esc = [x for x in s if x["ev"] == "escalate"]
            uns = [x for x in s if x["ev"] == "unsanctioned"]
            early = []        # 重起的 birth round 早於 supervisor 定的 not_before
            for p in plans:
                for c in p["affected"]:
                    nxt = [x for x in starts[c] if x["t"] > p["t"]][:1]      # supervisor 決定之後才起的那一代
                    if nxt and nxt[0]["round"] < p["not_before"]:
                        early.append({"child": c, "birth_round": nxt[0]["round"], "not_before": p["not_before"]})
            gaps = []            # keep 搶先起的：上一代 exit 到新一代 start 隔幾 ms
            for u in uns:
                prev = [x for x in e if x["ev"] == "exit" and x["name"] == u["child"]
                        and x["t"] < next(y["t"] for y in starts[u["child"]] if y["tid"] == u["tid"])]
                st = next(y["t"] for y in starts[u["child"]] if y["tid"] == u["tid"])
                if prev:
                    gaps.append(round((st - prev[-1]["t"]) * 1000))
            esc_round = esc[0]["round"] if esc else None
            after_esc = [x for c in ("w1", "w2") for x in starts[c] if esc_round is not None and x["round"] > esc_round]
            by = collections.Counter((x["child"], x["by"]) for x in s if x["ev"] in ("child-up", "unsanctioned") and "by" in x)
            deps = [(x["name"], x["round"], x["deps_ready"]) for c in ("cache", "web") for x in starts[c]]
            summary[nid] = {"starts": {c: len(v) for c, v in sorted(starts.items())}, "plans": len(plans),
                            "unsanctioned": [(x["child"], x["birth_round"], x["why"]) for x in uns],
                            "early_vs_backoff": early, "unsanctioned_gap_ms": gaps, "escalate_round": esc_round,
                            "pool_starts_after_escalate": len(after_esc), "by": {"%s/%s" % k: v for k, v in by.items()},
                            "deps_ready_at_start": deps, "rounds": sp.round_of(nid)}
            r.measure(nid, summary[nid])

        s = summary["spawn_tock"]
        r.check("spawn_tock：supervisor 是唯一的起任務者，沒有一次違反退避／停用（unsanctioned 0）",
                not s["unsanctioned"] and not s["early_vs_backoff"], s["unsanctioned"])
        r.check("spawn_tock：w1 起了 1＋3 次後升級，升級後 pool 沒再起", s["starts"].get("w1") == 4
                and s["escalate_round"] is not None and s["pool_starts_after_escalate"] == 0, s["starts"])
        r.check("spawn_tock：rest_for_one：cache 掛了只重起 cache、web，db 只起一次",
                s["starts"].get("db") == 1 and s["starts"].get("cache") == 2 and s["starts"].get("web") == 2, s["starts"])
        r.check("spawn_tock：temporary 的 job 只跑一次", s["starts"].get("job") == 1, s["starts"])
        r.check("spawn_tock：依序起（ordered）：每一代 cache、web 起來時依賴都已 ready",
                all(all(d.values()) for _, _, d in s["deps_ready_at_start"]), s["deps_ready_at_start"])
        k = summary["keep_tock"]
        r.check("keep_tock：keep 搶在 supervisor 前起回 crash 的子工作（unsanctioned > 0）——keep 的現行語意",
                len(k["unsanctioned"]) > 0, k["unsanctioned"][:4])
        for nid in ("keep_tock", "keep_poll"):
            x = summary[nid]
            r.measure("%s：違反（退避中／已放棄／temporary 做完卻被起）次數" % nid, len(x["unsanctioned"]))
            r.measure("%s：升級前 w1 起了幾次（政策要 4）" % nid, x["starts"].get("w1"))
            r.measure("%s：job（temporary）起了幾次（政策要 1）" % nid, x["starts"].get("job"))
        r.finding("keep 只有「沒有同名活實例就起」：crash 的子工作在下一個 tick 就被 keep 起回來，"
                  "supervisor 想退避、想停用只能搶著把項目從 tasks.json 拿掉；子工作多半是收到 tock 才動作、"
                  "tock 後馬上就是下一個 tick，連 20 ms 輪詢都常輸（D-18：缺 enabled／not_before／restart: on-failure）")
        r.finding("退出原因只有 code：supervisor 要自己記『這個 tid 是我 kill 的』才分得出 crash 與被收，"
                  "keep 起的新實例沒有 restart_of，看不出是誰起的、算不算一次重啟")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
