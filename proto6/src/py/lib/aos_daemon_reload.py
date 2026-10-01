"""aos-daemon 的重讀設定模組（plan m3m-daemon-modules.md 模組一）。

設定檔寫 `"modules": {"reload": {}}` 時掛上：收到 SIGHUP 就重讀同一份設定檔（照樣整份展開指示詞），
跟現在的清單比對 `insts`：

- 新出現的鍵：開一條新執行緒，照「開起來先跑一次」立刻跑；stdout `inst=<inst> added`。
- 不見的鍵：不再排下一次；正在跑的那次不殺、讓它跑完印完；之後控制指令對它回 `unknown_inst`；
  stdout `inst=<inst> removed`。之後又加回來＝新的一項（狀態從頭）。
- 鍵還在：`interval_ms`、`stop_on_nonzero`、第幾項（掛了 cgroup 模組還有那一項的 `cgroup` 上限）
  原地換；暫停、已停、待補照留。`interval_ms` 改了：下一次＝上一次結束＋新週期（已經過了就立刻跑；
  還沒跑完過一次的照原本的排程）。
- 頂層 `cwd`、`modules`（含狀態檔換了位置）、`exec_out_path`、`exec_err_path` 改了：不套用，stdout 印
  `reload: need restart: <鍵名>`，其他照套（R3，使用者 2026-10-01：「如果最上層這些改了，那就stdout輸出警告。」；
  `exec_out_path`／`exec_err_path` 第十二批補進來）。新加的項的輸出路徑也照開起來時的設定與起點算。
- 最後一行 `reloaded`。

重讀時設定壞了（JSON 壞、指示詞錯、缺 `interval_ms`、型別錯……）：整份不套用、stderr 一行
`aos-daemon: reload: <說明>`、舊設定照跑（R4）。這是本模組唯一的異常處理。

記住狀態模組掛著時，重讀**以記憶體為準**：不重讀狀態檔、不拿檔覆蓋還在的項；新加的項一律從頭
（跟「拿掉又加回來＝新的一項」一致）。套用完照記憶體寫一次狀態檔（拿掉的項就不見了；沒變就不寫）。

收屍／cgroup 模組掛著時（plan m3m 模組二）：新加的項建框、寫上限，`added` 之後印 `inst=<inst> cgroup=i-<h>`；
還在的項上限改了就重寫新設定裡的那幾個檔（拿掉的鍵不還原）；拿掉的項由它自己的執行緒在最後一次跑完、
清完之後刪框。建框、寫上限出錯算重讀出錯（R4），但出錯前已經寫進去的不還原。

帳號模組掛著時（plan m3m 模組五）：每一項的帳號照**開起來時**的名單核（名單本身改了算 `modules` 改了、只警告），
名單不准或帳號查不到算重讀出錯（R4、A6）；還在的項帳號改了，下一次開 `aos-exec` 起用新帳號。
重讀是主程式（已降成預設帳號）做的，設定檔要讀得到。
"""
import sys

import aos_daemon
from aos_daemon import err_path_for, give_env, load_full, say, start_item, state_changed

# R3：頂層這幾個改了不套用、stdout 警告（Setup 的屬性名, 印出的鍵名）
NEED_RESTART = (("start", "cwd"), ("modules", "modules"),
                ("out_tmpl", "exec_out_path"), ("err_tmpl", "exec_err_path"))


def reload(path, first):
    """重讀 path 並套用。first＝daemon 開起來時的 `Setup`（cwd、modules、exec_out_path、exec_err_path
    以它為準，因為它們從不套用）。"""
    added, removed = [], []
    try:
        new = load_full(path, read_state=False)
        with aos_daemon._items_lock:
            _apply(new, first, added, removed)
    except Exception as e:          # R4：唯一的例外——整份不套用、舊的照跑
        sys.stderr.write("aos-daemon: reload: %s\n" % (str(e) or type(e).__name__))
        sys.stderr.flush()
        return
    for attr, key in NEED_RESTART:
        if getattr(new, attr) != getattr(first, attr):
            say("reload: need restart: %s" % key)
    for inst in removed:
        say("inst=%s removed" % inst)
    for item in added:
        say("inst=%s added" % item.inst)
        if item.frame is not None:
            aos_daemon._cg.announce(item, say)
        start_item(item, first.start)
    state_changed()
    say("reloaded")


def _apply(new, first, added, removed):
    """在 _items_lock 底下比對、套用。cgroup 的建框、寫上限先做（出錯就丟出去、清單一點都不改）。"""
    items = aos_daemon._items
    cg = aos_daemon._cg
    if aos_daemon._acct is not None:    # m3m 模組五：照開起來時的名單核每一項的帳號，不合整份不套用
        aos_daemon._acct.policy.check_items(new.items)
    if cg is not None:
        for n in new.items:
            cur = items.get(n.inst)
            if cur is None:
                cg.make(n, startup=False)
            elif cur.cgroup != n.cgroup:
                cg.limits(cur.frame, n.cgroup)
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
            cur = n                     # 新的一項就用重讀出來的 Item；輸出路徑照開起來時的頂層設定與起點算
            cur.err_path = err_path_for(first.err_tmpl, n.inst, first.start)
            cur.out_path = err_path_for(first.out_tmpl, n.inst, first.start)
            give_env(cur, first)
            added.append(cur)
        else:
            _update(cur, n)
        items[n.inst] = cur
    # 照新設定檔的鍵順序重排（之後 status、狀態檔都照這個順序）
    order = [items.pop(i.inst) for i in new.items]
    items.update((i.inst, i) for i in order)


def _update(cur, n):
    """鍵還在：原地換值，暫停、已停、待補照留。輸出路徑不換（頂層 exec_out_path／exec_err_path 不套用）。"""
    with cur.cond:
        changed = cur.interval_ms != n.interval_ms
        cur.index = n.index
        cur.interval_ms = n.interval_ms
        cur.stop_on_nonzero = n.stop_on_nonzero
        cur.cgroup = n.cgroup
        cur.user = n.user
        if changed and not cur.running and cur.end_mono is not None:
            # R2：上一次結束＋新週期；已經過了就立刻跑（due 在過去，_next_run 馬上回）
            cur.due = cur.end_mono + n.interval_ms / 1000.0
        cur.cond.notify_all()
