"""aos-tick 的任務表（預設 `.aos/tasks.json`；`--node` 給檔時就是那個檔）：開格讀一次拿 `id`，跑到某項時才展開成 inst（B-620、P-202）。

〔使用者方向 2026-10-01，待統一更新 spec〕開格只做極簡檢查（`check_table()`），不過就丟 `TableInvalid`，
tick 印一行 `bad_table: …`、回 1（算 tick 自己的錯；在換紀錄之前，不佔 seq）：讀得到、合法 JSON、頂層是物件、有 `tasks` 陣列；
每項（整份 `$ref` 先展開）是物件且有 `argv`。其他一概不查（外層與每項的 `_metainfo`、`id`、`kind`
填不填與它們的值、值的型別、`id` 重複、陌生鍵如 `group`、`needs`、`methods`）。
沒有 `id` 的項：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，例如 "3"；跟別項撞了不管（使用者：「默認不重複」）。
不看 `user`（照 tick 自己的帳號跑，不回 125）。跑到某項才展開成 inst，那時 `load_obj` 丟錯就自然丟錯回 1。

inst 的讀驗解用從 proto5 複製來的 `aos_inst.load_obj`（不改它；〔使用者方向 2026-10-01〕它跟 proto5 一樣
不認得頂層 `user`，當陌生鍵忽略，所以 tick 不用先拿掉）。它不回 `id`，所以：

- `id`：先用 `aos_directives.resolve_located` 展開這一項的頂層（整份 `$ref` 在這裡展開），
  再讀展開後的 `id`（沒有就用位置字串）。
- 這一項是一份純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指的是這一項自己，
  不是整份 tasks.json；相對檔名以 node 根為中心。
"""
import json
import os

import aos_inst
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["TABLE_NAME", "TableInvalid", "read_table", "load_inst"]

TABLE_NAME = "tasks.json"          # 放在 node 狀態資料夾（預設 `.aos`，見 aos_tick.aos_dirname）裡


class TableInvalid(Exception):
    """任務表不合極簡檢查；`str(e)` 是一行白話。"""


def read_table(table, node_dir):
    """讀這一格的任務表 `table` 並做極簡檢查；回 (原始項目串列, id 串列)。
    項目裡的相對檔名與指示詞以 node 根為中心。"""
    try:
        with open(table, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise TableInvalid("%s 讀不到或不是合法 JSON：%s" % (table, e))
    return check_table(doc, node_dir)


def check_table(doc, node_dir):
    """使用者 2026-10-01：「該填的沒填，然後不符合 {"tasks":[]} 這樣的格式，其他就不檢查。」
    「最外層不用檢查_metainfo，每一項也只需要檢查argv」。回 (原始項目串列, id 串列)。
    「沒寫id的時候，那就是以其在tasks陣列中的index做id。直接數字轉字串。默認不重複」"""
    items = doc.get("tasks") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        raise TableInvalid("任務表頂層要是物件、要有 tasks 陣列")
    ids = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise TableInvalid("tasks[%d] 要是物件" % i)
        try:
            ctx = Context(Document(None, item), base_dir=node_dir)
            top = resolve_located(item, ctx, []).value          # 整份 `$ref` 在這裡展開
        except DirectiveError as e:
            raise TableInvalid("tasks[%d] 展開不了：%s" % (i, e))
        if not isinstance(top, dict) or "argv" not in top:
            raise TableInvalid("tasks[%d] 缺了 argv" % i)
        ids.append(top["id"] if "id" in top else str(i))
    return items, ids


def load_inst(item, node_dir):
    """把這一項當 inst 讀驗解；回 aos_inst 的 dict。"""
    return aos_inst.load_obj(item, node_dir)
