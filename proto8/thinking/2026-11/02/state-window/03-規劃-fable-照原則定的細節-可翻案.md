← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案）｜上一份 [02-現況-查清的-不是規劃](02-現況-查清的-不是規劃.md)｜下一份 [04-要使用者看的衝突與方向題](04-要使用者看的衝突與方向題.md)

## 規劃（fable，照原則定的細節，可翻案）

### 1. 名字

- daemon 自己那扇 state 的**慣用檔名**改 `daemon_state.json`（C-54：主題放前面，跟 `loops_state.json` 同一個格式）。因為程式本來就沒有預設名，「改」＝把 demo 五份 daemon.json、`aos_ai_daemon.py` 生的 daemon.json、`aos_ai_base.py:190` 讀的路徑、測試、README、N-28 範例裡的 `"state": "state.json"` 全改成 `"state": "daemon_state.json"`；**aos-daemon 程式不加預設名**（N-09「沒給就不開、不提醒」照舊）。子 loop 的 `loops/<名>/state.json`、agent 的 `state.json` 不動（那是 aos-loop 的窗）。
- daemon 的 `ctl.json` 要不要跟著改 `daemon_ctl.json`：使用者只說 state，照原則（C-54 同一組名字同一個格式）**建議一起改**，列成方向題 1。`loops_ctl.json`／`loops_state.json` 已經是主題前置，不動。

### 2. 寫入時機：啟動寫一次、有變動才更新

- **規則一句話**：每次「要寫 state」的時候，先組好這份 JSON（不含時間欄），跟上一份寫出去的比；**不一樣才寫**、一樣就不碰檔（N-14 的「比內容」搬到寫的一邊）。啟動後的第一份一定寫。結束那份一定寫（帶 `code`）。
- 什麼算變動（照這個規則自然得出，跟使用者舉的例子對得上）：
  - `phase` 變（running／waiting／paused／stopping／stopped／done）。
  - **處理 ctl 的各階段**：讀到新的好 ctl → `ctl_seq`／`max`／`interval_ms`／`paused` 生效值變；讀到壞 ctl → `ctl_warning` 從 null 變成原因；再讀到好的 → 清回 null；daemon 過渡期提醒 `ctl_note_` 同理。暫停中照樣每圈讀 ctl、有變就寫（現有測試 `test_cli.py:869` 那條「暫停中 loops_ctl 的 seq 回音」行為不變）。
  - daemon 的 `loops_state.json`：表有列起、退、收、拿掉、`letter_warning` 變、`ctl_seq`／`ctl_warning` 變。起一大批時每起一個就是一列變→照寫（原本 `beat()` 每秒一份的用意——讓人看得到進度——自然保留，而且更細）。`finish` 等子項退：進入 `stopping` 寫一份，之後每退一個寫一份，不再每秒一份。
  - 使用者原文的「ctl也是」：ctl 是別人寫的、程式只讀，不存在「程式寫 ctl」；這裡解讀成「ctl 相關的欄位有變才算變動」（上一點），不另立規矩。
- **`counter_runs` 不算變動**（方向題 2，fable 先這樣定）：它每次都加 1，若算變動，有身體的 loop 每次照寫兩份（跟現在一樣多）、沒身體的 daemon 每圈照寫（200 ms 一份，等於沒改），使用者的抱怨沒解。所以窗裡的 `counter_runs`＝「`updated_at` 那一刻的次數」，一份快照；準確的每次計數看 log（下節）。有身體的 loop 因為 `phase` 每次 running ⇄ waiting，仍是每次寫兩份——這是真的變動，照使用者原文（「phase 有變化」）就該寫；`interval_ms` 0 的 loop 連 `waiting` 都沒有、只有 `running`，一次一份。
- **心跳拿掉**（衝突 1）：不再「內容沒變也每秒碰一下」。活著照 N-17 的確定法看 `pid`＋`started_at_ticks`（＋`boot_id`），所有現有讀者本來就這樣做。`Loop::beat()` 保留當「要寫就寫」的入口但不再帶 1 秒計時（或整個拿掉，實作者定）。

