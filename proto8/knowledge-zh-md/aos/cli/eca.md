# `knowledge/aos/cli/eca.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/eca.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/eca.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/External coding agents (eca)`**

# 外部程式碼 agent（eca）

eca agent（由 aos 執行的 claude、codex 或 pi，像 `templates/eca-claude` 和 `templates/eca-pi`）背後的兩個指令。人兩個都用 `aos-agent` 操作；只有測試時才自己跑它們。

用 CLI 自己的 hook 看守 CLI 自己的工具（Bash ...）：`aos/cli/eca.md#/Guarding the CLI's own tools (claude)`。

pi 身體（kind pi，每則訊息一個回覆，沒有畫面）：`aos/cli/eca.md#/The pi body (kind pi)`。

**`#/aos-eca-turn: one turn`**

# aos-eca-turn：一回合

```sh
AOS_STACK=/abs/st AOS_WS=/abs/ws aos-eca-turn /abs/def      # loop form
echo '{"prompt": "hello there"}' | AOS_STACK=/abs/st aos-eca-turn --one /abs/def
# FAKE: hello there        (tool form: prints the answer)
```

eca agent 的 loop 的本體：它把 `$AOS_STACK/queue` 裡的每封信當成一個提示（prompt）交給 CLI，等回覆，然後把兩者都附加到 `history.jsonl`。DEF_DIR 是一個絕對路徑的資料夾（`AgentBad`），裡面有 `cli.json`（`CfgMissing`）；旗標放在它前面或後面都可以。`--on-empty stop`（預設）在佇列空的時候以結束碼 10 結束，`idle` 則是 0。`--on-busy yield`（預設）在有人掛著時先不處理這批，`answer` 會等。`--prompt FILE`（相對於 DEF_DIR；`PromptMissing`）是對話歷史和佇列都空的時候的開場訊息。`--one` 不收 `--on-empty`、`--prompt`（`ArgumentsBad`）。用 claude 而且畫面開著時，每封信會以一則有署名的跨工作階段訊息，送到 CLI 自己的訊息 socket（畫面顯示 `Message from @NAME`；模型會被告知這不是它的使用者打的）。NAME 是 `aos-agent say` 或 `chat` 的寄件人；沒有寄件人的信（新信通知、時鐘和目標的信、開場紀錄）署名 `aos通知中心`。寄件人名字不在 `history.jsonl` 裡；信的名字在：每封信那一列有 `"aos": {"letter": NAME}`，回覆有 `"aos": {"answer_to": [NAME, ...]}`（這一回合的每封信，也包括它回覆期間到的那些）。`$AOS_STACK/letters.json` 列出已經交出去、還沒回覆的信（`pending`），和被丟掉的信（`dropped`：壞掉的信、被 `before_queue` hook 擋下的信、或 `failed`）。它們會立刻送進去，就算有人掛著或有一回合正在跑也一樣，它回覆期間到的信也是。走這條路時，`--on-busy` 只決定拿不到鎖時怎麼辦。畫面關著時，`cli.json` 有 `"live_mail": true` 的 claude 身體會讓 CLI 的 stdin 保持開著（`--input-format stream-json --replay-user-messages`）：它回覆期間到的信會被寫進去，一行一封，模型會在它下一個工具步驟讀到（很長的前景指令仍然會讓它們延後；CLI 也會收到一行短短的系統文字，請它把長指令放到背景跑，並加上 `--system-prompt-snapshot off`，讓接續的對話也看得到；這是請求，不是保證）。一旦結果出來、每一行都被讀走、沒有背景工作在跑、也沒有新信在等，stdin 就會關掉。回覆是這一回合的每個結果，加上模型在讀進一封信之後、下一個工具之前說的話，用空行接成一筆對話歷史。最多加入 `live_mail_cap.letters` 封信（預設 5），`live_mail_cap.seconds`（預設 300）之後就不再加；其餘的等下一回合。冷卻（cooldown）剛結束的那一回合一封都不加。壞掉的 `live_mail_cap` 是 `CfgBad`。預設關閉。如果 socket 不知道在哪或連不上，或 30 秒內沒有回條，aos 會像以前一樣打字進畫面（stderr 上一個警告；回條沒來之後，對那個畫面會一直這樣，直到它下一次工作階段開始：重新開啟、/clear、/compact、/resume）。比較舊的畫面、codex、非互動的路徑、斜線指令和 `--one` 都像以前一樣打字或執行。`cli.json` 裡的 `"a2a": false` 會關掉它。提示交出去之後的失敗（`CliFailed`、`ReplyMissing`）會開始一段冷卻（`cooldown.json`，`aos-agent ctl ls -l` 會顯示）。claude 的 print 形式下，標示暫時性 API 錯誤（429、408、409、5xx、overloaded、連線失敗，或 CLI 自己的 api_retry 放棄）的結果行會以 0 結束，而不是停掉 loop：沒回覆的信留在 `retry.json` 裡待處理。冷卻之後，一個 `[aos] retry: ...` 提示會接著同一個對話，不重複它們的文字，也不領新的信；它的回覆算是那些信的回覆，並清掉重試紀錄。如果對話沒有存下來，就開一個新的，帶著對話歷史和重試提示。連續第 10 次暫時性失敗算成永久性（信被丟掉、重試紀錄被刪掉、結束碼 1）。暫時性的斜線指令失敗會把那封斜線信當 failed 丟掉，以 0 結束，並且不動之前的任何重試紀錄。其他失敗會把信當 `failed` 丟掉（這時 `aos-agent ask` 會說 `LetterDropped`），並像以前一樣停下；codex 一律維持舊的行為。不是文字的 claude 結果是 `CliFailed`。claude 的 `brain_failed` 事件帶有 `name`、`reason`、`code`、`retry`、`attempt`、`dropped`，暫時性錯誤還有 `wait_s`，有的時候還有 `status` / `cause`；codex 除了 hook 引擎的欄位，只留 `name` 和 `reason`。共用的 brain_notify hook 用 `CliFailed` / `ReplyMissing` 上的布林值 `retry` 來說明是會接續還是永久停下；沒有那個布林值時（codex），它安靜地什麼都不做。llm.json 裡的 `reasoning_effort`（模型想得多用力）會變成 claude 的 `--effort`（`low`、`medium`、`high`、`xhigh`、`max`；其他任何值都是 `CfgBad`；在 codex 上任何 `reasoning_effort` 都是 `CfgBad`）；它每回合都會重讀，但開著的畫面會維持開啟時的等級，直到關掉再開。對話歷史變了，就開一個新的對話，把紀錄帶過去（最多 cli.json 的 `reseed_bytes`，預設 48000）。內容剛好是 `/clear`、`/compact`、`/status`、`/usage` 或 `/exit` 的信（用 `aos-agent say` 或 `chat` 寄的），由 aos 來做，並以一則 `[aos] slash: ...` 訊息回覆（`/compact`、`/usage` 用 claude 自己的話）：`/clear` 把 `history.jsonl` 移到 `history_removed.jsonl`，並開一個新的對話；codex 的 `/compact` 開一個新的 thread，帶著 aos 的紀錄；`/exit` 關掉畫面。claude 的 `/compact` 之後，對話歷史就是它的摘要。`/compact INSTRUCTIONS` 也是 `/compact`（claude 會拿到給它摘要用的指示；codex 會忽略）。`/compact` 信一律自成一批：它前面的信先回覆，它和它後面的信在 `cur/` 裡等下一回合。eca-claude 範本的 `context_wrap` hook（on_clock，`lib/tools/agent/context_wrap`）會盯著上下文（context）：到了視窗的 `config.percent`（預設 35）時，它送一則收尾訊息，然後等那則被回覆而且佇列是空的，再送一封只有 `/compact` 的信；直到之後某一回合讀到低於上限之前，它都不會再重複。Claude Code 會自己壓縮（因為 `/compact` 或滿了的時候）；範本的 `compact_hook` 把它的 PreCompact / PostCompact hook 變成 aos 的 hook 點 `before_compact`（改摘要指示、給一段 `restore` 文字，會加在壓縮之後緊接的位置，或以結束碼 10 擋下它）和 `after_compact`（只通知，帶 `summary`）：`aos/me/self_hook.md#/Hook events`。被擋下的 `/compact` 信會用 CLI 自己的拒絕行回覆；對話歷史不變。畫面開著時，`/clear` 和 `/compact` 會被打字進畫面（它回覆時不會，claude 輸入框有文字時也不會：見 `#/screen`）。以 `/goal` 開頭的信（`/goal TEXT`、`/goal clear`、`/goal`）是 CLI 自己的目標，跟 aos 的 `goal.json` 是分開的：畫面開著就打字進去，不然就原樣交給 claude（codex exec 沒有 `/goal`；aos 會這樣說）。codex 的畫面問 `Replace goal?` 時，aos 會選 `1. Replace current goal`；其他任何問題它都不按。`TrustMissing`：見 `aos/cli/errors.md#/Codes you will meet`。其他代號：StackMissing、HistoryBad、PostFailed、WriteFailed、HookFailed、HooksBad、ToolsBad、CfgBad、ToolsMissing、CliMissing。

