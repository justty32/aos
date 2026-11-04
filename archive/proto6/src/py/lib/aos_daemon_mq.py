"""aos-daemon 的訊息模組：伺服器端（plan m3m-daemon-modules.md 模組四；使用者 2026-10-02 第二十五批改成多扇門）。

設定檔寫了 `"modules": {"mq": {"<門名>": "<路徑>", …}}` 時，`aos_daemon.main()` 每扇門叫一次 `serve()`：
每扇門一個 unix socket（不走控制 socket），協議照控制模組——一連線一請求、一行 JSON 來、一行 JSON 回。
每一項一個信箱，放記憶體、先進先出，daemon 重開就丟。每項設定的 `"mq": ["<門名>", …]` 是它訂了哪幾扇門。

- 寄：`{"send": <任何 JSON 值>}` → `{"ok":true}`。信＝寄的 JSON 原樣，daemon 不加任何欄位；放進**訂了這扇門**的
  每一項的信箱（寄件人自己有訂也收，不排除），並照現有急件規則叫醒它們（合併叫醒：待補跑是一個布林，
  叫幾次都只補一次；正在跑就跑完補一次、暫停中跑一次、已停不跑）。沒人訂就丟掉、照回 ok。
- 取：`{"take":"<inst>"}` → `{"ok":true,"messages":[<信>,…]}`，那一項全部的信取走；任何一扇門都行。
- 看：`{"peek":"<inst>"}`，回應同取，但信不取走。
- daemon 不驗身分（能連就能做，報別項的名字也照給）；誰能連由 socket 所在資料夾的權限決定，socket 檔本身一律 666。
- take／peek 的 inst 不在清單上回 `unknown_inst`；格式不對回 `bad_request`（只影響那一條連線）。其餘欄位一律忽略。

〔使用者 2026-10-02 第二十五批〕取代第十四、十五批的篩選（`--from`）、第二十一批的 `from_socket`、
第二十二批的廣播／頻道／`to`／`delivered`、急件 `urgent`。POC 默認一切正常：不設上限、不確認送達。
"""
import copy
import json
import os
import re

import aos_daemon
from aos_daemon_ctl import BadRequest, _want, serve as _serve

COMMANDS = ("send", "take", "peek")
DOOR_NAME = re.compile(r"[A-Za-z0-9_]+\Z")


def serve(name, path, items):
    """開一扇門：name＝門名、path＝絕對路徑、items＝daemon 的 {inst: Item}。"""
    _serve(path, items, lambda line, its: handle(parse(line), its, name))


def doors_of(conf, start, ctl_sock=None):
    """`modules.mq` → {門名: 絕對路徑}（照寫的順序）。相對路徑以起點為準。不合丟 ValueError（設定錯）：
    不是物件、沒有門、門名不是英數底線、路徑不是非空字串、兩扇門同一個檔、跟控制 socket 同一個檔。"""
    if not isinstance(conf, dict) or not conf:
        raise ValueError('modules.mq 要是 {"<門名>": "<socket 路徑>", …}，至少一扇門')
    doors, seen = {}, {}
    if ctl_sock is not None:
        seen[ctl_sock] = "modules.control.socket"
    for name, path in conf.items():
        if not DOOR_NAME.match(name):
            raise ValueError("modules.mq 的門名只能用英數與底線：%s" % json.dumps(name, ensure_ascii=False))
        if not isinstance(path, str) or not path:
            raise ValueError("modules.mq.%s 要是非空字串（socket 路徑）" % name)
        full = os.path.abspath(os.path.join(start, path))
        if full in seen:
            raise ValueError("modules.mq.%s 跟 %s 是同一個檔：%s" % (name, seen[full], full))
        seen[full] = "modules.mq." + name
        doors[name] = full
    return doors


def item_doors(entry, doors):
    """一項設定的 `mq`（門名的陣列）→ 去重後的門名 list。沒寫＝[]；格式不對、寫了沒有的門＝ValueError。"""
    m = entry.get("mq")
    if m is None:
        return []
    if not isinstance(m, list) or not all(isinstance(x, str) for x in m):
        raise ValueError('insts 某項的 mq 要是門名的陣列（例如 ["SOCKET_1"]）')
    out = []
    for name in m:
        if name not in doors:
            raise ValueError("insts 某項的 mq 寫了 modules.mq 裡沒有的門：%s" % json.dumps(name, ensure_ascii=False))
        if name not in out:
            out.append(name)
    return out


def parse(line):
    """一行 → (指令名, 值)。格式不對丟 BadRequest。"""
    try:
        req = json.loads(line.decode("utf-8"))
    except (ValueError, RecursionError):     # RecursionError＝巢得太深
        raise BadRequest("不是 JSON")
    if not isinstance(req, dict):
        raise BadRequest("不是 JSON 物件")
    names = [c for c in COMMANDS if c in req]
    if len(names) != 1:
        raise BadRequest("指令名要剛好一個（%s 之一）" % "／".join(COMMANDS))
    cmd = names[0]
    value = req[cmd]
    if cmd != "send" and not isinstance(value, str):
        raise BadRequest("%s 的值要是字串（inst 字面值）" % cmd)
    return cmd, value


def handle(request, items, door):
    """door＝收到請求的那扇門的門名（寄的時候決定收件人）。"""
    cmd, value = request
    if cmd in ("take", "peek"):
        item = items.get(value)
        if item is None:
            return {"ok": False, "error": "unknown_inst", "detail": value}
        with item.cond:
            got = item.mailbox
            if cmd == "take":
                item.mailbox = []
            else:
                got = list(got)
        return {"ok": True, "messages": got}
    with aos_daemon._items_lock:        # 重讀設定會原地改清單
        targets = [i for i in items.values() if door in i.doors]
    for item in targets:
        with item.cond:
            item.mailbox.append(copy.deepcopy(value))   # 每個信箱各自一份
            if not item.stopped:
                _want(item, False)
                item.cond.notify_all()
    return {"ok": True}
