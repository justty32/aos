#!/usr/bin/env python3
"""真模型場景：lead／coder（＋中途加入的 rita）用真的 LLM 合寫 dur.py 與 ranges.py，靠 ci 機器人的隱藏測試驗收。

    python3 proto7-1/demo/real.py [--root DIR] [--max-calls 400] [--max-seconds 900] [--join-after 60]

只打 LiteLLM 代理 http://127.0.0.1:4000/v1（模型寫在 demo/real_scene 與 demo/real_later 的 agent.json）。
不放進 unittest。跑到 lead 寫出 work/DONE.md、或 LLM 呼叫數到上限、或超過時間就停，最後印時間線摘要與統計。

場景：team（kernel：卡住重啟、預算 pause）、team/agents/lead（luna）、team/agents/coder（deepseek）、
team/agents/ci（不用 LLM 的測試機器人，信的 body 當原始碼跑隱藏測試、回 PASS／FAIL）。
coder 第一次收到 ci 結果後（或 --join-after 秒後），把 demo/real_later/rita（claude-haiku，審稿者）放進空間、
kernel.json 加成員：rita 寄信自我介紹靠執行中加掛，kernel 自己加掛 rita 的 .aos。
"""
import argparse
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P71 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(P71, "lib"))
sys.path.insert(0, HERE)
import aos7_audit  # noqa: E402
import aos7_fs as fs  # noqa: E402
from play import our_procs  # noqa: E402

DAEMON = os.path.join(P71, "bin", "aos7-daemon")
AGENTS = ("lead", "coder", "rita")


def tasks_of(root, who, name=None):
    out = sorted(glob.glob(os.path.join(root, "team", "agents", who, ".aos", "tasks", "*")))
    return [d for d in out if name is None or os.path.basename(d).startswith(name + "-r")]


def llm_calls(root):
    """全部 agent 任務的 usage.json 加總（含已結束、被 restart 掉的）。"""
    calls = tokens = 0
    for p in glob.glob(os.path.join(root, "team", "agents", "*", ".aos", "tasks", "*", "usage.json")):
        u = fs.read_json(p, {}) or {}
        calls += int(u.get("calls", 0))
        tokens += int(u.get("tokens", 0))
    return calls, tokens


def live_state(root, who):
    """這個 agent 最新任務的 state.json 狀態字（給跑著時的進度行）。"""
    ds = tasks_of(root, who, "agent")
    if not ds:
        return "-"
    d = max(ds, key=lambda x: (fs.read_json(os.path.join(x, "birth.json"), {}) or {}).get("round", 0))
    st = fs.read_json(os.path.join(d, "state.json"), {}) or {}
    return "%s@r%s" % (st.get("state", "?"), st.get("round", "?"))


def join_rita(root):
    shutil.copytree(os.path.join(HERE, "real_later", "rita"), os.path.join(root, "team", "agents", "rita"))
    kpath = os.path.join(root, "team", "kernel.json")
    cfg = fs.read_json(kpath, {})
    cfg["members"] = cfg.get("members", []) + ["agents/rita"]
    fs.write_json(kpath, cfg)


def run(root, a, log):
    """起 daemon、盯著呼叫數與完成條件、停掉；回 (殘留程序, 停的原因, 秒數, 取樣)。被中斷也照樣停 daemon。"""
    out = open(os.path.join(root, "daemon.out"), "w")
    env = fs.env_with_bin()
    env["AOS7_AUDIT"] = "1"
    d = subprocess.Popen([sys.executable, DAEMON, root], stdout=out, stderr=subprocess.STDOUT,
                         env=env, start_new_session=True)

    def _term(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, _term)
    t0, samples = time.monotonic(), []
    try:
        why = watch(root, a, log, d, t0, samples)
    except KeyboardInterrupt:
        why = "被中斷（SIGINT／SIGTERM）"
    secs = time.monotonic() - t0
    fs.write_json(os.path.join(root, ".aosd", "ctl", "zz-real-stop.json"), {"op": "stop", "kill": True, "by": "real.py"})
    try:
        d.wait(timeout=15)
    except subprocess.TimeoutExpired:
        d.terminate()
        d.wait(timeout=5)
    time.sleep(0.5)
    left = our_procs(root)
    for p in left:
        try:
            os.kill(p, signal.SIGKILL)
        except OSError:
            pass
    return left, why, secs, samples


