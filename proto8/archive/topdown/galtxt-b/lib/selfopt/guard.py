"""guard - 自我優化工具包的共用零件（不是工具、沒有 _entry；同資料夾的工具用 realpath 找到這裡再 import，照 proto8/lib/aos/aos_ws.py 的做法）。

邊界由程式擋、不靠 prompt（使用者 10-25「自我優化」；任務 b2_selfopt 第 1 項）：
- 沙盒＝$AOS_WS＝訓練場（train/init 出的那個資料夾：tree/、set/、runs/、rounds/、changes/、selfopt/）。讀可以讀整個訓練場；寫只限
  tree/<node>/（這次被優化的節點自己的資料夾，解開捷徑後還在裡面），而且不碰凍結的東西：路徑上任何一層 _metainfo 有 "frozen": true，
  或落在 FROZEN（量尺、評分、人評、工具包自己）裡，或路徑有一段叫 tests／test_*——一律拒寫並在 session 記一筆 attempted_violation。
- 這次是誰、目標、預算放在 session.json（host 開題時寫；工具從環境變數 SELFOPT_SESSION 找到它）。腦只能給工具參數、改不了環境變數，
  所以 node、預算、白名單都不是腦說了算。
- 預算：每叫一次工具 counter_calls +1（> max_calls 就拒）；腦用量 counter_tokens（host 問腦、run_self_test 真腦跑樹都加進來，> max_tokens 就拒）。
錯：Fail(代號, 原因)；tool_main 印「工具名: 代號 原因」到 stderr 與 stdout、退 1（proto8/lib 契約第 3 條）。
"""
import fnmatch, json, os, shutil, sys
from datetime import datetime, timezone

FROZEN = ("lib/lint", "lib/selfopt", "judge", "check", "human", "train")     # tree/ 相對：量尺（lint、critic、judge）、檢核、人評、訓練迴圈、工具包自己
DEFAULT_EDITABLE = ["system.txt", "*.json"]                                  # 白名單（相對節點）；session.editable 可改
NEVER_EDIT = ["_metainfo", "_entry", "*.py", "fsm.json", "loop.json", ".env", "hard_cases.jsonl", "versions/*", "*/_metainfo", "*/_entry"]
VERSIONS = "versions"


class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def jload(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_text(path, text):                     # N-05：先寫暫存再改名、留住原檔權限
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def read_meta(d):
    m = jload(os.path.join(d, "_metainfo"), {})
    return m if isinstance(m, dict) else {}


def write_meta(d, meta):
    """_metainfo 寫回：一個 key 一行（跟 repo 裡手寫的形狀接近，diff 好讀）。"""
    body = ",\n ".join("%s: %s" % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False)) for k, v in meta.items())
    write_text(os.path.join(d, "_metainfo"), "{" + body + "}\n")


