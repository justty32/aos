"""author 任務包（LLM 作者第一刀）：需求、工具卡、候選三層驗證與確定性編譯、答案驗收、close（spec 見 spec.md；
契約卡在 README.md）。發布與恢復在 aos7_author_pub.py。

    aos7-author register <request.json>
    aos7-author propose <rid> --candidate <file> [--auto]
    aos7-author publish <rid> [--sha S] [--resend]
    aos7-author answer <rid> [--sha S]
    aos7-author status|close <rid>

命令都在 node 目錄（cwd）下跑。第一刀不接模型：候選由 --candidate 注入（第二刀換 gateway、介面不變）。
帳只在 `<node>/author/`：共用鎖 `author.lock`，每需求 `req/<rid>/` 固定五檔
（request／candidate／verdict／intent／receipt），版本以 candidate_sha 為鍵放在檔內，不隨候選或回合增檔。
退出碼：0 成功、2 invalid、3 conflict、4 unknown、5 full。
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = os.path.dirname(HERE)
TOP = os.path.dirname(PACKS)                                   # proto7-2/
sys.path[:0] = [os.path.join(TOP, "lib"), os.path.join(PACKS, "step")]
from aos7_fs import N, OK, Unknown, fact, locked, sweep_tmp, test_point, write_json  # noqa: E402
import aos7_step  # noqa: E402  （只讀：用它的檢查器與 table_rev，不改 step）
from aos7_tick import check_item  # noqa: E402  （只讀：核心任務項契約）

STEP_BIN = os.path.join(PACKS, "step", "bin", "aos7-step")
CARDS = os.path.join(HERE, "toolcards", "csv.json")
CARDS_REL = "toolcards/csv.json"
RID_RE = re.compile(r"^[A-Za-z0-9_]{1,23}$")                  # job=<rid>_<sha8> ≤32 字，合 step 命名
NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REQ_RE = re.compile(r"^\$\{req:([A-Za-z0-9_]{1,32})\}$")
PARAM_RE = re.compile(r"^\{([A-Za-z0-9_]+)\}$")
MAX_VERSIONS = 2                 # 同 rid 已發布版本上限（隊長代定 ④；翻案改這裡）
MAX_CANDIDATE = 64 * 1024
MAX_STEPS = 16
LOCK_TIMEOUT = 5.0
WRITE_SUFFIXES = ("", ".tmp")    # CSV 工具先寫同目錄 <dst>.tmp 再 rename：兩個都要在 out 裡（卡的 writes 含 .tmp）
RESERVED = {"steps.json", "frame.json", "error.json", "results", "out"}   # step 的控制檔／目錄：輸入不得同名
FILES = ("request.json", "candidate.json", "verdict.json", "intent.json", "receipt.json")
CAND_KEYS = {"v", "mode", "intent", "start", "steps", "ends"}
STEP_KEYS = {"id", "tool", "args", "ok", "fail"}
ATTR_KEYS = {"finite", "idempotent", "argv", "run", "expect", "patience", "on_unknown", "on_timeout",
             "max_resends", "unknown_codes", "receipt", "wake", "options", "max_live", "enabled"}
CODES = {None: 0, "invalid": 2, "conflict": 3, "unknown": 4, "full": 5}


class Refuse(Exception):
    """一次拒絕：why 是 invalid／conflict／unknown／full，msg 給人看，extra 併進回值。"""

    def __init__(self, why, msg, **extra):
        super().__init__(msg)
        self.why, self.msg, self.extra = why, msg, extra


def result(ok, why=None, **kw):
    return dict(kw, ok=ok, why=why)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def canon(obj):
    """確定性 JSON（排序鍵、固定分隔、UTF-8）：算 payload／manifest 雜湊用。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def strict_json(raw):
    """嚴格讀 UTF-8 JSON：重複鍵、NaN／Infinity 都拒（ValueError）。不做任何修復。"""
    def pairs(ps):
        d = {}
        for k, v in ps:
            if k in d:
                raise ValueError("重複鍵 %r" % k)
            d[k] = v
        return d

    def const(c):
        raise ValueError("不收 %s" % c)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=const)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def write_bytes(path, data):
    """原子寫原文位元組（暫存檔名同 aos7_fs：`.<名>.tmp.<pid>`，寫者死後 sweep_tmp 認得）。"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def read_bytes(path):
    """回位元組；不存在回 None；其他讀不到丟 Refuse unknown。"""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        if isinstance(e, (FileNotFoundError, NotADirectoryError)):
            return None
        raise Refuse("unknown", "%s 讀不到：%r" % (path, e))


# ---------- 作者夾 ----------

class Node:
    """一個 node 的作者帳：`<node>/author/`。"""

    def __init__(self, node=None):
        self.node = os.path.realpath(node or os.getcwd())
        self.dir = os.path.join(self.node, "author")

    def lock(self):
        return locked(os.path.join(self.dir, "author"), LOCK_TIMEOUT)      # 共用鎖：author/author.lock

    def rdir(self, rid):
        return os.path.join(self.dir, "req", rid)

    def path(self, rid, name):
        return os.path.join(self.rdir(rid), name)

    def jd(self, job):
        return os.path.join(self.node, "jobs", job)

    def load(self, rid, name, default=None):
        """讀固定檔：不存在回 default；讀不到／壞／型別不對＝unknown（不當空帳）。"""
        st, v = fact(self.path(rid, name))
        if st == N:
            return default
        if st == OK and isinstance(v, dict) and v.get("v") == 1:
            return v
        raise Refuse("unknown", "%s/%s %s" % (rid, name, v if st != OK else "格式不對"))

    def save(self, rid, name, doc):
        write_json(self.path(rid, name), doc)

    def docs(self, rid):
        """一次讀齊四份帳（request 另讀）。"""
        return (self.load(rid, "candidate.json", {"v": 1, "active": None, "versions": {}}),
                self.load(rid, "verdict.json", {"v": 1, "versions": {}}),
                self.load(rid, "intent.json", {"v": 1, "versions": {}}),
                self.load(rid, "receipt.json"))

    def request(self, rid):
        raw = read_bytes(self.path(rid, "request.json"))
        if raw is None:
            raise Refuse("invalid", "需求 %s 沒登記（先 register）" % rid)
        return strict_json(raw), sha256(raw)


def check_rid(rid):
    if not (isinstance(rid, str) and RID_RE.match(rid)):
        raise Refuse("invalid", "rid 只能英數與 _、1～23 字，拿到 %r" % (rid,))


def published(receipt):
    """已有發布回條的版本：{sha: 回條}。"""
    return dict((receipt or {}).get("versions") or {})


# ---------- 工具卡 ----------

def load_toolcards(path=CARDS):
    """讀工具卡，回 {"tools": {...}, "sha256": 卡原文雜湊, "path": 相對包的路徑, "checker": ...}。壞卡丟 Refuse invalid。"""
    raw = read_bytes(path)
    if raw is None:
        raise Refuse("invalid", "工具卡不存在：%s" % path)
    try:
        doc = strict_json(raw)
    except ValueError as e:
        raise Refuse("invalid", "工具卡不是 JSON：%s" % e)
    if not (isinstance(doc, dict) and doc.get("v") == 1 and isinstance(doc.get("tools"), dict)):
        raise Refuse("invalid", "工具卡要是 {\"v\": 1, \"tools\": {...}}")
    for tid, c in doc["tools"].items():
        if not (isinstance(c, dict) and isinstance(c.get("argv"), list) and isinstance(c.get("params"), dict)
                and isinstance(c.get("finite"), bool) and isinstance(c.get("idempotent"), bool)
                and isinstance(c.get("artifacts"), list) and isinstance(c.get("script"), dict)):
            raise Refuse("invalid", "工具卡 %s 缺欄或型別不對" % tid)
    rel = os.path.relpath(path, HERE) if os.path.isabs(path) else path
    return {"tools": doc["tools"], "sha256": sha256(raw), "path": rel, "checker": doc.get("answer_checker")}


# ---------- 需求（A1-1） ----------

def _rel_ok(p):
    if not (isinstance(p, str) and p and "\0" not in p and not os.path.isabs(p)):
        return False
    parts = p.split("/")
    return all(x not in ("", ".", "..") for x in parts)


def check_request(req, node, cards):
    """需求的欄位與輸入檔：回 issues（空＝過）。輸入路徑相對 node，要是一般檔（不跟 symlink）、雜湊相符。"""
    out = []
    if not isinstance(req, dict):
        return ["需求要是物件"]
    if set(req) != {"v", "rid", "goal", "inputs", "tools"}:
        return ["需求欄位要恰為 v、rid、goal、inputs、tools，拿到 %s" % sorted(req)]
    if req["v"] != 1 or not is_int(req["v"]):
        out.append("v 要是 1")
    if not (isinstance(req["rid"], str) and RID_RE.match(req["rid"])):
        out.append("rid 只能英數與 _、1～23 字（不收路徑分隔、NUL、..）")
    if not (isinstance(req["goal"], str) and req["goal"].strip() and len(req["goal"]) <= 500 and "\0" not in req["goal"]):
        out.append("goal 要是非空字串（≤500 字、無 NUL）")
    tools = req["tools"]
    if not (isinstance(tools, list) and tools and all(isinstance(t, str) for t in tools) and len(set(tools)) == len(tools)):
        out.append("tools 要是互異字串的非空陣列")
    else:
        out += ["不認得的工具 %r（不在工具卡）" % t for t in tools if t not in cards["tools"]]
    ins = req["inputs"]
    if not (isinstance(ins, list) and 1 <= len(ins) <= 8):
        return out + ["inputs 要是 1～8 項的陣列"]
    names = set()
    for k, i in enumerate(ins):
        if not (isinstance(i, dict) and set(i) == {"path", "sha256"}):
            out.append("inputs[%d] 要恰為 {path, sha256}" % k)
            continue
        if not _rel_ok(i["path"]):
            out.append("inputs[%d].path 要是相對 node 的路徑（不收絕對、..、空段、NUL）" % k)
            continue
        if not (isinstance(i["sha256"], str) and SHA_RE.match(i["sha256"])):
            out.append("inputs[%d].sha256 要是 64 位小寫十六進位" % k)
            continue
        base = os.path.basename(i["path"])
        if base in names:
            out.append("inputs 檔名重複 %r" % base)
        names.add(base)
        have = input_sha(node, i["path"])
        if have != i["sha256"]:
            out.append("inputs[%d] %s 雜湊不符（%s）" % (k, i["path"], have or "不是一般檔或讀不到"))
    return out


def input_sha(node, rel):
    """輸入檔（相對 node）的 SHA-256；不是一般檔、經 symlink、逃出 node、讀不到回 None。"""
    p = os.path.join(node, rel)
    if os.path.realpath(p) != os.path.normpath(p):
        return None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as f:
        if not os.path.isfile(p):
            return None
        return sha256(f.read())


def register_request(node, request_path):
    """登記需求：嚴格讀、驗欄與輸入雜湊，保存原文到 author/req/<rid>/request.json。同 bytes＝dup；異＝conflict，不覆寫。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        raw = read_bytes(request_path)
        if raw is None:
            raise Refuse("invalid", "需求檔不存在：%s" % request_path)
        try:
            req = strict_json(raw)
        except ValueError as e:
            raise Refuse("invalid", "需求不是嚴格 JSON：%s" % e)
        issues = check_request(req, nd.node, load_toolcards())
        if issues:
            raise Refuse("invalid", "需求不合", issues=issues)
        rid, rsha = req["rid"], sha256(raw)
        with nd.lock():
            have = read_bytes(nd.path(rid, "request.json"))
            if have is not None:
                if have != raw:
                    raise Refuse("conflict", "rid %s 已登記不同內容（%s）" % (rid, sha256(have)), rid=rid)
                return result(True, rid=rid, request_sha=rsha, dup=True)
            write_bytes(nd.path(rid, "request.json"), raw)
        return result(True, rid=rid, request_sha=rsha, dup=False)
    except Refuse as r:
        return result(False, r.why, error=r.msg, **r.extra)
    except Unknown as e:
        return result(False, "unknown", error=str(e))


