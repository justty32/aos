"""ledger：報告 2026-10-03-other-os-borrow §14 實驗二（父子委派帳），全離線、mock provider。

帳本（ledger.py）是 node bank 的 keep 任務、唯一寫 ledger 的人，收 requests、寫 receipts。
P、Q 兩個父工作（node p、q）共用一個 mock 模型服務（provider.py，node provider 的 keep 任務）。
worker（worker.py）是 spawn 起的一次性任務；探針自己當 P 的 kernel，直接寫帳本請求。

  1. 重播 §11.2：P 10000，已花 3000、在途 1000、split 2400（S 1600、R 800），S 用 1200、R 用 700，還回 → 4900／1000／4100
     Q 穿插在中間
  2. 兩個請求同搶 P 的最後額度：一個成、一個可讀拒絕
  3. 同一份 grant 交給兩個 worker：只有一個 claim 成、只有它呼叫 provider
  4. 切點：reserve 落帳後、回條前 kill 帳本；provider 執行完、回條前 kill provider；settle 回條後、worker 讀之前 kill worker；
     每個都重送同一個 request_id
  5. 未知在途（provider 一直沒回）：release 被拒；worker 被 kill、帳本重起、worker 資料夾被搬到 tasks-old 都不免帳；
     provider 回了才結算
  6. 洩漏的 grant：Q 的任務自稱 P 的 worker 去 claim（量，不是 check：執行者身分是自報的）
每一步都用獨立重算器（本檔的 recompute，跟 ledger.py 分開寫）從 events.jsonl 重算，驗守恆式與帳本的 summary 一致。
"""
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import aos7_audit  # noqa: E402

PY = pl.PY
WORKER = os.path.join(HERE, "worker.py")
WMOUNTS = {"bank": "bank/io", "prov": "provider/io"}


def recompute(events):
    """獨立重算：每個事件是「桶子之間搬額度」。回 (每個 root 的四欄, 問題清單)。

    桶子：("free", context)、("reserved", res)、("spent", res)。context 的 root 與 parent 從 open／delegate 記。"""
    bucket, parent, root, closed, res_ctx, probs = {}, {}, {}, set(), {}, []
    rid_seen, res_end, claimed = set(), set(), set()

    def move(src, dst, n, ev):
        if src is not None:
            bucket[src] = bucket.get(src, 0) - n
            if bucket[src] < 0:
                probs.append("事件 %s 讓 %s 變負數" % (ev.get("seq"), src))
        if dst is not None:
            bucket[dst] = bucket.get(dst, 0) + n

    def open_up(c):
        while c in closed:
            c = parent[c]
        return c

    limits = {}
    for ev in events:
        k, rid = ev["kind"], ev.get("request_id")
        if rid:
            if rid in rid_seen:
                probs.append("request_id %s 記了兩筆" % rid)
            rid_seen.add(rid)
        if k == "open":
            root[ev["cid"]], parent[ev["cid"]], limits[ev["cid"]] = ev["cid"], None, ev["limit"]
            move(None, ("free", ev["cid"]), ev["limit"], ev)
        elif k == "delegate":
            for ch in ev["children"]:
                root[ch["context_id"]], parent[ch["context_id"]] = root[ev["parent"]], ev["parent"]
                move(("free", ev["parent"]), ("free", ch["context_id"]), ch["tokens"], ev)
        elif k == "reserve":
            if ev["res_id"] in res_ctx:
                probs.append("res %s 保留兩次" % ev["res_id"])
            res_ctx[ev["res_id"]] = (ev["cid"], ev["tokens"])
            move(("free", ev["cid"]), ("reserved", ev["res_id"]), ev["tokens"], ev)
        elif k == "claim":
            if ev["res_id"] in claimed:
                probs.append("res %s 被 claim 兩次" % ev["res_id"])
            claimed.add(ev["res_id"])
        elif k in ("settle", "release"):
            if ev["res_id"] in res_end:
                probs.append("res %s 結了兩次" % ev["res_id"])
            res_end.add(ev["res_id"])
            cid, t = res_ctx[ev["res_id"]]
            used = ev.get("used", 0) if k == "settle" else 0
            move(("reserved", ev["res_id"]), ("spent", ev["res_id"]), used, ev)
            move(("reserved", ev["res_id"]), ("free", open_up(cid)), t - used, ev)
        elif k == "return":
            move(("free", ev["cid"]), ("free", parent[ev["cid"]]), bucket.get(("free", ev["cid"]), 0), ev)
            closed.add(ev["cid"])
    out = {r: {"limit": limits[r], "spent": 0, "reserved": 0, "delegated_unspent": 0, "free": 0} for r in limits}
    for (kind, key), n in bucket.items():
        if kind == "free":
            out[root[key]]["free" if parent[key] is None else "delegated_unspent"] += n
        else:
            out[root[res_ctx[key][0]]][kind] += n
    for r, v in out.items():
        if v["spent"] + v["reserved"] + v["delegated_unspent"] + v["free"] != v["limit"]:
            probs.append("%s 不守恆：%s" % (r, v))
    return out, probs


