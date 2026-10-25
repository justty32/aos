"""demo.py FIELD fake|real [steps...] — 自我優化兩次示範（b2_selfopt 第 3、4 項）。
steps（預設全部、照順序，做過的跳過）：init r0 r1 writer plan r2
  init：train/init → tree/、set/ 多放「舊車票」題（同 round6 teach 示範）
  r0  ：舊車票題假腦跑一次（director 是純程式，假腦也會降級＋記難例；0 token）→ record 第 0 輪（難例收進 tree/，帶稿紙）
  r1  ：把 round6 measure 的 trim_after 6 次真腦跑（現在的樹）＋teach/round1 舊車票真腦 1 次匯入 runs/1/（0 token）→ score、record 第 1 輪（改前快照）
  writer：host 優化 draft/tools/writer（agent：它自己的腦＋system.txt）
  plan：host 優化 draft/tools/director/tools/plan_template（非 agent：臨時配腦）
  r2  ：changes/1.json（兩條 selfopt、touched、cost）→ 第 2 輪：第一題 ×2＋舊車票 ×1（fake／real）→ score、record（梯度）
"""
import json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
P8 = "/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4ee4157053b3206d/proto8"
GB = P8 + "/topdown/galtxt-b"
R6 = GB + "/plan/runs/round6"
bins = [P8 + "/impls/%s/bin" % n for n in ("aos-exec", "aos-loop", "aos-fsm", "aos-daemon", "aos-json")]
F = os.path.abspath(sys.argv[1])
real = sys.argv[2] == "real"
steps = sys.argv[3:] or ["init", "r0", "r1", "writer", "plan", "r2"]
Q1, QT = "新書_宮澤_主角先_梅花章", "新書_宮澤_主角先_舊車票"
W, PT = "draft/tools/writer", "draft/tools/director/tools/plan_template"
env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "GALTXT_", "SELFOPT_"))}
env["PATH"] = ":".join(bins + [env["PATH"]])
renv = dict(env, AOS_BRAIN_URL="http://localhost:4000/v1") if real else env
os.makedirs(F, exist_ok=True)
stack = F + "/.stack/"
os.makedirs(stack, exist_ok=True)


def ex(*a, e=None):
    r = subprocess.run(["aos-exec"] + list(a), env=dict(e or env, AOS_STACK=stack), capture_output=True, text=True)
    print(" ".join(x.replace(GB, "GB").replace(F, "F") for x in a), "→", r.returncode, r.stdout.strip()[-200:], r.stderr.strip()[-400:], flush=True)
    return r


def rnd(n):
    json.dump({"round": n}, open(stack + "round.json", "w"))


def run_tree(ws, q, e):
    if os.path.exists(os.path.join(ws, "run.json")):
        return
    shutil.rmtree(ws, ignore_errors=True)
    os.makedirs(os.path.join(ws, "new"))
    shutil.copy(os.path.join(F, "set", q + ".json"), os.path.join(ws, "new"))
    t = time.time()
    r = subprocess.run(["aos-exec", "--ws", ws, F + "/tree"], env=e, capture_output=True, text=True, timeout=1500)
    json.dump({"code": r.returncode, "elapsed_ms": int((time.time() - t) * 1000), "brain": "real" if "AOS_BRAIN_URL" in e else "fake"},
              open(os.path.join(ws, "run.json"), "w"))
    print("run", os.path.relpath(ws, F), r.returncode, r.stderr[-300:], flush=True)


if "init" in steps:
    ex("--ws", F, GB + "/train/init")
    q = json.load(open(GB + "/train/set/%s.json" % Q1))
    q["switches"] = {"first_speaker": "主角", "prop": "舊車票"}
    q["must_mention"] = [["新書", "進新書日"], ["舊車票"]]
    json.dump(q, open(os.path.join(F, "set", QT + ".json"), "w"), ensure_ascii=False, indent=1)

if "r0" in steps:
    rnd(0)
    run_tree(os.path.join(F, "runs", "0", QT, "1"), QT, env)
    ex("--ws", F, GB + "/train/record")

