# common.py - train 三支（verify.py、train.py、rate.py）共用的小東西：路徑、讀寫 JSON、跑根一題、加總用量、看預算；
# 第四輪（round4 § 7.1）加：scope_check（收窄守門）、gather（一堆 score.json → 照表走的 total／dims／tags 彙總，不寫死維度名）、
# run_cost（某個 agent 的小格們平均每次花多少：llm_calls、llm_tokens、time_ms）、brain（整棵樹哪些節點還靠腦，讀根的 rollup）、run_question 的 env；
# 步驟 4 加 rollup_up／rollup_view（叫 meta/rollup）。
# 不是格、沒有 _entry；三支用 sys.path 從自己的資料夾 import（cwd＝train/，fsm 的內嵌單子）。純標準庫。
import datetime, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))          # galtxt-a/train
ROOT = os.path.dirname(HERE)                                 # galtxt-a
EXAMPLES = os.path.join(ROOT, "plan", "examples")


def die(code, reason, rc=1):
    print("train: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(rc)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path, code="StateBad", what="檔"):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        die(code, "%s讀不了：%s（%s）" % (what, path, e))


def load_or(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05：先寫 . 開頭的暫存檔再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def stack():
    s = os.environ.get("AOS_STACK")
    if not s:
        die("StackMissing", "沒設定 AOS_STACK")
    return s


def epoch(st):
    try:
        with open(os.path.join(st, "epoch.txt"), encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except FileNotFoundError:
        return 0
    except ValueError as e:
        die("StateBad", "epoch.txt 不是整數：%s" % e)


def edir(st, n):
    return os.path.join(st, "epochs", "%03d" % n)


def settings():
    s = load(os.path.join(HERE, "set.json"), "SetBad", "set.json ")
    b = load(os.path.join(HERE, "budget.json"), "SetBad", "budget.json ")
    if not all(isinstance(s.get(k), list) and s[k] for k in ("train", "verify", "writers")):
        die("SetBad", "set.json 要有非空的 train、verify、writers 陣列")
    return s, b


def run_question(cell, example, writer=None, env=None):
    """在小格 cell/{ws,stack} 跑根一題（被殺重跑：ws 已在就照原樣接著跑）；回 (結束碼, score.json 路徑)；env＝多給根的環境變數"""
    base = example[:-5] if example.endswith(".json") else example
    ws, st = os.path.join(cell, "ws"), os.path.join(cell, "stack")
    score = os.path.join(ws, "out", base, "score.json")
    if os.path.isfile(score):
        return 0, score
    if not os.path.isdir(ws):
        task = load(os.path.join(EXAMPLES, example), "SetBad", "題目 ")
        if writer is not None:
            task["writer"] = writer                            # 題目級覆寫（write.py：brief.writer 最優先）
        os.makedirs(os.path.join(ws, "new"))
        os.makedirs(st, exist_ok=True)
        save(os.path.join(ws, "new", example), task)
    env = dict(os.environ, AOS_STACK=st + "/", **(env or {}))
    try:
        r = subprocess.run(["aos-exec", "--ws", ws, ROOT], env=env, stdout=sys.stderr)   # 根的 stdout 不混進這格的
    except OSError as e:
        die("RunFailed", "aos-exec 起不來：%s" % e)
    return r.returncode, score


def usage_of(d):
    """d 底下所有寫手／評審小格的用量：counter_calls＝history.jsonl 裡 assistant 的則數（假腦也算），counter_tokens＝usage.jsonl 的 total_tokens（只有真腦有）"""
    calls = tokens = 0
    for here, subs, files in os.walk(d):
        if "history.jsonl" in files:
            with open(os.path.join(here, "history.jsonl"), encoding="utf-8") as f:
                calls += sum(1 for l in f if '"role": "assistant"' in l)
        if "usage.jsonl" in files:
            with open(os.path.join(here, "usage.jsonl"), encoding="utf-8") as f:
                for l in f:
                    try:
                        tokens += int(json.loads(l).get("total_tokens") or 0)
                    except (ValueError, AttributeError, TypeError):
                        pass
    return {"counter_calls": calls, "counter_tokens": tokens}


def check_budget(st, budget):
    """到頂＝stderr 一行 BudgetSpent、退 2（格與格之間檢查，最多超一題）"""
    u = usage_of(os.path.join(st, "epochs"))
    started = load_or(os.path.join(st, "started_at.json"), {}).get("started_at_ms")
    elapsed = int(datetime.datetime.now().timestamp() * 1000) - started if started else 0
    for k, v in (("max_calls", u["counter_calls"]), ("max_tokens", u["counter_tokens"]), ("max_elapsed_ms", elapsed)):
        if k in budget and v >= budget[k]:
            die("BudgetSpent", "%s %d 到頂（用了 %d）；data/route.json 留在最後一次 optimize 的結果" % (k, budget[k], v), rc=2)
    return u


def mark_started(st):
    p = os.path.join(st, "started_at.json")
    if not os.path.exists(p):
        save(p, {"started_at": now(), "started_at_ms": int(datetime.datetime.now().timestamp() * 1000)})


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = os.path.join(os.path.dirname(dst), "." + os.path.basename(dst))
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def scope_check(score, sets, where):
    """收窄守門（round4 § 1.2）：score.json 的 style 不是 set.json scope.style＝StateBad（不靠人記得）"""
    want = (sets.get("scope") or {}).get("style")
    if want is not None and score.get("style") != want:
        die("StateBad", "%s 的 style %r 不在收窄範圍（set.json scope.style＝%r）" % (where, score.get("style"), want))


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def gather(scores):
    """[score.json] → {totals, dims, tags}：dims＝過護欄草稿每個維度的平均（護欄＝過的份數比例；整題維度＝各題平均），
    tags＝評審理由標籤計數；cell_hits＝過護欄草稿的 hits（lint 命中的格 id，步驟 3b）每格幾次（同一份同一格只算一次）；
    維度名照 score.json 裡有的走（pick 照 data/dims.json 算好的），這裡不寫死"""
    totals, per, guard, whole, tags, cell_hits = [], {}, [], {}, {}, {}
    for s in scores:
        for d in s["drafts"]:
            guard.append(d["dims"].get("護欄"))
            if d["tier0"]:
                continue
            totals.append(d["total"])
            for k, v in d["dims"].items():
                if k != "護欄":
                    per.setdefault(k, []).append(v)
            if d.get("reason"):
                tags[d["reason"]] = tags.get(d["reason"], 0) + 1
            for cid in sorted({i for xs in (d.get("hits") or {}).values() for i in xs}):
                cell_hits[cid] = cell_hits.get(cid, 0) + 1
        for k, v in (s.get("dims") or {}).items():
            whole.setdefault(k, []).append(v)
    dims = {k: mean(v) for k, v in per.items()}
    dims["護欄"] = mean(guard)
    dims.update({k: mean(v) for k, v in whole.items()})
    return {"totals": totals, "dims": dims, "tags": dict(sorted(tags.items())), "cell_hits": dict(sorted(cell_hits.items()))}


def run_cost(cells, agent):
    """root 小格們（cell/stack）底下 <agent>/runs/*（寫手＝寫手資料夾名、評審＝judge）平均每次：
    llm_calls（history 的 assistant 則數）、llm_tokens（usage.jsonl）、time_ms（trace.jsonl 的 elapsed_ms 加總；程式階沒有＝0）"""
    runs = []
    for cell in cells:
        d = os.path.join(cell, "stack", agent, "runs")
        runs += [os.path.join(d, r) for r in sorted(os.listdir(d))] if os.path.isdir(d) else []
    if not runs:
        return None
    calls = tokens = ms = 0
    for r in runs:
        u = usage_of(r)
        calls, tokens = calls + u["counter_calls"], tokens + u["counter_tokens"]
        t = os.path.join(r, "stack", "trace.jsonl")
        if os.path.isfile(t):
            with open(t, encoding="utf-8") as f:
                for l in f:
                    try:
                        ms += int(json.loads(l).get("elapsed_ms") or 0)
                    except (ValueError, AttributeError, TypeError):
                        pass
    k = len(runs)
    return {"llm_calls": round(calls / k, 2), "llm_tokens": round(tokens / k), "time_ms": round(ms / k), "counter_runs": k}


ROLLUP = os.path.join(ROOT, "meta", "rollup", "_entry")


def rollup_up(sub):
    """rollup --up <子樹>（round4 § 3.3）：寫完旁檔後沿這棵往上重算 rollup.json 到根；stdout 照印（每層一行）；失敗＝RollupFailed 退 1"""
    try:
        r = subprocess.run([ROLLUP, "--up", sub], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as e:
        die("RollupFailed", "meta/rollup 起不來：%s" % e)
    if r.returncode != 0:
        die("RollupFailed", "rollup --up %s 結束碼 %d：%s" % (sub, r.returncode, r.stderr.strip()))
    sys.stdout.write(r.stdout)
    sys.stdout.flush()


def rollup_view(sub):
    """rollup --dry-run --json <子樹>：現在算出來的彙總（不寫檔）"""
    try:
        r = subprocess.run([ROLLUP, "--dry-run", "--json", sub], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            die("RollupFailed", "rollup --dry-run %s 結束碼 %d：%s" % (sub, r.returncode, r.stderr.strip()))
        return json.loads(r.stdout.splitlines()[0])
    except (OSError, ValueError, IndexError) as e:
        die("RollupFailed", "rollup --dry-run %s：%s" % (sub, e))


def brain(usage, questions):
    """整棵樹的腦用量（round4 § 2.3）：每題平均幾次腦、幾 token（實測：usage ÷ 題數）；節點在哪階＝根的 rollup（直接子樹＋攤平的「子樹/孫」）"""
    b = rollup_view(".").get("brain") or {}
    return {"llm_calls_per_question": round(usage["counter_calls"] / questions, 2) if questions else None,
            "llm_tokens_per_question": round(usage["counter_tokens"] / questions) if questions else None,
            "nodes": b.get("nodes", {}), "counter_on_brain": b.get("counter_on_brain", 0), "counter_program": b.get("counter_program", 0)}
