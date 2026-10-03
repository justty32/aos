"""namespace：報告 2026-10-03-other-os-borrow §14 實驗一（Plan 9 式命名空間＋服務卡），全離線、mock 服務。

同一份 reviewer.py（同一個 argv）跑在 proj-a、proj-b，只認 mnt/mail、mnt/model、mnt/context。
服務是 tick 起的 keep 任務（mock_model.py），讀 requests/、寫 receipts/，有 service.json 服務卡與 instance_epoch。

  1. 兩個專案各處理一批工作（A 接 model-a、B 接 model-b）
  2. model-a 執行完 a-job3、寫回條前卡住 → 探針用 PID kill → keep 重起、epoch 換；a-job4 在舊 epoch 送出、還沒執行
  3. model-a 停著不處理（hold）時 a-job5 在途；改 proj-a 的 tasks.json mounts 換到 model-a2，restart reload
  4. 再 reload 一次，多掛 model-prev → model-a，放開 hold，舊請求收尾
  5. mounts 換到介面 llm-submit.v2 的 model-x：reviewer 要可讀拒絕、不送件；服務收到介面不合的請求也要可讀拒絕
盲讀那步（要 LLM）不做，改記「回答五題要讀哪些檔」（README）。
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
REVIEWER = os.path.join(HERE, "reviewer.py")
MOCK = os.path.join(HERE, "mock_model.py")
SERVICES = {"model-a": "llm-submit.v1", "model-a2": "llm-submit.v1", "model-b": "llm-submit.v1",
            "model-x": "llm-submit.v2"}


def client(svc):
    return "services/%s/clients/reviewer" % svc


def mounts(proj, svc, prev=None):
    m = {"mail": proj + "/inbox", "model": client(svc), "context": proj + "/context"}
    if prev:
        m["model-prev"] = client(prev)
    return m


def reviewer_item(proj, svc, prev=None):
    return {"name": "reviewer", "mode": "keep", "argv": [PY, REVIEWER], "mounts": mounts(proj, svc, prev)}


class NS:
    def __init__(self, sp):
        self.sp = sp

    def svc_path(self, svc, *rest):
        return self.sp.path("services/" + svc, *rest)

    def executed(self, svc):
        return pl.fs.read_jsonl(self.svc_path(svc, "executed.jsonl"))

    def exec_count(self, rid):
        return sum(1 for s in SERVICES for e in self.executed(s) if e["request_id"] == rid)

    def card(self, svc):
        return pl.fs.read_json(self.svc_path(svc, "clients", "reviewer", "service.json"), {}) or {}

    def rlog(self, proj):
        return pl.fs.read_jsonl(self.sp.path(proj, "context", "reviewer.jsonl"))

    def result(self, proj, job):
        return pl.fs.read_json(self.sp.path(proj, "context", "results", job + ".json"))

    def status(self, proj):
        return pl.fs.read_json(self.sp.path(proj, "context", "reviewer-status.json"), {}) or {}

    def mail(self, proj, job, work_id):
        pl.write(self.sp.path(proj, "inbox", job + ".json"),
                 {"work_id": work_id, "charge_context": "cc-" + proj, "body": "請審 %s 的改動" % work_id})

    def live(self, node, name):
        return [t for t in self.sp.live(node) if (self.sp.task_file(node, t, "birth.json") or {}).get("name") == name]

    def reload(self, proj, item):
        """改 tasks.json 的 reviewer 項目、對活的 reviewer 下 restart reload；回 (舊 tid, 新 tid, ctl-done)。"""
        pl.fs.edit_json(self.sp.path(proj, ".aos", "tasks.json"), lambda o: {"tasks": [item]})
        old = self.sp.wait_for(lambda: self.live(proj, "reviewer"), msg="%s 沒有活的 reviewer" % proj)[0]
        pl.write(os.path.join(pl.aos7_task.task_dir(self.sp.path(proj), old), "ctl.json"),
                 {"op": "restart", "reload": True, "by": "probe:kernel", "why": "換服務"})
        done = self.sp.wait_for(lambda: self.sp.task_file(proj, old, "ctl-done.json"), msg="reload 沒回條")
        new = self.sp.wait_for(lambda: [t for t in self.sp.tasks(proj)
                                        if (self.sp.task_file(proj, t, "birth.json") or {}).get("restart_of") == old],
                               msg="reload 沒起新的 reviewer")[0]
        return old, new, done


def main():
    r = pl.Result("namespace")
    with pl.Space("namespace") as sp:
        ns = NS(sp)
        for s, iface in SERVICES.items():
            sp.node("services/" + s, [{"name": "svc", "mode": "keep", "argv": [PY, MOCK]}], interval_ms=100,
                    files={"service.cfg.json": {"service_id": s, "interface": iface, "clients": ["reviewer"]}})
        sp.node("proj-a", [reviewer_item("proj-a", "model-a")], interval_ms=100)
        sp.node("proj-b", [reviewer_item("proj-b", "model-b")], interval_ms=100)
        sp.start(env={"AOS7_AUDIT": "1"})

        # ---- 1. 正常一批
        for i in range(1, 7):
            ns.mail("proj-b", "job%d" % i, "b-job%d" % i)
        for i in (1, 2):
            ns.mail("proj-a", "job%d" % i, "a-job%d" % i)
        sp.wait_for(lambda: all(ns.result("proj-a", "job%d" % i) for i in (1, 2)), msg="A 第一批沒做完")
        r.check("1: 同一份 reviewer，A 的 job1、2 經 mnt/model 拿到 model-a 的結果",
                all(ns.result("proj-a", "job%d" % i)["service_id"] == "model-a" for i in (1, 2)))

        # ---- 2. model-a 死在「執行完、回條前」，keep 重起換 epoch
        pl.write(ns.svc_path("model-a", "fault.json"), {"crash_after_exec": "a-job3-call-1"})
        ns.mail("proj-a", "job3", "a-job3")
        sp.wait_for(lambda: ns.exec_count("a-job3-call-1") == 1, msg="a-job3 沒執行")
        ns.mail("proj-a", "job4", "a-job4")      # 服務卡住時送出：在舊 epoch 送、還沒執行
        sp.wait_for(lambda: os.path.exists(ns.svc_path("model-a", "clients", "reviewer", "requests", "a-job4-call-1.json")),
                    msg="a-job4 沒送出")
        epoch1 = ns.card("model-a").get("instance_epoch")
        old_svc = ns.live("services/model-a", "svc")[0]
        pid = sp.task_file("services/model-a", old_svc, "pid.json")
        t_kill = time.monotonic()
        os.killpg(pid["pgid"], signal.SIGKILL)
        sp.wait_for(lambda: ns.card("model-a").get("instance_epoch") not in (None, epoch1), msg="model-a 沒換 epoch")
        r.measure("2: kill model-a → keep 重起、新服務卡出現 ms", round((time.monotonic() - t_kill) * 1000))
        sp.wait_for(lambda: ns.result("proj-a", "job3") and ns.result("proj-a", "job4"), msg="job3／4 沒收尾")
        res3, res4 = ns.result("proj-a", "job3"), ns.result("proj-a", "job4")
        r.check("2: model-a 換了 epoch（%s → %s）" % (epoch1, ns.card("model-a").get("instance_epoch")),
                ns.card("model-a").get("instance_epoch") == "model-a-2")
        r.check("2: a-job3（做完沒回條）重起後照 executed 帳補回條，沒有第二次副作用",
                ns.exec_count("a-job3-call-1") == 1 and res3["recovered"] is True and res3["executed_epoch"] == epoch1,
                res3)
        r.check("2: a-job4（舊 epoch 送出、沒執行）由新 epoch 執行一次",
                ns.exec_count("a-job4-call-1") == 1 and res4["executed_epoch"] == "model-a-2", res4)
        subs = [e for e in ns.rlog("proj-a") if e["ev"] == "submit"]
        r.check("2: reviewer 每個 request_id 只送一次（服務重起不重送）",
                len(subs) == len({e["request_id"] for e in subs}), [e["request_id"] for e in subs])
        r.check("2: reviewer 看到 epoch 換了（服務卡）",
                any(e["ev"] == "card" and e.get("epoch") == "model-a-2" for e in ns.rlog("proj-a")))

        # ---- 3. 換服務：model-a hold 時有在途請求，reload 到 model-a2（不留舊服務）
        pl.write(ns.svc_path("model-a", "fault.json"), {"hold": True})
        ns.mail("proj-a", "job5", "a-job5")
        sp.wait_for(lambda: os.path.exists(ns.svc_path("model-a", "clients", "reviewer", "requests", "a-job5-call-1.json")),
                    msg="a-job5 沒送出")
        old, new, done = ns.reload("proj-a", reviewer_item("proj-a", "model-a2"))
        res = done.get("result", {})
        r.check("3: restart reload 回條 ok、diff 列出 mounts 舊 → 新", res.get("ok") and "mounts" in (res.get("diff") or {}),
                res.get("msg"))
        sp.wait_for(lambda: "a-job5-call-1" in (ns.status("proj-a").get("unknown") or []), msg="新 reviewer 沒報 unknown")
        r.check("3: 新 reviewer 讀舊 checkpoint：a-job5 送去的 model-a 現在看不到 → 報 unknown（status 可讀）、不重送到 model-a2",
                not os.path.exists(ns.svc_path("model-a2", "clients", "reviewer", "requests", "a-job5-call-1.json"))
                and ns.exec_count("a-job5-call-1") == 0, ns.status("proj-a").get("why"))
        ns.mail("proj-a", "job6", "a-job6")
        sp.wait_for(lambda: ns.result("proj-a", "job6"), msg="job6 沒做完")
        r.check("3: 新工作 a-job6 走 model-a2（同一份程式、只換掛載）", ns.result("proj-a", "job6")["service_id"] == "model-a2")

        # ---- 4. 多掛 model-prev 收舊請求的尾
        old2, new2, done2 = ns.reload("proj-a", reviewer_item("proj-a", "model-a2", prev="model-a"))
        r.check("4: 第二次 reload ok（新增 model-prev）", (done2.get("result") or {}).get("ok"),
                (done2.get("result") or {}).get("msg"))
        pl.write(ns.svc_path("model-a", "fault.json"), {})
        rcv = sp.wait_for(lambda: [e for e in ns.rlog("proj-a") if e["ev"] == "receipt" and e["request_id"] == "a-job5-call-1"],
                          msg="job5 沒收尾")
        r.check("4: a-job5 經 mnt/model-prev 從 model-a 收尾，全空間只執行一次",
                ns.exec_count("a-job5-call-1") == 1 and rcv and rcv[0]["via"] == "model-prev", rcv)
        r.measure("3+4: 換服務且不丟在途請求要的控制步數（改 tasks.json＋ctl，兩次 reload）", 4)

        # ---- 5. 介面不合
        old3, new3, done3 = ns.reload("proj-a", reviewer_item("proj-a", "model-x"))
        ns.mail("proj-a", "job7", "a-job7")
        sp.wait_for(lambda: ns.status("proj-a").get("state") == "rejected", msg="reviewer 沒拒絕不合的介面")
        time.sleep(0.3)
        reqs_x = os.listdir(ns.svc_path("model-x", "clients", "reviewer", "requests"))
        r.check("5: 介面 llm-submit.v2：reviewer 寫可讀拒絕、一件都沒送、job7 沒做",
                not reqs_x and not ns.result("proj-a", "job7"), ns.status("proj-a").get("why"))
        bad = ns.svc_path("model-b", "clients", "reviewer")
        pl.write(os.path.join(bad, "requests", "probe-v0.json"),
                 {"request_id": "probe-v0", "interface": "llm-submit.v0", "work_id": "x", "input": "?"})
        rec = sp.wait_for(lambda: pl.fs.read_json(os.path.join(bad, "receipts", "probe-v0.json")), msg="服務沒回條")
        r.check("5: 服務收到介面不合的請求：回條 rejected、說得出哪裡不合、沒執行",
                rec.get("state") == "rejected" and "介面" in rec.get("why", "") and
                not any(e["request_id"] == "probe-v0" for e in ns.executed("model-b")), rec.get("why"))

        # ---- 6. B 全程正常、帳沒串
        sp.wait_for(lambda: all(ns.result("proj-b", "job%d" % i) for i in range(1, 7)), msg="B 沒做完")
        r.check("6: B 六件都進 proj-b/context、都由 model-b 做", all(
            ns.result("proj-b", "job%d" % i)["service_id"] == "model-b" and
            ns.result("proj-b", "job%d" % i)["work_id"] == "b-job%d" % i for i in range(1, 7)))
        wid = {s: sorted({e["work_id"] for e in ns.executed(s)}) for s in SERVICES}
        r.check("6: 各服務的 executed 帳只有自己客戶的工作（A 的在 model-a／a2、B 的在 model-b、model-x 沒有）",
                all(w.startswith("a-") for s in ("model-a", "model-a2") for w in wid[s])
                and all(w.startswith("b-") for w in wid["model-b"]) and not wid["model-x"], wid)
        r.check("6: 全空間每個 request_id 只執行一次",
                all(ns.exec_count(e["request_id"]) == 1 for s in SERVICES for e in ns.executed(s)))
        brev = {(sp.task_file("proj-b", t, "birth.json") or {}).get("argv")[1] for t in sp.tasks("proj-b")}
        arev = {(sp.task_file("proj-a", t, "birth.json") or {}).get("argv")[1] for t in sp.tasks("proj-a")}
        r.check("6: 兩個專案、四代 reviewer 跑的是同一支程式", arev == brev == {REVIEWER}, (arev, brev))

        # ---- 盲讀清單：回答五題要讀的檔（相對空間根）都在
        a = "proj-a/.aos/tasks/%s" % new3
        quiz = {
            "在哪送件": [client("model-a2") + "/service.json"],
            "誰付錢": [client("model-a2") + "/service.json", client("model-a2") + "/requests/a-job6-call-1.json"],
            "是否已完成": [client("model-a2") + "/receipts/a-job6-call-1.json"],
            "故障後能否重送": [client("model-a") + "/service.json", "proj-a/context/checkpoint.json",
                         client("model-a") + "/receipts/a-job3-call-1.json"],
            "現在接的是哪個服務（原題『哪份工具生效』，union 那步沒做）": [a + "/birth.json", "proj-a/.aos/tasks/%s/ctl-done.json" % old3],
        }
        miss = [p for ps in quiz.values() for p in ps if not os.path.isfile(os.path.join(sp.root, p))]
        r.check("盲讀清單：五題要讀的檔都在", not miss, miss)
        r.measure("盲讀清單：每題要讀幾個檔", {q: len(ps) for q, ps in quiz.items()})
        r.measure("盲讀清單：五題總共要讀的位元組", sum(os.path.getsize(os.path.join(sp.root, p))
                                              for p in {p for ps in quiz.values() for p in ps}))
        au = aos7_audit.scan(sp.root)
        r.check("寫入紀錄：reviewer 與服務沒寫到自己的 node 與掛載點以外", not au["bad"], au["bad"][:3])
        r.measure("寫入紀錄：任務數／寫入筆數", "%d／%d" % (au["tasks"], au["writes"]))
        r.finding("換服務時舊服務的在途請求：reload 換掉整份 mounts，舊目標就看不到了；要收尾得由 kernel 自己約定"
                  "多掛一個 model-prev（兩次 reload，4 個控制步）。tick 不知道『這個掛載點上還有在途請求』（E-03）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