# ---------- 候選：第一層（A1-3／A1-4） ----------

def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def out_path_ok(v, node, job):
    """寫路徑要在這一版的 out：`${out}/<相對段>`，不收 ..、絕對、空段、其他展開；已存在的段經 symlink 逃出 out 也拒。"""
    if not (isinstance(v, str) and v.startswith("${out}/")):
        return False
    rel = v[len("${out}/"):]
    if "${" in rel or not _rel_ok(rel):
        return False
    base = os.path.join(node, "jobs", job, "out")
    return all(os.path.realpath(os.path.join(base, rel + suf)).startswith(base + os.sep) for suf in WRITE_SUFFIXES)


def out_links(nd, job):
    """這一版 out/ 裡的 symlink（發布前再查一次：寫路徑與工具暫存檔都不能經 symlink 逃出）。"""
    jd = nd.jd(job)
    found = [p for p in (os.path.join(nd.node, "jobs"), jd, os.path.join(jd, "out")) if os.path.islink(p)]
    for d, dirs, files in os.walk(os.path.join(jd, "out")):
        found += [os.path.join(d, n) for n in dirs + files if os.path.islink(os.path.join(d, n))]
    return found


def layer1(raw, request, cards, node, job):
    """格式與展開：回 (issues, 候選)。issues 每項 {rule, where, why}；rule 見 spec §4。"""
    issues = []

    def add(rule, where, why):
        issues.append({"rule": rule, "where": where, "why": why})
    if len(raw) > MAX_CANDIDATE:
        add("size", None, "候選超過 %d bytes" % MAX_CANDIDATE)
        return issues, None
    try:
        cand = strict_json(raw)
    except (ValueError, UnicodeDecodeError) as e:
        add("json", None, "不是嚴格 JSON：%s（不自動修復）" % e)
        return issues, None
    if not isinstance(cand, dict):
        add("schema", None, "候選要是物件")
        return issues, None
    if any("\0" in s for s in _strings(cand)):
        add("nul", None, "字串不能有 NUL")
    for k in set(cand) - CAND_KEYS:
        add("attr" if k in ATTR_KEYS else "schema", None, "頂層不認得的欄 %r（屬性只由工具卡決定）" % k)
    for k in CAND_KEYS - set(cand):
        add("schema", None, "頂層缺 %r" % k)
    if issues:
        return issues, cand
    if not (is_int(cand["v"]) and cand["v"] == 1):
        add("schema", None, "v 要是 1")
    if not isinstance(cand["start"], str):
        add("schema", None, "start 要是步名字串")
    if cand["mode"] != "keep":
        add("mode", None, "mode 只能是 keep（作者工作是 keep＋max_live 1），拿到 %r" % (cand["mode"],))
    if not (isinstance(cand["intent"], str) and len(cand["intent"]) <= 500):
        add("schema", None, "intent 要是 ≤500 字的字串")
    ends = cand["ends"]
    if not (isinstance(ends, dict) and ends and all(isinstance(k, str) and NAME_RE.match(k) and v in ("ok", "failed")
                                                    for k, v in ends.items())):
        add("schema", None, "ends 要是 {名: \"ok\"|\"failed\"} 的非空物件")
        ends = {}
    steps = cand["steps"]
    if not (isinstance(steps, list) and 1 <= len(steps) <= MAX_STEPS and all(isinstance(s, dict) for s in steps)):
        add("schema", None, "steps 要是 1～%d 個物件" % MAX_STEPS)
        return issues, cand
    ids, deps, tool_of = [], [], {}
    in_names = {os.path.basename(i["path"]) for i in request["inputs"]}
    for k, s in enumerate(steps):
        where = s.get("id") if isinstance(s.get("id"), str) else "steps[%d]" % k
        for f in set(s) - STEP_KEYS:
            add("attr" if f in ATTR_KEYS else "schema", where,
                "步不認得的欄 %r%s" % (f, "（finite／idempotent／argv 只由工具卡決定，候選宣告無效）" if f in ATTR_KEYS else ""))
        for f in STEP_KEYS - set(s):
            add("schema", where, "步缺 %r" % f)
        if not STEP_KEYS <= set(s):
            continue
        sid = s["id"]
        if not (isinstance(sid, str) and NAME_RE.match(sid)) or sid in ends or sid in ids:
            add("schema", where, "步 id 要是英數與 _（≤32 字）、互異、不與 ends 同名")
            continue
        ids.append(sid)
        bad = [f for f in ("ok", "fail", "tool") if not isinstance(s[f], str)]
        for f in bad:
            add("schema", sid, "%s 要是字串" % f)
        if bad:
            continue
        tool = s["tool"]
        if tool not in cards["tools"] or tool not in request["tools"]:
            add("tool", sid, "工具 %r 不在工具卡或需求的 tools 白名單" % (tool,))
            continue
        tool_of[sid] = tool
        params = cards["tools"][tool]["params"]
        args = s["args"]
        if not isinstance(args, dict):
            add("param", sid, "args 要是物件")
            continue
        for a in set(args) - set(params):
            add("param", sid, "多餘參數 %r" % a)
        for a in set(params) - set(args):
            add("param", sid, "缺參數 %r" % a)
        for a in sorted(set(args) & set(params)):
            spec, v = params[a], args[a]
            if spec.get("type") == "string" and not isinstance(v, str):
                add("param", sid, "參數 %s 要是字串，拿到 %r" % (a, v))
                continue
            role = spec.get("role")
            if role == "write" and not out_path_ok(v, node, job):
                add("path", sid, "參數 %s 寫路徑 %r 不在這一版的 ${out} 裡" % (a, v))
                continue
            if role == "read" and not (v.startswith("${out}/") and _rel_ok(v[7:]) and "${" not in v[7:]):
                add("path", sid, "參數 %s 讀路徑 %r 要在 ${out} 裡" % (a, v))
                continue
            if role == "input" and not (v.startswith("${job}/") and v[7:] in in_names):
                add("path", sid, "參數 %s 要是 ${job}/<需求的輸入檔名>，拿到 %r" % (a, v))
                continue
            if role == "req":
                m = REQ_RE.match(v)
                if not m:
                    add("param", sid, "參數 %s 要是 ${req:<步>}，拿到 %r" % (a, v))
                else:
                    deps.append((sid, m.group(1), spec.get("tool")))
                continue
            if "value" in spec and v != spec["value"]:
                add("param", sid, "參數 %s 要是 %r，拿到 %r" % (a, spec["value"], v))
    if issues:
        return issues, cand
    _graph(cand, ids, ends, deps, tool_of, add)
    return issues, cand


