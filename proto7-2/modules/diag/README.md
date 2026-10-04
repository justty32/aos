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

「不知道」一律保留現狀（核心 spec 第 0 節），所以有些情況要人把證據修好才會往下走。

**先分清停多大**：**整 node 停開回合**（時間線停在 `error` 退避）／**單槽保留**（那個槽不起、不判 lost、不刪，其他槽照跑）／**單請求等待**（那份控制留著，其他照做）。

**通則**：

- **不是每個「不知道」都要人**：`aos7-diag` 列出的 `uncertain` 非空不等於要人工——「剛起」（birth→runner→pid.json 交接中）是正常暫態，看它持續多久、run 有沒有往前。`last_error` 只是最近一筆，不代表現在還壞著；合看 `phase`、`round`、`at`。
- **動手前**：先保存證據（複製 `.aos/round.json`、`last-round.json`、相關槽的 birth／pid／exit／ctl／ctl-done，和 `.aosd/status.json`），再 `pause` 這個 node（例 `aos7-ctl daemon <root> pause <node> --owner human`）讓會寫檔的動作停止競爭；pause 時不 tick／tock，也不執行任務控制。修完 `resume` 同一個 owner。
- **核實回合數 N**（round.json 壞掉、不在、或不是一般檔時要寫回）：看 last-round.json 的 `round`（已提交的最後一回合）、各槽 birth.json 的 `round` 與 exit.json 的 `round`／`seen_round`，取看得到的最大值。N＝last-round 的 `round` → 第 N 回合已收，寫 `{"round": N, "open": false}`；有槽的 birth `round` 比 last-round 大（＝N）→ 第 N 回合開了、總結沒提交，寫 `{"round": N, "open": true}` 讓 daemon 先 tock 收掉（核心 spec 2.2）（總結標 `incomplete`），**不要盲寫 false**——那會跳過這回合的結束與通知。
- **刪 birth.json＝重新授權執行**：槽變空槽，keep／each 會再起；只確認「現在沒有活程序」不能證明 once 沒產生過外部副作用（交付物要看槽外）。

| 情況 | 停止範圍｜看得到的證據 | 恢復步驟 |
|---|---|---|
| round.json 半寫、缺欄、型別錯、讀不到 | 整 node｜`phase: error`、`round_open: null`、`last_error.kind: round-unknown` | 修 I/O；內容壞照上面核實 N 寫回 |
| **round.json 存在但不是一般檔**（FIFO、資料夾） | 整 node｜同上，原因寫「存在但不是一般檔」 | 刪掉換回一般檔，內容照核實的 N 寫（N／false 或 N／true） |
| round.json 不在，last-round.json 讀不到、壞掉或不是一般檔 | 整 node｜tick 退出碼 3，`last_error` 說接號失敗 | 修好 last-round.json（不是一般檔就刪掉換回），或照核實的 N 直接寫 round.json。兩份都不在會當新空間從 1 數（run 仍遞增，核心 spec 5.2），不保護誤刪 |
| 明確 open，但 last-round.json 讀不到、列不出槽、總結寫入／讀回失敗 | 整 node｜`round_open: true`、`recovery_pending`、`last_error`，0.5～8 秒退避 | 修檔案系統／權限後自動重試 tock |
| gen.json 讀不到或不是 `{"gen": 整數}` | 所有 node（tick／tock 退出碼 3）｜各 node 的 `last_error` | 修存取；壞了寫回現役 daemon 的世代（status 的 `gen`），不要猜一個放舊動作過 |
| 看不到 node／root（EIO、EACCES…） | 該 node／整個 daemon 保留現狀｜node 的 `last_error.kind` 是 errno 名；root 是頂層 `last_error` | 修存取後自動恢復 |
| action.lock 持有者身分核對不了 | 整 node｜`last_error.kind: stale-holder-unverified`，why 說認不出的原因（沒殺任何程序） | 用 `fuser`／`lsof` 找 `<node>/.aos/action.lock` 的持有者，確定是舊的 tick／tock 才收掉，或補正 `action.owner.json` 的 pid／gen／starttime（下一次逾時自動回收）；**不要 unlink 鎖檔** |
| 槽的 birth／pid／exit 讀不到，或**存在但不是一般檔** | 單槽｜`aos7-diag` 的 `uncertain`、總結 `errors`（`where: judge`） | 修 I/O 後自動恢復；不是一般檔的刪掉換回——原內容不可考時等於刪 birth（上面通則） |
| birth.json 壞掉（半寫、不是物件、run 不是整數） | 單槽｜`aos7-diag` 的 `uncertain`／總結 `errors` 有刪 birth 的提示 | 確認沒有活程序、也確認 once 的副作用後才刪 birth.json |
| 活 pid 讀不到 stat／starttime，或 pid.json 的 starttime 本來就是 null | 單槽（當活＋unsure）｜`aos7-diag` 的 `uncertain`、總結 `errors`（`kind: unsure`） | 暫時讀錯自己會好；starttime null 不會因 /proc 恢復而補上身分，要等程序結束，或人工確認後收掉 |
| 疑似 lost，但掃描不完整、SIGKILL 後還在、最後重讀 exit.json 讀不到 | 單槽（UNKNOWN）｜總結 `errors`（`where: judge`）；ctl 留著 | 解除 I/O／權限／程序卡住後自動重判；不要為了進度手寫 lost |
| **kill 回 `ok: false`（unknown）** | 單請求（已處理掉、不會自己重試）｜ctl-done.json `result.ok: false`、msg 以 `unknown` 開頭；總結 `ctl` 那筆 `ok: false`。控制包 restart 的 once 項已加，等槽空才起（`skipped` 記 busy） | 手動確認並收掉 pid.json 記的那個程序；要再送 kill 照樣帶同一個 run |
| ctl.json 讀不到、目標槽 UNKNOWN | 單請求（留著）｜總結 `ctl` 那筆帶 `err` | 原因解除後自動執行 |
| ctl.json 處理完刪不掉 | 不停（每回合再執行一次，只對同一個 run，無害）｜總結 `ctl` 每回合一筆帶 `err`「刪不掉」 | 修權限後下一次自動刪；或人手刪 |
| tock.json 寫不進去 | 不停｜round.json `notify_errors`（核心不跨回合補送，F47） | 修權限後下一回合照常通知；要補上一回合的由模組讀 round.json 自己做 |
| daemon 控制檔處理丟例外（例如回條寫不進去） | 單請求｜status 的 `last_ctl_error`；請求刪掉（刪不掉就留在 `ctl/`，不再執行，每圈再試著刪） | 效果可能已生效：先看 status 核實，再決定要不要重送；重開 daemon 會把還卡在 `ctl/` 的當新請求 |
| tasks.json 讀不到／壞掉、表鎖逾時、項目不合法 | 回合照開、那些項不起｜round.json／總結的 `tasks_error`、`skipped` | 修表；status 只看到回合往前，看不出沒起工作，要讀總結 |
| 子 daemon 包擋下（子根有 stopped.json、已被認領、位置不合） | 那項的包裝程式退出碼 1｜總結 `ended` 該 run code 1、它的 out.log 有原因 | 見[子 daemon 包](../subd/README.md)；要重起就刪 stopped.json |
| pause、rounds 到零、missing、unregister、stop | 明確控制或實體變更｜`paused_by`、`steps_left`、`phase` | 不是故障：resume 對應 owner、把資料夾放回或重新 register、重起 daemon |
