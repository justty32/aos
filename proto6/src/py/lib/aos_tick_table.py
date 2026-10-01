"""aos-tick 的任務表 `.aos/tasks.json`：開格讀一次拿 `id`，跑到某項時才展開成 inst（B-620、P-202）。

〔使用者方向 2026-10-01〕POC 默認任務表是對的：不驗表（不回 2、不印 `config_invalid`），
也不看 `user`（照 tick 自己的帳號跑，不回 125）。表壞了就讓 Python 自然丟錯。

inst 的讀驗解用從 proto5 複製來的 `aos_inst.load_obj`（不改它）。它不回 `id`，也會對
「跟目前身分不同的 `user`」丟 `UserNotGranted`，所以：

- `id`：先用 `aos_directives.resolve_located` 展開這一項的頂層（整份 `$ref` 在這裡展開），
  再讀展開後的 `id`。
- `user`：交給 `load_obj` 前拿掉這一項字面上的 `user`。
- 這一項是一份純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指的是這一項自己，
  不是整份 tasks.json；相對檔名以 node 根為中心。
"""
import json
import os

import aos_inst
from aos_directives import Context, Document, resolve_located

__all__ = ["TABLE", "read_table", "task_id", "load_inst"]

TABLE = os.path.join(".aos", "tasks.json")


def read_table(node_dir):
    """讀 node 的任務表；回 (原始項目串列, id 串列)。"""
    with open(os.path.join(node_dir, TABLE), encoding="utf-8") as f:
        items = json.load(f)["tasks"]
    return items, [task_id(item, node_dir) for item in items]


def task_id(item, node_dir):
    """展開這一項的頂層（整份 `$ref`），讀它的 `id`。"""
    ctx = Context(Document(None, item), base_dir=os.path.abspath(node_dir))
    return resolve_located(item, ctx, []).value["id"]


def load_inst(item, node_dir):
    """把這一項當 inst 讀驗解（拿掉字面 `user`）；回 aos_inst 的 dict。"""
    item = {k: v for k, v in item.items() if k != "user"}
    return aos_inst.load_obj(item, node_dir)
