"""step 任務包：步驟表直譯器、檢查器、人手指令（spec 見同資料夾的 spec.md；契約卡在 README.md）。

    aos7-step run <工作資料夾>          普通 keep 任務（max_live 1）：每收到 tock 走一圈
    aos7-step check <steps.json>        結構＋三條（R1 有限、R2 冪等／回條、R3 時間線）
    aos7-step status|resume|close <工作資料夾> [--resend]

只用核心公開的檔：tasks.json（拿表鎖、三態寫，壞表拒寫）、槽的 birth.json／exit.json（判斷子工作起了沒、結束沒）、
round.json（本地回合）、tock.json（等回合）、槽 ctl.json（帶 run 的 kill）、daemon 控制檔（wake）。核心不知道這個包。
交付的依據是槽外的結果檔（aos7_step_result.py 寫）；exit.json 只當旁證。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))           # proto7-2/
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib")]
from aos7_fs import N, OK, U, Unknown, edit_json, fact, is_int, now, sweep_tmp, write_json  # noqa: E402

RESULT_BIN = os.path.join(HERE, "bin", "aos7-step-result")
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
MAX_STEPS_PER_PASS = 64   # 一圈最多走幾步（count／wait 的圈不會無限轉；超過就留到下一圈）


class Halt(Exception):
    """這一步走不下去、要停住等人（框架 phase=halted）。kind：unknown／timeout／failed／version／expand。"""

    def __init__(self, kind, why):
        super().__init__(why)
        self.kind = kind


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


# ---------- 工作資料夾 ----------

def table_rev(raw):
    return hashlib.sha1(raw).hexdigest()[:12]


class Job:
    """一個工作資料夾（spec §1）。jd 是相對 node（cwd）的路徑，展開 ${job} 時原樣用，node 搬家也不壞。"""

    def __init__(self, jd, node=None):
        self.jd = jd.rstrip("/")
        self.node = node or os.getcwd()
        self.frame_path = self.p("frame.json")

    def p(self, *a):
        return os.path.join(self.jd, *a)

    def a(self, rel):
        """相對 node 的路徑 → 絕對路徑（核心檔、結果檔都用它讀）。"""
        return rel if os.path.isabs(rel) else os.path.join(self.node, rel)

    def load_table(self):
        """回 (表, 版本)；讀不到、壞掉丟 Unknown（呼叫的人記錯、不前進）。"""
        path = self.a(self.p("steps.json"))
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            raise Unknown("steps.json 讀不到：%r" % e, kind="table")
        try:
            t = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise Unknown("steps.json 不是 JSON", kind="table")
        errs = errors_of(check(t))
        if errs:
            raise Unknown("steps.json 檢查沒過：%s" % "；".join("%s %s：%s" % (e["rule"], e["step"], e["why"])
                                                               for e in errs[:5]), kind="check")
        return t, table_rev(raw)

    def error(self, kind, where, why, rnd=None, tock=None):
        """記最近一筆錯誤到 error.json（覆寫，只留上一次）；寫不進去就算了，stderr 也有一份。"""
        rec = {"kind": kind, "where": where, "why": str(why)[:500], "at": now(), "round": rnd, "tock": tock}
        print("aos7-step: %s %s：%s" % (kind, where, why), file=sys.stderr, flush=True)
        try:
            write_json(self.a(self.p("error.json")), rec)
        except OSError:
            pass

    def read_frame(self):
        """框架三態：(N, None)／(OK, 框架)；讀不到、壞掉、缺欄丟 Unknown——不前進、記錯、等人，不從結果檔反推。"""
        st, fr = fact(self.a(self.frame_path))
        if st == N:
            return N, None
        if st == OK and isinstance(fr, dict) and fr.get("v") == 1 and isinstance(fr.get("inst"), str) \
                and fr.get("phase") in ("running", "halted", "ended") and isinstance(fr.get("rev"), int) \
                and all(isinstance(fr.get(k), dict) for k in ("counts", "visits", "accepted", "tries")):
            fr.setdefault("resends", {})
            return OK, fr
        raise Unknown("frame.json %s；不前進，等人修好或刪掉重來" % (fr if st != OK else "缺欄或型別不對"), kind="frame")

    def save(self, fr):
        """寫框架：拿 frame.json.lock，磁碟上的 rev 要等於讀進來的（人手 resume／close 改過就放棄這次寫，下一圈重讀）。"""
        want = fr.get("rev")

        def fn(cur):
            have = None if cur is None else (cur.get("rev") if isinstance(cur, dict) else "?")
            if have != (None if want == 0 else want):
                raise Unknown("frame.json 在這一圈中被改過（rev %r→%r），這圈不寫" % (want, have), kind="frame-race")
            return dict(fr, rev=want + 1, at=now())
        edit_json(self.a(self.frame_path), fn, timeout=2.0)
        fr["rev"] = want + 1


def new_frame(t, rev, rnd=None):
    """新工作：新 inst、pc=start、since＝現在的回合（spec §3；不知道就留 None，advance 開頭補）。rev=0 表示磁碟上還沒有框架。"""
    return {"v": 1, "job": t["job"], "inst": uuid.uuid4().hex[:8], "table": rev, "pc": t["start"],
            "phase": "running", "counts": {}, "visits": {t["start"]: 1}, "accepted": {}, "tries": {}, "resends": {},
            "pending": None, "halt": None, "end": None, "since": rnd, "seen": None, "rev": 0}


def request_of(fr, step):
    return "%s-%s-%d" % (fr["inst"], step, fr["visits"].get(step, 1))


# ---------- 讀核心公開的檔 ----------

def node_round(node, fallback=None):
    """本 node 現在的回合（round.json 的 round）；讀不到用 fallback（最近一次 tock 的回合）。"""
    st, r = fact(os.path.join(node, ".aos", "round.json"))
    if st == OK and isinstance(r, dict) and is_int(r.get("round")):
        return r["round"]
    return fallback


def slot_of(node, task):
    return os.path.join(node, ".aos", "tasks", task)


def attempt_of(d):
    """tasks.json 項或 birth.json 的 `x.step.attempt`（本包在 x 底下的 key）；沒有回 None。"""
    x = d.get("x") if isinstance(d, dict) else None
    st = x.get("step") if isinstance(x, dict) else None
    return st.get("attempt") if isinstance(st, dict) else None


def table_has(t, attempt):
    items = t.get("tasks") if isinstance(t, dict) else None
    return isinstance(items, list) and any(attempt_of(i) == attempt for i in items)


def slot_attempt(node, task, attempt):
    """槽裡是不是這個 attempt：回 None（不是／沒有槽）、("live", birth)、("ended", birth, exit)。讀不到丟 Unknown。"""
    fs = slot_of(node, task)
    st, b = fact(os.path.join(fs, "birth.json"))
    if st == N:
        return None
    if st != OK:
        raise Unknown("槽 %s 的 birth.json %s" % (task, b), kind="slot")
    if attempt_of(b) != attempt:
        return None
    st, ex = fact(os.path.join(fs, "exit.json"))
    if st == OK and isinstance(ex, dict) and ex.get("run") == b.get("run"):
        return ("ended", b, ex)
    if st not in (OK, N):
        raise Unknown("槽 %s 的 exit.json %s" % (task, ex), kind="slot")
    return ("live", b)


# ---------- 直譯器 ----------

def test_crash(job, point):
    """測試用的 SIGKILL 點（包自己的，不碰核心鉤子）：工作資料夾有 `.step-crash` 寫著這個點就刪檔、殺自己。"""
    path = job.a(job.p(".step-crash"))
    try:
        with open(path) as f:
            want = f.read().strip()
    except OSError:
        return
    if want == point:
        os.unlink(path)
        os.kill(os.getpid(), signal.SIGKILL)


class Interp:
    """一圈的狀態：工作、表、框架、回合。"""

    def __init__(self, job, t, fr, rnd):
        self.job, self.t, self.fr, self.rnd = job, t, fr, rnd
        self.steps = t["steps"]
        self.opts = dict(DEFAULTS, **t.get("options", {}))

    def opt(self, s, k):
        return s.get(k, self.opts[k])

    # ----- 展開與條件 -----

    def vars(self, step, p=None):
        v = {"job": self.job.jd, "out": self.job.p("out"), "step": step}
        if p:
            v.update(request=p["request"], attempt=p["attempt"], result=p["result"])
        return v

    def expand(self, s, v):
        def one(m):
            k = m.group(1)
            if k.startswith("req:"):
                acc = self.fr["accepted"].get(k[4:])
                if not acc:
                    raise Halt("expand", "${%s}：%s 還沒有採用的結果" % (k, k[4:]))
                return acc["request"]
            if k not in v:
                raise Halt("expand", "${%s} 在這裡展開不了" % k)
            return v[k]
        return VAR_RE.sub(one, s)

    def cond(self, c, step):
        """四種條件之一（spec §2）。讀不到的檔＝不成立（下一圈再看）。"""
        v = self.vars(step)
        if "exists" in c:
            return os.path.exists(self.job.a(self.expand(c["exists"], v)))
        if "glob" in c:
            import glob
            return bool(glob.glob(self.job.a(self.expand(c["glob"], v))))
        if "result.ok" in c:
            return bool((self.fr["accepted"].get(c["result.ok"]) or {}).get("ok"))
        st, d = fact(self.job.a(self.expand(c["num"], v)))
        for part in c["key"].split("."):
            d = d.get(part) if isinstance(d, dict) else None
        if st != OK or not isinstance(d, (int, float)) or isinstance(d, bool):
            return False
        return OPS[c["op"]](d, c["value"])

    # ----- 轉移 -----

    def goto(self, target):
        fr = self.fr
        fr["pc"] = target
        fr["visits"][target] = fr["visits"].get(target, 0) + 1
        fr["since"] = self.rnd
        fr["pending"] = None

    def halt(self, kind, why):
        self.fr["phase"] = "halted"
        self.fr["halt"] = {"kind": kind, "why": why, "step": self.fr["pc"], "round": self.rnd, "at": now()}

    def accept(self, step, s, res):
        """採用一份結果：記 accepted、照 ok／fail 跳；沒寫 fail 的失敗＝停（failed）。"""
        self.fr["accepted"][step] = {k: res.get(k) for k in ("request", "attempt", "ok", "run", "code", "receipt")
                                     if k in res}
        if res.get("ok"):
            self.goto(s["ok"])
        elif "fail" in s:
            self.goto(s["fail"])
        else:
            self.fr["pending"] = None
            self.halt("failed", "%s 的結果 ok: false（code %r），表上沒寫 fail" % (step, res.get("code")))

    # ----- 派工（spec §5 第 4 點） -----

    def new_pending(self, step):
        fr = self.fr
        req = request_of(fr, step)
        k = fr["tries"].get(req, 0) + 1
        fr["tries"][req] = k
        att = "%s-a%d" % (req, k)
        return {"step": step, "request": req, "attempt": att, "n": k, "task": "step-%s-%s" % (fr["job"], step),
                "result": self.job.p("results", step, att + ".json"), "state": "intent",
                "intent_round": self.rnd, "since": self.rnd}

    def item(self, s, p):
        v = self.vars(p["step"], p)
        argv = [self.expand(x, v) for x in s["run"]]
        cmd = [sys.executable, RESULT_BIN, "--result", p["result"], "--job", self.fr["job"], "--inst", self.fr["inst"],
               "--step", p["step"], "--request", p["request"], "--attempt", p["attempt"]]
        for e in s.get("expect", []):
            cmd += ["--expect", self.expand(e, v)]
        return {"name": p["task"], "mode": "once", "argv": cmd + ["--"] + argv,
                "x": {"step": {k: (self.fr[k] if k in ("job", "inst") else p[k])
                               for k in ("job", "inst", "step", "request", "attempt")}}}

    def add_item(self, item, p, fresh_check=False):
        """拿表鎖加 once 項（表上已有同 attempt 就不加）。fresh_check：補加前在鎖內確認「確定沒加上過」
        （槽裡沒有這個 attempt、回合 == intent_round），不成立丟 Halt unknown。表壞、鎖拿不到丟 Unknown（拒寫）。"""
        node = self.job.node

        def fn(t):
            t = {"tasks": []} if t is None else t
            if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
                raise Unknown("tasks.json 不是 {\"tasks\": [...]}，拒寫", kind="tasks")
            if table_has(t, p["attempt"]):
                return None
            if fresh_check:
                if slot_attempt(node, p["task"], p["attempt"]) is not None:
                    raise Halt("unknown", "派工意圖之後槽裡出現這個 attempt，表上卻沒有")
                cur = node_round(node)
                if cur is None or cur > p["intent_round"]:
                    raise Halt("unknown", "派工意圖寫了、表上沒有這項、槽也沒有（回合 %r，意圖在 %r）：說不清加上過沒有"
                               % (cur, p["intent_round"]))
            return dict(t, tasks=list(t.get("tasks", [])) + [item])
        edit_json(os.path.join(node, ".aos", "tasks.json"), fn, timeout=1.0)

    def dispatch(self, step, s, p=None):
        """先存意圖、再加項、再記 queued。表壞／鎖不到＝撤意圖、記錯，下一圈重來（spec §5）。"""
        if self.rnd is None:
            raise Unknown("不知道現在第幾回合（round.json 讀不到），這圈不派工", kind="round")
        p = p or self.new_pending(step)
        item = self.item(s, p)           # 先展開（展開不了＝停），再存意圖
        self.fr["pending"] = p
        self.job.save(self.fr)
        test_crash(self.job, "after-intent")
        try:
            self.add_item(item, p)
        except Unknown:
            self.fr["pending"] = None
            self.job.save(self.fr)
            raise
        test_crash(self.job, "after-add")
        p["state"] = "queued"
        self.job.save(self.fr)
        if self.opt(s, "wake"):
            try:
                import aos7_ctl
                aos7_ctl.daemon_ctl(os.environ["AOS7_ROOT"], "wake", os.environ["AOS7_NODE_ID"], why="step %s" % step)
            except (OSError, KeyError) as e:
                self.job.error("wake", step, e, self.rnd)

    # ----- 等一個派出的嘗試（spec §5 第 4～6 點） -----

    def read_result(self, p):
        st, r = fact(self.job.a(p["result"]))
        if st == N:
            return None
        if st == U:
            raise Unknown("結果檔 %s" % r, kind="result")
        ids = {"job": self.fr["job"], "inst": self.fr["inst"], "step": p["step"], "request": p["request"],
               "attempt": p["attempt"]}
        if st != OK or not isinstance(r, dict) or any(r.get(k) != v for k, v in ids.items()) \
                or not isinstance(r.get("ok"), bool):
            raise Halt("unknown", "結果檔 %s 內容不合（識別欄對不上或缺 ok）" % p["result"])
        return r

    def evidence(self, p):
        """回 ("result", r)／("wait", 說明)／("readd", None)／("unknown", 說明)。讀順序：結果→表→槽→回合
        （tick 先寫 birth 再刪表項，先讀表後讀槽才不會兩邊都撲空）。"""
        r = self.read_result(p)
        if r:
            return "result", r
        st, t = fact(os.path.join(self.job.node, ".aos", "tasks.json"))
        if st == OK and table_has(t, p["attempt"]):
            p["state"] = "queued"
            return "wait", "表上還沒起"
        sa = slot_attempt(self.job.node, p["task"], p["attempt"])
        if sa and sa[0] == "live":
            return "wait", "子工作在跑（%s#%s）" % (p["task"], sa[1].get("run"))
        if sa:
            r = self.read_result(p)       # 包裝程式先寫結果才結束：看到 exit 之後再讀一次
            if r:
                return "result", r
            ex = sa[2]
            return "unknown", "子工作 %s#%s 結束了（code %r%s）卻沒有結果檔" % (
                p["task"], sa[1].get("run"), ex.get("code"), "，never_started" if ex.get("never_started") else "")
        if st not in (OK, N):
            raise Unknown("tasks.json %s，看不出表上有沒有這項" % t, kind="tasks")
        if p["state"] == "intent":
            return "readd", None
        return "unknown", "表上沒有、槽裡也沒有這個 attempt，結果檔也沒有（槽可能已被清掉）"

    def on_unknown(self, step, s, p, why):
        if "receipt" in s and self.cond(s["receipt"], step):
            self.accept(step, s, {"request": p["request"], "attempt": p["attempt"], "ok": True, "receipt": True})
            return True
        n = self.fr["resends"].get(p["request"], 0)
        if self.opt(s, "on_unknown") == "resend" and s.get("idempotent") is True \
                and n < s.get("max_resends", 1):
            self.fr["resends"][p["request"]] = n + 1
            q = self.new_pending(step)
            self.dispatch(step, s, q)
            return False
        self.halt("unknown", why)
        return False

    def on_timeout(self, step, s, p):
        ot = self.opt(s, "on_timeout")
        why = "等了 %d 回合（patience %d，本地回合）" % (self.rnd - (p or self.fr)["since"], s["patience"])
        if ot == "fail" and "fail" in s:
            self.goto(s["fail"])
            return True
        if ot == "kill" and p:
            sa = slot_attempt(self.job.node, p["task"], p["attempt"])
            if sa and sa[0] == "live":
                import aos7_ctl
                aos7_ctl.task_ctl(slot_of(self.job.node, p["task"]), why="step timeout", run=sa[1]["run"])
                why += "；已送 kill（run %s）" % sa[1]["run"]
        self.halt("timeout", why + "；逾時不等於沒做，遲到的結果照樣留著")
        return False

    def expired(self, s, since):
        """耐性到期了沒：本 node 回合（pause 時不走）；回合不知道就不算到期（spec §5 第 5 點）。"""
        return "patience" in s and self.rnd is not None and since is not None and self.rnd - since > s["patience"]

    # ----- 一圈 -----

    def advance(self):
        """照 pc 前進，最多登記一個 once。回 True＝工作結束。"""
        fr = self.fr
        if fr["since"] is None and self.rnd is not None:      # 建框架時回合還不知道：第一次知道就當耐性起點
            fr["since"] = self.rnd
        for _ in range(MAX_STEPS_PER_PASS):
            if fr["phase"] != "running":
                break
            step = fr["pc"]
            s = self.steps[step]
            k = kind_of(s)
            if k == "end":
                fr["phase"], fr["end"] = "ended", s["end"]
                break
            if k == "count":
                c = fr["counts"].get(step, 0) + 1
                fr["counts"][step] = c
                self.goto(s["then"] if c <= s["count"] else s["exhausted"])
                continue
            if k == "wait":
                if self.cond(s["wait"], step):
                    self.goto(s["then"])
                    continue
                if self.expired(s, fr["since"]) and self.on_timeout(step, s, None):
                    continue
                break
            p = fr["pending"]
            if p is None:
                if "receipt" in s and self.cond(s["receipt"], step):
                    self.accept(step, s, {"request": None, "ok": True, "receipt": True})
                    continue
                self.dispatch(step, s)
                break
            what, val = self.evidence(p)
            if what == "result":
                test_crash(self.job, "before-accept")
                if not val.get("ok") and val.get("code") in s.get("unknown_codes", ()):
                    if self.on_unknown(step, s, p, "退出碼 %r：未交付終局結果" % val["code"]):
                        continue
                    break
                self.accept(step, s, val)
                continue
            if what == "readd":
                item = self.item(s, p)
                try:
                    self.add_item(item, p, fresh_check=True)
                except Halt as h:
                    if h.kind != "unknown":
                        raise
                    if self.on_unknown(step, s, p, str(h)):
                        continue
                    break
                p["state"] = "queued"
                break
            if what == "unknown":
                if self.on_unknown(step, s, p, val):
                    continue
                break
            if self.expired(s, p["since"]) and self.on_timeout(step, s, p):
                continue
            break
        return fr["phase"] == "ended"


def run_pass(jd, tock_round=None, node=None):
    """直譯器的一圈（spec §5）。回 "exit"＝這個 run 該結束（工作已結束）；None＝等下一個 tock。錯誤記 error.json、不前進。"""
    job = Job(jd, node)
    rnd = node_round(job.node, tock_round)
    try:
        t, rev = job.load_table()
        st, fr = job.read_frame()
        if st == N:
            fr = new_frame(t, rev, rnd)
            job.save(fr)
        if fr["phase"] == "ended":
            if not t.get("options", {}).get("restart_on_end"):
                return "exit"
            close(job, fr, reopen=(t, rev, rnd))
            st, fr = job.read_frame()
        it = Interp(job, t, fr, rnd)
        if fr["phase"] == "running" and fr["table"] != rev:
            it.halt("version", "工作進行中 steps.json 被改了（%s→%s）；執行中的工作固定版本，改回原表或 close 重來"
                    % (fr["table"], rev))
        if fr["phase"] == "running":
            try:
                it.advance()
            except Halt as h:
                it.halt(h.kind, str(h))
        fr["seen"], fr["tock"] = rnd, tock_round      # tock：這圈是哪個 tock 叫醒的（啟動時那圈是 None）
        job.save(fr)
        return "exit" if fr["phase"] == "ended" else None
    except Unknown as e:
        job.error(e.kind, "pass", e, rnd, tock_round)
    except OSError as e:
        job.error("os", "pass", repr(e), rnd, tock_round)
    return None


def close(job, fr, reopen=None):
    """結案：清 results/，框架標 closed（reopen＝(表, 版本, 回合) 時直接換成新工作）。只准已結束的工作。"""
    if fr["phase"] != "ended":
        raise Unknown("工作還沒結束（phase %s），不能 close" % fr["phase"], kind="close")
    shutil.rmtree(job.a(job.p("results")), ignore_errors=True)
    nf = new_frame(*reopen) if reopen else dict(fr, closed=True)
    nf["rev"] = fr["rev"]
    job.save(nf)


def main_run(jd):
    from aos7_taskside import task_env, wait_tock
    job = Job(jd)
    sweep_tmp(job.a(jd))
    results = job.a(job.p("results"))
    try:
        steps = os.listdir(results)
    except OSError:
        steps = []
    for step in steps:
        sweep_tmp(os.path.join(results, step))
    me = task_env()
    if run_pass(jd) == "exit":
        return 0
    last = 0
    while True:
        last = wait_tock(me["task"], last)
        if run_pass(jd, last) == "exit":
            return 0


class Parser(argparse.ArgumentParser):
    def error(self, message):
        message = " ".join(message.splitlines())
        self.exit(2, "aos7-step: 參數不合：%s。例：aos7-step check jobs/demo/steps.json\n" % message)


def main(argv=None):
    ap = Parser(prog="aos7-step", description="step 任務包：步驟表直譯器")
    ap.add_argument("cmd", choices=("run", "check", "status", "resume", "close"))
    ap.add_argument("path", help="工作資料夾（check 給 steps.json）")
    ap.add_argument("--resend", action="store_true", help="resume 時用同一個 request、新 attempt 重派（人負責）")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return main_run(a.path)
    if a.cmd == "check":
        st, t = fact(a.path)
        issues = check(t) if st == OK else [{"level": "error", "step": None, "rule": "struct", "why": str(t)}]
        print(json.dumps(issues, ensure_ascii=False, indent=1))
        return 1 if errors_of(issues) else 0
    job = Job(a.path)
    try:
        st, fr = job.read_frame()
        if st == N:
            print("沒有 frame.json（工作還沒開始）")
            return 1
        if a.cmd == "status":
            err = fact(job.a(job.p("error.json")))[1]
            print(json.dumps({k: fr.get(k) for k in ("job", "inst", "pc", "phase", "end", "halt", "pending", "seen")}
                             | {"error": err}, ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "close":
            close(job, fr)
            return 0
        if fr["phase"] != "halted":   # resume
            print("沒有停住（phase %s）" % fr["phase"])
            return 1
        fr.update(phase="running", halt=None, since=node_round(job.node, fr.get("seen")))
        if a.resend:
            req = fr["pending"]["request"] if fr.get("pending") else request_of(fr, fr["pc"])
            fr["resends"].pop(req, None)
        if fr.get("pending"):
            if a.resend:
                fr["pending"] = None          # 下一圈同一個 request、新 attempt
            else:
                fr["pending"]["since"] = fr["since"]
        job.save(fr)
        return 0
    except Unknown as e:
        print("aos7-step: 不確定：%s。證據留著，確認檔案後照原樣再跑" % " ".join(str(e).splitlines()), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
