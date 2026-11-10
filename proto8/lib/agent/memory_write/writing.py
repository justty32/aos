"""memory_write 的三個動作：add／set／rm 一次把內容與它在表（_index.json 或 _index key）裡的那格一起維護；寫到哪都行，能不能成看檔案權限。

圖紙 proto8/thinking/2026-11/10/json-memory/03（使用者 11-10 晚：新增刪除工具一次做完兩處「A」；同時寫「不管，自行承擔風險」＝不加鎖；
寫入「想怎麽寫就怎麼寫，有權限就能動」＝不限庫根底下，失敗＝WriteFailed）。
自己的簡介（資料夾的 _description.json、物件的 _description key）當普通路徑寫：值要是字串、不帶 description、不進表。
add 不給 value（使用者 11-10 深夜）：目標已在＝只補表裡那格；不在＝NodeMissing、什麼都不寫；create: true＝建空的再補格。
JSON 的寫交給 aos-json（set、同檔兩處用 batch --parents、del；每份檔暫存後原子 rename）；非 .json 檔照原文由這裡原子寫。
寫的路上不穿 $ref（不給 --follow）：路上碰到指示詞＝TargetBad，要改就直接寫它指到的那份檔。
新增要動兩份檔時先寫內容再寫表：中途死掉＝留下沒登記的東西（ls 的 not in index: 看得到）；刪除也是先刪內容再拔格。
錯誤 raise tool_io.Error，由 _entry 轉成錯誤行。"""
import json
import os
import shutil
import stat
import tempfile

import memory_fs as fs
from tool_io import Error

MAX_BYTES = 8000
MISSING = object()


def is_intro(loc, folder=False):
    """這個位置是不是某個地方自己的簡介：資料夾的 _description.json、物件的 _description key。"""
    if loc.tokens is None:
        return not folder and os.path.basename(loc.fs) == fs.DESC_FILE
    return loc.tokens[-1] == fs.DESC_KEY


def check_intro(has_value, value):
    if has_value and not isinstance(value, str):
        raise Error("ValueBad", "a description (_description.json or a _description key) must be one string")


def check_name(name):
    if not name or name in (".", "..") or name.startswith((".", "_")):
        raise Error("PathBad", "%r cannot be added: names starting with . or _ are reserved "
                    "(except _description.json and the _description key)" % name)


def encode(fs_path, value):
    """要寫進檔的文字；.json＝JSON，其他副檔名＝value 要是字串、照原文。超過 8000 bytes＝ValueBad。"""
    if fs_path.endswith(".json"):
        text = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, str):
        text = value
    else:
        raise Error("ValueBad", "%s is not a .json file, so value must be a string" % os.path.basename(fs_path))
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise Error("ValueBad", "value is over %d bytes; split it into several keys or files" % MAX_BYTES)
    return text


def check_value(value):
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise Error("ValueBad", "value is over %d bytes; split it into several keys or files" % MAX_BYTES)


