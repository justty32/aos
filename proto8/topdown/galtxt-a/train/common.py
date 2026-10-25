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


def called(sets):
    """這棵樹每題實際會被叫到的節點的根（步驟 5 隊長裁定）：set.json 的 writers、data/route.json 會選到的（default＋by_style）、grader、train/weigh；
    再加它們底下的「子樹/孫」與根的 tools/*（is_called 判）。凍結的 writer-sol 只有被 route 選到才算；idle、train、train/optimize、meta、human 不算"""
    route = load_or(os.path.join(ROOT, "data", "route.json"), {}) or {}
    roots = set(sets.get("writers") or []) | {route.get("default")} | set((route.get("by_style") or {}).values()) | {"grader", "train/weigh"}
    return {r for r in roots if isinstance(r, str) and r}


def is_called(name, roots):
    return name.startswith("tools/") or any(name == r or name.startswith(r + "/") for r in roots)


def brain(usage, questions, sets):
    """整棵樹的腦用量（round4 § 2.3）：每題平均幾次腦、幾 token（實測：usage ÷ 題數）；節點在哪階＝根的 rollup（直接子樹＋攤平的「子樹/孫」），
    只留 called() 的（其餘放 excluded {名: 階}；meta/rollup 讀根評級這格的 excluded，根 rollup.json 的 brain 跟這裡同一套）"""
    b = rollup_view(".").get("brain") or {}
    every = dict(b.get("nodes") or {}, **(b.get("excluded") or {}))
    roots = called(sets)
    nodes = {k: v for k, v in sorted(every.items()) if is_called(k, roots)}
    on = sum(1 for v in nodes.values() if v in ("agent", "semi"))
    return {"llm_calls_per_question": round(usage["counter_calls"] / questions, 2) if questions else None,
            "llm_tokens_per_question": round(usage["counter_tokens"] / questions) if questions else None,
            "nodes": nodes, "counter_on_brain": on, "counter_program": len(nodes) - on,
            "excluded": {k: v for k, v in sorted(every.items()) if k not in nodes}}


# ---- 步驟 5：梯度（round4 § 4.1）、通用改動清單 params/changed.json（§ 5.2 第 5 點、selfopt § 1.2）----

def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def diff(before, after, _pre=""):
    """§ 4.1 的結構化 diff（跟 _metainfo 同形，巢狀的物件攤平成「a.b」）：數值鍵＝差（after − before，三位小數）；
    非數值（字串、布林、null↔數）＝[舊, 新]；陣列當集合＝{"+": 多的, "-": 少的}；沒變的鍵不出現；兩邊同＝{}"""
    out = {}
    before, after = before or {}, after or {}
    for k in sorted(set(before) | set(after)):
        a, b, name = before.get(k), after.get(k), _pre + k
        if a == b:
            continue
        if isinstance(a, (dict, type(None))) and isinstance(b, (dict, type(None))) and (isinstance(a, dict) or isinstance(b, dict)):
            out.update(diff(a, b, name + "."))
        elif isinstance(a, (list, type(None))) and isinstance(b, (list, type(None))):
            ka = {json.dumps(x, ensure_ascii=False, sort_keys=True): x for x in a or []}
            kb = {json.dumps(x, ensure_ascii=False, sort_keys=True): x for x in b or []}
            plus, minus = [kb[x] for x in sorted(set(kb) - set(ka))], [ka[x] for x in sorted(set(ka) - set(kb))]
            if plus or minus:
                out[name] = {"+": plus, "-": minus}
        elif _num(a) and _num(b):
            d = round(b - a, 3)
            if d:
                out[name] = d
        else:
            out[name] = [a, b]
    return out


def val_of(avg, k):
    if k < 3 or avg is None:
        return "none"
    return "good" if avg >= 4.0 else "ok" if avg >= 3.0 else "bad"


def epoch_cells(d):
    """某個 epoch 的驗證＋measure 小格（verify.py 開的 epochs/NNN/{verify,measure}/<題名>/）"""
    out = []
    for sub in ("verify", "measure"):
        p = os.path.join(d, sub)
        out += [os.path.join(p, x) for x in sorted(os.listdir(p))] if os.path.isdir(p) else []
    return out


