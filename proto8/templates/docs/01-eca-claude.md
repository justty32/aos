← [回入口 README.md](../README.md)｜段落：外部 coding agent 範本（eca-claude）｜上一份：—｜下一份：[02-agent-fsm](02-agent-fsm.md)

## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../../py/docs/05-commands.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。CLI 對話共用 [py/aos/agentlib/cli_session.py](../../py/aos/agentlib/cli_session.py)，介面宣告共用 [py/aos/declared_files.py](../../py/aos/declared_files.py)（K-5）；前者在 `aos.agentlib`、後者在 `aos` 頂層（裝好在 `lib/aos/`），不 import 命令列那套 `aos.flags`。設計：[thinking 2026-10-30 eca](../../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（沒有 codex 版範本，只差 `cli.json`：要就複製一份、`cli.json` 換成下面這份；**沙盒是 `workspace-write`**，codex 用自己的指令在工作區讀寫（11-12 使用者「codex拿掉唯讀沙盒」；不是 `danger-full-access`，隊長代定、使用者「可以先定這樣」，[thinking 11-12 eca-file-tools](../../thinking/2026-11/12/eca-file-tools.md)）。不要照抄 py/tools/agent/codex 那支工具的 `cli.json`：那是給腦叫的 codex 工具，沙盒唯讀。）第三種身 pi（11-18）有自己的範本與說明：[03-eca-pi](03-eca-pi.md)。

```json
{"kind": "codex",
 "flags": ["-c", "sandbox_mode=\"workspace-write\"", "-c", "approval_policy=\"never\""],
 "print_flags": [],
 "timeout_ms": 0}
```

**aos 自己會加的旗標，`flags`／`print_flags` 不要再寫**——寫了＝讀設定時 `CfgBad …: print_flags has --skip-git-repo-check, which aos adds itself; remove it`，這隻停下、信留在 queue（不進冷卻、不掉信），把那個旗標拿掉再 `aos-agent ctl start` 就接著答：

| 身體 | 寫了＝`CfgBad` | aos 有宣告才加、你也可以自己寫的 |
|---|---|---|
| codex | `--skip-git-repo-check`、`--json`、`-o`／`--output-last-message`（codex 不收重複的旗標，寫第二次它退 2） | `-c …`（`mcp_servers.*`、`developer_instructions`、畫面的 `notify`；`-c` 可以重複） |
| claude | `-p`／`--print`、`--output-format`、`--session-id`、`--resume`／`-r`、`--continue`／`-c`（輸出格式與接哪段對話歸 aos）、`--settings`（CLI 只認命令列上最後一個，aos 自己那個接在後面；要帶設定寫 `cli.json` 的 `settings` 鍵，見下） | `--mcp-config`、`--allowedTools`、`--append-system-prompt-file`、`--system-prompt-snapshot`、`--model`（`llm.json` 有寫就換掉）；`--agents` 跟 `tools_sub` 同寫＝`CfgBad` |

**定義自帶 Claude Code 設定（`cli.json` 的 `settings`，選填；使用者 11-13「都按照建議」，[ops-agent-six-suggestions 第 1 題乙](../../thinking/2026-11/13/ops-agent-six-suggestions.md)）**：值是 Claude Code `settings.json` 那種物件（`hooks`、`permissions`…），或一個 JSON 檔的路徑（相對從 `cli.json` 的資料夾算，每輪重讀）。aos 把它併進自己加的那一個 `--settings`：`hooks` 每個事件的表接在一起（定義的在前、aos 的在後，兩邊都會跑）；其他頂層鍵定義有寫的照定義、沒寫的用 aos 的。非互動與畫面兩條路都帶。有寫 `settings` 時 CLI 行程多一個環境變數 `AOS_CLI_DEF`＝這份定義資料夾的絕對路徑，hook 指令寫 `python3 "$AOS_CLI_DEF/gate.py"` 就找得到定義裡的檔。只有 claude 身認（codex 身寫了＝`CfgBad`；codex 的核准設定另議）；不是物件、檔讀不了、`hooks` 不是「事件名: 陣列」＝`CfgBad`。內容 aos 不驗，照樣交給 CLI。範本本身不帶 `settings`（預設全面開放）。跟工作區 `.claude/settings.json` 的差別：這份只管這隻 agent，不影響同一個資料夾的其他 session；兩邊都有就都算數。

