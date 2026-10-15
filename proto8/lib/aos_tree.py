#!/usr/bin/env python3
"""inst 樹工具（同像性，thinking 2026-10-15-homoiconic）：把一棵 aos 程式樹畫出來，或把路徑全攤成一份 JSON。純標準庫。

    python3 aos_tree.py print  TARGET [--depth N]     畫樹：每行 `位置: 種類 id`
    python3 aos_tree.py inline TARGET [--depth N]     stdout 一份自含的 JSON（所有以路徑參照的 inst 都攤成物件）

TARGET 同 aos_inst（檔、資料夾、可接 `#/位置`）。只動純資料、不跑任何東西、不改任何執行期程式。

只看位置（決定 5）：fsm 的 `states` 格（字串／物件／`{"val"}`）、loop／daemon 的 `inst`、daemon 的 `children`、
gate 的 `target`、agent 的 `brain`／`tools`／`judge`。別的 key 一律當資料，不跟進。
id（決定 1，永不為 null）：路徑參照＝realpath（`#/位置`）；內嵌＝外層 id 接 `#/位置`（例 `外層#/states/think`）；
整棵從 dict 來沒有檔＝`sha256:內容雜湊` 當外層 id。
路徑（決定 2）：找子 inst 的名字（槽位裡的字串、檔裡的指示詞）從**那份檔所在的資料夾**算；從 dict 來的從呼叫者 cwd 算。
葉子 inst 自己的路徑（argv、cwd、串流）原樣不動——照 aos_inst 一律是執行時的 cwd 算，攤平不改它們（所以攤成一份也照樣跑）。
循環（決定 3）：同一個 id 已在這條路徑上＝停、留原名字不攤，那個 node 是 `ref`、帶 `"stop": "TreeCycle"`（print 那行尾巴寫 `(TreeCycle)`）。
深度（決定 4）：`--depth N`（預設 16）超過的同樣留名字不攤，`"stop": "TreeDepth"`。攤出來的路徑參照那份加 `id`（原 id，沒寫才補）。
兩種都是預料到的正常狀況（遞迴的表），照樣退 0、不寫 stderr（N-43；10-15 使用者「都按照推薦。」，原本 stderr 吐 warning）。
API：`build(x, depth=16, warn=None)` → (樹 node, 攤好的 doc)；x＝TARGET 字串或 dict。node＝{"id", "kind", "label", "kids": [node]}
（停住的 ref 多 `stop`）；warn(code, msg) 想另外收停住的原因可以給，命令列不給。
"""
import copy
import hashlib
import json
import os
import sys

import aos_cli
import aos_inst
from aos_cli import CliError
from aos_directives import DirectiveError, locate, resolve, split_target, target_id

__all__ = ["build", "main", "render", "slots"]


def slots(doc):
    """doc 裡所有「要跑的 inst」的位置：[(path tuple, 標籤)]，只收字串或物件。"""
    out = []
    ok = lambda v: isinstance(v, (str, dict))
    for n, v in (doc.get("states") if isinstance(doc.get("states"), dict) else {}).items():
        if isinstance(v, dict) and "val" in v:
            if ok(v["val"]):
                out.append((("states", n, "val"), "states/" + n))
        elif ok(v):
            out.append((("states", n), "states/" + n))
    for k in ("inst", "target", "brain", "judge"):
        if ok(doc.get(k)):
            out.append(((k,), k))
    for i, v in enumerate(doc.get("children") if isinstance(doc.get("children"), list) else []):
        if ok(v):
            out.append((("children", i), "children/%d" % i))
    for n, v in (doc.get("tools") if isinstance(doc.get("tools"), dict) else {}).items():
        if ok(v):
            out.append((("tools", n), "tools/" + n))
    return out


def _kind(doc):
    ks = [k for key, k in (("states", "fsm"), ("brain", "agent"), ("children", "daemon"), ("inst", "loop"),
                           ("target", "gate"), ("judge", "kernel")) if key in doc]
    return "+".join(ks) or "inst"


def _child_id(ident, path):
    return ident + ("/" if "#" in ident else "#/") + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in path)