def snapshot(v, stage, cost):
    """被改子樹的對外描述（§ 4.1 before／after 的形狀）：v＝那個 epoch 的 verify.json（驗證題＋measure 的實測），
    stage＝那時的 <子樹>/stage.json（沒有＝None），cost＝那棵在驗證小格的每次用量（run_cost；量不到退回每題用量）"""
    v = v or {}
    out = {"val": val_of(v.get("score_mean"), v.get("counter_samples") or 0), "total_avg": v.get("score_mean"),
           "determinism": (v.get("measure") or {}).get("一致"), "dims": v.get("dims") or {},
           "bench": {"guard_hit": v.get("guard_hit"), "bigram_overlap": v.get("bigram_overlap")},
           "tags": sorted(v.get("tags") or {}), "cells": sorted(v.get("cell_hits") or {})}
    b = v.get("brain") or {}
    out["cost"] = {"llm_tokens": (cost or {}).get("llm_tokens", b.get("llm_tokens_per_question")),
                   "llm_calls": (cost or {}).get("llm_calls", b.get("llm_calls_per_question"))}
    if isinstance(stage, dict):
        out["stage"], out["tools"] = stage.get("stage"), sorted(stage.get("tools") or [])
    return out


def cell_prefix(rel):
    """data/<路徑>.json → 格 id 前綴（cells.py 的規則：templates→tpl、templates.distilled→tpld；其餘「/」換「.」）；不是 data 底下的 JSON＝None"""
    if not (rel.startswith("data/") and rel.endswith(".json")):
        return None
    p = rel[5:-5].replace("/", ".")
    return {"templates": "tpl", "templates.distilled": "tpld"}.get(p, p)


def cells_touched(rel, old_path, new_path):
    """這一步改了 data 底下哪幾格（grad.json 的 changed_cells）：cells.touched(舊, 新, 前綴)；不是格檔＝[]"""
    pre = cell_prefix(rel)
    if pre is None:
        return []
    sys.path.insert(0, ROOT)
    import cells  # noqa: E402
    return cells.touched(load_or(old_path, {}) if old_path else {}, load_or(new_path, {}), pre)


def params_save(st, n, change, files, created=()):
    """改樹之前叫（optimize 的外部動作、selfopt accept 都用這支）：files（相對樹根）拷進 $AOS_STACK/epochs/NNN/params/<同路徑>，
    再寫 params/changed.json＝change＋{files, created, at}。change 至少 {source, action, subtree}；可帶 target、cells（改了哪幾格；沒給＝verify 照 files 算）、
    from／to／task。回滾（verify 選 B）＝files 有快照的拷回、沒快照的（本來不存在）刪掉、created 整個刪（只准 tools/ 底下）"""
    for k in ("source", "action", "subtree"):
        if not isinstance(change.get(k), str):
            die("StateBad", "changed.json 要有字串 %s" % k)
    p = os.path.join(edir(st, n), "params")
    for rel in files:
        src = os.path.join(ROOT, rel)
        if os.path.isfile(src):
            copy(src, os.path.join(p, rel))
    save(os.path.join(p, "changed.json"), dict(change, files=list(files), created=list(created), at=now()))
    return p


def _inside(rel):
    full = os.path.realpath(os.path.join(ROOT, rel))
    if os.path.isabs(rel) or ".." in rel.split("/") or not full.startswith(ROOT + os.sep):
        die("StateBad", "changed.json 的路徑 %r 不在樹裡" % rel)
    return full


def rollback(params, change):
    """照 changed.json 把樹改回去；回改了哪些檔"""
    done = []
    for rel in change.get("files") or []:
        full, snap = _inside(rel), os.path.join(params, rel)
        if os.path.isfile(snap):
            copy(snap, full)
        elif os.path.isfile(full):
            os.remove(full)
        done.append(rel)
    for rel in change.get("created") or []:
        full = _inside(rel)
        if "tools" not in rel.split("/")[:-1]:
            die("StateBad", "created 只准刪 tools/ 底下的：%r" % rel)
        if os.path.isdir(full) and not os.path.islink(full):
            shutil.rmtree(full)
        elif os.path.lexists(full):
            os.remove(full)
        done.append(rel)
    return done
