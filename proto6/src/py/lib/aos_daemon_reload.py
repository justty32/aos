"""aos-daemon 的重讀設定模組（plan m3m-daemon-modules.md 模組一）。

設定檔寫 `"modules": {"reload": {}}` 時掛上：收到 SIGHUP 就重讀同一份設定檔（照樣整份展開指示詞），
跟現在的清單比對 `insts`：

- 新出現的鍵：開一條新執行緒，照「開起來先跑一次」立刻跑；stdout `inst=<inst> added`。
- 不見的鍵：不再排下一次；正在跑的那次不殺、讓它跑完印完；之後控制指令對它回 `unknown_inst`；
  stdout `inst=<inst> removed`。之後又加回來＝新的一項（狀態從頭）。
- 鍵還在：`interval_ms`、`stop_on_nonzero`、`exec_out_path`／`exec_err_path` 算出來的路徑、第幾項
  原地換；暫停、已停、待補照留。`interval_ms` 改了：下一次＝上一次結束＋新週期（已經過了就立刻跑；
  還沒跑完過一次的照原本的排程）。
- 頂層 `cwd`、`modules`（含狀態檔換了位置）改了：不套用，stdout 印 `reload: need restart: cwd`
  （或 `modules`），其他照套（R3，使用者 2026-10-01：「如果最上層這些改了，那就stdout輸出警告。」）。
- 最後一行 `reloaded`。

重讀時設定壞了（JSON 壞、指示詞錯、缺 `interval_ms`、型別錯……）：整份不套用、stderr 一行
`aos-daemon: reload: <說明>`、舊設定照跑（R4）。這是本模組唯一的異常處理。

記住狀態模組掛著時，重讀**以記憶體為準**：不重讀狀態檔、不拿檔覆蓋還在的項；新加的項一律從頭
（跟「拿掉又加回來＝新的一項」一致）。套用完照記憶體寫一次狀態檔（拿掉的項就不見了；沒變就不寫）。
"""
import sys

import aos_daemon
from aos_daemon import Item, give_env, load_full, say, start_item, state_changed


def reload(path, first):
    """重讀 path 並套用。first＝daemon 開起來時的 `Setup`（cwd、modules 以它為準，因為它們從不套用）。"""
    try:
        new = load_full(path, read_state=False)
    except Exception as e:          # R4：唯一的例外——整份不套用、舊的照跑
        sys.stderr.write("aos-daemon: reload: %s\n" % (str(e) or type(e).__name__))
        sys.stderr.flush()
        return
    if new.start != first.start:
        say("reload: need restart: cwd")
    if new.modules != first.modules:
        say("reload: need restart: modules")
    added, removed = [], []
    with aos_daemon._items_lock:
        items = aos_daemon._items
        fresh = {i.inst: i for i in new.items}
        for inst in [k for k in items if k not in fresh]:
            old = items.pop(inst)
            with old.cond:
                old.removed = True
                old.pending = False
                old.cond.notify_all()
            removed.append(inst)
        for n in new.items:
            cur = items.get(n.inst)
            if cur is None:
                cur = Item(n.index, n.inst, n.interval_ms, n.stop_on_nonzero, n.err_path, n.out_path)
                give_env(cur, first.sock)
                added.append(cur)
            else:
                _update(cur, n)
            items[n.inst] = cur
        # 照新設定檔的鍵順序重排（之後 status、狀態檔都照這個順序）
        order = [items.pop(i.inst) for i in new.items]
        items.update((i.inst, i) for i in order)
    for inst in removed:
        say("inst=%s removed" % inst)
    for item in added:
        say("inst=%s added" % item.inst)
        start_item(item, first.start)
    state_changed()
    say("reloaded")


def _update(cur, n):
    """鍵還在：原地換值，暫停、已停、待補照留。"""
    with cur.cond:
        changed = cur.interval_ms != n.interval_ms
        cur.index = n.index
        cur.interval_ms = n.interval_ms
        cur.stop_on_nonzero = n.stop_on_nonzero
        cur.err_path, cur.out_path = n.err_path, n.out_path
        if changed and not cur.running and cur.end_mono is not None:
            # R2：上一次結束＋新週期；已經過了就立刻跑（due 在過去，_next_run 馬上回）
            cur.due = cur.end_mono + n.interval_ms / 1000.0
        cur.cond.notify_all()