def watch(root, a, log, d, t0, samples):
    """每 0.5 秒看一次：加入 rita、印狀態變化、判斷要不要停。回停的原因。"""
    joined, done_at, last_line = False, None, None
    quiet_since, last_activity = 0.0, None
    margin = 2 * len(AGENTS)  # 每個 agent 同時最多一個 think 在飛（含一次重問＝2 次呼叫），留餘裕保證不超過上限
    while d.poll() is None:
        time.sleep(0.5)
        t = time.monotonic() - t0
        calls, tokens = llm_calls(root)
        if not joined and (t > a.join_after or glob.glob(os.path.join(root, "team/agents/ci/sent.jsonl"))):
            join_rita(root)
            joined = True
            log("  [%5.1fs] 加入新成員 rita（node 放進空間＋kernel.json 加成員）" % t)
        states = {w: live_state(root, w) for w in AGENTS}
        st = fs.read_json(os.path.join(root, ".aosd", "status.json"), {}) or {}
        paused = sorted(k for k, v in (st.get("nodes") or {}).items() if v.get("paused"))
        line = "%s calls=%d%s" % (" ".join("%s:%s" % kv for kv in states.items()), calls,
                                  (" paused=" + ",".join(paused)) if paused else "")
        samples.append({"t": round(t, 1), "calls": calls, "tokens": tokens, "paused": paused, "states": states})
        if _changed(line, last_line):
            log("  [%5.1fs] %s" % (t, line))
            last_line = line
        if done_at is None and os.path.exists(os.path.join(root, "team/agents/lead/work/DONE.md")):
            done_at = t
            log("  [%5.1fs] lead 寫出 DONE.md，再跑 %d 秒收尾" % (t, a.grace))
        if done_at is not None and t - done_at > a.grace:
            return "完成（lead 寫了 DONE.md）"
        if calls >= a.max_calls - margin:
            return "LLM 呼叫數到上限（%d ≥ %d − %d）" % (calls, a.max_calls, margin)
        activity = (calls, len(glob.glob(os.path.join(root, "team/agents/*/inbox/**/*.json"), recursive=True)))
        if activity != last_activity:
            quiet_since, last_activity = t, activity
        if t - quiet_since > a.idle_stop:
            return "全員閒置 %d 秒（沒有新的 LLM 呼叫、沒有新信）" % a.idle_stop
        if t > a.max_seconds:
            return "超過時間上限 %d 秒" % a.max_seconds
    return "daemon 自己結束了"


def _changed(line, last):
    """只在「狀態字」或呼叫數變了才印（回合數每半秒都在變，不算）。"""
    strip = lambda x: " ".join(w.split("@")[0] for w in (x or "").split())  # noqa: E731
    return strip(line) != strip(last)


def runs_of(trace):
    """trace.jsonl → 狀態連續段 [(state, 起回合, 迄回合, 段內處理的 tock 數)]。"""
    out = []
    for t in trace:
        if out and out[-1][0] == t["state"]:
            s, a, _, n = out[-1]
            out[-1] = (s, a, t["round"], n + 1)
        else:
            out.append((t["state"], t["round"], t["round"], 1))
    return out