def _graph(cand, ids, ends, deps, tool_of, add):
    """依賴：跳轉目標存在、無環、每步可達且都走得到終點；每個 ${req:X} 在所有可達路徑上 X 都已成功採用。"""
    by = {s["id"]: s for s in cand["steps"]}
    if cand["start"] not in by:
        add("graph", None, "start %r 不是步" % (cand["start"],))
        return
    bad = [(sid, f) for sid, s in by.items() for f in ("ok", "fail") if s[f] not in by and s[f] not in ends]
    for sid, f in bad:
        add("graph", sid, "%s 目標 %r 不存在" % (f, by[sid][f]))
    if bad:
        return
    color, order = {}, []

    def dfs(u):
        color[u] = 1
        for f in ("ok", "fail"):
            w = by[u][f]
            if w in by:
                if color.get(w) == 1:
                    add("dep", u, "跳轉成環（%s → %s）" % (u, w))
                    return False
                if w not in color and not dfs(w):
                    return False
        color[u] = 2
        order.append(u)
        return True
    if not dfs(cand["start"]):
        return
    for sid in by:
        if sid not in color:
            add("graph", sid, "走不到的步")
    order.reverse()                      # 拓撲序
    must = {cand["start"]: set()}
    for u in order:
        for f in ("ok", "fail"):
            w = by[u][f]
            if w in by:
                got = must[u] | ({u} if f == "ok" else set())
                must[w] = got if w not in must else (must[w] & got)
    for sid, target, tool in deps:
        if sid not in must:
            continue
        if target not in by or (tool and tool_of.get(target) != tool):
            add("dep", sid, "${req:%s} 要指向工具 %s 的步" % (target, tool))
        elif target not in must[sid]:
            add("dep", sid, "${req:%s} 在某條可達路徑上還沒成功採用" % target)