### 3. 每次都會變的東西進 log

- **開法**：loop.json／daemon.json 多一個**選填 key `log`**＝檔名、在 `$AOS_STACK` 底下、沒寫＝不開（跟 `ctl`／`state` 同一條線 N-11、同一套路徑規則、同樣 `StackMissing`）。不借 `state` 這個 key 順便開第二個檔（C-56「寫什麼就做什麼」）。daemon 幫子 loop 補 `ctl`／`state` 時**不補 `log`**（使用者沒要求、子 loop 自己的 loop.json 要就寫）。
- **慣用檔名**：loop 寫 `log.jsonl`、daemon 寫 `daemon_log.jsonl`（跟 `daemon_state.json` 同一組）。不用 `trace.jsonl`：agent 的 fsm 跟它的 aos-loop **共用同一個 `$AOS_STACK`**（agent-bob 的 `.stack/` 裡 `state.txt`、`trace.jsonl` 是 fsm 的，`state.json` 是 loop 的），叫 `trace.jsonl` 會撞。
- **格式**：JSONL、**一次一行、那次結束時追加**（同 N-39 fsm 的做法）：`{"started_at": 這次開始的 UTC 時間(ISO 8601 到毫秒，P-38), "counter_runs": N, "code": 子程式的碼, "signal": 訊號或 null, "elapsed_ms": 跑了多久}`——欄位名照 N-30／N-39 現成的。**沒有身體的 daemon 沒有「次」可記，log 不寫行**（它的每圈只有 `counter_runs` 加 1，沒有值得記的事；子項的起退已經在 `loops_state.json` 列上）。結束不寫 log 行（結束碼在 state 的 `code`）。
- **上限／輪替**：跟 N-39「trace 不設上限」、N-28「aos 不保證子項輸出不無限長、使用者自行承擔」一致——**不設上限、不輪替**；要輪替自己在外面接 logrotate。一行約 120 bytes，一天跑 10 萬次才 12 MB。
- 寫法：`fopen` append、一行一次 `fwrite`＋`fclose`（一行小於 PIPE_BUF 的追加在 POSIX 上是原子的，不需要 N-05 的改名）；寫不了＝`WriteFailed` 一行、退 1（同 N-39 ③④）。

### 4. `updated_at`

- 兩扇窗（`state.json`／`daemon_state.json`、`loops_state.json`）都加 **`updated_at`**＝這份寫出去的那一刻，格式同 `recorded_at`（ISO 8601 UTC 到毫秒，`aos::utc_now_ms()`；C-54 R6「時間點＝`<發生了什麼>_at`」）。放在最後一欄（`recorded_at` 之後），現有欄位順序不動。
- `recorded_at` 照使用者「json 格式不用動」**留著**；心跳拿掉之後它跟 `updated_at` 永遠同值——這點列成方向題 3（要不要順手把 `recorded_at` 收掉），fable 不自己動。
- `kind` 照留；誰在用見現況（沒人讀，只有測試）。

### 5. 讀者怎麼改

- 判活著：**不改**——aos-eca-hub、aos_ai_base、adopt 全是 pid＋`started_at_ticks`。N-17 的「超過 3 倍間隔沒動靜算疑似死亡」那句失效、從條文拿掉（衝突 1）。
- 看進度：有身體的 loop 看 `log.jsonl` 行數／最後一行（P-19 本來就這樣說 fsm）；`counter_runs` 在窗裡是快照。沒身體的 daemon 看 `loops_state.json` 的表。
- `aos_ai_daemon.py status` 的 `recorded_at` 顯示欄改 `updated_at`。
- 測試：心跳間隔那幾條改成「睡著 1.5 秒窗的 `updated_at` **不變**、mtime 不變」「暫停中 loops_ctl 的 seq 變了 loops_state 照寫」；欄位順序表加 `updated_at`；`test_demo.py` 抹掉的欄位加 `updated_at`、demo 小格檔案表加 `log.jsonl`（若 demo 開了 log）。
