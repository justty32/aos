"""blindread：S-01 盲讀。用 probes/namespace 的服務卡與回條造一個世界，請模型只靠 read_file 回答五題，
對照「寫死路徑」版（同一個世界，拿掉服務卡與掛載點，路徑寫死在 proj-a/reviewer.cfg.json）。

造世界（約 3 秒，namespace 的第 1～4 步，停在舊服務還 hold 著 a-job5 的時候）：
  A 的 job1～4 經 model-a（job3 做完沒回條時 kill 服務、新 epoch 補回條）；model-a hold 時 job5 在途；
  reload 換到 model-a2、job6 做完；再 reload 多掛 model-prev → model-a。pause 全部 node 後複製一份當 card 版，
  再複製一份改成 hardcoded 版。

    python3 probe.py                       # 離線：造世界、驗題目與標準答案檔、答案跟世界對得上、照稿腦答對、評分器會扣錯
    python3 probe.py --real deepseek-chat,claude-haiku-4.5,chatgpt-gpt-6-luna-low [--calls 20] [--cap N] [--tag rep2]
真模型：每個模型 × 兩個版本各一次，每次最多 --calls 次呼叫（預設 20），這次合計 ≤ --cap（≤ CAP＝150，跨次累計由跑的人扣）；
結果存 runs/（--tag 加在檔名後）。
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES = os.path.dirname(HERE)
sys.path.insert(0, PROBES)
import probelib as pl  # noqa: E402
import llmop  # noqa: E402

CAP = 150
Q = os.path.join(HERE, "questions.json")
A = os.path.join(HERE, "answers.json")


def load_namespace():
    spec = importlib.util.spec_from_file_location("ns_probe", os.path.join(PROBES, "namespace", "probe.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_world(sp):
    """namespace 第 1～4 步，停在 a-job5 還在 model-a 上 hold 著。回現任 reviewer 的 tid。"""
    ns_mod = load_namespace()
    ns = ns_mod.NS(sp)
    for s, iface in ns_mod.SERVICES.items():
        if s == "model-x":
            continue
        sp.node("services/" + s, [{"name": "svc", "mode": "keep", "argv": [pl.PY, ns_mod.MOCK]}], interval_ms=100,
                files={"service.cfg.json": {"service_id": s, "interface": iface, "clients": ["reviewer"]}})
    sp.node("proj-a", [ns_mod.reviewer_item("proj-a", "model-a")], interval_ms=100)
    sp.node("proj-b", [ns_mod.reviewer_item("proj-b", "model-b")], interval_ms=100)
    sp.start()
    for i in range(1, 4):
        ns.mail("proj-b", "job%d" % i, "b-job%d" % i)
    for i in (1, 2):
        ns.mail("proj-a", "job%d" % i, "a-job%d" % i)
    sp.wait_for(lambda: all(ns.result("proj-a", "job%d" % i) for i in (1, 2)), msg="A 第一批沒做完")
    pl.write(ns.svc_path("model-a", "fault.json"), {"crash_after_exec": "a-job3-call-1"})
    ns.mail("proj-a", "job3", "a-job3")
    sp.wait_for(lambda: ns.exec_count("a-job3-call-1") == 1, msg="a-job3 沒執行")
    ns.mail("proj-a", "job4", "a-job4")
    sp.wait_for(lambda: os.path.exists(ns.svc_path("model-a", "clients", "reviewer", "requests", "a-job4-call-1.json")))
    epoch1 = ns.card("model-a").get("instance_epoch")
    old_svc = ns.live("services/model-a", "svc")[0]
    os.killpg(sp.task_file("services/model-a", old_svc, "pid.json")["pgid"], 9)
    sp.wait_for(lambda: ns.card("model-a").get("instance_epoch") not in (None, epoch1), msg="model-a 沒換 epoch")
    sp.wait_for(lambda: ns.result("proj-a", "job3") and ns.result("proj-a", "job4"), msg="job3／4 沒收尾")
    pl.write(ns.svc_path("model-a", "fault.json"), {"hold": True})
    ns.mail("proj-a", "job5", "a-job5")
    sp.wait_for(lambda: os.path.exists(ns.svc_path("model-a", "clients", "reviewer", "requests", "a-job5-call-1.json")))
    ns.reload("proj-a", ns_mod.reviewer_item("proj-a", "model-a2"))
    ns.mail("proj-a", "job6", "a-job6")
    sp.wait_for(lambda: ns.result("proj-a", "job6"), msg="job6 沒做完")
    _, new, _ = ns.reload("proj-a", ns_mod.reviewer_item("proj-a", "model-a2", prev="model-a"))
    sp.wait_for(lambda: ns.status("proj-a").get("state") == "ok" and ns.status("proj-a").get("by", "").endswith(new)
                and "a-job5-call-1" in (ns.status("proj-a").get("pending") or []), msg="新 reviewer 沒接上 model-prev")
    sp.wait_for(lambda: all(ns.result("proj-b", "job%d" % i) for i in range(1, 4)), msg="B 沒做完")
    nodes = ["services/" + s for s in ("model-a", "model-a2", "model-b")] + ["proj-a", "proj-b"]
    for n in nodes:
        sp.ctl("pause", node=n)
    sp.wait_for(lambda: all(sp.status().get("nodes", {}).get(n, {}).get("phase") == "paused" for n in nodes), timeout=10)
    return new


def snapshot(sp, dst):
    def ign(d, names):
        return [n for n in names if not (os.path.isfile(os.path.join(d, n)) or os.path.isdir(os.path.join(d, n))
                                         or os.path.islink(os.path.join(d, n)))]
    shutil.copytree(sp.root, dst, symlinks=True, ignore=ign)
    return dst


def make_hardcoded(card, dst):
    """同一個世界，拿掉服務卡、掛載點與 reload 的 diff；路徑寫死在 reviewer.cfg.json。"""
    shutil.copytree(card, dst, symlinks=True)
    for d, dirs, files in os.walk(dst):
        if "service.json" in files and os.path.basename(os.path.dirname(d)) == "clients":
            os.remove(os.path.join(d, "service.json"))
        if "mnt" in dirs and os.path.exists(os.path.join(d, "birth.json")):
            shutil.rmtree(os.path.join(d, "mnt"))
            dirs.remove("mnt")
        if "birth.json" in files:
            p = os.path.join(d, "birth.json")
            b = pl.fs.read_json(p, {}) or {}
            b.pop("mounts", None)
            pl.fs.write_json(p, b)
        if "ctl-done.json" in files:
            p = os.path.join(d, "ctl-done.json")
            c = pl.fs.read_json(p, {}) or {}
            pl.fs.write_json(p, {"op": c.get("op"), "by": c.get("by"), "why": "改了 reviewer.cfg.json，重起",
                                 "result": {"ok": True, "msg": "restart", "at": (c.get("result") or {}).get("at")}})
    for proj, svc in (("proj-a", "model-a2"), ("proj-b", "model-b")):
        tj = os.path.join(dst, proj, ".aos", "tasks.json")
        t = pl.fs.read_json(tj, {}) or {}
        for i in t.get("tasks", []):
            i.pop("mounts", None)
        pl.fs.write_json(tj, t)
        cfg = {"requests": "services/%s/clients/reviewer/requests" % svc,
               "receipts": "services/%s/clients/reviewer/receipts" % svc,
               "context": proj + "/context", "mail": proj + "/inbox"}
        if proj == "proj-a":
            cfg["old_receipts"] = "services/model-a/clients/reviewer/receipts"
        pl.fs.write_json(os.path.join(dst, proj, "reviewer.cfg.json"), cfg)
    return dst


# ---------------- 評分 ----------------

def parse_answer(text):
    if not text:
        return None
    for m in reversed(list(re.finditer(r"\{", text))):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and "q1" in obj:
            return obj
    return None


def norm(x):
    return x.strip().lower() if isinstance(x, str) else x


def grade(ans, world, key):
    """回 {q: bool}。q1 比實際位置（掛載點下的路徑也算對）。"""
    acc, k = key["accept"], key["answers"]
    out = {}
    if not isinstance(ans, dict):
        return {q: False for q in ("q1", "q2", "q3", "q4", "q5")}
    q1 = ans.get("q1")
    if isinstance(q1, str) and q1.strip():
        p = q1.strip()
        p = (p[2:] if p.startswith("./") else p).rstrip("/")
        out["q1"] = os.path.realpath(os.path.join(world, p)) == os.path.realpath(os.path.join(world, k["q1"]))
    else:
        out["q1"] = False
    out["q2"] = norm(ans.get("q2")) == k["q2"]
    q3 = ans.get("q3") if isinstance(ans.get("q3"), dict) else {}
    out["q3"] = all(norm(q3.get(r)) in [norm(x) for x in acc[v]] for r, v in k["q3"].items())
    out["q4"] = norm(ans.get("q4")) in acc["no"] if not isinstance(ans.get("q4"), bool) else ans.get("q4") is False
    q5 = ans.get("q5") if isinstance(ans.get("q5"), dict) else {}
    out["q5"] = norm(q5.get("active")) == k["q5"]["active"] and norm(q5.get("prev")) == k["q5"]["prev"]
    return out


def prompt(qs, tid):
    taskdir = "proj-a/.aos/tasks/%s" % tid
    system = ("你在一個用資料夾與 JSON 檔組成的系統裡。你只有一個工具 read_file：讀一個檔（回內容），"
              "或列一個資料夾（回每項名字，資料夾結尾加 /）。路徑相對空間根，\".\" 是根。沒有其他說明文件；"
              "請只靠讀檔找答案，不要猜。")
    goal = "\n".join([qs["role"].format(taskdir=taskdir), "", "請回答："] +
                     ["%s（%s）%s" % (q["id"], q["short"], q["q"]) for q in qs["questions"]] + ["", qs["answer_format"]])
    return system, goal


def script_steps(tid):
    t = "proj-a/.aos/tasks/%s" % tid
    reads = [t, t + "/birth.json", t + "/mnt/model/service.json", t + "/mnt/model-prev/service.json",
             t + "/mnt/context/checkpoint.json", t + "/mnt/model/requests/a-job6-call-1.json",
             t + "/mnt/model/receipts/a-job6-call-1.json", t + "/mnt/model-prev/receipts"]
    final = json.dumps({"q1": t + "/mnt/model/requests", "q2": "cc-proj-a",
                        "q3": {"a-job5-call-1": "pending", "a-job6-call-1": "settled"}, "q4": "no",
                        "q5": {"active": "model-a2", "prev": "model-a"}, "evidence": reads}, ensure_ascii=False)
    return [("read_file", {"path": p}) for p in reads] + [final]


def run_model(brain, world, qs, tid, max_calls, transcript=None):
    tools = llmop.FileTools(world, name="reviewer", read_only=sorted(os.listdir(world)))
    system, goal = prompt(qs, tid)
    out = llmop.run_agent(brain, tools, system, goal, max_calls=max_calls, timeout_s=600, transcript=transcript,
                          nudge=lambda final: None if parse_answer(final) else
                          "請只回一個 JSON 物件，照題目給的格式（q1～q5、evidence）。")
    reads = [x for x in tools.log if x["tool"] == "read_file"]
    out["reads"] = len(reads)
    out["read_errors"] = len([x for x in reads if not x.get("ok")])
    out["paths"] = [x["path"] for x in reads]
    return out


def main(argv):
    models = llmop.model_arg(argv)
    max_calls = int(argv[argv.index("--calls") + 1]) if "--calls" in argv else 20
    cap = min(CAP, int(argv[argv.index("--cap") + 1])) if "--cap" in argv else CAP     # 這次最多打幾次（跨次累計自己扣）
    tag = ("-" + argv[argv.index("--tag") + 1]) if "--tag" in argv else ""
    r = pl.Result("blindread")
    qs, key = pl.fs.read_json(Q), pl.fs.read_json(A)
    r.check("題目檔與標準答案檔在、五題都有答案", isinstance(qs, dict) and isinstance(key, dict)
            and [q["id"] for q in qs["questions"]] == ["q1", "q2", "q3", "q4", "q5"]
            and set(key["answers"]) == {"q1", "q2", "q3", "q4", "q5"})
    with pl.Space("blindread") as sp:
        tid = build_world(sp)
        card = snapshot(sp, os.path.join(sp.base, "world-card"))
        hard = make_hardcoded(card, os.path.join(sp.base, "world-hardcoded"))
        k = key["answers"]
        cl = os.path.join(card, "services", "model-a2", "clients", "reviewer")
        r.check("答案對得上世界：q1 的資料夾在、a-job6 的 charge_context 是 cc-proj-a",
                os.path.isdir(os.path.join(card, k["q1"])) and
                (pl.fs.read_json(os.path.join(cl, "requests", "a-job6-call-1.json"), {}) or {}).get("charge_context") == k["q2"])
        ra = os.path.join(card, "services", "model-a", "clients", "reviewer")
        r.check("答案對得上世界：a-job6 已 settled；a-job5 在 model-a 有請求、沒回條",
                (pl.fs.read_json(os.path.join(cl, "receipts", "a-job6-call-1.json"), {}) or {}).get("state") == "settled"
                and os.path.exists(os.path.join(ra, "requests", "a-job5-call-1.json"))
                and not os.path.exists(os.path.join(ra, "receipts", "a-job5-call-1.json")))
        b = pl.fs.read_json(os.path.join(card, "proj-a", ".aos", "tasks", tid, "birth.json"), {}) or {}
        m = {n: v.get("to") for n, v in (b.get("mounts") or {}).items()}
        r.check("答案對得上世界：現任 reviewer 掛 model → model-a2、model-prev → model-a",
                m.get("model", "").startswith("services/model-a2/") and m.get("model-prev", "").startswith("services/model-a/"), m)
        hard_cards = [d for d, _, f in os.walk(hard) if "service.json" in f and "clients" in d]
        r.check("hardcoded 版：沒有服務卡、沒有掛載點，路徑寫在 proj-a/reviewer.cfg.json",
                not hard_cards and not os.path.exists(os.path.join(hard, "proj-a", ".aos", "tasks", tid, "mnt"))
                and os.path.exists(os.path.join(hard, "proj-a", "reviewer.cfg.json")), hard_cards[:2])
        sb = run_model(llmop.ScriptBrain(script_steps(tid)), card, qs, tid, 30)
        g = grade(parse_answer(sb["final"]), card, key)
        r.check("照稿腦（card 版，只讀 8 個檔）五題全對；q1 寫掛載點下的路徑也算對", all(g.values()), g)
        wrong = {"q1": "services/model-a/clients/reviewer/requests", "q2": "cc-proj-b",
                 "q3": {"a-job5-call-1": "settled", "a-job6-call-1": "settled"}, "q4": "yes",
                 "q5": {"active": "model-a", "prev": None}}
        r.check("評分器會扣錯（全錯的答案 0 分）", not any(grade(wrong, card, key).values()))
        r.measure("card 版五題要讀的位元組（照稿腦的 8 個檔）",
                  sum(os.path.getsize(os.path.join(card, p)) for p in sb["paths"] if os.path.isfile(os.path.join(card, p))))

        if models:
            if os.system("curl -s -m 5 -o /dev/null http://127.0.0.1:4000/v1/models") != 0:
                r.finding("LiteLLM 代理 127.0.0.1:4000 不在，跳過真模型")
                return r.done()
            out_dir = os.path.join(HERE, "runs")
            os.makedirs(out_dir, exist_ok=True)
            used = 0
            rows = []
            for model in models:
                for variant, world in (("card", card), ("hardcoded", hard)):
                    budget = min(max_calls, cap - used)
                    if budget <= 0:
                        r.finding("呼叫上限 %d 用完，%s／%s 沒跑" % (cap, model, variant))
                        continue
                    tr = os.path.join(out_dir, "%s-%s%s.transcript.jsonl" % (variant, model.replace(".", "_"), tag))
                    if os.path.exists(tr):
                        os.remove(tr)
                    o = run_model(llmop.RealBrain(model), world, qs, tid, budget, transcript=tr)
                    used += o["calls"]
                    ans = parse_answer(o["final"])
                    g = grade(ans, world, key)
                    row = {"model": model, "variant": variant, "score": sum(g.values()), "grade": g, "answer": ans,
                           "calls": o["calls"], "tokens": o["tokens"], "reads": o["reads"],
                           "read_errors": o["read_errors"], "stop": o["stop"], "paths": o["paths"]}
                    rows.append(row)
                    pl.fs.write_json(os.path.join(out_dir, "%s-%s%s.json" % (variant, model.replace(".", "_"), tag)), row)
                    print("  %s／%s：%d/5 %s 呼叫 %d 讀 %d" % (model, variant, row["score"], g, o["calls"], o["reads"]), flush=True)
            pl.fs.write_json(os.path.join(out_dir, "summary%s.json" % tag),
                             {"at": pl.fs.now(), "calls": used, "cap": cap,
                              "rows": [{k2: v for k2, v in x.items() if k2 != "paths"} for x in rows]})
            r.measure("真模型呼叫數（這次上限 %d）" % cap, used)
            for x in rows:
                r.measure("%s／%s" % (x["model"], x["variant"]), {"分數": x["score"], "錯的題": [q for q, ok in x["grade"].items() if not ok],
                                                               "呼叫": x["calls"], "讀檔": x["reads"]})
    return r.done()


if __name__ == "__main__":
    pl.run_main(lambda: main(sys.argv[1:]))