**畫面裡的環境變數跟 loop 一致（11-13 修）**：`aos-eca-turn` 每一圈把自己手上的 `AOS_HOME`、`AOS_DAEMON`、`AOS_CLOCK`、`AOS_CLOCK_INTERVAL`、`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_LINUX_USER_STACK` 記進小格的 `env.json`（值沒變不重寫），`aos-agent open` 開畫面時這幾個照它給（有記的設成那個值、沒記的拿掉），不用開畫面那個人的殼的——以前人開的畫面裡 `peek_clock` 會回 `ClockMissing`。還沒記過（畫面比 loop 先開）＝照舊用殼的、stderr 提醒一行。已經開著的畫面不會變，關掉重開才拿到。

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 0},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json", "on_start": …, "on_stop": …}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；三扇窗落在 $AOS_STACK；on_start／on_stop＝aos-hook fire -q --stop-on-nonzero --def $AOS_CD 發 after_start／after_stop，before_run／after_run 預設不接）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、tools_sub、timeout_ms〔0＝不限時〕）：--tools Read,Write,Edit,Glob,Grep,Bash,Agent,Skill、--permission-mode dontAsk、--allowedTools Write,Edit,Bash、--strict-mcp-config；
              tools_sub＝子 agent 那台的登記檔（見下「子 agent 與 skill」）
              （claude 內建的寫檔、改檔、指令都開，aos 不給檔案與 shell 工具；--model 不寫在這，見 llm.json；不加全繞過權限的旗標）
  llm.json    腦設定：{"model": "sonnet"}（cli_session 每題依 interfaces.json 的 llm 宣告讀定義並疊 stack 下同一相對路徑的覆蓋層，補成 --model）；認 model 與 reasoning_effort（思考程度，補成 --effort，見下「思考程度」）；claude CLI 沒有 temperature 等取樣旗標，那些鍵這邊沒有對應
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
  tools.json  aos-tools 的登記檔：`"$override"` 一串 [py/packs](../../py/packs/README.md) 八包（gadgets、events、self、def、mailbox、json〔json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set〕、jsonx〔jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_get、jsonx_multi_set〕、index〔index_view〕），self 包比照 agent-fsm 關掉 self_llm、self_system、self_history、self_ctl（11-21 線 top-1121-ecaeffort，照使用者對 agent-fsm 選的「self 只留兩支」，[tool-desc-瘦身 04](../../thinking/2026-11/21/tool-desc-瘦身-1121/04-使用者已答.md)；要用 `self_tools add` 加回），共 30 支；不掛通用四包 look、change、delete（含 trash）、shell（11-11 晚使用者「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」、11-12「可以先定這樣，然後trash也拿掉。」）與 subagent、goal、todo（原話與代定見範本 README）；do_task 只給 agent-fsm，寫 `"do_task": null`；
              cli.json 沒寫 tools＝照 interfaces.json 的 tools 宣告用它，cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__peek_now_time…；帶 `--own <stack>/tools.json`，self_tools 加減工具後 aos-mcp 送 list_changed，同一輪就叫得到，使用者「3.同一輪就生效」）；不要工具就刪掉它
  tools_sub.json  子 agent 那台的登記檔：gadgets、json、index 三包裡不改東西的九支（peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_len、json_multi_get、index_view）
  interfaces.json  {"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json", "llm_keys": ["model", "reasoning_effort"], "history": "history.jsonl", "system": "system.txt"}, "hooks": [loop_hooks.json、eca/hooks.json、mcp/hooks.json 三個 {"$env": "AOS_HOME", "$path": …} 指示詞], "hookeds": "hookeds.json"}（hooks＝hook 點的宣告，只是參考；hookeds＝被勾清單；history 鍵給 aos-agent history 找檔；llm_keys：aos-agent llm set 不在上面的鍵照存＋warning；aos-agent ctl add 只看這個宣告）
  system.txt  兩段短文（自己是 aos agent、知識庫在 $AOS_HOME/knowledge/ 怎麼找），以 --append-system-prompt-file 接在 CLI 自己的系統提示後面；11-21 比照 agent-fsm 補知識庫路徑（線 top-1121-ecaeffort；之前範本沒有這個檔）
  hookeds.json  被勾清單（預設一格 timer：on_clock 每 300000 ms、handler py/tools/agent/hook_noop 什麼都不做；另一格 mail_notify：on_clock 每 60000 ms（使用者「每 1 分鐘」）、handler py/tools/agent/mail_notify，有新信才往 queue 寄一則 `[aos] new_mail: …`；stack 那份同名蓋過、null 關掉；`aos-agent hook` 管，見下「eca 的 hook」）
  screen/     子介面：_entry＝["aos-eca-screen", "--eca", ".."]（aos-agent open／close／watch 叫它；動作接在最後）
  README.md、_metainfo.json  首行一句話與 summary 一致；估時 cost.time_ms 60000、resource ["llm"]，沒有頂層 timeout_ms（讓 agent_def check 過）