class LP:
    def __init__(self, sp, r):
        self.sp, self.r, self.n = sp, r, 0

    def p(self, *rest):
        return self.sp.path("bank", *rest)

    def events(self):
        return pl.fs.read_jsonl(self.p("ledger", "events.jsonl"))

    def summary(self):
        return pl.fs.read_json(self.p("ledger", "summary.json"), {}) or {}

    def executed(self):
        return pl.fs.read_jsonl(self.sp.path("provider", "executed.jsonl"))

    def req(self, obj, wait=True):
        pl.write(self.p("io", "requests", obj["request_id"] + ".json"), obj)
        if wait:
            return self.sp.wait_for(lambda: pl.fs.read_json(self.p("io", "receipts", obj["request_id"] + ".json")),
                                    msg="帳本沒回 %s" % obj["request_id"])

    def job(self, node, name, **spec):
        pl.write(self.sp.path(node, "jobs", name + ".json"), dict(spec, job=name))

    def spawn(self, node, names):
        self.n += 1
        pl.write(self.sp.path(node, ".aos", "spawn", "w%03d.json" % self.n),
                 {"batch": [{"name": "w-" + n, "argv": [PY, WORKER, n], "mounts": WMOUNTS} for n in names]})

    def state(self, node, name):
        return pl.fs.read_json(self.sp.path(node, "jobs", name + ".state.json"), {}) or {}

    def jlog(self, node, name):
        return pl.fs.read_jsonl(self.sp.path(node, "jobs", name + ".log.jsonl"))

    def wait_state(self, node, name, steps=("done", "rejected")):
        return self.sp.wait_for(lambda: self.state(node, name).get("step") in steps and self.state(node, name),
                                timeout=15, msg="%s/%s 沒到 %s（現在 %s）" % (node, name, steps, self.state(node, name)))

    def live_named(self, node, name):
        return [t for t in self.sp.live(node) if (self.sp.task_file(node, t, "birth.json") or {}).get("name") == name]

    def kill(self, node, name):
        """用 pid.json 的 pgid SIGKILL 那個活任務（模擬當機）；回 tid。"""
        tid = self.sp.wait_for(lambda: self.live_named(node, name), msg="%s 沒有活的 %s" % (node, name))[0]
        pid = self.sp.wait_for(lambda: self.sp.task_file(node, tid, "pid.json"), msg="沒有 pid.json")
        os.killpg(pid["pgid"], signal.SIGKILL)
        self.sp.wait_for(lambda: self.sp.task_file(node, tid, "exit.json"), msg="%s 沒寫 exit.json" % tid)
        return tid

    def verify(self, tag):
        """等帳本 summary 跟上事件，獨立重算、比對、驗守恆。回重算的 roots。"""
        self.sp.wait_for(lambda: self.summary().get("revision") == len(self.events()), msg="summary 沒跟上")
        evs = self.events()
        mine, probs = recompute(evs)
        theirs = {k: {x: v[x] for x in ("limit", "spent", "reserved", "delegated_unspent", "free")}
                  for k, v in self.summary().get("roots", {}).items()}
        self.r.check("%s：守恆、不為負、request 不重記、與帳本 summary 一致" % tag, not probs and mine == theirs,
                     probs or (None if mine == theirs else {"重算": mine, "帳本": theirs}))
        return mine