**`#/aos-eca-screen: the screen`**

# aos-eca-screen：畫面

```sh
aos-eca-screen --eca /abs/def open --detach   # screen opened (...)
aos-eca-screen --eca /abs/def watch           # follows live.jsonl until one answer ends
aos-eca-screen --eca /abs/def close           # closed
aos-eca-screen --eca /abs/def peek /usage     # the /usage answer, printed at once
```

人用的是 `aos-agent open / close / watch / peek -t NAME`（`aos/cli/talk_settings.md#/chat and screens`）。它讀 `AOS_STACK`（沒設 = `StackMissing`）和 `AOS_WS`；ECA_DIR 裡放 cli.json。`--eca` 放在動作前面或後面；`--detach`（沒有短名）放在 open 後面。資料夾裡沒有 cli.json（open、watch、peek）或沒有 `--eca` = `ArgumentsBad`；cli.json 壞掉時 close 仍然會關，附一個警告；不認得的動作 = `CommandUnknown`。open 除非 detach，否則會掛上去；Ctrl-]（或 Ctrl-\）離開時畫面繼續跑。close 會保留對話，正在回覆時拒絕（`SessionBad`）。watch 在一個回覆結束後結束，或在它的 daemon 列停止執行或消失時結束（daemon 或表讀不了：它繼續等）；Ctrl-C 以結束碼 0 離開它。