```

**思考程度**（11-21 線 top-1121-ecaeffort；使用者「eca也都有跟上嗎？reasoning eff那些」）：`llm.json` 的 `reasoning_effort`＝claude 的 `--effort`，pi 身（[03](03-eca-pi.md)）＝`--thinking`。`aos-agent llm --target myproj set reasoning_effort=high`、`llm rm reasoning_effort` 回定義的值（範本沒寫＝CLI 自己的預設）。

| 身體 | 旗標 | 收的級別（出處） |
|---|---|---|
| claude | `--effort` | `low`、`medium`、`high`、`xhigh`、`max`（`claude --help`，2.1.330；[model-config](https://code.claude.com/docs/en/model-config)：模型不支援的級別往下退到它有的最高一級） |
| pi | `--thinking` | `off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`（`pi --help`，1.5.2；pi 的 `docs/cli.md`：超過模型能力的級別會被壓到模型有的） |
| codex | — | 沒接，寫了＝`CfgBad` |

- **只收那支 CLI 認得的名字**，其他（例 llm kernel 那邊才有的 `none`、claude 身寫 `off`）＝`CfgBad`：在認領信之前就停、信留在 queue，`aos-agent llm set` 改對或 `llm rm` 後下一輪照跑。兩支 CLI 遇到不認得的值都只印一行 warning、改用預設照跑（11-21 實測），aos 不讓它靜靜變回預設；也不替你換名字（`none` 不會變成 pi 的 `off`）。
- **什麼時候生效**：沒開畫面＝下一輪（每輪重讀 `llm.json`、重起 CLI）。畫面開著＝畫面是開的那一刻帶的旗標，改了要 `aos-agent close` 再 `open` 才換；不想關就在畫面裡打 CLI 自己的指令（claude `/effort high`、pi `/thinking`），那只算那個畫面，aos 不知道。
- **pi 的對話會記程度**：pi 把程度記在對話檔裡，`--thinking` 有給就蓋過；`llm rm reasoning_effort` 之後同一段對話照用上次記的程度（不是回 pi 的預設），開新對話（`/clear`）才回預設。claude 每輪是新行程、程度不跟著對話走，拿掉就回 CLI 的預設。
- `/status` 會多寫 `reasoning_effort X`（有設時）。

**實例＝定義 × 工作區**：工作區＝CLI 的 cwd（你的程式專案）；stack 預設 `<工作區>/.stack/`（掛 daemon 的在 daemon 給的 proc 的 stack），裡面長 `queue/`、`history.jsonl`、`ctl.json`、`state.json` 與 cli_session 的小格 `claude/`（`session.txt`、`transcripts/`…）。這隻自己改過的還有 tools 與 llm 覆蓋層（只存差異；路徑依 `interfaces.json` 的同名欄位，此範本是 `tools.json`、`llm.json`，K-6）（`aos-agent tools`／`llm`；`aos-agent llm --target myproj set model=haiku`＝下一題起 `--model haiku`，`reset` 回定義的 sonnet）。換定義的模型＝`aos-json set --str proto8/templates/eca-claude/llm.json#/model opus`。eca 的腦是 CLI 自己，不經 llm kernel（think-as-function 03 § 2）。

```sh
# PATH 要有 proto8/bin 的 aos-exec／aos-loop／aos-post／aos-daemon 與 aos-eca-turn、aos-eca-screen、aos-tools、aos-daemon-ctl、
# aos-mcp、aos-agent（source 過 "$AOS_HOME/env.sh" 就都在），還有 claude；AOS_DAEMON＝跑著的 daemon 的 $AOS_STACK
aos-agent ctl add --ws ~/code/myproj --name myproj proto8/templates/eca-claude
aos-agent say --target myproj 看一下 README 在講什麼 && aos-agent listen --target myproj
aos-agent ctl pause --target myproj  # 暫停：不餵下一則（新信留 queue/new/），粒度＝一則訊息
aos-agent open --target myproj       # 接上畫面（Ctrl-] 跳出）
aos-agent ctl rm myproj              # 拔掉、stack 留著（加 --purge 才連 stack 刪）
```

