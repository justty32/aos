"""aos_json_multi - json_multi_get／json_multi_set：一次多格，逐格照 json_get／json_set 做、照順序、一格一行「路徑 TAB 結果」，不回滾。

使用者 11-11「有需要的話，可以提供工具json_multi_get/set」、11-12「一次讀寫多格、複雜組的json工具可以做。」（thinking 2026-11/12/json-tools/03）。
每格各自叫 aos-json（同一份檔多格就是多次原子寫入，前面的成功不因後面失敗而撤回）；某格錯＝那一行寫 `[error] 代號 原因`、其他格照做；
有任何一格錯，最後印 `json_multi_*: error: PlacesFailed N of M ...`、退 1（lib 契約：有錯誤行不退 0）。整批的參數錯（paths／items 不是非空陣列）不做任何一格。"""
import aos_json
import tool_io


def main(op):
    name = "json_multi_" + op
    aos_json.start(name)
    key = "paths" if op == "get" else "items"
    args = tool_io.arguments()                  # arguments(key) 只收字串，這裡的 key 是陣列，自己查
    entries = args.get(key)
    if not isinstance(entries, list) or not entries:
        tool_io.die("ArgumentsBad", "%s must be a non-empty array" % key)
    if op == "get":
        aos_json.limit(args, "max_bytes", "AOS_JSON_MAX_BYTES", aos_json.MAX_BYTES)   # 整批的參數錯先報、一格都不做
    lines, failed = [], 0
    aos_json.MULTI = True
    try:
        for entry in entries:
            path = entry.get("path") if isinstance(entry, dict) else entry
            try:
                out = one(op, entry, args)
            except aos_json.Failed as e:
                out, failed = "[error] %s %s" % (e.code, e.reason), failed + 1
            lines.append("%s\t%s" % (path if isinstance(path, str) else aos_json.compact(path), out))
    finally:
        aos_json.MULTI = False
    text = "\n".join(lines)
    if failed:
        tool_io.die("PlacesFailed", "%d of %d places failed (lines with [error] above); the others were done, nothing was undone"
                    % (failed, len(entries)), before=text + "\n")
    print(text)


def one(op, entry, args):
    if op == "get":
        if not isinstance(entry, str) or not entry:
            aos_json.die("ArgumentsBad", "each path must be a non-empty string FILE#/POINTER")
        return aos_json.do_get(args, aos_json.Target(entry), [])
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]:
        aos_json.die("ArgumentsBad", 'each item must be {"path": "FILE#/POINTER", "value": ...}')
    if "value" not in entry:
        aos_json.die("ArgumentsBad", "missing value (any JSON)")
    extra = set(entry) - {"path", "value"}
    if extra:
        aos_json.die("ArgumentsBad", "unknown key in item: %s (only path and value)" % ", ".join(sorted(extra)))
    return aos_json.do_set({"value": entry["value"], "parents": args.get("parents")}, aos_json.Target(entry["path"]), False)
