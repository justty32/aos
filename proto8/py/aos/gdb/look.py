"""aos.gdb.look - 讀 stack 裡的檔（stage、history、observed、最後一次問腦、信箱、stderr；把手上的 a.look 就是它）、why() 的結果長相、跑一條指令的小殼。

停住時人看的全在 stack 的普通檔（thinking/2026-11/19/aos-gdb-1119/07 第三節）；這裡每個方法只讀一個檔，不解讀、不改。
讀檔收進 a.look（使用者 11-19 選項框「收進 a.look」，thinking/2026-11/19/aos-pylib-1119/07 第 5 題），a.history 等名字還給 aos-agent。
Look 只需要 self.stack；觀察者（aos.gdb.watcher）交給條件函式的 t 也是它（Argon A8）。
跑指令、例外、Text 用入口那份（aos.py._shell）：整個活的那一邊只有一種 Failed。"""
import json
import os

from aos.py._shell import Failed, Text, call, show  # noqa: F401（Failed、Text 給 aos.gdb 其他檔用）


def run(argv, echo=True, input=None):
    """跑一條指令，回 stdout（Text，可能是空的）；退非 0 丟 Failed。echo＝這條可以印（aos.py.echo 開著才真的印，在 stderr）。"""
    return call(argv, input=input, quiet=not echo)


def _read(path):
    show("# read %s" % path)


def _tail_jsonl(path, n):
    _read(path)
    try:
        with open(path, encoding="utf-8") as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
    except FileNotFoundError:
        return []
    out = []
    for x in lines[-n:] if n else lines:
        try:
            out.append(json.loads(x))
        except ValueError:
            out.append({"unreadable": x})
    return out


def bp_id(name):
    """hook 名 gdb_<id>／觀察者 proc 名 gdbw_<id>（或已經拿掉字首的 id）→ 斷點 id：號碼＝int（使用者 11-20 選純數字），自己取的名字＝str；空＝None。"""
    s = name or ""
    for p in ("gdbw_", "gdb_"):                  # gdbw_ 先比（它也以 gdb 開頭）
        if s.startswith(p):
            s = s[len(p):]
            break
    if not s:
        return None
    return int(s) if s.isascii() and s.isdigit() else s


DIGITS = 4                                       # 號碼在名字裡補零到幾位（使用者 11-20 選「斷點號碼檔名補零」；紀錄寫的例子是 gdb_0002）


def bp_name(id):
    """斷點 id → hook 名／proc 名裡字首後面那段：號碼補零到 DIGITS 位（gdb_0002：hook 照名字的字典順序跑、ls 夾也照號碼排；
    過了 9999 就是原樣的 5 位以上，順序從那裡起不保證），自己取的名字原樣。bp_id 反過來（"0002" → 2）。"""
    return "%0*d" % (DIGITS, id) if isinstance(id, int) and not isinstance(id, bool) else str(id)


