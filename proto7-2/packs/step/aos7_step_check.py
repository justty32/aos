"""step 步驟表檢查器（spec §6）與共用表欄定義。"""
import json
import re
from aos7_fs import is_int

NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
KINDS = ("run", "wait", "count", "end")
# 可逐步覆蓋的選項只有 wake（run）、on_timeout、on_unknown；restart_on_end 是工作級（spec §2）
FIELDS = {"run": {"run", "ok", "fail", "finite", "idempotent", "patience", "on_timeout", "on_unknown", "max_resends",
                  "receipt", "expect", "wake", "unknown_codes", "note"},
          "wait": {"wait", "then", "patience", "on_timeout", "fail", "note"},
          "count": {"count", "then", "exhausted", "note"},
          "end": {"end", "note"}}
TARGETS = {"run": ("ok", "fail"), "wait": ("then", "fail"), "count": ("then", "exhausted"), "end": ()}
OPTIONS = {"wake": (False, True), "restart_on_end": (False, True),
           "on_timeout": ("unknown", "fail", "kill"), "on_unknown": ("stop", "resend")}
DEFAULTS = {"wake": False, "restart_on_end": False, "on_timeout": "unknown", "on_unknown": "stop"}
COND_KINDS = ("exists", "glob", "result.ok", "num")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b,
       "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b, ">": lambda a, b: a > b}
VAR_RE = re.compile(r"\$\{([^}]*)\}")
PLAIN_VARS = ("job", "out", "step", "request", "attempt", "result")
# R3：v1 只有「本 node 的回合」一條時間線；看起來是別的鐘（秒、毫秒、期限、指定 clock）的欄一律擋
TIME_RE = re.compile(r"(_s|_ms|_sec|seconds|deadline|ttl|clock|timeout)$")

# ---------- 檢查器（spec §6） ----------

def kind_of(s):
    """步的種類鍵；不是恰好一個回 None。"""
    ks = [k for k in KINDS if k in s] if isinstance(s, dict) else []
    return ks[0] if len(ks) == 1 else None


def _cond_issues(c, steps):
    """條件 c 的格式問題（字串清單）。只准四種，不開運算式（spec §2）。"""
    if not isinstance(c, dict):
        return ["條件要是物件"]
    ks = [k for k in COND_KINDS if k in c]
    if len(ks) != 1:
        return ["條件要恰好一種（%s），拿到 %r" % ("／".join(COND_KINDS), sorted(c))]
    k = ks[0]
    extra = set(c) - ({"num", "key", "op", "value"} if k == "num" else {k})
    out = ["條件多了不認得的欄 %s" % sorted(extra)] if extra else []
    if k == "result.ok" and c[k] not in steps:
        out.append("result.ok 指到不存在的步 %r" % (c[k],))
    elif k != "result.ok" and not isinstance(c[k], str):
        out.append("%s 要是路徑字串" % k)
    if k == "num" and not (isinstance(c.get("key"), str) and c.get("op") in OPS
                           and isinstance(c.get("value"), (int, float)) and not isinstance(c.get("value"), bool)):
        out.append("num 要有 key（字串）、op（%s）、value（數字）" % " ".join(OPS))
    return out


def _var_issues(strings, steps):
    out = []
    for s in strings:
        for v in VAR_RE.findall(s):
            if v not in PLAIN_VARS and not (v.startswith("req:") and v[4:] in steps):
                out.append("不認得的展開 ${%s}" % v)
    return out


def _cycles(steps):
    """自己走得回自己的步（在跳轉圈裡）。"""
    def succ(n):
        s = steps.get(n)
        k = kind_of(s)
        return [s[f] for f in TARGETS.get(k, ()) if isinstance(s.get(f), str) and s.get(f) in steps]
    out = set()
    for n in steps:
        seen, todo = set(), list(succ(n))
        while todo:
            m = todo.pop()
            if m == n:
                out.add(n)
                break
            if m not in seen:
                seen.add(m)
                todo.extend(succ(m))
    return out


