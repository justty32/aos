"""量每一跳（2026-09-24 tick-gap，P2 隊）：環境變數 AOS_HOPS 設成一個檔的絕對路徑，各程式就往裡面追加時間戳。

沒設＝什麼都不做（一次 dict 查詢）。設了：daemon 開格、kernel 一格的起訖／讀到的單／放出去的工作／收到的回音／叫醒、
cpu 撿到一件／做完一件、agent 一格的起訖與送出的工作、aos-llm call 的起訖與 HTTP 起訖、投輸入的 wake，各記一行 JSON。
每行一次 `write`（O_APPEND），多支程式同時寫不會交錯。寫不進去就算了，絕不擋路。

`boot` 是這支行程被 fork／exec 的時間（Linux 讀 /proc；別的系統沒有＝null），拿來量「起一支 Python 花多久」。

分析：`python3 lib/aos_hops.py report HOPS檔 [--agent 名字] [--json]`——把一個 agent 相關的事件照時間排好，
相鄰兩件之間的時間記到「這一跳」名下（整段牆上時間剛好被切成一跳一跳，加起來等於從頭到尾）。
"""
import json
import os
import sys
import time

ENV = "AOS_HOPS"
_BOOT = []


def _boot_time():
    """這支行程開始的 epoch 秒：/proc/self/stat 第 22 欄（開機後幾個 clock tick）換成 epoch；拿不到回 None。
    換算用「現在的 epoch − 現在的 CLOCK_BOOTTIME」，不用 /proc/stat 的 btime（它只到整秒）。"""
    if _BOOT:
        return _BOOT[0]
    value = None
    try:
        with open("/proc/self/stat", "rb") as f:
            stat = f.read().decode()
        start_ticks = int(stat.rsplit(")", 1)[1].split()[19])
        booted = time.time() - time.clock_gettime(time.CLOCK_BOOTTIME)
        value = booted + start_ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, AttributeError):
        value = None
    _BOOT.append(value)
    return value


def on():
    return bool(os.environ.get(ENV))


