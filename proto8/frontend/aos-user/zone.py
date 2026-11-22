# zone.py - 使用者專區的函式庫＋指令列（aos-user 的本體）：init、send、ls、show、answer、reply、ok、door、verify、tick、notify；網頁 web.py 也只呼叫這裡。
# 規劃：~/repo/aos/proto8/thinking/2026-11/13/user-zone-plan.md（段 1、段 2）。專區＝使用者的 stack，mailbox/ 是標準 aos-post 信箱。
# 「回了才消」：看＝new/→cur/；只有回信寄出成功才把信從 cur/ 搬到 done/<月>/<信名>/（原信＋reply.json）。從不呼叫會刪信的 read。
# 段 2（11-13 晚「專區第二階段可以開始了」）：tick＝收件檢查（schema、每寄件人每小時上限）→不合的搬 rejected/<信名>/＋reason.txt 並退信；
#   new/ 裡還沒通知過的信跳 notify-send；有 deadline 的題到期前 24 小時、過期各提醒一次。狀態全記在 log.jsonl（checked／rejected／notified／reminded）。
import datetime
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

PROG = "aos-user"
ZONE_VER = "user-zone/1"
DOOR_VER = "user-door/1"
KINDS = ("decide", "verify", "trial", "chore", "fyi")
FYI_STATUSES = ("DONE", "FAILED", "BLOCKED")
STANDARD = ("from", "to", "status", "title", "what", "outputs", "not_done", "decide")
KEY = re.compile(r"^[A-Za-z0-9]{1,8}$")
QID = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
MAX_QUESTIONS = 7
DEFAULT_PORT = 8766


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ---- 位置 --------------------------------------------------------------------

def zone_dir(zone=None):
    """--zone ＞ $AOS_USER_ZONE ＞ ~/.aos/user。"""
    z = zone or os.environ.get("AOS_USER_ZONE", "") or os.path.join(os.path.expanduser("~"), ".aos", "user")
    return os.path.abspath(os.path.expanduser(z))


def box(zone):
    return os.path.join(zone, "mailbox")


def need_zone(zone):
    if not os.path.isdir(os.path.join(box(zone), "new")):
        raise Fail("ZoneMissing", "no user zone at %s (run: aos-user init)" % zone)


# ---- 樣板 --------------------------------------------------------------------

DOOR = {
    "door": DOOR_VER,
    "who": "the user (a human), not an agent",
    "mailbox": "mailbox",
    "tool": "aos-user send (shell); agents without a shell: mailbox_send with box=<zone>/mailbox and status NEEDS-USER (old format, still read)",
    "schema": "schema/letter.json",
    "accept": list(KINDS),
    "rules": [
        "decide: every question has options (key + label), a recommend that is one of the keys, and a two-sentence eli5",
        "at most 7 questions in one letter",
        "verify and chore: say what to do (what) and when it counts as done (done_when)",
        "do not send progress here; progress goes to the board",
        "do not ask what you can find out yourself",
        "risk=irreversible (push, delete, sending outside) may not carry default_if_silent",
        "default_if_silent needs a deadline; it means: if no answer by then, you go on with it, and the user may undo it later",
        "deadline is a date or a local time: 2026-11-15 or 2026-11-15T18:00",
        "at most 10 letters from one sender in one hour (max_per_hour in config.json)",
        "a letter that breaks these rules is moved to rejected/ and returned to its reply_to (status FAILED, with the reason)",
    ],
    "urgent": "urgent=true only when no answer blocks everything",
    "mode": "normal",
    "answers": "a reply comes back to your reply_to with in_reply_to set; body has the 8 standard fields plus zone, answers, letter_hash, reply_id, via; check it with: aos-user verify <reply letter folder>",
}

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "user-zone/1/letter",
    "title": "a letter to the user zone (the body of an aos-post letter)",
    "type": "object",
    "required": ["zone", "kind", "from", "to", "status", "title", "what", "host"],
    "properties": {
        "zone": {"const": ZONE_VER},
        "kind": {"enum": list(KINDS)},
        "from": {"type": "string"}, "to": {"const": "user"},
        "status": {"enum": ["NEEDS-USER"] + list(FYI_STATUSES)},
        "title": {"type": "string", "minLength": 1},
        "what": {"type": "string", "minLength": 1},
        "outputs": {"type": "string"}, "not_done": {"type": "string"}, "decide": {"type": "string"},
        "done_when": {"type": "string"},
        "questions": {"type": "array", "minItems": 1, "maxItems": MAX_QUESTIONS, "items": {
            "type": "object", "required": ["id", "question", "eli5", "options", "recommend"],
            "properties": {
                "id": {"type": "string", "pattern": QID.pattern},
                "question": {"type": "string"}, "eli5": {"type": "string"},
                "options": {"type": "array", "minItems": 2, "items": {
                    "type": "object", "required": ["key", "label"],
                    "properties": {"key": {"type": "string", "pattern": KEY.pattern},
                                   "label": {"type": "string"}, "consequence": {"type": "string"}}}},
                "recommend": {"type": "string"}, "why": {"type": "string"},
                "details": {"type": "string"}, "source_path": {"type": "string"}}}},
        "risk": {"enum": ["normal", "irreversible"]},
        "urgent": {"type": "boolean"},
        "deadline": {"type": "string"},
        "default_if_silent": {"type": "string"},
        "dedupe_key": {"type": "string"},
        "host": {"type": "string"},
        "origin": {"type": "string"},
    },
}

DEFAULT_MAX_PER_HOUR = 10
DEFAULT_REMIND_HOURS = 24
CONFIG = {"port": DEFAULT_PORT, "notify": True, "quiet_hours": None, "max_per_hour": DEFAULT_MAX_PER_HOUR,
          "remind_hours": DEFAULT_REMIND_HOURS,
          "note": "aos-user tick (every minute): notify = desktop notices on/off (aos-user notify on|off); "
                  "quiet_hours = \"23:00-08:00\" or null (only urgent letters notify then); "
                  "max_per_hour = letters one sender may send per hour, more are returned; "
                  "remind_hours = remind this long before a deadline (and once more when it has passed)"}