def _type_issues(table):
    """圖檢查之前先驗型別：會拿去查表（`in steps`、`in OPS`）的欄必須是字串，否則圖檢查會拋例外。回 [(步, 說明)]。"""
    steps = table["steps"]
    out = [] if isinstance(table.get("start", ""), str) else [(None, "start 要是步名字串")]
    for name, s in steps.items():
        if not isinstance(s, dict):
            continue
        for f in ("ok", "fail", "then", "exhausted"):
            if f in s and not isinstance(s[f], str):
                out.append((name, "%s 要是步名字串，拿到 %r" % (f, s[f])))
        for where, c in (("wait", s.get("wait")), ("receipt", s.get("receipt"))):
            if isinstance(c, dict):
                if "result.ok" in c and not isinstance(c["result.ok"], str):
                    out.append((name, "%s 的 result.ok 要是步名字串" % where))
                if "num" in c and "op" in c and not isinstance(c["op"], str):
                    out.append((name, "%s 的 op 要是字串" % where))
    return out


def check(table):
    """檢查步驟表，回 [{"level", "step", "rule", "why"}]。rule：struct／R1／R2／R3。不執行、不改檔。"""
    issues = []

    def add(level, step, rule, why):
        issues.append({"level": level, "step": step, "rule": rule, "why": why})
    if not isinstance(table, dict) or not isinstance(table.get("steps"), dict) or not table["steps"]:
        add("error", None, "struct", "步驟表要是 {\"job\", \"start\", \"steps\": {...}}")
        return issues
    steps = table["steps"]
    bad = _type_issues(table)
    for step, why in bad:            # 型別不對就只報這些、不做圖檢查（不拋例外）
        add("error", step, "struct", why)
    if bad:
        return issues
    for k in set(table) - {"job", "start", "steps", "options", "note"}:
        add("error", None, "R3" if TIME_RE.search(k) else "struct", "不認得的頂層欄 %r" % k)
    if not (isinstance(table.get("job"), str) and NAME_RE.match(table["job"])):
        add("error", None, "struct", "job 要是英數與 _（最多 32 字）")
    if table.get("start") not in steps:
        add("error", None, "struct", "start %r 不是表上的步" % (table.get("start"),))
    opts = table.get("options", {})
    if not isinstance(opts, dict):
        add("error", None, "struct", "options 要是物件")
        opts = {}
    for k, v in opts.items():
        if k not in OPTIONS:
            add("error", None, "R3" if TIME_RE.search(k) else "struct", "不認得的選項 %r" % k)
        elif v not in OPTIONS[k] or (isinstance(v, bool) != isinstance(OPTIONS[k][0], bool)):
            add("error", None, "struct", "選項 %s 只能是 %s" % (k, "／".join(map(json.dumps, OPTIONS[k]))))
    cyc = _cycles(steps)
    for name, s in steps.items():
        if not NAME_RE.match(str(name)):
            add("error", name, "struct", "步名只能用英數與 _（最多 32 字）")
        k = kind_of(s)
        if k is None:
            add("error", name, "struct", "每步恰好一個種類鍵（%s）" % "／".join(KINDS))
            continue
        for f in set(s) - FIELDS[k]:
            add("error", name, "R3" if TIME_RE.search(f) else "struct",
                "%s 步不認得的欄 %r%s" % (k, f, "（v1 只有本地回合的 patience）" if TIME_RE.search(f) else ""))
        for f in TARGETS[k]:
            if f in s and s[f] not in steps:
                add("error", name, "struct", "%s 指到不存在的步 %r" % (f, s[f]))
        need = {"run": ("ok",), "wait": ("then",), "count": ("then", "exhausted"), "end": ()}[k]
        for f in need:
            if f not in s:
                add("error", name, "struct", "%s 步要有 %s" % (k, f))
        if "patience" in s and not (is_int(s["patience"]) and s["patience"] >= 0):
            add("error", name, "R3", "patience 只接受非負整數（本 node 的回合數）；v1 沒有其他時間線，拿到 %r"
                % (s["patience"],))
        ot = s.get("on_timeout", opts.get("on_timeout", "unknown"))     # 套全域預設後的有效值
        if "on_timeout" in s and s["on_timeout"] not in OPTIONS["on_timeout"]:
            add("error", name, "struct", "on_timeout 只能是 unknown／fail／kill")
        elif ot == "kill" and k == "wait":
            add("error", name, "struct", "on_timeout: kill 只給 run 步%s" % (
                "" if "on_timeout" in s else "（全域選項是 kill，要在步內改回 unknown／fail）"))
        elif ot == "fail" and k in ("run", "wait") and "patience" in s and "fail" not in s:
            add("error", name, "struct", "on_timeout: fail 要有 fail 目標")
        if k == "run":
            a = s["run"]
            if not (isinstance(a, list) and a and all(isinstance(x, str) for x in a)):
                add("error", name, "struct", "run 要是非空字串陣列")
                a = []
            if "unknown_codes" in s:
                codes = s["unknown_codes"]
                if not (isinstance(codes, list) and codes
                        and all(is_int(c) and 1 <= c <= 255 for c in codes) and len(set(codes)) == len(codes)):
                    add("error", name, "struct", "unknown_codes 要是非空、互異的整數陣列（1～255）")
            ex = s.get("expect", [])
            if not (isinstance(ex, list) and all(isinstance(x, str) for x in ex)):
                add("error", name, "struct", "expect 要是路徑字串陣列")
                ex = []
            for f in ("finite", "idempotent", "wake"):
                if f in s and not isinstance(s[f], bool):
                    add("error", name, "struct", "%s 要是 true／false" % f)
            ou = s.get("on_unknown", opts.get("on_unknown", "stop"))
            if ou not in OPTIONS["on_unknown"]:
                add("error", name, "struct", "on_unknown 只能是 stop／resend")
            if "max_resends" in s and not (is_int(s["max_resends"]) and s["max_resends"] >= 0):
                add("error", name, "struct", "max_resends 要是非負整數（自動重送次數，預設 1）")
            for w in _var_issues(a + ex, steps):
                add("error", name, "struct", w)
            if "receipt" in s:
                for w in _cond_issues(s["receipt"], steps):
                    add("error", name, "struct", "receipt：" + w)
            if s.get("finite") is not True and "patience" not in s:
                add("error", name, "R1", "等結束只等有限工作：沒宣告 finite: true，也沒有 patience，可能永遠等")
            idem = s.get("idempotent") is True
            if name in cyc and not idem and "receipt" not in s:
                add("error", name, "R2", "在重試圈裡（走得回自己），要 idempotent: true 或先查回條（receipt）")
            if ou == "resend" and not idem:
                add("error", name, "R2", "on_unknown: resend 只准冪等步（idempotent: true）")
        elif k == "wait":
            for w in _cond_issues(s["wait"], steps):
                add("error", name, "struct", w)
            if "patience" not in s:
                add("warn", name, "R1", "wait 沒有 patience：條件不成立就一直等")
        elif k == "count" and not (is_int(s["count"]) and s["count"] >= 0):
            add("error", name, "struct", "count 要是非負整數")
        elif k == "end" and not isinstance(s["end"], str):
            add("error", name, "struct", "end 要是字串（結束狀態）")
    reach, todo = set(), [table.get("start")]
    while todo:
        n = todo.pop()
        if n in steps and n not in reach:
            reach.add(n)
            k = kind_of(steps[n])
            todo.extend(steps[n].get(f) for f in TARGETS.get(k, ()))
    for n in steps:
        if n not in reach:
            add("warn", n, "struct", "從 start 走不到")
    return issues


def errors_of(issues):
    return [i for i in issues if i["level"] == "error"]


