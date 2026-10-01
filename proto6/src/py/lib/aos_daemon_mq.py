"""aos-daemon 的訊息模組：伺服器端（plan m3m-daemon-modules.md 模組四）。

設定檔寫了 `"modules": {"mq": {"socket": "<路徑>"}}` 時，`aos_daemon.main()` 叫 `serve()`：
另開一個 unix socket（不走控制 socket），協議照控制模組——一連線一請求、一行 JSON 來、一行 JSON 回。
收件人就是 daemon 的一項（`insts` 的鍵，逐字比對）；每一項一個信箱，放記憶體、先進先出，daemon 重開就丟。

- 寄：`{"send":"<收件 inst>","msg":<任何 JSON 值>,"from":"<寄件 inst>"|null,"urgent":false}` → `{"ok":true}`。
  `from`、`urgent` 可省（null、false）。`from` 原樣存、不核對（M1）。
- 取：`{"take":"<inst>"}` → `{"ok":true,"messages":[{"from":…,"msg":…},…]}`，一次全部取走（M3：不限只取自己）。
- 急件：放進信箱後照控制模組 wake（不帶選項）的規則叫醒收件那一項——正在跑就補一次、暫停中跑一次、
  已停不跑（信照樣收下、回 ok）。不用掛控制模組也做得到。
- 收件人不在清單上回 `unknown_inst`；格式不對回 `bad_request`（只影響那一條連線）。

〔使用者 2026-10-01 第十二批〕M1～M4 照 plan 建議。POC 默認一切正常：不設上限、不檢查權限、不確認送達。
"""
import json

from aos_daemon_ctl import BadRequest, _want, serve as _serve

COMMANDS = ("send", "take")


def serve(path, items):
    _serve(path, items, lambda line, its: handle(parse(line), its))


def parse(line):
    """一行 → (指令名, inst, 其餘欄位 dict)。格式不對丟 BadRequest。"""
    try:
        req = json.loads(line.decode("utf-8"))
    except ValueError:
        raise BadRequest("不是 JSON")
    if not isinstance(req, dict):
        raise BadRequest("不是 JSON 物件")
    names = [c for c in COMMANDS if c in req]
    if len(names) != 1:
        raise BadRequest("指令名要剛好一個（%s 之一）" % "／".join(COMMANDS))
    cmd = names[0]
    inst = req[cmd]
    if not isinstance(inst, str):
        raise BadRequest("%s 的值要是字串（inst 字面值）" % cmd)
    rest = {}
    if cmd == "send":                   # take 帶別的欄位一律忽略
        if "msg" not in req:
            raise BadRequest("send 要有 msg")
        rest["msg"] = req["msg"]
        rest["from"] = req.get("from")
        if rest["from"] is not None and not isinstance(rest["from"], str):
            raise BadRequest("from 要是字串或 null")
        rest["urgent"] = req.get("urgent", False)
        if not isinstance(rest["urgent"], bool):
            raise BadRequest("urgent 要是布林")
    return cmd, inst, rest


def handle(request, items):
    cmd, inst, rest = request
    item = items.get(inst)
    if item is None:
        return {"ok": False, "error": "unknown_inst", "detail": inst}
    with item.cond:
        if cmd == "take":
            got, item.mailbox = item.mailbox, []
            return {"ok": True, "messages": got}
        item.mailbox.append({"from": rest["from"], "msg": rest["msg"]})
        if rest["urgent"] and not item.stopped:
            _want(item, False)
            item.cond.notify_all()
    return {"ok": True}
