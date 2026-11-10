# aos_agent/history.py - 看與改 agent 的對話紀錄（宣告的 history 檔，一行一則訊息）：ls、rm 一段、summarize 一段換成一則、set 任一行；改掉的原文預設搬到旁邊。
# 使用者 11-10 晚 self_history 五題：「1.全給，風險自己擔。2.可以。3.可選，默認搬到旁邊(可以選要搬到哪) 4.接受縮水版。5.對」
#   （thinking 2026-11/10/self-family）。這支是人用的那層；「正在進行的這一步動不了」只在包它的 self_history，這裡不擋。
# 哪個檔：定義 interfaces.json 的 aos-agent.history（相對這隻的 stack；agent-fsm、eca-claude 都宣告 history.jsonl）；沒宣告＝HistoryMissing。
# 行號＝第幾則訊息（從 1 起，空行不算）；一段＝N、A-B、A-（到最後）。讀不懂的行照原文顯示、照樣能刪能改。
# 寫法：整份寫暫存再改名（讀的人不會看到半份）；寫之前再看一次檔有沒有被別人動過（agent 正好接了一行），動過就重讀重做，最多 3 次。
# 改掉的原文：每則一行 {"removed_at", "op", "line", "message"|"raw"} 接在旁邊那份（預設 history 同資料夾的 <名>_removed.jsonl；
#   --keep FILE 換位置、相對 cwd；--no-keep 不留＝不可逆，終端上先問、-y 跳過）。先寫旁邊那份、再換 history。
# summarize 的新訊息：角色預設 user，內容固定「[aos] summary: lines A-B, N messages. 摘要」（第三批統一成 [aos] 種類: 內容）（使用者 11-10 深夜：「self_history的摘要這塊，身份可以是user，
#   只是內容這塊希望能符合特定格式，比如我們現有的error那樣，就aos:...。」；形狀隊長代定）；set 照原樣寫、不套。
# 跑著的 agent 怎麼看到：fsm 每次 think 從頭讀 history；wait 寄之前看 history 比請求新就回 think 重組。eca 下一輪發現 history 被改過＝開新對話、帶改過的紀錄過去（縮水版）。
import datetime
import json
import os
import sys
import aos_flags
from . import PROG
from .common import Fail, actions, bad_args, parse, target
from .decl import agent_decl

KEEP_FLAGS = """      --keep FILE     append the removed messages to FILE (relative to the current directory)
                      instead of the default <history>_removed.jsonl next to the history file
      --no-keep       do not keep them (asks on a terminal; -y skips)
  -y, --yes           with --no-keep: skip the question"""
HELPS = {
    "ls": """aos-agent history ls - list this agent's conversation, one message per line

usage: aos-agent [--daemon D] history [--target NAME] ls [-j | --json] [RANGE]
       aos-agent history ls --help

flags:
  -j, --json   print one JSON array of {"line": N, "message": {...}} ({"line": N, "raw": TEXT} for a line that is not JSON)
  -h, --help   show this help

Print LINE TAB ROLE TAB TEXT per message (newlines shown as \\n; tool calls as -> name(arguments)).
RANGE = N, A-B or A- (to the end); default: all. Line numbers count messages from 1.
exit codes: 0 listed; 1 error (HistoryMissing, RangeBad...).
""",
    "rm": """aos-agent history rm - delete some messages

usage: aos-agent [--daemon D] history [--target NAME] rm [--keep FILE | --no-keep [-y]] RANGE
       aos-agent history rm --help

flags:
%s
  -h, --help          show this help

RANGE = N, A-B or A- (to the end). The messages after it move up.
exit codes: 0 removed; 1 error (HistoryMissing, RangeBad, WriteFailed...); 130 Ctrl-C.
""" % KEEP_FLAGS,
    "summarize": """aos-agent history summarize - replace some messages with one message you write

usage: aos-agent [--daemon D] history [--target NAME] summarize [--role ROLE] [--keep FILE | --no-keep [-y]] RANGE TEXT
       aos-agent history summarize --help

flags:
      --role ROLE     the new message's role (default: user)
%s
  -h, --help          show this help

RANGE = N, A-B or A- (to the end); TEXT = your summary (- reads it from stdin); flags go before TEXT (from TEXT on
nothing is read as a flag). The new message goes at line A and reads
  [aos] summary: lines A-B, N messages. TEXT
so it is not taken for something the user said (set writes a message as given).
exit codes: 0 replaced; 1 error (HistoryMissing, RangeBad, WriteFailed...); 130 Ctrl-C.
""" % KEEP_FLAGS,
    "set": """aos-agent history set - replace one message with any JSON object

usage: aos-agent [--daemon D] history [--target NAME] set [--keep FILE | --no-keep [-y]] LINE JSON
       aos-agent history set --help

flags:
%s
  -h, --help          show this help

JSON = the whole new message, e.g. '{"role": "user", "content": "hi"}' (- reads it from stdin);
written as given, nothing checked but that it is one JSON object; flags go before JSON.
exit codes: 0 replaced; 1 error (HistoryMissing, RangeBad, MessageBad, WriteFailed...); 130 Ctrl-C.
""" % KEEP_FLAGS,
}
HELP = """aos-agent history - see and change this agent's conversation (its history file)

usage: aos-agent [--daemon D] history [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent history ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means ls. The file is the one the definition declares (interfaces.json aos-agent.history,
relative to the agent's stack). Removed messages are kept next to it unless --no-keep.
A running fsm agent uses the change from its next request; an eca agent (claude, codex) starts a new
conversation on its next turn and carries the changed record over. Pausing first (ctl pause) is safest.
exit codes: 0 ok; 1 error (TargetMissing, HistoryMissing, RangeBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] history [--target NAME] ")
TRIES = 3


def history_file(a):
    """宣告的 history 位置（相對 stack）；沒宣告＝HistoryMissing。"""
    folder, decl = agent_decl(a)
    rel = decl.get("history")
    if rel is None:
        raise Fail("HistoryMissing", "%s does not declare the history sub-interface (write {\"aos-agent\": {\"history\": \"history.jsonl\"}} in %s/interfaces.json)" % (a.name, folder))
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in rel.split("/"):
        raise Fail("InterfaceBad", "history in %s/interfaces.json must be a relative file path inside the stack" % folder)
    return os.path.join(a.stack, rel)


def read_rows(path):
    """非空行的原文（不含換行）；檔不在＝[]。回 (rows, 指紋)。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
            st = os.fstat(f.fileno())
    except FileNotFoundError:
        return [], None
    except OSError as e:
        raise Fail("HistoryBad", "cannot read %s: %s" % (path, e))
    try:
        text = data.decode("utf-8")
    except UnicodeError as e:
        raise Fail("HistoryBad", "%s is not UTF-8: %s" % (path, e))
    return [l for l in text.split("\n") if l.strip()], (st.st_size, st.st_mtime_ns)


