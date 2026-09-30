"""aos-tick 的任務表 `.aos/tasks.json`：開格讀一次、只驗四件事；跑到某項時重新展開（B-620、P-202）。

核心只驗：合法 JSON、`_metainfo` 是 `aos-tasks` 第 1 版、每項（整份 `$ref` 展開後）是合法
inst、`id` 在表內唯一。缺 `kind`、`system.x`、`methods` 形狀、陌生鍵（含舊的 `group`、`needs`）
都不驗、照跑。

inst 的讀驗解用從 proto5 複製來的 `aos_inst.load_obj`（不改它）。它不回 `id`、也會對
「跟目前身分不同的 `user`」丟 `UserNotGranted`，所以：

- `id`：先用 `aos_directives.resolve_located` 展開這一項的頂層（整份 `$ref` 在這裡展開），
  再讀展開後的 `id`。〔最小合理〕要是非空字串，不然算表壞（紀錄與 `AOS_TASK_ID` 要用它）；
  ID 的字元規則是完整 schema 的事，核心不驗。
- `user`：讀這一項的**字面值**（整份 `$ref` 引進來的不看，跟 aos-exec 一致），自己判；
  交給 `load_obj` 的是拿掉 `user` 的那一份。
- 這一項是一份純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指的是這一項自己，
  不是整份 tasks.json；相對檔名以 node 根為中心。
"""
import json
import os
import pwd

import aos_inst
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["TableError", "TABLE", "read_table", "task_id", "check_user", "load_inst"]

TABLE = os.path.join(".aos", "tasks.json")


class TableError(Exception):
    """任務表壞了：整表拒絕、回 2。`str(e)` 是一行白話（前面由呼叫者加 `config_invalid:`）。"""


def read_table(node_dir):
    """讀 node 的任務表並只驗四件事；回 (原始項目串列, id 串列)。壞了丟 TableError。"""
    path = os.path.join(node_dir, TABLE)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        # 〔使用者方向 2026-09-30 晚〕有 .aos/ 但沒有 tasks.json 算表壞
        raise TableError("沒有 %s" % TABLE)
    except OSError as e:
        raise TableError("讀不到 %s：%s" % (TABLE, e))
    try:
        obj = json.loads(raw)
    except ValueError as e:
        raise TableError("%s 不是合法 JSON：%s" % (TABLE, e))
    if not isinstance(obj, dict):
        raise TableError("%s 頂層要是物件" % TABLE)
    mi = obj.get("_metainfo")
    if not (isinstance(mi, dict) and mi.get("_type") == "aos-tasks"
            and type(mi.get("_version")) is int and mi.get("_version") == 1):
        raise TableError("_metainfo 要是 {\"_type\":\"aos-tasks\",\"_version\":1}，現在是 %s"
                         % json.dumps(mi, ensure_ascii=False))
    items = obj.get("tasks")
    if not isinstance(items, list):
        raise TableError("tasks 要是陣列")
    ids, seen = [], {}
    for i, item in enumerate(items):
        where = "tasks[%d]" % i
        try:
            tid = task_id(item, node_dir)
            check_user(item)                    # 型別錯才算壞；帳號不同或查不到留到跑時回 125
            load_inst(item, node_dir)
        except aos_inst.InstError as e:
            raise TableError("%s：%s" % (where, e))
        if tid in seen:
            raise TableError("%s 的 id %r 跟 tasks[%d] 重複" % (where, tid, seen[tid]))
        seen[tid] = i
        ids.append(tid)
    return items, ids


def task_id(item, node_dir):
    """展開這一項的頂層（整份 `$ref`），讀它的 `id`。不合就丟 InstError。"""
    ctx = Context(Document(None, item), base_dir=os.path.abspath(node_dir))
    try:
        top = resolve_located(item, ctx, []).value
    except DirectiveError as e:
        raise aos_inst.InstError(e.code, e.msg)
    if not isinstance(top, dict):
        raise aos_inst.InstError("NotAnObject", "任務要是一個 JSON 物件，不是 %s" % type(top).__name__)
    tid = top.get("id")
    if not isinstance(tid, str) or tid == "":
        raise aos_inst.InstError("TaskIdInvalid", "任務的 id 要是非空字串，現在是 %s"
                                 % json.dumps(tid, ensure_ascii=False))
    return tid


def check_user(item):
    """看這一項字面上的 `user`。回 None＝照 tick 自己的帳號跑；回字串＝不是 tick 的帳號（說明）。

    型別錯、放指示詞、負數＝這一項不是合法 inst，丟 `UserInvalid`（表壞）。
    〔最小合理〕名稱查不到帳號不算表壞（範例表 tasks.user.valid.json 的帳號在別的機器上本來就
    可能不存在），當成「跟 tick 不同」，跑到時回 125。
    """
    if not isinstance(item, dict) or "user" not in item:
        return None
    user = item["user"]
    if user == "":
        return None
    if isinstance(user, bool) or not isinstance(user, (str, int)):
        raise aos_inst.InstError("UserInvalid", "user 要是帳號名稱字串或非負整數 UID（不吃指示詞），不是 %s"
                                 % type(user).__name__)
    if isinstance(user, int):
        if user < 0:
            raise aos_inst.InstError("UserInvalid", "user 的 UID 不能是負數：%d" % user)
        uid = user
    else:
        try:
            uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            return "user %r 查不到帳號，當成不是 tick 的帳號（UID %d）" % (user, os.geteuid())
    if uid != os.geteuid():
        return "user %r（UID %d）不是 tick 的帳號（UID %d），核心不切帳號" % (user, uid, os.geteuid())
    return None


def load_inst(item, node_dir):
    """把這一項當 inst 讀驗解（拿掉字面 `user`，身分由 check_user 判）；回 aos_inst 的 dict。"""
    if isinstance(item, dict) and "user" in item:
        item = {k: v for k, v in item.items() if k != "user"}
    return aos_inst.load_obj(item, node_dir)