# ---------- 第二層：套工具卡編譯（A1-4） ----------

def job_of(rid, csha):
    return "%s_%s" % (rid, csha[:8])


def task_of(rid, csha, job, payload_sha=None):
    au = {"owner": "author", "rid": rid, "candidate_sha": csha}
    if payload_sha:
        au["payload_sha"] = payload_sha
    return {"name": "author-" + job, "mode": "keep", "max_live": 1,
            "argv": ["python3", STEP_BIN, "run", "jobs/" + job], "x": {"author": au}}


def compile_steps(cand, cards, job):
    """候選＋卡 → steps.json（位元組確定）。屬性（finite／idempotent／expect）只取卡。"""
    steps = {}
    for s in cand["steps"]:
        card = cards["tools"][s["tool"]]
        argv = []
        for a in card["argv"]:
            m = PARAM_RE.match(a)
            argv.append(s["args"][m.group(1)] if m else a)
        steps[s["id"]] = {"run": argv, "finite": card["finite"], "idempotent": card["idempotent"],
                          "expect": list(card["artifacts"]), "ok": s["ok"], "fail": s["fail"]}
    for e, v in cand["ends"].items():
        steps[e] = {"end": v}
    table = {"job": job, "start": cand["start"], "options": {"wake": False, "restart_on_end": False}, "steps": steps}
    return table, (json.dumps(table, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


def job_files(nd, request, cards, cand, steps_raw):
    """版本固定來源：{檔名: 位元組}。腳本從 step 範例原樣取、對卡的雜湊；輸入從 node 取、對需求的雜湊。不符丟 Refuse invalid。"""
    files = {}
    for tool in sorted({s["tool"] for s in cand["steps"]}):
        sc = cards["tools"][tool]["script"]
        raw = read_bytes(os.path.join(PACKS, sc["src"]))
        if raw is None or sha256(raw) != sc["sha256"]:
            raise Refuse("invalid", "工具 %s 的腳本 %s 與卡的雜湊不符" % (tool, sc["src"]))
        files[sc["as"]] = raw
    for i in request["inputs"]:
        base = os.path.basename(i["path"])
        raw = read_bytes(os.path.join(nd.node, i["path"])) if input_sha(nd.node, i["path"]) else None
        if raw is None or sha256(raw) != i["sha256"]:
            raise Refuse("invalid", "輸入 %s 與需求的雜湊不符" % i["path"])
        if base in files or base in RESERVED or base.startswith("."):
            raise Refuse("invalid", "輸入檔名 %s 與腳本或 step 控制檔撞名（或以 . 開頭）" % base)
        files[base] = raw
    files["steps.json"] = steps_raw
    return files


def manifest_of(rid, request_sha, csha, job, cards, file_shas):
    return {"v": 1, "rid": rid, "request_sha": request_sha, "candidate_sha": csha, "job": job,
            "files": dict(file_shas), "toolcards": {"path": cards["path"], "sha256": cards["sha256"]},
            "task": task_of(rid, csha, job)}


def payload_of(manifest):
    return sha256(canon(manifest))


def candidate_raw(entry):
    if entry.get("raw_b64") is not None:
        return base64.b64decode(entry["raw_b64"])
    return entry["raw"].encode("utf-8")


def validate_compile(nd, rid, csha, cdoc=None, vdoc=None, idoc=None, receipt=None):
    """三層驗證的前兩層＋確定性編譯（在作者鎖內呼叫）：過了才寫 jobs/<job>/；回 verdict 項。"""
    request, rsha = nd.request(rid)
    if cdoc is None:
        cdoc, vdoc, idoc, receipt = nd.docs(rid)
    entry = cdoc["versions"].get(csha)
    if entry is None:
        raise Refuse("invalid", "候選 %s 沒存" % csha[:12])
    raw = candidate_raw(entry)
    cards = load_toolcards()
    job = job_of(rid, csha)
    v = {"candidate_sha": csha, "request_sha": rsha, "job": job, "ok": False, "validated": False,
         "payload_sha": None, "issues": [], "manifest": None, "steps_sha256": None, "answer": "pending"}
    issues, cand = layer1(raw, request, cards, nd.node, job)
    if not issues:
        table, steps_raw = compile_steps(cand, cards, job)
        issues = [{"rule": "step", "where": e["step"], "why": "%s：%s" % (e["rule"], e["why"])}
                  for e in aos7_step.errors_of(aos7_step.check(table))]
        try:
            check_item(task_of(rid, csha, job, "0" * 64))
        except ValueError as e:
            issues.append({"rule": "task", "where": None, "why": str(e)})
    if issues:
        v["issues"] = issues
        return v
    try:
        files = job_files(nd, request, cards, cand, steps_raw)
    except Refuse as r:
        v["issues"] = [{"rule": "source", "where": None, "why": r.msg}]
        return v
    # 短雜湊撞名：同 job 名但完整 sha 不同的版本＝conflict，絕不覆蓋
    for doc in (vdoc["versions"], idoc["versions"], published(receipt)):
        for other, e in doc.items():
            if other != csha and e.get("job") == job:
                raise Refuse("conflict", "job %s 已屬於候選 %s（前 8 碼撞名）" % (job, other[:12]))
    shas = {n: sha256(b) for n, b in files.items()}
    manifest = manifest_of(rid, rsha, csha, job, cards, shas)
    write_job(nd, job, files)
    v.update(ok=True, validated=True, payload_sha=payload_of(manifest), manifest=manifest,
             steps_sha256=shas["steps.json"])
    return v


def write_job(nd, job, files):
    """寫一版的固定來源：已有同雜湊重用、異雜湊 conflict；steps.json 最後寫。frame／results／out 不碰。"""
    jd = nd.jd(job)
    jobs = os.path.join(nd.node, "jobs")
    if os.path.lexists(jobs) and os.path.realpath(jobs) != jobs:
        raise Refuse("invalid", "jobs/ 是 symlink，不寫")
    if os.path.lexists(jd) and (os.path.islink(jd) or not os.path.isdir(jd)):
        raise Refuse("conflict", "jobs/%s 已存在且不是資料夾" % job)
    for name in sorted(files, key=lambda n: n == "steps.json"):
        p = os.path.join(jd, name)
        have = read_bytes(p)
        if have is None:
            write_bytes(p, files[name])
        elif have != files[name]:
            raise Refuse("conflict", "jobs/%s/%s 已有不同內容，不覆蓋" % (job, name))


def recompute_payload(nd, rid, v):
    """發布前重算：從磁碟上的 jobs/<job>/ 固定來源、目前的工具卡與需求重組 manifest。讀不到的檔記成 None。"""
    _, rsha = nd.request(rid)
    cards = load_toolcards()
    shas = {}
    for name in (v.get("manifest") or {}).get("files", {}):
        raw = read_bytes(os.path.join(nd.jd(v["job"]), name))
        shas[name] = sha256(raw) if raw is not None else None
    return payload_of(manifest_of(rid, rsha, v["candidate_sha"], v["job"], cards, shas))


# ---------- propose（A1-3） ----------

def propose(node, rid, *, candidate_path, auto=False):
    """收一份候選（第一刀由檔案注入）：保存原文、前兩層驗證、過了編譯成 jobs/<job>/。預設不發布；auto 才接發布。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        raw = read_bytes(candidate_path)
        if raw is None:
            raise Refuse("invalid", "候選檔不存在：%s" % candidate_path)
        csha = sha256(raw)
        with nd.lock():
            v = _propose_locked(nd, rid, csha, raw)
        out = result(v["ok"], None if v["ok"] else "invalid", rid=rid, candidate_sha=csha, job=v["job"] if v["ok"] else None,
                     payload_sha=v["payload_sha"], issues=v["issues"])
        if auto and v["ok"]:
            import aos7_author_pub
            out["publish"] = aos7_author_pub.publish(nd, rid, candidate_sha=csha)
            out["ok"], out["why"] = out["publish"]["ok"], out["publish"]["why"]
        return out
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg, **r.extra)
    except Unknown as e:
        return result(False, "unknown", rid=rid, error=str(e))


def _propose_locked(nd, rid, csha, raw):
    nd.request(rid)
    cdoc, vdoc, idoc, receipt = nd.docs(rid)
    if receipt and receipt.get("closed"):
        raise Refuse("conflict", "需求 %s 已結案" % rid)
    pub = published(receipt)
    if csha in vdoc["versions"] and csha in cdoc["versions"]:
        return vdoc["versions"][csha]                       # 同一份候選重送：回原審查，不增檔
    for sha in idoc["versions"]:
        if sha not in pub:
            raise Refuse("unknown", "版本 %s 的發布結果不明；先 publish %s（或查明後 --resend）" % (sha[:12], rid))
    if len(pub) >= MAX_VERSIONS:
        raise Refuse("full", "需求 %s 已發布 %d 版（上限 %d）；先 close" % (rid, len(pub), MAX_VERSIONS))
    old = cdoc.get("active")
    if old and old not in pub and old != csha:              # 每 rid 同時一個待審候選：換掉舊的待審（沒登記過）
        if old[:8] == csha[:8]:
            raise Refuse("conflict", "候選 %s 與待審的 %s 前 8 碼撞名" % (csha[:12], old[:12]))
        vdoc["versions"].pop(old, None)
        cdoc["versions"].pop(old, None)
        nd.save(rid, "verdict.json", vdoc)
        # 舊待審沒登記過（無 intent、無回條）：它的 job 是作者自己寫的未發布來源，連同「編譯完、verdict 未存就被殺」的殘留一起清
        shutil.rmtree(nd.jd(job_of(rid, old)), ignore_errors=True)
    entry = {"size": len(raw)}
    try:
        entry["raw"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        entry["raw_b64"] = base64.b64encode(raw).decode("ascii")
    cdoc["versions"][csha] = entry
    cdoc["active"] = csha
    nd.save(rid, "candidate.json", cdoc)
    v = validate_compile(nd, rid, csha, cdoc, vdoc, idoc, receipt)
    vdoc["versions"][csha] = v
    nd.save(rid, "verdict.json", vdoc)
    return v


# ---------- 答案驗收（A1-7）與 close（A1-8） ----------

def answer(node, rid, *, candidate_sha=None):
    """step 結束、close 之前：核 steps 雜湊＝verdict，跑工具卡指定的獨立檢查器，結果記進 verdict 的 answer。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        with nd.lock():
            request, _ = nd.request(rid)
            cdoc, vdoc, idoc, receipt = nd.docs(rid)
            sha = candidate_sha or cdoc.get("active")
            v = vdoc["versions"].get(sha)
            if not v or sha not in published(receipt):
                raise Refuse("conflict", "版本 %s 沒有發布回條，不驗答案" % (sha or "-")[:12])
            cards = load_toolcards()
            issues = []
            steps = read_bytes(os.path.join(nd.jd(v["job"]), "steps.json"))
            if steps is None or sha256(steps) != v["steps_sha256"]:
                issues.append("steps.json 雜湊不等於 verdict")
            checker = os.path.join(HERE, cards["checker"])
            src = os.path.join("jobs", v["job"], "data.csv")          # 工具實際讀的快照，先核 manifest 雜湊
            snap = read_bytes(os.path.join(nd.node, src))
            if snap is None or sha256(snap) != v["manifest"]["files"].get("data.csv"):
                issues.append("jobs/%s/data.csv 與 manifest 雜湊不符" % v["job"])
            p = subprocess.run([sys.executable, checker, "jobs/" + v["job"], src], cwd=nd.node,
                               capture_output=True, text=True, timeout=60)
            try:
                got = json.loads(p.stdout)
            except ValueError:
                got = {"ok": False, "issues": ["檢查器輸出不是 JSON：%s" % p.stderr.strip()[-300:]]}
            ok = bool(got.get("ok")) and p.returncode == 0 and not issues
            v["answer"] = {"ok": ok, "issues": issues + list(got.get("issues") or []),
                           "checker_sha256": sha256(read_bytes(checker) or b"")}
            nd.save(rid, "verdict.json", vdoc)
        return result(ok, None if ok else "invalid", rid=rid, candidate_sha=sha, answer=v["answer"])
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg, **r.extra)
    except Unknown as e:
        return result(False, "unknown", rid=rid, error=str(e))


def close_request(node, rid):
    """人明示結案：所有版本有回條、step 已 close、答案已驗 → 回條記 hashes／證據／答案／closed，再清 candidate／verdict／intent。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        with nd.lock():
            nd.request(rid)
            cdoc, vdoc, idoc, receipt = nd.docs(rid)
            if not (receipt and receipt.get("closed")):
                _close_check(nd, rid, cdoc, vdoc, idoc, receipt)
                for sha, rc in receipt["versions"].items():
                    v = vdoc["versions"][sha]
                    rc.update(closed=True, answer=v["answer"], steps_sha256=v["steps_sha256"],
                              files=v["manifest"]["files"], toolcards=v["manifest"]["toolcards"])
                receipt["closed"] = True
                nd.save(rid, "receipt.json", receipt)
                test_point("author:close-after-receipt")
            for name in ("candidate.json", "verdict.json", "intent.json"):
                try:
                    os.unlink(nd.path(rid, name))
                except FileNotFoundError:
                    pass
                test_point("author:close-after-" + name.split(".")[0])
            sweep_tmp(nd.rdir(rid))
            sweep_tmp(nd.dir)
        return result(True, rid=rid, versions=sorted(receipt["versions"]))
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg, **r.extra)
    except (Unknown, OSError) as e:
        return result(False, "unknown", rid=rid, error=str(e))


def _close_check(nd, rid, cdoc, vdoc, idoc, receipt):
    pub = published(receipt)
    for sha in idoc["versions"]:
        if sha not in pub:
            raise Refuse("unknown", "版本 %s 的發布結果不明，不結案、不刪" % sha[:12])
    if not pub:
        raise Refuse("conflict", "需求 %s 沒有已發布的版本" % rid)
    act = cdoc.get("active")
    if act and act not in pub and (vdoc["versions"].get(act) or {"ok": True}).get("ok"):
        raise Refuse("conflict", "還有待審的合法候選 %s（先 publish 或換掉）" % act[:12])
    for sha, rc in pub.items():
        v = vdoc["versions"].get(sha)
        if not v:
            raise Refuse("unknown", "版本 %s 的 verdict 不見了" % sha[:12])
        st, fr = fact(os.path.join(nd.jd(rc["job"]), "frame.json"))
        if not (st == OK and isinstance(fr, dict) and fr.get("phase") == "ended" and fr.get("closed") is True):
            raise Refuse("conflict", "版本 %s 的 step 工作還沒 close（先 aos7-step close jobs/%s）" % (sha[:12], rc["job"]))
        if v.get("answer") == "pending":
            raise Refuse("conflict", "版本 %s 的答案還沒驗（step close 之前先 aos7-author answer）" % sha[:12])


def status(node, rid):
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        cdoc, vdoc, idoc, receipt = nd.docs(rid)
        vers = {}
        for sha in set(vdoc["versions"]) | set(idoc["versions"]) | set(published(receipt)):
            v, rc = vdoc["versions"].get(sha) or {}, published(receipt).get(sha) or {}
            vers[sha] = {"job": v.get("job") or rc.get("job"), "ok": v.get("ok", True if rc else None),
                         "issues": v.get("issues"), "intent": sha in idoc["versions"],
                         "receipt": bool(rc), "answer": v.get("answer", rc.get("answer"))}
        return result(True, rid=rid, active=cdoc.get("active"), closed=bool(receipt and receipt.get("closed")),
                      versions=vers)
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-author", description="author 任務包：CSV 固定工具作者（第一刀，假候選）")
    ap.add_argument("cmd", choices=("register", "propose", "publish", "answer", "status", "close"))
    ap.add_argument("arg", help="register 給需求檔；其餘給 rid")
    ap.add_argument("--candidate", help="propose：候選檔")
    ap.add_argument("--auto", action="store_true", help="propose：固定試驗，過了直接發布")
    ap.add_argument("--sha", help="publish／answer：指定版本（預設 active）")
    ap.add_argument("--resend", action="store_true", help="publish：結果 unknown 的版本由人負責重走首次發布")
    a = ap.parse_args(argv)
    nd = Node()
    if a.cmd == "register":
        r = register_request(nd, a.arg)
    elif a.cmd == "propose":
        if not a.candidate:
            ap.error("propose 要 --candidate")
        r = propose(nd, a.arg, candidate_path=a.candidate, auto=a.auto)
    elif a.cmd == "publish":
        import aos7_author_pub
        r = aos7_author_pub.publish(nd, a.arg, candidate_sha=a.sha, resend=a.resend)
    elif a.cmd == "answer":
        r = answer(nd, a.arg, candidate_sha=a.sha)
    elif a.cmd == "close":
        r = close_request(nd, a.arg)
    else:
        r = status(nd, a.arg)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return CODES.get(r.get("why"), 1) if not r.get("ok") or r.get("why") else 0


if __name__ == "__main__":
    sys.exit(main())