def write_json(path, data, mode=0o644):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def init(zone):
    """建專區；已有的檔不蓋。回傳新建的東西。"""
    made = []
    for d in ("mailbox/tmp", "mailbox/new", "mailbox/cur", "done", "rejected", "drafts", "schema", "web"):
        p = os.path.join(zone, d)
        if not os.path.isdir(p):
            os.makedirs(p)
            made.append(d + "/")
    for name, data in (("door.json", DOOR), ("schema/letter.json", SCHEMA), ("config.json", CONFIG)):
        p = os.path.join(zone, name)
        if not os.path.exists(p):
            write_json(p, data)
            made.append(name)
    p = os.path.join(zone, "log.jsonl")
    if not os.path.exists(p):
        open(p, "a").close()
        made.append("log.jsonl")
    p = os.path.join(zone, "web", "token")
    if not os.path.exists(p):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, (secrets.token_hex(24) + "\n").encode())
        os.close(fd)
        made.append("web/token")
    os.chmod(os.path.join(zone, "web"), 0o700)
    return made


def log(zone, ev, **kw):
    line = dict({"at": now_iso(), "ev": ev}, **kw)
    fd = os.open(os.path.join(zone, "log.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    os.write(fd, (json.dumps(line, ensure_ascii=False) + "\n").encode())
    os.close(fd)


def read_log(zone):
    out = []
    try:
        with open(os.path.join(zone, "log.jsonl"), encoding="utf-8") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def host():
    return socket.gethostname()


# ---- 寄信（agent 用）----------------------------------------------------------

def check_letter(b):
    """照 schema 驗一封信的 body；不合＝SchemaBad。"""
    def bad(msg):
        raise Fail("SchemaBad", msg + " (see the door: aos-user door)")
    if not isinstance(b, dict):
        bad("the letter must be a JSON object")
    if b.get("zone") != ZONE_VER:
        bad("zone must be %s" % ZONE_VER)
    k = b.get("kind")
    if k not in KINDS:
        bad("kind must be one of %s" % ", ".join(KINDS))
    for f in ("from", "title", "what", "host"):
        if not isinstance(b.get(f), str) or not b[f].strip():
            bad("%s must be a non-empty string" % f)
    if "\n" in b["title"]:
        bad("title must be one line")
    if b.get("to") != "user":
        bad("to must be user")
    st = b.get("status")
    if k == "fyi":
        if st not in FYI_STATUSES:
            bad("fyi status must be one of %s" % ", ".join(FYI_STATUSES))
    elif st != "NEEDS-USER":
        bad("%s letters have status NEEDS-USER" % k)
    risk = b.get("risk", "normal")
    if risk not in ("normal", "irreversible"):
        bad("risk must be normal or irreversible")
    if "urgent" in b and not isinstance(b["urgent"], bool):
        bad("urgent must be true or false")
    for f in ("deadline", "default_if_silent", "dedupe_key", "origin", "done_when", "outputs", "not_done", "decide"):
        if f in b and not isinstance(b[f], str):
            bad("%s must be a string" % f)
    if b.get("deadline") and parse_deadline(b["deadline"]) is None:
        bad("deadline must be a date or a local time: 2026-11-15 or 2026-11-15T18:00")
    if b.get("default_if_silent"):
        if risk == "irreversible":
            bad("an irreversible letter may not have default_if_silent")
        if not b.get("deadline"):
            bad("default_if_silent needs a deadline")
    if k in ("verify", "chore") and not (b.get("done_when") or "").strip():
        bad("%s letters need done_when (when it counts as done)" % k)
    qs = b.get("questions")
    if k == "decide":
        if not isinstance(qs, list) or not qs:
            bad("decide letters need questions (a non-empty list)")
        if len(qs) > MAX_QUESTIONS:
            bad("at most %d questions in one letter (got %d)" % (MAX_QUESTIONS, len(qs)))
        ids = set()
        for i, q in enumerate(qs, 1):
            if not isinstance(q, dict):
                bad("question %d must be an object" % i)
            qid = q.get("id")
            if not isinstance(qid, str) or not QID.match(qid) or qid in ids:
                bad("question %d: id must be 1-16 letters/digits/_/-, and unique" % i)
            ids.add(qid)
            for f in ("question", "eli5"):
                if not isinstance(q.get(f), str) or not q[f].strip():
                    bad("question %s: %s must be a non-empty string" % (qid, f))
            opts = q.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                bad("question %s: options must list at least 2 choices" % qid)
            keys = []
            for o in opts:
                if not isinstance(o, dict) or not isinstance(o.get("key"), str) or not KEY.match(o["key"]) \
                        or o["key"] == "other" or not isinstance(o.get("label"), str) or not o["label"].strip():
                    bad("question %s: each option needs key (1-8 letters/digits, not 'other') and label" % qid)
                keys.append(o["key"])
            if len(set(keys)) != len(keys):
                bad("question %s: option keys must be unique" % qid)
            if q.get("recommend") not in keys:
                bad("question %s: recommend must be one of the option keys %s" % (qid, ", ".join(keys)))
    elif qs is not None:
        bad("only decide letters carry questions")


def build_letter(src, kind, title=None, sender=None, status=None):
    b = dict(src or {})
    b["zone"] = ZONE_VER
    if kind:
        b["kind"] = kind
    if title:
        b["title"] = title
    if sender:
        b["from"] = sender
    if not b.get("from"):
        st = os.environ.get("AOS_STACK", "")
        b["from"] = os.path.basename(st.rstrip("/")) if st else (os.environ.get("USER") or "?")
    b["to"] = "user"
    if status:
        b["status"] = status
    b.setdefault("status", "DONE" if b.get("kind") == "fyi" else "NEEDS-USER")
    b.setdefault("host", host())
    if not b.get("what") and b.get("kind") == "decide" and isinstance(b.get("questions"), list):
        b["what"] = "%d question(s) for the user to decide; see questions" % len(b["questions"])
    if b.get("kind") == "decide":
        b.setdefault("decide", "see questions (aos-user show)")
    for f in ("outputs", "not_done", "decide"):
        b.setdefault(f, "none")
    return b


def post(args, body, env=None):
    exe = shutil.which("aos-post")
    if not exe:
        raise Fail("ToolMissing", "aos-post is not on PATH")
    p = subprocess.run([exe] + args, input=json.dumps(body, ensure_ascii=False), capture_output=True,
                       text=True, env=env, timeout=30)
    if p.returncode != 0:
        line = (p.stderr.strip().splitlines() or ["aos-post failed"])[-1]
        m = re.match(r"^aos-post: error: (\S+) (.*)$", line)
        raise Fail(m.group(1), m.group(2)) if m else Fail("PostFailed", line)
    return p.stdout.strip()


def send(zone, body, reply_to=None):
    """agent 寄一封進專區：驗格式 → aos-post send --reply-to。回傳信名。"""
    check_letter(body)
    need_zone(zone)
    if not reply_to:
        st = os.environ.get("AOS_STACK", "")
        reply_to = os.path.join(st, "mailbox") if st else None
    if not reply_to and body["kind"] != "fyi":
        raise Fail("ArgumentsBad", "no place for the answer: give --reply-to MAILBOX (or set $AOS_STACK)")
    args = ["send"]
    if reply_to:
        args += ["--reply-to", os.path.abspath(os.path.expanduser(reply_to))]
    return post(args + [box(zone)], body)


# ---- 讀信 --------------------------------------------------------------------

def _scan(zone, where):
    d = os.path.join(box(zone), where)
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        if n.startswith("."):
            continue
        lt = load(os.path.join(d, n, "letter.json"))
        out.append(Letter(zone, where, n, lt))
    return out


class Letter:
    def __init__(self, zone, where, name, letter):
        self.zone, self.where, self.name, self.letter = zone, where, name, letter
        self.bad = not isinstance(letter, dict)
        b = letter.get("body") if isinstance(letter, dict) else None
        self.body = b if isinstance(b, dict) else {"what": b}
        self.new = where == "new"
        self.fmt = "zone" if self.body.get("zone") == ZONE_VER else "old"
        self.kind = self.body.get("kind") if self.fmt == "zone" and self.body.get("kind") in KINDS else (
            "decide" if (self.body.get("status") == "NEEDS-USER") else "fyi")
        self.urgent = self.body.get("urgent") is True
        self.sent_at = (letter or {}).get("sent_at") or ""

    @property
    def path(self):
        return os.path.join(box(self.zone), self.where, self.name)

    def questions(self):
        qs = self.body.get("questions")
        return qs if self.fmt == "zone" and isinstance(qs, list) else []

    def reply_box(self):
        r = (self.letter or {}).get("reply_to")
        if not isinstance(r, str) or not r:
            return None
        return r if os.path.isabs(r) else os.path.normpath(os.path.join(box(self.zone), r))

    def group(self):
        k = self.body.get("dedupe_key")
        return ("k", k) if isinstance(k, str) and k else ("n", self.name)

    def row(self, num, same):
        b = self.body
        return {"n": num, "letter": self.name, "where": self.where, "format": self.fmt, "kind": self.kind,
                "from": b.get("from"), "title": b.get("title"), "questions": len(self.questions()),
                "deadline": b.get("deadline"), "urgent": self.urgent, "risk": b.get("risk", "normal"),
                "host": b.get("host"), "sent_at": self.sent_at, "same": [x.name for x in same],
                "bad": self.bad}


def waiting(zone):
    """待辦（new＋cur），照 urgent 在上、寄出先後排；同 dedupe_key 疊成一組。回傳 [(主信, [同組其他])]。"""
    ls = _scan(zone, "new") + _scan(zone, "cur")
    ls.sort(key=lambda x: (not x.urgent, x.sent_at, x.name))
    groups, order = {}, []
    for x in ls:
        g = x.group()
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(x)
    return [(groups[g][0], groups[g][1:]) for g in order]


def pick(zone, ref):
    """ref＝ls 的編號或信名。回傳 (主信, 同組其他)。"""
    ws = waiting(zone)
    if re.match(r"^[0-9]+$", str(ref)) and len(str(ref)) < 6:
        i = int(ref)
        if 1 <= i <= len(ws):
            return ws[i - 1]
        raise Fail("LetterMissing", "no letter number %s (aos-user ls shows %d)" % (ref, len(ws)))
    for main, same in ws:
        if ref == main.name or ref in [s.name for s in same]:
            return main, same
    raise Fail("LetterMissing", "no waiting letter named %s" % ref)


def take(zone, x):
    """看＝new/→cur/（自己 rename，aos-post take 不能指定名字）。"""
    if x.where != "new":
        return x
    src, dst = x.path, os.path.join(box(zone), "cur", x.name)
    try:
        os.rename(src, dst)
    except OSError as e:
        raise Fail("MoveFailed", "cannot move %s to cur/: %s" % (x.name, e))
    log(zone, "seen", letter=x.name)
    return Letter(zone, "cur", x.name, x.letter)


def lost_letters(zone):
    """log 記看過、但 cur/ 與 done/ 都沒有的（多半被 aos-mailbox read 刪了）。"""
    seen, gone = [], set()
    for ln in read_log(zone):
        if ln.get("ev") == "seen":
            seen.append(ln.get("letter"))
        elif ln.get("ev") in ("answered", "replied", "ok", "rejected"):
            gone.add(ln.get("letter"))
    out = []
    for n in seen:
        if n in gone or n in out:
            continue
        if os.path.isdir(os.path.join(box(zone), "cur", n)) or os.path.isdir(os.path.join(box(zone), "new", n)):
            continue
        out.append(n)
    return out


def done_list(zone, limit=50):
    out = []
    root = os.path.join(zone, "done")
    try:
        months = sorted(os.listdir(root), reverse=True)
    except OSError:
        return out
    for m in months:
        d = os.path.join(root, m)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d), reverse=True):
            lt = load(os.path.join(d, n, "letter.json")) or {}
            rp = load(os.path.join(d, n, "reply.json"))
            b = lt.get("body") if isinstance(lt.get("body"), dict) else {}
            out.append({"letter": n, "month": m, "from": b.get("from"), "title": b.get("title"),
                        "kind": b.get("kind") or "old", "reply": rp})
            if len(out) >= limit:
                return out
    return out