在畫面上打的斜線指令會送到 CLI 本身。aos 會跟著它：CLI 換到另一個對話時（claude `/clear` 或 `/resume`），下一個回覆就接在那個對話裡；`/clear` 也會清空 agent 的 `history.jsonl`（codex：當回覆來自一個只有這一回合的 thread 時；有更早回合的 thread 算 `/resume`，對話歷史不變）。claude 的 `/compact` 保留對話，並用 claude 的摘要取代對話歷史（一則 `[aos] summary: ...` 訊息）；codex 的 `/compact` 不給摘要文字，所以對話歷史變成 codex 保留下來的使用者和助理訊息（來自它壓縮後的 `replacement_history`，不含工具定義、工具呼叫和 `<environment_context>` 區塊；什麼都讀不到時，對話歷史不變）。舊訊息會移到 `history_removed.jsonl`。`/exit` 結束畫面；下一則訊息會在沒有畫面的情況下回覆。

`peek /status` 或 `peek /usage`（`aos-agent peek -t NAME /usage`）印出跟寄信一樣的回覆，但立刻印出，agent 在一回合中也可以：沒有信、對話歷史裡沒東西、cell 上沒有鎖、沒有打字進畫面（`/usage` 是另外跑一個 `claude -p --no-session-persistence`；codex 在畫面以外沒有用量報告，它會這樣說）。其他指令：`ArgumentsBad`。全景頁的用量和狀態按鈕就是用它；`/context` 仍然走佇列（它不能被打字進一個正在回覆的畫面）。

畫面開著時從佇列來的斜線信（例如 `context_wrap` 送的那封單獨的 `/compact`）：如果畫面正在回覆（cell 裡有 `busy.txt`），或（claude）它的輸入框有人打了字、或讀不到（有別的對話框開著），就不會打字：信留在 `cur/` 裡，下一輪再試，並在 agent 的紀錄裡留一個警告；aos 絕不清掉輸入框（那會吃掉人打的字）。在那次查看和打字之間那一瞬間按下的鍵，仍然可能接到指令上（已知的限制）。否則 aos 會把它打字進畫面（tmux `send-keys -l`，半秒後按 Enter），然後最多等 120 秒讓 CLI 的 hook 取代對話歷史（claude：SessionStart compact 或 clear），再回覆那封信；如果到時候對話歷史還沒變，回覆會這樣說，而且指令不會再打一次。同樣的輸入框檢查也適用於 claude 畫面上的 `/goal` 和 `/context`；codex 的畫面不檢查。