class Ctx:
    """一次工具呼叫的環境：訓練場、session、這次的節點。"""

    def __init__(self, tool):
        self.tool = tool
        ws = os.environ.get("AOS_WS")
        if not ws or not os.path.isdir(ws):
            raise Fail("WsMissing", "沒設 AOS_WS 或它不是資料夾（要是訓練場）")
        self.field = os.path.realpath(ws)
        sp = os.environ.get("SELFOPT_SESSION")
        if not sp:
            raise Fail("SessionMissing", "沒設 SELFOPT_SESSION（工具包要由 selfopt host 叫）")
        self.session_path = sp if os.path.isabs(sp) else os.path.join(self.field, sp)
        self.session = jload(self.session_path)
        if not isinstance(self.session, dict) or not isinstance(self.session.get("node"), str):
            raise Fail("SessionBad", "%s 讀不了或沒有 node" % self.session_path)
        self.tree = os.path.realpath(os.path.join(self.field, "tree"))
        if not os.path.isfile(os.path.join(self.tree, "_entry")):
            raise Fail("TreeMissing", "訓練場沒有 tree/（先 train/init）")
        self.node = self.session["node"].strip("/")
        self.node_dir = os.path.join(self.tree, self.node)          # 不 realpath：節點本身是捷徑時，寫入檢查會發現它指到外面
        if not os.path.isdir(self.node_dir):
            raise Fail("NodeMissing", "tree/%s 不是資料夾" % self.node)

    # ── session 記帳 ──
    def save(self):
        write_json(self.session_path, self.session)

    def charge_call(self):
        s = self.session
        s["counter_calls"] = s.get("counter_calls", 0) + 1
        s.setdefault("calls", []).append({"tool": self.tool, "called_at": now()})
        if s["counter_calls"] > s.get("max_calls", 12):
            s["calls"][-1]["refused"] = "BudgetBad"
            self.save()
            raise Fail("BudgetBad", "工具呼叫次數用完（max_calls %d）" % s.get("max_calls", 12))
        self.save()

    def charge_tokens(self, n, kind):
        s = self.session
        s["counter_tokens"] = s.get("counter_tokens", 0) + n
        s["counter_tokens_" + kind] = s.get("counter_tokens_" + kind, 0) + n
        self.save()

    def tokens_left(self):
        return self.session.get("max_tokens", 0) - self.session.get("counter_tokens", 0)

    def violation(self, code, path, reason):
        self.session.setdefault("attempted_violations", []).append(
            {"tool": self.tool, "path": path, "code": code, "reason": reason, "attempted_at": now()})
        self.save()
        raise Fail(code, reason)

    # ── 寫入檢查 ──
    def frozen_reason(self, real):
        """real＝解開捷徑後的絕對路徑；回凍結的理由或 None。"""
        rel = os.path.relpath(real, self.tree)
        if rel.startswith(".."):
            return "不在 tree/ 裡"
        parts = [] if rel == "." else rel.split(os.sep)
        for p in parts:
            if p == "tests" or p.startswith("test_"):
                return "測試檔不准改"
        for f in FROZEN:
            if rel == f or rel.startswith(f + os.sep):
                return "%s 是凍結的（量尺／評分／人評／工具包）" % f
        d = real if os.path.isdir(real) else os.path.dirname(real)
        while True:
            if read_meta(d).get("frozen") is True:
                return "%s 的 _metainfo 標 frozen" % (os.path.relpath(d, self.tree))
            if os.path.realpath(d) == self.tree or len(d) <= len(self.tree):
                return None
            d = os.path.dirname(d)

    def resolve_write(self, rel, whitelist=True):
        """節點相對路徑 → 可寫的絕對路徑；越界、凍結、不在白名單都拒（記 attempted_violation）。"""
        if not isinstance(rel, str) or not rel or os.path.isabs(rel):
            raise Fail("ArgumentsBad", "path 要是節點資料夾裡的相對路徑")
        target = os.path.join(self.node_dir, rel)
        real = os.path.join(os.path.realpath(os.path.dirname(target)), os.path.basename(target))
        if os.path.islink(target):
            real = os.path.realpath(target)
        home = os.path.realpath(self.node_dir)
        why = self.frozen_reason(real)
        if why:
            self.violation("FrozenBad", rel, "%s：%s" % (rel, why))
        if not (real == home or real.startswith(home + os.sep)) or home != os.path.join(self.tree, self.node):
            self.violation("ScopeBad", rel, "%s 解開後是 %s，不在自己的資料夾 tree/%s 裡" % (rel, os.path.relpath(real, self.field), self.node))
        norm = os.path.relpath(real, home)
        if whitelist:
            allow = self.session.get("editable") or DEFAULT_EDITABLE
            if any(fnmatch.fnmatch(norm, p) or fnmatch.fnmatch(os.path.basename(norm), p) for p in NEVER_EDIT) or \
                    not any(fnmatch.fnmatch(norm, p) for p in allow):
                self.violation("WhitelistBad", rel, "%s 不在可改的白名單（%s；永遠不改 %s）" % (norm, "、".join(allow), "、".join(NEVER_EDIT)))
        return real, norm

    def save_version(self, real, norm):
        """寫前存：versions/selfopt_<session>/<相對路徑>（這個 session 第一次碰這個檔才存＝存的是改前的原樣；新建的檔記 created）。"""
        vdir = os.path.join(os.path.realpath(self.node_dir), VERSIONS, "selfopt_" + self.session["session"])
        os.makedirs(vdir, exist_ok=True)
        if not os.path.exists(os.path.join(os.path.realpath(self.node_dir), VERSIONS, "_metainfo")):
            write_json(os.path.join(os.path.realpath(self.node_dir), VERSIONS, "_metainfo"),
                       {"summary": "前版留檔（kind data、runtime 不讀）：selfopt_<session>/ 是自我優化改檔前的原樣", "kind": "data"})
        man = read_meta(vdir) or {"summary": "自我優化 session %s 改檔前的原樣（只存被改到的檔）" % self.session["session"],
                                  "kind": "data", "files": {}}
        if norm in man["files"]:
            return os.path.relpath(vdir, self.field)
        if os.path.exists(real):
            dst = os.path.join(vdir, norm)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(real, dst)
            man["files"][norm] = "saved"
        else:
            man["files"][norm] = "created"
        write_meta(vdir, man)
        return os.path.relpath(vdir, self.field)

    def record_edit(self, norm, kind, **extra):
        self.session.setdefault("edits", []).append(dict({"path": norm, "kind": kind, "edited_at": now()}, **extra))
        self.save()

    # ── _metainfo.lifecycle.history ──
    def append_history(self, entry):
        """寫回節點 _metainfo.lifecycle.history 一筆（工具包自己的記帳、不經白名單；節點凍結就不寫）。回寫了沒。"""
        home = os.path.realpath(self.node_dir)
        if self.frozen_reason(home) or home != os.path.join(self.tree, self.node):
            return False
        meta = read_meta(home)
        lc = meta.setdefault("lifecycle", {"stage": "pure" if meta.get("uses_llm") is False else "agent"})
        lc.setdefault("history", []).append(entry)
        write_meta(home, meta)
        return True