def mark(who, ev, boot=False, **fields):
    """追加一行 {t, pid, who, ev, ...}；AOS_HOPS 沒設就立刻回。"""
    path = os.environ.get(ENV)
    if not path:
        return
    record = {"t": time.time(), "pid": os.getpid(), "who": who, "ev": ev}
    if boot:
        record["boot"] = _boot_time()
    record.update(fields)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o644)
        try:
            os.write(fd, (json.dumps(record, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass


# ---------------------------------------------------------------- 分析

A_BOOT, A_BEGIN, A_SEND, A_END = "agent 的 Python 起來", "agent 一格開始", "agent 送單", "agent 一格結束"
K_READ, K_RESP_JOB, K_RESP_AGENT = "kernel 開格（讀到單）", "kernel 開格（收工作回音）", "kernel 開格（收 agent 回音"
K_JOB, K_AGENT, K_REPLY = "kernel 放工作", "kernel 派 agent", "kernel 放回音＋叫醒"
C_PICK_A, C_DONE_A, C_PICK_J, C_DONE_J = "cpu 撿到 agent", "cpu 做完 agent", "cpu 撿到工作", "cpu 做完工作"
L_BOOT, L_HTTP0, L_HTTP1, L_END = "aos-llm 的 Python 起來", "模型 HTTP 開始", "模型 HTTP 結束", "aos-llm 結束"
W_SENT = "有人投輸入＋wake"
IDLE = "閒著（沒人說話，不算進牆上時間）"

# 相鄰兩件（前 → 後）→ 這一跳叫什麼。沒列到的照「前 → 後」原樣印（多半是 agent 與工作重疊的那一小段）。
HOP_NAMES = {
    (K_AGENT, C_PICK_A): "① 派 agent → cpu 撿到（cpu 輪詢 poll_ms）",
    (C_PICK_A, A_BEGIN): "② cpu 撿到 → agent 起 Python（fork＋import）",
    (A_BEGIN, A_SEND): "④ agent 一格：讀家、收回音、結清、建批",
    (A_BEGIN, A_END): "④ agent 一格（沒送單：收回音結清、或停車）",
    (A_SEND, A_END): "④ agent 一格：送單後收尾",
    (A_SEND, K_READ): "⑤ 送單 → kernel 開格（daemon 察覺新檔＋起 kernel）",
    (A_END, K_READ): "⑤ 送單 → kernel 開格（daemon 察覺新檔＋起 kernel）",
    (W_SENT, K_READ): "⑤ 投輸入＋wake → kernel 開格",
    (K_READ, K_JOB): "⑥ kernel 一格：讀單到放工作",
    (K_READ, K_AGENT): "⑥ kernel 一格：讀 wake 到派 agent",
    (K_JOB, C_PICK_J): "⑦ 放工作 → cpu 撿到（cpu 輪詢 poll_ms）",
    (C_PICK_J, L_HTTP0): "⑧ cpu 撿到 → aos-llm 起 Python、讀設定、組好請求",
    (L_HTTP0, L_HTTP1): "⑩ 等模型（HTTP）",
    (L_HTTP1, L_END): "⑪ aos-llm 收尾",
    (L_END, C_DONE_J): "⑫ 工作結束 → cpu 發現（cpu 等子行程的輪詢）",
    (C_DONE_A, K_RESP_JOB): "⑬ cpu 回音 → kernel 開格（daemon 察覺通知＋起 kernel）",
    (K_RESP_JOB, K_AGENT): "⑭ kernel 一格：收回音到派 agent",
    (C_PICK_J, C_DONE_J): "⑩ 工具（含起行程）",
    (C_DONE_J, K_RESP_JOB): "⑬ cpu 回音 → kernel 開格（daemon 察覺通知＋起 kernel）",
    (K_RESP_JOB, K_REPLY): "⑭ kernel 一格：收回音到放回音",
    (K_REPLY, K_AGENT): "⑮ 放回音＋叫醒 → 派 agent（叫醒在出貨時，派工要等下一格）",
    (A_END, C_DONE_A): "⑯ agent 退出 → cpu 發現（cpu 等子行程的輪詢）",
    (C_DONE_A, K_RESP_AGENT + "，退 0）"): "⑰ cpu 回音 → kernel 開格（daemon 察覺通知＋起 kernel）",
    (C_DONE_A, K_RESP_AGENT + "，退 101）"): "⑰ cpu 回音 → kernel 開格（daemon 察覺通知＋起 kernel）",
    (C_DONE_A, K_RESP_AGENT + "，退 102）"): "⑰ cpu 回音 → kernel 開格（daemon 察覺通知＋起 kernel）",
    (K_RESP_AGENT + "，退 0）", K_AGENT): "⑱ agent 退 0（做了事）→ 等 interval_ms 才再派",
    (K_RESP_AGENT + "，退 101）", K_AGENT): "⑱ agent 退 101 → 等 interval_ms 才再派",
    (K_RESP_AGENT + "，退 102）", K_AGENT): "⑱ agent 退 102、跑時已被叫醒 → 再派（改前照 101 等 interval_ms）",
    (K_RESP_AGENT + "，退 103）", K_AGENT): "⑱ agent 退 103 → 馬上再派",
}


class _Ev:
    __slots__ = ("t", "kind", "raw")

    def __init__(self, t, kind, raw):
        self.t, self.kind, self.raw = t, kind, raw


def load(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and isinstance(rec.get("t"), (int, float)):
                out.append(rec)
    out.sort(key=lambda r: r["t"])
    return out


def agent_names(records):
    return sorted({r["agent"] for r in records if r.get("who") == "agent" and isinstance(r.get("agent"), str)})


def timeline(records, agent):
    """一個 agent 相關的事件（照時間）。agent＝家的資料夾名；kernel 裡的行程名是 agent-<名>，它的工作是 aw-<名>-…。"""
    proc = "agent-" + agent
    prefix = "aw-%s-" % agent
    reqs = {}                    # cpu 上的 request 檔名 → "agent"／"job"
    ktick = {}                   # kernel pid → 那格的 begin 時間
    evs = []

    def mine(name):
        return isinstance(name, str) and (name == proc or name.startswith(prefix))

    for r in records:
        who, ev = r.get("who"), r.get("ev")
        if who == "agent" and r.get("agent") == agent:
            if ev == "begin":
                if r.get("boot"):
                    evs.append(_Ev(r["boot"], A_BOOT, r))
                evs.append(_Ev(r["t"], A_BEGIN, r))
            elif ev == "send":
                evs.append(_Ev(r["t"], A_SEND, r))
            elif ev == "end":
                evs.append(_Ev(r["t"], A_END, r))
        elif who == "wake" and r.get("agent") == agent:
            evs.append(_Ev(r["t"], W_SENT, r))
        elif who == "kernel":
            if ev == "begin":
                ktick[r["pid"]] = r["t"]
            elif ev == "req" and r.get("method") in ("add", "wake") and (mine(r.get("proc")) or r.get("wake") == proc):
                evs.append(_Ev(ktick.get(r["pid"], r["t"]), K_READ, r))
            elif ev == "dispatch" and mine(r.get("proc")):
                own = r.get("proc") == proc
                reqs[r.get("request")] = "agent" if own else "job"
                evs.append(_Ev(r["t"], K_AGENT if own else K_JOB, r))
            elif ev == "resp" and mine(r.get("proc")):
                kind = (K_RESP_AGENT + "，退 %s）" % r.get("code")) if r.get("proc") == proc else K_RESP_JOB
                evs.append(_Ev(ktick.get(r["pid"], r["t"]), kind, r))
            elif ev == "reply" and r.get("wake") == proc:
                evs.append(_Ev(r["t"], K_REPLY, r))
        elif who == "cpu" and r.get("request") in reqs:
            own = reqs[r["request"]] == "agent"
            if ev == "pick":
                evs.append(_Ev(r["t"], C_PICK_A if own else C_PICK_J, r))
            elif ev == "done":
                evs.append(_Ev(r["t"], C_DONE_A if own else C_DONE_J, r))
        elif who == "llm" and (r.get("batch") or "").startswith(prefix):
            if ev == "begin" and r.get("boot"):
                evs.append(_Ev(r["boot"], L_BOOT, r))
            elif ev == "http_start":
                evs.append(_Ev(r["t"], L_HTTP0, r))
            elif ev == "http_end":
                evs.append(_Ev(r["t"], L_HTTP1, r))
            elif ev == "end":
                evs.append(_Ev(r["t"], L_END, r))
    evs.sort(key=lambda e: e.t)
    return evs


def _dedupe(evs):
    """同一種、同一個時間點（kernel 同一格讀到好幾張單）只留一件。"""
    out = []
    for e in evs:
        if out and out[-1].kind == e.kind and abs(out[-1].t - e.t) < 1e-6:
            continue
        out.append(e)
    return out


MODEL, TOOL, TICK = "⑩ 等模型（HTTP）", "⑩ 跑工具（cpu 撿到到做完）", "④ agent 一格（Python 裡做事）"


def _intervals(evs):
    """哪幾段時間是「真的在做事」：模型 HTTP、工具工作（不是問模型的那種）、agent 一格。回 [(起, 迄, 名字)]。"""
    llm = {e.raw.get("batch") for e in evs if e.kind in (L_HTTP0, L_HTTP1, L_END)}
    req_proc = {e.raw.get("request"): e.raw.get("proc") for e in evs if e.kind == K_JOB}
    out, open_ = [], {}
    for e in evs:
        if e.kind == L_HTTP0:
            open_[("http", e.raw.get("batch"))] = e.t
        elif e.kind == L_HTTP1 and ("http", e.raw.get("batch")) in open_:
            out.append((open_.pop(("http", e.raw.get("batch"))), e.t, MODEL))
        elif e.kind in (C_PICK_J, C_DONE_J):
            proc = req_proc.get(e.raw.get("request")) or ""
            if proc.rsplit("-", 1)[0] in llm:
                continue
            if e.kind == C_PICK_J:
                open_[("tool", e.raw.get("request"))] = e.t
            elif ("tool", e.raw.get("request")) in open_:
                out.append((open_.pop(("tool", e.raw.get("request"))), e.t, TOOL))
        elif e.kind == A_BEGIN:
            open_["tick"] = e.t
        elif e.kind == A_END and "tick" in open_:
            out.append((open_.pop("tick"), e.t, TICK))
    return out


def hops(evs):
    """把一個 agent 的牆上時間切成一跳一跳：({名字: [毫秒, …]}, 牆上毫秒)。

    相鄰兩件事件之間是一段。這段落在「真的在做事」裡（等模型 > 跑工具 > agent 一格，照這個優先）就算那一項；
    否則就是排程的一跳，照（前一件, 後一件）命名。接到「有人投輸入」之前那段是閒著，另記、不算進牆上時間。"""
    evs = [e for e in _dedupe(evs) if e.kind not in (A_BOOT, L_BOOT)]
    busy = _intervals(evs)
    rank = {MODEL: 0, TOOL: 1, TICK: 2}
    table, wall = {}, 0.0
    for a, b in zip(evs, evs[1:]):
        ms = (b.t - a.t) * 1000
        if b.kind == W_SENT:
            table.setdefault(IDLE, []).append(ms)
            continue
        inside = [name for lo, hi, name in busy if lo <= a.t and b.t <= hi and hi > lo]
        if inside:
            name = min(inside, key=rank.get)
        else:
            name = HOP_NAMES.get((a.kind, b.kind)) or "%s → %s" % (a.kind, b.kind)
        wall += ms
        table.setdefault(name, []).append(ms)
    return table, wall


def summarize(table, wall):
    rows = []
    for name, ms in table.items():
        ms = sorted(ms)
        rows.append({"hop": name, "n": len(ms), "total_ms": round(sum(ms)), "mean_ms": round(sum(ms) / len(ms), 1),
                     "p50_ms": round(ms[len(ms) // 2], 1), "max_ms": round(ms[-1], 1)})
    rows.sort(key=lambda r: (r["hop"] == IDLE, -r["total_ms"]))
    return {"wall_ms": round(wall), "hops": rows}


def render(agent, summary):
    lines = ["agent %s：從第一件到最後一件 %.1f 秒" % (agent, summary["wall_ms"] / 1000),
             "%-58s %5s %9s %8s %8s %8s" % ("這一跳", "次", "合計ms", "平均", "中位", "最久")]
    for r in summary["hops"]:
        lines.append("%-58s %5d %9d %8.1f %8.1f %8.1f" % (r["hop"][:58], r["n"], r["total_ms"], r["mean_ms"],
                                                          r["p50_ms"], r["max_ms"]))
    return "\n".join(lines)


def report(path, agent=None, as_json=False):
    records = load(path)
    names = [agent] if agent else agent_names(records)
    out = {}
    for name in names:
        evs = timeline(records, name)
        if agent is None and not any(e.kind == A_SEND for e in evs):
            continue                      # 沒送過單的 agent（團隊裡閒著的成員）不列
        table, wall = hops(evs)
        out[name] = summarize(table, wall)
    if as_json:
        return json.dumps(out, ensure_ascii=False, indent=1)
    return "\n\n".join(render(n, s) for n, s in out.items())


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] != "report":
        sys.stderr.write("用法：aos_hops.py report HOPS檔 [--agent 名字] [--json]\n")
        return 2
    path, agent, as_json = args[1], None, "--json" in args
    if "--agent" in args:
        agent = args[args.index("--agent") + 1]
    print(report(path, agent, as_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
