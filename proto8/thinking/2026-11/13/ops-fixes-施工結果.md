# 線巳施工結果（11-13）：ops-agent 六點建議裡使用者裁要做的幾件——信的留底進工作區（A1）、範本 README 指到 CLI 自己的 hook（A2）、畫面的環境變數（B1）、flags 裡的 `--settings`（B2）、定義自帶 CLI 設定（B3）

← [11-13 日索引](README.md)｜出處：[ops-agent-six-suggestions](ops-agent-six-suggestions.md)（三題的裁定記在那份的三題下面）

## 出問題時一步退回

| 哪一件 | 怎麼退 |
|---|---|
| B1、B2、B3（畫面的環境變數、`--settings` 報 `CfgBad`、定義帶 `settings`） | `git revert 2e907fb4e`（程式都在這一個 commit；`~/.local/bin` 的指令直接 import repo，revert 存檔就生效）。退回後已寫出的 `<stack>/<claude 或 codex>/env.json` 沒人讀、留著無害 |
| 只想關掉某一隻的定義設定 | 把那隻 `cli.json` 的 `settings` 鍵拿掉，下一輪（非互動）或下次開畫面就沒有 |
| 某隻因為 `flags` 寫了 `--settings` 停在 `CfgBad` | 把那個旗標從 `cli.json` 拿掉（要帶設定改寫 `settings` 鍵），再 `aos-agent ctl start`；信還在 queue |
| A1（`keep` 收檔名、`--keep-to`） | `git revert d23e1528e`；沒給新參數時行為本來就沒變 |

## 使用者原話與裁定

- 11-13 對 ops-agent-six-suggestions 三題的回覆（逐字）：「都按照建議」——第 1 題乙（定義可以自帶 CLI 設定）、第 2 題乙（索引檢查工具先讓 ops-agent 自己寫，我們不做）、第 3 題甲（收信、寄信都能在工作區留一行）。
- 11-13 在 ops-agent 畫面上直接對它說的（經 ops-agent 來信轉述，逐字）：「我覺得沒差，eca的bash工具，就是讓eca自己的機制擋。頂多加個hook，在eca跳yes/no的時候幫忙接住，寄信給特定目標處理。這個之後再做，這有點麻煩。我覺得現在就是勇敢一點，就全面開放。後面再來做這塊。」

## A1 信的留底進工作區（第 3 題甲）

結論（現況）：

- 給腦的工具：`mailbox_read` 的 `keep` 除了 `true` 也收一個檔名；`mailbox_send` 多一個選填的 `keep`（檔名）。檔名從工作區算（比照 `self_history` 的 `"keep": "FILE"`）。每封信在那個檔追加一行 JSON（jsonl）。沒給、給 `true` 的行為跟以前逐字相同。
- 人用的指令：`aos-mailbox read --keep-to 檔`、`aos-mailbox send --keep-to 檔`（可跟 `--keep` 併用）。
- 一行長這樣：收信 `{"kept": "received", "letter", "sent_at", "in_reply_to", "from", "to", "status", "title", "what", "outputs", "not_done", "decide"}`；寄信同一組鍵、`"kept": "sent"`。
- 寫不了＝`WriteFailed`：收信那邊信留在信箱、下次照樣讀得到；寄信那邊檔開不了就不寄。

代定（可翻案）：

1. **留底那行不放這台機器上的絕對路徑**：沒有 `sender`、`reply_to`；`to` 是路徑（寄到 `box`）時也不放。依據：出處 03 檔「建議留底那行不放 `sender`／`reply_to` 的絕對路徑，只留 `from`／`to` 名字與信名」；`to` 是路徑時取最小＝整個鍵不寫（不另外發明改寫規則）。後果：留底檔可以直接進 git，但看不出要回信到哪——回信要在讀信當下做（印給腦看的那份照舊有 `reply_to`）。
2. `mailbox_read` 的 `keep` 給檔名時**只進檔、不另外留在 `mailbox/archive/`**（一份就好；兩邊都要的人用指令 `--keep --keep-to`）。
3. 每行最前面多一個 `kept`（`received`／`sent`），因為收、寄接在同一個檔。
4. 寄信那行的 `sent_at` 讀自剛寄進對方信箱 `new/` 的那封；對方在這一瞬間已經拿走＝`null`。
5. 上層資料夾不在不替人建（＝`WriteFailed`）。
6. 寄信是「先開檔、寄、再寫那行」：寄出後才寫不了（例如磁碟滿）＝`WriteFailed`，原因句開頭 `letter 信名 was sent, but:`。
7. 格式 jsonl 照出處檔的代定。

