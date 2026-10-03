"""ci：不用 LLM 的測試機器人（keep 任務）。每個 tock 看信箱：每封信的 body 當原始碼（有 parse_ranges／format_ranges
就當 ranges.py、否則當 dur.py），跑對應的 check_*.py，
把 PASS／FAIL 與失敗案例回信給寄件者。寄信、搬信、outbox 都用 agent 的同一套工具（經過掛載點，S-23）。"""
import json
import os
import re
import signal
import subprocess
import sys

# proto7-1 的 lib：tick 把 bin/ 放在 PATH 最前面（spec 第 5 節），lib 在它旁邊
_BIN = next((p for p in os.environ.get("PATH", "").split(os.pathsep) if os.path.exists(os.path.join(p, "aos7-agent"))), "")
sys.path.insert(0, os.path.join(os.path.dirname(_BIN), "lib"))
import aos7_agent_tools as tools  # noqa: E402
from aos7_fs import append_jsonl, now, read_json, task_env, wait_tock, write_json  # noqa: E402

FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract(body):
    """信裡的程式碼：有 ``` 圍欄取第一段，否則整段。"""
    body = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    m = FENCE.search(body)
    return m.group(1) if m else body


def module_of(code):
    return "ranges" if re.search(r"def\s+(parse|format)_ranges\b", code) else "dur"


def check(node, n, code):
    mod = module_of(code)
    d = os.path.join(node, "work", "runs", str(n))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, mod + ".py"), "w", encoding="utf-8") as f:
        f.write(code)
    try:
        p = subprocess.run([sys.executable, "-B", "check_%s.py" % mod, d], cwd=node, capture_output=True, text=True,
                           timeout=10)
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        r = {"passed": 0, "total": 20, "fails": ["測試沒跑完：%r" % e]}
    r["module"] = mod
    write_json(os.path.join(d, "result.json"), r)
    return r


def main():
    ctx = task_env()
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    st = read_json(os.path.join(ctx["node"], "work", "ci-state.json"), {"n": 0}) or {"n": 0}
    rnd = 0
    while True:
        r = wait_tock(ctx["task"], rnd, timeout=0.5)
        if r is None:
            continue
        rnd = r
        for x in tools.flush_outbox(ctx):
            print(json.dumps({"at": now(), "round": rnd, "msg": x}, ensure_ascii=False), flush=True)
        names = tools.list_inbox(ctx["node"])
        for name, l in zip(names, tools.read_letters(ctx["node"], names)):
            st["n"] += 1
            res = check(ctx["node"], st["n"], extract(l.get("body")))
            ok = not res["fails"]
            head = "%s.py %s %d/%d（第 %d 次測試）" % (res["module"], "PASS" if ok else "FAIL", res["passed"],
                                                    res["total"], st["n"])
            body = head if ok else head + "失敗案例：\n" + "\n".join(res["fails"][:12])
            out = tools.do_tool(ctx, {"tool": "send", "to": l.get("from") or "", "body": body}, rnd) \
                if l.get("from") else "沒有寄件者，不回"
            append_jsonl(os.path.join(ctx["node"], "work", "ci-log.jsonl"),
                         {"at": now(), "round": rnd, "n": st["n"], "module": res["module"], "from": l.get("from"), "letter": name,
                          "passed": res["passed"], "total": res["total"], "reply": out})
            print(json.dumps({"at": now(), "round": rnd, "msg": out}, ensure_ascii=False), flush=True)
            tools.move_done(ctx["node"], [name])
            write_json(os.path.join(ctx["node"], "work", "ci-state.json"), st)


if __name__ == "__main__":
    main()
