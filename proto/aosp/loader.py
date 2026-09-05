"""載入器：把頂層 <名>.aos.json 原稿變成 .aos/program/<名>.json 模板。

原型第一版：原稿＝模板同格式，只做嚴格檢查＋抄過去。拆平（把巢狀結構攤成步陣列）
先不做，記進 FINDINGS。
"""
import glob
import os

from . import fsutil

KINDS = ("inst", "call", "await")


class ParseError(Exception):
    """嚴格解析失敗，對應退出碼 3。"""


def _need(obj, key, where):
    if key not in obj:
        raise ParseError("%s 少了 `%s`" % (where, key))
    return obj[key]


def check_program(prog, where="模板"):
    if not isinstance(prog, dict):
        raise ParseError("%s 不是物件" % where)
    if prog.get("format_version") != 1:
        raise ParseError("%s 的 `format_version` 必須是 1" % where)
    name = _need(prog, "name", where)
    steps = _need(prog, "steps", where)
    if not isinstance(steps, list) or not steps:
        raise ParseError("%s 的 `steps` 必須是非空陣列" % where)
    seen = set()
    for i, s in enumerate(steps):
        w = "%s 第 %d 步" % (where, i + 1)
        if not isinstance(s, dict):
            raise ParseError("%s 不是物件" % w)
        sname = _need(s, "name", w)
        if sname in seen:
            raise ParseError("%s 步名 `%s` 重複" % (where, sname))
        seen.add(sname)
        kind = _need(s, "kind", w)
        if kind not in KINDS:
            raise ParseError("%s 的 `kind` 是 `%s`，只認得 %s" % (w, kind, "／".join(KINDS)))
        if kind == "inst":
            inst = _need(s, "inst", w)
            if not isinstance(inst, dict):
                raise ParseError("%s 的 `inst` 不是物件" % w)
            argv = _need(inst, "argv", w + " 的 inst")
            if not isinstance(argv, list) or not argv:
                raise ParseError("%s 的 `argv` 必須是非空陣列" % w)
        elif kind == "call":
            _need(s, "child", w)
            mode = _need(s, "mode", w)
            if mode not in ("sync", "async"):
                raise ParseError("%s 的 `mode` 必須是 sync 或 async" % w)
            _need(s, "result", w)
        elif kind == "await":
            _need(s, "result", w)
    for s in steps:
        for key in ("then", "on_fail"):
            tgt = s.get(key)
            if tgt is not None and tgt != "end" and tgt not in seen:
                raise ParseError("步 `%s` 的 `%s` 指向不存在的步名 `%s`" % (s["name"], key, tgt))
    return prog


def compile_source(land, name="main"):
    """讀 <名>.aos.json，寫 .aos/program/<名>.json。回傳模板。"""
    src_path = land.source(name)
    src = fsutil.read_json(src_path)
    if src is None:
        raise ParseError("找不到原稿 %s" % src_path)
    if isinstance(src, dict) and "name" not in src:
        src = dict(src, name=name)
    check_program(src, "原稿 %s" % os.path.basename(src_path))
    out = land.program(src["name"])
    fsutil.write_json(out, src)
    return src


def compile_all(land):
    """把地上所有 *.aos.json 都編一次。"""
    names = []
    for p in sorted(glob.glob(os.path.join(land.root, "*.aos.json"))):
        base = os.path.basename(p)[: -len(".aos.json")]
        compile_source(land, base)
        names.append(base)
    return names


def load_program(land, name, auto_compile=True):
    """拿模板；沒有就從原稿編一份。"""
    prog = fsutil.read_json(land.program(name))
    if prog is None and auto_compile:
        prog = compile_source(land, name)
    if prog is None:
        raise ParseError("找不到模板 `%s`（也沒有 %s.aos.json）" % (name, name))
    return check_program(prog, "模板 %s" % name)


def step_by_name(prog, name):
    for s in prog["steps"]:
        if s["name"] == name:
            return s
    return None


def next_step_name(prog, cur_name):
    steps = prog["steps"]
    for i, s in enumerate(steps):
        if s["name"] == cur_name:
            return steps[i + 1]["name"] if i + 1 < len(steps) else "end"
    return "end"