動的檔：`cmd/aos-mailbox/aos_mailbox/__init__.py`、`lib/agent/mailbox_read/`、`lib/agent/mailbox_send/`（`_entry`、`_tooldef.json`、`_metainfo.json`）、兩支測試、`cmd/aos-mailbox/README.md`、`lib/docs/03`、P-48 一句、知識庫 `aos/mailbox.json#/tools`（線辰早上補的「寄出的信沒有留底」「`read --all --keep -j >> FILE`」兩條改成現況）、`aos/cli/mailbox.json`、`aos/errors/common.json#/mail`。

測試：新增 `test_mailbox.py` 的 `test_keep_to_appends_one_json_line_per_letter`、`test_keep_to_unwritable_takes_and_sends_nothing`，`test_mailbox_tools.py` 的 `test_keep_file_in_workspace`（外加 `test_refusals` 兩列）。拿 HEAD 的程式跑新測試：`FAILED (failures=2)`、`FAILED (failures=1)`；改後 `Ran 7 tests … OK`、`Ran 4 tests … OK`。

## A2 範本 README 指到 CLI 自己的 hook

`templates/eca-claude/README.md` 加一段「權限與擋 CLI 自己的工具」：範本是全面開放、aos 的 hook 看不到 CLI 自己的工具、要擋用 CLI 自己的 hook（指到知識庫 `aos/cli/eca.json#/cli_hooks`），附出處 02 檔那支最小範例（`host_gate.py`）。範本本身不帶任何這種 hook。

## B1 人開的畫面拿不到 `AOS_CLOCK`（bug）

結論（現況）：`aos-agent open` 開的畫面裡，CLI 與它帶起來的 `aos-mcp` 拿到的 `AOS_HOME`、`AOS_DAEMON`、`AOS_CLOCK`、`AOS_CLOCK_INTERVAL`、`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_LINUX_USER_STACK` 跟那隻的 loop 一致，不再是開畫面那個人的殼的。

- 做法：loop 那邊每一圈（`aos-eca-turn`）與每一題（`cli_ask.ask`，工具形也經過）把自己手上的這幾個變數記進小格的 `env.json`（值沒變不重寫）；`cli_screen.start` 起 tmux 那段暫時換上「殼的環境＋這幾個照 `env.json`」——有記的設成那個值、沒記的拿掉——做完換回。
- 只對接線後才開的畫面有效；已開著的畫面要關掉重開（`aos-agent close` 再 `open`）。
- 還沒記過（畫面比 loop 先開）＝照舊用殼的、stderr 一行 `warning: no env.json in the cell yet …`。

代定（可翻案）：

1. 「loop 那邊沒有的就拿掉」：殼裡有、loop 沒有的（例如人的殼自己設了 `AOS_KERNEL`）在畫面裡不見。依據：任務要的是「一致」。
2. 沒有照出處檔另外在 claude 的 `mcp.json` 明寫 `env`：環境對了，`aos-mcp`、子 agent 那台、Bash 都是繼承，一個機制就夠（KISS）；codex 身本來就明寫，值跟著同一份走。
3. `env.json` 不進 git（`stack.gitignore` 加 `**/env.json`）：裡面是這台的絕對路徑，每圈照實重記。附錄 4 加一列（暫時檔）。

## B2 `flags` 裡的 `--settings` 被靜默蓋掉（bug）

結論（現況）：`cli.json` 的 `flags`／`print_flags` 寫 `--settings`（含 `--settings=…`）＝讀設定時 `CfgBad … has --settings, which aos adds itself; remove it (for --settings: put the settings in the settings key of cli.json; aos merges them into its own)`，在認領信之前停、信留在 queue。`cli_cfg.py` 那句「可重複，不擋」的註解改掉了。接線前唯讀看過 `~/aos-home` 現役六份 `cli.json`，沒有一份寫 `--settings`。

## B3 定義自帶 CLI 設定（第 1 題乙）

結論（現況）：`cli.json` 多一個選填鍵 `settings`——Claude Code `settings.json` 那種物件，或一個 JSON 檔的路徑（相對 `cli.json` 的資料夾，每題重讀）。aos 把它併進自己加的那一個 `--settings`：

- `hooks` 每個事件的表接在一起（定義的在前、aos 的在後，兩邊都跑）；其他頂層鍵定義有寫的照定義、沒寫的用 aos 的。
- 非互動（`claude -p`）與畫面兩條路都帶。有寫 `settings` 時 CLI 行程多一個環境變數 `AOS_CLI_DEF`＝定義資料夾，hook 指令寫 `python3 "$AOS_CLI_DEF/gate.py"`。
- 只有 claude 身認。**codex 身：不適用／另議**（寫了＝`CfgBad`；codex 自己的核准設定這次沒看）。
- 沒寫 `settings` 時兩條路的命令列跟以前逐字相同。**範本不帶 `settings`、預設權限不變**（使用者「現在就是勇敢一點，就全面開放」）；README 與知識庫的 hook 範例只是「想擋的人可以這樣做」。