畫面開著時上下文有多滿：互動式的 claude 不寫 `live.jsonl`，所以 `context_wrap` 讀 claude 自己的對話紀錄（transcript）（`<cell>/transcripts/claude-<session>.jsonl`，或 `~/.claude/projects/*/<session>.jsonl`）：最後一個完成回合的用量；壓縮剛結束時，直到下一個回覆之前都讀不到數字。對話紀錄裡沒有上下文視窗的大小：它來自 hook 的 `config.window`，不然就來自 `live.jsonl` 裡更早的一個 `claude -p` 回合；兩者都沒有時，hook 保持安靜，所以一個從來只在畫面上講過話的 agent 需要 `config.window`（`aos/me/self_hook.md#/Hook options and answers`）。

**`#/External MCP servers (claude and codex)`**

# 外部 MCP 伺服器（claude 和 codex）

每個伺服器一個伺服器檔；在 `cli.json` 裡列成 `"mcp_servers": ["mcp/site.json"]`（相對於 cli.json，可以用指示詞（directive））。CLI 自己連線；列出來的伺服器是完全核准的；`only` / `except` 挑工具。工具名是 `mcp__<name>__<tool>`。

```json
{"description": "<one line>",
 "mcp_server": {"name": "site", "transport": "http", "url": "https://<host>:<port>/mcp",
                "bearer_token_env": "SITE_TOKEN", "env_file": "/home/<me>/.config/<agent>/site.env", "ca_file": "/home/<me>/.config/<agent>/ca-bundle.pem"}}
```

stdio：`"transport": "stdio", "command", "args", "env", "env_file"`；它透過 `aos-mcp-launch <server file>` 啟動，這個程式只把 env_file 讀進伺服器的行程裡。伺服器在伺服器檔所在的資料夾裡啟動：相對的 `command` 和 `args` 路徑從那裡算（要工作區裡的路徑就寫 `{"$env": "AOS_WS", "$path": "data"}`）。它也會拿到啟動它的人的環境（用 claude 時：整個 shell 的環境，包括 API 金鑰）。

- `env_file` 現在跟 aos-tools 的 env 檔用同一套 dotenv 子集：`${X}` 展開、行內 `#` 註解和嚴格成對的引號；`A=x # note` 讀成 `x`，接著 `B=${A}y` 讀成 `xy`。
- token 檔在 CLI 啟動時讀；codex 只在它自己的環境裡拿到這個值，它的 shell 的環境裡沒有（會加上 shell_environment_policy.exclude）；claude 透過 headersHelper 拿到，絕不放在它的環境裡。
- `ca_file` 設定 SSL_CERT_FILE / CODEX_CA_CERTIFICATE（codex）或 NODE_EXTRA_CA_CERTS（claude）。
- 壞掉的伺服器檔，或指令找不到、執行不了的 stdio 伺服器（每次 CLI 啟動前都會檢查），會被略過，並留一行 `cli_session: warning: external MCP server ... skipped`；其他的仍然會掛上。沒有畫面的 claude 回合，在 CLI 回報時會印出 `warning: external MCP server NAME was not connected when claude started (status ...)`；之後才壞掉的不會回報。
- 絕對不要用 `aos-agent ctl add --envs` 傳機密：它會以純文字存在 procs/<name>/exec.json 裡。
- 或者用 aos-mcp-import 把同一個伺服器檔凍結成 aos 工具（`aos/cli/mcp_import.md`）；這樣 aos 的 hook 就看得到那些呼叫。每個伺服器挑一種方式。

**`#/Guarding the CLI's own tools (claude)`**

# 看守 CLI 自己的工具（claude）

aos 的 hook（`before_tool`、`after_tool`）只看得到 aos 工具。要檢查 Bash、Write 或 Edit，用 Claude Code 自己的 hook。