# ---- 回信（使用者用）----------------------------------------------------------

def letter_hash(x):
    try:
        with open(os.path.join(x.path, "letter.json"), "rb") as f:
            return "sha256:" + hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def parse_answers(x, tokens, all_recommend=False):
    """tokens＝['q1:a', 'q2:c*', 'q3:other']；回傳 answers 與警告。全部題都要答。"""
    qs = {q["id"]: q for q in x.questions()}
    got, warns = {}, []
    for t in tokens:
        m = re.match(r"^([^:]+):([A-Za-z0-9]+)(\*?)$", t)
        if not m:
            raise Fail("ArgumentsBad", "answer %r: write id:key (add * when it is not the recommended one)" % t)
        qid, key, star = m.groups()
        if qid not in qs:
            raise Fail("ArgumentsBad", "no question %s in this letter (questions: %s)" % (qid, ", ".join(qs)))
        keys = [o["key"] for o in qs[qid]["options"]] + ["other"]
        if key not in keys:
            raise Fail("ArgumentsBad", "question %s: %s is not an option (%s)" % (qid, key, ", ".join(keys)))
        differs = key != qs[qid]["recommend"]
        if star and not differs:
            warns.append("%s:%s is the recommended one; the * is ignored" % (qid, key))
        got[qid] = {"id": qid, "answer": key, "differs": differs}
    if all_recommend:
        for qid, q in qs.items():
            if qid not in got:
                if x.body.get("risk") == "irreversible":
                    raise Fail("ArgumentsBad", "this letter is irreversible; --all-recommend does not apply, answer each question")
                got[qid] = {"id": qid, "answer": q["recommend"], "differs": False}
    miss = [q for q in qs if q not in got]
    return [got[q] for q in qs if q in got], miss, warns


