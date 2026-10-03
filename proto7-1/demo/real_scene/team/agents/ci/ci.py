"""ci：不用 LLM 的測試機器人（keep 任務）。每個 tock 看信箱：每封信的 body 當原始碼（定義了 parse_ranges／format_ranges
就當 ranges.py、parse_duration／format_duration 就當 dur.py，都沒有就回 FAIL「看不出是哪個模組」），跑對應的 check_*.py，
把 PASS／FAIL 與失敗案例回信給寄件者。寄信、搬信、outbox 都用 agent 的同一套工具（經過掛載點，S-23）。

為了不跟 agent 互相觸發成迴圈（problems-real.md R-6、R-14）：
- 信裡沒有任何 `def` 的（「謝謝」「已完成」之類）不測、不回。
- 跟測過的完全相同的程式碼不再測、不回（結果寄件者已經拿過了）。
PASS 時另把結果和程式碼寄給 ci.json 的 `cc_pass` 清單（例如負責人），讓它拿到第一手結果（R-7）。"""
import hashlib
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

extract = tools.extract_code  # 信裡的程式碼：有 ``` 圍欄取第一段，否則整段


def module_of(code):
    """定義了哪個模組的函式；都沒有回 None。"""
    if re.search(r"def\s+(parse|format)_ranges\b", code):
        return "ranges"
    if re.search(r"def\s+(parse|format)_duration\b", code):
        return "dur"
    return None


def classify(body, seen):
    """這封信要怎麼處理：("not_code", code, None)＝沒有 def，不測不回；("dup", code, 舊結果)＝測過一樣的；
    ("test", code, 指紋)＝要測。seen＝{指紋: 舊結果}。"""
    code = extract(body)
    if not re.search(r"^\s*def\s+\w+", code, re.M):
        return "not_code", code, None
    h = hashlib.sha1(code.strip().encode("utf-8")).hexdigest()[:10]
    if h in seen:
        return "dup", code, seen[h]
    return "test", code, h


def check(node, n, code):
    mod = module_of(code)
    if mod is None:
        return {"passed": 0, "total": 0, "module": "?",
                "fails": ["看不出是哪個模組：要定義 parse_duration／format_duration（dur.py）或 parse_ranges／format_ranges（ranges.py）"]}
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


def handle(ctx, st, l, rnd, cc=()):
    """處理一封信；回一行紀錄（dict）。st＝{"n", "seen"} 會被更新。"""
    sender = l.get("from")
    kind, code, info = classify(l.get("body"), st.setdefault("seen", {}))
    rec = {"at": now(), "round": rnd, "from": sender, "kind": kind}
    if kind == "not_code":
        return dict(rec, reply="不是原始碼，不測不回")
    if kind == "dup":
        return dict(rec, n=info["n"], module=info["module"], passed=info["passed"], total=info["total"],
                    reply="跟第 %d 次一樣，不測不回" % info["n"])
    st["n"] += 1
    res = check(ctx["node"], st["n"], code)
    ok = not res["fails"]
    st["seen"][info] = {"n": st["n"], "module": res["module"], "passed": res["passed"], "total": res["total"]}
    head = "%s.py %s %d/%d（第 %d 次測試）" % (res["module"], "PASS" if ok else "FAIL", res["passed"], res["total"], st["n"])
    body = head if ok else head + "失敗案例：\n" + "\n".join(res["fails"][:12])
    out = tools.do_tool(ctx, {"tool": "send", "to": sender, "body": body}, rnd) if sender else "沒有寄件者，不回"
    for to in cc if ok else ():
        if to != sender:
            out += "｜" + tools.do_tool(ctx, {"tool": "send", "to": to, "body": "%s，寄件者 %s。通過的完整原始碼：\n```python\n%s\n```\n"
                                              % (head, sender, code)}, rnd)
    return dict(rec, n=st["n"], module=res["module"], passed=res["passed"], total=res["total"], reply=out)


def main():
    ctx = task_env()
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    st = read_json(os.path.join(ctx["node"], "work", "ci-state.json"), {"n": 0}) or {"n": 0}
    cc = (read_json(os.path.join(ctx["node"], "ci.json"), {}) or {}).get("cc_pass") or []
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
            rec = handle(ctx, st, l, rnd, cc)
            append_jsonl(os.path.join(ctx["node"], "work", "ci-log.jsonl"), dict(rec, letter=name))
            print(json.dumps({"at": now(), "round": rnd, "msg": rec["reply"]}, ensure_ascii=False), flush=True)
            tools.move_done(ctx["node"], [name])
            write_json(os.path.join(ctx["node"], "work", "ci-state.json"), st)


if __name__ == "__main__":
    main()