aos 在你的工作區裡啟動 claude，沒有把它隔離：工作區的 `.claude/settings.json` 照常會被讀，裡面的 hook 會跟 aos 加的 hook 一起跑。原裝範本用 `--permission-mode dontAsk` 跑，而且允許 Bash：沒有人確認指令。

原裝範本沒有這種 hook。要把關 Bash，在工作區的 `.claude/settings.json` 加一個 matcher 是 `Bash` 的 `PreToolUse` hook：

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/path/gate.py"}]}]}}
```

那個程式從 stdin 收到 JSON 格式的呼叫（指令行是 `tool_input.command`），並用印出的東西做決定：

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "why"}}
```

回覆會造成什麼：

- 什麼都沒印：指令執行，沒有人被問。
- `deny`：指令不執行；你會拿到原因。
- `ask`：畫面開著時，畫面上會出現一個確認框，等人回應。沒有畫面時（aos 跑 `claude -p`）它算 deny。所以「先問使用者」需要畫面開著；被拒絕時，回報這件事並請人開畫面；不要換個寫法來繞過關卡。
- 同一個檔裡的權限規則（`permissions.ask`、`permissions.deny`）在這個模式下只會拒絕，不管有沒有畫面；`permissions.ask` 不會出現確認框。

沒涵蓋到的：人在畫面上用 `!` 打的指令（不會呼叫任何 hook）；codex。

只給一個 agent 的規則：把同樣的設定放在它的定義裡，放在 `cli.json` 的 `settings` 鍵底下（一個像 `.claude/settings.json` 的物件，或 `cli.json` 旁邊一個 JSON 檔的路徑）。aos 會把它合併進自己加的 `--settings`：兩邊的 hook 都會跑。在 hook 指令裡，`$AOS_CLI_DEF` 是定義夾：`"command": "python3 \"$AOS_CLI_DEF/gate.py\""`。定義由它的主人（一個人）改，不是由你改（`aos/rules.md`）。只限 claude；其他任何 kind（codex、pi）上 `settings` 都是 `CfgBad`。

不要把 `--settings` 放在 `cli.json` 的 flags 裡：`CfgBad`（agent 在收任何訊息之前就停下）；用 `settings` 鍵。

沒有畫面的回合會啟動一個新的 CLI，所以會重新讀那個檔。開著的畫面會不會吃到變更，沒有驗證過：關掉再開。

**`#/Delayed screen closure`**

# 延後關閉畫面

eca 範本有 screen_linger_start（after_start，排第一）和 screen_linger_stop（after_stop），逾時 4000 ms；處理程式遇到錯誤只會警告並以 0 結束，所以失敗不會停掉 loop。stop 會在畫面的 tmux 伺服器上排定關閉；start/wake 會取消它。cli.json 的 screen_close_after_s 是以秒為單位的非負整數：預設 600，0 會透過 reap 立刻關閉。改過的設定只在下一次 stop 才生效。

排定的命令（order）存在 <stack>/<kind>/screen_close.json。reap 會檢查 token、tmux 伺服器的身分，以及本機 loop 的 pid/ticks/boot_id；它絕不讀 daemon 的表。新的 loop 或畫面不會被關；無法驗證的活著的 pid 會保留命令並警告。cell 鎖忙碌時每 30 秒重試，最多十次。掛著在看的人也會被斷線。把兩個 hook 都設成 null 就停用關閉。`aos-agent ctl stop` 本身不會關畫面，所以 stop 之後這兩個 hook 是唯一會關畫面的；`ctl rm` 和 `ctl set-def` 仍然會立刻關掉它。

沒有 sweeper 當後備：沒有 after_stop 的 SIGKILL/OOM，或在 agent 已經停下時開畫面，都不會排定關閉。搬動整棵樹可能讓排定的絕對路徑指令失效。需要 tmux 3.2 或更新的版本。

**`#/The pi body (kind pi)`**

# pi 身體（kind pi）

`cli.json` 裡的 `"kind": "pi"` 會執行 pi 程式碼 agent（`templates/eca-pi`）。`pi` 必須在 PATH 上，它所跑在上面的 `node` 也是（pi 的啟動程式開頭是 `#!/usr/bin/env node`；結束碼 127 表示其中一個不見了）。開畫面的 shell 也兩個都需要。