def answer_line(x, answers, note):
    """跟 decide-page 同寫法的一行：id:代號、id:代號*（備註：…）。"""
    parts = ["%s:%s%s" % (a["id"], a["answer"], "*" if a["differs"] else "") for a in answers]
    s = "、".join(parts)
    if note:
        s += "（備註：%s）" % note.replace("\n", " / ")
    return s


def human_what(x, answers, note, text):
    if answers:
        qs = {q["id"]: q for q in x.questions()}
        bits = []
        for a in answers:
            q = qs.get(a["id"], {})
            lab = {o["key"]: o.get("label", "") for o in q.get("options", [])}.get(a["answer"], "other (see note)")
            bits.append("%s: %s (%s)%s" % (a["id"], a["answer"], lab,
                                           ", not the recommended one" if a["differs"] else ", as recommended"))
        s = "; ".join(bits)
        if note:
            s += ". Note: " + note
        return s
    return text or "ok"


def _sender_env(zone):
    env = dict(os.environ)
    for k in ("AOS_WS", "AOS_CF", "AOS_CLOCK"):
        env.pop(k, None)
    env["AOS_STACK"] = zone
    return env


def _finish(zone, x, reply, ev):
    """搬 cur/→done/<月>/<信名>/，寫 reply.json；記 log。"""
    month = time.strftime("%Y-%m")
    dd = os.path.join(zone, "done", month)
    os.makedirs(dd, exist_ok=True)
    dst = os.path.join(dd, x.name)
    os.rename(x.path, dst)
    if reply is not None:
        write_json(os.path.join(dst, "reply.json"), reply)
    try:
        os.remove(os.path.join(zone, "drafts", x.name + ".json"))
    except OSError:
        pass
    return dst


def save_draft(zone, x, data):
    write_json(os.path.join(zone, "drafts", x.name + ".json"), dict(data, saved_at=now_iso()))


def load_draft(zone, name):
    return load(os.path.join(zone, "drafts", name + ".json"))


def respond(zone, ref, answers=None, note="", text="", via="cli", ok_only=False, all_recommend=False):
    """answer／reply／ok 共用：組回信、寄給同組每一封的 reply_to、成功的搬 done/。回傳結果列表。"""
    need_zone(zone)
    main, same = pick(zone, ref)
    main = take(zone, main)
    same = [take(zone, s) for s in same]
    warns = []
    if ok_only:
        if main.kind != "fyi" and main.fmt == "zone":
            raise Fail("ArgumentsBad", "letter %s is %s; use answer or reply, ok is for fyi" % (main.name, main.kind))
        out = []
        for x in [main] + same:
            dst = _finish(zone, x, None, "ok")
            log(zone, "ok", letter=x.name, via=via)
            out.append({"letter": x.name, "done": dst, "reply": None})
        return out, warns
    ans = []
    if answers is not None or all_recommend:
        if not main.questions():
            raise Fail("ArgumentsBad", "letter %s has no questions; use reply" % main.name)
        ans, miss, warns = parse_answers(main, answers or [], all_recommend)
        if miss:
            save_draft(zone, main, {"answers": ans, "note": note, "text": text})
            raise Fail("AnswerMissing", "not answered yet: %s (saved as a draft; letter stays waiting)" % ", ".join(miss))
    elif not text.strip():
        raise Fail("ArgumentsBad", "reply needs some text")
    out = []
    for x in [main] + same:
        rb = x.reply_box()
        if not rb:
            raise Fail("ReplyToMissing", "letter %s has no reply_to; use ok to just put it away" % x.name)
        rid = secrets.token_hex(8)
        b = x.body
        body = {"from": "user", "to": b.get("from") or "?", "status": "DONE",
                "title": "Re: %s" % (b.get("title") or x.name),
                "what": human_what(main, ans, note, text), "outputs": "none", "not_done": "none", "decide": "none",
                "zone": ZONE_VER, "answers": ans, "answer_line": answer_line(main, ans, note) if ans else "",
                "note": note, "text": text, "via": via, "answered_at": now_iso(), "host": host(),
                "letter_hash": letter_hash(x), "reply_id": rid,
                "auth": {"level": 1, "check": "aos-user verify <this reply letter folder>"}}
        try:
            name = post(["send", "--in-reply-to", x.name, rb], body, env=_sender_env(zone))
        except Fail as e:
            save_draft(zone, x, {"answers": ans, "note": note, "text": text})
            log(zone, "reply_failed", letter=x.name, code=e.code)
            raise Fail(e.code, "cannot send the reply for %s to %s: %s (letter stays waiting; answer saved as a draft)"
                       % (x.name, rb, e))
        dst = _finish(zone, x, dict(body, sent_as=name, sent_to=rb), "answered")
        log(zone, "answered" if ans else "replied", letter=x.name, reply=name, reply_id=rid, to=rb,
            letter_hash=body["letter_hash"], via=via)
        out.append({"letter": x.name, "done": dst, "reply": name, "to": rb})
    return out, warns


