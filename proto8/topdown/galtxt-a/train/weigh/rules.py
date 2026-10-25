# rules.py - 判斷器的規則階（round4 § 4.4）：照 rules.json 比兩份梯度 diff（A＝這一步、B＝不動），回「選：A|B」「理由：標籤」。
# 兩種用法：(1) 被 _entry 在 stage rules 時 import、對題目 decide()；(2) 假腦（brain.py 的 fake）也 import 它——假腦＝規則表，agent／rules 兩階答案相同。
# 題目（JSON）：{"A": diff, "B": diff（不動＝{}）, "before": 快照, "after": 快照, "params": {"min_gain", "min_loss"}, "epoch", "subtree", "action"}；
# diff 的鍵是攤平的（cost.llm_tokens、dims.護欄、tags＝{"+","-"}），快照是巢狀的（train/common.py 的 snapshot）。
# 規則一列：{"key", 條件…, "label"}；條件：lt／le／ge／gt（數；"min_gain"／"-min_loss" 從 params 取；relative＝差 ÷ before 的值）、
# drops／rises（數＝差的正負；[舊,新]＝val 照 good＞ok＞bad＞none、其他照大小，null 最小）、to_zero（after 是 0 而 before ＞ 0，看快照）、
# only_if_before_lt（before 的值 ＜ 這個才算）、contains_any（集合的 "+"／"-" 有其中一個）、and（另一列也要成立）；
# reject_if 的列可帶 unless（一列或多列，任一成立＝這條不拒）。沒這個鍵＝沒變＝條件不成立。
# 判法：A、B 各自先過 reject_if（任一成立＝那份出局）；兩份都還在＝看 prefer 第一條成立的順位（小的贏）；都沒有或同順位＝tie（rules.json 寫 B）。
# 純標準庫、確定性。
import json

RANK = {"good": 3, "ok": 2, "bad": 1, "none": 0}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def get(d, key):
    """攤平的 diff 取值：先找整個 key；沒有就把最後一段當子鍵（tags.+ → diff["tags"]["+"]）"""
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    head, _, tail = key.rpartition(".")
    sub = d.get(head) if head else None
    return sub.get(tail) if isinstance(sub, dict) else None


def path(d, key):
    """巢狀的快照取值：cost.llm_tokens → d["cost"]["llm_tokens"]"""
    for k in key.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _thr(x, params):
    if isinstance(x, str):
        neg = x.startswith("-")
        v = (params or {}).get(x.lstrip("-"))
        return -v if neg and _num(v) else v
    return x


def _order(key, x):
    if key.split(".")[-1] == "val":
        return RANK.get(x, -1)
    if x is None:
        return float("-inf")
    return float(x) if isinstance(x, (bool, int, float)) else None


def holds(rule, d, q):
    key, params = rule["key"], q.get("params") or {}
    before, after = q.get("before") or {}, q.get("after") or {}
    v = get(d, key)
    if "only_if_before_lt" in rule:
        b = path(before, key)
        if not (_num(b) and b < rule["only_if_before_lt"]):
            return False
    if rule.get("to_zero"):
        a, b = path(after, key), path(before, key)
        if not (_num(a) and _num(b) and a == 0 and b > 0) or d is not q.get("A"):
            return False
    for op in ("lt", "le", "ge", "gt"):
        if op in rule:
            t = _thr(rule[op], params)
            x = v
            if rule.get("relative") and _num(x):
                b = path(before, key)
                x = x / b if _num(b) and b > 0 else None
            if not (_num(x) and _num(t)):
                return False
            if not {"lt": x < t, "le": x <= t, "ge": x >= t, "gt": x > t}[op]:
                return False
    for op in ("drops", "rises"):
        if rule.get(op):
            if _num(v):
                ok = v < 0 if op == "drops" else v > 0
            elif isinstance(v, list) and len(v) == 2:
                a, b = _order(key, v[0]), _order(key, v[1])
                ok = a is not None and b is not None and (b < a if op == "drops" else b > a)
            else:
                ok = False
            if not ok:
                return False
    if "contains_any" in rule:
        xs = v if isinstance(v, list) else []
        if not any(t in xs for t in rule["contains_any"]):
            return False
    if "and" in rule and not holds(rule["and"], d, q):
        return False
    return True


def rejected(rules, d, q):
    for r in rules.get("reject_if") or []:
        un = r.get("unless")
        un = un if isinstance(un, list) else [un] if un else []
        if holds(r, d, q) and not any(holds(u, d, q) for u in un):
            return r.get("label") or r["key"]
    return None


def preferred(rules, d, q):
    for i, r in enumerate(rules.get("prefer") or []):
        if holds(r, d, q):
            return i, r.get("label") or r["key"]
    return None, None


def decide(q, rules):
    """回 (choice, reason)"""
    A, B = q.get("A") or {}, q.get("B") or {}
    ra, rb = rejected(rules, A, q), rejected(rules, B, q)
    if ra and not rb:
        return "B", "拒A：" + ra
    if rb and not ra:
        return "A", "拒B：" + rb
    if ra and rb:
        return rules.get("tie", "B"), "兩份都拒"
    ia, la = preferred(rules, A, q)
    ib, lb = preferred(rules, B, q)
    if ia is not None and (ib is None or ia < ib):
        return "A", la
    if ib is not None and (ia is None or ib < ia):
        return "B", lb
    return rules.get("tie", "B"), "沒有可取的變化" if ia is None else "同順位：" + la


def answer(q, rules):
    choice, reason = decide(q, rules)
    return "選：%s\n理由：%s\n" % (choice, reason)


def load_rules(p="rules.json"):
    with open(p, encoding="utf-8") as f:
        return json.load(f)