- 每一批是一次 `pi --mode rpc --no-approve --session-dir <cell>/pi-sessions --session-id <id>` 執行：aos 把提示當成一個 `prompt` 命令送出，執行在 `agent_settled` 結束。aos 在第一回合產生 id（`session.txt`）；同一個 id 就接續同一個對話。對話檔是 `<cell>/pi-sessions/<time>_<id>.jsonl`（cell = `$AOS_STACK/pi`）。事件寫到 `<cell>/live.jsonl`。
- 它回覆期間到的信，每封送一個 `steer`；pi 在下一次呼叫模型之前讀它們，全部都在 `agent_settled` 之前。回覆是每一段用空行接起來（對提示和每封信各一個回覆，或一個涵蓋全部的回覆）。cli.json 裡的 `"live_mail": false` 會關掉這個（信等下一回合）；`live_mail_cap` 跟 claude 一樣。
- 就算模型呼叫失敗，pi 也以 0 結束：以 `stopReason` `error` 或 `aborted` 結束的回覆是 `CliFailed`，附上 pi 的 errorMessage。失敗不分暫時性和永久性（跟 codex 一樣）；pi 會先自己重試。
- 畫面：`aos-agent open` 在 tmux 裡用同一個對話啟動互動式的 `pi`（`--tui-mode regular`），帶著 aos 的畫面擴充（`<cell>/pi-aos-screen.mjs`，它會載入 `lib/aos/agentlib/pi_aos_screen.mjs`）。它把每個結束的回合回報給 aos（`<cell>/turns.jsonl`），跟著 `/new` 和壓縮走，而且畫面開著時，aos 的信會經過 `<cell>/pi_inbox/` 進到對話裡（有回合在跑時是一個 `steer`）。`aos-agent close` 結束它；`ctl stop` 之後，畫面在 `screen_close_after_s`（預設 600）之後關掉。
- 人在畫面上打的東西和 pi 對它的回覆，在 `turns.jsonl` 和 pi 的對話檔裡，不在 aos 的對話歷史裡。經過 inbox 送的信沒有寄件人那一行。
- aos 工具：每次執行前，aos 會寫 `<cell>/pi-aos-mcp.mjs`，一個登記 aos MCP 伺服器的一行 pi 擴充，並用 `-e` 傳進去。工具是直接宣告的：`mcp__aos__NAME`。`mcp_servers`（外部 MCP）對 pi 是 `CfgBad`。
- `system` 用 `--append-system-prompt FILE` 附加，每次執行都重新讀。llm.json 裡的 `model` 會變成 `--model PROVIDER/ID`；沒有 = pi 自己的預設（`pi --list-models`；預設必須是你已登入的供應商）。llm.json 裡的 `reasoning_effort` 會變成 `--thinking`（`off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`；其他任何值都是 `CfgBad`）。pi 把等級記在它的對話裡：`aos-agent llm rm reasoning_effort` 之後，同一個對話會維持最後的等級；新的對話（`/clear`）從 pi 的預設開始。
- aos 會加上 `--mode`、`--session-dir`、`--session-id`、`--no-approve`；在 flags 裡寫這些，或 `-p`、`--print`、`--session`、`--no-session`、`--fork`、`-c`、`--continue`、`-r`、`--resume`、`--approve`、`-a` 或 `-na`，都是 `CfgBad`。
- 權限：pi 什麼都不問，也沒有沙盒。它的 read、bash、edit 和 write 以這個 Linux 使用者的身分執行。`--no-approve` 只是把工作區的 `.pi/` 設定、MCP 檔和擴充擋在外面；`AGENTS.md` / `CLAUDE.md` 仍然會被讀。
- 斜線：沒有畫面時，`/compact [INSTRUCTIONS]` 會在同一個對話上啟動一個 `pi --mode rpc`，送它 `compact`；對話歷史變成 pi 的摘要（對話太短時 pi 會拒絕；這時對話歷史不變）。畫面開著時就打字進去；pi 沒有壓縮時，aos 等 120 秒，然後回覆說對話歷史沒有變。`/clear` 開一個新的對話（在開著的畫面上打成 `/new`）。`/goal` 和 `/usage` 回覆為無法使用；`/status` 可以用。
- context_wrap：範本裡沒有；pi 的事件帶有 token 數，但沒有上下文視窗：給 hook `config.window`。
