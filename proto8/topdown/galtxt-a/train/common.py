# common.py - train 三支（verify.py、train.py、rate.py）共用的小東西：路徑、讀寫 JSON、跑根一題、加總用量、看預算
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


def run_question(cell, example, writer=None):
    """在小格 cell/{ws,stack} 跑根一題（被殺重跑：ws 已在就照原樣接著跑）；回 (結束碼, score.json 路徑)"""
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
    env = dict(os.environ, AOS_STACK=st + "/")
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