代定（可翻案）：

1. 頂層鍵撞到 aos 自己要加的（現在只有 a2a 的 `crossSessionInbound`）＝照定義（寫什麼就做什麼）。後果：定義寫 `refuse` 的話，那隻的信投不進收件口、30 秒後自動退回貼字（線壬原本就有的退路）。
2. 新環境變數叫 `AOS_CLI_DEF`，只在有寫 `settings` 時才給（沒寫時行為逐字不變）。
3. `settings` 的內容 aos 不驗（CLI 自己的格式），只驗形狀：是物件、`hooks` 是「事件名: 陣列」。
4. 字串＝檔路徑、物件＝設定本身，所以這個鍵不收指示詞（`{"$env": …}` 會被當成設定物件）。

## 之後要做的方向（今天不做，只寫判斷）

使用者說的「頂多加個hook，在eca跳yes/no的時候幫忙接住，寄信給特定目標處理」：

- 會用到的 CLI hook 事件（判斷，**沒實測**）：Claude Code 在要跳權限確認框時有 `PermissionRequest` 事件（hook 可以直接回允許／拒絕），另有 `Notification` 事件（等人按的時候通知）。前者能「接住並代答」，後者只能「知道它在等」。
- B3 的機制夠不夠接：**帶得進去**——定義的 `settings.hooks` 可以放任何事件，hook 程式用 `$AOS_CLI_DEF` 找自己、用 `aos-mailbox send` 寄信。**但不夠做完整件事**，還缺三樣：(1) 現在範本是 `dontAsk`，CLI 根本不會跳 yes/no（只有 hook 回 `ask` 而且畫面開著才跳；非互動那條路永遠不跳），要先定哪些情況該跳；(2) hook 寄完信要等「特定目標」回覆才能答，hook 有自己的逾時，等多久、等不到算拒絕還是放行要定；(3) 這段期間 `aos-eca-turn` 也在等 CLI（`timeout_ms`），兩邊的期限要對得上。所以它是另一件要設計的事，B3 只是提供了掛 hook 的位置。

## 測試

| 夾 | 新增／結果 |
|---|---|
| `cmd/aos-mailbox/tests` | 新 2 例；改前 `FAILED (failures=2)`，改後 `Ran 7 tests … OK` |
| `lib/agent/mailbox_send/tests` | 新 1 例＋2 列；改前 `FAILED (failures=1)`，改後 `Ran 4 tests … OK` |
| `lib/agent/tests` | 新檔 `test_cli_screen_env.py` 5 例（`test_note_env_keeps_only_the_listed_names_and_rewrites_only_on_change`、`test_screen_env_follows_the_loop_not_the_shell`、`test_no_record_yet_keeps_the_shell_and_warns_once`、`test_start_runs_tmux_with_the_loop_env_and_puts_the_shell_back`、`test_ask_records_the_env_of_the_asking_side`）、`test_cli_settings.py` 8 例（`test_settings_flag_in_flags_is_cfgbad_and_points_to_the_key`、`test_absent_means_exactly_what_it_was`、`test_object_is_merged_under_what_aos_adds`、`test_file_is_read_from_the_definition_folder_each_time`、`test_bad_shapes_are_cfgbad`、`test_print_path_passes_one_settings_flag_and_the_definition_folder`、`test_screen_path_merges_into_its_one_settings_flag`、`test_shipped_templates_have_no_settings`）；改前 `FAILED (errors=5)`、`FAILED (failures=14, errors=4)`，改後 `Ran 5 tests … OK`、`Ran 8 tests … OK`；整夾 11 支全 OK |
| `cmd/aos-eca/tests` | 7 支全 OK |
| `cmd/aos-agent/tests` | 13 支 OK；`test_daemon_down` 2 例紅，改前的 HEAD 上同樣紅（`DaemonFailed` 不是 `DaemonMissing`，ctl 那邊的） |
| `lib/tests`、`templates/tests/test_paths_move` | 17 支全 OK、4 例 OK |

真 claude（2.1.323、haiku；暫存樹 `~/code/si-try-1113/tree`：根 daemon＋一隻 `eca-claude` 範本的 `bob`，定義的 `cli.json` 帶 `settings`——一條 matcher `Bash` 的 `PreToolUse` hook，指令 `python3 "$AOS_CLI_DEF/gate.py"`，含 `forbidden-word` 就 deny）：

