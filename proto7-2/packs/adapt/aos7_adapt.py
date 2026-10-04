"""adapt 任務包：鏈宣告、檢查器、確定性鏈、來源鐘、三態暫存器（spec 見同資料夾的 spec.md；契約卡在 README.md）。

    aos7-adapt run <宣告>      普通 keep 任務（max_live 1）：每收到自己的 tock 重算一次，寫 in/<sense>.json
    aos7-adapt check <宣告>    檢查器：欄位、步種類、need、時間值；不執行，有錯退出碼 1
    aos7-adapt status <宣告>   人手：印暫存器摘要（cwd＝node）

只用核心公開的檔：自己槽的 tock.json（等回合）、birth.json（掛載表，經工具包 resolver）、來源 node 的 round.json（來源鐘）、
自己 node 的 round.json（框架起點）。核心不知道這個包。判定都走 aos7_fs.fact 的三態（N 不存在／OK／其餘不知道）。
"""
import argparse
import decimal
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))           # proto7-2/
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib")]
from aos7_fs import BAD, N, OK, ROUND_CLOSED, ROUND_OPEN, fact, is_int, now, read_round, write_json  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
AS_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
DECL_KEYS = {"v", "sense", "src", "src_clock", "max_age", "patience", "stall", "steps", "need", "note"}
REQUIRED = ("sense", "src", "src_clock", "steps", "need")
STEP_KINDS = ("select", "scale", "threshold")
CMP_KEYS = ("ge", "gt", "le", "lt")
META = ("v", "seq", "round", "at")          # 來源物件的信封欄，不算 omitted
FRAME_KEYS = ("sense", "chain", "since", "my_round", "last_ok_my_round", "last_clock", "last_seq", "stall_rounds",
              "skipped", "resetting", "void_sha", "prev_state", "cur", "last")



def round_half_up(x, nd):
    """四捨五入到小數 nd 位（平手遠離零；Python 內建 round 是平手取偶數，不合 spec §2）。"""
    q = decimal.Decimal(1).scaleb(-nd)
    return float(decimal.Decimal(repr(x)).quantize(q, rounding=decimal.ROUND_HALF_UP))