if "r1" in steps:
    rnd(1)
    summ = {r["ws"]: r for r in json.load(open(R6 + "/measure/summary.json"))["trim_after"]["rows"]}
    srcs = [("measure/trim_after/%s" % s, s) for s in summ]
    srcs = [(R6 + "/measure/" + s, s) for s in summ] + [(R6 + "/teach/round1", "teach/round1")]
    for src, tag in srcs:
        if tag.startswith("teach"):
            q, k = QT, "1"
        else:
            _, q, k = tag.split("/")
        ws = os.path.join(F, "runs", "1", q, k)
        if os.path.exists(ws):
            continue
        os.makedirs(os.path.join(ws, "out", q))
        for n in ("answer.txt", "score.json", "measure.json", "check.json"):
            if os.path.exists(os.path.join(src, n)):
                shutil.copy(os.path.join(src, n), os.path.join(ws, "out", q, n))
        rj = {"code": 0, "imported_from": "plan/runs/round6/" + tag}
        if tag in summ:
            rj["tool_calls"] = summ[tag]["tool_calls"]
            rj["counter_tool_args_bad"] = summ[tag]["writer_tool_replies_argbad"]
        json.dump(rj, open(os.path.join(ws, "run.json"), "w"), ensure_ascii=False)
    ex("--ws", F, GB + "/train/score")
    ex("--ws", F, GB + "/train/record")


def host(name, q):
    if os.path.exists(os.path.join(F, "selfopt", name, "report.json")):
        return
    os.makedirs(os.path.join(F, "new"), exist_ok=True)
    json.dump(q, open(os.path.join(F, "new", name + ".json"), "w"), ensure_ascii=False)
    t = time.time()
    r = subprocess.run(["aos-exec", "--ws", F, GB + "/lib/selfopt/host"], env=dict(renv, AOS_STACK=F + "/selfopt/.stack_%s/" % name),
                       capture_output=True, text=True, timeout=3000)
    print("host", name, r.returncode, "%.0fs" % (time.time() - t), r.stderr[-1500:], flush=True)


WRITER_EVIDENCE = [
    "plan/runs/round6/measure.md（真腦 luna-low、4 題×1＋第一題多 2 次，每組 6 次）：",
    "現在的樹（有 trim）：根 token 平均 20204／次、其中 writer 16612（3 次問腦：叫 lint、叫 trim、交稿）；總分 5.00（σ 0）；lint 違規 0/6；腦 6/6 叫 trim 但 trim 6 次 changes 全空（稿子交到 trim 前已被 lint 自檢修乾淨）。",
    "不給 trim 的那組（GALTXT_OFF_TRIM）：根 token 19402、writer 15843；總分 4.83；6 次裡有 3 次第一次叫 lint 漏給 brief_path（工具回 ArgumentsBad、只好再叫一次），而且幾乎每次自檢兩回。",
    "每多一次工具來回，整段對話（稿紙＋前面幾則）要重送一次，約 +5000 token。",
    "read_runs 第 1 輪就是現在的樹那 6 次（匯入的），可以看每次叫工具的順序。"]
PT_EVIDENCE = [
    "plan/runs/round6/teach.md：表外的開關組合 主角|舊車票 不在 plans.json 上，director 只好用 default 表（score.json 帶 degraded），難例記在 director 的 hard_cases.jsonl（read_self 看得到，reason 以「plan_template:」開頭）。",
    "第 0 輪：舊車票題又降級了一次（同一筆難例）。",
    "表的每一列要能過 plan_lint（beat 文法 B0 B1 B2 B3+ (B4) B5 (B6) B7、每組必提詞要有一拍認領、拍數合理）；佔位 {hero}／{heroine}／{m0}／{m1}／{prop} 由 plan_template 填。"]

if "writer" in steps:
    q = {"mode": "optimize", "node": W, "round": 1,
         "goal": "請優化：降低 token 且分數不掉（證據：measure.md——lint 漏給 brief_path、自檢兩回、trim 叫了卻沒改字）",
         "evidence": WRITER_EVIDENCE, "max_calls": 12, "max_tokens": 45000, "self_test": "real" if real else "fake"}
    if not real:
        q["fake_script"] = [{"name": "read_self", "arguments": {}}, {"name": "read_runs", "arguments": {"round": 1}},
                            {"name": "edit_self", "arguments": {"path": "system.txt", "edits": [{"old_text": "最多自檢兩次。", "new_text": "最多自檢一次。"}]}},
                            {"name": "run_self_test", "arguments": {}}, {"name": "note", "arguments": {"why": "假腦"}}]
    host("writer", q)