def _load(target, base):
    """字串 TARGET（相對檔從 base 算）→ (doc, id)。指示詞解不出環境變數（`$env`）時留原樣當資料：看樹不需要執行期的環境。"""
    file, pos = split_target(target)
    real = aos_inst._file(file if os.path.isabs(file) else os.path.join(base, file))
    try:
        with open(real, encoding="utf-8") as f:
            root = json.load(f)
        old = os.getcwd()
        try:
            os.chdir(os.path.dirname(real))          # 指示詞的相對檔名從那份檔的資料夾算
            try:
                doc = resolve(root, os.getcwd(), real, pos)
            except DirectiveError as e:
                if e.code != "EnvironmentVariableMissing":
                    raise
                doc = locate(root, pos, real)
        finally:
            os.chdir(old)
    except (OSError, ValueError) as e:
        raise CliError("ReferenceReadFailed", "讀不了 %s：%s" % (real, e))
    except DirectiveError as e:
        raise CliError(e.code, e.msg)
    ident = target_id(real, pos)
    if not isinstance(doc, dict):
        raise CliError("FieldType", "%s 要是物件" % ident)
    return doc, ident


def build(x, depth=16, warn=None):
    """x＝TARGET 字串或 dict → (樹 node, 攤好的 doc)。warn(code, msg) 收警告（沒給＝丟掉）。"""
    warn = warn or (lambda c, m: None)
    if isinstance(x, str):
        doc, ident = _load(x, os.getcwd())
        base = os.path.dirname(ident.partition("#")[0])
        return _walk(doc, ident, base, (ident,), depth, warn, "", True)
    ident = "sha256:" + hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]
    try:
        x = resolve(x, os.getcwd(), ident)
    except DirectiveError as e:
        raise CliError(e.code, e.msg)
    return _walk(x, ident, os.getcwd(), (ident,), depth, warn, "", False)


def _walk(doc, ident, base, stack, depth, warn, label, from_path):
    out = copy.deepcopy(doc)
    node = {"id": ident, "kind": _kind(doc), "label": label, "kids": []}
    for path, lab in slots(doc):
        v = doc
        for p in path:
            v = v[p]
        cur = out
        for p in path[:-1]:
            cur = cur[p]
        if isinstance(v, str):
            try:
                sub, sid = _load(v, base)
            except CliError as e:
                raise CliError(e.code, "%s 的 %s：%s" % (ident, lab, e.msg))
            if sid in stack or len(stack) > depth:
                warn("TreeCycle" if sid in stack else "TreeDepth",
                     "%s 的 %s 指向 %s：%s，留名字不攤" % (ident, lab, sid, "已在這條路徑上（循環）" if sid in stack else "超過深度 %d" % depth))
                node["kids"].append({"id": sid, "kind": "ref", "label": lab, "kids": [],
                                     "stop": "TreeCycle" if sid in stack else "TreeDepth"})
                continue
            sbase = os.path.dirname(sid.partition("#")[0])
            kid, kdoc = _walk(sub, sid, sbase, stack + (sid,), depth, warn, lab, True)
        else:
            sid = _child_id(ident, path)
            kid, kdoc = _walk(v, sid, base, stack, depth, warn, lab, False)
        node["kids"].append(kid)
        cur[path[-1]] = kdoc
    if from_path:
        out.setdefault("id", ident)
    return node, out


def render(node, indent=0):
    """樹 node → 縮排的多行文字。"""
    head = "%s%s%s %s" % ("  " * indent, node["label"] + ": " if node["label"] else "", node["kind"], node["id"])
    if node.get("stop"):
        head += " (%s)" % node["stop"]
    return "\n".join([head] + [render(k, indent + 1) for k in node["kids"]])


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    depth = 16
    try:
        if "--depth" in args:
            i = args.index("--depth")
            depth = int(args[i + 1])
            del args[i:i + 2]
        if len(args) != 2 or args[0] not in ("print", "inline"):
            raise CliError("Usage", "用法：aos_tree.py print|inline TARGET [--depth N]")
        node, doc = build(args[1], depth)
        if args[0] == "print":
            print(render(node))
        else:
            aos_cli.emit(doc)
        return 0
    except (CliError, ValueError, IndexError) as e:
        aos_cli.error(getattr(e, "code", "Usage"), getattr(e, "msg", str(e)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