def sha(obj):
    """正規 JSON（鍵排序）的 sha256：依據版本與鏈版本都用它。"""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def is_num(v):
    """有限的數字（JSON 的 true／false 不算）。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def space_path_ok(p):
    """空間路徑：非空字串、相對、不含 `..` 段（跟核心掛載的字面檢查同一套）。"""
    if not isinstance(p, str) or not p or os.path.isabs(p):
        return False
    return ".." not in p.replace(os.sep, "/").split("/")


# ---------- 檢查器（spec §6） ----------

def check(d):
    """回 [{"level", "where", "rule", "why"}]；不執行、不拋例外（壞型別也回診斷）。"""
    out = []

    def err(where, rule, why):
        out.append({"level": "error", "where": where, "rule": rule, "why": why})

    if not isinstance(d, dict):
        err(None, "struct", "宣告要是 JSON 物件")
        return out
    for k in sorted(set(d) - DECL_KEYS):
        err(k, "struct", "不認得的欄 %r" % k)
    for k in REQUIRED:
        if k not in d:
            err(k, "struct", "缺必填欄 %s" % k)
    if "v" in d and d["v"] != 1:
        err("v", "struct", "v 只准 1")
    if "sense" in d and not (isinstance(d["sense"], str) and NAME_RE.match(d["sense"])):
        err("sense", "type", "sense 要是英數、_、-，最多 32 字")
    for k in ("src", "src_clock"):
        if k in d and not space_path_ok(d[k]):
            err(k, "type", "%s 要是空間路徑（相對空間根、不含 ..）" % k)
    if space_path_ok(d.get("src_clock")) and os.path.basename(d["src_clock"]) != "round.json":
        err("src_clock", "clock", "src_clock 要指到來源 node 的 .aos/round.json（v1 只認來源回合這一條鐘）")
    for k in ("max_age", "patience", "stall"):
        if k in d and d[k] is not None and not (is_int(d[k]) and d[k] >= 0):
            err(k, "time", "%s 要是非負整數（回合數）或 null；不收秒、毫秒、期限" % k)
    produced = []
    steps = d.get("steps")
    if "steps" in d and not (isinstance(steps, list) and steps):
        err("steps", "type", "steps 要是非空陣列")
        steps = []
    for i, s in enumerate(steps or []):
        where = "steps[%d]" % i
        kinds = [k for k in STEP_KINDS if isinstance(s, dict) and k in s]
        if not isinstance(s, dict) or len(kinds) != 1 or set(s) - {kinds[0], "note"}:
            err(where, "step", "每步恰一個種類鍵（%s），可另帶 note" % "／".join(STEP_KINDS))
            continue
        k, a = kinds[0], s[kinds[0]]
        if k == "select":
            if i != 0:
                err(where, "step", "select 只能是第一步、只能一個（v1 一條鏈一個來源值）")
            if not (isinstance(a, str) and a and all(a.split("."))):
                err(where, "type", "select 要是點分路徑字串（每段非空）")
            continue
        if i == 0:
            err(where, "step", "第一步要是 select")
        if not isinstance(a, dict):
            err(where, "type", "%s 的參數要是物件" % k)
            continue
        if k == "scale":
            bad = set(a) - {"mul", "q", "round", "as"}
            if bad:
                err(where, "struct", "scale 不認得的欄 %s" % sorted(bad))
            if not is_num(a.get("mul")):
                err(where, "type", "scale.mul 要是數字")
            if not (is_num(a.get("q")) and a["q"] >= 0):
                err(where, "type", "scale.q（取整誤差界）要是非負數字")
            if "round" in a and not (is_int(a["round"]) and 0 <= a["round"] <= 12):
                err(where, "type", "scale.round 要是 0～12 的整數（小數位數）")
            elif "round" in a and is_num(a.get("q")) and a["q"] < 0.5 * 10 ** -a["round"] * (1 - 1e-9):
                err(where, "err", "scale.q=%r 蓋不住取整到小數 %d 位的誤差（至少 %g）"
                    % (a["q"], a["round"], 0.5 * 10 ** -a["round"]))
        else:   # threshold
            cmp = [c for c in CMP_KEYS if c in a]
            bad = set(a) - set(CMP_KEYS) - {"as"}
            if bad:
                err(where, "struct", "threshold 不認得的欄 %s" % sorted(bad))
            if len(cmp) != 1 or not is_num(a.get(cmp[0] if cmp else "")):
                err(where, "type", "threshold 要恰一個比較鍵（%s）且值是數字" % "／".join(CMP_KEYS))
            if "as" not in a:
                err(where, "struct", "threshold 要有 as（產出欄名）")
        if "as" in a:
            if not (isinstance(a["as"], str) and AS_RE.match(a["as"])):
                err(where, "type", "as 要是英數與 _，最多 32 字")
            elif a["as"] in produced:
                err(where, "struct", "as %r 重複" % a["as"])
            else:
                produced.append(a["as"])
    need = d.get("need")
    if "need" in d:
        if not (isinstance(need, list) and need and all(isinstance(n, str) for n in need)):
            err("need", "type", "need 要是非空字串陣列")
        else:
            for n in need:
                if n not in produced:
                    err("need", "need", "need 欄 %r 不在鏈的產出裡（產出：%s）" % (n, produced))
    return out


# ---------- 鏈（spec §2） ----------

def pick(doc, path):
    """點分路徑取值；走不到回 (False, None)。"""
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def leaves(obj, prefix=""):
    """物件的葉路徑（點分）。"""
    if isinstance(obj, dict) and obj:
        out = []
        for k, v in obj.items():
            out += leaves(v, prefix + k if not prefix else prefix + "." + k)
        return out
    return [prefix] if prefix else []


def omitted_of(doc, selected):
    """來源物件裡沒被選到的葉路徑（扣掉信封欄 v／seq／round／at）。"""
    keep = [p for p in leaves({k: v for k, v in doc.items() if k not in META})
            if not (p == selected or p.startswith(selected + "."))]
    return sorted(keep)


def band(op, t, lo, hi):
    """區間 [lo, hi] 對門檻 t：整段成立 True、整段不成立 False、跨過 None。"""
    if op == "ge":
        return True if lo >= t else (False if hi < t else None)
    if op == "gt":
        return True if lo > t else (False if hi <= t else None)
    if op == "le":
        return True if hi <= t else (False if lo > t else None)
    return True if hi < t else (False if lo >= t else None)   # lt


def run_chain(steps, doc):
    """跑一次鏈。回 {"out", "err", "trace", "omitted", "fail", "band"}：fail＝走 unknown 分支的原因（select_missing／not_number），
    band＝落在誤差帶的產出欄。從固定的 doc 重算，不讀上一跳。"""
    out, errs, trace, x, e = {}, {}, [], None, 0.0
    selected, fail, inband = "", None, []
    for s in steps:
        k = next(k for k in STEP_KINDS if k in s)
        a = s[k]
        if k == "select":
            selected = a
            found, x = pick(doc, a)
            if not found:
                fail = "select_missing"
                break
            e = 0.0
            trace.append({"step": "select", "x": x, "err": e})
            continue
        if not is_num(x):
            fail = "not_number"
            break
        if k == "scale":
            x = x * a["mul"]
            if "round" in a:
                x = round_half_up(x, a["round"])
            e = abs(a["mul"]) * e + a["q"]
            trace.append({"step": "scale", "x": x, "err": e})
            if "as" in a:
                out[a["as"]], errs[a["as"]] = x, e
        else:
            op = next(c for c in CMP_KEYS if c in a)
            v = band(op, a[op], x - e, x + e)
            trace.append({"step": "threshold", op: a[op], "as": a["as"], "v": v})
            out[a["as"]] = v
            if v is None:
                inband.append(a["as"])
    return {"out": out, "err": errs, "trace": trace, "fail": fail, "band": inband,
            "omitted": omitted_of(doc, selected) if selected and isinstance(doc, dict) else []}


# ---------- 鐘（spec §3） ----------

def completed_tock(path):
    """round.json 的 completed_tock：closed 取 round、open 取 round−1；其餘（不存在、讀不到、壞）＝None 不知道。
    （抄 budget 包同名函式；兩包共用時再搬進工具包。）"""
    st, r, _ = read_round(path)
    if st == ROUND_CLOSED:
        return r["round"]
    if st == ROUND_OPEN:
        return r["round"] - 1
    return None


# ---------- 框架與判定（spec §4、§5） ----------

def new_frame(sense, chain, my_round):
    """新框架：耐性起點 since 在建立時就寫（A4-03）。"""
    return {"v": 1, "sense": sense, "chain": chain, "since": my_round, "my_round": None, "last_ok_my_round": my_round,
            "last_clock": None, "last_seq": None, "stall_rounds": 0, "skipped": 0, "resetting": False,
            "void_sha": None, "prev_state": None, "cur": None, "last": None}


def frame_ok(fr):
    return (isinstance(fr, dict) and fr.get("v") == 1 and all(k in fr for k in FRAME_KEYS)
            and is_int(fr["skipped"]) and is_int(fr["stall_rounds"]) and isinstance(fr["sense"], str))


def read_source(path):
    """來源檔三態：("ok", 物件)｜("missing", None)｜("unknown", (原因碼, 說明))。缺 round 也算不知道。"""
    if path is None:
        return "unknown", ("not_mounted", "來源路徑沒有掛載蓋到")
    st, v = fact(path)
    if st == N:
        return "missing", None
    if st != OK:
        return "unknown", ("src_bad" if st == BAD else "src_unreadable", str(v))
    if not isinstance(v, dict) or not is_int(v.get("round")):
        return "unknown", ("src_bad", "來源不是物件或缺整數 round")
    return "ok", v


def evaluate(decl, fr, my_round, ct, src):
    """一圈的判定（純函式，spec §4.2）。decl 已過檢查器；fr 是框架（不改原物件）；ct 是來源 completed_tock 或 None；
    src 是 read_source 的結果。回 (新框架, 暫存器)。"""
    fr = json.loads(json.dumps(fr))
    fresh = fr["my_round"] is None or my_round > fr["my_round"]
    # 來源狀態
    reset = False
    if ct is not None:
        lc = fr["last_clock"]
        if lc is not None and ct < lc:
            reset = True
        elif lc is None or ct > lc:
            fr["stall_rounds"] = 0
        elif fresh:
            fr["stall_rounds"] += 1
        fr["last_clock"] = ct
    sst, doc = src
    basis = None
    if sst == "ok":
        basis = {"src": decl["src"], "sha": sha(doc), "seq": doc.get("seq") if is_int(doc.get("seq")) else None,
                 "src_round": doc["round"]}
        if fr["cur"] and doc["round"] < fr["cur"]["basis"]["src_round"]:
            reset = True
        s = basis["seq"]
        if s is not None:
            if fr["last_seq"] is not None and s > fr["last_seq"] + 1:
                fr["skipped"] += s - fr["last_seq"] - 1
            fr["last_seq"] = s
    if reset:
        fr["resetting"], fr["stall_rounds"] = True, 0
        if fr["cur"]:
            fr["void_sha"] = fr["cur"]["basis"]["sha"]
        fr["cur"] = None
        if fr["last"]:
            fr["last"]["void"] = True

    ch = run_chain(decl["steps"], doc) if sst == "ok" else None
    reg = {"value": None, "err": None, "basis": basis, "trace": ch["trace"] if ch else [],
           "omitted": ch["omitted"] if ch else [], "held": 0, "detail": None}

    def age_of(b):
        return None if ct is None or b is None else max(0, ct - b["src_round"])

    def gate(b):
        """讀到一份依據之後還要過的效期／停太久；回 unknown 的原因或 None。"""
        if is_int(decl.get("max_age")) and age_of(b) > decl["max_age"]:
            return "expired"
        if is_int(decl.get("stall")) and fr["stall_rounds"] > decl["stall"]:
            return "stalled"
        return None

    if sst == "missing":
        state, why = "absent", "src_missing"
    elif sst != "ok" or ch["fail"] or ct is None:
        # 耐性分支（spec §4.2 第 3 列）
        if sst != "ok":
            why, reg["detail"] = doc
        else:
            why = ch["fail"] or "clock_unknown"
        held = my_round - fr["last_ok_my_round"]
        patience = decl.get("patience") or 0
        cur = fr["cur"]
        if fr["prev_state"] == "ok" and cur and held <= patience and not fr["resetting"] \
                and (ct is None or gate(cur["basis"]) is None):
            state = "ok"
            reg.update(value=cur["value"], err=cur["err"], basis=cur["basis"], trace=cur["trace"],
                       omitted=cur["omitted"], held=held)
        else:
            state = "unknown"
            if ct is not None and cur and gate(cur["basis"]):
                why = gate(cur["basis"])
    else:
        fr["last_ok_my_round"] = my_round
        if doc["round"] > ct + 1 or basis["sha"] == fr["void_sha"]:
            state, why = "unknown", "void_basis"
        elif gate(basis):
            state, why = "unknown", gate(basis)
        elif ch["band"]:
            state, why = "unknown", "within_error_band"
        elif any(ch["out"].get(n) is None for n in decl["need"]):
            state, why = "unknown", "need_missing"
        else:
            state, why = "ok", None
            reg.update(value=ch["out"], err=ch["err"])
            fr["cur"] = {"value": ch["out"], "err": ch["err"], "basis": basis, "trace": ch["trace"],
                         "omitted": ch["omitted"]}
            fr["last"] = {"value": ch["out"], "err": ch["err"], "basis": basis, "my_round": my_round}
            fr["resetting"] = False
    if ct is None:
        src_state = "unknown"
    elif reset or fr["resetting"]:
        src_state = "reset"          # 偵測到的那一圈（就算同圈採用了新依據）一直報到採用一份新依據為止
    else:
        src_state = "advancing" if fr["stall_rounds"] == 0 else "stalled"
    fr["prev_state"], fr["my_round"] = state, my_round
    reg = {"v": 1, "sense": decl["sense"], "state": state, "value": reg["value"], "err": reg["err"],
           "basis": reg["basis"], "chain": {"sha": fr["chain"][:16]}, "trace": reg["trace"], "omitted": reg["omitted"],
           "age_src_rounds": age_of(reg["basis"]), "src_state": src_state, "stall_rounds": fr["stall_rounds"],
           "skipped": fr["skipped"], "why": why, "detail": reg["detail"], "held": reg["held"], "last": fr["last"],
           "my_round": my_round, "at": now()}
    return fr, reg


def unknown_register(sense, why, detail, my_round, last, chain=None):
    """宣告壞、鏈被改、框架壞：只寫一份 unknown 暫存器（框架不動）。"""
    return {"v": 1, "sense": sense, "state": "unknown", "value": None, "err": None, "basis": None,
            "chain": {"sha": (chain or "")[:16] or None}, "trace": [], "omitted": [], "age_src_rounds": None,
            "src_state": None, "stall_rounds": None, "skipped": None, "why": why, "detail": detail, "held": 0,
            "last": last, "my_round": my_round, "at": now()}


# ---------- 任務（spec §4） ----------

class Adapter:
    """一個 adapt 任務：node（cwd）、宣告路徑（相對 node）、槽、掛載解析器。"""

    def __init__(self, decl_path, node, taskdir, resolve):
        self.decl_path = decl_path if os.path.isabs(decl_path) else os.path.join(node, decl_path)
        self.node, self.taskdir, self.resolve = node, taskdir, resolve
        self.frame_path = os.path.join(taskdir, "state.json")

    def log(self, why):
        print("aos7-adapt: %s" % why, file=sys.stderr, flush=True)

    def reg_path(self, sense):
        return os.path.join(self.node, "in", sense + ".json")

    def load_decl(self):
        """回 (宣告, 雜湊, 問題)；問題 None＝可用。"""
        st, d = fact(self.decl_path)
        if st != OK:
            return None, None, "宣告讀不到或不是 JSON：%s" % (d or "不存在")
        errs = [i for i in check(d) if i["level"] == "error"]
        if errs:
            return None, None, "宣告檢查沒過：" + "；".join("%s %s：%s" % (e["rule"], e["where"], e["why"])
                                                         for e in errs[:5])
        return d, sha(d), None

    def own_round(self):
        st, r, _ = read_round(os.path.join(self.node, ".aos", "round.json"))
        return r["round"] if st in (ROUND_OPEN, ROUND_CLOSED) else None

    def init(self):
        """啟動：框架不存在就建（since＝現在的回合）。宣告壞、回合不知道就留給第一圈。"""
        d, ch, issue = self.load_decl()
        rnd = self.own_round()
        if issue or rnd is None:
            return
        if fact(self.frame_path)[0] == N:
            write_json(self.frame_path, new_frame(d["sense"], ch, rnd))

    def write_reg(self, sense, reg):
        try:
            write_json(self.reg_path(sense), reg)
        except OSError as e:
            self.log("暫存器寫不進去：%r" % e)

    def pass_(self, my_round):
        """一圈（spec §4）：讀宣告、框架、來源鐘、來源檔 → 判 → 先寫框架、再寫暫存器。"""
        d, ch, issue = self.load_decl()
        fst, fr = fact(self.frame_path)
        if fst == OK and not frame_ok(fr):
            fst = "bad"
        if fst not in (OK, N):
            sense = d["sense"] if d else None
            if sense:
                old = fact(self.reg_path(sense))[1]
                last = old.get("last") if isinstance(old, dict) else None
                self.write_reg(sense, unknown_register(sense, "frame_bad", "槽 state.json 讀不到或壞；等人刪掉重來",
                                                       my_round, last, ch))
            self.log("state.json 讀不到或壞（%s），不前進" % fst)
            return
        if issue:
            self.log(issue)
            if fst == OK:
                self.write_reg(fr["sense"], unknown_register(fr["sense"], "decl_bad", issue, my_round, fr["last"],
                                                             fr["chain"]))
            return
        if fst == N:
            fr = new_frame(d["sense"], ch, my_round)
        elif fr["chain"] != ch:
            self.write_reg(fr["sense"], unknown_register(
                fr["sense"], "chain_changed", "鏈宣告在工作中被改（%s→%s）；改回原宣告，或停任務、刪槽 state.json 換鏈"
                % (fr["chain"][:16], ch[:16]), my_round, fr["last"], fr["chain"]))
            return
        clock = self.resolve(d["src_clock"])
        ct = completed_tock(clock) if clock else None
        fr, reg = evaluate(d, fr, my_round, ct, read_source(self.resolve(d["src"])))
        if clock is None and reg["why"] == "clock_unknown":
            reg["why"] = "clock_not_mounted"
        try:
            write_json(self.frame_path, fr)
        except OSError as e:
            self.log("state.json 寫不進去：%r；這圈不寫暫存器" % e)
            return
        self.write_reg(d["sense"], reg)


def main_run(decl_path):
    from aos7_taskside import resolver, task_env, wait_tock
    me = task_env()
    ad = Adapter(decl_path, me["node"], me["task"], resolver(me["task"]))
    ad.init()
    last = 0
    while True:
        last = wait_tock(me["task"], last, poll=0.01)
        ad.pass_(last)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-adapt", description="adapt 任務包：最新值轉接")
    ap.add_argument("cmd", choices=("run", "check", "status"))
    ap.add_argument("decl", help="鏈宣告（相對 node，例如 adapt/temp.json）")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return main_run(a.decl)
    st, d = fact(a.decl)
    if a.cmd == "check":
        issues = check(d) if st == OK else [{"level": "error", "where": None, "rule": "struct",
                                             "why": "讀不到或不是 JSON：%s" % (d or "不存在")}]
        print(json.dumps(issues, ensure_ascii=False, indent=1))
        return 1 if issues else 0
    if st != OK or not isinstance(d, dict) or not isinstance(d.get("sense"), str):
        print("aos7-adapt: 宣告讀不到", file=sys.stderr)
        return 3
    rst, r = fact(os.path.join("in", d["sense"] + ".json"))
    if rst != OK or not isinstance(r, dict):
        print("aos7-adapt: 暫存器 in/%s.json %s" % (d["sense"], "還沒有" if rst == N else "讀不到"), file=sys.stderr)
        return 1 if rst == N else 3
    print(json.dumps({k: r.get(k) for k in ("sense", "state", "value", "why", "age_src_rounds", "src_state",
                                            "skipped", "held", "my_round")}
                     | {"basis": r.get("basis")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
