# aos-agent listen 微調（2026-09-24）

← [notes 索引](README.md)｜規範 [cli-listen.md](../spec/aos-agent/cli-listen.md)｜審查 [任務書](2026-09-24-listen-tweak-review-task.md)／[astra 報告](2026-09-24-listen-tweak-review-astra.md)

使用者原話：「aos-agent listen 還可以微調一下。比如 `--last 10`，就是讀最後十筆訊息。然後 `--last` 不要是預設。然後有 `--show-calls`，連同工具呼叫一起印出來（但是簡化版，就是說明呼叫了啥工具）；`--show-calls-full`，則是印出更細節的內容。」

## 做了什麼

- `aos-agent listen [--target DIR] (--last [N] | --wait [秒] | --follow) [--show-calls | --show-calls-full] [--json]`
- **`--last [N]`**：印最後 N 則回話（N 省略＝1，要是正整數，否則用法錯 2）。N＞1 或開了 `--show-calls*` 時，每一輪前面一行標頭 `── 第 R 輪 · 收話 MM-DD HH:MM:SS ──`，多則之間靠它分隔。N＝1 又沒開 `--show-calls*` 時跟以前一模一樣（只印回話本身，方便 `$(…)`）。不到 N 則就有幾則印幾則，stderr 一行 `note: 記憶裡只有 K 則回話，全印`。
- **「回話」怎麼算**：assistant 有字、或沒叫工具的那則。只叫工具的那則不算（例外：它是最後一則 assistant，也就是這輪還沒走完，照以前印 `(tool_calls: …)`）。有字又叫工具的中間句（「讓我看看」）算一則。
- **時間從哪來**：記憶本身沒有時間戳。這裡印的是「收下那輪輸入的時刻」，取自輸入封存檔名 `done/<原檔名>.<ns>-<pid>.done` 裡的 ns；每輪第一句 user 對封存裡同內容的那次收件。對不上（封存被清、手改記憶）就只印 `── 第 R 輪 ──`。
- **`--show-calls`**：一個呼叫一行 `[呼叫 名 k=v]`（值超過 40 字截、整段超過 120 字截），結果一行 `[結果 名：第一行]`（多行註明幾行，第一行超過 60 字截）。
- **`--show-calls-full`**：`[呼叫 名 id=…]` 下面縮排印參數 JSON；`[結果 名 id=… K 行 L 字]` 下面縮排印原文；參數、結果各超過 4000 字只印前 4000 字，並一行註明「截斷：共 L 字…全文在記憶檔」。
- 兩個旗標對三種看法都有效：`--last N` 印「倒數第 N＋1 則回話之後」到記憶尾；`--wait` 印這一輪；`--follow` 每多一格就即時印（叫工具那一刻就出呼叫行）。搭 `--json` 時每格一行原樣 JSON（含 tool 訊息）。
- 程式：印法拆到新檔 `lib/aos_agent_listen_render.py`；`aos_agent_listen.py` 只接上；`aos_agent_cli.py` 只動 listen 那幾行與 `HELPS` 的 listen 一句。
- 規範：§1.5 從 `cli-talk.md` 搬到新檔 `cli-listen.md`（7.1 KB）；`cli.md` 用法總表、`essentials.md`、`README.md` 檔表、`history.md` 沿革一起改。

## 不給看法時選了什麼：用法錯、退 2

`aos-agent listen` 什麼都不給＝stderr `aos-agent: Usage: listen 要選一種看法：--last [N]（最後 N 則）、--wait [秒]（等下一則）、--follow（一直印）；例：aos-agent listen --last`，stdout 空，退 2。

理由：使用者說 `--last` 不要是預設，剩下的兩種預設都不好——預設 `--wait` 會卡 300 秒、預設 `--follow` 永遠不退，新手打 `listen` 會以為當掉。報錯順便把三種列出來，打錯一次就學會。跟其他用法錯一樣退 2，腳本也分得出來。

## 真跑輸出（LiteLLM deepseek-chat，daemon＋kernel＋`init` 的家，說了三句）

```
$ aos-agent listen
aos-agent: Usage: listen 要選一種看法：--last [N]（最後 N 則）、--wait [秒]（等下一則）、--follow（一直印）；例：aos-agent listen --last
(退 2)
$ aos-agent listen --last 3
aos-agent: time: 09-24 15:41:41
── 第 1 輪 · 收話 09-24 15:41:07 ──
現在是 2026年9月24日 下午3點41分。
── 第 2 輪 · 收話 09-24 15:41:22 ──
你好，我是繁體中文助理，可協助回答問題與查詢時間。
── 第 3 輪 · 收話 09-24 15:41:28 ──
現在是 15:41:35，與上次（15:41:14）相差 21 秒。
$ aos-agent listen --last 3 --show-calls
aos-agent: time: 09-24 15:41:41
── 第 1 輪 · 收話 09-24 15:41:07 ──
[呼叫 date]
[結果 date：2026-09-24 15:41:14]
現在是 2026年9月24日 下午3點41分。
── 第 2 輪 · 收話 09-24 15:41:22 ──
你好，我是繁體中文助理，可協助回答問題與查詢時間。
── 第 3 輪 · 收話 09-24 15:41:28 ──
[呼叫 date]
[結果 date：2026-09-24 15:41:35]
現在是 15:41:35，與上次（15:41:14）相差 21 秒。
$ aos-agent listen --last 3 --show-calls-full
aos-agent: time: 09-24 15:41:41
── 第 1 輪 · 收話 09-24 15:41:07 ──
[呼叫 date id=call_00_qil7JYbqjfRImzu23bDY9134]
  {}
[結果 date id=call_00_qil7JYbqjfRImzu23bDY9134 1 行 20 字]
  2026-09-24 15:41:14
現在是 2026年9月24日 下午3點41分。
── 第 2 輪 · 收話 09-24 15:41:22 ──
你好，我是繁體中文助理，可協助回答問題與查詢時間。
── 第 3 輪 · 收話 09-24 15:41:28 ──
[呼叫 date id=call_00_vm2zNwwUFdFltBY6uJLZ7059]
  {}
[結果 date id=call_00_vm2zNwwUFdFltBY6uJLZ7059 1 行 20 字]
  2026-09-24 15:41:35
現在是 15:41:35，與上次（15:41:14）相差 21 秒。
```

