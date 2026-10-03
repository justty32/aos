"""hsched 的合作式 mock worker（keep 任務，node P／Q）：一次做一份工作。不打 LLM。

    python3 worker.py <名字>
收 `<node>/work/<名字>/assign/<job>.json`（kernel 經掛載寫的派工：{job, ticket, tokens, lat}），依序：
  1. 向閘門要 grant（`mnt/bank/requests/<ticket>.json`），被拒就寫結果 ok:false 收手；
  2. mock provider：合成延遲＝lat × 當時的延遲倍數（`mnt/pub/provider.json`），以控制回合計（`mnt/clk/round.json`）；
  3. settle（用量＝合成 token 成本），寫 `<node>/work/<名字>/results/<job>.json`。
起來先寫 `alive.json`（kernel 據此知道多了幾個 worker）。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
sys.path.insert(0, HERE)
import aos7_fs as fs  # noqa: E402
import sim  # noqa: E402

E = fs.task_env()
NAME = sys.argv[1]
WD = os.path.join(E["node"], "work", NAME)
M = os.path.join(E["task"], "mnt")
ME = "%s:%s" % (E["node_id"], E["tid"])
os.makedirs(os.path.join(WD, "assign"), exist_ok=True)
os.makedirs(os.path.join(WD, "results"), exist_ok=True)
fs.write_json(os.path.join(WD, "alive.json"), {"name": NAME, "tid": E["tid"], "at": fs.now()})


def clock():
    return (fs.read_json(os.path.join(M, "clk", "round.json"), {}) or {}).get("round", 0)


def bank(rid, obj):
    rp = os.path.join(M, "bank", "receipts", rid + ".json")
    rec = fs.read_json(rp)
    if not isinstance(rec, dict):
        fs.write_json(os.path.join(M, "bank", "requests", rid + ".json"), dict(obj, request_id=rid))
        while not isinstance(rec, dict):
            time.sleep(0.005)
            rec = fs.read_json(rp)
    return rec


while True:
    ad = os.path.join(WD, "assign")
    for f in sorted(x for x in os.listdir(ad) if x.endswith(".json") and not x.startswith(".")):
        a = fs.read_json(os.path.join(ad, f))
        if not isinstance(a, dict):
            continue
        res = os.path.join(WD, "results", f)
        if os.path.exists(res):
            continue
        g = bank(a["ticket"], {"op": "grant", "ticket": a["ticket"], "project": E["node_id"], "job": a["job"],
                               "tokens": a["tokens"], "worker": NAME, "from": ME})
        if not g.get("ok"):
            fs.write_json(res, {"job": a["job"], "ok": False, "why": g.get("why"), "reason": g.get("reason"),
                                "round": clock()})
            continue
        start = g["round"]
        prov = fs.read_json(os.path.join(M, "pub", "provider.json"), {}) or {}
        lat = sim.latency(a["lat"], start, prov)
        while clock() < start + lat:
            time.sleep(0.005)
        s = bank(a["ticket"] + "-settle", {"op": "settle", "ticket": a["ticket"], "used": a["tokens"], "from": ME})
        fs.write_json(res, {"job": a["job"], "ok": True, "start": start, "lat": lat, "done": clock(),
                            "used": s.get("used"), "settled": s.get("ok")})
    time.sleep(0.005)