def stamp(path):
    try:
        st = os.stat(path)
        return st.st_size, st.st_mtime_ns
    except FileNotFoundError:
        return None


def message(raw):
    try:
        m = json.loads(raw)
    except ValueError:
        return None
    return m if isinstance(m, dict) else None


def span(text, n, one=False):
    """N、A-B、A-（one＝只收 N）→ (a, b) 1 起、含兩端；超出或倒過來＝RangeBad。"""
    a, dash, b = text.partition("-")
    ok = a.isdecimal() and (not dash or (not one and (b == "" or b.isdecimal())))
    if not ok:
        raise Fail("RangeBad", "%s is not a %s (write %s)" % (text, "line number" if one else "range", "N" if one else "N, A-B or A-"))
    a = int(a)
    b = int(b) if b else (n if dash else a)
    if n == 0:
        raise Fail("RangeBad", "the history is empty")
    if a < 1 or b > n or a > b:
        raise Fail("RangeBad", "%s is outside 1-%d (the history has %d messages)" % (text, n, n))
    return a, b


def one_line(s):
    return str(s).replace("\\", "\\\\").replace("\n", "\\n").replace("\t", " ")


def show(n, raw):
    m = message(raw)
    if m is None:
        return "%d\t?\t%s" % (n, one_line(raw))
    c = m.get("content")
    text = c if isinstance(c, str) else ("" if c is None else json.dumps(c, ensure_ascii=False))
    if m.get("role") == "tool" and m.get("tool_call_id"):
        text = "(%s) %s" % (m["tool_call_id"], text)
    for call in m.get("tool_calls") or []:
        f = call.get("function") if isinstance(call, dict) else None
        if isinstance(f, dict):
            text += "%s-> %s(%s)" % (" " if text else "", f.get("name"), f.get("arguments", ""))
    return "%d\t%s\t%s" % (n, one_line(m.get("role", "?")), one_line(text))


def summary_text(lo, hi, text):
    """summarize 寫進去的那則：「[aos] summary: lines A-B, N messages. 摘要」（一則＝line A, 1 message.），讀的人分得出這不是使用者講的
    （使用者 11-10 深夜第 8 題；第三批「1.可以。2.好，統一。」改成 [aos] 種類: 內容，aos_flags.aos_note）。"""
    k = hi - lo + 1
    where = "line %d, 1 message" % lo if k == 1 else "lines %d-%d, %d messages" % (lo, hi, k)
    return aos_flags.aos_note("summary", "%s. %s" % (where, text))


def from_arg(v):
    return sys.stdin.read() if v == "-" else v


def keep_target(path, topts):
    if topts.get("no_keep"):
        return None
    if "keep" in topts:
        return os.path.abspath(topts["keep"])
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(os.path.dirname(path), stem + "_removed.jsonl")