不掛 daemon、直接 `aos-exec --ws ~/code/myproj proto8/templates/eca-claude &` 跑的，aos-agent 不管：`aos-post send --ordered ~/code/myproj/.stack/queue` 寫信（stdin＝`{"role": "user", "content": 話}`）、看 `.stack/history.jsonl`、寫 `.stack/ctl.json` 停（`{"cmd": "pause"}`／`{"cmd": "stop"}`）。

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [05-commands/01](../../py/docs/05-commands/01-逐支說明.md)）。`--on-busy yield` 只管貼字那條路：畫面開著、信走 claude 的收件口（一封一個署名信封，11-13 [eca-a2a-notify](../../thinking/2026-11/13/eca-a2a-notify.md)）時不退讓，有人接在畫面上、正在跑一輪都照投，`loop.json` 不用改。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就放一份檔、aos-eca-turn 加 `--prompt 那個檔`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。**goal**（[thinking goal](../../thinking/2026-11/11/goal/README.md)）：queue 空、上一輪 CLI 答完了、`$AOS_STACK/goal.json` 是 active＝這輪的題目換成一則 `[aos] goal: …`（射後不理版也一樣：有 active 的 goal 就不收工）；這輪 CLI 自己的對話檔（`transcripts/`）裡叫了 `goal` 以外的工具＝計數歸零，連續 LIMIT 次（預設 10）沒進展＝goal 改 paused；codex 照同一套。

**沒開畫面時中途收信（`live_mail`，預設關；[wake-1114](../../thinking/2026-11/14/wake-1114.md)）**：`cli.json` 寫 `"live_mail": true`，非互動那條路的 `claude -p` 加 `--input-format stream-json --replay-user-messages`、stdin 先不關。aos-eca-turn 等回答時 queue 又來的信，照畫面那條路的規矩認領、過 before_queue，一封一行寫進 stdin（寫進去＝交出去：接進 history、收信、after_queue），模型在下一個工具空檔讀到；CLI 回 `isReplay` 表示那行被取走。看到 result、每行都被取走、沒有背景任務、又沒新信，才關 stdin 讓它收尾；result 之後還有行沒取走、30 秒沒動靜也關。回答＝這一輪每個 result，加上取走中途信之後、下一次用工具之前模型說的話，用空行接成 history 的一則。上限 `live_mail_cap`（預設 `{"letters": 5, "seconds": 300}`，格式錯＝`CfgBad`）；冷卻剛到期那一輪不投；slash 指令停在它前面。依 claude 2.1.325 實測。

**history 被改過＝開新對話**（[self-family](../../thinking/2026-11/10/self-family/README.md) ⑩，10-30 eca 09「停著時改 history 再繼續」的縮水版）：每輪 assistant 接進 history 後，把整份 history 的 sha256 寫進小格的 `.history_sum`；下一輪交出去前算出來不一樣（人用 `aos-agent history` 或直接改了）＝`drop_session`、開新的 claude 對話，題目前面照換台那套帶改過的 user／assistant 紀錄（上限 `reseed_bytes`），stderr 一行 `warning: history.jsonl was changed since the last turn; starting a new claude conversation that carries the changed record`。這一輪中間被改（claude 叫 `self_history`）＝`.history_sum` 寫 `edited`、下一輪照樣開新的。畫面開著時不換、只 warning。用法：`aos-agent history -t 名字 ls`、`rm 3-4`、`summarize 1-6 "…"`；原文搬到 stack 裡 `history_removed.jsonl`。

**slash 指令**（[eca-slash](../../thinking/2026-11/12/eca-slash.md)，使用者「eca就是會變成以他為主，aos體系要盡量跟上」）：畫面上打的照 CLI 自己的做，aos 跟上——對話 id 換了（`/clear`、`/resume`、codex 的 `/new`）畫面 hook 就改記 `session.txt`，`/clear` 連 history 一起清（claude 看 SessionStart source clear；codex 看換到的 thread 是不是剛開的——rollout 只有這一輪＝清、剛交出去的 user 留著，有舊輪數＝`/resume` 到別段、只跟 id；codex 自己開的 multi-agent 子 agent 也是一段 thread、講完也會叫 hook，它的對話檔第一行有 `parent_thread_id`，認得出來就不理——不換 `session.txt`、不清 history；`session.txt` 若已經記到子 agent 的 thread，下一輪非互動會改接它的主對話、stderr 一行 `warning: session.txt names a codex sub-agent thread …`）；claude 的 `/compact` 同一個 id、history 換成它的摘要一則（`[aos] summary: …`；原文都搬到 `history_removed.jsonl`）；codex 的 `/compact` 不給摘要文字，改成從它壓縮後留下的 `replacement_history` 撈出 user／assistant 的話（工具定義、developer 訊息、工具呼叫、它自己塞的 `<environment_context>` 這類都略過）當新 history，前面一則 `[aos] summary: … codex compacted …`；畫面上打的在下一輪看到 rollout 多一個 `compacted` 時補做（`.compact_seen` 記已跟上幾次），撈不到就不動；`/exit` 畫面關掉，下一句照常（非互動）答。`aos-agent say`／`chat` 送一封剛好是 `/clear`、`/compact`、`/status`、`/usage`、`/exit` 的信＝aos-eca-turn ⑭ 做出同樣的效果、回一則 `[aos] slash: …`；畫面開著時 `/clear`、`/compact` 直接打進畫面（正在答題就等下一輪）。`/goal …`（以 `/goal` 開頭就算，含 `/goal clear`、只打 `/goal` 查看）是 CLI 自己的 goal，跟 aos 的 `goal.json` 各管各的：畫面開著打進去；沒開＝claude 原樣交給它（`claude -p` 認得，但目標只活在那一次 `claude -p` 裡），codex exec 沒有 `/goal`、回一句請開畫面；`/status` 多一行 CLI 最後記下的 goal；經 aos 打進 codex 畫面的 `/goal 新目標` 若跳「Replace goal?」選單（已有 goal），aos 自動選「1. Replace current goal」，選單認不得就不按、回一句請人處理（人自己在畫面上打的不代按）。codex 身也有畫面（同一個 `screen/`：`aos-agent open` 開得起來、answer 照進 turns／history）。