def history_entry(session, node_dir, why, expect=None, by="note"):
    """lifecycle.history 的一筆（note 工具與 host 收工補記共用）。"""
    stage = (read_meta(node_dir).get("lifecycle") or {}).get("stage")
    e = {"round": session.get("round"), "from": stage, "to": stage, "move": "selfopt", "goal": session.get("goal"), "why": why}
    if expect:
        e["expect"] = expect
    e["changed"] = sorted({x["path"] for x in session.get("edits") or []})
    e["self_tests"] = [{k: t.get(k) for k in ("question", "brain", "total", "counter_tokens")} for t in session.get("self_tests") or []]
    e.update({"by": by, "session": session.get("session"), "noted_at": now()})
    return e


def tool_main(name, fn):
    """讀 stdin（空＝{}）→ fn(args, ctx) 回 dict → stdout 一行 JSON。錯照 lib 契約：stderr＋stdout 一行、退 1。"""
    sys.dont_write_bytecode = True
    try:
        raw = sys.stdin.read()
        try:
            args = json.loads(raw) if raw.strip() else {}
        except ValueError as e:
            raise Fail("ArgumentsBad", "stdin 不是 JSON：%s" % e)
        if not isinstance(args, dict):
            raise Fail("ArgumentsBad", "參數要是 JSON 物件")
        ctx = Ctx(name)
        ctx.charge_call()
        out = fn(args, ctx)
    except Fail as e:
        line = "%s: %s %s" % (name, e.code, str(e.reason).replace("\n", " "))
        print(line, file=sys.stderr)
        print(line)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False))
