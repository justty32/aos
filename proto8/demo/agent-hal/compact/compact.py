# compact.py - 土法 compact：$AOS_STACK/history.jsonl 太大時，壓成一份短的 history（形狀照舊，agent-dan 的 brain 直接能用）。
#   第 1 步 note：每次叫工具（assistant 的 tool_calls＋對應的 tool 結果）交給便宜模型，一個呼叫一句「在幹嘛，結果如何」。
#   第 2 步 segment：第 1 步後的紀錄每 COMPACT_SEG_KB 切一段，各段產總結，並挑幾行原樣保留（keep，打標記＋理由）。
#   第 3 步 final：各段總結＋候選保留行串起來，交給較強的模型修飾成一份摘要、選最後要留的 keep。
# 最近 COMPACT_KEEP_TURNS 題與還沒答完的那題原樣不動；更早的換成一則 user（摘要＋保留原文）＋一則 assistant（讀過了）。
# 原始 history 不刪不改：整份輪替到 $AOS_STACK/compact/<run>/orig.jsonl（像 log 輪替），新的另寫一份換上去。
# 每步的產物都落在 $AOS_STACK/compact/run/（做到一半失敗，重跑從斷的那步接著做）；做完改名成 <run>，報告 report.json、log.jsonl。
# 用法：aos-exec compact [--force]（--force＝不看門檻；在 fsm 裡當一格就不帶，沒超過門檻直接退 0）。
import datetime, fcntl, hashlib, json, os, sys, time
import ask
from ask import die, flat

KEEP_TAGS = ("user_words", "decision", "number", "open", "other")
MARK = "【compact】"
ACK = "好，我已讀過先前對話的摘要與保留的原文，接著往下。"


def env_int(name, default):
    v = os.environ.get(name)
    if v in (None, ""):
        return default
    try:
        n = int(v)
    except ValueError:
        die("SettingBad", "%s 不是整數：%r" % (name, v))
    if n < 0:
        die("SettingBad", "%s 不能是負的：%r" % (name, v))
    return n


OVER_KB = env_int("COMPACT_OVER_KB", 32)            # history 超過幾 KB 才壓
SEG_KB = max(1, env_int("COMPACT_SEG_KB", 8))        # 第 2 步每段幾 KB
KEEP_TURNS = env_int("COMPACT_KEEP_TURNS", 2)        # 最近幾題原樣不動（還沒答完的那題一定不動）
KEEP_MAX = env_int("COMPACT_KEEP_MAX", 3)            # 第 2 步每段最多保留幾行
KEEP_FINAL_MAX = env_int("COMPACT_KEEP_FINAL_MAX", 12)   # 第 3 步最後最多留幾行
KEEP_LINE_MAX = env_int("COMPACT_KEEP_LINE_MAX", 1500)   # 一行保留行最多幾字，超過不收（記在報告的 dropped）
RESULT_CUT = env_int("COMPACT_RESULT_CUT", 2000)     # 給第 1 步看的工具結果最多幾字（頭 3/4＋尾 1/4）
MODEL_NOTE = os.environ.get("COMPACT_MODEL_NOTE") or "chatgpt-gpt-6-luna-low"
MODEL_SEG = os.environ.get("COMPACT_MODEL_SEG") or "chatgpt-gpt-6-luna-low"
MODEL_FINAL = os.environ.get("COMPACT_MODEL_FINAL") or "chatgpt-gpt-6-sol"

stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
args = sys.argv[1:]
if any(a != "--force" for a in args):
    die("ArgumentsBad", "只認得 --force：%s" % " ".join(args))
force = "--force" in args
HIST = os.path.join(stack, "history.jsonl")
CDIR = os.path.join(stack, "compact")
RUN = os.path.join(CDIR, "run")
HERE = os.path.dirname(os.path.abspath(__file__))


def prompt(name, max_keep=0):
    with open(os.path.join(HERE, "prompts", name + ".txt"), encoding="utf-8") as f:
        return f.read().replace("{max_keep}", str(max_keep))


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, value):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05：先寫 . 開頭的暫存檔再改名
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def text(m):
    c = m.get("content")
    return c if isinstance(c, str) else ("" if c is None else json.dumps(c, ensure_ascii=False))


