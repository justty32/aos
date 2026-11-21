"""aos.gdb.decl - aos-gdb 拿 hook 宣告（hooks.json 那種）當參考：列出有哪些點、各點事件有哪些欄位；給 a.bp 補種類與主詞、下斷點時提醒、照 input schema 排停下的事件。

使用者 11-21（線 top-1121-gdbdecl，紀錄 thinking/2026-11/21/gdb-參考宣告-1121.md）：「4.要做，我覺得可以在gdb啓動時給他選項，跟他說可以參考這份宣告，然後再去做一些事情。」
同日的原則「宣告只是參考」：不給宣告 gdb 照舊；給了但跟實際對不上也不擋——讀不到的檔一行 warning 跳過，下斷點時點名或欄位不在宣告裡一行 warning、照下。

一個 REPL 一份（模組裡的 current；aos-gdb 裡叫 hooks）：
    hooks.load(*paths)        讀宣告檔加進來（同一個 id 先讀到的算，同 aos.hook_point.read）；壞的檔一行 warning 跳過
    hooks.load_def(x)         讀一個定義夾 interfaces.json 最外層 "hooks" 指的那幾份；x＝定義夾路徑，或遙控器 a（問 aos-agent ctl state who 的 def）
    hooks.clear()             全拿掉（回到沒有宣告：a.bp 照預設）
    hooks                     REPL 裡直接打＝一張表：點、gdb 怎麼停、宣告的 phase／block、主詞、欄位
    hooks.get(id)、hooks.fields(id)、hooks.points、hooks.files
a.bp 怎麼用它（aos.gdb 叫這裡的函式；沒載入任何宣告＝全部照預設，跟沒有這個模組一樣）：
    extra_kinds(defaults)     宣告了、但 gdb 預設沒有的點（on_clock、tool_error、watch、不是 Python 名字的除外）→ 多出來的斷點種類
    subject(kind)             宣告的 condition 欄（與 subject 說法）→ (參數名, 事件欄位)；沒宣告＝None（用預設）
    warnings(kind, py)        下斷點時的提醒句子：點不在宣告裡、py 條件讀的事件欄位不在宣告的 input 裡
    layout(event, kind)       照宣告的 input 排一個事件（宣告的欄位照順序、帶說明，沒宣告的另列）
不讀 sh 條件（猜不出它讀哪些欄位）；扣住還是暫停不從宣告讀（照 aos.gdb.trigger.how，見紀錄「沒做的」）。不印東西以外的副作用；錯不丟（讀檔錯＝warning）。"""
import dis
import json
import keyword
import os
import sys
import types

from aos import hook_point

RESERVED = ("sh", "py", "times", "once", "id", "replace", "every_ms", "also")   # a.bp.add 的關鍵字參數：主詞不能叫這些
SKIP = ("on_clock", "tool_error", "watch")                                    # 不當成斷點種類的 id（on_clock 要給間隔；後兩個是 gdb 自己的種類）
WIDTH = 100


def _warn(where, text):
    sys.stderr.write("%s: warning: %s\n" % (where, text))
    sys.stderr.flush()


def _name_ok(s):
    return isinstance(s, str) and s.isidentifier() and not keyword.iskeyword(s)