def write_file(fs_path, value):
    text = encode(fs_path, value)
    if fs_path.endswith(".json"):
        fs.aos_json(["set", fs_path], text, "WriteFailed")
        return
    target = os.path.realpath(fs_path)
    fd, temporary = tempfile.mkstemp(prefix=".tmp.", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if os.path.exists(target):
                mode = stat.S_IMODE(os.stat(target).st_mode)
            else:                               # 新檔照 umask（mkstemp 預設 0600）
                mask = os.umask(0)
                os.umask(mask)
                mode = 0o666 & ~mask
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
        os.replace(temporary, target)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def raw_file(fs_path):
    """整份檔的原文 JSON（不解指示詞）；檔不在＝NodeMissing、不是 .json＝TargetBad。"""
    if not fs_path.endswith(".json"):
        raise Error("TargetBad", "%s is not a .json file; # only goes inside a .json file" % os.path.basename(fs_path))
    return fs.get(fs.Loc(fs_path, None))


def walk_raw(root, loc, data, tokens):
    """在原文裡照 tokens 走；路上碰到指示詞＝TargetBad，沒有＝MISSING。"""
    value = data
    for i, t in enumerate(tokens):
        if isinstance(value, dict) and ("$ref" in value or "$env" in value):
            raise Error("TargetBad", "%s is a $ref or $env; write to the file it points to instead"
                        % fs.show(root, fs.Loc(loc.fs, tokens[:i] or None)))
        if isinstance(value, dict) and t in value:
            value = value[t]
        elif isinstance(value, list) and t.isdigit() and int(t) < len(value):
            value = value[int(t)]
        else:
            return MISSING
    return value


def cell_key(table, base, inside, loc, default):
    """表裡指到 loc 的那格的 key；沒有＝default。"""
    for c in fs.cells(base, table, inside):
        if c.target == loc:
            return c.key
    return default


def folder_cell(root, folder, loc, description=None, remove=False):
    """資料夾的 _index.json：加／換說明（description）或拔掉（remove）指到 loc 的那格；檔不在就建。"""
    index = os.path.join(folder, "_index.json")
    exists = os.path.isfile(index)
    table = fs.folder_table(folder, raw_file) if exists else {}
    name = os.path.basename(loc.fs) + ("/" if os.path.isdir(loc.fs) else "")
    key = cell_key(table, fs.Loc(folder, None), False, loc, name)
    if remove:
        if key in table:
            fs.aos_json(["del", index + "#/" + fs.esc(key)], "", "WriteFailed")
    elif not exists:
        fs.aos_json(["set", index], json.dumps({key: {"_description": description}}, ensure_ascii=False), "WriteFailed")
    elif isinstance(table.get(key), dict):
        fs.aos_json(["set", index + "#/" + fs.esc(key) + "/_description"], json.dumps(description, ensure_ascii=False), "WriteFailed")
    else:
        fs.aos_json(["set", index + "#/" + fs.esc(key)], json.dumps({"_description": description}, ensure_ascii=False), "WriteFailed")


def missing_folder(root, loc):
    """add 時上一層資料夾不在：NodeMissing 照舊附上一層有哪些，再教先開資料夾（小模型照抄出廠例子 notes/amy.json 會撞到）。"""
    parent = os.path.dirname(loc.fs)
    if os.path.lexists(parent):                 # 上一層是檔：fs.missing 會提示 file.json#/key 的寫法
        return fs.missing(root, loc)
    error = fs.missing(root, fs.Loc(parent, None))
    top = parent
    while not os.path.lexists(os.path.dirname(top)) and os.path.dirname(top) != top:
        top = os.path.dirname(top)
    if os.path.lexists(top) or not os.path.isdir(os.path.dirname(top)):
        return error                            # 路上有同名的檔：fs.missing 的提示已經說了
    folder = fs.show(root, fs.Loc(top, None)).rstrip("/") + "/"
    return Error("NodeMissing", '%s; the folder %s does not exist yet: first call {"op": "add", "path": "%s", "description": "<what goes in it>"}, then add again'
                 % (str(error), folder, folder))


def missing_file(root, loc):
    """add 物件裡的 key 而那份 .json 檔不在：教先用 value {} 開檔。"""
    error = fs.missing(root, loc)
    name = fs.show(root, fs.Loc(loc.fs, None))
    if not os.path.isdir(os.path.dirname(loc.fs)) or not loc.fs.endswith(".json"):
        return error
    return Error("NodeMissing", '%s; the file %s does not exist yet: first call {"op": "add", "path": "%s", "value": {}, "description": "<what goes in it>"}, then add again'
                 % (str(error), name, name))


def object_parent(root, loc):
    """物件裡一個 key 的上一層：回 (原文整份, 上一層物件)；不在＝NodeMissing、陣列＝TargetBad。"""
    if not os.path.isfile(loc.fs):
        raise fs.missing(root, loc)
    data = raw_file(loc.fs)
    parent = walk_raw(root, loc, data, loc.tokens[:-1])
    if parent is MISSING:
        raise fs.missing(root, fs.Loc(loc.fs, loc.tokens[:-1] or None))
    if isinstance(parent, list):
        raise Error("TargetBad", "arrays have no index; add and rm only work on objects (use set to change an item)")
    if not isinstance(parent, dict) or "$ref" in parent or "$env" in parent:
        raise Error("TargetBad", "%s is not an object" % fs.show(root, fs.Loc(loc.fs, loc.tokens[:-1] or None)))
    return data, parent


def object_cell(root, loc, parent, description):
    """batch 用：上一層 _index 裡指到 loc 的那格換說明的 {指標: 值}。"""
    up = loc.tokens[:-1]
    table = parent.get("_index") if isinstance(parent.get("_index"), dict) else {}
    key = cell_key(table, fs.Loc(loc.fs, up or None), True, loc, fs.esc(loc.tokens[-1]))   # 表的 key 是相對路徑：/ 寫成 ~1
    if isinstance(table.get(key), dict):
        return {fs.pointer(up + ("_index", key, "_description")): description}
    return {fs.pointer(up + ("_index", key)): {"_description": description}}


def batch(fs_path, changes):
    fs.aos_json(["batch", "--parents", fs_path], json.dumps(changes, ensure_ascii=False), "WriteFailed")


def folder_registered(folder, loc):
    """資料夾的 _index.json 裡已經有指到 loc 的格嗎。"""
    if not os.path.isfile(os.path.join(folder, "_index.json")):
        return False
    return cell_key(fs.folder_table(folder, raw_file), fs.Loc(folder, None), False, loc, None) is not None


def no_value(root, loc, create, description):
    """add 不給 value、目標又不在：create＝建空的（非 .json 檔＝空檔，.json 檔與 key＝空字串 ""），否則 NodeMissing、什麼都不寫（使用者 11-10 深夜「報錯」）。"""
    if create:
        return ""
    here = fs.show(root, loc)
    with_value = {"op": "add", "path": here, "description": description, "value": "<the content>"}
    empty = {"op": "add", "path": here, "description": description, "create": True}
    raise Error("NodeMissing", "%s does not exist, so there is nothing to put in the index; give value to write it, like %s, "
                "or make it empty, like %s" % (here, json.dumps(with_value, ensure_ascii=False), json.dumps(empty, ensure_ascii=False)))


def add(root, loc, folder, has_value, value, description, create=False):
    """新增：資料夾（folder＝path 以 / 結尾，帶空的 _index.json）、新檔、或物件裡新 key；都同時在表裡加一格。
    不給 value：目標已在（沒登記）＝只補表裡那格、內容不動；不在＝NodeMissing，create＝建空的再補格（11-10 深夜）。"""
    intro = is_intro(loc, folder)
    if intro:
        check_intro(has_value, value)
    if loc.tokens is None:
        if not intro:
            check_name(os.path.basename(loc.fs))
        parent = os.path.dirname(loc.fs)
        if not os.path.isdir(parent):
            raise missing_folder(root, loc)
        exists = os.path.lexists(loc.fs)
        if exists and (intro or folder or has_value):
            raise Error("NodeExists", "%s already exists; use set to change it" % fs.show(root, loc)
                        + ("" if intro or folder else " (set with description also puts it in the index)"))
        if folder:
            if has_value and value not in (None, ""):   # 小模型常給 "value": null 或 ""，當作沒給
                raise Error("ValueBad", "a folder takes no value; add files into it afterwards")
            os.mkdir(loc.fs)
            fs.aos_json(["set", os.path.join(loc.fs, "_index.json")], "{}", "WriteFailed")
        elif intro:
            if not has_value:
                raise Error("ValueBad", "value is required")
            write_file(loc.fs, value)
        elif exists:                            # 不給 value、已經在：只補表裡那格，內容不動（11-10 深夜）
            if folder_registered(parent, loc):
                raise Error("NodeExists", "%s already exists and is in the index; use set to change its value or description"
                            % fs.show(root, loc))
        else:
            write_file(loc.fs, value if has_value else no_value(root, loc, create, description))
        if not intro:
            folder_cell(root, parent, loc, description)
        return
    if not intro:
        check_name(loc.tokens[-1])
    if intro and not has_value:
        raise Error("ValueBad", "value is required")
    if has_value:
        check_value(value)
    if not os.path.lexists(loc.fs):
        raise missing_file(root, loc)
    _, parent = object_parent(root, loc)
    exists = loc.tokens[-1] in parent
    if exists and (intro or has_value):
        raise Error("NodeExists", "%s already exists; use set to change it" % fs.show(root, loc)
                    + ("" if intro else " (set with description also puts it in the index)"))
    changes = {}
    if exists:                                  # 不給 value、已經在：只補表裡那格
        table = parent.get("_index") if isinstance(parent.get("_index"), dict) else {}
        if cell_key(table, fs.Loc(loc.fs, loc.tokens[:-1] or None), True, loc, None) is not None:
            raise Error("NodeExists", "%s already exists and is in the index; use set to change its value or description"
                        % fs.show(root, loc))
    else:
        changes[fs.pointer(loc.tokens)] = value if has_value else no_value(root, loc, create, description)
    if not intro:
        changes.update(object_cell(root, loc, parent, description))
    batch(loc.fs, changes)


def set_(root, loc, has_value, value, description):
    """換內容（value）、換說明（description），或兩個一起；位置要已經在。"""
    if not has_value and description is None:
        raise Error("ValueBad", "set needs value, description or both")
    if is_intro(loc):
        check_intro(has_value, value)
    if loc.tokens is None:
        if not os.path.lexists(loc.fs):
            raise fs.missing(root, loc)
        if description is not None and loc.fs == root:
            raise Error("PathBad", "the root has no index entry; its own description is _description.json (add or set it with value)")
        if has_value:
            if os.path.isdir(loc.fs):
                raise Error("TargetBad", "%s is a folder and has no value; set its files instead" % fs.show(root, loc))
            write_file(loc.fs, value)
        if description is not None:
            folder_cell(root, os.path.dirname(loc.fs), loc, description)
        return
    if not os.path.isfile(loc.fs):
        raise fs.missing(root, loc)
    data = raw_file(loc.fs)
    if walk_raw(root, loc, data, loc.tokens) is MISSING:
        raise fs.missing(root, loc)
    changes = {}
    if has_value:
        check_value(value)
        changes[fs.pointer(loc.tokens)] = value
    if description is not None:
        parent = walk_raw(root, loc, data, loc.tokens[:-1])
        if not isinstance(parent, dict):
            raise Error("TargetBad", "array items have no index entry, so no description")
        changes.update(object_cell(root, loc, parent, description))
    batch(loc.fs, changes)


def remove(root, loc, recursive):
    """刪檔／資料夾（不空要 recursive）／物件裡的 key，並拔掉表裡指到它的那格；根＝PathBad。"""
    if loc.tokens is None:
        if loc.fs == root:
            raise Error("PathBad", "the memory root cannot be removed")
        if not os.path.lexists(loc.fs):
            raise fs.missing(root, loc)
        parent = os.path.dirname(loc.fs)
        if os.path.islink(loc.fs) or not os.path.isdir(loc.fs):
            os.unlink(loc.fs)
        else:
            if any(n != "_index.json" for n in os.listdir(loc.fs)) and not recursive:
                raise Error("ChildrenExist", "%s is not empty; use recursive: true" % fs.show(root, loc))
            shutil.rmtree(loc.fs)
        if os.path.isfile(os.path.join(parent, "_index.json")):
            folder_cell(root, parent, loc, remove=True)
        return
    _, parent = object_parent(root, loc)
    if loc.tokens[-1] not in parent:
        raise fs.missing(root, loc)
    fs.aos_json(["del", fs.spec(loc)], "", "WriteFailed")
    table = parent.get("_index") if isinstance(parent.get("_index"), dict) else {}
    key = cell_key(table, fs.Loc(loc.fs, loc.tokens[:-1] or None), True, loc, fs.esc(loc.tokens[-1]))
    if key in table:
        fs.aos_json(["del", loc.fs + "#" + fs.pointer(loc.tokens[:-1] + ("_index", key))], "", "WriteFailed")