def cut_middle(s, n):
    if s is None or len(s) <= n:
        return s
    head = n * 3 // 4
    return s[:head] + "\n…（中間截掉 %d 字）…\n" % (len(s) - n) + s[-(n - head):]


def now_id():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


# ---- 讀 history、切出要壓的那段 ----

def load():
    """回 [(行號, 原始那行, message)]；有一行不是 JSON 物件＝HistoryBad。"""
    out = []
    with open(HIST, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                m = json.loads(line)
            except ValueError as e:
                die("HistoryBad", "history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
            if not isinstance(m, dict):
                die("HistoryBad", "history.jsonl 第 %d 行不是物件" % n)
            out.append((n, line.rstrip("\n"), m))
    return out


def split_point(rows):
    """要壓的是 rows[:cut]。一題＝從 user 起、到一則沒有 tool_calls 的 assistant 止；最近 KEEP_TURNS 題與沒答完的那題不壓。"""
    done, start = [], None
    for i, (_, _, m) in enumerate(rows):
        role = m.get("role")
        if role == "user" and start is None:
            start = i
        elif role == "assistant" and not m.get("tool_calls") and start is not None:
            done.append(start)
            start = None
    if KEEP_TURNS:
        return done[-KEEP_TURNS] if len(done) > KEEP_TURNS else 0
    return start if start is not None else len(rows)


def old_compact(rows):
    """開頭是上一次 compact 留下的那一對（user 以 MARK 開頭＋assistant）就回 (run 名, 那則 user 的內容)。"""
    if len(rows) >= 2 and rows[0][2].get("role") == "user" and text(rows[0][2]).startswith(MARK) \
            and rows[1][2].get("role") == "assistant":
        head = text(rows[0][2]).split("\n", 1)[0]
        words = head[len(MARK):].split()
        run = words[0].replace("run=", "") if words else ""
        if not run or not all(ch.isdigit() or ch in "-x" for ch in run):
            run = ""                            # 認不出是哪一次（被手改過）：只拿那則的全文當舊摘要
        return run, text(rows[0][2])
    return None


# ---- 第 1 步：工具呼叫各一句 ----

def stage_note(body, report):
    """回第 1 步後的行：一般訊息原樣（加 _n）；每個工具呼叫換成一行 tool_note（_n＝[叫的那行, 結果那行]）。"""
    cache_path = os.path.join(RUN, "notes.json")
    cache = read_json(cache_path, {})
    results = {}
    for n, _, m in body:
        if m.get("role") == "tool" and m.get("tool_call_id") is not None:
            results.setdefault(m["tool_call_id"], (n, m))
    called, lines, last_user = set(), [], ""
    st = report["stages"]["note"]
    for n, _, m in body:
        role = m.get("role")
        if role == "tool":
            if m.get("tool_call_id") in called:
                continue                      # 已經跟著它的呼叫縮成一句
            lines.append({"_n": [None, n], "role": "tool_note", "tool_call_id": m.get("tool_call_id"),
                          "name": "?", "ok": None, "content": "（找不到是誰叫的）工具回：" + flat(text(m), 80)})
            continue
        calls = [c for c in (m.get("tool_calls") or []) if isinstance(c, dict)] if role == "assistant" else []
        if not calls:
            if role == "user":
                last_user = text(m)
            lines.append(dict(m, _n=n))
            continue
        if text(m).strip():                   # 叫工具時順便說的話，留成一行
            lines.append({"_n": n, "role": "assistant", "content": text(m)})
        items = []
        for c in calls:
            fn = c.get("function") if isinstance(c.get("function"), dict) else {}
            cid = c.get("id")
            res = results.get(cid)
            items.append({"id": cid, "name": fn.get("name") or "?", "arguments": fn.get("arguments"),
                          "result": cut_middle(text(res[1]), RESULT_CUT) if res else None,
                          "n_result": res[0] if res else None})
            called.add(cid)
        key = str(n)
        if key not in cache:
            data = {"calls": items}
            user = "使用者在問：%s\nagent 說：%s\n\n" % (flat(last_user, 300), flat(text(m), 300) or "（沒說話）")
            user += "\n\n".join("呼叫 id=%s\n工具：%s\n參數：%s\n結果：%s" % (
                it["id"], it["name"], flat(it["arguments"] if isinstance(it["arguments"], str)
                                           else json.dumps(it["arguments"], ensure_ascii=False), 1000),
                it["result"] if it["result"] is not None else "（沒有結果：中途停了）") for it in items)
            content, usage = ask.ask(MODEL_NOTE, prompt("note"), user, data, ask.fake_note)
            count(st, usage)
            got = ask.parse_json(content)
            notes = {}
            if got and isinstance(got.get("notes"), list):
                notes = {x.get("id"): x for x in got["notes"] if isinstance(x, dict) and isinstance(x.get("line"), str)}
            fell = [it["id"] for it in items if it["id"] not in notes]
            st["counter_fallbacks"] += len(fell)
            cache[key] = {}
            for it in items:
                x = notes.get(it["id"])
                if x:
                    ok = x.get("ok") if isinstance(x.get("ok"), bool) else None
                    line = flat(x["line"], 200)
                else:                          # 退路：模型沒給這個 id（或回的不是 JSON）就照字面拼
                    ok = None if it["result"] is not None else False
                    line = json.loads(ask.fake_note({"calls": [it]}))["notes"][0]["line"]
                if it["result"] is None:
                    ok = False
                cache[key][str(it["id"])] = {"ok": ok, "line": line}
            write_json(cache_path, cache)
        for it in items:
            x = cache[key].get(str(it["id"])) or {"ok": None, "line": "?"}
            lines.append({"_n": [n, it["n_result"]], "role": "tool_note", "tool_call_id": it["id"],
                          "name": it["name"], "ok": x["ok"], "content": x["line"]})
    return lines


def count(st, usage):
    st["counter_calls"] += 1
    st["prompt_tokens"] += usage["prompt_tokens"]
    st["completion_tokens"] += usage["completion_tokens"]
    st["estimated"] = st["estimated"] or usage["estimated"]


# ---- 第 2 步：逐段總結＋挑保留行 ----

def first_n(line):
    n = line["_n"]
    return n if isinstance(n, int) else (n[0] if n[0] is not None else n[1])


def keep_text(line):
    """保留行的原文：第 1 步後的那行（一般訊息＝原樣；工具呼叫＝那一句），去掉 _n。"""
    return json.dumps({k: v for k, v in line.items() if k != "_n"}, ensure_ascii=False)


def size(line):
    return len(keep_text(line).encode("utf-8"))


def segments(lines):
    """每段約 SEG_KB；同一則 assistant 叫的幾個工具不拆開；超過時盡量切在一則 user 前（前半至少半段）。"""
    blocks = []
    for ln in lines:
        k = ln["_n"][0] if ln["role"] == "tool_note" and isinstance(ln["_n"], list) else None
        if blocks and k is not None and blocks[-1]["key"] == k:
            blocks[-1]["lines"].append(ln)
        elif blocks and k is not None and ln["role"] == "tool_note" and blocks[-1]["key"] is None \
                and blocks[-1]["lines"][-1]["role"] == "assistant" and blocks[-1]["lines"][-1]["_n"] == k:
            blocks[-1]["lines"].append(ln)   # 叫工具時說的話跟它的工具算一塊
            blocks[-1]["key"] = k
        else:
            blocks.append({"key": k, "lines": [ln]})
    limit = SEG_KB * 1024
    segs, cur = [], []
    bsize = lambda b: sum(size(x) for x in b["lines"])
    for b in blocks:
        if cur and sum(map(bsize, cur)) + bsize(b) > limit:
            at = len(cur)
            for i in range(len(cur) - 1, 0, -1):
                if cur[i]["lines"][0]["role"] == "user" and sum(map(bsize, cur[:i])) >= limit // 2:
                    at = i
                    break
            segs.append(cur[:at])
            cur = cur[at:]
        cur.append(b)
    if cur:
        segs.append(cur)
    return [[ln for b in s for ln in b["lines"]] for s in segs]


def render(ln, cut):
    if ln["role"] == "tool_note":
        ok = {True: "成功", False: "失敗", None: "不確定"}[ln["ok"]]
        return "L%d 工具 %s（%s，id=%s）：%s" % (first_n(ln), ln["name"], ok, ln["tool_call_id"], ln["content"])
    return "L%d %s：%s" % (first_n(ln), ln.get("role"), cut_middle(text(ln), cut))


def stage_segment(lines, report):
    st = report["stages"]["segment"]
    segs = segments(lines)
    st["counter_segments"] = len(segs)
    out = []
    os.makedirs(os.path.join(RUN, "seg"), exist_ok=True)
    for i, seg in enumerate(segs, 1):
        path = os.path.join(RUN, "seg", "%04d.json" % i)
        nums = [first_n(ln) for ln in seg]
        got = read_json(path)
        if got is None or got.get("lines") != nums:
            by_n = {first_n(ln): ln for ln in seg}
            data = {"max_keep": KEEP_MAX, "lines": [{"n": first_n(ln), "role": ln["role"], "text": text(ln)}
                                                     for ln in seg]}
            user = "\n".join(render(ln, SEG_KB * 1024) for ln in seg)
            content, usage = ask.ask(MODEL_SEG, prompt("segment", KEEP_MAX), user, data, ask.fake_segment)
            count(st, usage)
            reply = ask.parse_json(content)
            fallback = not (reply and isinstance(reply.get("summary"), str))
            summary = content.strip() if fallback else reply["summary"].strip()
            st["counter_fallbacks"] += fallback
            if not summary:                    # 空的摘要換上去＝這段整個不見：寧可停下（重跑會再問這段）
                die("SummaryEmpty", "第 %d 段（L%d～L%d）的摘要是空的" % (i, nums[0], nums[-1]))
            keeps, dropped = [], []
            ks = (reply or {}).get("keep")
            for k in (ks if isinstance(ks, list) and not fallback else []):
                n = k.get("n") if isinstance(k, dict) else k
                if isinstance(n, str) and n.lstrip("L").isdigit():
                    n = int(n.lstrip("L"))
                if n not in by_n:
                    dropped.append({"n": n, "why": "不在這段"})
                    continue
                if any(x["id"] == "L%d" % n for x in keeps):
                    continue
                if len(keeps) >= KEEP_MAX:
                    dropped.append({"n": n, "why": "超過每段上限 %d" % KEEP_MAX})
                    continue
                t = keep_text(by_n[n])
                if len(t) > KEEP_LINE_MAX:
                    dropped.append({"n": n, "why": "太長（%d 字 > %d）" % (len(t), KEEP_LINE_MAX)})
                    continue
                tag = k.get("tag") if isinstance(k, dict) and k.get("tag") in KEEP_TAGS else "other"
                why = flat(k.get("why"), 80) if isinstance(k, dict) and isinstance(k.get("why"), str) else ""
                keeps.append({"id": "L%d" % n, "tag": tag, "why": why, "text": t})
            got = {"lines": nums, "summary": summary, "keep": keeps, "dropped": dropped, "fallback": fallback}
            write_json(path, got)
        out.append(got)
    return out


# ---- 第 3 步：最後修飾 ----

def keep_entry(k):
    return "[%s %s：%s] %s" % (k["id"], k["tag"], k["why"] or "—", k["text"])


def summary_of(content, reply, fallback):
    return (content if fallback else reply["summary"]).strip()


def stage_final(segs, old, report):
    path = os.path.join(RUN, "final.json")
    got = read_json(path)
    if got is not None:
        return got
    st = report["stages"]["final"]
    old_final = read_json(os.path.join(CDIR, old[0], "final.json")) if old and old[0] else None
    old_summary = (old_final or {}).get("summary") or (old[1] if old else "")
    cands = [dict(k, id="old:" + k["id"].split(":")[-1]) for k in (old_final or {}).get("keep", [])]
    for s in segs:
        cands += s["keep"]
    user = ""
    if old:
        user += "## 更早一次壓縮留下的摘要\n%s\n\n" % old_summary
    user += "## 這次各段的摘要（照時間順序）\n"
    for i, s in enumerate(segs, 1):
        user += "### 第 %d 段（L%d～L%d）\n%s\n\n" % (i, s["lines"][0], s["lines"][-1], s["summary"])
    user += "## 候選保留行\n" + ("\n".join(keep_entry(k) for k in cands) or "（沒有）")
    data = {"old_summary": old_summary if old else "", "segments": [s["summary"] for s in segs],
            "candidates": [k["id"] for k in cands], "max_keep": KEEP_FINAL_MAX}
    content, usage = ask.ask(MODEL_FINAL, prompt("final", KEEP_FINAL_MAX), user, data, ask.fake_final)
    count(st, usage)
    reply = ask.parse_json(content)
    fallback = not (reply and isinstance(reply.get("summary"), str))
    st["counter_fallbacks"] += fallback
    if not summary_of(content, reply, fallback):
        die("SummaryEmpty", "第 3 步的摘要是空的")
    by_id = {k["id"]: k for k in cands}
    if fallback:
        summary, ids = content.strip(), [k["id"] for k in cands]
    else:
        summary = reply["summary"].strip()
        ids = [x for x in (reply.get("keep") or []) if isinstance(x, str)]
    keep, seen = [], set()
    for x in ids:
        if x in by_id and x not in seen and len(keep) < KEEP_FINAL_MAX:
            keep.append(by_id[x])
            seen.add(x)
    got = {"summary": summary, "keep": keep, "counter_candidates": len(cands), "fallback": fallback}
    write_json(path, got)
    return got


# ---- 主流程 ----

def main():
    if not os.path.isfile(HIST):
        return 0
    before = os.path.getsize(HIST)
    if not force and before <= OVER_KB * 1024 and not os.path.isdir(RUN):
        return 0
    os.makedirs(CDIR, exist_ok=True)
    lock = open(os.path.join(CDIR, ".lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)           # 同一個 stack 一次只壓一個（手動跑與 fsm 格撞到時，後到的等）
    t0 = time.time()
    src = read_json(os.path.join(RUN, "source.json"))
    if src and os.path.isfile(HIST) and src.get("new_sha") == sha(HIST):
        return finish(src)                     # 上次已換上新的 history、只差收尾
    if src and src.get("sha") != sha(HIST):    # history 在中斷後又變了：舊的半成品留著不用（不刪）
        os.replace(RUN, os.path.join(CDIR, "stale-" + now_id()))
        src = None
    if not src and not force:
        if before <= OVER_KB * 1024:
            return 0
        if last_log().get("nosave") == sha(HIST):
            return 0                           # 這份 history 上次壓了沒變小：同一份不再花錢壓（多接幾行才再試）
    rows = load()
    cut = split_point(rows)
    prefix, tail = rows[:cut], rows[cut:]
    old = old_compact(prefix)
    body = prefix[2:] if old else prefix
    if not body:
        log({"skip": "沒有可以壓的（全是最近 %d 題、還沒答完的那題、或上次的摘要）" % KEEP_TURNS,
             "bytes": before, "time": now_id()})
        return 0
    os.makedirs(RUN, exist_ok=True)
    if not src:
        src = {"sha": sha(HIST), "bytes": before, "cut": cut, "started": now_id()}
        write_json(os.path.join(RUN, "source.json"), src)
    report = read_json(os.path.join(RUN, "report.json")) or {
        "stages": {s: {"counter_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "estimated": False, "counter_fallbacks": 0}
                   for s in ("note", "segment", "final")}}
    report["stages"]["segment"].setdefault("counter_segments", 0)
    try:
        lines = stage_note(body, report)
        write_jsonl(os.path.join(RUN, "stage1.jsonl"), lines)
        segs = stage_segment(lines, report)
        final = stage_final(segs, old, report)
    finally:
        write_json(os.path.join(RUN, "report.json"), report)    # 失敗也記下花了多少（重跑接著累加）
    run_id = src["started"]
    while os.path.exists(os.path.join(CDIR, run_id)):
        run_id += "x"
    rnd = ((read_json(os.path.join(CDIR, old[0], "report.json")) or {}).get("round", 1) + 1) if old and old[0] else 1
    head = "%srun=%s 第 %d 次壓縮。以下是先前對話（原本 %d 則訊息、%.1f KB）的摘要與原樣保留的幾則；" \
           "原始紀錄在 $AOS_STACK/compact/%s/orig.jsonl。" % (MARK, run_id, rnd, len(prefix),
                                                         sum(len(r[1].encode()) + 1 for r in prefix) / 1024, run_id)
    content = head + "\n\n## 摘要\n" + final["summary"]
    if final["keep"]:
        content += "\n\n## 原樣保留的訊息（keep）\n" + "\n".join("- " + keep_entry(k) for k in final["keep"])
    new_lines = [json.dumps({"role": "user", "content": content}, ensure_ascii=False),
                 json.dumps({"role": "assistant", "content": ACK}, ensure_ascii=False)] + [r[1] for r in tail]
    new_path = os.path.join(RUN, "history.new.jsonl")
    with open(new_path, "w", encoding="utf-8") as f:
        f.write("".join(x + "\n" for x in new_lines))
    report.update({"run": run_id, "round": rnd, "seconds": round(time.time() - t0, 2),
                   "models": {"note": MODEL_NOTE, "segment": MODEL_SEG, "final": MODEL_FINAL},
                   "settings": {"over_kb": OVER_KB, "seg_kb": SEG_KB, "keep_turns": KEEP_TURNS, "max_keep": KEEP_MAX,
                                "max_keep_final": KEEP_FINAL_MAX, "max_keep_line_chars": KEEP_LINE_MAX},
                   "before": {"bytes": before, "counter_messages": len(rows)},
                   "compacted": {"bytes": sum(len(r[1].encode()) + 1 for r in prefix), "counter_messages": len(prefix),
                                 "stage1_bytes": sum(size(x) + 1 for x in lines)},
                   "after": {"bytes": os.path.getsize(new_path), "counter_messages": len(new_lines)},
                   "counter_tail_messages": len(tail),
                   "keep": {"counter_candidates": final["counter_candidates"], "final": [k["id"] + " " + k["tag"] for k in final["keep"]],
                            "dropped": [d for s in segs for d in s["dropped"]]}})
    write_json(os.path.join(RUN, "report.json"), report)
    if report["after"]["bytes"] >= before:    # 沒變小就不換（摘要寫得比原文還長）；半成品收成 nosave-<run>
        os.replace(RUN, os.path.join(CDIR, "nosave-" + run_id))
        log({"nosave": src["sha"], "run": "nosave-" + run_id, "before": before, "after": report["after"]["bytes"]})
        print("compact: 壓完沒變小（%d → %d bytes），不換上去；見 compact/nosave-%s" % (before, report["after"]["bytes"], run_id))
        return 0
    if sha(HIST) != src["sha"]:               # 壓的時候有人又接了一行：這次不換（半成品留著，下次會當 stale 收起來）
        die("HistoryChanged", "壓的期間 history.jsonl 被改了，這次不換上去")
    src.update({"new_sha": sha(new_path), "run": run_id})
    write_json(os.path.join(RUN, "source.json"), src)
    orig = os.path.join(RUN, "orig.jsonl")
    if not os.path.exists(orig):
        try:
            os.link(HIST, orig)                # 原本那份檔原封不動地收進來（同一份檔，不複製）
        except OSError:
            import shutil
            shutil.copy2(HIST, orig)
    os.replace(new_path, HIST)                 # 新的換上去（一步到位：別人看到的不是舊的就是新的）
    return finish(src)


def write_jsonl(path, lines):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
    os.replace(tmp, path)


def finish(src):
    dest = os.path.join(CDIR, src["run"])
    os.replace(RUN, dest)
    report = read_json(os.path.join(dest, "report.json"))
    log(report)
    st = report["stages"]
    print("compact: %d 則 %.1f KB → %d 則 %.1f KB（呼叫 note %d、segment %d、final %d 次；留 %d 行；%s）" % (
        report["before"]["counter_messages"], report["before"]["bytes"] / 1024, report["after"]["counter_messages"],
        report["after"]["bytes"] / 1024, st["note"]["counter_calls"], st["segment"]["counter_calls"], st["final"]["counter_calls"],
        len(report["keep"]["final"]), "compact/" + src["run"]))
    return 0


def last_log():
    try:
        with open(os.path.join(CDIR, "log.jsonl"), encoding="utf-8") as f:
            lines = [x for x in f if x.strip()]
        return json.loads(lines[-1]) if lines else {}
    except (OSError, ValueError):
        return {}


def log(entry):
    with open(os.path.join(CDIR, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


sys.exit(main())
