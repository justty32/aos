self_history 的 `range: "-3"` 報 FlagUnknown：查證根因、修成值照傳、range 加「最後 N 則」`-N`，並盤點其他包命令列的工具（線 top-1121-histrange）。

← [2026-11-21](README.md)

## 使用者原話

- 「self_history的毛病...說說」
- （頂層列了三樣：只修錯誤讓它回 RangeBad／順便查其他包著命令行指令的工具有沒有同樣的問題／讓 range 支援「最後 N 則」）「派線去修，三樣都做」

出處：[tool-desc-瘦身-1121/05](tool-desc-瘦身-1121/05-施工結果.md)「看到的事」第 2 條、小任務表第 7 列（luna 想列最後 3 則，傳 `range: "-3"`，工具回 `FlagUnknown`）。

## 根因（查證過，跟推測一樣）

乾淨複本（HEAD 2c3225a07）用假的 daemon 表直接叫：

| 叫法 | 修前 |
|---|---|
| `self_history {"op":"ls","range":"-3"}`（整數 `-3` 也一樣） | `FlagUnknown unknown flag -3` |
| `self_history {"op":"rm","range":"-3"}` | `RangeBad -3 is not a range (write N, A-B or A-)` |
| `aos-agent history ls -3`、`rm -1` | `FlagUnknown` |
| `aos-agent history ls -- -3` | `RangeBad`（過了旗標解析，但 `-3` 不是合法 range） |

self_history 把 rm／summarize／set 的值放在 `--` 後面，**只有 ls 沒放**，`-3` 就被 aos-agent 當成旗標。下層的旗標解析（`tool_io.tokenize_flags`）本來就有「長得像負數的當位置參數」，但只在前面已經有一個位置參數時才算；`ls -3` 的 `-3` 是第一個，所以不算。

## 三樣各做了什麼

1. **值照傳**：self_history 的 range 一律放在 `--` 後面（`_entry` 一行）。寫壞的 range 現在由 aos-agent 回 `RangeBad`，訊息講合法寫法：`x is not a range (write N, A-B, A- = A to the end, or -N = the last N)`。
2. **其他工具**：見下面「同類工具」。
3. **最後 N 則**：range 多一種寫法 `-N`。`aos-agent history ls -3`、`rm -2`、`summarize -2 TEXT` 都收（不用寫 `--`）；self_history `{"op":"ls","range":"-3"}` 也收。`-0`、比總則數大＝`RangeBad`（`-9 asks for the last 9 messages but the history has 5 (write -1 to -5)`）。self_history 的 rm／summarize 給 `-N` 一定碰到「這一步」，照舊 `RangeBad`、不改。
   - 做法：旗標解析加一個選用的 `numbers`（`aos_flags.parse` → `tool_io.tokenize_flags`），開了就「沒人認又長得像負數的，就算是第一個也當位置參數」；只有 aos-agent history 開。其他指令不變。
   - 說明跟著補：`_tooldef.json` range 那格（`"4", "2-5", "6-" or "-3" (last 3)`）、`aos-agent history --help` 三處 RANGE 那句、知識庫 `aos/me/self_history.json`、`aos/cli/history.json`（多一行 `ls -3` 例子）、`py/aos/apps/agent/README.md`。

## 同類工具

逐支看了「把 JSON 參數接成命令列、再叫另一支 aos 指令」的工具（agent 夾三十多支、aos 夾 feedback、llm_forward；子 agent 盤點，再用真的 `aos_flags.parse` 重現）。共用的 `cmd_call.call`、`mailbox_call` 本身不拼命令列，不是原因。全表在 [self-history-range-1121.json](self-history-range-1121.json)。

**有問題、修了的（6 組，都是同一個病：值當最後一個位置參數、前面沒放 `--`）**，修法都是在值前面加 `--`：

| 工具 | 參數 | 修前 |
|---|---|---|
| self_history | `range`（ls） | `-3` → FlagUnknown |
| self_tools | `name`（get／rm）、`path`（add） | `-x` → FlagUnknown；`--help` 印說明、退 0，工具當成功回；`--replace` 被吃掉再報缺參數 |
| self_hook | 同上 | 同上；`--async` 這類當 path 會默默生效 |
| agent_def 的 tools | 同上（共用 `def_edit.tools`） | 同上 |
| self_llm | `keys`（rm）、`settings` 的鍵（set） | 最糟：`rm ["a", "--target", "v"]` 或鍵寫 `--target`，會默默把目標改成別隻 agent |
| agents_ctl、subagent | `name`（rm）、`def`（add）（共用 `agents_cmd`） | `-x` → FlagUnknown；`--purge` 這類被吃掉再報缺名字 |

其餘（board_read、mailbox_*、clock_register、goal、self_system、self_state、self_ctl、do_task、fork、tools_def、kernel_gate、llm_forward、user_send、user_verify、todo、hook 那幾支）值已在 `--` 後、是帶值旗標的值、走 stdin、或是絕對路徑，沒問題。

## 只列不修的鄰近問題

都不是減號那個修法能順帶解的，只列：

- **值剛好是 `--`**：board_set 的 `text`、board_wait 的 `what` 被下層（`board_cmd._words`）吃成空字串；feedback 的 `command`／`pain`／`suggest` 被下層（`apps/feedback`）在 `--` 後再刪一次，`pain` 是 `--` 時 `suggest` 會補位成 `pain`（資料錯位）。
- **值剛好是 `-`**：mailbox_send 的 `what`、clock_register 的 `text` 會改讀 stdin，回清楚的錯（不是 bug，只是怪）。
- **enum 沒在工具層驗**：`tool_io` 只驗型別，user_send 的 `kind`、mailbox_send 的 `status` 靠下層擋。
- **subagent 的 `ctl where NAME`**：名字是 `-` 開頭、而且 `ctl add` 印出空行時才會錯，條件很窄。
- 空字串：self_* 多半先擋成 ArgumentsBad；board_set、mailbox_send 的選填鍵空字串被默默略過。值含換行不會被吃掉。

## 測試

新測試修前都紅、修後都綠：`py/tests/apps/agent/test_history.py` 加 `test_last_n`、`test_bad_range_says_how_to_write_it`；self_history 加 `-3` 放 `--` 後、`-N` 碰到這一步；self_tools、self_hook、self_llm、agents_ctl 各加減號值的例子（subagent 跟著改預期的命令列）；agent_def 用真的 aos-tools 驗 `-x`、`--help`、`-3` 回 ToolMissing（修前 FlagUnknown）。乾淨複本（HEAD e674b1105＋本線的檔）全套逐夾跟基準比：只多了新測試，沒有新紅（`apps/feedback` 基準就紅，`templates/tests/agent-fsm` 另跑也全綠）。

## 替使用者定的細節

- **寫法選 `-3`**：現有文法是 `N`、`A-B`、`A-`，`-3` 原本不合法（回 RangeBad），沒有舊意思要讓；模型自己就會這樣寫（luna 就是）。可能的誤讀是照 `A-` 對稱讀成「從頭到第 3 則」，說明一律寫明 `-N = the last N`。
- **`-N` 比總則數大＝RangeBad**，不自動縮成全部：跟現有「超出範圍＝RangeBad」一致，`rm -9` 不會默默刪光。
- **`set` 的 LINE 不收 `-N`**：只說要「最後 N 則」的 range；`set -1` 回 `RangeBad ... (write N)`。
- **CLI 的 `-3` 不用寫 `--`**：用選用開關只開在 aos-agent history，不改全部指令的解析規則。