class Decl:
    """載入的 hook 宣告（只是參考）。points＝{id: 點}，files＝讀進來的檔（絕對路徑，照順序）。"""

    def __init__(self):
        self.points, self.files = {}, []

    def __bool__(self):
        return bool(self.files)

    # ---- 載入 ----
    def load(self, *paths, where="hooks.load"):
        """讀宣告檔加進來；回自己。一份讀不到或格式不對＝一行 warning、跳過那一份，其他照讀。"""
        for p in paths:
            p = os.path.abspath(os.path.expanduser(str(p)))
            try:
                got = hook_point.read([p])
            except hook_point.PointsBad as e:
                _warn(where, "%s; going on without it" % e)
                continue
            if p not in self.files:
                self.files.append(p)
            for k, v in got.items():
                self.points.setdefault(k, v)
        return self

    def load_def(self, x, where="hooks.load_def"):
        """讀一個定義夾的 interfaces.json 最外層 "hooks" 那幾份。x＝定義夾路徑，或遙控器（agent.attach 回的）：問它的 def。回自己。"""
        d = x
        if not isinstance(x, (str, os.PathLike)):
            try:
                who = (x.ctl.state("who", json=True) or {}).get("who") or {}
            except Exception as e:                      # 問不到（不在表上、指令失敗）＝warning，不擋
                _warn(where, "cannot ask where the definition of %s is: %s" % (getattr(x, "name", x), e))
                return self
            d = who.get("def")
            if not isinstance(d, str) or not d:
                _warn(where, "aos-agent ctl state who gives no definition folder for %s" % getattr(x, "name", x))
                return self
        try:
            paths = hook_point.files(str(d), "hooks")
        except hook_point.InterfaceBad as e:
            _warn(where, "%s; going on without it" % e)
            return self
        if not paths:
            _warn(where, "%s has no \"hooks\" at the top of its interfaces.json; nothing loaded" % d)
            return self
        return self.load(*paths, where=where)

    def clear(self):
        """全拿掉：a.bp 回到預設。回自己。"""
        self.points, self.files = {}, []
        return self

    # ---- 查 ----
    def get(self, id):
        """一個點的宣告（dict，原樣）；沒有＝None。"""
        return self.points.get(id)

    def fields(self, id):
        """一個點的 input 有哪些欄位（照宣告的順序）；沒宣告這個點、或 input 沒寫 properties＝None。"""
        props = (self.points.get(id) or {}).get("input", {}).get("properties")
        return list(props) if isinstance(props, dict) else None

    def __repr__(self):
        if not self:
            return "no hook declarations loaded (aos-gdb --hooks FILE or --def-hooks; here hooks.load(FILE) or hooks.load_def(a))"
        from aos import gdb as g
        defaults = g.EVENTS
        extra = extra_kinds(defaults)
        lines = ["hook declarations (only for reference): %d point(s) from %d file(s); hooks.load(FILE) adds, hooks.clear() empties"
                 % (len(self.points), len(self.files))]
        lines += ["  " + f for f in self.files]
        rows = [("point", "a.bp.add", "declared", "subject", "fields")]
        for id, p in self.points.items():
            if id in defaults or id in extra:
                how = g.trigger.how(id)
            elif id == "on_clock":
                how = "- (needs an interval)"
            else:
                how = "- (not a kind)"
            said = ", ".join(str(x) for x in (p.get("phase"), "block" if p.get("block") is True else None) if x) or "-"
            sub = g.subject_of(id) if (id in defaults or id in extra) else None
            rows.append((id, how, said, "%s= (%s)" % sub if sub else "-", ", ".join(_plain(self.fields(id))) or "-"))
        w = [max(len(r[i]) for r in rows) for i in range(4)]
        lines += ["  ".join(r[i].ljust(w[i]) for i in range(4)) + "  " + r[4] for r in rows]
        lines.append("(a.bp.add.<point>: hold = held before it happens, pause = stops when that step ends; "
                     "kinds gdb has but these files do not declare still work, with a warning)")
        return "\n".join(lines)


def _plain(names):
    """欄位清單去掉每個 handler 都有的 event、hook、stack。"""
    return [n for n in (names or []) if n not in ("event", "hook", "stack")]


current = Decl()


def extra_kinds(defaults):
    """宣告了、預設沒有、當得了 a.bp.add.<名字> 的點（照宣告順序）。"""
    return tuple(k for k in current.points if k not in defaults and k not in SKIP and _name_ok(k))


def subject(kind):
    """宣告裡這個點的 condition（拿事件的哪個欄位比主詞）→ (a.bp.add 的參數名, 欄位)；參數名＝宣告的 subject（當得了參數名才用），不然＝欄位名。
    沒宣告這個點、沒寫 condition、或欄位名當不了參數＝None（呼叫的一方用預設）。"""
    field = (current.points.get(kind) or {}).get("condition")
    if not _name_ok(field) or field in RESERVED:
        return None
    said = current.points[kind].get("subject")
    return (said if _name_ok(said) and said not in RESERVED else field), field


