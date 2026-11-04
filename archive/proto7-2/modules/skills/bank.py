#!/usr/bin/env python3
"""選用題庫：在暫存 node 放 11 個 skill（library/ 3 個＋workflows 8 個，都用 symlink），逐題 pick，印分數與效率四指標。

    python3 proto7-2/modules/skills/bank.py [--gateway llm.fake|llm.litellm] [--model M] [--out report.json]

未給 --node 的暫存 node 結束即清，報告 node 為 null；重跑不重問請給 --node。
真 AI 只在 --gateway llm.litellm 時用（每題 1 次，同題重跑不重問）。--local 不開帳、不問 AI。退出碼：0＝orig ≥8、longtask ≥16 且挑錯本 0、1＝未達標、2＝環境不對。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))
SKILLS = os.path.join(HERE, "aos7-skills")
BUDGET = os.path.join(TOP, "packs", "budget", "bin", "aos7-budget")


def setup(node, bank, wf, gateway):
    """建 node：skills 連結、已關的回合、帳。"""
    sk = os.path.join(node, "skills")
    os.makedirs(sk)
    for name in sorted(os.listdir(os.path.join(HERE, "library"))):
        os.symlink(os.path.join(HERE, "library", name), os.path.join(sk, name))
    for name in bank["workflows"]:
        os.symlink(os.path.join(wf, name), os.path.join(sk, name))
    os.makedirs(os.path.join(node, ".aos"))
    with open(os.path.join(node, ".aos", "round.json"), "w") as f:
        f.write('{"round":5,"open":false}\n')
    if gateway is None:
        return
    os.makedirs(os.path.join(node, "budget", "llm"))
    grant = {"v": 1, "grant": "skills-bank", "budget": "llm", "holder": "skills", "resource": "llm.tokens",
             "gateway": gateway, "amount": 100000000, "clock": "completed_tock", "from": 0, "until": 1000000,
             "delegate": False}
    with open(os.path.join(node, "budget", "llm", "grant.json"), "w") as f:
        json.dump(grant, f)
    subprocess.run([sys.executable, BUDGET, "init", "budget/llm"], cwd=node, check=True, capture_output=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bank.py", description="skills 選用題庫")
    ap.add_argument("--gateway", default="llm.fake", choices=["llm.fake", "llm.litellm"])
    ap.add_argument("--model", default="chatgpt-gpt-6-sol-high")
    ap.add_argument("--workflows", default=os.path.join(os.environ.get("AOS7_WF_HOME", os.path.expanduser("~/repo/workflows")), "skills"))
    ap.add_argument("--node", help="沿用這個 node（重跑不重問）；不給就新建暫存 node")
    ap.add_argument("--out")
    ap.add_argument("--local", action="store_true", help="不開帳、不起 ledger、0 次 AI")
    a = ap.parse_args(argv)
    with open(os.path.join(HERE, "examples", "bank.json")) as f:
        bank = json.load(f)
    with open(os.path.join(HERE, "examples", "bank", "longtask.json")) as f:
        longtask = json.load(f)
    if not all(os.path.isfile(os.path.join(a.workflows, n, "SKILL.md")) for n in bank["workflows"]):
        print("bank.py: 找不到 workflows 的 skill（--workflows 或 AOS7_WF_HOME）", file=sys.stderr)
        return 2
    node = a.node or tempfile.mkdtemp(prefix="aos7-skills-bank.")
    try:
        if not os.path.isdir(os.path.join(node, "skills")):
            setup(node, bank, a.workflows, None if a.local else a.gateway)
        if a.local and os.path.exists(os.path.join(node, "budget/llm")):
            print("bank.py: --local 要用沒有 budget/llm 的 node", file=sys.stderr)
            return 2
        ledger = None if a.local else subprocess.Popen([sys.executable, BUDGET, "ledger", "budget/llm"], cwd=node,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        sys.path[:0] = [os.path.join(TOP, "packs", "budget")]
        import aos7_budget
        rows = []
        try:
            if ledger is not None and not aos7_budget.ledger_running(aos7_budget.Bud(os.path.join(node, "budget/llm")), wait=2):
                raise RuntimeError("帳任務未能啟動")
            for setname, questions in (("orig", bank["questions"]), ("longtask", longtask["questions"])):
                for item in questions:
                    t = time.monotonic()
                    argv = [sys.executable, SKILLS, "pick", node, item["q"], "--model", a.model]
                    if not a.local:
                        argv += ["--budget", "budget/llm"]
                    p = subprocess.run(argv, capture_output=True, text=True, timeout=900)
                    got = p.stdout.strip()
                    got = os.path.basename(os.path.dirname(got)) if got.endswith("SKILL.md") else got or None
                    rows.append({"set": setname, "q": item["q"], "want": item["want"], "got": got,
                                 "ok": got == item["want"], "rc": p.returncode,
                                 "seconds": round(time.monotonic() - t, 3), "err": p.stderr.strip()[-300:] or None})
        finally:
            if ledger is not None:
                ledger.terminate()
                ledger.wait(10)
        with open(os.path.join(node, "skills", ".pick", "log.jsonl")) as f:
            log = [json.loads(line) for line in f if line.strip()]
        last, retries = {}, 0          # 重試＝同 call 上一次沒成功（rc≠0）又再來；成功後重跑只重印回條，不算
        for rec in log:
            retries += rec["call"] in last and last[rec["call"]] != 0
            last[rec["call"]] = rec["rc"]
        used = [rec.get("used") or 0 for rec in log[-len(rows):]]
        score = sum(r["ok"] for r in rows)
        sets = {name: sum(r["ok"] for r in rows if r["set"] == name) for name in ("orig", "longtask")}
        ai_calls = sum(rec["via"] == "llmcall" for rec in log)
        wrong_book = sum(r["got"] != r["want"] and r["got"] != "none" for r in rows)
        report = {"ai_calls": ai_calls, "wrong_book": wrong_book, "sets": sets, "v": 1, "gateway": a.gateway, "model": a.model, "node": node if a.node else None, "score": score, "of": len(rows),
                  "metrics": {"tokens_per_q": round(sum(used) / len(rows), 1), "parallel": 1,
                              "seconds_per_q": round(sum(r["seconds"] for r in rows) / len(rows), 3),
                              "retries": retries},
                  "rows": rows}
        text = json.dumps(report, ensure_ascii=False, indent=1)
        if a.out:
            with open(a.out, "w") as f:
                f.write(text + "\n")
        for r in rows:
            print("%s %-26s ← %s" % ("對" if r["ok"] else "錯", r["got"], r["q"]))
        print("選對 %d／%d；每題 token %s、並行 1、每題 %s 秒、重試 %d；orig %d／10、longtask %d／17、ai_calls %d、wrong_book %d%s" % (
            score, len(rows), report["metrics"]["tokens_per_q"], report["metrics"]["seconds_per_q"],
            report["metrics"]["retries"], sets["orig"], sets["longtask"], ai_calls, wrong_book, "；node：" + node if a.node else ""))
        return 0 if sets["longtask"] >= 16 and sets["orig"] >= 8 and wrong_book == 0 else 1
    finally:
        if not a.node:
            shutil.rmtree(node, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