**eca 的 hook：有哪些、沒有哪些**（[hook 圖紙 § 6](../../thinking/2026-11/10/self-family/hook/01-圖紙.md#6-eca-縮水版)，使用者「7.接受」縮水版）：腦在外面的 CLI，aos 只攔得到經過自己手的東西。

| 事件 | eca 有沒有 | 在哪 |
|---|---|---|
| `before_queue`（可改 content、可丟信）／`after_queue` | 有 | aos-eca-turn：讀出好信、交給 CLI 之前／信接進 history 之後 |
| `before_tool`（可改 arguments、可攔）／`after_tool`（可改結果） | 只有經 aos-mcp 叫的 aos 工具 | aos-mcp 的 tools/call（cli_session 起它時帶 `--hooks <定義>`） |
| `brain_failed` | 有（`name`＝`CliFailed`／`ReplyMissing`，交出去之後才算） | aos-eca-turn |
| `tool_added` | 有（看這隻生效的 aos 登記檔，交出去之前比一次） | aos-eca-turn |
| `after_start`／`after_stop` | 有 | loop.json 的 `on_start`／`on_stop` → `aos-hook fire --def` |
| `before_run`／`after_run`（每一輪前後；before_run 退 10＝跳過這輪） | loop.json 接了線才有（範本預設不接） | loop.json 的 `on_before_run`／`on_after_run` → `aos-hook fire --def` |
| `on_clock`（[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)） | 有（每輪最開頭判，冷卻中、退讓的那輪也判；到了才起 handler） | aos-eca-turn |
| `before_compact`（可改摘要指示、可交壓完補回的字、可攔）／`after_compact`（只告知） | 只有 claude 身、`cli.json` 掛了範本的 `compact_hook` 時（見下「壓縮前後的 hook 點」） | `compact_hook`（Claude Code 自己的 PreCompact／PostCompact hook）→ `aos-hook fire --def $AOS_CLI_DEF` |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos |

**壓縮前後的 hook 點**（11-21 線 top-1121-ecaeffort；使用者「compact的機制不管，但可以試試看提供相應的hook點」）：壓縮是 Claude Code 自己做的（`/compact` 或它自己快滿時），aos 不改它怎麼壓；範本的 `compact_hook` 掛在 Claude Code 給的三個時刻，其中兩個接成 aos 的點（宣告在 [py/aos/apps/eca/hooks.json](../../py/aos/apps/eca/hooks.json)，只是參考）。`compact_hook` 經 `aos-hook fire --def $AOS_CLI_DEF` 發，自己讀結果：第一個退 10 的攔下；退 0 的 stdout 物件依名字順序設 `instructions`／`restore`（每個 handler 拿同一份事件）；失敗的一行 warning：

| Claude Code 的 hook | aos 的點 | 欄位 | hook 能做什麼 |
|---|---|---|---|
| `PreCompact` | `before_compact` | `trigger`（`manual`＝/compact、`auto`＝CLI 自己壓）、`asked`（/compact 後面的字）、`instructions`（compact_hook 給 CLI 的摘要指示，起始是範本那段「要留什麼」）、`restore`（null） | 改 `instructions`（空字串＝不給）；交 `restore`（一段字，壓完接進對話）；退 10＝攔下，compact_hook 退 2，Claude Code 不壓 |
| `PostCompact` | `after_compact` | `trigger`、`summary`（Claude Code 寫好的摘要） | 只告知（Claude Code 的 PostCompact 沒有決定權） |
| `SessionStart`（matcher `compact`） | （不發） | | compact_hook 印提醒、`handoff.md`、`restore`（印一次就刪） |

- **補回的字為什麼在 `before_compact`**：11-21 實測 claude 2.1.330 的 `-p` `/compact`，`SessionStart`（compact）比 `PostCompact` 早跑，`PostCompact` 才交的字要等下一次壓縮才印得出來；所以 `restore` 在壓之前交、存在 `$AOS_STACK/claude/compact_restore.txt`，壓完由 `SessionStart` 印進壓縮後的對話（沒交或被攔＝刪掉上次留下的）。
- **摘要內容 hook 寫不了**：Claude Code 不讓 hook 給摘要（agent-fsm 規劃裡「換」那層在這裡做不到）；能調的是指示、能補的是 `restore`、能攔。
- **攔下 `/compact` 那封信**：實測 aos-eca-turn 照一般回答收（history 多 `/compact` 與一句「Compaction blocked by PreCompact hook: … compact blocked by hook 名: 那個 hook 的 stdout」），不算 `CliFailed`、不冷卻，history 沒被換成摘要。自動壓縮被攔：Claude Code 照它的規則跳過，或那次需要空間的請求失敗。
- **出錯不擋 Claude**：`AOS_HOME`、`AOS_CLI_DEF`、`AOS_STACK` 少一個就不發；`aos-hook` 起不來或報錯＝stderr 一行 warning、照沒有 hook 的樣子做。`cli.json` 裡這三個 hook 的 `timeout` 是 60 秒（以前 10 秒），hook 的 handler 各自的 `timeout_ms` 要在這之內。
- 畫面開著時在畫面裡壓、自動壓縮兩條路沒實測；pi、codex 不發這兩個點（pi 有自己的 `session_before_compact`／`session_compact` 外掛事件，這次沒接，見紀錄）。

hook 失敗（退 0／10 以外、逾時、起不來、stdout 不合）：能攔的點停下——`before_queue` 的＝`aos-eca-turn: error: HookFailed …` 退 1，信留在 `queue/cur/`、history 不動，修好照問；aos-mcp 裡 `before_tool` 的＝那次工具呼叫回錯（isError）給 CLI，不整支死。其他點＝一行 warning、照常。loop 的四個點照 aos-loop 的規矩（非 0＝loop 停，before_run 退 10＝跳過這輪）。

**長跑怎麼調**：`cli.json` 的 `print_flags` 預設 `--max-budget-usd 0.5`，是每次非互動 CLI 呼叫的美元上限；任務常因額度不足停下時再提高，想限制單次成本就降低。`cli.json.timeout_ms` 與 `loop.json.exec.timeout_ms` 範本都是 0＝不限時（11-15 起；以前 600000／900000。使用者 11-15：「AI一輪跑個二三十分鐘都很正常，eca也是可能長時間不回應，逾時這東西應該要默認爲0，也就是不限時間，除非是一些有特殊需求的。」；cli.json 沒寫 `timeout_ms` 也是不限時）。要上限才寫正整數毫秒：`cli.json` 那層限制 CLI 呼叫，`loop.json` 那層限制整次 aos-eca-turn，兩層都寫時外層要比內層長，讓它有時間收尾。不限時的時候一輪很久沒動靜（`live.jsonl`、`turns.jsonl`、`busy.txt`、對話 transcript 都沒在變）滿 10 分鐘就在 stack 寫 `quiet.json`（py/aos/agentlib/quiet.py；只標記、不殺不丟信），一有動靜或這輪結束就收掉。`loop.json.interval_ms` 預設 300，是每輪結束後等多久再看 queue；調大可減少空轉、但收信會較慢，調小則較快回應，不會增加同時跑的輪數。

## 子 agent 與 skill（11-12 晚 eca-task-subagent）

使用者 11-12 晚：「claude code cli自己本身有Task工具，可以的話幫我加入claude eca範本和定義中(Skill也加上)」「將aos mcp切成幾個，一個是給主agent用的，另一個是比較少功能的，給子agent用的」。調查、實測與代定在 [thinking 11-12 eca-task-subagent](../../thinking/2026-11/12/eca-task-subagent.md)。

- **開法**：`cli.json` 的 `--tools` 列 `Agent`（子 agent 工具；2.1.63 前叫 `Task`，舊名還認）與 `Skill`。dontAsk 下這兩支不必進 `--allowedTools`；子 agent 的權限照主對話的（Write、Edit、Bash、`mcp__aos…` 照白名單，其他照拒）。
- **不切的話**：claude 的子 agent 繼承主對話全部 MCP 工具，`mcp__aos__*` 整台都叫得到（含 self_ctl、mailbox_send 這類）。
- **切（`tools_sub`）**：`cli.json` 寫 `"tools_sub": "<登記檔>"`（寫法同 `tools`：相對從 `cli.json` 的資料夾算，也可寫指示詞；不是檔＝`ToolsMissing`）。cli_session 起 claude 時多帶三樣：
  1. `--agents`：蓋掉內建的 `general-purpose`——`disallowedTools: ["mcp__aos"]`（看不到主 agent 那台）、`mcpServers` 內嵌 `aos_sub`（`aos-mcp --ws <工作區> --stack <stack> [--hooks <定義>] [tools_flags…] <tools_sub 那份>`；只有這個子 agent 連得到，主對話的清單沒有它）。內建工具照繼承。
  2. `--allowedTools` 多 `mcp__aos_sub`（整台免問）。
  3. `--settings` 的 PreToolUse hook（matcher `mcp__aos__.*`，`cli_session.py guard`）：別的類型的子 agent（Explore、Plan、外掛帶的、使用者自己定義的）還看得到 `mcp__aos__*`，但 hook 輸入帶 `agent_id`＝子 agent 叫的＝擋下、回一句說明；主對話叫的不受影響。
- **子 agent 那台放什麼**（代定、可翻案）：只放 `_metainfo.side_effect` 是 false 而且講的不是「這隻 agent 自己」的——peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_len、json_multi_get、index_view 九支。不放：會改東西的 json_set／add／del／multi_set、self 一族、events、def、mailbox 三支（信箱是主 agent 的）。要加減＝改定義的 `tools_sub.json`。
- **不跟著變的**：這隻自己用 `self_tools` 加減的工具只進主 agent 那台（`aos_sub` 不帶 `--own`）；`aos-agent tools` 也只管主 agent 那份。外部 MCP server（`mcp_servers`）照 CLI 預設，子 agent 一樣繼承。
- **限制**：只有 claude 身（codex 寫了＝`CfgBad`）；`flags` 裡自己寫了 `--agents` 又寫 `tools_sub`＝`CfgBad`。子 agent 是 CLI 的黑盒子：它叫 `mcp__aos_sub__*` 照樣過 aos-mcp 的 `before_tool`／`after_tool` hook，其餘 aos 看不到。
- **skill**：claude 自己從工作區 `.claude/skills/`、帳號的 `~/.claude/skills/` 與外掛找；主對話與子 agent 都能用 `Skill` 叫。aos 不管 skill 放哪。

## 接外部 MCP server（11-12 external-mcp）

兩條路：**CLI 自己接**（本節前半）與**經 aos**（本節最後一段，凍結成一包 aos 工具）。一台選一條。

定義資料夾放一份 **server 檔**（一台一份，例 `mcp/teamsite.json`），`cli.json` 加 `"mcp_servers": ["mcp/teamsite.json"]`（相對從 `cli.json` 的資料夾算，也可寫指示詞；可列好幾份）。claude、codex 兩身都吃；CLI 自己連、自己列工具（不凍結說明），列了的那台整台免核准，`only`／`except` 挑工具。某一份壞了＝`cli_session: warning: external MCP server … skipped: …`，其他照接；stdio 的每次起 CLI 前還會先看指令找不找得到、能不能執行，不行＝同一種 warning（`… skipped: CommandMissing its command is not found or cannot be run: …`）跳過那台。claude 非互動那條若 CLI 開場回報某台沒連上，stderr 多一行 `warning: external MCP server X was not connected when claude started (status failed)`（回合照走；codex 沒有這種回報，起來之後才壞的看不到）。設計：[external-mcp 02](../../thinking/2026-11/12/external-mcp/02-設計.md)；程式：`py/aos/mcp_server_file.py`、`py/aos/apps/mcp_launch`。

**http（Bearer＋自簽 CA）**：

```json
{"description": "<一句話：這台是什麼>",
 "mcp_server": {"name": "<名字，小寫英數底線>", "transport": "http", "url": "https://<主機>:<埠>/mcp",
                "bearer_token_env": "<放 token 的變數名，例 TEAMSITE_TOKEN>",
                "env_file": "<token 檔的絕對路徑，例 /home/<你>/.config/<agent>/teamsite.env>",
                "ca_file": "<CA bundle 的絕對路徑（選填）>"}}
```

token 檔一行 `TEAMSITE_TOKEN=<值>`、權限 600，放定義與工作區以外。起 CLI 那一刻才讀：codex＝值只放進 codex 行程的環境、自動補 `shell_environment_policy.exclude`（腦的 shell 看不到）；claude＝走 `headersHelper`（值不進 claude 的環境）。`ca_file`＝codex 的 `SSL_CERT_FILE`／`CODEX_CA_CERTIFICATE`、claude 的 `NODE_EXTRA_CA_CERTS`。

**stdio**（經 `aos-mcp-launch` 起，`env_file` 整份只進 server 行程）：

```json
{"description": "<一句話>",
 "mcp_server": {"name": "<名字>", "transport": "stdio", "command": "<指令>", "args": ["<參數>"],
                "env": {"<明文變數>": "<值>"}, "env_file": "<金鑰檔的絕對路徑（選填）>", "only": ["<工具名>"]}}
```

`command` 與 `args` 的相對路徑都從 server 檔所在的資料夾算（server 就在那裡起；要工作區的路徑寫 `{"$env": "AOS_WS", "$path": "…"}`），經 aos 那條同一條規則。server 拿到起它那個行程的全部環境變數（claude 身與經 aos＝起樹那個殼的整份，殼裡的 API key 也在；codex 只帶 aos 給的幾個），使用者 11-12 裁不做白名單、風險自負。

腦看到的工具名＝`mcp__<名字>__<工具名>`。**秘密不要用 `aos-agent ctl add --envs` 給**（值明文寫進 `procs/<名>/exec.json`）。`aos-mcp-launch` 要在 PATH（`source "$AOS_HOME/env.sh"` 重 source 一次）。

**經 aos（凍結成一包工具）**：同一份 server 檔也可以先跑一次 `aos-mcp-import mcp/teamsite.json`（[README](../../py/aos/apps/mcp_import/README.md)），把工具凍結進檔裡，再疊進定義的 `tools.json`：`{"$override": [<原本的包…>, "mcp/teamsite.json"], "tools": {}}`。腦看到的是 aos 的工具 `teamsite_<工具名>`（eca 經 aos-mcp＝`mcp__aos__teamsite_<工具名>`；agent-fsm 也用得到，這條路不限 eca）。**先放好 server 檔、匯入過再疊**：`$override` 指到不在的檔＝整份登記讀不了（`PathMissing`）；還沒匯入的檔疊上去＝那一層沒有工具、不報錯。

| | 經 aos（`aos-mcp-import`＋`tools.json`） | CLI 自己接（`cli.json` 的 `mcp_servers`） |
|---|---|---|
| 工具說明 | 匯入那刻凍結；server 改了要 `aos-mcp-import sync`（`--yes` 才寫） | 每次起 CLI 照 server 當下的 |
| hook | `before_tool`／`after_tool` 攔得到（走 aos-mcp 或 agent-fsm 的 act） | 攔不到（CLI 自己叫） |
| 關掉單支 | `self_tools rm`、`aos-agent tools` 照一般工具 | 改 server 檔的 `only`／`except` |
| server 行程 | 每次叫起一台新的（http＝開一個新 session），叫完就收 | CLI 開著的期間一直連著 |
| 誰能用 | agent-fsm 與 eca 兩種身體 | 只有 eca（claude、codex） |
| http 金鑰 | 只收 Bearer，**一定要寫 `env_file`**（沒寫＝`PackBad`）；值只放進請求標頭 | 沒寫 `env_file` 時 codex 用行程本來繼承的變數 |

- **一台選一條**：兩條同時掛，腦會同時看到 `mcp__teamsite__x` 與 `mcp__aos__teamsite_x`，等於同一支工具兩個名字。
- **有狀態的 server**（瀏覽器、要先登入的）走 CLI 自己接：經 aos 每次都是新的一台，上一次的狀態不在。
- `env_file` 現在與 aos-tools 的 env 檔同讀法：dotenv 子集，支援 `${X}` 展開、行內 `#` 註解與嚴格成對引號；例如 `A=x # note` 讀成 `x`，接著 `B=${A}y` 讀成 `xy`。建議 `chmod 600`、放定義與工作區以外（兩條路都不檢查權限）。
- 家機有 proxy：http server 在區網或本機卻連不上，先設 `NO_PROXY=<主機>`（經 aos 那條用 Python `urllib`，照環境變數走 proxy）。
- 經 aos 的錯誤代號（`ServerFailed`、`ServerRejected`、`CallFailed`…）怎麼讀：knowledge `aos/cli/mcp_import.md#/Codes from external MCP tools`。