if "plan" in steps:
    q = {"mode": "optimize", "node": PT, "round": 1,
         "goal": "請優化：消化 hard_cases——讓表外的「主角|舊車票」不再降級（在你的 plans.json 補一列），新列要過 plan_lint、不動別的列",
         "evidence": PT_EVIDENCE, "max_calls": 10, "max_tokens": 15000, "self_test": "fake"}
    if not real:
        row = json.load(open(R6 + "/teach/taught_row.json"))["主角|舊車票"]
        row.pop("taught")
        q["fake_script"] = [{"name": "read_self", "arguments": {}},
                            {"name": "edit_self", "arguments": {"path": "plans.json", "edits": [{"old_text": '"plans": {\n', "new_text": '"plans": {\n  "主角|舊車票": %s,\n' % json.dumps(row, ensure_ascii=False)}]}},
                            {"name": "run_self_test", "arguments": {"question": QT}}, {"name": "note", "arguments": {"why": "假腦"}}]
    host("plan", q)

if "plan2" in steps:      # 第一次 plan session 用 edits 改 JSON 一直 TextMissing、預算用完；edit_self 加了 set 之後再來一次（預算壓到 6000＝最多兩三次問腦）
    q = {"mode": "optimize", "node": PT, "round": 1,
         "goal": "請優化：消化 hard_cases——讓表外的「主角|舊車票」不再降級（在你的 plans.json 補一列），新列要過 plan_lint、不動別的列",
         "evidence": PT_EVIDENCE + ["上一次 session（selfopt/plan）用 edit_self 的 edits 改 plans.json，old_text 猜錯縮排 → TextMissing，預算用完、沒改成；改 JSON 請用 edit_self 的 set（JSON 指標，例 /plans/主角|舊車票）。"],
         "max_calls": 6, "max_tokens": 6000, "self_test": "fake"}
    host("plan2", q)

if "r2" in steps:
    cp = os.path.join(F, "changes", "1.json")
    if not os.path.exists(cp):
        moves, tokens = [], 0
        for name, node in (("writer", W), ("plan", PT), ("plan2", PT)):
            if not os.path.exists(os.path.join(F, "selfopt", name, "report.json")):
                continue
            rep = json.load(open(os.path.join(F, "selfopt", name, "report.json")))
            moves.append({"kind": "selfopt", "node": node, "status": "applied", "why": rep["goal"], "session": "selfopt/%s" % name,
                          "changed": sorted({e["path"] for e in rep["edits"]}), "counter_tokens": rep["counter_tokens"],
                          "counter_attempted_violations": len(rep["attempted_violations"])})
            tokens += rep["counter_tokens"]
        os.makedirs(os.path.dirname(cp), exist_ok=True)
        json.dump({"round": 1, "moves": moves, "touched": sorted({m["node"] for m in moves if m["changed"]}), "cost": {"counter_tokens": tokens},
                   "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": "selfopt host（不是 train/apply）"},
                  open(cp, "w"), ensure_ascii=False, indent=1)
    rnd(2)
    st = os.path.join(F, "selfopt", "writer", "tests", "1")       # writer 的真腦自測：改完之後沒再改，跑的就是最後這棵樹、分數是外部量尺打的 → 當第 2 輪第一題的第 1 次（省 2 萬）
    w1 = os.path.join(F, "runs", "2", Q1, "1")
    if os.path.exists(os.path.join(st, "run.json")) and not os.path.exists(w1):
        shutil.copytree(st, w1, symlinks=True)
        rj = json.load(open(os.path.join(w1, "run.json")))
        rj["imported_from"] = "selfopt/writer/tests/1（writer session 的真腦 run_self_test）"
        json.dump(rj, open(os.path.join(w1, "run.json"), "w"), ensure_ascii=False)
    jobs = [(os.path.join(F, "runs", "2", Q1, "2"), Q1, renv), (os.path.join(F, "runs", "2", QT, "1"), QT, renv if "qt_real" in sys.argv else env)]
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda j: run_tree(*j), jobs))
    ex("--ws", F, GB + "/train/score")
    ex("--ws", F, GB + "/train/record")
