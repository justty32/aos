self_history 的 `range: "-3"` 報 FlagUnknown：查證根因、修成值照傳、加「最後 K 則」（命令列第二輪改成旗標 `-n K`），並盤點其他包命令列的工具（線 top-1121-histrange）。

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

1. **值照傳**：self_history 的 range 一律放在 `--` 後面（`_entry` 一行）。寫壞的 range 現在由 aos-agent 回 `RangeBad`，訊息講合法寫法：`x is not a range (write N, A-B or A- = A to the end)`（第二輪的寫法）。
2. **其他工具**：見下面「同類工具」。
3. **最後 N 則**：第一輪（6c6255fea）做成 range 的位置參數 `-N`（`ls -3` 不用寫 `--`，旗標解析加了選用開關 `numbers`）；使用者看了改成旗標帶值，見下一節，第一輪的寫法與開關都拿掉了。

## 第二輪：最後 K 則改成旗標 `-n K`

使用者 11-21 看了回報（逐字）：

1. 「self_history這塊set竟然不能收-N？爲何？命令列這塊說不定可以改成-N 3, -N -2這樣，用-N或-n都可，隨你。」
2. 「啊，-N "-3"」
3. 「-N "2"，都可以」

旗標的意思是「最後 K 則」，值寫 `3` 或 `-3` 都是最後 3 則。

| 寫法 | 意思 |
|---|---|
| `aos-agent history ls -n 3`、`ls -n -3`、`ls --last 3` | 最後 3 則 |
| `rm -n 2`、`summarize -n 2 TEXT`（TEXT 是 `-` 開頭時寫 `summarize -n 2 -- "-5 degrees"`） | 最後 2 則刪掉／換成一則摘要 |
| `ls 3-5`、`ls 4`、`ls 6-`、`rm 2-3`、`summarize 1-2 TEXT` | 一般範圍，照舊是位置參數 |
| `ls -3` | `FlagUnknown`（裸的 `-3` 不再收） |
| `ls -- -3` | `RangeBad -3 is not a range (write N, A-B or A- = A to the end; for the last 3 messages use -n 3)` |
| `ls -n 0`、`ls -n 9`（只有 5 則）、`ls -n x` | `RangeBad`（`-n 9 asks for the last 9 messages but the history has 5 (write 1 to 5)`） |
| `ls -n 2 3`、`ls -a -n 2`、`rm -n 1 2` | `ArgumentsBad`（擇一） |
| self_history `{"op":"ls","range":"-3"}` | JSON 介面不變；底下改傳 `--last 3`。`-0`、比總則數大在工具這層先報 `RangeBad range "-9" asks for the last 9 messages but you have 6 (write "-1" to "-6")` |

改的地方：`history.py`（`-n/--last`、`last_span`、summarize 有 `-n` 時 TEXT 是第一個位置參數）、旗標解析的 `numbers` 開關拿掉（`tool_io`、`flags`、`common` 回到第一輪之前）、self_history 的 `_entry`、`--help`、apps/agent README、知識庫 `cli/history`、`cli/flags`、`me/self_history`。測試：`test_history` 的 `test_last_n`、`test_bad_range_says_how_to_write_it` 改寫，self_history 改預期的命令列、加 `test_last_k_more_than_the_history`，修前都紅；相關幾夾（`py/tests/apps/agent` 226、self_history 8、self_tools、subagent、旗標與 tool_io 的測試）乾淨複本全綠。

### set 收不收 `-n`（只評估，沒做）

技術上加起來很短（set 多收 `-n K`＝倒數第 K 則），但有三個坑：

- **工具用不到**：history 的最後一則永遠是「正在進行的這一步」（叫 self_history 的那則或這一輪的 user），self_history 給 set 倒數第 1 則一定 `RangeBad`；只有倒數第 2 則以前才改得到，模型得先 ls 算位置，跟寫行號差不多。
- **會跑掉**：在跑的 agent 一直往 history 接新的一行，「倒數第 1 則」每接一行就換一則；寫入前發現檔被動過會重讀重做（最多 3 次），重做時倒數第 1 則已經是別則，改到的不是你看到的那則。正數行號只有刪改前面時才會位移，接新行不影響。要用就得先 `ctl pause`。
- **值的意思要定**：set 只改一行，`-n 3` 是「倒數第 3 則」還是不收大於 1 的值，要另外定；而 ls／rm／summarize 的 `-n 3` 是「最後 3 則」（一段），同一個旗標在 set 意思不一樣容易誤會。

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

第二輪（現行）：

- **字母選 `-n`、長名 `--last`**：小寫跟其他短名一致（`-a`、`-l`、`-j`、`-y`）；`--last` 讀起來就是「最後」。
- **一般範圍留位置參數，最後 K 則只有 `-n` 一種寫法**：位置參數的 `-3`（裸的或寫在 `--` 後）都不收，`-- -3` 的錯誤訊息直接提示 `-n 3`；第一輪加的旗標解析開關拿掉，不留兩種寫法。
- **`-n` 跟 RANGE、`-a` 擇一**，都給＝`ArgumentsBad`。
- **`-n 0`、比總則數大＝RangeBad**，不自動縮成全部（同第一輪）。
- **summarize 有 `-n` 時 TEXT 是第一個位置參數**：TEXT 是 `-` 開頭要先寫 `--`（工具一律帶）；沒 `-n` 照舊 `RANGE TEXT`、TEXT 起原樣。
- **self_history 的 JSON 不變**：`"range": "-3"`（或整數 -3）＝最後 3 則，工具轉成 `--last 3`；K 超出在工具層先報錯，用工具的寫法講。
- **set 不收 `-n`**：等使用者看上面的評估再定。

第一輪（已被第二輪取代，留著當紀錄）：寫法選 range 的 `-3`；`-N` 比總則數大＝RangeBad；set 的 LINE 不收 `-N`；CLI 的 `-3` 不用寫 `--`（旗標解析的選用開關）。
