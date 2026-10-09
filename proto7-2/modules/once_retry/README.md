# once 保證包（once_retry）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（4.4 once、5.4 的事實欄 `never_started`）

**讓 once 盡量至少一次**：核心的 once 是最多一次——tick 被殺在「寫了 birth.json、runner 還沒起」之間，那項一次都沒跑、報成 lost、不再起（P2-02）。這包把「看起來從沒起來過」的 lost 加回 tasks.json，重起一次。它靠取樣、也要槽證據還在，所以不是無條件的至少一次（見「明確不管」與界線）；可能跑兩次（極小機率真的跑過），是選它的人接受的代價。

| 項目 | 內容 |
|---|---|
| 接法 | A 普通 keep 任務：`{"name": "retry", "mode": "keep", "argv": ["python3", "<proto7-2>/modules/once_retry/retry_lost.py"]}` |
| 預設 | 關 |
| 依賴 | 核心的事實欄 `never_started`、`x` 透傳、once 的 `slot` |
| 程式 | `retry_lost.py`（`scan(node)` 也可以同程序呼叫） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/once_retry/tests`） |

## 契約卡

- **職責**：把「看起來從沒起來過」的 lost once 加回 tasks.json 重起一次，讓選它的 once 在觀察得到、槽證據還在時補登成至少一次（下面規則節）；取樣漏掉或槽已刪就退回最多一次。
- **前置條件**：要保證的 once 項帶 `x.retry_lost: true`；本任務是收得到 tock 的普通 keep；改 tasks.json 的人都拿表鎖（核心 spec §4.3）。
- **保證**：
  - 只加回 `lost`＋`never_started`（核心 §5.4 事實欄）、槽 birth 同 run、`once`、`x.retry_lost` 都成立的那筆；加回的項釘同槽、帶 `x.retry_of`，表上已有同 `retry_of` 的不重加。
  - 表讀不到、壞掉、表鎖拿不到＝不寫（核心 §4.1 G1），記著下一次 tock 再試。
- **明確不管**：取樣漏掉那一回合（退回最多一次）；槽已被刪（核心 §5.1）；極小機率真的跑過而跑兩次（選它的人接受的代價）。

## 規則

- 要保證的 once 項帶 `"x": {"retry_lost": true}`（核心照抄進 birth.json，不看內容）。舊的頂層 `retry_lost` 欄核心不收（那項不合、tasks_error 指到這裡）。
- 每收到一次 tock，讀自己 node 的 `.aos/last-round.json`：`ended` 裡 `lost` 而且 `never_started`（核心判 lost 時 birth 沒有 runner、沒有 pid.json、out.log 不存在或空）的那筆，槽的 birth.json（槽還在）同一個 run、`once`、`x.retry_lost` 是 true → 照 birth 的定義（`argv`／`inst`、`mounts`、`x`）拿表鎖加回一項 once：`slot` 釘同槽、`x.retry_of`＝原 run id。表上已有同 `retry_of` 的不重加。
- 加不回（表鎖一秒拿不到、表讀不到或壞掉、birth 讀不到或壞掉）＝記著，下一次 tock 再試；任務重起就忘了（取樣，見下）。
- 每次加回都在表鎖內重讀槽的 birth：run 已換、不是 once、`x.retry_lost` 不再是 true，或 birth 確定不存在，就丟掉該候選，不再重試；不拿 pending 裡的舊 birth 當作證據。表鎖不護 birth：核心在這次重讀與提交之間正好重用該槽時仍可能多加回一次（契約是至少一次，R8-26 只縮窗口）。
- 加回的項同樣帶 `x.retry_lost`，再遇到同樣情況會再加回。

## 界線（方案 6.1 第 3 點）

- **取樣**：這是普通任務，它收到的是「最新一次」tock。它慢了、被 pause、或報 lost 的那一回合它還沒起來，錯過那筆 lost 的 last-round.json，就退回最多一次。要精確，得放回核心（頂層定案 5 選了移出）。
- 槽在報完 lost 的下一回合可能被刪（名字不在表上）；加回的 once 釘同槽，tock 就不刪。但它錯過太久、槽已刪掉，也就加不回了。
- 以前在核心時 lost 的紀錄帶 `retried: true`；現在核心不知道這件事，看 tasks.json 有沒有 `x.retry_of`，或之後的 `ended`。
