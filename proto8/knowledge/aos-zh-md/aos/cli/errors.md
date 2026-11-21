# `knowledge/aos/cli/errors.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/errors.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 錯誤與重試

決定要不要重試之前，先看程式名、錯誤代號和原因。

錯誤走 stderr：`PROGRAM: error: Code reason`，通常以 1 結束。`PROGRAM: warning: text` 是提醒，可能以 0 結束。stdout 放結果。結束碼 10 表示「那裡沒東西」（沒有信、沒有鎖、還沒有回覆）。子程式可能回報它自己的錯誤；不要把它當成 aos-agent 的解析錯誤。另見一般錯誤（`aos/errors.json`）。

---

**`#/codes`**

# 你會碰到的代號

- `ArgumentsBad`、`FlagUnknown`、`CommandUnknown`：修正呼叫。照它的用法說明，或照它建議的那一層 `--help`。
- `CommandMissing`：把點名的相依程式（例如 aos-exec、aos-json、aos-post、bwrap）放到 PATH 上。
- `TargetMissing`：給 `--target`、設 `$AOS_AGENT`，或在該 agent 的 stack 裡面跑（aos/cli/flags.json `target`）。
- `InstanceMissing`（daemon-ctl：`ProcMissing`）：這個名字不在表上。查 `ctl ls`。
- `InterfaceMissing`、`ToolsMissing`、`LlmMissing`、`HooksMissing`、`SystemMissing`：定義缺了需要的介面或檔案。修定義，或選一個支援的動作。
- `PhaseBad`：停止的用 start，睡著的用 wake；照原因做。
- `SessionBad`：畫面正在回覆；等一下再 close、stop 或 rm。
- `TrustMissing`：eca 畫面上的 claude 停在「信任這個資料夾」的提示；什麼都沒打進去。必須由人來選：接上去（`aos-agent open`），或在那個資料夾跑一次 `claude`。不要替他們回答那個提示。
- `AddRejected`/`CtlRejected`：看 daemon 或 kernel 給的代號和原因。先修好那個原因再送。
- 其他代號：`InterfaceBad`、`LlmBad`、`SystemBad`、`ToolsBad`（宣告的檔案或工具清單讀不了或格式壞了）；`ScreenBad`（畫面的進入點帶著錯誤結束）；`StateMissing`（不是 daemon stack：沒有 `procs_state.json`）；`QuestionUnknown`（listen：還沒問過任何東西）；`KeyMissing`（llm rm：鍵沒改）；`HistoryBad`、`MessageBad`（對話歷史檔讀不了、set 的 JSON 不是一個物件）；`WriteFailed`（stack 的檔案寫不進去）；`PostFailed`（say：aos-post 失敗）。見 `aos/errors.json`。
- `StackMissing`：沒設 `AOS_STACK`；零件（aos-loop、aos-fsm、aos-daemon）需要它。

---

**`#/timeouts`**

# 逾時與重試

ctl add/rm/start/stop/sleep/wake 會等回覆；`--timeout-s S` 預設 30。`DaemonMissing` 表示找不到 daemon（沒有 `--daemon` 或 `$AOS_DAEMON`，而且對 aos-agent 來說，從目前資料夾裡某個 agent 的 stack 往上兩層也沒有 daemon；aos-daemon-ctl 還會再試 `./.stack`）、它的目錄不存在，或那裡沒有 daemon 在跑；什麼都沒送出。`DaemonFailed` 表示 daemon 在跑，但逾時之前沒收到回覆。`WaitFailed` 表示預期的結果沒來；kernel 可能沒在跑，或回覆來了但表沒變成那個結果。

逾時的信如果還沒被領走，就會被收回；原因會寫 `letter withdrawn, it will not be applied` 或 `could not withdraw it; it may still be applied`。不要連續送重複的。查 `aos-daemon-ctl ping`、`ctl ls` 和 `ctl state`；確認過結果之後才晚點重試。

`AnswerMissing` 表示沒有回覆可拿，或等到逾時。這不證明 agent 停了，除非它寫 `stopped on an error before answering`：那就是 agent 的腦呼叫失敗、agent 因此停下，這一行帶著那個錯誤（例如 `EndpointFailed HTTP 400 ...`）；去修那個原因，不要乾等。agent 自己會重試的腦呼叫失敗，在等待時是一個警告，並加在逾時那一行的最後（`X's last brain call failed: ...`）。先查狀態，再重新 listen，不要盲目重複 say。如果知道信的名字，用 `listen --letter NAME`；錯誤行會點出那封信和它最後的狀態。

`LetterDropped`（ask、chat、listen --letter）表示 agent 丟掉了那封信，永遠不會回覆它：它不是有效的訊息、被 `before_queue` hook 擋下，或 eca agent 的 CLI 在收下它之後失敗。原因在那一行裡。要新的回覆就再說一次。