（`time:` 那行是 stderr。`--show-calls-full` 那段是修掉「結尾換行多印一行空白」之後、在同一個家重跑的樣子，真跑當下結果下面多一行 `  `。）

`--follow --show-calls` 真跑（開著 follow 再 `say "用 date 工具查現在幾點"`，每 0.5 秒看一次輸出檔）：說完約 7 秒出 `[呼叫 date]`，9.5 秒出 `[結果 date：2026-09-24 15:42:13]`，14 秒出回話——呼叫行是即時印的，不等輪完。
清場：agent stop → kernel halt → daemon halt，`pgrep -fa listen-tweak` 空。date 沒有參數，所以真跑看不到 `k=v`；有參數、長值截斷、多行結果、4000 字截斷都在測試裡驗。

## 測試

1153 → 1173（新檔 `test_agent_listen_tweak.py` 20 條）→ 修完 astra 必修 1180（該檔 27 條），全測連跑兩次綠。舊測試裡裸 `listen` 的九處補上 `--last`（daily 3、daily_edges 2、fix_r4 2、fix_r5 1、fix_cli 1）；`test_agent_fix_r4` 的 `test_listen_default_is_last` 改名 `test_listen_last_bare_is_one`（只驗 `--last` 不帶數字＝1，不給看法的用法錯在新檔驗）。

## astra 審查：必修 7 條全修，建議 4 條修 3 條

[報告全文](2026-09-24-listen-tweak-review-astra.md)。astra 在唯讀沙箱裡跑不了測試（建不了暫存目錄），改用 mock 驗證。

| # | 必修 | 怎麼修 |
|---|---|---|
| 1 | 不同輪重用同一個 tool_call_id 時，前一輪的結果被後面的呼叫改名 | 工具名表照記憶順序邊走邊更新，結果只對它之前最近的呼叫；`--follow` 也一樣 |
| 2 | `info.json` 壞了改讀沒驗過的記憶時，怪形狀（`null` 元素、`tool_calls: [null]`、`arguments` 不是字串）會噴 traceback | 印法全部容錯：非物件略過、怪呼叫寫 `?`、非字串印 JSON；`print_message` 與「還在處理中」警告也改用同一套 |
| 3 | `--last` 後面 4301 位數的數字讓 `int()` 爆掉 | 去掉前導 0 後超過 9 位就當十億（＝全部），不真的換算 |
| 4 | 封存只用 ns 分組（同 ns 不同 pid 被併成一次）、組內用封存名排（跟原檔名順序可能相反） | 用完整 `<ns>-<pid>` 分組，組內照 input 路徑順序＋原檔名排 |
| 5 | 封存檔名裡的 ns 大到 `fromtimestamp` 溢位，整個回話印不出來 | 換不成時間的那筆就不印時間 |
| 6 | 簡化呼叫行的鍵、工具名裡有換行時變成兩行 | 名、鍵、值的 LF／CR 一律轉成 `\n`／`\r` |
| 7 | `--follow` 真程序測試：子程序啟動慢於 0.5 秒就會永久卡在 `readline()` | 先握手（一直補 ping 直到它印出來）、讀 stdout 走執行緒＋佇列、每次讀有 10 秒期限、cleanup 會 kill＋收屍 |

建議：①時間是推定（重複問句會配錯）→ 規範寫明限制，沒改對法；②封存略過 symlink／FIFO → 修了（成本問題沒動，量大再說）；③補測試 → 每條必修都補了一條；④`-h` 說「全印」與區段範圍 → `-h` 改「各最多 4000 字」，規範寫明 `--last N --show-calls` 看不到同輪更早那則有字回話上的呼叫。

## README／教程該改的句子（這隊不改 README，另一隊在拆 tutorials/）

- `proto5/README.md` 第 79 行：「看回話用 `listen`（09-24 fix-r4，取代舊的 `last`），三種擇一：`--last`（預設）印最後一則就退；…」
  → 「看回話用 `listen`，三種**一定要給一種**（不給會報用法錯）：`--last [N]` 印最後 N 則就退（不帶數字＝1，N＞1 時每輪前面一行 `── 第 R 輪 · 收話 時間 ──`）；`--wait [秒]` …；`--follow` …。加 `--show-calls` 連叫了哪些工具、結果第一行一起印，`--show-calls-full` 印完整參數與回傳（09-24 listen 微調）。」
- 第 83 行 `aos-agent listen --target $W/bob` → `aos-agent listen --target $W/bob --last`（可再加一行 `aos-agent listen --target $W/bob --last 3 --show-calls`）。
- 第 147 行「看 `prompts/history.json`；`listen` 只印 assistant 的話」→「用 `aos-agent listen --last --show-calls-full` 看（或直接看 `prompts/history.json`）」。
- 第 171 行 `aos-agent listen --target $W/amy` → 加 `--last`。