# ---- 驗回信（L1）--------------------------------------------------------------

def verify(zone, path):
    """收信方驗一封回信是不是從這個專區寄出的：比 done/ 的 reply.json 與 log。回傳 (ok, 理由)。"""
    if os.path.isdir(path):
        p = os.path.join(path, "letter.json")
    elif os.path.isfile(path):
        p = path
    else:
        raise Fail("VerifyBad", "%s is not a letter file or folder" % path)
    lt = load(p)
    if not isinstance(lt, dict) or not isinstance(lt.get("body"), dict):
        raise Fail("LetterBad", "cannot read %s" % p)
    b = lt["body"]
    orig = lt.get("in_reply_to")
    if b.get("zone") != ZONE_VER or not orig:
        return False, "not a user-zone reply (no zone key or no in_reply_to)"
    if os.path.abspath(lt.get("sender") or "") != zone:
        return False, "sender is %s, not the zone %s" % (lt.get("sender"), zone)
    hit = None
    for m in sorted(os.listdir(os.path.join(zone, "done"))) if os.path.isdir(os.path.join(zone, "done")) else []:
        rp = os.path.join(zone, "done", m, orig, "reply.json")
        if os.path.exists(rp):
            hit = rp
    if not hit:
        return False, "the zone has no answered letter %s in done/" % orig
    kept = load(hit) or {}
    kept = {k: v for k, v in kept.items() if k not in ("sent_as", "sent_to")}
    if kept != b:
        diff = sorted(k for k in set(kept) | set(b) if kept.get(k) != b.get(k))
        return False, "the reply differs from the zone's copy in: %s" % ", ".join(diff)
    if not any(ln.get("reply_id") == b.get("reply_id") and ln.get("letter") == orig for ln in read_log(zone)):
        return False, "the zone log has no line for reply %s" % b.get("reply_id")
    return True, "matches %s and the zone log (level 1: same Linux account, so an agent with a shell could still fake both)" % hit


def door_get(zone):
    d = load(os.path.join(zone, "door.json"))
    if not isinstance(d, dict):
        raise Fail("ZoneMissing", "no door.json in %s (run: aos-user init)" % zone)
    return d


def door_mode(zone, mode):
    if mode not in ("normal", "away"):
        raise Fail("ArgumentsBad", "mode must be normal or away")
    d = door_get(zone)
    d["mode"] = mode
    write_json(os.path.join(zone, "door.json"), d)
    log(zone, "door", mode=mode)
    return d


# ---- 段 2：收件檢查、退信、通知、到期提醒（aos-user tick，systemd --user 計時器每分鐘跑）---------------

def parse_deadline(s):
    """'2026-11-15'＝那天結束（隔天 00:00）；'2026-11-15T18:00'＝當地時間。認不得＝None。回傳 naive 當地時間。"""
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return datetime.datetime.fromisoformat(s) + datetime.timedelta(days=1)
        d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def config_get(zone):
    c = load(os.path.join(zone, "config.json"))
    c = c if isinstance(c, dict) else {}
    out = {"notify": c.get("notify") is True, "quiet_hours": c.get("quiet_hours"),
           "max_per_hour": DEFAULT_MAX_PER_HOUR, "remind_hours": DEFAULT_REMIND_HOURS}
    for k in ("max_per_hour", "remind_hours"):
        v = c.get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            out[k] = v
    return out


def config_set(zone, **kw):
    p = os.path.join(zone, "config.json")
    c = load(p)
    c = c if isinstance(c, dict) else {}
    c.update(kw)
    write_json(p, c)
    return c


def in_quiet(quiet, now):
    """quiet＝'23:00-08:00'（可跨午夜）；壞的或 None＝不安靜。"""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", quiet or "") if isinstance(quiet, str) else None
    if not m:
        return False
    a = int(m.group(1)) * 60 + int(m.group(2))
    b = int(m.group(3)) * 60 + int(m.group(4))
    t = now.hour * 60 + now.minute
    return (a <= t < b) if a <= b else (t >= a or t < b)


def _sender_of(x):
    """限量用的寄件人：信封 sender（aos-post 從寄件端 AOS_STACK 算的）＞ body.from。"""
    s = (x.letter or {}).get("sender") if isinstance(x.letter, dict) else None
    return s if isinstance(s, str) and s else ("from:%s" % (x.body.get("from") or "?"))


def inspect(x):
    """收件檢查：回傳不合的理由（字串）或 None。舊格式（沒 zone 鍵）照收（沒 shell 的身用 mailbox_send 寄）。"""
    if x.bad:
        return "letter.json is missing or not JSON"
    if not isinstance(x.letter.get("body"), dict):
        return "the body is not a JSON object"
    if x.fmt == "old":
        return None
    try:
        check_letter(x.body)
    except Fail as e:
        return str(e)
    if x.kind != "fyi" and not x.reply_box():
        return "no reply_to: the answer would have nowhere to go"
    return None


def _inside(path, root):
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def reject(zone, x, reason):
    """不合的信：new/<信名>→rejected/<信名>/＋reason.txt，退信給 reply_to（status FAILED）。回傳退信信名或 None。"""
    dst = os.path.join(zone, "rejected", x.name)
    os.makedirs(os.path.join(zone, "rejected"), exist_ok=True)
    os.rename(x.path, dst)
    with open(os.path.join(dst, "reason.txt"), "w", encoding="utf-8") as f:
        f.write(reason + "\n")
    rb = x.reply_box()
    sent, err = None, None
    if not rb:
        err = "no reply_to"
    elif _inside(rb, zone):
        err = "reply_to is inside the zone (not returned, to avoid a loop)"
    else:
        b = x.body
        body = {"from": "user", "to": b.get("from") or "?", "status": "FAILED",
                "title": "Returned: %s" % (b.get("title") or x.name),
                "what": "The user zone did not take your letter: %s. Read the door (aos-user door, or %s), "
                        "fix the letter and send it again." % (reason, os.path.join(zone, "door.json")),
                "outputs": "none", "not_done": "the user has not seen this letter", "decide": "none",
                "zone": ZONE_VER, "returned": x.name, "reason": reason, "host": host()}
        try:
            sent = post(["send", "--in-reply-to", x.name, rb], body, env=_sender_env(zone))
        except Fail as e:
            err = "%s %s" % (e.code, e)
    log(zone, "rejected", letter=x.name, sender=_sender_of(x), reason=reason, returned=sent, return_error=err)
    return sent, err