def report(root, log, secs, samples):
    t_start = None
    stats = {}
    log("\n== 各 agent：LLM 呼叫、回合、閒置 ==")
    for who in ("lead", "coder", "rita"):
        node = os.path.join(root, "team", "agents", who)
        if not os.path.isdir(node):
            continue
        cfg = fs.read_json(os.path.join(node, "agent.json"), {})
        model = (cfg.get("llm") or {}).get("model")
        calls = []
        trace = []
        tids = tasks_of(root, who, "agent")
        for d in tids:
            calls += [dict(c, tid=os.path.basename(d)) for c in fs.read_jsonl(os.path.join(d, "llm.jsonl"))]
            trace += fs.read_jsonl(os.path.join(d, "trace.jsonl"))
        rnd = (fs.read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0)
        handled = len(trace)
        span = [c["round_after"] - c["round_before"] for c in calls
                if isinstance(c.get("round_after"), int) and isinstance(c.get("round_before"), int)]
        ms = [c["ms"] for c in calls]
        idle = sum(1 for t in trace if t["state"] == "idle")
        bad = [c for c in calls if c.get("note") != "ok"]   # 含「重問後才成功」的
        thinks, calls_n = len(calls), sum(c.get("calls", 1) for c in calls)
        tok = sum(c.get("tokens", 0) for c in calls)
        stats[who] = {"model": model, "thinks": thinks, "calls": calls_n, "tokens": tok, "llm_s": sum(ms) / 1000, "rounds": rnd,
                      "tocks": handled, "idle": idle, "bad": len(bad), "tasks": len(tids)}
        log("  %-5s %-24s 任務 %d 個  think %d 次＝呼叫 %d 次（不是一次就 ok 的 %d）tokens %d  LLM 共 %.1fs（平均 %.1fs、最長 %.1fs）"
            % (who, model, len(tids), thinks, calls_n, len(bad), tok, sum(ms) / 1000, (sum(ms) / len(ms) / 1000) if ms else 0,
               max(ms) / 1000 if ms else 0))
        if span:
            log("        一次呼叫跨 %d～%d 回合（平均 %.1f）；node 跑了 %d 回合，agent 處理 %d 個 tock（併掉 %d 個，%.0f%%）；"
                "處理的 tock 裡 idle %d（%.0f%%）"
                % (min(span), max(span), sum(span) / len(span), rnd, handled, rnd - handled,
                   100 * (rnd - handled) / max(rnd, 1), idle, 100 * idle / max(handled, 1)))
        for c in bad:
            log("        [%s r%s] %s ｜原文：%s" % (c["tid"], c.get("round_before"), c["note"][:120],
                " ".join(str(c.get("raw")).split())[:160]))
        seg = runs_of(trace)
        log("        狀態段（state 起～迄回合 / 處理 tock 數）：" + " ".join(
            "%s%s-%s/%d" % (s[0], a, b, n) for s, a, b, n in seg[:60]) + (" …" if len(seg) > 60 else ""))

    log("\n== 信件（依時間）==")
    letters = []
    for p in glob.glob(os.path.join(root, "team", "agents", "*", "inbox", "**", "*.json"), recursive=True):
        m = fs.read_json(p, {}) or {}
        letters.append((str(m.get("at")), os.path.relpath(p, root), m))
    for p in glob.glob(os.path.join(root, "team", "agents", "*", "outbox", "**", "*.json"), recursive=True):
        m = fs.read_json(p, {}) or {}
        letters.append((str(m.get("at")), os.path.relpath(p, root), dict(m, undelivered=True)))
    letters.sort()
    t0 = letters[0][0] if letters else None
    for at, rel, m in letters:
        body = " ".join(str(m.get("body")).split())
        state = "（沒寄出：%s）" % rel if m.get("undelivered") else ("" if "/done/" in rel else "（未讀）")
        log("  %s %-6s → %-6s r%-4s %s%s" % (at[11:19], str(m.get("from")).split("/")[-1],
            str(m.get("to")).split("/")[-1], m.get("round"), body[:160] + ("…" if len(body) > 160 else ""), state))

    log("\n== ci 的測試紀錄 ==")
    for c in fs.read_jsonl(os.path.join(root, "team/agents/ci/work/ci-log.jsonl")):
        log("  %s 第 %s 次  來自 %s  %s/%s" % (c["at"][11:19], c["n"], c["from"], c["passed"], c["total"]))

    log("\n== kernel 的決定 ==")
    for p in sorted(glob.glob(os.path.join(root, "team", ".aos", "tasks", "*", "decisions.jsonl"))):
        for d in fs.read_jsonl(p):
            log("  %s team 第%s 回合 %-6s %-8s %s (%s)" % (d.get("at", "")[11:19], d.get("round"), d.get("rule"),
                d.get("op"), d.get("target"), d.get("why")))
    log("\n== daemon 執行過的控制檔 ==")
    for p in sorted(glob.glob(os.path.join(root, ".aosd", "ctl-done", "*.json"))):
        c = fs.read_json(p, {}) or {}
        log("  %-60s ok=%s" % (os.path.basename(p), (c.get("result") or {}).get("ok")))
    log("\n== 任務控制（ctl-done）與加掛回條 ==")
    for p in sorted(glob.glob(os.path.join(root, "**", ".aos", "tasks", "*", "ctl-done.json"), recursive=True)):
        c = fs.read_json(p, {}) or {}
        log("  %s  %s by=%s why=%s ok=%s" % (os.path.relpath(os.path.dirname(p), root), c.get("op"), c.get("by"),
            c.get("why"), (c.get("result") or {}).get("ok")))
    for p in sorted(glob.glob(os.path.join(root, "**", ".aos", "tasks", "*", "mount-done", "*.json"), recursive=True)):
        c = fs.read_json(p, {}) or {}
        log("  加掛 %s ← %s ok=%s" % (os.path.relpath(os.path.dirname(os.path.dirname(p)), root), c.get("path"),
            (c.get("result") or {}).get("ok")))
    au = aos7_audit.scan(root)
    log("\n== 寫入紀錄：%d 個任務、%d 筆寫入，越界 %d 筆 ==" % (au["tasks"], au["writes"], len(au["bad"])))
    for d, r in au["bad"][:10]:
        log("  [越界] %s %s %s" % (os.path.relpath(d, root), r.get("op"), r.get("path")))

    log("\n== 成果 ==")
    res = {}
    for mod in ("dur", "ranges"):
        final = os.path.join(root, "team/agents/lead/work/%s.py" % mod)
        if not os.path.exists(final):
            log("  lead 沒有寫出 work/%s.py" % mod)
            res[mod] = None
            continue
        tmpd = tempfile.mkdtemp(prefix="aos7-real-check-")
        shutil.copy(final, os.path.join(tmpd, mod + ".py"))
        p = subprocess.run([sys.executable, "-B", "check_%s.py" % mod, tmpd], cwd=os.path.join(root, "team/agents/ci"),
                           capture_output=True, text=True, timeout=20)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            r = {"passed": 0, "total": None, "fails": [p.stdout[-300:] + p.stderr[-300:]]}
        shutil.rmtree(tmpd, ignore_errors=True)
        res[mod] = r
        log("  lead/work/%s.py 跑隱藏測試：%s/%s %s" % (mod, r["passed"], r["total"], "; ".join(r["fails"][:5])))
        with open(final, encoding="utf-8") as f:
            log("  --- %s.py ---\n" % mod + "".join("  | " + x for x in f.readlines()[:70]))
    dm = os.path.join(root, "team/agents/lead/work/DONE.md")
    if os.path.exists(dm):
        with open(dm, encoding="utf-8") as f:
            log("  --- DONE.md ---\n  " + f.read().strip().replace("\n", "\n  "))
    return stats, res


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", help="空間根（預設開暫存資料夾）；會先清空")
    ap.add_argument("--max-calls", type=int, default=400, help="整場 LLM 呼叫上限（預設 400）")
    ap.add_argument("--max-seconds", type=float, default=900)
    ap.add_argument("--join-after", type=float, default=60, help="最晚第幾秒加入 rita")
    ap.add_argument("--grace", type=float, default=8, help="DONE.md 出現後再跑幾秒")
    ap.add_argument("--idle-stop", type=float, default=150, help="沒有新呼叫、沒有新信超過幾秒就停")
    ap.add_argument("--log", help="摘要另存到這個檔")
    a = ap.parse_args()
    root = os.path.abspath(a.root) if a.root else tempfile.mkdtemp(prefix="aos7-real-")
    if a.root and os.path.exists(root):
        shutil.rmtree(root)
    shutil.copytree(os.path.join(HERE, "real_scene"), root, dirs_exist_ok=True)
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)
    log("空間根：%s  上限：%d 次呼叫、%d 秒" % (root, a.max_calls, a.max_seconds))
    left, why, secs, samples = run(root, a, log)
    calls, tokens = llm_calls(root)
    log("\n停：%s；跑了 %.0f 秒；LLM 呼叫 %d 次、tokens %d" % (why, secs, calls, tokens))
    stats, res = report(root, log, secs, samples)
    log("\n殘留程序：%s" % (left or "無"))
    fs.write_json(os.path.join(root, "real-summary.json"),
                  {"why": why, "seconds": round(secs, 1), "calls": calls, "tokens": tokens, "agents": stats,
                   "final": res, "left": left, "samples": samples})
    if a.log:
        with open(a.log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 0 if all(r and not r["fails"] for r in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
