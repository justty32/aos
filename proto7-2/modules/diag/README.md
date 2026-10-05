# 診斷包（diag）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（第 0 節：錯誤四分支）

**唯讀的診斷工具＋操作手冊**：核心的 status 只放基本欄位與最近一筆 `last_error`；判不出的槽是哪些、為什麼、該怎麼恢復，用這個工具按需重算，照下面的表處理。

| 項目 | 內容 |
|---|---|
| 接法 | C 工具：`aos7-diag <root> [node-id]`（`proto7-2/modules/diag/aos7-diag`） |
| 預設 | 開（工具，不在任何迴圈裡） |
| 依賴 | 核心的判定函式（`aos7_task.judge`、`aos7_fs.fact`）——只讀 |
| 程式 | `aos7-diag` |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/diag/tests`） |

## 契約卡

- **職責**：唯讀重算判不出的槽、把原因對到恢復步驟；保管「會停下等人」的操作手冊（核心 spec §12）。
- **前置條件**：人或工具按需呼叫；status.json 由 daemon 寫。
- **保證**：不寫任何檔、不收程序、不做身分掃描；判定用核心同一套入口（`judge`、`fact`，核心 §0、§5.4），不另判一次。
- **明確不管**：跟 tick／tock 掃描後的結論可能不同（這裡是掃描前的樣子，只供參考）；替人動手修；`steps_left`（daemon 記憶體裡，留在核心 status）。

## aos7-diag

印一份 JSON：每個已登記 node 的 `phase`／`round`／`round_open`／`last_error`／`paused_by`／`steps_left`（照抄 status.json），加上：

- `uncertain`：重新判定每個槽，列出判不出的（UNKNOWN）與保守當活的（unsure），各帶槽、run、原因。用核心的 `judge`，**不做** lost 前的身分掃描、不收程序、不寫任何檔。
- `hints`：照 `uncertain` 的原因與 `last_error.kind` 對到下面表裡的恢復步驟（一句）。

status 不再放 `uncertain`（以前 daemon 每 0.25 秒重算一次）；`steps_left` 是 daemon 記憶體裡的倒數，這個工具算不出來，留在核心 status。

## 界線（方案 6.1 第 9 點）

- 只看 status 的人看不到判不出的槽：要跑 `aos7-diag`，或讀回合總結的 `errors`。
- `aos7-diag` 只用 `judge`、不做 lost 前的身分掃描：tick／tock 會掃描後判成 lost 或「aos7-run 還在、當活」的槽，這裡可能還列成疑似 lost 之前的樣子；它是唯讀的參考，不改任何狀態。
- 表裡的恢復步驟是人做的；工具只指方向，不替你動手。

## 會停下等人的情況與恢復步驟（操作手冊，從核心 spec §12 搬來）

整份操作手冊（停多大、通則、逐情況的證據與恢復步驟表）在 [recovery.md](recovery.md)。