def notify_send(summary, body, urgent=False):
    """桌面通知；沒 notify-send 或失敗＝丟 Fail（tick 只印警告，不記成已通知，下一分鐘再試）。"""
    exe = shutil.which("notify-send")
    if not exe:
        raise Fail("ToolMissing", "notify-send is not on PATH")
    args = [exe, "-a", "aos-user", "-u", "critical" if urgent else "normal", summary, body]
    p = subprocess.run(args, capture_output=True, text=True, timeout=15)
    if p.returncode != 0:
        raise Fail("NotifyFailed", (p.stderr.strip() or "notify-send exited %d" % p.returncode).splitlines()[-1])


def _lines(xs, limit=5):
    out = ["%s%s (%s)" % ("! " if x.urgent else "", x.body.get("title") or x.name, x.body.get("from") or "?")
           for x in xs[:limit]]
    if len(xs) > limit:
        out.append("... and %d more" % (len(xs) - limit))
    return out


def tick(zone, now=None, notifier=None):
    """一次收件檢查＋通知＋提醒。now＝datetime（測試用）；notifier(summary, body, urgent)＝換掉 notify-send（測試用）。
    回傳 {"checked": [...], "rejected": [{letter, reason, returned, error}], "notified": [...], "reminded": [...], "warnings": [...]}。"""
    need_zone(zone)
    now = now or datetime.datetime.now()
    t_now = now.timestamp()
    notifier = notifier or notify_send
    out = {"checked": [], "rejected": [], "notified": [], "reminded": [], "warnings": []}
    lockfd = os.open(zone, os.O_RDONLY)
    try:
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            out["warnings"].append("another tick is running")
            return out
        cfg = config_get(zone)
        lines = read_log(zone)
        known = {ln.get("letter") for ln in lines if ln.get("ev") in ("checked", "rejected")}
        recent = {}
        for ln in lines:
            if ln.get("ev") == "checked" and isinstance(ln.get("t"), (int, float)) and t_now - ln["t"] < 3600:
                recent[ln.get("sender")] = recent.get(ln.get("sender"), 0) + 1
        fresh = [x for x in _scan(zone, "new") if x.name not in known]
        fresh.sort(key=lambda x: (x.sent_at, x.name))
        for x in fresh:
            reason = inspect(x)
            who = _sender_of(x)
            if reason is None and recent.get(who, 0) >= cfg["max_per_hour"]:
                reason = "more than %d letters from %s in one hour; wait and send fewer (group questions in one letter)" % (
                    cfg["max_per_hour"], x.body.get("from") or who)
            if reason is None:
                recent[who] = recent.get(who, 0) + 1
                log(zone, "checked", letter=x.name, sender=who, t=t_now)
                out["checked"].append(x.name)
                continue
            try:
                sent, err = reject(zone, x, reason)
            except OSError as e:          # 使用者剛好 show 走了（new/→cur/）：這封下次不再檢查
                out["warnings"].append("cannot move %s to rejected/: %s" % (x.name, e))
                continue
            out["rejected"].append({"letter": x.name, "reason": reason, "returned": sent, "error": err})
            if err:
                out["warnings"].append("letter %s rejected but not returned: %s" % (x.name, err))
        # 通知：還在 new/（沒看過）、沒通知過的；出門模式或安靜時段只通知急件，其他的留到可以通知時
        lines = read_log(zone)
        told = set()
        reminded = set()
        for ln in lines:
            if ln.get("ev") == "notified":
                told.update(ln.get("letters") or [])
            elif ln.get("ev") == "reminded":
                reminded.add((ln.get("letter"), ln.get("stage")))
        mode = (load(os.path.join(zone, "door.json")) or {}).get("mode", "normal")
        quiet = mode == "away" or in_quiet(cfg["quiet_hours"], now)
        ok_now = lambda x: x.urgent or not quiet  # noqa: E731
        if cfg["notify"]:
            news = [x for x in _scan(zone, "new") if x.name not in told and ok_now(x)]
            news.sort(key=lambda x: (not x.urgent, x.sent_at, x.name))
            if news:
                urgent = any(x.urgent for x in news)
                try:
                    notifier("aos-user: %d new letter%s for you" % (len(news), "" if len(news) == 1 else "s"),
                             "\n".join(_lines(news) + ["aos-user ls"]), urgent)
                    log(zone, "notified", letters=[x.name for x in news])
                    out["notified"] = [x.name for x in news]
                except Fail as e:
                    out["warnings"].append("notice not shown: %s %s" % (e.code, e))
            due = []
            for main, same in waiting(zone):
                dl = parse_deadline(main.body.get("deadline"))
                if dl is None or not ok_now(main):
                    continue
                stage = "overdue" if now >= dl else ("soon" if now >= dl - datetime.timedelta(hours=cfg["remind_hours"]) else None)
                if stage and (main.name, stage) not in reminded:
                    due.append((main, stage))
            if due:
                body = ["%s %s: %s (%s)" % ("past" if st == "overdue" else "due", m.body.get("deadline"),
                                            m.body.get("title") or m.name, m.body.get("from") or "?") for m, st in due[:5]]
                if len(due) > 5:
                    body.append("... and %d more" % (len(due) - 5))
                try:
                    notifier("aos-user: %d letter%s near or past the deadline" % (len(due), "" if len(due) == 1 else "s"),
                             "\n".join(body + ["aos-user ls"]), any(m.urgent for m, _ in due))
                    for m, st in due:
                        log(zone, "reminded", letter=m.name, stage=st)
                        out["reminded"].append({"letter": m.name, "stage": st})
                except Fail as e:
                    out["warnings"].append("reminder not shown: %s %s" % (e.code, e))
        return out
    finally:
        os.close(lockfd)


