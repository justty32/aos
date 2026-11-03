# drift.py - train/score 的漂移那段（plan/round6.md §5、§7-7）：rounds/<輪>.json.drift 的三條線。score 的 _entry 載入它；測試直接叫 compute。
# 錨點（train/init 存的，不在＝不算、drift 為 null）：$AOS_WS/critic_v0/（那時的 critic 複本）、$AOS_WS/v0_drafts/<題>/<次>/answer.txt（tree_v0 那一代的既有稿）。
# 向量：critic 的 semantic÷3、承接、含蓄、角色味、反差、文筆（0～1，取兩位小數）；一條線的值＝各稿各維差的平均。
#   ① critic_drift（critic 漂多少）：現在的 critic 評 v0 的稿 − critic_v0 評同一批 v0 稿（基準）。現在的 critic 跟 critic_v0 檔案一樣＝0、0 token（「critic 未變＝漂移 0」）。
#   ② progress（樹真的進步多少）：critic_v0 評這輪的稿 − 基準（同題的 v0 稿）；另記 critic_gap＝這輪 score.json 裡現在 critic 給的 − critic_v0 給的（同一稿）。
#     這輪的稿取前 max_drafts 份（預設 2；有 critic 題目檔的才算，題目檔＝那次跑的 .stack/critic/ws/done/1.json）；v0 稿的題目借同題這輪的題目檔、換掉 draft。
#     基準（critic_v0 評 v0 稿）每題只問一次腦，存 $AOS_WS/drift/baseline.json，之後的輪照用。
#   ③ anchor：跟上一輪比，lint 維（護欄、語域，有錨）與 critic 維（同上的向量，無錨）的平均各變多少；critic 升而 lint 沒升＝suspicious（只標）。
# 腦用量（counter_tokens）＝這次為漂移問 critic 的 token 加總（假腦 0）。
import hashlib, json, os, re, shutil, subprocess

DIMS = ("semantic", "承接", "含蓄", "角色味", "反差", "文筆")
CRITIC_FILES = ("ask.py", "system.txt", "_entry", ".env")


