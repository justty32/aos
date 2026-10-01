"""aos-daemon 的訊息模組：伺服器端（plan m3m-daemon-modules.md 模組四）。

設定檔寫了 `"modules": {"mq": {"socket": "<路徑>"}}` 時，`aos_daemon.main()` 叫 `serve()`：
另開一個 unix socket（不走控制 socket），協議照控制模組——一連線一請求、一行 JSON 來、一行 JSON 回。
收件人就是 daemon 的一項（`insts` 的鍵，逐字比對）；每一項一個信箱，放記憶體、先進先出，daemon 重開就丟。

- 寄：`{"send":"<收件 inst>","msg":<任何 JSON 值>,"from":"<寄件 inst>"|null,"from_socket":"<寄件方訊息 socket>"|null,"urgent":false}`
  → `{"ok":true,"delivered":1}`。`from`、`from_socket`、`urgent` 可省（null、null、false）。`from`、`from_socket` 原樣存、不核對（M1）。
  跨 daemon（第二十一批）：寄件方直接連收件方 daemon 的 socket；daemon 不轉送、不知道信從哪個 daemon 來，
  只是多存一個 `from_socket`（`aos-mq send` 自動填寄件方自己的 socket），收件方要回信就照它寄回去。
- 取：`{"take":"<inst>","from":[<寄件 inst 或 null>,…]}` → `{"ok":true,"messages":[{"from":…,"from_socket":…,"to":…,"msg":…},…]}`。
  沒給 `from`＝信箱全部取走；給了＝只取寄件人在陣列裡的（`null`＝寄件人是 null 的信），其他照順序留著
  （使用者 2026-10-01 第十四批；第十五批 `from` 改成可以多個）。
- 看：`{"peek":"<inst>","from":…}`，回應同取，但信不取走（第十五批）。
- 「只能取／看自己的信箱」是 `aos-mq` 那一側做的（只用 AOS_DAEMON_INST）；daemon 不驗身分，照 POC「能連就能做」，
  直接連 socket 照樣取得到別項的（使用者 2026-10-01 第十五批 1.a；之後設計各 socket 權限時再說）。
- 廣播與頻道（第二十二批）：`{"broadcast":true,…}` 寄給這個 daemon 的每一項、`{"channel":"<名字>",…}` 只寄給
  訂了那個頻道的項（每項設定的 `"mq": {"subscribe": [...]}`），欄位同 `send`；都**不寄給寄件人自己**（`from` 等於那一項、
  而且 `from_socket` 是 null 或就是這個 daemon 的訊息 socket——跨 daemon 來的信不算自己）。沒人收也回 ok。
  每封信多一個 `to`：單寄是收件 inst、全體是 `"*"`、頻道是 `"#<名字>"`。寄的回應 `{"ok":true,"delivered":<收到的項數>}`。
  `take`／`peek` 多一個 `to` 篩選（非空陣列，同 `from`）。
- 急件：放進信箱後照控制模組 wake（不帶選項）的規則叫醒收件那一項——正在跑就補一次、暫停中跑一次、
  已停不跑（信照樣收下、回 ok）。不用掛控制模組也做得到。
- 收件人不在清單上回 `unknown_inst`；格式不對回 `bad_request`（只影響那一條連線）。

〔使用者 2026-10-01 第十二批〕M1～M4 照 plan 建議。POC 默認一切正常：不設上限、不檢查權限、不確認送達。
"""
import copy
import json

import aos_daemon
from aos_daemon_ctl import BadRequest, _want, serve as _serve

SEND = ("send", "broadcast", "channel")         # 寄的三種（第二十二批）
COMMANDS = SEND + ("take", "peek")


def serve(path, items):
    _serve(path, items, lambda line, its: handle(parse(line), its, path))


def item_subscribe(entry):
    """第二十二批：一項設定的 `mq.subscribe`（頻道名的陣列）。沒寫＝[]；格式不對＝設定錯（ValueError）。"""
    m = entry.get("mq")
    if m is None:
        return []
    if not isinstance(m, dict):
        raise ValueError("insts 某項的 mq 要是物件")
    subs = m.get("subscribe", [])
    if not isinstance(subs, list) or not all(isinstance(x, str) and x for x in subs):
        raise ValueError("mq.subscribe 要是非空字串的陣列")
    return list(subs)


def _filter(req, key):
    want = req.get(key)
    if want is not None:
        if not isinstance(want, list) or not want:
            raise BadRequest("%s 要是非空陣列（元素是字串或 null）" % key)
        if not all(w is None or isinstance(w, str) for w in want):
            raise BadRequest("%s 的元素要是字串或 null" % key)
    return want


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
    if cmd == "broadcast":
        if inst is not True:
            raise BadRequest("broadcast 的值要是 true")
    elif cmd == "channel":
        if not isinstance(inst, str) or not inst:
            raise BadRequest("channel 的值要是非空字串（頻道名）")
    elif not isinstance(inst, str):
        raise BadRequest("%s 的值要是字串（inst 字面值）" % cmd)
    rest = {}
    if cmd in ("take", "peek"):         # 只看 from、to（篩選）；msg、urgent 忽略
        rest["from"] = _filter(req, "from")
        rest["to"] = _filter(req, "to")
    if cmd in SEND:
        if "msg" not in req:
            raise BadRequest("send 要有 msg")
        rest["msg"] = req["msg"]
        rest["from"] = req.get("from")
        if rest["from"] is not None and not isinstance(rest["from"], str):
            raise BadRequest("from 要是字串或 null")
        rest["from_socket"] = req.get("from_socket")
        if rest["from_socket"] is not None and not isinstance(rest["from_socket"], str):
            raise BadRequest("from_socket 要是字串或 null")
        rest["urgent"] = req.get("urgent", False)
        if not isinstance(rest["urgent"], bool):
            raise BadRequest("urgent 要是布林")
    return cmd, inst, rest


def handle(request, items, own=None):
    """own＝這個 daemon 的訊息 socket 絕對路徑（判斷「寄件人自己」用）。"""
    cmd, inst, rest = request
    if cmd in ("take", "peek"):
        item = items.get(inst)
        if item is None:
            return {"ok": False, "error": "unknown_inst", "detail": inst}
        wf, wt = rest["from"], rest["to"]
        pick = lambda m: (wf is None or m["from"] in wf) and (wt is None or m["to"] in wt)
        with item.cond:
            got = [m for m in item.mailbox if pick(m)]
            if cmd == "take":
                item.mailbox = [m for m in item.mailbox if not pick(m)]
        return {"ok": True, "messages": got}
    if cmd == "send":
        item = items.get(inst)
        if item is None:
            return {"ok": False, "error": "unknown_inst", "detail": inst}
        targets, to = [item], inst
    else:
        sender = rest["from"] if rest["from_socket"] in (None, own) else None   # 跨 daemon 來的不算自己
        with aos_daemon._items_lock:    # 重讀設定會原地改清單
            pool = list(items.values())
        if cmd == "broadcast":
            to = "*"
            targets = [i for i in pool if i.inst != sender]
        else:
            to = "#" + inst
            targets = [i for i in pool if inst in i.subscribe and i.inst != sender]
    for item in targets:
        letter = {"from": rest["from"], "from_socket": rest["from_socket"], "to": to,
                  "msg": copy.deepcopy(rest["msg"])}  # 每個信箱各自一份
        with item.cond:
            item.mailbox.append(letter)
            if rest["urgent"] and not item.stopped:
                _want(item, False)
                item.cond.notify_all()
    return {"ok": True, "delivered": len(targets)}