def rejected_list(zone, limit=50):
    out = []
    d = os.path.join(zone, "rejected")
    try:
        names = sorted(os.listdir(d), reverse=True)
    except OSError:
        return out
    for n in names[:limit]:
        lt = load(os.path.join(d, n, "letter.json")) or {}
        b = lt.get("body") if isinstance(lt.get("body"), dict) else {}
        try:
            with open(os.path.join(d, n, "reason.txt"), encoding="utf-8") as f:
                reason = f.read().strip()
        except OSError:
            reason = ""
        out.append({"letter": n, "from": b.get("from"), "title": b.get("title"), "reason": reason})
    return out


# ---- 指令列 ------------------------------------------------------------------

HELP = """aos-user - the user's zone: agents send letters that need the user; the user lists, reads and answers them

usage: aos-user [--zone DIR] SUBCOMMAND [ARGS...]

for the user:
  ls [--json] [--done]          what waits for you (urgent first); --done: answered ones
  show N                        read letter N (number from ls, or its name); it moves from new/ to cur/
  answer N q1:a q2:c* [--note TEXT] [--all-recommend]
                                answer a decide letter (* = not the recommended one, as in decide-page)
  reply N TEXT                  answer in your own words (verify, trial, chore, old-format letters)
  ok N                          put away a fyi letter (no reply is sent)
  door [--mode normal|away]     show the door (the notice for senders), or switch mode
  serve [--port 8766]           the web page, bound to 127.0.0.1 only
  ls --rejected [--json]        letters that broke the door's rules (returned to their senders)
  notify [on|off|test]          desktop notices on/off (config.json), or show one test notice
  tick [--json] [--quiet]       check new letters (rules, per-sender limit per hour), return bad ones,
                                notify about new letters and deadlines; a systemd --user timer runs it every minute
for agents:
  send --kind KIND [--title T] [--from NAME] [--reply-to MAILBOX] [--urgent] [--deadline D] [FILE|-]
                                send a letter; the body JSON comes from FILE or stdin; checked against schema/letter.json
  verify REPLY_LETTER_FOLDER    check that a reply really came from this zone (level 1)
setup:
  init                          make the zone (keeps files that exist)
  where                         print the zone folder

zone: --zone ＞ $AOS_USER_ZONE ＞ ~/.aos/user.  Never read the zone with aos-mailbox read (it deletes letters).
exit codes: 0 ok; 10 nothing waiting (ls); 1 error ("aos-user: error: CODE reason" on stderr).
more: $AOS_HOME/frontend/aos-user/README.md"""


def die(code, msg):
    sys.stderr.write("%s: error: %s %s\n" % (PROG, code, msg))
    sys.exit(1)


def take_flag(args, name, has_value=True):
    if name in args:
        i = args.index(name)
        if not has_value:
            del args[i]
            return True
        if i + 1 >= len(args):
            raise Fail("ArgumentsBad", "%s needs a value" % name)
        v = args[i + 1]
        del args[i:i + 2]
        return v
    return None