def main():
    r = pl.Result("ledger")
    with pl.Space("ledger") as sp:
        L = LP(sp, r)
        sp.node("bank", [{"name": "ledger", "mode": "keep", "argv": [PY, os.path.join(HERE, "ledger.py")],
                          "mounts": {"prov": "provider/io/receipts"}}], interval_ms=100,
                files={"accounts.json": {"P": {"limit": 10000}, "Q": {"limit": 5000}}})
        sp.node("provider", [{"name": "provider", "mode": "keep", "argv": [PY, os.path.join(HERE, "provider.py")],
                              "mounts": {"bank": "bank/io"}}], interval_ms=100)
        sp.node("p", [], interval_ms=100, keep_ended_rounds=3)
        sp.node("q", [], interval_ms=100)
        sp.start(env={"AOS7_AUDIT": "1"})
        sp.wait_for(lambda: L.summary().get("roots", {}).get("Q"), msg="帳本沒開帳")

        # ---- 1. §11.2 重播
        pl.write(sp.path("provider", "fault.json"), {"hold": ["inflight-a1"]})
        L.job("p", "seed", context="P", tokens=3000, want=3000, attempt="seed-a1")
        L.spawn("p", ["seed"])
        L.wait_state("p", "seed")
        L.job("p", "inflight", context="P", tokens=1000, want=900, attempt="inflight-a1")
        L.spawn("p", ["inflight"])
        L.wait_state("p", "inflight", ("calling",))
        m = L.verify("1a 已花 3000、在途 1000")
        r.check("1a: P＝已花 3000／在途 1000／自由 6000", (m["P"]["spent"], m["P"]["reserved"], m["P"]["free"]) == (3000, 1000, 6000), m["P"])
        rec = L.req({"request_id": "delegate-review-17", "op": "delegate", "parent": "P",
                     "expected_revision": L.summary()["revision"],
                     "children": [{"context_id": "cc-review-s", "holder": "p", "tokens": 1600},
                                  {"context_id": "cc-review-r", "holder": "p", "tokens": 800}]})
        m = L.verify("1b split 2400")
        r.check("1b: split 後 P 可再分配只剩 3600、委派未支用 2400", rec.get("ok") and
                (m["P"]["free"], m["P"]["delegated_unspent"]) == (3600, 2400), m["P"])
        L.job("p", "S", context="cc-review-s", tokens=1600, want=1200, attempt="S-a1")
        L.job("p", "R", context="cc-review-r", tokens=800, want=700, attempt="R-a1")
        L.job("q", "q1", context="Q", tokens=500, want=400, attempt="q1-a1")
        L.spawn("p", ["S", "R"])
        L.spawn("q", ["q1"])
        for n, j in (("p", "S"), ("p", "R"), ("q", "q1")):
            L.wait_state(n, j)
        L.verify("1c S、R、Q 做完")
        for c in ("cc-review-s", "cc-review-r"):
            L.req({"request_id": "return-" + c, "op": "return", "context_id": c})
        m = L.verify("1d 還回父")
        r.check("1d: §11.2 終值 P＝已花 4900／在途 1000／自由 4100（S 用 1200、R 用 700，剩 500 回父）",
                (m["P"]["spent"], m["P"]["reserved"], m["P"]["free"], m["P"]["delegated_unspent"]) == (4900, 1000, 4100, 0), m["P"])
        r.check("1d: Q 只有自己的 400", (m["Q"]["spent"], m["Q"]["free"]) == (400, 4600), m["Q"])

        # ---- 2. 兩個請求同搶最後額度
        for i in (1, 2):
            L.req({"request_id": "race-%d" % i, "op": "reserve", "context": "P", "tokens": 3000}, wait=False)
        recs = [sp.wait_for(lambda i=i: pl.fs.read_json(L.p("io", "receipts", "race-%d.json" % i))) for i in (1, 2)]
        oks = [x for x in recs if x.get("ok")]
        bad = [x for x in recs if not x.get("ok")]
        r.check("2: 同搶 4100 裡的 3000＋3000：恰好一個成、另一個拒絕說額度不足",
                len(oks) == 1 and len(bad) == 1 and "額度不足" in bad[0].get("why", ""), [x.get("why") for x in bad])
        L.req({"request_id": "race-release", "op": "release", "res_id": oks[0]["res_id"]})
        L.verify("2 搶完、放掉沒 claim 的")

        # ---- 3. 同一 grant 給兩個 worker
        g = L.req({"request_id": "grant-g", "op": "reserve", "context": "P", "tokens": 500})["res_id"]
        L.job("p", "g1", res_id=g, want=300, attempt="g-a1")
        L.job("p", "g2", res_id=g, want=300, attempt="g-a2")
        L.spawn("p", ["g1", "g2"])
        s1, s2 = L.wait_state("p", "g1"), L.wait_state("p", "g2")
        steps = sorted([s1["step"], s2["step"]])
        rej = s1 if s1["step"] == "rejected" else s2
        r.check("3: 同一份 grant：一個 worker 做完、另一個 claim 被拒（可讀：重複）",
                steps == ["done", "rejected"] and "重複" in rej.get("why", ""), rej.get("why"))
        r.check("3: provider 對這份 grant 只執行一次", sum(1 for e in L.executed() if e["res_id"] == g) == 1)
        L.verify("3 重複 grant")

        # ---- 4. 切點
        # k1：reserve 落帳後、回條前 kill 帳本
        pl.write(L.p("fault.json"), {"hang_after_event": "k1-reserve"})
        L.job("p", "k1", context="P", tokens=300, want=200, attempt="k1-a1")
        L.spawn("p", ["k1"])
        sp.wait_for(lambda: any(e.get("request_id") == "k1-reserve" for e in L.events()), msg="k1 沒落帳")
        pl.write(L.p("fault.json"), {})
        t0 = time.monotonic()
        L.kill("bank", "ledger")
        st = L.wait_state("p", "k1")
        r.measure("4 k1: kill 帳本 → keep 重起 → worker 拿到補的回條、做完 ms", round((time.monotonic() - t0) * 1000))
        L.req({"request_id": "k1-reserve", "op": "reserve", "context": "P", "tokens": 300})   # 再重送一次同 id
        time.sleep(0.1)
        r.check("4 k1: reserve 落帳後帳本死：重起照事件補回條（replayed）、重送同 id 不記第二筆、worker 做完",
                st["step"] == "done" and sum(1 for e in L.events() if e.get("request_id") == "k1-reserve") == 1
                and pl.fs.read_json(L.p("io", "receipts", "k1-reserve.json"), {}).get("replayed"))
        L.verify("4 k1")
        # k2：provider 執行完、回條前 kill provider
        pl.write(sp.path("provider", "fault.json"), {"hold": ["inflight-a1"], "crash_after_exec": "k2-a1"})
        L.job("p", "k2", context="P", tokens=300, want=250, attempt="k2-a1")
        L.spawn("p", ["k2"])
        sp.wait_for(lambda: any(e["attempt_id"] == "k2-a1" for e in L.executed()), msg="k2 沒執行")
        pl.write(sp.path("provider", "fault.json"), {"hold": ["inflight-a1"]})
        L.kill("provider", "provider")
        st = L.wait_state("p", "k2")
        prec = pl.fs.read_json(sp.path("provider", "io", "receipts", "k2-a1.json"), {})
        pl.write(sp.path("provider", "io", "requests", "k2-a1.json"),
                 {"attempt_id": "k2-a1", "res_id": st["res_id"], "executor": "probe", "want": 250})   # 重送
        time.sleep(0.15)
        r.check("4 k2: provider 做完沒回條就死：重起照 executed 補回條、重送不再執行、帳只結一次",
                st["step"] == "done" and prec.get("recovered") and
                sum(1 for e in L.executed() if e["attempt_id"] == "k2-a1") == 1 and
                sum(1 for e in L.events() if e["kind"] == "settle" and e["res_id"] == st["res_id"]) == 1)
        L.verify("4 k2")
        # k3：settle 回條已寫、worker 讀之前 kill worker
        L.job("p", "k3", context="P", tokens=300, want=100, attempt="k3-a1", hang_at="after_settle_sent")
        L.spawn("p", ["k3"])
        sp.wait_for(lambda: os.path.exists(L.p("io", "receipts", "k3-settle.json")), msg="k3 沒結算")
        L.kill("p", "w-k3")
        L.job("p", "k3", context="P", tokens=300, want=100, attempt="k3-a1")
        L.req({"request_id": "k3-settle", "op": "settle", "res_id": L.state("p", "k3")["res_id"]}, wait=False)   # 重送
        L.spawn("p", ["k3"])
        st = L.wait_state("p", "k3")
        r.check("4 k3: settle 後 worker 死：新 worker 接 state、讀到同一張回條；重送的 settle 不記第二筆",
                st["step"] == "done" and st.get("used") == 100 and
                sum(1 for e in L.events() if e.get("request_id") == "k3-settle") == 1)
        L.verify("4 k3")

        # ---- 5. 未知在途
        res_in = L.state("p", "inflight")["res_id"]
        rel = L.req({"request_id": "inflight-release", "op": "release", "res_id": res_in})
        r.check("5: provider 沒回條時 release 被拒（在途未知，不釋放）", not rel.get("ok") and "在途未知" in rel.get("why", ""),
                rel.get("why"))
        wtid = L.kill("p", "w-inflight")
        L.kill("bank", "ledger")
        sp.wait_for(lambda: sp.live("bank"), msg="帳本沒重起")
        sp.wait_for(lambda: not os.path.isdir(pl.aos7_task.task_dir(sp.path("p"), wtid)), timeout=10,
                    msg="worker 資料夾沒搬到 tasks-old")
        m = L.verify("5 worker 死、帳本重起、worker 資料夾歸檔")
        r.check("5: worker 死、帳本重起、資料夾搬到 tasks-old 之後，在途 1000 仍保留",
                m["P"]["reserved"] == 1000 and
                os.path.isdir(os.path.join(sp.path("p"), ".aos", "tasks-old", wtid)), m["P"])
        pl.write(sp.path("provider", "fault.json"), {})
        L.spawn("p", ["inflight"])
        st = L.wait_state("p", "inflight")
        m = L.verify("5 provider 回條後結算")
        r.check("5: provider 確認後才結算：用 900、退 100，在途歸零", st["step"] == "done" and st.get("used") == 900
                and m["P"]["reserved"] == 0, (st, m["P"]))
        log = L.jlog("p", "inflight")
        r.check("5: 接手的 worker 沒重新 reserve／claim、沒重送 provider 請求",
                sum(1 for e in log if e["ev"] == "send" and e["op"] in ("reserve", "claim")) == 2
                and sum(1 for e in log if e["ev"] == "call") == 1)

        # ---- 6. 洩漏的 grant：Q 的任務自稱 P 的 worker
        leak = L.req({"request_id": "grant-leak", "op": "reserve", "context": "P", "tokens": 200})["res_id"]
        L.job("q", "forge", res_id=leak, want=200, attempt="forge-a1", executor="p:w-real-r99")
        L.spawn("q", ["forge"])
        st = L.wait_state("q", "forge")
        ex = [e for e in L.executed() if e["attempt_id"] == "forge-a1"]
        r.measure("6: Q 的任務拿洩漏的 P grant、自稱 p:w-real-r99 去 claim 的結果", st["step"])
        r.measure("6: provider 帳上那筆的 payer／自報 executor", ex and [ex[0]["payer"], ex[0]["executor"]])
        m = L.verify("6 洩漏的 grant")

        # ---- 總核對
        evs, exs = L.events(), L.executed()
        settled = {e["res_id"]: e for e in evs if e["kind"] == "settle"}
        claims = {e["res_id"]: e for e in evs if e["kind"] == "claim"}
        r.check("總：provider 每次執行都恰好對應一筆 settle（同 res、同 attempt、同用量），沒有多也沒有漏",
                len(exs) == len({e["attempt_id"] for e in exs}) and
                all(e["res_id"] in settled and settled[e["res_id"]]["used"] == e["used"] and
                    claims[e["res_id"]]["attempt_id"] == e["attempt_id"] for e in exs) and
                sum(1 for e in settled.values() if e.get("provider_state") == "done") == len(exs))
        qres = {e["res_id"] for e in evs if e["kind"] == "reserve" and e["cid"] == "Q"}
        r.check("總：Q 的帳只有 Q 自己的請求；provider 記給 Q 的只有 Q 的工作；洩漏那筆記在 P 不在 Q",
                all(e["request_id"].startswith("q") for e in evs if e["kind"] == "reserve" and e["cid"] == "Q")
                and all(e["work_id"].startswith("q") and e["res_id"] in qres for e in exs if e["payer"] == "Q")
                and all(e["payer"] == "P" for e in exs if e["attempt_id"] == "forge-a1") and m["Q"]["spent"] == 400)
        r.measure("總：事件數／provider 執行數", "%d／%d" % (len(evs), len(exs)))
        r.measure("總：P、Q 終值（重算）", m)
        # 重算器自己要抓得到錯：重複結算、多 claim、憑空多花
        dup = evs + [dict(evs[-1], seq=999)] if evs[-1]["kind"] == "settle" else evs + [dict(next(
            e for e in evs if e["kind"] == "settle"), seq=999, request_id="dup")]
        bad1 = recompute(dup)[1]
        bad2 = recompute(evs + [dict(next(e for e in evs if e["kind"] == "claim"), seq=998, request_id="dup2")])[1]
        bad3 = recompute([dict(e, used=e["used"] + 5000) if e["kind"] == "settle" else e for e in evs])[1]
        r.check("重算器自己會抓錯（重複結算、同 res 兩次 claim、結算超過保留額）", bad1 and bad2 and bad3,
                [bad1[:1], bad2[:1], bad3[:1]])
        au = aos7_audit.scan(sp.root)
        r.check("寫入紀錄：帳本、provider、worker 都只寫自己的 node 與掛載點", not au["bad"], au["bad"][:3])
        r.finding("執行者身分是自報的：Q 的任務拿到洩漏的 P grant（res_id＋attempt），自稱 p:w-real-r99 就 claim 成、"
                  "provider 照做並記給 P。帳本與 provider 都分不出請求檔是誰寫的；tick 知道（birth.json 的 node／tid／mounts），"
                  "但沒有交給服務驗的管道（E-01）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
