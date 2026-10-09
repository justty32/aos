# 診斷包（diag）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（第 0 節：錯誤四分支）

**唯讀的診斷工具＋操作手冊**：核心的 status 只放基本欄位與最近一筆 `last_error`；判不出的槽是哪些、為什麼、該怎麼恢復，用這個工具按需重算，照下面的表處理。

| 項目 | 內容 |
|---|---|
| 接法 | C 工具：`aos7-diag <root> [node-id]`（`proto7-2/modules/diag/aos7-diag`）；`aos7-diag --llm <node>` 看 LLM 待辦 |
| 預設 | 開（工具，不在任何迴圈裡） |
| 依賴 | 核心的判定函式（`aos7_task.judge`、`aos7_fs.fact`）——只讀 |
| 程式 | `aos7-diag` |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/diag/tests`） |

## 第一次用

兩種看法，都只讀、不改任何檔：

- **看整個空間的核心**：`aos7-diag <root> [node-id]`。`<root>` 是 aos 空間根（有 `.aosd/` 的那個資料夾）；只想看一個 node 就再給它的 id。
- **看一個 node 的 LLM 線路**：`aos7-diag --llm <node>`。`<node>` 是那個 node 自己的資料夾（底下有 `llmcall/`、`budget/`、`jobs/` 的那層）。舊指令 `aos7-llmdiag` 已併入這裡。

`--llm` 印一行 JSON，三張表：

| 表 | 白話 | 下一步 |
|---|---|---|
| `llmcall_pending` | 送出了但還沒結案的 LLM 呼叫。`stage: request`＝還沒收到回覆；`stage: raw`＝回覆收到了、還沒記帳 | 照原樣再跑那次呼叫會接續；想先看證據用 `aos7-llmcall status` |
| `author_halted` | 停住的學徒 job，`why` 寫為什麼停 | 照 `why` 處理後再叫學徒接著做 |
| `budget_inflight` | 這個帳還有幾筆預留沒結 | 多半跟著上面的呼叫一起結；呼叫都結了還不是 0 才要人看 |

這是「現在檔案長怎樣」的快照，只供參考；它不判斷是卡死還是正在跑——隔一會再看一次，數字沒動才算卡住。檔案格式與出錯時的說明見 [ADVANCED](ADVANCED.md)。

## 契約卡

- **職責**：唯讀重算判不出的槽、把原因對到恢復步驟；保管「會停下等人」的操作手冊（核心 spec §12）；`--llm` 也唯讀列出 LLM 待辦。
- **前置條件**：人或工具按需呼叫；status.json 由 daemon 寫。
- **保證**：不寫任何檔、不收程序、不做身分掃描；判定用核心同一套入口（`judge`、`fact`，核心 §0、§5.4），不另判一次；`--llm` 也唯讀、不寫任何檔。
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