| 情況 | 結果 |
|---|---|
| 非互動（畫面沒開），請它跑 `echo forbidden-word` | 沒跑；它回「The Bash call was blocked before it ran: a PreToolUse hook rejected…」；hook 的 log 記到，`permission_mode` 是 `dontAsk`、`AOS_CLI_DEF`＝定義資料夾 |
| 人開的畫面（開畫面的殼沒有 `AOS_CLOCK`、另塞一個假的 `AOS_KERNEL`） | 畫面裡 claude 行程的環境有 `AOS_CLOCK`＝樹的時鐘檔、`AOS_LLM_KERNEL`、`AOS_DAEMON`，假的 `AOS_KERNEL` 不見 |
| 畫面裡叫 `peek_clock` | `{"cycle": 66, "interval_ms": 1000}` |
| 畫面裡請它跑 `echo forbidden-word-2` | 畫面顯示「Not run · permission denied … PreToolUse:Bash hook error: commands with forbidden-word are not allowed by this agent's definition」 |
| 畫面裡 a2a 收件口 | 照常（「› Message from @…」），跟併進去的設定並存 |
| 對照：同一棵樹用改前的程式開畫面 | `peek_clock: error: ClockMissing AOS_CLOCK is not set (this agent is not under a daemon with a clock)`——bug 重現 |

沒驗的：`settings` 給檔路徑那種寫法只有單元測試、沒用真 claude 跑；子 agent（Agent 工具）叫 Bash 時定義的 hook 有沒有被叫；codex 身的畫面（環境那段兩種身共用，只用 claude 實跑）。

## 生效表

| 改了什麼 | 什麼時候生效 | 跑著的 agent 要做什麼 |
|---|---|---|
| `cmd/aos-mailbox`（`--keep-to`） | 存檔即生效（`~/.local/bin` 連到 repo）；只多旗標 | 不用 |
| `lib/agent/mailbox_read`、`mailbox_send`（`keep` 收檔名） | 等 `~/aos-home/lib` 重抄 | 重抄後 aos-mcp 重起才看到新說明：非互動下一輪就是；開著畫面的要重開畫面 |
| `lib/agent/cli_*.py`、`cmd/aos-eca`（B1～B3） | 存檔即生效 | loop 下一圈自己寫出 `env.json`（12:19 唯讀看過 `~/aos-home` 六隻都有了）；**畫面要關掉重開才拿到對的環境變數**；已開著的照舊 |
| `cli.json` 的 `settings` 鍵 | 存檔即生效（現役定義都沒寫，沒有人變） | 要用的那隻：改定義後，非互動下一輪生效、畫面要重開 |
| `flags` 寫 `--settings`＝`CfgBad` | 存檔即生效 | 現役六份 `cli.json` 都沒寫，沒有人停 |
| `stack.gitignore` 多 `**/env.json` | 新抄的 stack 才有 | 已經抄過 `.gitignore` 的 stack，重抄前 `git status` 會多看到 `env.json`（無害） |
| 知識庫、範本、範本說明 | 等 `~/aos-home/knowledge`、`templates` 重抄 | — |

## 給 ops-agent 的說明（新功能怎麼用）

```text
1. Letters can now leave a record in your workspace. mailbox_read {"all": true, "keep": "mail/letters.jsonl"} appends one JSON
   line per letter to that file and removes the letter from the mailbox; mailbox_send {..., "keep": "mail/letters.jsonl"} appends
   one line for the letter you sent. The file name counts from your workspace and its folder must exist. A line holds kept
   ("received" or "sent"), letter, sent_at, in_reply_to, from, to, status, title, what, outputs, not_done, decide, and no absolute
   paths, so it can go into git; answer a letter when you read it (the record does not keep reply_to). keep: true and no keep work
   as before. Available after ~/aos-home/lib is copied again; until then: aos-mailbox -s "$AOS_STACK" read --all --keep-to FILE.
2. Rules for your own Bash can live in your definition instead of the workspace: your owner adds a "settings" key to your
   cli.json (an object like .claude/settings.json, or the path of a JSON file next to cli.json). aos merges it into the --settings
   it passes to Claude Code, on both paths (screen and no screen). In a hook command, $AOS_CLI_DEF is your definition folder:
   "command": "python3 \"$AOS_CLI_DEF/host_gate.py\"". The workspace .claude/settings.json still works too; both count.
   The default stays wide open: no hook is shipped.
3. "--settings" inside cli.json flags is now an error (CfgBad) instead of being silently dropped; use the "settings" key.
4. The screen bug is fixed: a screen opened with aos-agent open now gets AOS_CLOCK, AOS_KERNEL and AOS_LLM_KERNEL as your loop
   has them, so peek_clock and clock_register work there. Your current screen was opened before the fix: it has to be closed
   and opened again (aos-agent close, then open) to get them.
5. The index check tool: write yours as an aos tool (a folder with _entry, one JSON object on stdin) and attach it with
   self_tools; we take it into the stock pack once it has run for a while.
```