def keep(where, op, first, rows):
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    out = []
    for i, raw in enumerate(rows):
        m = message(raw)
        rec = {"removed_at": at, "op": op, "line": first + i}
        rec.update({"message": m} if m is not None else {"raw": raw})
        out.append(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        os.makedirs(os.path.dirname(where) or ".", exist_ok=True)
        with open(where, "a", encoding="utf-8") as f:
            f.write("".join(out))
    except OSError as e:
        raise Fail("WriteFailed", "cannot keep the removed messages in %s (nothing changed): %s" % (where, e))


def rewrite(path, change, where, op):
    """change(rows) -> (新 rows, 被換掉的那段 rows, 那段第一行)。寫之前檔被動過＝重來（最多 TRIES 次）。"""
    for _ in range(TRIES):
        rows, before = read_rows(path)
        new, gone, first = change(rows)
        tmp = os.path.join(os.path.dirname(path), ".%s.tmp" % os.path.basename(path))
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("".join(r + "\n" for r in new))
        except OSError as e:
            raise Fail("WriteFailed", "cannot write %s: %s" % (tmp, e))
        if stamp(path) != before:                   # 這段時間 agent 接了一行：重讀重做
            os.unlink(tmp)
            continue
        if where:
            keep(where, op, first, gone)
        try:
            os.replace(tmp, path)
        except OSError as e:
            raise Fail("WriteFailed", "cannot replace %s: %s%s" % (path, e, "; the removed messages were already copied to %s" % where if where else ""))
        return len(gone)
    raise Fail("WriteFailed", "%s kept changing while writing (tried %d times); pause the agent first (aos-agent ctl pause)" % (path, TRIES))


def where_said(where):
    return "the originals are in %s" % where if where else "not kept"


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in HELPS:
        raise Fail("CommandUnknown", "history: unknown action %s (%s; see aos-agent history --help)" % (act, ", ".join(HELPS)))
    flags = {"--keep": "keep"} if act != "ls" else {}
    switches = {"--json": "json"} if act == "ls" else {"--no-keep": "no_keep", "--yes": "yes"}
    shorts = {"-j": "--json"} if act == "ls" else {"-y": "--yes"}
    if act == "summarize":
        flags["--role"] = "role"
    topts, args = parse(args, flags, switches, help=HELPS[act], short=shorts,
                        keep=2 if act in ("summarize", "set") else None)   # 11-10 Q3：TEXT／JSON 起原樣收（內容裡的 - 開頭字不是旗標）
    count = {"ls": (0, 1), "rm": (1, 1), "summarize": (2, 2), "set": (2, 2)}[act]
    if not count[0] <= len(args) <= count[1]:
        raise bad_args(HELPS[act], "%s needs %s" % (act, {"ls": "at most one RANGE", "rm": "one RANGE",
                                                           "summarize": "RANGE and TEXT", "set": "LINE and JSON"}[act]))
    if "keep" in topts and topts.get("no_keep"):
        raise bad_args(HELPS[act], "give --keep FILE or --no-keep, not both")
    if topts.get("yes") and not topts.get("no_keep"):
        raise bad_args(HELPS[act], "-y only goes with --no-keep")
    a = target(opts)
    path = history_file(a)
    if act == "ls":
        rows, _ = read_rows(path)
        lo, hi = span(args[0], len(rows)) if args else (1, len(rows))
        picked = list(range(lo, hi + 1)) if rows else []
        if topts.get("json"):
            print(json.dumps([dict({"line": n}, **({"message": message(rows[n - 1])} if message(rows[n - 1]) is not None
                                                  else {"raw": rows[n - 1]})) for n in picked], ensure_ascii=False))
        else:
            for n in picked:
                print(show(n, rows[n - 1]))
        return
    where = keep_target(path, topts)
    if where is None and not aos_flags.confirm(PROG, "delete these messages of %s for good (--no-keep)?" % a.name, yes=topts.get("yes", False)):
        aos_flags.warn(PROG, "nothing done")
        return
    if act == "rm":
        def change(rows):
            lo, hi = span(args[0], len(rows))
            return rows[:lo - 1] + rows[hi:], rows[lo - 1:hi], lo
        k = rewrite(path, change, where, "rm")
        lo = int(args[0].partition("-")[0])
        print("removed %d message%s from line %d; %s" % (k, "" if k == 1 else "s", lo, where_said(where)))
    elif act == "summarize":
        text = from_arg(args[1])
        role = topts.get("role", "user")
        if not text.strip():
            raise bad_args(HELPS[act], "TEXT is empty")

        def change(rows):
            lo, hi = span(args[0], len(rows))
            new = json.dumps({"role": role, "content": summary_text(lo, hi, text)}, ensure_ascii=False)
            return rows[:lo - 1] + [new] + rows[hi:], rows[lo - 1:hi], lo
        k = rewrite(path, change, where, "summarize")
        lo = int(args[0].partition("-")[0])
        print("replaced %d message%s with one %s message at line %d; %s" % (k, "" if k == 1 else "s", role, lo, where_said(where)))
    else:
        try:
            m = json.loads(from_arg(args[1]))
        except ValueError as e:
            raise Fail("MessageBad", "JSON is not valid JSON: %s" % e)
        if not isinstance(m, dict):
            raise Fail("MessageBad", "JSON must be one JSON object, like {\"role\": \"user\", \"content\": \"hi\"}")
        new = json.dumps(m, ensure_ascii=False)

        def change(rows):
            n, _ = span(args[0], len(rows), one=True)
            return rows[:n - 1] + [new] + rows[n:], rows[n - 1:n], n
        rewrite(path, change, where, "set")
        print("replaced line %s; %s" % (args[0], where_said(where)))