def jload(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def critic_hash(d):
    h = hashlib.sha256()
    for n in CRITIC_FILES:
        p = os.path.join(d, n)
        h.update(n.encode())
        if os.path.isfile(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def vec_of_verdict(v):
    d = v.get("dims") if isinstance(v.get("dims"), dict) else {}
    out = {"semantic": round(v["semantic"] / 3, 2) if num(v.get("semantic")) is not None else None}
    out.update({k: round(d[k], 2) if num(d.get(k)) is not None else None for k in DIMS[1:]})
    return out


def vec_of_score(score):
    s = ((score or {}).get("dims") or {}).get("語意")
    if not isinstance(s, dict):
        return {k: None for k in DIMS}
    role = s.get("角色味")
    val = lambda x: num(x.get("val")) if isinstance(x, dict) else num(x)
    out = {"semantic": val(s), "承接": val(s.get("承接")), "含蓄": val(s.get("含蓄")), "角色味": val(role),
           "反差": num(role.get("反差")) if isinstance(role, dict) else num(s.get("反差")), "文筆": val(s.get("文筆"))}
    return {k: round(v, 2) if v is not None else None for k, v in out.items()}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def diff(va, vb):
    """兩組向量（同長、逐稿配對）各維差的平均（a − b）＋每維。"""
    per = {k: mean([a.get(k) - b.get(k) for a, b in zip(va, vb) if a.get(k) is not None and b.get(k) is not None]) for k in DIMS}
    return {"val": mean(list(per.values())), "dims": per}


def run_critic(cdir, question, sub, env):
    shutil.rmtree(sub, ignore_errors=True)
    write_json(os.path.join(sub, "ws", "new", "1.json"), question)
    r = subprocess.run(["aos-exec", "--ws", os.path.join(sub, "ws"), cdir], env=dict(env, AOS_STACK=sub + "/"),
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    tokens = 0
    try:
        with open(os.path.join(sub, "llm.jsonl"), encoding="utf-8") as f:
            tokens = sum(int(json.loads(l).get("counter_tokens") or 0) for l in f if l.strip())
    except (OSError, ValueError):
        pass
    if r.returncode != 0:
        return None, tokens
    try:
        with open(os.path.join(sub, "ws", "out", "1.txt"), encoding="utf-8") as f:
            v = json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", f.read().strip()))
    except (OSError, ValueError):
        return None, tokens
    return (vec_of_verdict(v) if isinstance(v, dict) else None), tokens


def lint_mean(rows):
    xs = []
    for r in rows:
        d = (r.get("score") or {}).get("dims") or {}
        xs += [num(d.get(k).get("val")) if isinstance(d.get(k), dict) else num(d.get(k)) for k in ("護欄", "語域")]
    return mean(xs)


def critic_mean(rows):
    return mean([mean(list(vec_of_score(r.get("score")).values())) for r in rows])


def compute(ws, n, rows, prev, env, max_drafts=2):
    cv0, cnow, v0d = os.path.join(ws, "critic_v0"), os.path.join(ws, "tree", "judge", "tools", "critic"), os.path.join(ws, "v0_drafts")
    if not os.path.isdir(cv0) or not os.path.isdir(cnow):
        return None
    work = os.path.join(ws, "drift", str(n))
    tokens = 0
    ok = [r for r in rows if not r.get("failed") and os.path.isfile(os.path.join(ws, r["ws"], ".stack", "critic", "ws", "done", "1.json"))]
    pick = ok[:max_drafts]
    qfile = {r["q"]: os.path.join(ws, r["ws"], ".stack", "critic", "ws", "done", "1.json") for r in ok}

    def v0_question(q):
        tq, ans = jload(qfile.get(q)), os.path.join(v0d, q, "1", "answer.txt")
        if not isinstance(tq, dict) or not os.path.isfile(ans):
            return None
        with open(ans, encoding="utf-8") as f:
            return dict(tq, draft=f.read().rstrip("\n"))

    bpath = os.path.join(ws, "drift", "baseline.json")
    base = jload(bpath, {}) or {}
    for r in pick:                               # 基準：critic_v0 評 v0 稿（每題一次，存起來）
        q = r["q"]
        if q not in base and v0_question(q) is not None:
            v, t = run_critic(cv0, v0_question(q), os.path.join(work, "baseline", q), env)
            tokens += t
            if v is not None:
                base[q] = v
    if base:
        write_json(bpath, base)
    pairs = [r for r in pick if r["q"] in base]

    same = critic_hash(cv0) == critic_hash(cnow)
    if same:
        line1 = {"val": 0, "dims": {k: 0 for k in DIMS}, "counter_tokens": 0, "note": "critic 未變＝漂移 0（檔案 hash 與 critic_v0 相同，沒有問腦）"}
    else:
        now_on_v0, t1 = [], 0
        for r in pairs:
            v, t = run_critic(cnow, v0_question(r["q"]), os.path.join(work, "now_on_v0", r["q"]), env)
            t1 += t
            now_on_v0.append(v or {})
        tokens += t1
        line1 = dict(diff(now_on_v0, [base[r["q"]] for r in pairs]), counter_tokens=t1, counter_drafts=len(pairs))

    v0_on_now, t2 = [], 0
    for i, r in enumerate(pairs):
        v, t = run_critic(cv0, jload(qfile[r["q"]]), os.path.join(work, "v0_on_now", "%d" % i), env)
        t2 += t
        v0_on_now.append(v or {})
    tokens += t2
    line2 = dict(diff(v0_on_now, [base[r["q"]] for r in pairs]), counter_tokens=t2, counter_drafts=len(pairs),
                 drafts=[r["ws"] for r in pairs])
    line2["critic_gap"] = diff([vec_of_score(r.get("score")) for r in pairs], v0_on_now)

    line3 = None
    prev_rows = [r for r in (prev or {}).get("runs") or [] if not r.get("failed") and isinstance(r.get("score"), dict)]
    now_rows = [r for r in rows if not r.get("failed") and isinstance(r.get("score"), dict)]
    if prev_rows and now_rows:
        dl = (lint_mean(now_rows) or 0) - (lint_mean(prev_rows) or 0)
        dc = (critic_mean(now_rows) or 0) - (critic_mean(prev_rows) or 0)
        line3 = {"lint_delta": round(dl, 3), "critic_delta": round(dc, 3),
                 "same_direction": (dl > 0) == (dc > 0) and (dl < 0) == (dc < 0),
                 "suspicious": dc > 0.05 and dl <= 0, "note": "lint 維＝護欄、語域（有錨）；critic 維＝語意拆的六維（無錨）；跟上一輪比"}
    return {"critic_drift": line1, "progress": line2, "anchor": line3, "counter_tokens": tokens, "critic_same_as_v0": same}