def print_letter(x):
    b = x.body
    print("letter: %s  (%s, %s%s)" % (x.name, x.kind, "old format" if x.fmt == "old" else "zone",
                                      ", URGENT" if x.urgent else ""))
    for k in ("from", "title", "what", "done_when", "deadline", "default_if_silent", "risk", "host", "origin"):
        if b.get(k):
            print("%s: %s" % (k, b[k]))
    if x.fmt == "old":
        for k in ("outputs", "not_done", "decide"):
            if b.get(k) and b[k] != "none":
                print("%s: %s" % (k, b[k]))
    for q in x.questions():
        print("\n[%s] %s" % (q["id"], q.get("question")))
        if q.get("eli5"):
            print("    %s" % q["eli5"])
        for o in q.get("options", []):
            star = " *recommended*" if o["key"] == q.get("recommend") else ""
            cons = " -> %s" % o["consequence"] if o.get("consequence") else ""
            print("  %s) %s%s%s" % (o["key"], o.get("label"), cons, star))
        if q.get("why"):
            print("    why: %s" % q["why"])
        if q.get("details"):
            print("    details: %s" % q["details"])
        if q.get("source_path"):
            print("    source: %s" % q["source_path"])
    print("\nreply_to: %s" % (x.reply_box() or "(none)"))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args or args[0] in ("-h", "--help", "help"):
            print(HELP)
            return 0
        zarg = take_flag(args, "--zone")
        zone = zone_dir(zarg)
        if not args:
            raise Fail("ArgumentsBad", "missing subcommand (see aos-user --help)")
        sub, rest = args[0], args[1:]
        if "-h" in rest or "--help" in rest:
            print(HELP)
            return 0
        if sub == "init":
            made = init(zone)
            log(zone, "init", made=made)
            print("%s: %s" % (zone, ("made " + ", ".join(made)) if made else "already there, nothing changed"))
        elif sub == "where":
            print(zone)
        elif sub == "send":
            kind = take_flag(rest, "--kind")
            title = take_flag(rest, "--title")
            sender = take_flag(rest, "--from")
            reply_to = take_flag(rest, "--reply-to")
            deadline = take_flag(rest, "--deadline")
            urgent = take_flag(rest, "--urgent", False)
            src = rest[0] if rest else "-"
            if src == "-" and sys.stdin.isatty():
                raise Fail("ArgumentsBad", "the letter JSON comes from FILE or a pipe")
            raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
            try:
                data = json.loads(raw) if raw.strip() else {}
            except ValueError as e:
                raise Fail("SchemaBad", "the letter is not JSON: %s" % e)
            if not isinstance(data, dict):
                raise Fail("SchemaBad", "the letter must be a JSON object")
            if urgent:
                data["urgent"] = True
            if deadline:
                data["deadline"] = deadline
            body = build_letter(data, kind, title, sender)
            print(send(zone, body, reply_to))
        elif sub == "ls":
            js = take_flag(rest, "--json", False)
            if take_flag(rest, "--rejected", False):
                d = rejected_list(zone)
                if js:
                    print(json.dumps(d, ensure_ascii=False))
                else:
                    for r in d:
                        print("%s\t%s\t%s\t%s" % (r["letter"], r["from"], r["title"], r["reason"]))
                return 0
            if take_flag(rest, "--done", False):
                d = done_list(zone)
                if js:
                    print(json.dumps(d, ensure_ascii=False))
                else:
                    for r in d:
                        rp = r["reply"] or {}
                        print("%s\t%s\t%s\t%s" % (r["month"], r["from"], r["title"],
                                                  rp.get("answer_line") or rp.get("text") or "(ok)"))
                return 0
            need_zone(zone)
            ws = waiting(zone)
            rows = [m.row(i, s) for i, (m, s) in enumerate(ws, 1)]
            for n in lost_letters(zone):
                sys.stderr.write("aos-user: warning: letter %s was seen but is gone from cur/ and done/ "
                                 "(read by aos-mailbox read?)\n" % n)
            if js:
                print(json.dumps(rows, ensure_ascii=False))
                return 0
            if not rows:
                print("nothing waiting")
                return 10
            for r in rows:
                flags = ("!" if r["urgent"] else " ") + ("*" if r["where"] == "new" else " ")
                extra = []
                if r["questions"]:
                    extra.append("%dq" % r["questions"])
                if r["deadline"]:
                    extra.append("by " + r["deadline"])
                if r["format"] == "old":
                    extra.append("old")
                if r["same"]:
                    extra.append("x%d" % (len(r["same"]) + 1))
                print("%2d %s %-6s %-14s %s%s" % (r["n"], flags, r["kind"], (r["from"] or "?")[:14], r["title"],
                                                  ("  [" + ", ".join(extra) + "]") if extra else ""))
            print("(! urgent, * not seen yet)")
        elif sub == "show":
            if len(rest) != 1:
                raise Fail("ArgumentsBad", "usage: aos-user show N")
            need_zone(zone)
            m, s = pick(zone, rest[0])
            m = take(zone, m)
            for x in s:
                take(zone, x)
            print_letter(m)
            if s:
                print("same question also from: %s" % ", ".join(x.body.get("from") or x.name for x in s))
        elif sub == "answer":
            note = take_flag(rest, "--note") or ""
            allr = take_flag(rest, "--all-recommend", False)
            if not rest:
                raise Fail("ArgumentsBad", "usage: aos-user answer N q1:a q2:c* [--note TEXT]")
            out, warns = respond(zone, rest[0], answers=rest[1:], note=note, all_recommend=allr)
            for w in warns:
                sys.stderr.write("aos-user: warning: %s\n" % w)
            for r in out:
                print("answered %s -> %s (reply %s)" % (r["letter"], r["to"], r["reply"]))
        elif sub == "reply":
            if len(rest) < 2:
                raise Fail("ArgumentsBad", "usage: aos-user reply N TEXT")
            out, _ = respond(zone, rest[0], text=" ".join(rest[1:]))
            for r in out:
                print("replied %s -> %s (reply %s)" % (r["letter"], r["to"], r["reply"]))
        elif sub == "ok":
            if len(rest) != 1:
                raise Fail("ArgumentsBad", "usage: aos-user ok N")
            out, _ = respond(zone, rest[0], ok_only=True)
            for r in out:
                print("put away %s" % r["letter"])
        elif sub == "door":
            mode = take_flag(rest, "--mode")
            d = door_mode(zone, mode) if mode else door_get(zone)
            print(json.dumps(d, ensure_ascii=False, indent=1))
        elif sub == "verify":
            if len(rest) != 1:
                raise Fail("ArgumentsBad", "usage: aos-user verify REPLY_LETTER_FOLDER")
            ok, why = verify(zone, os.path.abspath(rest[0]))
            if not ok:
                raise Fail("VerifyBad", why)
            print("ok: " + why)
        elif sub == "tick":
            js = take_flag(rest, "--json", False)
            quiet = take_flag(rest, "--quiet", False)
            if rest:
                raise Fail("ArgumentsBad", "usage: aos-user tick [--json] [--quiet]")
            r = tick(zone)
            for w in r["warnings"]:
                sys.stderr.write("aos-user: warning: %s\n" % w)
            if js:
                print(json.dumps(r, ensure_ascii=False))
            elif not quiet or r["checked"] or r["rejected"] or r["notified"] or r["reminded"]:
                print("checked %d, rejected %d, notified %d, reminded %d" % (
                    len(r["checked"]), len(r["rejected"]), len(r["notified"]), len(r["reminded"])))
                for x in r["rejected"]:
                    print("rejected %s: %s (%s)" % (x["letter"], x["reason"],
                                                    "returned as " + x["returned"] if x["returned"] else "not returned"))
        elif sub == "notify":
            if len(rest) > 1 or (rest and rest[0] not in ("on", "off", "test")):
                raise Fail("ArgumentsBad", "usage: aos-user notify [on|off|test]")
            need_zone(zone)
            if rest and rest[0] == "test":
                notify_send("aos-user: test notice", "If you see this, desktop notices work. (aos-user notify test)")
                print("sent a test notice")
            elif rest:
                config_set(zone, notify=rest[0] == "on")
                log(zone, "config", notify=rest[0] == "on")
            if not rest or rest[0] != "test":
                c = config_get(zone)
                print("notify: %s; quiet_hours: %s; max_per_hour: %d; remind_hours: %d" % (
                    "on" if c["notify"] else "off", c["quiet_hours"], c["max_per_hour"], c["remind_hours"]))
        elif sub == "serve":
            port = take_flag(rest, "--port")
            import web
            need_zone(zone)
            web.serve(zone, int(port) if port else (door_cfg_port(zone)))
        else:
            raise Fail("CommandUnknown", "unknown subcommand %s (see aos-user --help)" % sub)
    except Fail as e:
        die(e.code, e)
    except OSError as e:
        die("Internal", e)
    return 0


def door_cfg_port(zone):
    c = load(os.path.join(zone, "config.json")) or {}
    p = c.get("port")
    return p if isinstance(p, int) else DEFAULT_PORT
