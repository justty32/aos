# judge.py - judge 格：拿判準比 run 格的結果，寫 $AOS_STACK/versions/<版>/verdict.json，再決定下一步
#   達成          → 把這一版放到 $AOS_WS/out/best/、寫報告，退 10（loop 收工、以 0 結束）
#   預算用完      → 把最好的那一版放到 out/best/、寫報告，stderr 一行 BudgetSpent，退 2（loop 以 2 結束；改 budget.json 再跑會接著改）
#   還沒達成      → 退 0，fsm 往下走到 improve
# verdict 的 feedback 是要給改進者看的：例子只給看得到的那幾組（hidden 的只說幾組沒過）；檢查程式的話就是它的 stdout。
import json, os, shutil, sys
import common
from common import VERSIONS, stack, ws


def norm(text):
    """比 stdout 時不計行尾空白與頭尾空行。"""
    return "\n".join(line.rstrip() for line in text.strip("\n").splitlines())


def quote(text):
    lines = text.rstrip("\n").splitlines() or [""]
    return "\n".join("  |" + l for l in lines)


current = (common.read(os.path.join(stack, "current.txt")) or "").strip()
vdir = os.path.join(VERSIONS, current)
runs_text = common.read(os.path.join(vdir, "runs.jsonl"))
if not current or runs_text is None:
    common.die("StackBad", "%s 還沒跑過（沒有 runs.jsonl）" % (current or "current.txt"))
runs = [json.loads(l) for l in runs_text.splitlines() if l.strip()]
kind, crit = common.criteria()

if kind == "cases":
    if len(runs) != len(crit):
        common.die("StackBad", "runs.jsonl 有 %d 組、judge/cases.json 有 %d 組（判準跑到一半改了？重跑這版）" % (len(runs), len(crit)))
    fails, hidden_fails = [], 0
    for i, (c, r) in enumerate(zip(crit, runs), 1):
        ok = (not r["timed_out"] and norm(r["stdout"]) == norm(c["stdout"])
              and ("code" not in c or r["code"] == c["code"]))
        if ok:
            continue
        if c.get("hidden"):
            hidden_fails += 1
            continue
        what = "逾時（%d 毫秒）" % c.get("timeout_ms", 10000) if r["timed_out"] else "結束碼 %d" % r["code"]
        fails.append("例子 %d：參數 %s，stdin：\n%s\n期望 stdout%s：\n%s\n實際（%s）stdout：\n%s%s" % (
            i, json.dumps(c.get("args", []), ensure_ascii=False), quote(c.get("stdin", "")),
            "（結束碼 %d）" % c["code"] if "code" in c else "", quote(c["stdout"]), what, quote(r["stdout"]),
            "\nstderr：\n" + quote(r["stderr"]) if r["stderr"].strip() else ""))
    total = len(crit)
    score = total - len(fails) - hidden_fails
    feedback = "\n\n".join(fails)
    if hidden_fails:
        feedback += ("\n\n" if feedback else "") + "另有 %d 組看不到的例子沒過（不給內容）。" % hidden_fails
else:
    r = runs[0]
    total = 1
    score = 1 if (r["code"] == 0 and not r["timed_out"]) else 0
    feedback = "檢查程式%s，它的輸出：\n%s" % ("逾時" if r["timed_out"] else "結束碼 %d" % r["code"], quote(r["stdout"]))
passed = score == total
common.write(os.path.join(vdir, "verdict.json"), json.dumps(
    {"version": current, "passed": passed, "score": score, "total": total, "feedback": feedback if not passed else "",
     "at": common.now()}, ensure_ascii=False) + "\n")


def report(why):
    """out/best/＝最好的那版；out/report.txt＝每一版的來歷與判定；out/result.json＝總結。"""
    best = common.best()
    out = os.path.join(ws, "out")
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, "best")
    if os.path.lexists(dst):
        shutil.rmtree(dst)
    common.copy_target(os.path.join(VERSIONS, best), dst)
    used, limit = common.used(), common.budget()
    lines = ["self-improve 報告（%s）" % common.now(), "結果：%s" % why,
             "最好的一版：%s（已複製到 out/best/）" % best,
             "用掉：改進 %d 輪（上限 %d）、%d 秒（上限 %d）、%d tokens（上限 %d）" % (
                 used["counter_rounds"], limit["rounds"], used["elapsed_ms"] // 1000, limit["elapsed_ms"] // 1000,
                 used["counter_tokens"], limit["tokens"]), ""]
    for v in common.versions():
        meta = common.read_json(os.path.join(VERSIONS, v, "version.json"), {})
        d = common.verdict(v)
        got = "%d/%d%s" % (d["score"], d["total"], "（達成）" if d["passed"] else "") if d else "沒判"
        src = "原版" if not meta.get("from") else "從 %s 改" % meta["from"]
        lines.append("%s（%s）：%s" % (v, src, got))
        diff = common.read(os.path.join(VERSIONS, v, "diff.txt"))
        if diff is not None:
            plus = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
            minus = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
            files = sorted({l.split(" ", 1)[1].split("\t")[0] for l in diff.splitlines() if l.startswith("+++ ")})
            lines.append("  改了：%s（+%d −%d）" % ("、".join(files) or "沒改", plus, minus))
        if meta.get("same_as"):
            lines.append("  跟 %s 一模一樣（繞回去了）" % meta["same_as"])
        if meta.get("ignored"):
            lines.append("  target/ 以外寫的東西沒採用：%s" % "、".join(meta["ignored"]))
        answer = common.read(os.path.join(VERSIONS, v, "answer.txt"))
        if answer:
            lines.append("  改進者說：" + " ".join(answer.split())[:300])
    for f in sorted(os.listdir(os.path.join(stack, "failed"))) if os.path.isdir(os.path.join(stack, "failed")) else []:
        lines.append("%s：改進者中途失敗（留在 stack 的 failed/%s）" % (f.split(".")[0], f))
    common.write(os.path.join(out, "report.txt"), "\n".join(lines) + "\n")
    common.write(os.path.join(out, "result.json"), json.dumps(
        {"passed": passed, "best": best, "score": common.verdict(best)["score"], "total": total,
         "used": used, "budget": limit, "at": common.now()}, ensure_ascii=False) + "\n")


if passed:
    report("達成（%s 全過）" % current)
    sys.exit(10)
used, limit = common.used(), common.budget()
over = [k for k, u in (("rounds", "counter_rounds"), ("elapsed_ms", "elapsed_ms"), ("tokens", "counter_tokens"))
        if used[u] >= limit[k]]                   # 用量是計數 counter_*（10-25）、預算是上限，照舊 rounds／tokens
if over:
    best = common.best()
    report("沒達成：預算用完（%s）" % "、".join(over))
    print("self-improve: BudgetSpent %s 用完了，最好的一版 %s（%d/%d）在 out/best/" % (
        "、".join(over), best, common.verdict(best)["score"], total), file=sys.stderr)
    sys.exit(2)