class Why:
    """why() 的結果：paused（停著沒：ctl pause 已套用，或扣在斷點上）、held（扣住的那份 hold.json 或 None）、
    current（最後一張字條是不是這次停的原因）、notes（上次 resume 之後的字條）、pending（扣住之後又來的 ctl 指令 (seq, cmd) 或 None）、
    breakpoint（現在停在哪個斷點的 id：號碼 int，或自己取的名字 str；不是停在斷點上＝None）。
    a.bp.resume()／step()／pause() 回的也是它（wait=False 時是背景等完之後 .wait() 回的），另有 outcome（stopped＝停了、idle＝閒著不會停、
    gone＝行程不在、interrupted＝Ctrl-C 不等了、cancelled＝Pending.cancel() 不等了）與 head（印出來的第一行，例 "stopped at breakpoint 1 (before_tool: write)"）；a.bp.why() 回的這兩個是 None。"""

    def __init__(self, name, paused, current, notes, held=None, pending=None):
        self.name, self.paused, self.current, self.notes, self.held, self.pending = name, paused, current, notes, held, pending
        last = notes[-1] if notes else {}
        self.breakpoint = (bp_id(held.get("trigger")) if held else bp_id(last.get("trigger")) if paused and current and notes else None)
        self.outcome = self.head = None

    def __bool__(self):
        return bool(self.notes)

    def __repr__(self):
        body = self._body()
        if self.head is None:
            return body
        if self.outcome != "stopped":
            return self.head
        return self.head + "\n" + body

    def _body(self):
        last = self.notes[-1] if self.notes else {}
        who = ("a.bp.%s()" % last.get("by") if last.get("by") in ("step", "pause")
               else "breakpoint %s (%s)" % (bp_id(last.get("trigger")), "a watcher" if last.get("by") == "watch" else "a trigger"))
        if self.held:
            h = self.held
            d = h.get("detail", {})
            thing = ("tool %s has not run yet" % d.get("name") if h.get("event") == "before_tool"
                     else "letter %s is not taken in yet" % d.get("letter") if h.get("event") == "before_queue" else "the event has not happened yet")
            head = "%s is held at breakpoint %s: %s; a.bp.resume() lets it go on as it was, a.bp.step() runs it and stops after this step" % (
                self.name, bp_id(h.get("trigger")), thing)
            if self.pending:
                head += ("\n  then it %ss: aos-agent ctl %s (seq %s) came while held, and the loop applies it after this step"
                         % (self.pending[1], self.pending[1], self.pending[0]))
        elif not self.paused:
            head = "%s is not paused" % self.name
        elif self.current:
            head = "%s is paused by %s" % (self.name, who)
        elif self.notes:
            head = "%s is paused, but ctl was used after the last note (by hand or by someone else); the notes may be old" % self.name
        else:
            head = "%s is paused, with no note (paused by hand, or by something that leaves no note)" % self.name
        lines = [head]
        for n in self.notes:
            d = n.get("detail", {})
            what = " ".join("%s=%s" % (k, json.dumps(d[k], ensure_ascii=False)) for k in ("name", "code", "arguments", "content", "letter", "stage")
                            if k in d)
            lines.append("  %s %s %s: %s%s%s%s" % (n.get("at", "?"), n.get("by", "?"), n.get("trigger") or "-", n.get("about") or n.get("event"),
                                                  " [held before it]" if n.get("how") == "hold" and n.get("kind") == "stop" else "",
                                                  " [held again: the earlier hold was cut off]" if n.get("again") else "",
                                                  " (pause failed: %s)" % n.get("why") if n.get("kind") == "pause_failed" else
                                                  " (hold ended without release: %s; %s)" % (n.get("why"), n.get("next")) if n.get("kind") == "hold_ended" else ""))
            if what:
                lines.append("      " + what)
        return "\n".join(lines)


class Look:
    """讀 stack 的檔（a.look）；需要 self.stack。讀不到的檔＝None／[]（不是錯），JSON 壞了＝Failed（code JsonBad）。"""

    def path(self, rel=""):
        return os.path.join(self.stack, rel)

    def file(self, rel):
        """stack 裡任一個檔的內容（Text）；沒有＝None。"""
        p = self.path(rel)
        _read(p)
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return Text(f.read())
        except FileNotFoundError:
            return None

    def where(self):
        """停在哪一格（stage.txt）。"""
        s = self.file("stage.txt")
        return None if s is None else s.strip()

    def history(self, n=5):
        """history.jsonl 最後 n 則（0＝全部）。"""
        return _tail_jsonl(self.path("history.jsonl"), n)

    def observed(self, n=5):
        """observed.jsonl 最後 n 筆（每次想、每次工具的流水帳）。"""
        return _tail_jsonl(self.path("observed.jsonl"), n)

    def request(self):
        """最後一次問腦的整份（think/request.json）；沒有＝None。"""
        t = self.file(os.path.join("think", "request.json"))
        try:
            return None if t is None else json.loads(t)
        except ValueError as e:
            raise Failed("a.look.request", "%s is not JSON: %s" % (self.path(os.path.join("think", "request.json")), e), code="JsonBad") from None

    def queue(self):
        """信箱裡還沒收的信（queue/new/ 的檔名）。"""
        p = self.path(os.path.join("queue", "new"))
        _read(p)
        try:
            return sorted(n for n in os.listdir(p) if not n.startswith("."))
        except FileNotFoundError:
            return []

    def stderr(self, n=20):
        """stderr.txt 最後 n 行。"""
        t = self.file("stderr.txt")
        return Text("") if t is None else Text("\n".join(t.splitlines()[-n:]) + "\n")