def warnings(kind, event, py=None, var="ev"):
    """下斷點時的提醒（句子的串列，可能是空的）。kind＝a.bp.add 的種類、event＝實際掛的事件（tool_error 掛 after_tool）。沒載入宣告＝[]。"""
    if not current:
        return []
    out = []
    if event not in current.points:
        out.append("%s is not in the loaded hook declarations (hooks lists them); added anyway" % event)
        return out
    fields = current.fields(event)
    if fields is None or py is None:
        return out
    bad = [f for f in py_fields(py, var) if f not in fields]
    if bad:
        out.append("the py condition reads %s, not declared in the input of %s (declared: %s); added anyway"
                   % (", ".join("ev[%r]" % f for f in bad), event, ", ".join(_plain(fields)) or "-"))
    return out


def py_fields(py, var="ev"):
    """py 條件讀了事件的哪些最上層欄位（ev["x"]、ev.get("x")）；猜的，猜不到的不算。py＝函式或運算式字串（變數 var）。"""
    if isinstance(py, str):
        try:
            code = compile(py, "<condition>", "eval")
        except SyntaxError:
            return []
    elif isinstance(py, types.FunctionType):
        code = py.__code__
        if code.co_argcount < 1:
            return []
        var = code.co_varnames[0]
    else:
        return []
    out = []
    _scan(code, var, out)
    return out


def _scan(code, var, out):
    ins = list(dis.get_instructions(code))
    for i, x in enumerate(ins):
        if x.opname.startswith("LOAD_") and x.argval == var and x.opname not in ("LOAD_CONST", "LOAD_ATTR"):
            nxt = ins[i + 1:i + 3]
            if len(nxt) == 2 and nxt[0].opname == "LOAD_CONST" and isinstance(nxt[0].argval, str) \
                    and (nxt[1].opname.startswith("BINARY_SUBSCR") or nxt[1].opname == "BINARY_OP"):
                f = nxt[0].argval
            elif len(nxt) == 2 and nxt[0].opname in ("LOAD_ATTR", "LOAD_METHOD") and nxt[0].argval == "get" \
                    and nxt[1].opname == "LOAD_CONST" and isinstance(nxt[1].argval, str):
                f = nxt[1].argval
            else:
                continue
            if f not in out:
                out.append(f)
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            _scan(c, var, out)


def layout(event, kind, where=""):
    """一個事件排成給人看的幾行：有宣告這個點＝宣告的欄位照順序、帶 description，沒宣告的欄位另列；沒宣告＝照事件原本的順序。"""
    point = current.points.get(kind) if current else None
    props = (point or {}).get("input", {}).get("properties")
    props = props if isinstance(props, dict) else {}
    std = [k for k in ("event", "hook", "stack") if k in event]           # 每個 handler 都有的三鍵：排最前、不算「沒宣告」
    keys = std + [k for k in props if k in event and k not in std] + [k for k in event if k not in props and k not in std]
    head = "event %s%s" % (kind, where)
    head += "; fields in the order the declaration gives" if props else \
        ("; %s is not in the loaded hook declarations" % kind if current else "")
    w = max([len(k) for k in keys] + [4])
    lines = [head]
    for k in keys:
        v = json.dumps(event[k], ensure_ascii=False)
        if len(v) > WIDTH:
            v = v[:WIDTH] + "..."
        note = props.get(k, {}).get("description") if isinstance(props.get(k), dict) else None
        tail = "   # %s" % note if note else ("   # not declared" if props and k not in props and k not in std else "")
        lines.append("  %s  %s%s" % (k.ljust(w), v, tail))
    missing = [k for k in _plain(list(props)) if k not in event]
    if missing:
        lines.append("  (declared but not in this event: %s)" % ", ".join(missing))
    return "\n".join(lines)
